"""Reading one group back out of PostgreSQL, and who is allowed to.

The fake repository answers `get_context` from a dict, which proves the route
and the permission call are wired together and proves nothing about SQL. This
layer runs the real `SELECT` against the migrated schema, and -- more to the
point -- decides membership from `memberships.state` in the database rather than
from a set a test populated by hand.

The distinction matters here because the refusal is the security half. A group
id is exactly the kind of value that travels in a share link, so "holds the id"
must not be "may read the group".
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.api.deps import Actor
from app.api.errors import ApiProblem
from app.api.repository import SqlAlchemyApiRepository
from app.api.schemas import ContextCreateRequest
from app.api.service import ApiService
from app.db.models import (
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    Person,
)

NOW = datetime(2030, 8, 29, 9, 0, tzinfo=UTC)
ROLES = frozenset({"member", "group_admin"})


def _actor(person_id: uuid.UUID, context_id: uuid.UUID | None = None) -> Actor:
    return Actor(
        id=person_id,
        roles=ROLES,
        context_ids=frozenset({context_id} if context_id else set()),
    )


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _service(session: Session) -> ApiService:
    return ApiService(SqlAlchemyApiRepository(session))


def _join(session: Session, context_id, person_id, state=MembershipState.ACTIVE):
    membership = Membership(
        id=uuid.uuid4(),
        context_id=context_id,
        person_id=person_id,
        state=state,
        joined_at=NOW,
        left_at=NOW if state is MembershipState.LEFT else None,
        role=MembershipRole.MEMBER,
    )
    session.add(membership)
    session.flush()
    return membership


def test_a_group_created_through_the_api_can_be_read_back_by_its_id(
    postgres_session: Session,
):
    """`POST /contexts` hands back an id once. Without this, that is the only
    moment the name and the id are ever in the same place."""
    owner = _person(postgres_session, "Nam")
    service = _service(postgres_session)
    created = service.create_context(
        ContextCreateRequest(display_name="Hội đi Đà Lạt"), _actor(owner.id)
    )

    read = service.get_context(created.id, _actor(owner.id, created.id))

    assert read.id == created.id
    assert read.display_name == "Hội đi Đà Lạt"
    assert read.created_by_id == owner.id
    assert read.created_at == created.created_at


def test_an_invited_member_reads_the_same_name_as_the_creator(
    postgres_session: Session,
):
    """Membership, not authorship, is the predicate -- a link recipient who
    joined is exactly the caller this route exists for."""
    owner = _person(postgres_session, "Nam")
    friend = _person(postgres_session, "Hà")
    service = _service(postgres_session)
    created = service.create_context(
        ContextCreateRequest(display_name="Hội đi Đà Lạt"), _actor(owner.id)
    )
    _join(postgres_session, created.id, friend.id)

    read = service.get_context(created.id, _actor(friend.id, created.id))

    assert read.display_name == "Hội đi Đà Lạt"


def test_a_person_who_never_joined_is_refused_the_group_name(
    postgres_session: Session,
):
    outsider = _person(postgres_session, "Người lạ")
    owner = _person(postgres_session, "Nam")
    service = _service(postgres_session)
    created = service.create_context(
        ContextCreateRequest(display_name="Hội đi Đà Lạt"), _actor(owner.id)
    )

    with pytest.raises(ApiProblem) as caught:
        # The context id is passed in `context_ids` on purpose: the header is
        # written by a gateway on behalf of the caller and can claim anything.
        # The database row is what must refuse.
        service.get_context(created.id, _actor(outsider.id, created.id))

    assert caught.value.status_code == 403


def test_someone_who_left_the_group_stops_being_able_to_read_it(
    postgres_session: Session,
):
    """`is_member` reads `state`, so a `LEFT` row is the case that distinguishes
    "has a membership row" from "is a member". Same rule the roster applies."""
    owner = _person(postgres_session, "Nam")
    former = _person(postgres_session, "Hà")
    service = _service(postgres_session)
    created = service.create_context(
        ContextCreateRequest(display_name="Hội đi Đà Lạt"), _actor(owner.id)
    )
    _join(postgres_session, created.id, former.id, state=MembershipState.LEFT)

    with pytest.raises(ApiProblem) as caught:
        service.get_context(created.id, _actor(former.id, created.id))

    assert caught.value.status_code == 403


def test_the_group_name_is_read_from_the_row_and_not_from_the_request(
    postgres_session: Session,
):
    """A rename through the database has to reach the reader.

    Without this, a service that echoed back whatever it was handed at creation
    time would pass every assertion above.
    """
    owner = _person(postgres_session, "Nam")
    service = _service(postgres_session)
    created = service.create_context(
        ContextCreateRequest(display_name="Tên cũ"), _actor(owner.id)
    )
    postgres_session.get(Context, created.id).display_name = "Tên mới"
    postgres_session.flush()

    read = service.get_context(created.id, _actor(owner.id, created.id))

    assert read.display_name == "Tên mới"
