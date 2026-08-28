"""Identity on real PostgreSQL, because the guarantees are PostgreSQL's.

A person's standing in a group is protected by a PARTIAL unique index --
"at most one membership that has not ended, per person per group" -- and by a
check constraint tying `state = 'left'` to `left_at`. Neither exists in a
dict-backed fake. A test suite that only ran against the fake would report
these as working while the database had never been asked.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Context, Membership, MembershipState, Person

NOW = datetime(2030, 8, 28, 9, 0, tzinfo=UTC)


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _context(session: Session, owner: Person, name: str = "Nhóm thử") -> Context:
    context = Context(id=uuid.uuid4(), display_name=name, created_by_id=owner.id)
    session.add(context)
    session.flush()
    return context


def _join(session: Session, context: Context, person: Person, **over) -> Membership:
    fields = {
        "id": uuid.uuid4(),
        "context_id": context.id,
        "person_id": person.id,
        "state": MembershipState.ACTIVE,
        "joined_at": NOW,
    }
    fields.update(over)
    membership = Membership(**fields)
    session.add(membership)
    session.flush()
    return membership


def test_a_person_cannot_hold_two_open_memberships_in_one_group(
    postgres_session: Session,
):
    """Two open rows would make "is this person in the group" ambiguous, and
    every permission check downstream reads that answer."""
    owner = _person(postgres_session, "Nam")
    context = _context(postgres_session, owner)
    _join(postgres_session, context, owner)

    with pytest.raises(IntegrityError):
        _join(postgres_session, context, owner)
        postgres_session.flush()


def test_the_same_person_may_be_in_two_different_groups(postgres_session: Session):
    """The index is scoped per group. Sharing a flat and sharing a holiday are
    different groups and must not exclude each other."""
    owner = _person(postgres_session, "Nam")
    first = _context(postgres_session, owner, "Nhà trọ")
    second = _context(postgres_session, owner, "Đi Vũng Tàu")

    _join(postgres_session, first, owner)
    _join(postgres_session, second, owner)

    open_rows = (
        postgres_session.query(Membership)
        .filter(Membership.person_id == owner.id, Membership.left_at.is_(None))
        .count()
    )
    assert open_rows == 2


def test_leaving_then_rejoining_creates_a_second_row(postgres_session: Session):
    """Re-joining is a new fact, not the old one resumed.

    What somebody could see during the first stretch is not what they may see
    during the second, and one row cannot answer both. Reviving the old row
    would also silently backdate the new membership.
    """
    owner = _person(postgres_session, "Nam")
    friend = _person(postgres_session, "Hà")
    context = _context(postgres_session, owner)

    first = _join(postgres_session, context, friend)
    first.state = MembershipState.LEFT
    first.left_at = NOW + timedelta(days=1)
    postgres_session.flush()

    # Allowed only because the earlier row is closed.
    second = _join(postgres_session, context, friend, joined_at=NOW + timedelta(days=2))
    postgres_session.flush()

    assert second.id != first.id
    assert first.left_at is not None
    assert second.left_at is None


def test_leaving_without_a_timestamp_is_refused(postgres_session: Session):
    """`state = 'left'` and `left_at` have to agree.

    Otherwise a row can say somebody left while the partial index still counts
    them as present -- the group would show them gone and the permission check
    would let them in.
    """
    owner = _person(postgres_session, "Nam")
    context = _context(postgres_session, owner)
    membership = _join(postgres_session, context, owner)

    membership.state = MembershipState.LEFT
    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_a_timestamp_without_the_left_state_is_refused(postgres_session: Session):
    """The other direction of the same constraint."""
    owner = _person(postgres_session, "Nam")
    context = _context(postgres_session, owner)
    membership = _join(postgres_session, context, owner)

    membership.left_at = NOW + timedelta(days=1)
    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_a_group_cannot_point_at_a_person_who_does_not_exist(
    postgres_session: Session,
):
    """`context_id` used to be a bare UUID pointing at nothing, so any value
    was a valid group. The same must not be true of who created one."""
    context = Context(
        id=uuid.uuid4(), display_name="Nhóm ma", created_by_id=uuid.uuid4()
    )
    postgres_session.add(context)
    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_two_people_may_share_a_display_name(postgres_session: Session):
    """Identity is an id, never a name.

    Two friends called Nam are two people. The mobile client learned this the
    expensive way: keying anything by name collapsed them into one, and one of
    them silently stopped owing money.
    """
    owner = _person(postgres_session, "Nam")
    namesake = _person(postgres_session, "Nam")
    context = _context(postgres_session, owner)

    _join(postgres_session, context, owner)
    _join(postgres_session, context, namesake)

    assert owner.id != namesake.id
    members = (
        postgres_session.query(Membership)
        .filter(Membership.context_id == context.id, Membership.left_at.is_(None))
        .count()
    )
    assert members == 2
