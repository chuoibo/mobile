"""Every way `POST /contexts/{id}/ai-turn` can stay silent, named at the wire.

The client has to say *why* the companion said nothing. `spoke=false` rendered
as blank is the failure `test_companion_requested_turn.py` was opened for: a
refusal on wall-clock time looked exactly like an outage, and a person read it
as the model not understanding the word "lịch trình".

So the reasons are a contract, and this file is where it is written down. Two
things are pinned:

1.  Each reason is reachable **through HTTP** and arrives spelled exactly as
    below. A string asserted only against `plan_turn` proves the domain agrees
    with itself, not that the route ships it.
2.  The vocabulary is **closed and complete**. The set is read back out of the
    source with `ast` rather than retyped here, because a hand-written list
    does not know what it is missing: a new reason added to `plan_turn` with no
    copy behind it would ship as a blank screen and no test would notice.

What is deliberately NOT pinned as distinct, and is the answer to "can the
client tell these apart":

*   `unavailable` is every model-backend failure -- provider quota exhausted,
    missing key, network, timeout, garbage response. `GeminiCompanion.reply`
    throws away the provider exception on purpose (its text carries both the
    API key and the group's own words), and one string is what survives. A
    client cannot distinguish "Gemini said 429" from "we have no key".
*   there is no reason for "did not understand the request". The prompt tells
    the model to answer with a text card when nothing in the catalogue fits, so
    a misunderstood question comes back `spoke=true` with a text card. Silence
    is never how not-understood is reported.
"""

from __future__ import annotations

import ast
import pathlib
import uuid
from datetime import UTC, datetime, timedelta

import anyio
import pytest

from app.api import companion_places, service
from app.api.deps import get_companion, get_repository
from app.api.main import create_app
from app.api.repository import (
    MembershipRecord,
    MessagePage,
    MessageRecord,
    PersonRecord,
)
from app.domain import companion as companion_domain
from app.domain.companion import CompanionError

from .conftest import SeedCatalogueReads, ASGITestClient

NOW = datetime(2030, 8, 27, 12, 0, tzinfo=UTC)
CONTEXT_ID = uuid.UUID("3cc00000-cccc-4ccc-8ccc-00000000f16a")
MEMBER_ID = uuid.UUID("4dd00000-dddd-4ddd-8ddd-00000000f16a")

HEADERS = {"X-Actor-ID": str(MEMBER_ID), "X-Actor-Roles": "member"}

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

CARD = {
    "kind": "places",
    "payload": {"intro": "Tối nay ăn nướng nhé", "place_ids": ["p-tiem-nuong"]},
}

#: The whole client-visible vocabulary of this route's ``reason`` field.
#: ``test_no_reason_ships_without_a_name_here`` re-derives it from the source,
#: so adding one without adding copy is a red test rather than a blank screen.
REASONS = {
    "ok",
    "no_conversation",
    "already_spoke_last",
    "cooldown",
    "rate_limited",
    "asked_too_often",
    "unavailable",
    "ungrounded",
}


def _human(seconds_ago: int) -> MessageRecord:
    return MessageRecord(
        id=uuid.uuid4(),
        context_id=CONTEXT_ID,
        author_id=MEMBER_ID,
        kind="text",
        body="Đi Đà Lạt 2 ngày 1 đêm, 8 người, budget 2 triệu/người",
        image_url=None,
        card=None,
        created_at=NOW - timedelta(seconds=seconds_ago),
    )


def _ai(seconds_ago: int) -> MessageRecord:
    return MessageRecord(
        id=uuid.uuid4(),
        context_id=CONTEXT_ID,
        author_id=None,
        kind="ai_card",
        body=None,
        image_url=None,
        card=CARD,
        created_at=NOW - timedelta(seconds=seconds_ago),
    )


class ConversationRepository(SeedCatalogueReads):
    """A group whose message history the test poses into each refusal state."""

    def __init__(self, conversation: tuple[MessageRecord, ...]) -> None:
        self.conversation = conversation

    def is_member(self, context_id, person_id):
        del person_id
        return context_id == CONTEXT_ID

    def list_messages(self, context_id, limit):
        del context_id, limit
        return MessagePage(messages=tuple(reversed(self.conversation)), has_more=False)

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


class ScriptedCompanion:
    """Answers with a fixed card, or raises a fixed backend failure."""

    def __init__(self, answer=None, raises: Exception | None = None) -> None:
        self._answer = CARD if answer is None else answer
        self._raises = raises
        self.calls = 0

    def reply(self, **kwargs):
        del kwargs
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._answer


@pytest.fixture
def turn(monkeypatch):
    """Drive one `/ai-turn` against a posed history and a scripted model."""

    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr(service, "_now", lambda: NOW)
    monkeypatch.setattr(
        companion_places, "load_place_catalogue", lambda: list(CATALOGUE)
    )

    def take(conversation, *, companion=None, requested=False):
        app = create_app()
        app.dependency_overrides[get_repository] = lambda: ConversationRepository(
            tuple(conversation)
        )
        app.dependency_overrides[get_companion] = lambda: (
            companion if companion is not None else ScriptedCompanion()
        )
        response = ASGITestClient(app).post(
            f"/contexts/{CONTEXT_ID}/ai-turn",
            headers=HEADERS,
            json={"requested": requested},
        )
        assert response.status_code == 200, response.text
        return response.json()

    return take


def test_a_grounded_answer_is_reason_ok(turn):
    body = turn([_human(60)])

    assert body["spoke"] is True
    assert body["reason"] == "ok"


def test_a_group_that_has_said_nothing_is_reason_no_conversation(turn):
    """Not courtesy: with nothing said there is nothing to answer."""

    body = turn([])

    assert body["spoke"] is False
    assert body["reason"] == "no_conversation"


def test_speaking_twice_in_a_row_is_reason_already_spoke_last(turn):
    """The companion answered last and nobody has replied. Cadence, not a cap.

    The newest AI message is older than the cooldown, so this is the rule under
    test rather than the clock one below.
    """

    body = turn([_human(600), _ai(300)])

    assert body["spoke"] is False
    assert body["reason"] == "already_spoke_last"


def test_answering_inside_ninety_seconds_is_reason_cooldown(turn):
    """The state qa2 measured on F16: a person spoke, the AI spoke 30s ago."""

    body = turn([_human(120), _ai(30), _human(10)])

    assert body["spoke"] is False
    assert body["reason"] == "cooldown"


def test_the_same_turn_asked_for_is_not_refused_on_the_clock(turn):
    """`cooldown` is only ever a reason for a turn nobody asked for.

    Pinned here because it decides the client's copy: the string the frontend
    must write words for arrives only when it did not set `requested`.
    """

    body = turn([_human(120), _ai(30), _human(10)], requested=True)

    assert body["spoke"] is True
    assert body["reason"] == "ok"


def test_the_window_ceiling_unasked_is_reason_rate_limited(turn):
    body = turn([_human(600), _ai(500), _ai(400), _ai(300), _human(200)])

    assert body["spoke"] is False
    assert body["reason"] == "rate_limited"


def test_the_window_ceiling_when_asked_is_reason_asked_too_often(turn):
    """A different name on purpose: a question the person asked was dropped.

    A client sorting reasons into "the AI chose to stay quiet" and "your
    question did not get answered" cannot file this one under silence.
    """

    body = turn(
        [_human(600), _ai(500), _ai(400), _ai(300), _human(200)], requested=True
    )

    assert body["spoke"] is False
    assert body["reason"] == "asked_too_often"


def test_a_card_that_names_a_place_we_do_not_have_is_reason_ungrounded(turn):
    """The anti-fabrication boundary, seen from the wire."""

    invented = {
        "kind": "places",
        "payload": {"intro": "", "place_ids": ["p-khong-co-trong-catalogue"]},
    }
    companion = ScriptedCompanion(answer=invented)

    body = turn([_human(60)], companion=companion)

    assert body["spoke"] is False
    assert body["reason"] == "ungrounded"
    assert companion.calls == 1


@pytest.mark.parametrize(
    ("label", "failure"),
    [
        # What `GeminiCompanion.reply` raises when GEMINI_API_KEY is absent.
        ("no key", CompanionError("COMPANION_NOT_CONFIGURED")),
        # What it raises for a provider 429 -- the paid quota is gone. The
        # adapter keeps only `type(exc).__name__`, so this is the whole signal.
        ("provider quota exhausted", RuntimeError("ClientError")),
        ("provider outage", RuntimeError("ServerError")),
        ("provider answered non-JSON", RuntimeError("JSONDecodeError")),
    ],
)
def test_every_backend_failure_collapses_into_one_reason_unavailable(
    turn, label, failure
):
    """The gap, pinned rather than described.

    Four different causes, one string. "Hết lượt gọi model" is not something a
    client can say, because by the time the reason is chosen the difference has
    already been dropped on purpose: provider exception text carries the API
    key and the group's own prompt often enough that keeping it is the classic
    leak. Telling these apart needs a code chosen *before* that redaction, and
    no such code exists today.
    """

    body = turn([_human(60)], companion=ScriptedCompanion(raises=failure))

    assert body["spoke"] is False, label
    assert body["reason"] == "unavailable", label


def _function(path: pathlib.Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _reason_sources(path: pathlib.Path, name: str) -> tuple[set[str], list[str]]:
    """Split a function's `reason` values into the strings it can name, and the
    expressions this reader cannot follow.

    Both shapes the two layers use are covered: the domain returns
    ``{"reason": ...}`` and the service passes ``reason=...``. Neither is always
    a bare literal -- the window ceiling picks its name with a conditional and
    binds it to a local first -- so simple local assignments are resolved.

    The unresolved half is returned rather than dropped, and that is the point.
    A reader that silently skipped what it could not parse would report a
    complete-looking vocabulary while a whole branch shipped an unnamed string;
    the first draft of this helper did exactly that and missed two of eight.
    """

    target = _function(path, name)
    assignments: dict[str, list[ast.expr]] = {}
    for node in ast.walk(target):
        if isinstance(node, ast.Assign):
            for bound in node.targets:
                if isinstance(bound, ast.Name):
                    assignments.setdefault(bound.id, []).append(node.value)

    resolved: set[str] = set()
    unresolved: list[str] = []

    def visit(node: ast.expr) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            resolved.add(node.value)
        elif isinstance(node, ast.IfExp):
            visit(node.body)
            visit(node.orelse)
        elif isinstance(node, ast.Name) and node.id in assignments:
            for value in assignments[node.id]:
                visit(value)
        else:
            unresolved.append(ast.unparse(node))

    for node in ast.walk(target):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if isinstance(key, ast.Constant) and key.value == "reason":
                    visit(value)
        elif isinstance(node, ast.keyword) and node.arg == "reason":
            visit(node.value)

    return resolved, unresolved


def test_no_reason_ships_without_a_name_here():
    """The vocabulary is closed, and this file knows the whole of it.

    Read back out of the source instead of retyped, so a reason added to
    `plan_turn` or to `take_companion_turn` without client copy fails here
    rather than shipping as a `spoke=false` the screen renders as nothing.
    """

    domain_named, _ = _reason_sources(
        pathlib.Path(companion_domain.__file__), "plan_turn"
    )
    service_named, _ = _reason_sources(
        pathlib.Path(service.__file__), "take_companion_turn"
    )

    assert domain_named | service_named == REASONS


def test_the_only_reason_the_reader_cannot_name_is_the_forwarded_one():
    """Everything `_reason_sources` gave up on, listed, so nothing hides there.

    The route re-emits `plan_turn`'s answer under a subscript, which no source
    reader can resolve to a string -- and that is fine precisely because it is
    the domain's own value, already counted above. Any *second* unreadable
    expression would be a name the vocabulary test cannot see, so it fails here
    instead of shipping as a screen that renders nothing.
    """

    _, domain_unresolved = _reason_sources(
        pathlib.Path(companion_domain.__file__), "plan_turn"
    )
    _, service_unresolved = _reason_sources(
        pathlib.Path(service.__file__), "take_companion_turn"
    )

    assert domain_unresolved == []
    assert service_unresolved == ["decision['reason']"]
