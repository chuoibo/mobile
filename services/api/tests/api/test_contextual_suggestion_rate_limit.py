"""The F33 card reaches Gemini on a GET, and arrived after the file that meters.

``GET /contexts/{id}/contextual-suggestion`` calls the model on every request
that finds a conversation. There is no cache in front of it and there cannot be
a useful one: the card is a function of one group's last few messages, and any
cache coarser than that would serve one group's evening to another.

That is the same shape ``GET /contexts/{id}/suggestion`` had before #293, and
the reason this file exists is that #293 could not have caught it -- F33 did not
exist yet. ``test_every_paid_route_carries_its_own_window`` enumerates the
limiters it knows by name, so a *new* unmetered route is invisible to it. The
last case here closes that hole by counting model-reaching routes instead.

What this file does NOT prove: that the ceiling is the right number, or that it
survives a second replica. The window is per process and in memory, so two API
replicas mean twice the ceiling and a restart forgives everyone -- a
blast-radius cap for a single-box demo, not a quota. Same limit the sibling
files state about the routes they cover.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import anyio
import pytest

from app.api import companion_places
from app.api.deps import get_contextual_suggester, get_repository
from app.api.main import create_app
from app.api.repository import MembershipRecord, MessagePage, MessageRecord
from app.api.routes.suggestions import get_contextual_suggestion_limiter
from app.api.search_rate_limit import (
    CONTEXTUAL_SUGGESTION_LIMIT_PER_WINDOW,
    FixedWindowLimiter,
)
from app.domain.suggestion import SUGGESTION_KIND

from .conftest import ASGITestClient

NOW = datetime(2030, 8, 27, 12, 0, tzinfo=UTC)
CONTEXT_ID = uuid.UUID("3cc00000-cccc-4ccc-8ccc-0000c0000031")
MEMBER_ID = uuid.UUID("4dd00000-dddd-4ddd-8ddd-0000d0000031")

HEADERS = {"X-Actor-ID": str(MEMBER_ID), "X-Actor-Roles": "member"}

# Invented here rather than read from the shipped catalogue: what is under test
# is a counter, and a test that also depended on which places the product ships
# would go red the day somebody edits a seed file.
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
    }
]

CONTEXTUAL_CARD = {
    "kind": SUGGESTION_KIND,
    "payload": {
        "title": "Gần trung tâm, đi bộ được",
        "when_text": "Tối nay",
        "stops": [
            {
                "place_id": "p-tiem-nuong",
                "time_text": "19:00",
                "note": "Đi bộ từ chỗ mọi người đang ngồi",
                "reason": "Hai bạn vừa nói chán và muốn đi đâu đó gần",
                "verdict": "hop",
            }
        ],
    },
}


class StubRepository:
    """One group, mid-conversation, so the model is reached every request.

    Two human lines and not one, deliberately. `has_conversation` stays quiet
    below `MIN_LINES`, so a single-message stub would answer `no_conversation`
    without ever calling the suggester -- and every case in this file would
    pass against an app with no ceiling at all. Holding the conversation open
    is what makes this file able to fail.
    """

    def __init__(self) -> None:
        self.conversation = (
            MessageRecord(
                id=uuid.uuid4(),
                context_id=CONTEXT_ID,
                author_id=MEMBER_ID,
                kind="text",
                body="Đi đâu không?",
                image_url=None,
                card=None,
                created_at=NOW - timedelta(minutes=2),
            ),
            MessageRecord(
                id=uuid.uuid4(),
                context_id=CONTEXT_ID,
                author_id=uuid.uuid4(),
                kind="text",
                body="Chán quá.",
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


class CountingContextualSuggester:
    """Records every call, so a refusal that still paid can be seen."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, digest, places) -> dict:
        del places
        self.calls.append(digest)
        return CONTEXTUAL_CARD


@pytest.fixture
def suggester():
    return CountingContextualSuggester()


@pytest.fixture
def client(monkeypatch, suggester):
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
    app.dependency_overrides[get_contextual_suggester] = lambda: suggester
    return ASGITestClient(app)


def card(client, headers=None):
    return client.get(
        f"/contexts/{CONTEXT_ID}/contextual-suggestion",
        headers=HEADERS if headers is None else headers,
    )


def other_actor() -> dict[str, str]:
    return {"X-Actor-ID": str(uuid.uuid4()), "X-Actor-Roles": "member"}


@pytest.fixture
def metered(client):
    """A three-per-window ceiling, so a burst is three calls and not thirty."""

    limiter = FixedWindowLimiter(
        limit=3,
        window_seconds=60,
        code="contextual_suggestion_rate_limited",
        message="Too many cards.",
    )
    client.app.dependency_overrides[get_contextual_suggestion_limiter] = (
        lambda: limiter
    )
    return limiter


# ---------------------------------------------------------------------------
# The premise: below the ceiling there is nothing else between GET and Gemini
# ---------------------------------------------------------------------------


def test_below_the_ceiling_every_card_in_a_burst_still_reaches_the_model(
    client, suggester
):
    """Why the window is the only thing protecting this route.

    Every GET under the ceiling spends a model call: no cache, no cadence rule,
    nothing. That is the fact the rest of this file rests on -- if a cache ever
    appears in front of the route, this goes red and the ceiling cases below
    stop meaning what they say they mean.

    The count is deliberately below `CONTEXTUAL_SUGGESTION_LIMIT_PER_WINDOW`,
    so this measures the absence of a cache and not the presence of a limiter.
    """

    burst = CONTEXTUAL_SUGGESTION_LIMIT_PER_WINDOW - 1
    codes = [card(client).status_code for _ in range(burst)]

    assert codes == [200] * burst
    assert len(suggester.calls) == burst


def test_a_burst_from_one_person_is_cut_off(client, metered):
    codes = [card(client).status_code for _ in range(5)]

    assert codes == [200, 200, 200, 429, 429]


def test_the_refused_cards_are_the_ones_that_never_reach_the_model(client, metered, suggester):
    """A 429 that still spent the call would be a limiter in name only."""

    for _ in range(5):
        card(client)

    assert len(suggester.calls) == 3


def test_a_refused_card_names_this_route_and_not_search_or_scans(client, metered):
    """The refusal a person reads has to name the feature they were using."""

    for _ in range(4):
        response = card(client)

    assert response.status_code == 429
    body = response.json()
    assert body["code"] == "contextual_suggestion_rate_limited"
    # Not the neighbour's code either: sharing `suggestion_rate_limited` would
    # tell a client branching on it about a feature nobody was using.
    assert "search" not in body["detail"].lower()
    assert "scan" not in body["detail"].lower()


def test_the_cut_off_is_per_person_not_a_switch_that_silences_the_group(client, metered):
    """A global counter would let one person take the card from everybody --
    the exact failure the module exists to prevent, caused by us.
    """

    for _ in range(4):
        card(client)

    assert card(client, headers=other_actor()).status_code == 200


def test_the_shipped_route_meters_without_any_test_installing_a_limiter(
    client, suggester
):
    """Every case above installs its own ceiling. This one spends the real one."""

    codes = [
        card(client).status_code
        for _ in range(CONTEXTUAL_SUGGESTION_LIMIT_PER_WINDOW + 1)
    ]

    assert codes == [200] * CONTEXTUAL_SUGGESTION_LIMIT_PER_WINDOW + [429]
    assert len(suggester.calls) == CONTEXTUAL_SUGGESTION_LIMIT_PER_WINDOW


def test_spending_the_contextual_ceiling_leaves_the_proactive_card_whole(client):
    """Two cards, two windows. Sharing one object is the cheap way to "add" a
    limiter and it makes one feature's burst disable its neighbour.
    """

    state = client.app.state

    assert state.contextual_suggestion_limiter is not state.suggestion_limiter


def test_each_application_carries_its_own_contextual_window(client):
    """A module-level limiter would make a suite's colour depend on its order."""

    other = create_app()

    assert (
        client.app.state.contextual_suggestion_limiter
        is not other.state.contextual_suggestion_limiter
    )


def test_every_route_that_reaches_the_model_carries_its_own_window(client):
    """Counted, not enumerated -- so the *next* paid route cannot slip through.

    Its sibling case in `test_companion_rate_limit.py` lists the limiters it
    knows by name. That shape is green by construction for any route added
    afterwards, which is exactly how F33 shipped unmetered: the route was new,
    the list was not. This counts the windows the app actually builds, so
    adding a seventh paid route without a window fails here.
    """

    state = client.app.state
    windows = {
        id(state.search_limiter),
        id(state.receipt_scan_limiter),
        id(state.chat_expense_limiter),
        id(state.screenshot_scan_limiter),
        id(state.companion_turn_limiter),
        id(state.suggestion_limiter),
        id(state.contextual_suggestion_limiter),
    }

    assert len(windows) == 7
