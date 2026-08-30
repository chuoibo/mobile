"""A member has a name, and the roster is where a client can read it.

`memberships.person_id` is a foreign key into `people`, and `people.display_name`
is `NOT NULL`. So for every row the roster returns, the database already holds
the name -- the read model simply dropped it between the table and the wire.

That gap is not cosmetic. The only screens that could name anybody were the ones
carrying a hardcoded list of seven demo people; the first real human to join
through `POST /contexts` or through an invite link arrived on the chat screen as
a hexadecimal string, because a UUID was the only thing the API ever said about
them.

Both layers are asserted here on purpose. The service test proves the join
happens; the HTTP test proves the field survives the response model. A response
model that drops a field leaves every service test green -- this repo has
shipped that failure before.
"""

from __future__ import annotations

import uuid

import anyio
import httpx
import pytest
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.api.schemas import MembershipInviteRequest
from app.api.service import ApiService
from app.db.models import (
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    Person,
)

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

ROLES = frozenset({"member", "group_admin"})


def _actor(person_id: uuid.UUID, context_id: uuid.UUID | None = None) -> Actor:
    return Actor(
        id=person_id,
        roles=ROLES,
        context_ids=frozenset({context_id} if context_id else set()),
    )


def _headers(person_id: uuid.UUID) -> dict[str, str]:
    return {"X-Actor-ID": str(person_id), "X-Actor-Roles": "member,group_admin"}


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _group(session: Session, owner: Person) -> Context:
    context = Context(
        id=uuid.uuid4(), display_name="Nhóm ăn tối", created_by_id=owner.id
    )
    session.add(context)
    session.flush()
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=owner.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.ADMIN,
            joined_at=NOW,
        )
    )
    session.flush()
    return context


def _http(session: Session, monkeypatch: pytest.MonkeyPatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def test_the_roster_names_every_member_it_returns(postgres_session: Session):
    """Two people, two names, and neither of them is a UUID."""
    owner = _person(postgres_session, "Nam")
    friend = _person(postgres_session, "Hà")
    context = _group(postgres_session, owner)
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=friend.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
        )
    )
    postgres_session.flush()
    service = ApiService(SqlAlchemyApiRepository(postgres_session))

    listed = service.list_context_members(context.id, _actor(owner.id, context.id))

    assert {row.person_id: row.display_name for row in listed.members} == {
        owner.id: "Nam",
        friend.id: "Hà",
    }


def test_two_members_who_registered_different_names_stay_apart(
    postgres_session: Session,
):
    """The failure this replaces collapsed everybody into one placeholder.

    A roster that answers "Thành viên" twice is a roster that cannot be used to
    pick who owes what, which is the one job it has on the bill screen.
    """
    owner = _person(postgres_session, "Nam")
    first = _person(postgres_session, "Hà")
    second = _person(postgres_session, "Linh")
    context = _group(postgres_session, owner)
    for person in (first, second):
        postgres_session.add(
            Membership(
                id=uuid.uuid4(),
                context_id=context.id,
                person_id=person.id,
                state=MembershipState.ACTIVE,
                role=MembershipRole.MEMBER,
                joined_at=NOW,
            )
        )
    postgres_session.flush()
    service = ApiService(SqlAlchemyApiRepository(postgres_session))

    names = [
        row.display_name
        for row in service.list_context_members(
            context.id, _actor(owner.id, context.id)
        ).members
    ]

    assert sorted(names) == ["Hà", "Linh", "Nam"]


def test_an_invited_member_is_named_in_the_answer_that_invites_them(
    postgres_session: Session,
):
    """The invite response is a membership row too, and the client shows it
    before it ever reloads the roster."""
    owner = _person(postgres_session, "Nam")
    friend = _person(postgres_session, "Hà")
    context = _group(postgres_session, owner)
    service = ApiService(SqlAlchemyApiRepository(postgres_session))

    invited = service.invite_context_member(
        context.id,
        MembershipInviteRequest(person_id=friend.id),
        _actor(owner.id, context.id),
    )

    assert invited.display_name == "Hà"


def test_the_members_route_puts_the_name_on_the_wire(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Measured where the bug was measured: the JSON a phone actually parses."""
    owner = _person(postgres_session, "Nam")
    friend = _person(postgres_session, "Hà")
    context = _group(postgres_session, owner)
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=friend.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
        )
    )
    postgres_session.flush()
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(
                f"/contexts/{context.id}/members", headers=_headers(owner.id)
            )

    listed = anyio.run(exchange)

    assert listed.status_code == 200, listed.text
    rows = listed.json()["members"]
    assert {row["person_id"]: row["display_name"] for row in rows} == {
        str(owner.id): "Nam",
        str(friend.id): "Hà",
    }
    # No row may answer with the id it is meant to explain. That string on a
    # screen is the whole defect being fixed here.
    assert all(row["display_name"] != row["person_id"] for row in rows)


# --- who may read the roster -------------------------------------------
#
# Adding names to this route also decided what leaks when its guard fails: the
# answer went from a list of UUIDs to a list of the real people in a group.
# Across the whole suite this route had only ever answered 200, so the
# `is_group_member` check in `list_context_members` was load-bearing and
# untested -- and so was the rule its comment states, that a former member is
# refused. Both cases below trip the guard rather than describe it.


def _read_members(app, context_id: uuid.UUID, reader: Person):
    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(
                f"/contexts/{context_id}/members", headers=_headers(reader.id)
            )

    return anyio.run(exchange)


def test_a_stranger_cannot_read_a_groups_roster(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Naming a context id is not membership in it."""
    owner = _person(postgres_session, "Nam")
    stranger = _person(postgres_session, "Người lạ")
    context = _group(postgres_session, owner)
    app = _http(postgres_session, monkeypatch)

    listed = _read_members(app, context.id, stranger)

    assert listed.status_code == 403, listed.text
    assert "Nam" not in listed.text


def test_someone_who_left_stops_reading_the_roster(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The rule `list_context_members` documents, held by a test.

    A guard that asks only whether a membership row exists passes the stranger
    case above and still fails this one, which is why they are separate.
    """
    owner = _person(postgres_session, "Nam")
    former = _person(postgres_session, "Hà")
    context = _group(postgres_session, owner)
    membership = Membership(
        id=uuid.uuid4(),
        context_id=context.id,
        person_id=former.id,
        state=MembershipState.LEFT,
        role=MembershipRole.MEMBER,
        joined_at=NOW,
        left_at=NOW,
    )
    postgres_session.add(membership)
    postgres_session.flush()
    app = _http(postgres_session, monkeypatch)

    listed = _read_members(app, context.id, former)

    assert listed.status_code == 403, listed.text
    assert "Nam" not in listed.text
