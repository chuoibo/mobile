"""Authorization on the identity routes, proved rather than declared.

Codex registered every action in the closed permission table and called
`_require_permission` in every service method. All of that was correct, and
none of it was covered: deleting the check from `list_context_members` left
275 tests green.

That is the same shape as the bug QA found in `GET /batches/{id}/obligations`
a few hours earlier -- an `actor` argument accepted and never read. A check
nobody exercises and a check nobody wrote fail identically, and both look fine
in a diff.

These run against real PostgreSQL because membership is enforced by a partial
unique index and a check constraint, and a dict-backed fake has neither.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.api.deps import Actor
from app.api.errors import ApiProblem
from app.api.repository import SqlAlchemyApiRepository
from app.api.service import ApiService
from app.db.models import Context, Membership, MembershipState, Person

NOW = datetime(2030, 8, 28, 9, 0, tzinfo=UTC)
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


def _group_with_member(session: Session) -> tuple[Context, Person, Person]:
    owner = _person(session, "Nam")
    outsider = _person(session, "Người lạ")
    context = Context(id=uuid.uuid4(), display_name="Nhóm thử", created_by_id=owner.id)
    session.add(context)
    session.flush()
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=owner.id,
            state=MembershipState.ACTIVE,
            joined_at=NOW,
        )
    )
    session.flush()
    return context, owner, outsider


def test_a_member_can_read_the_roster(postgres_session: Session):
    context, owner, _ = _group_with_member(postgres_session)
    service = ApiService(SqlAlchemyApiRepository(postgres_session))

    result = service.list_context_members(context.id, _actor(owner.id, context.id))

    assert [row.person_id for row in result.members] == [owner.id]


def test_somebody_who_is_not_in_the_group_cannot_read_the_roster(
    postgres_session: Session,
):
    """The roster is who a person shares money with. Handing it to a stranger
    who happens to know a group id is the same leak as the collection board."""
    context, _, outsider = _group_with_member(postgres_session)
    service = ApiService(SqlAlchemyApiRepository(postgres_session))

    with pytest.raises(ApiProblem) as caught:
        service.list_context_members(context.id, _actor(outsider.id, context.id))

    assert caught.value.status_code == 403
    # And the refusal says nothing about who is in the group.
    assert "Nam" not in str(caught.value.detail)


def test_a_former_member_loses_the_roster(postgres_session: Session):
    """Leaving is recorded rather than deleted, which makes it easy to keep
    reading a row that has ended. Membership is `left_at IS NULL`, not `a row
    exists`."""
    context, owner, friend = _group_with_member(postgres_session)
    membership = Membership(
        id=uuid.uuid4(),
        context_id=context.id,
        person_id=friend.id,
        state=MembershipState.ACTIVE,
        joined_at=NOW,
    )
    postgres_session.add(membership)
    postgres_session.flush()

    service = ApiService(SqlAlchemyApiRepository(postgres_session))
    assert service.list_context_members(context.id, _actor(friend.id, context.id))

    membership.state = MembershipState.LEFT
    membership.left_at = NOW
    postgres_session.flush()

    with pytest.raises(ApiProblem) as caught:
        service.list_context_members(context.id, _actor(friend.id, context.id))
    assert caught.value.status_code == 403


def test_an_invited_person_is_not_yet_a_member(postgres_session: Session):
    """§9: being added to a group is something that happens to you. An invite
    that already granted access would make accepting it decorative."""
    context, _, invitee = _group_with_member(postgres_session)
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=invitee.id,
            state=MembershipState.INVITED,
        )
    )
    postgres_session.flush()

    service = ApiService(SqlAlchemyApiRepository(postgres_session))
    with pytest.raises(ApiProblem) as caught:
        service.list_context_members(context.id, _actor(invitee.id, context.id))
    assert caught.value.status_code == 403
