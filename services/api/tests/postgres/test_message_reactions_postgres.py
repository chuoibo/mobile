"""Reactions on the real repository, real HTTP, `prod` auth mode (M3).

What only PostgreSQL can show: the unique index turns two hearts from one
person into one row and the route into an idempotent 201; the CHECK refuses a
kind the closed set does not know; a page of messages loads its reactions in
one query and each reader sees their own `mine`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import anyio
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.api.service import token_digest
from app.db.models import (
    Context,
    Membership,
    MembershipOrigin,
    MembershipRole,
    MembershipState,
    Message,
    MessageKind,
    MessageReaction,
    Person,
)

pytestmark = pytest.mark.postgres


def _prod_app(session: Session):
    app = create_app(auth_mode="prod")
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def _call(app, method: str, path: str, *, token: str, json=None):
    async def go():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.request(
                method, path, json=json, headers={"Authorization": f"Bearer {token}"}
            )

    return anyio.run(go)


class World:
    def __init__(self, session: Session):
        self.session = session
        self.now = datetime.now(UTC)
        self.a = Person(id=uuid.uuid4(), display_name="An")
        self.b = Person(id=uuid.uuid4(), display_name="Bình")
        session.add_all([self.a, self.b])
        session.flush()
        self.group = Context(
            id=uuid.uuid4(), display_name="Hội", created_by_id=self.a.id
        )
        session.add(self.group)
        session.flush()
        for person, role in (
            (self.a, MembershipRole.ADMIN),
            (self.b, MembershipRole.MEMBER),
        ):
            session.add(
                Membership(
                    id=uuid.uuid4(),
                    context_id=self.group.id,
                    person_id=person.id,
                    state=MembershipState.ACTIVE,
                    role=role,
                    origin=MembershipOrigin.NAMED,
                    invited_by_id=self.a.id,
                    joined_at=self.now,
                )
            )
        self.message = Message(
            id=uuid.uuid4(),
            context_id=self.group.id,
            author_id=self.a.id,
            kind=MessageKind.TEXT,
            body="đi thôi",
            created_at=self.now,
        )
        session.add(self.message)
        session.flush()

    def session_for(self, person) -> str:
        raw = f"tok-{uuid.uuid4().hex}"
        SqlAlchemyApiRepository(self.session).create_account_session(
            person_id=person.id,
            token_digest=token_digest(raw),
            issued_from_invite_id=None,
            expires_at=self.now + timedelta(days=1),
            now=self.now,
            issued_via="otp",
        )
        self.session.flush()
        return raw


def test_two_hearts_from_one_person_are_one_row_and_each_reader_sees_mine(
    postgres_session,
):
    world = World(postgres_session)
    app = _prod_app(postgres_session)
    an, binh = world.session_for(world.a), world.session_for(world.b)
    path = f"/contexts/{world.group.id}/messages/{world.message.id}/reactions"

    first = _call(app, "POST", path, token=an, json={"kind": "heart"})
    again = _call(app, "POST", path, token=an, json={"kind": "heart"})
    assert (first.status_code, again.status_code) == (201, 201), (
        first.text,
        again.text,
    )
    theirs = _call(app, "POST", path, token=binh, json={"kind": "heart"})
    fire = _call(app, "POST", path, token=binh, json={"kind": "fire"})
    assert theirs.status_code == 201 and fire.status_code == 201
    rows = postgres_session.scalars(
        select(MessageReaction).where(MessageReaction.message_id == world.message.id)
    ).all()
    assert sorted((r.person_id, r.kind) for r in rows) == sorted(
        [(world.a.id, "heart"), (world.b.id, "heart"), (world.b.id, "fire")]
    )

    as_an = _call(app, "GET", f"/contexts/{world.group.id}/messages", token=an).json()
    assert as_an["messages"][0]["reactions"] == [
        {"kind": "heart", "count": 2, "mine": True},
        {"kind": "fire", "count": 1, "mine": False},
    ]
    as_binh = _call(
        app, "GET", f"/contexts/{world.group.id}/messages", token=binh
    ).json()
    assert as_binh["messages"][0]["reactions"] == [
        {"kind": "heart", "count": 2, "mine": True},
        {"kind": "fire", "count": 1, "mine": True},
    ]

    gone = _call(app, "DELETE", f"{path}/heart", token=an)
    assert gone.status_code == 200
    assert gone.json()["reactions"] == [
        {"kind": "heart", "count": 1, "mine": False},
        {"kind": "fire", "count": 1, "mine": False},
    ]


def test_the_database_refuses_an_unknown_kind_and_a_duplicate(postgres_session):
    world = World(postgres_session)
    postgres_session.add(
        MessageReaction(message_id=world.message.id, person_id=world.a.id, kind="heart")
    )
    postgres_session.flush()
    # The same heart from the same person: the unique index, not the route.
    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(
                MessageReaction(
                    message_id=world.message.id, person_id=world.a.id, kind="heart"
                )
            )
            postgres_session.flush()
    # A kind outside the closed set: the CHECK, whatever the route validates.
    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(
                MessageReaction(
                    message_id=world.message.id, person_id=world.b.id, kind="poop"
                )
            )
            postgres_session.flush()
