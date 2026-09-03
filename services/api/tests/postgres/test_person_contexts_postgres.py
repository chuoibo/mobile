"""The conversation list and the read mark, on the real repository and real HTTP.

The fake cannot express what these rows depend on: a membership row per state
with its own id, a keyset comparison on `(created_at, id)`, `DISTINCT ON` for
the newest message per group, and two check constraints on how a session was
minted. Every case here builds an application in `prod` auth mode and speaks
to it with a Bearer, the way the phone does.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import anyio
import httpx
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.api.service import token_digest
from app.db.models import (
    AccountSession,
    Context,
    Membership,
    MembershipOrigin,
    MembershipRole,
    MembershipState,
    Message,
    MessageKind,
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
    """Two people, three groups, and the friend who is the one asking."""

    def __init__(self, session: Session):
        self.session = session
        self.now = datetime.now(UTC)
        self.owner = Person(id=uuid.uuid4(), display_name="Minh Anh")
        self.friend = Person(id=uuid.uuid4(), display_name="Hà")
        session.add_all([self.owner, self.friend])
        session.flush()
        self.a = self._context("Hội đi Đà Lạt")
        self.b = self._context("Nhà 4 người")
        self.c = self._context("Nhóm cũ")
        self._member(self.a, self.owner, MembershipState.ACTIVE, MembershipRole.ADMIN)
        self._member(self.a, self.friend, MembershipState.ACTIVE)
        self._member(self.b, self.owner, MembershipState.ACTIVE, MembershipRole.ADMIN)
        self.invited = self._member(self.b, self.friend, MembershipState.INVITED)
        self._member(self.c, self.owner, MembershipState.ACTIVE, MembershipRole.ADMIN)
        self._member(self.c, self.friend, MembershipState.LEFT)
        session.flush()

    def _context(self, name: str) -> Context:
        context = Context(
            id=uuid.uuid4(), display_name=name, created_by_id=self.owner.id
        )
        self.session.add(context)
        self.session.flush()
        return context

    def _member(self, context, person, state, role=MembershipRole.MEMBER) -> Membership:
        row = Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=person.id,
            state=state,
            role=role,
            origin=MembershipOrigin.NAMED,
            invited_by_id=self.owner.id,
            joined_at=self.now if state == MembershipState.ACTIVE else None,
            left_at=self.now if state == MembershipState.LEFT else None,
        )
        self.session.add(row)
        return row

    def say(self, context, author, body: str, minutes: int) -> Message:
        row = Message(
            id=uuid.uuid4(),
            context_id=context.id,
            author_id=author.id,
            kind=MessageKind.TEXT,
            body=body,
            created_at=self.now + timedelta(minutes=minutes),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def session_for(self, person, issued_via: str = "otp") -> str:
        raw = f"tok-{uuid.uuid4().hex}"
        SqlAlchemyApiRepository(self.session).create_account_session(
            person_id=person.id,
            token_digest=token_digest(raw),
            issued_from_invite_id=None,
            expires_at=self.now + timedelta(days=1),
            now=self.now,
            issued_via=issued_via,
        )
        self.session.flush()
        return raw


def test_the_list_has_active_and_invited_rows_with_real_membership_ids(
    postgres_session: Session,
):
    session = postgres_session
    world = World(session)
    app = _prod_app(session)
    token = world.session_for(world.friend)

    response = _call(app, "GET", "/people/me/contexts", token=token)

    assert response.status_code == 200, response.text
    rows = {row["id"]: row for row in response.json()["contexts"]}
    assert set(rows) == {str(world.a.id), str(world.b.id)}
    assert rows[str(world.a.id)]["member_count"] == 2
    assert rows[str(world.b.id)]["member_count"] == 1
    assert rows[str(world.b.id)]["my_state"] == "invited"
    assert rows[str(world.b.id)]["membership_id"] == str(world.invited.id), (
        "đúng hàng membership thật, để POST /memberships/{id}/accept gọi được"
    )


def test_unread_is_a_keyset_over_other_peoples_messages_and_the_mark_is_forward_only(
    postgres_session: Session,
):
    session = postgres_session
    world = World(session)
    app = _prod_app(session)
    token = world.session_for(world.friend)
    first = world.say(world.a, world.owner, "Cuối tuần này đi Đà Lạt nhé", 1)
    world.say(world.a, world.friend, "Okiiii", 2)
    newest = world.say(world.a, world.owner, "Mình có quán bánh căn view đẹp", 3)

    listed = _call(app, "GET", "/people/me/contexts", token=token).json()["contexts"]
    a = next(row for row in listed if row["id"] == str(world.a.id))
    assert a["unread_count"] == 2
    assert a["last_message"]["id"] == str(newest.id)
    assert a["last_message"]["author_display_name"] == "Minh Anh"
    assert listed[0]["id"] == str(world.a.id), "nhóm có tin mới nhất đứng đầu"

    marked = _call(
        app,
        "PUT",
        f"/contexts/{world.a.id}/read-mark",
        token=token,
        json={"message_id": str(newest.id)},
    )
    assert marked.status_code == 200, marked.text
    assert marked.json()["unread_count"] == 0

    stale = _call(
        app,
        "PUT",
        f"/contexts/{world.a.id}/read-mark",
        token=token,
        json={"message_id": str(first.id)},
    )
    assert stale.json()["last_read_message_id"] == str(newest.id)

    # A fourth message arrives: exactly one unread, counted from the mark.
    world.say(world.a, world.owner, "Đi nhé?", 4)
    again = _call(app, "GET", "/people/me/contexts", token=token).json()["contexts"]
    assert next(r for r in again if r["id"] == str(world.a.id))["unread_count"] == 1


def test_a_message_of_another_group_is_a_404_and_a_non_member_a_403(
    postgres_session: Session,
):
    session = postgres_session
    world = World(session)
    app = _prod_app(session)
    token = world.session_for(world.friend)
    elsewhere = world.say(world.b, world.owner, "tin nhóm B", 1)
    private = world.say(world.a, world.owner, "tin nhóm A", 1)

    wrong_group = _call(
        app,
        "PUT",
        f"/contexts/{world.a.id}/read-mark",
        token=token,
        json={"message_id": str(elsewhere.id)},
    )
    assert wrong_group.status_code == 404, wrong_group.text

    # The friend is only INVITED to B: reading B's marks is not theirs yet.
    not_yet = _call(
        app,
        "PUT",
        f"/contexts/{world.b.id}/read-mark",
        token=token,
        json={"message_id": str(elsewhere.id)},
    )
    assert not_yet.status_code == 403, not_yet.text
    del private


def test_the_database_refuses_a_session_whose_provenance_contradicts_its_invite(
    postgres_session: Session,
):
    session = postgres_session
    world = World(session)
    session.begin_nested()
    with pytest.raises(IntegrityError):
        session.add(
            AccountSession(
                person_id=world.friend.id,
                token_digest=token_digest("x"),
                issued_from_invite_id=None,
                issued_via="invite",
                created_at=world.now,
                expires_at=world.now + timedelta(days=1),
            )
        )
        session.flush()
    session.rollback()
    session.begin_nested()
    with pytest.raises(IntegrityError):
        session.add(
            AccountSession(
                person_id=world.friend.id,
                token_digest=token_digest("y"),
                issued_from_invite_id=None,
                issued_via="magic-link",
                created_at=world.now,
                expires_at=world.now + timedelta(days=1),
            )
        )
        session.flush()
    session.rollback()
