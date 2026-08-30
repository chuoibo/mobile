"""When the roster comes back empty, the unchecked ids become the roster.

The fake in `tests/api` cannot fail this. Its `list_members` returns two active
rows for every context by construction, so `split_bill`'s fallback --

    app/api/service.py:1840
        if not participant_ids:
            participant_ids = {
                share.participant_id for item in record.items for share in item.shares
            }

-- is unreachable there. Only a real `memberships` table can be empty, which is
what makes this tier load-bearing rather than a copy of the fake one.

`#247`'s own docstring named this branch and left it: the late refusal at
`split` is "reachable only while the roster is non-empty, which is the
condition `split_bill`'s own fallback removes". This file is that sentence
turned into a case that fails.

Two ways a real group has no active member, neither of them exotic:

  * No `memberships` row at all. This is not hypothetical -- it is exactly the
    state `bug-053800` put every expense into earlier today, where `api.ts`
    carried a `CONTEXT_ID` that had never had a row in `contexts`. `#244` fixed
    the client; the server still answers this way if anything else produces it.
  * Rows exist and none is `ACTIVE` -- a group just created where everyone is
    still `INVITED`. `models.py` says being added to a group is something that
    happens to you, so a roster of pending invitations is a normal state, not a
    corrupt one.

Measured on main @ 431dd7c, printed total 135.000₫ across two dishes:

    roster: one ACTIVE member   -> split refused, UNKNOWN_PARTICIPANT
    roster: no membership rows  -> split OK, stranger allocated 65.000₫
    roster: all INVITED         -> split OK, stranger allocated 65.000₫

The sum is 135.000₫ in every one of those runs and every allocation is a whole
đồng, so all three money rules hold while the money is assigned to somebody the
group does not contain. Ownership is a separate invariant from arithmetic, and
this is what it looks like when only the arithmetic is guarded.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.api.deps import Actor
from app.api.errors import ApiProblem
from app.api.repository import SqlAlchemyApiRepository
from app.api.schemas import (
    BillCreateRequest,
    BillItemCreateRequest,
    BillSplitRequest,
)
from app.api.service import ApiService
from app.db.models import (
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    Person,
)

pytestmark = pytest.mark.postgres

NOW = datetime(2030, 8, 29, 9, 0, tzinfo=UTC)
ROLES = frozenset({"member", "advancer"})
PHO_VND = 65_000
BUN_VND = 70_000
PRINTED_TOTAL_VND = PHO_VND + BUN_VND


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _context(session: Session, owner_id: uuid.UUID) -> uuid.UUID:
    context = Context(
        id=uuid.uuid4(), display_name="Nhóm ăn tối", created_by_id=owner_id
    )
    session.add(context)
    session.flush()
    return context.id


def _membership(
    session: Session,
    context_id: uuid.UUID,
    person_id: uuid.UUID,
    state: MembershipState,
) -> None:
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context_id,
            person_id=person_id,
            state=state,
            joined_at=NOW if state is MembershipState.ACTIVE else None,
            left_at=None,
            role=MembershipRole.MEMBER,
        )
    )
    session.flush()


def _bill_request(
    context_id: uuid.UUID, pho_owner: uuid.UUID, bun_owner: uuid.UUID
) -> BillCreateRequest:
    """Two dishes at different prices, so an even split and a per-item split
    cannot return the same numbers and hide which one ran."""

    return BillCreateRequest(
        context_id=context_id,
        printed_total_vnd=PRINTED_TOTAL_VND,
        items_total_vnd=PRINTED_TOTAL_VND,
        confidence=88,
        needs_review=False,
        items=[
            BillItemCreateRequest(
                item_key="i1",
                name="Phở bò",
                quantity=1,
                unit_price_vnd=PHO_VND,
                line_total_vnd=PHO_VND,
                suggested_participant_ids=[pho_owner],
            ),
            BillItemCreateRequest(
                item_key="i2",
                name="Bún chả",
                quantity=1,
                unit_price_vnd=BUN_VND,
                line_total_vnd=BUN_VND,
                suggested_participant_ids=[bun_owner],
            ),
        ],
    )


def _money_reaching(
    session: Session,
    context_id: uuid.UUID,
    payer_id: uuid.UUID,
    pho_owner: uuid.UUID,
) -> dict[uuid.UUID, int]:
    """Walk `POST /bills` then `POST /bills/{id}/split` and return who got paid.

    A refusal at either door means nobody was allocated anything, which is the
    property under test being satisfied -- so it maps to an empty dict rather
    than to an error. That keeps this usable no matter which door the eventual
    fix puts the guard behind.
    """

    service = ApiService(SqlAlchemyApiRepository(session))
    actor = Actor(id=payer_id, roles=ROLES, context_ids=frozenset({context_id}))

    try:
        bill = service.create_bill(
            _bill_request(context_id, pho_owner, payer_id), actor
        )
    except ApiProblem:
        return {}

    try:
        split = service.split_bill(bill.id, BillSplitRequest(for_ledger=False), actor)
    except ApiProblem:
        return {}

    return dict(split.allocation.allocations)


def test_a_group_with_members_splits_its_own_bill(postgres_session: Session):
    """Positive control. Without it, a service that refuses every split
    satisfies every other case in this file."""

    payer = _person(postgres_session, "Nam")
    friend = _person(postgres_session, "Hà")
    context_id = _context(postgres_session, payer.id)
    _membership(postgres_session, context_id, payer.id, MembershipState.ACTIVE)
    _membership(postgres_session, context_id, friend.id, MembershipState.ACTIVE)

    allocations = _money_reaching(postgres_session, context_id, payer.id, friend.id)

    assert sum(allocations.values()) == PRINTED_TOTAL_VND
    assert set(allocations) == {payer.id, friend.id}


def test_a_stranger_is_refused_while_the_roster_is_not_empty(
    postgres_session: Session,
):
    """The refusal that does exist today, pinned so the contrast is measured
    rather than asserted. It happens at `split`, after the share is already
    stored and readable -- late, but it does happen."""

    payer = _person(postgres_session, "Nam")
    stranger = _person(postgres_session, "Người lạ")
    context_id = _context(postgres_session, payer.id)
    _membership(postgres_session, context_id, payer.id, MembershipState.ACTIVE)

    allocations = _money_reaching(postgres_session, context_id, payer.id, stranger.id)

    assert allocations == {}


@pytest.mark.xfail(
    strict=True,
    reason=(
        "OPEN: with no membership rows the fallback in split_bill makes the "
        "unchecked ids the roster, and the stranger is allocated money. "
        "Remove this marker as part of the fix."
    ),
)
def test_no_membership_rows_must_not_turn_a_stranger_into_a_participant(
    postgres_session: Session,
):
    payer = _person(postgres_session, "Nam")
    stranger = _person(postgres_session, "Người lạ")
    context_id = _context(postgres_session, payer.id)
    # deliberately no membership rows: the `bug-053800` shape

    allocations = _money_reaching(postgres_session, context_id, payer.id, stranger.id)

    assert stranger.id not in allocations, (
        f"{allocations.get(stranger.id)}đ allocated to a non-member"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "OPEN: a group where nobody has accepted yet has no ACTIVE row, so the "
        "same fallback fires. Remove this marker as part of the fix."
    ),
)
def test_a_group_of_pending_invitations_must_not_pay_a_stranger(
    postgres_session: Session,
):
    payer = _person(postgres_session, "Nam")
    stranger = _person(postgres_session, "Người lạ")
    context_id = _context(postgres_session, payer.id)
    _membership(postgres_session, context_id, payer.id, MembershipState.INVITED)

    allocations = _money_reaching(postgres_session, context_id, payer.id, stranger.id)

    assert stranger.id not in allocations, (
        f"{allocations.get(stranger.id)}đ allocated to a non-member"
    )


def test_the_money_rules_hold_even_while_the_wrong_person_is_paid(
    postgres_session: Session,
):
    """Why no existing gate catches any of this.

    This case asserts the CURRENT behaviour on purpose, and it must stay green
    after the fix too: whatever `split` ends up answering, whenever it answers
    at all, the sum is the printed total and every share is a whole đồng. That
    is the whole point -- the three money rules are satisfied on both sides of
    this bug, so they were never going to be the thing that noticed it.
    """

    payer = _person(postgres_session, "Nam")
    stranger = _person(postgres_session, "Người lạ")
    context_id = _context(postgres_session, payer.id)

    allocations = _money_reaching(postgres_session, context_id, payer.id, stranger.id)

    if allocations:
        assert sum(allocations.values()) == PRINTED_TOTAL_VND
        assert all(isinstance(amount, int) for amount in allocations.values())
