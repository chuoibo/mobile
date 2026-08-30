"""How much of the project's model quota one identity may spend on the companion.

Two routes reach Gemini and were not metered:

``GET  /contexts/{id}/suggestion``  calls the model on **every** request. There
is no cache and no cadence rule in front of it, so a client that polls -- or a
loop -- spends one model call per request for as long as it runs.

``POST /contexts/{id}/ai-turn``     calls the model whenever ``plan_turn``
allows it. That rule is a conversation cadence, not a ceiling: it refuses while
the companion spoke last, and the caller lifts that refusal by posting one more
message. Two cheap requests per model call is not a cap.

``app/api/search_rate_limit.py`` was written for exactly this failure and its
own docstring said "two routes spend that quota and both are metered here" --
true when it was written, and these two arrived after it. The key it protects
is the one the demo runs on, and there is one of them.

What this file does NOT prove: that the ceilings are the right numbers, or that
they survive a second replica. The windows are per process and in memory, so
two API replicas mean twice the ceiling and a restart forgives everyone. That
is a blast-radius cap for a single-box demo, not a quota -- the same limit
`test_receipts_scan_rate_limit.py` states about the route it covers.

It also does not prove anything about ``GET /places``, which reaches Gemini
too and is bounded by a cache rather than a window.

That paragraph used to end "bounded already ... one call per place per process,
so a window there would be protecting something that is not exposed", and it
was wrong -- measured on `d4bf672`, 25 requests bought 25 model calls as soon
as one row's reason was dropped. The cache stored successes only, so a row the
model would not answer was indistinguishable from one nobody had asked about.
See `tests/api/test_places_reason_retry_storm.py`; the bound is real now, and
it is a cooldown, not a window.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import anyio
import pytest

from app.api import companion_places
from app.api.deps import get_companion, get_repository, get_suggester
from app.api.main import create_app
from app.api.repository import (
    MembershipRecord,
    MemoryPage,
    MessagePage,
    MessageRecord,
    OutingRecord,
    PersonRecord,
    RecapOutingRecord,
)
from app.api.routes.messages import get_companion_turn_limiter
from app.api.routes.suggestions import get_suggestion_limiter
from app.api.search_rate_limit import (
    COMPANION_TURN_LIMIT_PER_WINDOW,
    SUGGESTION_LIMIT_PER_WINDOW,
    FixedWindowLimiter,
)
from app.domain.suggestion import SUGGESTION_KIND

from .conftest import ASGITestClient

NOW = datetime(2030, 8, 27, 12, 0, tzinfo=UTC)
CONTEXT_ID = uuid.UUID("3cc00000-cccc-4ccc-8ccc-0000c0000001")
MEMBER_ID = uuid.UUID("4dd00000-dddd-4ddd-8ddd-0000d0000001")

# Two entries, invented here rather than read from the shipped catalogue: what
# is under test is a counter, and a test that also depends on which places the
# product ships would go red the day somebody edits a seed file.
CATALOGUE = [
    {
        "id": "p-tiem-nuong",
        "name": "Tiệm Nướng Xóm Lào",
        "address": "27/1 Yersin, TP. Đà Lạt",
        "price_min_vnd": 200_000,
        "price_max_vnd": 250_000,
        "rating": 4.7,
        "distance_km": 1.2,
        "open_hours": "10:00 – 22:30",
        "category": "quan-an-local",
    },
    {
        "id": "p-cafe-suong",
        "name": "Cafe Sương Mai",
        "address": "12 Trần Phú, TP. Đà Lạt",
        "price_min_vnd": 40_000,
        "price_max_vnd": 90_000,
        "rating": 4.5,
        "distance_km": 0.8,
        "open_hours": "07:00 – 22:00",
        "category": "cafe",
    },
]

COMPANION_CARD = {
    "kind": "places",
    "payload": {"intro": "Tối nay ăn nướng nhé", "place_ids": ["p-tiem-nuong"]},
}

SUGGESTION_CARD = {
    "kind": SUGGESTION_KIND,
    "payload": {
        "title": "Tối thứ Bảy: nướng rồi cà phê",
        "when_text": "Tối thứ Bảy tuần này",
        "stops": [
            {
                "place_id": "p-tiem-nuong",
                "time_text": "18:00",
                "note": "Đi sớm cho kịp chỗ ngoài trời",
                "reason": "Nhóm hay ăn quán local, vừa ngân sách",
                "verdict": "hop",
            }
        ],
    },
}

HEADERS = {"X-Actor-ID": str(MEMBER_ID), "X-Actor-Roles": "member"}


def other_actor() -> dict[str, str]:
    return {"X-Actor-ID": str(uuid.uuid4()), "X-Actor-Roles": "member"}


class StubRepository:
    """Only the reads these two workflows make, and nothing else.

    The shared fake in `conftest.py` knows nothing about messages, trips or the
    memory wall, and teaching it those would be a much larger change than the
    counter under test. What this stands in for is narrow: one group, one human
    line already said, one finished trip behind it -- the smallest state in
    which **both** routes reach the model on every single request.

    Every request reaching the model is the property that makes this file able
    to fail. `create_message` deliberately does not append to what
    `list_messages` returns: if it did, the companion's own card would be the
    last message, `plan_turn` would answer `already_spoke_last`, and the burst
    would stop after one call whether a limiter existed or not. Every case here
    would then be green against an unmetered app. The cadence rule is real and
    is tested in `tests/domain/test_companion.py`; holding it open here is what
    isolates the ceiling.
    """

    def __init__(self) -> None:
        self.conversation = (
            MessageRecord(
                id=uuid.uuid4(),
                context_id=CONTEXT_ID,
                author_id=MEMBER_ID,
                kind="text",
                body="Tối nay đi đâu nhỉ?",
                image_url=None,
                card=None,
                created_at=NOW - timedelta(minutes=5),
            ),
        )

    def is_member(self, context_id, person_id):
        del person_id
        return context_id == CONTEXT_ID

    def list_messages(self, context_id, limit):
        del context_id, limit
        return MessagePage(messages=self.conversation, has_more=False)

    def list_members(self, context_id):
        del context_id
        return [
            MembershipRecord(
                id=uuid.uuid4(),
                context_id=CONTEXT_ID,
                person_id=MEMBER_ID,
                display_name="Hà",
                state="active",
                role="member",
                origin="founder",
                invited_by_id=None,
                joined_at=NOW,
                left_at=None,
                created_at=NOW,
            )
        ]

    def get_person(self, person_id):
        return PersonRecord(id=person_id, display_name="Hà", created_at=NOW)

    def create_message(self, **fields):
        return MessageRecord(
            id=uuid.uuid4(),
            context_id=fields["context_id"],
            author_id=fields["author_id"],
            kind=fields["kind"],
            body=fields["body"],
            image_url=fields["image_url"],
            card=fields["card"],
            created_at=fields["now"],
        )

    def group_recap(self, context_id, *, today):
        del today
        return [
            RecapOutingRecord(
                outing=OutingRecord(
                    id=uuid.uuid4(),
                    context_id=context_id,
                    created_by_id=MEMBER_ID,
                    title="Đà Lạt cuối tuần",
                    starts_on=(NOW - timedelta(days=6)).date(),
                    ends_on=(NOW - timedelta(days=4)).date(),
                    headcount=4,
                    budget_per_person_vnd=300_000,
                    created_at=NOW - timedelta(days=7),
                    stops=(),
                ),
                in_progress=False,
                split_total_vnd=520_000,
                expense_count=1,
                memory_count=0,
            )
        ]

    def list_memories(self, context_id, *, limit, kind):
        del context_id, limit, kind
        return MemoryPage(memories=(), has_more=False)


class CountingCompanion:
    """Records every call, so a refusal that still paid can be seen."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def reply(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return COMPANION_CARD


class CountingSuggester:
    """Same job on the other route."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, history, places) -> dict:
        del places
        self.calls.append(history)
        return SUGGESTION_CARD


@pytest.fixture
def companion():
    return CountingCompanion()


@pytest.fixture
def suggester():
    return CountingSuggester()


@pytest.fixture
def client(monkeypatch, companion, suggester):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    monkeypatch.setattr(
        companion_places, "load_place_catalogue", lambda: list(CATALOGUE)
    )
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: StubRepository()
    app.dependency_overrides[get_companion] = lambda: companion
    app.dependency_overrides[get_suggester] = lambda: suggester
    return ASGITestClient(app)


def turn(client, headers=None):
    return client.post(
        f"/contexts/{CONTEXT_ID}/ai-turn",
        headers=HEADERS if headers is None else headers,
    )


def suggestion(client, headers=None):
    return client.get(
        f"/contexts/{CONTEXT_ID}/suggestion",
        headers=HEADERS if headers is None else headers,
    )


def install(client, dependency, code, message, limit=3):
    """A three-per-window ceiling, so a burst is three calls and not thirty."""

    limiter = FixedWindowLimiter(
        limit=limit, window_seconds=60, code=code, message=message
    )
    client.app.dependency_overrides[dependency] = lambda: limiter
    return limiter


@pytest.fixture
def metered_turns(client):
    return install(
        client, get_companion_turn_limiter, "turn_rate_limited", "Too many turns."
    )


@pytest.fixture
def metered_suggestions(client):
    return install(
        client, get_suggestion_limiter, "suggestion_rate_limited", "Too many cards."
    )


# ---------------------------------------------------------------------------
# The unmetered state this file was opened for: every request reaches the model
# ---------------------------------------------------------------------------


def test_without_a_ceiling_every_turn_in_a_burst_reaches_the_model(client, companion):
    """The premise, asserted rather than assumed.

    If the conversation cadence already stopped a burst, a window on this route
    would be protecting nothing and the cases below would prove only that a
    counter counts. It does not: with the caller still talking, `plan_turn`
    says `ok` every time.
    """

    for _ in range(5):
        assert turn(client).json()["spoke"] is True

    assert len(companion.calls) == 5


def test_without_a_ceiling_every_suggestion_in_a_burst_reaches_the_model(
    client, suggester
):
    for _ in range(5):
        assert suggestion(client).json()["suggested"] is True

    assert len(suggester.calls) == 5


# ---------------------------------------------------------------------------
# POST /contexts/{id}/ai-turn
# ---------------------------------------------------------------------------


def test_a_burst_of_companion_turns_from_one_person_is_cut_off(client, metered_turns):
    for _ in range(3):
        assert turn(client).status_code == 200

    assert turn(client).status_code == 429


def test_the_refused_turns_are_the_ones_that_never_reach_the_model(
    client, companion, metered_turns
):
    """The assertion that makes the gate worth having.

    The point is not the status code, it is that the model call did not happen.
    A 429 raised after the companion answered has spent exactly what it refused.
    """

    for _ in range(6):
        turn(client)

    assert len(companion.calls) == 3


def test_a_refused_turn_names_the_companion_and_not_search_or_scans(client):
    """The refusal names the thing that was refused.

    `FixedWindowLimiter` takes its code and sentence from the caller precisely
    so a third and fourth route cannot answer with `search_rate_limited`, which
    would tell the person -- and the client branching on the code -- about a
    feature they were not using.
    """

    for _ in range(COMPANION_TURN_LIMIT_PER_WINDOW):
        turn(client)
    body = turn(client).json()

    assert body["code"] == "companion_turn_rate_limited"
    assert "search" not in body["detail"].lower()
    assert "scan" not in body["detail"].lower()


def test_the_turn_cut_off_is_per_person_not_a_switch_that_silences_the_group(
    client, metered_turns
):
    """A single global counter would make one person's loop everyone's outage."""

    for _ in range(3):
        assert turn(client).status_code == 200

    assert turn(client, headers=other_actor()).status_code == 200
    assert turn(client).status_code == 429


# ---------------------------------------------------------------------------
# GET /contexts/{id}/suggestion
# ---------------------------------------------------------------------------


def test_a_burst_of_suggestions_from_one_person_is_cut_off(client, metered_suggestions):
    for _ in range(3):
        assert suggestion(client).status_code == 200

    assert suggestion(client).status_code == 429


def test_the_refused_suggestions_are_the_ones_that_never_reach_the_model(
    client, suggester, metered_suggestions
):
    for _ in range(6):
        suggestion(client)

    assert len(suggester.calls) == 3


def test_a_refused_suggestion_names_suggestions(client):
    for _ in range(SUGGESTION_LIMIT_PER_WINDOW):
        suggestion(client)
    body = suggestion(client).json()

    assert body["code"] == "suggestion_rate_limited"
    assert "search" not in body["detail"].lower()
    assert "scan" not in body["detail"].lower()


def test_the_suggestion_cut_off_is_per_person(client, metered_suggestions):
    for _ in range(3):
        assert suggestion(client).status_code == 200

    assert suggestion(client, headers=other_actor()).status_code == 200
    assert suggestion(client).status_code == 429


# ---------------------------------------------------------------------------
# The two windows, and the two that already existed
# ---------------------------------------------------------------------------


def test_spending_the_turn_ceiling_leaves_the_suggestion_ceiling_whole(client):
    """The two routes are metered apart, and this is the only case saying so.

    Every other case here stays green if both routes count into ONE window:
    turns alone still stop at their ceiling, cards alone still stop at theirs.
    A shared window is visible only when one identity uses both -- and then
    somebody who chatted with the companion opens the group's home screen and
    is refused a suggestion in a sentence about a feature they were not using.

    Same argument, and the same shape, as
    `test_spending_the_search_ceiling_leaves_the_scan_ceiling_whole`.
    """

    turn_codes = [
        turn(client).status_code for _ in range(COMPANION_TURN_LIMIT_PER_WINDOW + 1)
    ]

    assert turn_codes[-1] == 429
    assert suggestion(client).status_code == 200


def test_the_shipped_routes_meter_without_any_test_installing_a_limiter(
    client, companion, suggester
):
    """Every case above that installs its own limiter stays green if the app
    ships with none. These two spend the real ceilings.
    """

    turn_codes = [
        turn(client).status_code for _ in range(COMPANION_TURN_LIMIT_PER_WINDOW + 1)
    ]
    card_codes = [
        suggestion(client).status_code for _ in range(SUGGESTION_LIMIT_PER_WINDOW + 1)
    ]

    assert turn_codes == [200] * COMPANION_TURN_LIMIT_PER_WINDOW + [429]
    assert card_codes == [200] * SUGGESTION_LIMIT_PER_WINDOW + [429]
    assert len(companion.calls) == COMPANION_TURN_LIMIT_PER_WINDOW
    assert len(suggester.calls) == SUGGESTION_LIMIT_PER_WINDOW


def test_each_application_carries_its_own_companion_windows(client):
    """A module-level limiter would make a suite's colour depend on its order.

    Measured, not argued: `app.api.main.app` is a module-level singleton, so a
    window hung there is shared by every test in the session that imports it.
    """

    other = create_app()

    assert (
        client.app.state.companion_turn_limiter
        is not other.state.companion_turn_limiter
    )
    assert client.app.state.suggestion_limiter is not other.state.suggestion_limiter


def test_every_paid_route_carries_its_own_window(client):
    """One object per route, not one object with six names.

    The cheapest way to "add" a limiter is to hand the new routes an object
    that already existed. Every ceiling assertion above survives that, because
    each route alone still stops somewhere.
    """

    state = client.app.state
    windows = {
        id(state.search_limiter),
        id(state.receipt_scan_limiter),
        id(state.chat_expense_limiter),
        id(state.screenshot_scan_limiter),
        id(state.companion_turn_limiter),
        id(state.suggestion_limiter),
    }

    assert len(windows) == 6
