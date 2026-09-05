"""Asking the companion a question, as opposed to letting it volunteer one.

`plan_turn`'s cadence was written for a companion that decides on its own
whether the room wants to hear from it. `POST /ai-turn` is also the path a
person takes to ask it something, and there the same rules produce a feature
that looks broken from outside.

Measured on a live stack (real PostgreSQL, real Gemini, `98b7b1b`) on
2026-08-30, in the order a person types:

    POST /messages  "Tối mai nhóm mình đi ăn rồi cà phê nhé"
    POST /ai-turn                 -> 200 spoke=true  itinerary card, 7.3s
    POST /messages  "Lên giúp lịch trình chi tiết từng giờ"
    POST /ai-turn                 -> 200 spoke=false reason=cooldown
    (45 seconds pass, ask again)
    POST /ai-turn                 -> 200 spoke=false reason=cooldown

The model was never called on the last two. That matters for what this file is
testing: the reported failure was read as the companion misunderstanding the
word "lịch trình", and it is not -- nothing ever reached the model to
misunderstand anything. The refusal happened two layers earlier, on wall-clock
time, and `spoke=false` with a reason the client renders as nothing at all is
indistinguishable from an outage.

So the route accepts an optional `requested` flag. What it must NOT do is
matter to a client that does not send it: the shipped app posts this route with
`Content-Type: application/json` and an empty body, and a body model that
rejects that would take the whole chat screen down. That case is first below,
because it is the one a green suite would most plausibly miss.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import anyio
import pytest

from app.api import companion_places
from app.api.deps import get_companion, get_repository
from app.api.main import create_app
from app.api.repository import (
    MembershipRecord,
    MessagePage,
    MessageRecord,
    PersonRecord,
)

from .conftest import SeedCatalogueReads, ASGITestClient

NOW = datetime(2030, 8, 27, 12, 0, tzinfo=UTC)
CONTEXT_ID = uuid.UUID("3cc00000-cccc-4ccc-8ccc-0000c0000009")
MEMBER_ID = uuid.UUID("4dd00000-dddd-4ddd-8ddd-0000d0000009")

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


class ConversationRepository(SeedCatalogueReads):
    """One group whose last two messages are the ones that trigger `cooldown`.

    The companion answered thirty seconds ago and a person has spoken since, so
    an unasked turn is refused on the clock. That is the exact state measured
    on the live stack, expressed as the smallest fixture that reaches it.
    """

    def __init__(self) -> None:
        self.conversation = (
            MessageRecord(
                id=uuid.uuid4(),
                context_id=CONTEXT_ID,
                author_id=MEMBER_ID,
                kind="text",
                body="Tối mai nhóm mình đi ăn rồi cà phê nhé",
                image_url=None,
                card=None,
                created_at=NOW - timedelta(minutes=1),
            ),
            MessageRecord(
                id=uuid.uuid4(),
                context_id=CONTEXT_ID,
                author_id=None,
                kind="ai_card",
                body=None,
                image_url=None,
                card=CARD,
                created_at=NOW - timedelta(seconds=30),
            ),
            MessageRecord(
                id=uuid.uuid4(),
                context_id=CONTEXT_ID,
                author_id=MEMBER_ID,
                kind="text",
                body="Lên giúp lịch trình chi tiết từng giờ",
                image_url=None,
                card=None,
                created_at=NOW - timedelta(seconds=10),
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


class CountingCompanion:
    """Records every call, so "refused before the model" is visible."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def reply(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return CARD


@pytest.fixture
def companion():
    return CountingCompanion()


@pytest.fixture
def client(monkeypatch, companion):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    monkeypatch.setattr(
        companion_places, "load_place_catalogue", lambda *_: list(CATALOGUE)
    )
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: ConversationRepository()
    app.dependency_overrides[get_companion] = lambda: companion
    return ASGITestClient(app)


def test_the_shipped_client_posting_no_body_at_all_still_gets_a_turn(client):
    """`apps/mobile/src/screens/chat/ai.ts` sends this exact request.

    It sets `Content-Type: application/json` and passes no `body:` to fetch, so
    the server receives that header over zero bytes. Making the flag required,
    or giving it a model FastAPI validates eagerly, turns every AI turn in the
    product into a 422 -- a break far larger than the bug being fixed, and one
    that a suite driving the route with a JSON body would never see.
    """

    response = client.post(
        f"/contexts/{CONTEXT_ID}/ai-turn",
        headers={**HEADERS, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["reason"] == "cooldown"


def test_a_turn_nobody_asked_for_is_still_refused_on_the_clock(client, companion):
    """The cadence survives. Without this the fix reads as "delete the rule"."""

    body = client.post(
        f"/contexts/{CONTEXT_ID}/ai-turn", headers=HEADERS, json={}
    ).json()

    assert body["spoke"] is False
    assert body["reason"] == "cooldown"
    assert companion.calls == []


def test_a_turn_the_person_asked_for_reaches_the_model_inside_the_cooldown(
    client, companion
):
    """The reported bug, at the route that produced it."""

    response = client.post(
        f"/contexts/{CONTEXT_ID}/ai-turn", headers=HEADERS, json={"requested": True}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["spoke"] is True
    assert body["reason"] == "ok"
    assert body["message"]["card"]["kind"] == "places"
    assert len(companion.calls) == 1


def test_asking_is_metered_by_the_same_window_as_volunteering(client):
    """`requested` must not be a way to buy model calls the ceiling forbids.

    Thirty a minute is the route's HTTP window; the flag does not widen it. A
    caller that could lift the ceiling by naming itself a request would leave
    the key with no ceiling at all, which is what the window exists for.
    """

    codes = [
        client.post(
            f"/contexts/{CONTEXT_ID}/ai-turn",
            headers=HEADERS,
            json={"requested": True},
        ).status_code
        for _ in range(31)
    ]

    assert codes[-1] == 429
    assert codes.count(200) == 30


def test_a_body_that_is_not_the_flag_is_refused_rather_than_ignored(client):
    """A misspelled key is a client that thinks it is asking for something.

    `{"request": true}` accepted as a no-op is a 200 that means the opposite of
    what the caller wrote, and the caller has no way to find out -- the same
    class of failure this whole file exists to remove.

    The value is checked the same way, but the bar is "not a boolean" rather
    than "not literally true/false". Measured on pydantic 2 in lax mode:
    `"yes"`, `"true"` and `1` become True, `"no"`/`"false"`/`0` become False,
    and `"maybe"`, `5`, `[]` and `null` are all refused. Every coercion it does
    make says what the caller said, so demanding a JSON literal here would buy
    nothing and would reject honest clients.
    """

    for body in ({"request": True}, {"requested": "maybe"}, {"requested": None}):
        assert (
            client.post(
                f"/contexts/{CONTEXT_ID}/ai-turn", headers=HEADERS, json=body
            ).status_code
            == 422
        ), body
