"""`POST /contexts/{id}/ai-turn` over real HTTP, against real PostgreSQL.

The group-message surface has no dict-backed fake in this repo, and inventing
one for the companion would prove the least interesting half of the feature.
The interesting half is what the database is asked to store: a message with no
author, whose payload has to satisfy the `payload_matches_kind` check
constraint, written only on the turns where the companion was actually allowed
to speak. A fake repository accepts all of that unconditionally.

The Gemini backend IS faked here -- deliberately. What this file proves holds
whichever model is plugged in: that a refused card writes no row, that an
invented place is refused, that no field the contract did not name survives
into storage, and that nothing anybody typed reaches the log. Whether a real
model stays inside the catalogue is a different claim, needs a real call, and
lives in `tests/live/test_companion_gemini_live.py`.

Rows here are flushed, never committed; the session fixture rolls back, so the
shared schema keeps the row counts other files assert on.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

import anyio
import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_companion, get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import (
    Context,
    Expense,
    Membership,
    MembershipRole,
    MembershipState,
    Message,
    MessageKind,
    Person,
)

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

# A string nobody would produce by accident, planted in a message body so the
# privacy case can look for it everywhere output goes.
SECRET = "SENTINEL-rieng-tu-cua-nhom-khong-duoc-log"

# The conversation happened before the service clock reads `NOW`, so no message
# is in the future and none of them sit inside the companion's cooldown window.
CONVERSATION_START = NOW - timedelta(hours=2)

CATALOGUE = [
    {
        "id": "p-tiem-nuong",
        "name": "Tiệm Nướng Xóm Lào",
        "address": "27/1 Yersin, TP. Đà Lạt",
        "price_min_vnd": 200_000,
        "price_max_vnd": 250_000,
    },
    {
        "id": "p-cafe-suong",
        "name": "Cafe Sương Mai",
        "address": "12 Trần Phú, TP. Đà Lạt",
        "price_min_vnd": 40_000,
        "price_max_vnd": 90_000,
    },
]

GOOD_CARD = {
    "kind": "places",
    "payload": {"intro": "Tối nay ăn nướng nhé", "place_ids": ["p-tiem-nuong"]},
}


class FakeCompanion:
    """Records what it was handed; returns a canned card."""

    def __init__(self, card=None, error=None):
        self.card = card if card is not None else GOOD_CARD
        self.error = error
        self.calls: list[dict] = []

    def reply(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.card


def _http(session: Session, monkeypatch: pytest.MonkeyPatch, companion: FakeCompanion):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    monkeypatch.setattr(
        "app.api.companion_places.load_place_catalogue", lambda: list(CATALOGUE)
    )
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    app.dependency_overrides[get_companion] = lambda: companion
    return app


def _headers(person_id: uuid.UUID) -> dict[str, str]:
    return {"X-Actor-ID": str(person_id), "X-Actor-Roles": "member"}


def _group(session: Session) -> tuple[Context, Person, Person]:
    owner = Person(id=uuid.uuid4(), display_name="Nam")
    friend = Person(id=uuid.uuid4(), display_name="Linh")
    outsider = Person(id=uuid.uuid4(), display_name="Người lạ")
    session.add_all([owner, friend, outsider])
    session.flush()
    context = Context(
        id=uuid.uuid4(), display_name="Team Đà Lạt", created_by_id=owner.id
    )
    session.add(context)
    session.flush()
    for person in (owner, friend):
        session.add(
            Membership(
                id=uuid.uuid4(),
                context_id=context.id,
                person_id=person.id,
                state=MembershipState.ACTIVE,
                role=MembershipRole.MEMBER,
                joined_at=NOW,
            )
        )
    session.flush()
    return context, owner, outsider


def _say(session: Session, context: Context, author: Person | None, body: str) -> None:
    """Append one message, strictly later than every message before it.

    The timestamp is computed rather than fixed, and that is load-bearing. The
    feed orders by `(created_at DESC, id DESC)`, so messages sharing one
    timestamp are ordered by a random UUID4 -- and "who spoke last" is exactly
    what the speaking cap reads. Stamping every row with `NOW` made the
    already-spoke-last case pass or fail on which UUID happened to sort higher.

    Timestamps run backwards from `NOW` so the whole conversation sits in the
    past relative to the service clock, and well outside the cooldown window.
    """

    said_before = _message_count(session, context)
    session.add(
        Message(
            id=uuid.uuid4(),
            context_id=context.id,
            author_id=None if author is None else author.id,
            kind=MessageKind.AI_CARD if author is None else MessageKind.TEXT,
            body=None if author is None else body,
            card={"kind": "text", "payload": {"text": body}} if author is None else None,
            created_at=CONVERSATION_START + timedelta(minutes=said_before),
        )
    )
    session.flush()


def _message_count(session: Session, context: Context) -> int:
    return session.execute(
        select(func.count()).select_from(Message).where(Message.context_id == context.id)
    ).scalar_one()


def _turn(app, actor: uuid.UUID, context: Context) -> httpx.Response:
    async def call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.post(
                f"/contexts/{context.id}/ai-turn", headers=_headers(actor)
            )

    return anyio.run(call)


def test_a_stranger_cannot_make_another_groups_ai_speak(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, outsider = _group(postgres_session)
    _say(postgres_session, context, owner, "Tối nay đi đâu?")
    companion = FakeCompanion()

    response = _turn(_http(postgres_session, monkeypatch, companion), outsider.id, context)

    assert response.status_code == 403
    assert companion.calls == []
    assert _message_count(postgres_session, context) == 1


def test_the_companion_answers_with_a_card_authored_by_nobody(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, _ = _group(postgres_session)
    _say(postgres_session, context, owner, "Tối nay đi đâu mọi người?")

    response = _turn(
        _http(postgres_session, monkeypatch, FakeCompanion()), owner.id, context
    )

    assert response.status_code == 200
    body = response.json()
    assert body["spoke"] is True
    assert body["message"]["kind"] == "ai_card"
    assert body["message"]["author_id"] is None

    stored = postgres_session.execute(
        select(Message).where(Message.kind == MessageKind.AI_CARD, Message.context_id == context.id)
    ).scalar_one()
    assert stored.author_id is None
    assert stored.body is None
    assert stored.card["kind"] == "places"
    assert stored.card["payload"]["places"][0]["name"] == "Tiệm Nướng Xóm Lào"


def test_the_model_is_given_the_real_conversation_and_the_real_members(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """"Có ngữ cảnh nhóm thật" is not observable from the response body.

    A canned reply looks identical to a grounded one from the outside, so the
    only place this can be checked is what the service handed the model.
    """

    context, owner, _ = _group(postgres_session)
    _say(postgres_session, context, owner, "Mình muốn ăn nướng, ngân sách 250k/người")
    companion = FakeCompanion()

    _turn(_http(postgres_session, monkeypatch, companion), owner.id, context)

    assert len(companion.calls) == 1
    handed = companion.calls[0]
    transcript = str(handed["conversation"])
    assert "ăn nướng" in transcript
    assert {"Nam", "Linh"} <= {member["display_name"] for member in handed["members"]}
    assert [place["id"] for place in handed["places"]] == [
        "p-tiem-nuong",
        "p-cafe-suong",
    ]


def test_the_companion_that_spoke_last_stays_quiet_and_writes_nothing(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, _ = _group(postgres_session)
    _say(postgres_session, context, owner, "Đi đâu?")
    _say(postgres_session, context, None, "Gợi ý của AI")
    companion = FakeCompanion()
    before = _message_count(postgres_session, context)

    response = _turn(_http(postgres_session, monkeypatch, companion), owner.id, context)

    assert response.status_code == 200
    assert response.json() == {
        "context_id": str(context.id),
        "spoke": False,
        "reason": "already_spoke_last",
        "message": None,
    }
    assert companion.calls == [], "a capped turn must not spend a model call"
    assert _message_count(postgres_session, context) == before


def test_a_card_naming_an_invented_place_is_refused_and_writes_nothing(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, _ = _group(postgres_session)
    _say(postgres_session, context, owner, "Gợi ý chỗ ăn đi")
    companion = FakeCompanion(
        card={
            "kind": "places",
            "payload": {"intro": "Chỗ này ngon", "place_ids": ["p-quan-khong-co-that"]},
        }
    )
    before = _message_count(postgres_session, context)

    response = _turn(_http(postgres_session, monkeypatch, companion), owner.id, context)

    assert response.status_code == 200
    assert response.json()["spoke"] is False
    assert response.json()["reason"] == "ungrounded"
    assert _message_count(postgres_session, context) == before


def test_the_companion_cannot_write_money_into_the_group(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """It suggests; a person confirms. Nothing on this path may reach the ledger."""

    context, owner, _ = _group(postgres_session)
    _say(postgres_session, context, owner, "Chia tiền luôn đi")
    companion = FakeCompanion(
        card={
            "kind": "places",
            "payload": {
                "intro": "Mình chia luôn nhé",
                "place_ids": ["p-tiem-nuong"],
                "expense": {"total_vnd": 900_000, "payer_id": str(owner.id)},
                "amount_vnd": 900_000,
            },
        }
    )
    expenses_before = postgres_session.execute(
        select(func.count()).select_from(Expense)
    ).scalar_one()

    response = _turn(_http(postgres_session, monkeypatch, companion), owner.id, context)

    assert response.status_code == 200
    stored = postgres_session.execute(
        select(Message).where(Message.kind == MessageKind.AI_CARD, Message.context_id == context.id)
    ).scalar_one()
    assert set(stored.card["payload"]) == {"intro", "places"}
    assert "900000" not in str(stored.card).replace("_", "")
    assert (
        postgres_session.execute(select(func.count()).select_from(Expense)).scalar_one()
        == expenses_before
    ), "the companion turn must never create an expense"


def test_nothing_anybody_typed_reaches_the_log(
    postgres_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    context, owner, _ = _group(postgres_session)
    _say(postgres_session, context, owner, f"Chuyển vào {SECRET} nhé")
    companion = FakeCompanion()

    with caplog.at_level(logging.DEBUG):
        response = _turn(
            _http(postgres_session, monkeypatch, companion), owner.id, context
        )

    assert response.status_code == 200
    assert SECRET not in caplog.text
    assert SECRET not in response.text


def test_a_backend_failure_leaks_neither_the_conversation_nor_the_credential(
    postgres_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    """The exception text is the classic leak: it carries both at once."""

    context, owner, _ = _group(postgres_session)
    _say(postgres_session, context, owner, f"Chuyển vào {SECRET} nhé")
    companion = FakeCompanion(
        error=RuntimeError(f"400 Bad Request key=AIzaSyFAKE prompt={SECRET}")
    )
    before = _message_count(postgres_session, context)

    with caplog.at_level(logging.DEBUG):
        response = _turn(
            _http(postgres_session, monkeypatch, companion), owner.id, context
        )

    assert response.status_code == 200
    assert response.json()["spoke"] is False
    assert response.json()["reason"] == "unavailable"
    assert SECRET not in response.text and "AIzaSy" not in response.text
    assert SECRET not in caplog.text and "AIzaSy" not in caplog.text
    assert _message_count(postgres_session, context) == before
