"""Identity guarantees that only a real PostgreSQL schema can prove."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    BankRecipient,
    Context,
    Expense,
    Group,
    Membership,
    MembershipRole,
    MembershipState,
    Person,
)

NOW = datetime(2030, 8, 28, 9, 0, tzinfo=UTC)


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name, created_at=NOW)
    session.add(person)
    session.flush()
    return person


def _group(session: Session, owner: Person, name: str = "Nhóm thử") -> Group:
    group = Group(
        id=uuid.uuid4(),
        display_name=name,
        created_by_id=owner.id,
        created_at=NOW,
    )
    session.add(group)
    session.flush()
    return group


def _context(session: Session, group: Group, owner: Person) -> Context:
    context = Context(
        id=uuid.uuid4(),
        group_id=group.id,
        display_name="Chuyến thử",
        created_by_id=owner.id,
        created_at=NOW,
    )
    session.add(context)
    session.flush()
    return context


def _join(
    session: Session,
    group: Group,
    person: Person,
    **over,
) -> Membership:
    fields = {
        "id": uuid.uuid4(),
        "group_id": group.id,
        "person_id": person.id,
        "state": MembershipState.ACTIVE,
        "role": MembershipRole.MEMBER,
        "joined_at": NOW,
        "created_at": NOW,
    }
    fields.update(over)
    membership = Membership(**fields)
    session.add(membership)
    session.flush()
    return membership


def test_group_and_context_are_distinct_identities(postgres_session: Session):
    owner = _person(postgres_session, "Nam")
    group = _group(postgres_session, owner)
    context = _context(postgres_session, group, owner)

    assert context.id != group.id
    assert context.group_id == group.id


def test_expense_rejects_a_context_that_does_not_exist(postgres_session: Session):
    postgres_session.add(Expense(context_id=uuid.uuid4(), created_at=NOW))

    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_financial_subject_rejects_a_person_that_does_not_exist(
    postgres_session: Session,
):
    postgres_session.add(
        BankRecipient(
            recipient_id=uuid.uuid4(),
            bank_bin="970407",
            account_number="SYNTHETIC001",
            account_name="SYNTHETIC PERSON",
            confirmed_by_recipient_at=NOW,
            created_at=NOW,
        )
    )

    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_a_person_cannot_hold_two_open_memberships_in_one_group(
    postgres_session: Session,
):
    owner = _person(postgres_session, "Nam")
    group = _group(postgres_session, owner)
    _join(postgres_session, group, owner, role=MembershipRole.ADMIN)

    with pytest.raises(IntegrityError):
        _join(postgres_session, group, owner)


def test_the_same_person_may_be_in_two_different_groups(postgres_session: Session):
    owner = _person(postgres_session, "Nam")
    first = _group(postgres_session, owner, "Nhà trọ")
    second = _group(postgres_session, owner, "Nhóm đi chơi")

    _join(postgres_session, first, owner)
    _join(postgres_session, second, owner)

    open_rows = (
        postgres_session.query(Membership)
        .filter(
            Membership.person_id == owner.id,
            Membership.state.in_((MembershipState.INVITED, MembershipState.ACTIVE)),
        )
        .count()
    )
    assert open_rows == 2


def test_leaving_then_rejoining_creates_a_second_row(postgres_session: Session):
    owner = _person(postgres_session, "Nam")
    friend = _person(postgres_session, "Hà")
    group = _group(postgres_session, owner)

    first = _join(postgres_session, group, friend)
    first.state = MembershipState.LEFT
    first.left_at = NOW + timedelta(days=1)
    postgres_session.flush()

    second = _join(
        postgres_session,
        group,
        friend,
        joined_at=NOW + timedelta(days=2),
    )

    assert second.id != first.id
    assert first.left_at is not None
    assert second.left_at is None


def test_closed_membership_intervals_cannot_overlap(postgres_session: Session):
    owner = _person(postgres_session, "Nam")
    group = _group(postgres_session, owner)
    first = _join(postgres_session, group, owner)
    first.state = MembershipState.LEFT
    first.left_at = NOW + timedelta(days=10)
    postgres_session.flush()

    overlapping = Membership(
        id=uuid.uuid4(),
        group_id=group.id,
        person_id=owner.id,
        state=MembershipState.LEFT,
        role=MembershipRole.MEMBER,
        joined_at=NOW + timedelta(days=2),
        left_at=NOW + timedelta(days=3),
        created_at=NOW + timedelta(days=2),
    )
    postgres_session.add(overlapping)

    with pytest.raises(IntegrityError) as caught:
        postgres_session.flush()
    assert caught.value.orig.diag.constraint_name == "ex_memberships_no_overlap"


@pytest.mark.parametrize(
    "terminal_state", [MembershipState.LEFT, MembershipState.REMOVED]
)
def test_terminal_membership_requires_a_valid_interval(
    postgres_session: Session,
    terminal_state: MembershipState,
):
    owner = _person(postgres_session, "Nam")
    group = _group(postgres_session, owner)
    membership = _join(postgres_session, group, owner)
    membership.state = terminal_state

    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_membership_cannot_end_before_it_joined(postgres_session: Session):
    owner = _person(postgres_session, "Nam")
    group = _group(postgres_session, owner)
    membership = _join(postgres_session, group, owner)
    membership.state = MembershipState.LEFT
    membership.left_at = NOW - timedelta(seconds=1)

    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_invitation_is_not_active_membership(postgres_session: Session):
    owner = _person(postgres_session, "Nam")
    friend = _person(postgres_session, "Hà")
    group = _group(postgres_session, owner)
    invitation = Membership(
        id=uuid.uuid4(),
        group_id=group.id,
        person_id=friend.id,
        state=MembershipState.INVITED,
        role=MembershipRole.MEMBER,
        invited_by_id=owner.id,
        joined_at=NOW,
        created_at=NOW,
    )
    postgres_session.add(invitation)

    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_invitation_requires_an_inviter(postgres_session: Session):
    owner = _person(postgres_session, "Nam")
    friend = _person(postgres_session, "Hà")
    group = _group(postgres_session, owner)
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            group_id=group.id,
            person_id=friend.id,
            state=MembershipState.INVITED,
            role=MembershipRole.MEMBER,
            created_at=NOW,
        )
    )

    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_two_people_may_share_a_display_name(postgres_session: Session):
    first = _person(postgres_session, "Nam")
    second = _person(postgres_session, "Nam")

    assert first.id != second.id
