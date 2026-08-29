"""Who the ledger may charge, decided by `memberships` rather than the body.

`tests/api` proves the rule against a fake whose roster is a set of pairs and
whose every row reads `state="active"`. That fake cannot fail the interesting
half of this. The real `SqlAlchemyApiRepository.list_members` filters on
`left_at IS NULL` and **not** on `state`, so it hands back `INVITED` rows too:
people someone else added to a group who have not agreed to be there. The
`state == "active"` filter in `ApiService._require_participants_are_members` is
what excludes them, and only a real roster can show that filter doing work.

`MembershipState.INVITED` exists for a documented reason -- `models.py` says
being added to a group is something that happens to you, and a boundary you
were placed inside without agreeing is not one. Billing someone in that state
turns a pending invitation into a debt.

The other half is `LEFT`. That one the `left_at IS NULL` clause already covers
in SQL, so it is asserted here to pin the two halves to different mechanisms:
if someone later "simplifies" the service filter away, `INVITED` goes red while
`LEFT` stays green, and the diff says exactly which guarantee moved.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.api.deps import Actor
from app.api.errors import ApiProblem
from app.api.repository import SqlAlchemyApiRepository
from app.api.schemas import ExpenseConfirmationRequest, ExpenseInput
from app.api.service import ApiService
from app.db.models import (
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    Person,
)

NOW = datetime(2030, 8, 29, 9, 0, tzinfo=UTC)
TOTAL_VND = 80_000
ROLES = frozenset({"member", "advancer"})


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _membership(
    session: Session,
    context_id: uuid.UUID,
    person_id: uuid.UUID,
    state: MembershipState,
    *,
    left_at: datetime | None = None,
) -> None:
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context_id,
            person_id=person_id,
            state=state,
            # `joined_at` stays None for an invitation nobody accepted: the
            # row records that they were asked, not that they arrived.
            joined_at=NOW if state is MembershipState.ACTIVE else None,
            left_at=left_at,
            role=MembershipRole.MEMBER,
        )
    )
    session.flush()


def _confirm(
    session: Session,
    context_id: uuid.UUID,
    payer_id: uuid.UUID,
    participants: list[uuid.UUID],
):
    """Drive the real service over the real roster, evenly splitting the total."""
    service = ApiService(SqlAlchemyApiRepository(session))
    expense_id = SqlAlchemyApiRepository(session).create_expense(context_id).id
    share, remainder = divmod(TOTAL_VND, len(participants))
    ordered = sorted(participants, key=lambda value: value.bytes)
    allocations = {person_id: share for person_id in ordered}
    # The last dong goes somewhere; money rule 2 does not get a rounding
    # exemption just because this test is about people rather than arithmetic.
    allocations[ordered[-1]] += remainder

    return service.confirm_expense(
        expense_id,
        ExpenseConfirmationRequest(
            proposal=ExpenseInput(
                context_id=context_id,
                description="Lẩu nấm",
                recorded_by_id=payer_id,
                paid_by_id=payer_id,
                verification_scope="totals_only",
                occurred_at=NOW,
                participants=ordered,
                total_amount_vnd=TOTAL_VND,
                items=[],
                surcharges=[],
                discounts=[],
            ),
            expected_allocations=allocations,
            acknowledge_as_advancer=True,
        ),
        Actor(id=payer_id, roles=ROLES, context_ids=frozenset({context_id})),
    )


def _context(session: Session, owner_id: uuid.UUID, name: str = "Nhóm ăn tối") -> uuid.UUID:
    """A real row, because `memberships.context_id` is a real foreign key.

    Worth stating: `fk_memberships_context` is one of the constraints this
    layer exists to run. The fake in `tests/api` holds memberships as a set of
    UUID pairs, so there a group is whatever UUID somebody typed.
    """

    context = Context(id=uuid.uuid4(), display_name=name, created_by_id=owner_id)
    session.add(context)
    session.flush()
    return context.id


def _group_of_two(session: Session) -> tuple[uuid.UUID, Person, Person]:
    payer = _person(session, "Nam")
    friend = _person(session, "Hà")
    context_id = _context(session, payer.id)
    _membership(session, context_id, payer.id, MembershipState.ACTIVE)
    return context_id, payer, friend


def test_two_active_members_are_billable(postgres_session: Session):
    """The positive control, first: without it every case below is satisfied
    by a service that refuses everything."""
    context_id, payer, friend = _group_of_two(postgres_session)
    _membership(postgres_session, context_id, friend.id, MembershipState.ACTIVE)

    response = _confirm(postgres_session, context_id, payer.id, [payer.id, friend.id])

    assert sum(response.allocations.values()) == TOTAL_VND


def test_an_invited_person_who_never_accepted_cannot_be_billed(
    postgres_session: Session,
):
    """`left_at IS NULL` is true for them, so SQL alone lets this through."""
    context_id, payer, friend = _group_of_two(postgres_session)
    _membership(postgres_session, context_id, friend.id, MembershipState.INVITED)

    with pytest.raises(ApiProblem) as caught:
        _confirm(postgres_session, context_id, payer.id, [payer.id, friend.id])

    assert caught.value.status_code == 422
    assert caught.value.code == "participant_not_in_context"
    assert str(friend.id) in caught.value.detail


def test_a_person_who_left_the_group_cannot_be_billed(postgres_session: Session):
    context_id, payer, friend = _group_of_two(postgres_session)
    _membership(
        postgres_session,
        context_id,
        friend.id,
        MembershipState.LEFT,
        left_at=NOW,
    )

    with pytest.raises(ApiProblem) as caught:
        _confirm(postgres_session, context_id, payer.id, [payer.id, friend.id])

    assert caught.value.code == "participant_not_in_context"


def test_a_member_of_a_different_group_cannot_be_billed(postgres_session: Session):
    """The likeliest real mistake: a real person, active, wrong group.

    A UUID nobody has ever seen is a typo. This one is a person the caller
    genuinely knows, and it is the shape a client bug produces when it reuses
    a roster across screens.
    """
    context_id, payer, friend = _group_of_two(postgres_session)
    other_group = _context(postgres_session, friend.id, "Nhóm công ty")
    _membership(postgres_session, other_group, friend.id, MembershipState.ACTIVE)

    with pytest.raises(ApiProblem) as caught:
        _confirm(postgres_session, context_id, payer.id, [payer.id, friend.id])

    assert caught.value.code == "participant_not_in_context"


def test_nothing_is_written_when_a_participant_is_refused(postgres_session: Session):
    """The refusal must precede the write, not be undone after it.

    Read back through a fresh query rather than the ORM identity map, because
    an object still sitting in the session would answer this the same way
    whether or not it ever reached the table.
    """
    from app.db.models import ConfirmedAllocation

    context_id, payer, friend = _group_of_two(postgres_session)
    _membership(postgres_session, context_id, friend.id, MembershipState.INVITED)

    with pytest.raises(ApiProblem):
        _confirm(postgres_session, context_id, payer.id, [payer.id, friend.id])
    postgres_session.flush()

    charged = postgres_session.query(ConfirmedAllocation).filter(
        ConfirmedAllocation.participant_id == friend.id
    )
    assert charged.count() == 0
