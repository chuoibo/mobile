"""Real PostgreSQL evidence for the F24 point lookup used by the route."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.api.repository import SqlAlchemyApiRepository
from app.db.models import Context, Message, MessageKind, Person

NOW = datetime(2030, 8, 30, 8, 0, tzinfo=UTC)


def test_chat_expense_get_message_reads_the_stored_author_and_text(
    postgres_session: Session,
) -> None:
    author = Person(id=uuid.uuid4(), display_name="Người trả")
    postgres_session.add(author)
    postgres_session.flush()
    context = Context(
        id=uuid.uuid4(),
        display_name="Nhóm đi sân bay",
        created_by_id=author.id,
    )
    postgres_session.add(context)
    postgres_session.flush()
    message = Message(
        id=uuid.uuid4(),
        context_id=context.id,
        author_id=author.id,
        kind=MessageKind.TEXT,
        body="Tao trả Grab 180k rồi nhé.",
        created_at=NOW,
    )
    postgres_session.add(message)
    postgres_session.flush()
    postgres_session.expire_all()

    record = SqlAlchemyApiRepository(postgres_session).get_message(message.id)

    assert record is not None
    assert record.id == message.id
    assert record.context_id == context.id
    assert record.author_id == author.id
    assert record.kind == "text"
    assert record.body == "Tao trả Grab 180k rồi nhé."


def test_chat_expense_get_message_returns_none_for_an_unknown_id(
    postgres_session: Session,
) -> None:
    assert SqlAlchemyApiRepository(postgres_session).get_message(uuid.uuid4()) is None
