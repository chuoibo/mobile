"""Who administers a group, according to the database rather than a header.

`X-Actor-Roles` already carries a `group_admin` string, and it is written by a
gateway on behalf of whoever is calling. That is fine for saying "this caller
is a signed-in member"; it is not an answer to "is this person an admin of THIS
group", because the header does not know which group is being asked about.

So the role lives on the membership row -- one person, one group, one standing
-- and it is `memberships.role`, not a second `group_members` table. A parallel
table would mean two answers to who is in a group, and the two would disagree
the first time somebody left via one of them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.api.deps import Actor
from app.api.errors import ApiProblem
from app.api.repository import SqlAlchemyApiRepository
from app.api.schemas import ContextCreateRequest, MemberRoleRequest
from app.api.service import ApiService
from app.db.models import Membership, MembershipRole, MembershipState, Person

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


def _join(
    session: Session,
    context_id,
    person_id,
    role: MembershipRole = MembershipRole.MEMBER,
) -> Membership:
    # The enum member, not the bare string, for the same reason `state` uses
    # one: an attribute assigned a plain string stays a plain string until the
    # row is reloaded, and the repository reads `.value` off it.
    membership = Membership(
        id=uuid.uuid4(),
        context_id=context_id,
        person_id=person_id,
        state=MembershipState.ACTIVE,
        joined_at=NOW,
        role=role,
    )
    session.add(membership)
    session.flush()
    return membership


def test_whoever_creates_a_group_administers_it(postgres_session: Session):
    """A group born with no admin cannot invite anybody, which makes it a dead
    object from its first second."""
    owner = _person(postgres_session, "Nam")
    service = _service(postgres_session)

    context = service.create_context(
        ContextCreateRequest(display_name="Nhóm mới"), _actor(owner.id)
    )
    members = service.list_context_members(context.id, _actor(owner.id, context.id))

    assert [(row.person_id, row.role) for row in members.members] == [
        (owner.id, "admin")
    ]


def test_an_invited_member_joins_as_a_plain_member(postgres_session: Session):
    owner = _person(postgres_session, "Nam")
    friend = _person(postgres_session, "Hà")
    service = _service(postgres_session)
    context = service.create_context(
        ContextCreateRequest(display_name="Nhóm mới"), _actor(owner.id)
    )

    from app.api.schemas import MembershipInviteRequest

    invited = service.invite_context_member(
        context.id, MembershipInviteRequest(person_id=friend.id), _actor(owner.id, context.id)
    )

    assert invited.role == "member"


def test_a_plain_member_cannot_hand_themselves_the_admin_role(
    postgres_session: Session,
):
    """The whole point of the column. The actor header says `group_admin` --
    it says that for every signed-in member -- and the database disagrees."""
    owner = _person(postgres_session, "Nam")
    friend = _person(postgres_session, "Hà")
    service = _service(postgres_session)
    context = service.create_context(
        ContextCreateRequest(display_name="Nhóm mới"), _actor(owner.id)
    )
    _join(postgres_session, context.id, friend.id)

    with pytest.raises(ApiProblem) as caught:
        service.set_context_member_role(
            context.id,
            friend.id,
            MemberRoleRequest(role="admin"),
            _actor(friend.id, context.id),
        )

    assert caught.value.status_code == 403


def test_an_admin_promotes_a_member_and_the_change_sticks(postgres_session: Session):
    owner = _person(postgres_session, "Nam")
    friend = _person(postgres_session, "Hà")
    service = _service(postgres_session)
    context = service.create_context(
        ContextCreateRequest(display_name="Nhóm mới"), _actor(owner.id)
    )
    _join(postgres_session, context.id, friend.id)

    promoted = service.set_context_member_role(
        context.id,
        friend.id,
        MemberRoleRequest(role="admin"),
        _actor(owner.id, context.id),
    )
    assert promoted.role == "admin"

    roster = service.list_context_members(context.id, _actor(owner.id, context.id))
    assert dict((row.person_id, row.role) for row in roster.members)[friend.id] == "admin"


def test_a_promoted_member_can_then_promote_somebody_else(postgres_session: Session):
    """Proves the promotion changed the DATABASE and not just a response body:
    the new admin's next call is authorised by the row that was just written."""
    owner = _person(postgres_session, "Nam")
    friend = _person(postgres_session, "Hà")
    third = _person(postgres_session, "Quyên")
    service = _service(postgres_session)
    context = service.create_context(
        ContextCreateRequest(display_name="Nhóm mới"), _actor(owner.id)
    )
    _join(postgres_session, context.id, friend.id)
    _join(postgres_session, context.id, third.id)

    service.set_context_member_role(
        context.id, friend.id, MemberRoleRequest(role="admin"), _actor(owner.id, context.id)
    )
    promoted = service.set_context_member_role(
        context.id, third.id, MemberRoleRequest(role="admin"), _actor(friend.id, context.id)
    )

    assert promoted.role == "admin"


def test_an_admin_cannot_promote_somebody_who_is_not_in_the_group(
    postgres_session: Session,
):
    owner = _person(postgres_session, "Nam")
    stranger = _person(postgres_session, "Người lạ")
    service = _service(postgres_session)
    context = service.create_context(
        ContextCreateRequest(display_name="Nhóm mới"), _actor(owner.id)
    )

    with pytest.raises(ApiProblem) as caught:
        service.set_context_member_role(
            context.id,
            stranger.id,
            MemberRoleRequest(role="admin"),
            _actor(owner.id, context.id),
        )

    assert caught.value.status_code == 404


def test_an_admin_of_one_group_is_not_an_admin_of_another(postgres_session: Session):
    """The reason a header cannot answer this: `group_admin` in a role set says
    nothing about WHICH group."""
    owner = _person(postgres_session, "Nam")
    other = _person(postgres_session, "Hà")
    service = _service(postgres_session)
    mine = service.create_context(
        ContextCreateRequest(display_name="Nhóm tôi"), _actor(owner.id)
    )
    theirs = service.create_context(
        ContextCreateRequest(display_name="Nhóm họ"), _actor(other.id)
    )
    _join(postgres_session, theirs.id, owner.id)
    assert mine.id != theirs.id

    with pytest.raises(ApiProblem) as caught:
        service.set_context_member_role(
            theirs.id,
            other.id,
            MemberRoleRequest(role="member"),
            _actor(owner.id, theirs.id),
        )

    assert caught.value.status_code == 403


def test_leaving_and_rejoining_starts_from_a_plain_membership(
    postgres_session: Session,
):
    """Re-joining creates a new row rather than reviving the old one, so an
    admin who left and came back does not silently get their powers back."""
    owner = _person(postgres_session, "Nam")
    friend = _person(postgres_session, "Hà")
    service = _service(postgres_session)
    context = service.create_context(
        ContextCreateRequest(display_name="Nhóm mới"), _actor(owner.id)
    )
    membership = _join(
        postgres_session, context.id, friend.id, role=MembershipRole.ADMIN
    )

    service.leave_context(context.id, friend.id, _actor(friend.id, context.id))
    postgres_session.flush()
    assert membership.state is MembershipState.LEFT

    rejoined = _join(postgres_session, context.id, friend.id)

    assert rejoined.role == "member"
