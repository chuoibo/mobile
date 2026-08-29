"""The money routes decide membership from `memberships`, on real PostgreSQL.

The `tests/api` twin of this file proves the routing and the refusal against a
fake whose `is_member` is a set lookup. That fake cannot distinguish the two
cases this layer exists for, because the real predicate is not set membership:

    Membership.state == ACTIVE  AND  Membership.left_at IS NULL

A dict-backed fake models "left the group" by deleting the entry, which is the
one thing the production schema deliberately never does -- `Membership` keeps
the row and flips its state, because money that was owed does not stop having
been owed. So "a former member is refused" is only really tested here, against
the partial unique index and the state column that make the distinction real.

The header cannot express any of it. `X-Actor-Contexts` is a list of ids with
no state attached, so a client that still names the group -- a stale build, a
bookmarked link -- reads as a member forever. That is the case below.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.api.deps import Actor
from app.api.errors import ApiProblem
from app.api.repository import SqlAlchemyApiRepository
from app.api.schemas import BillCreateRequest
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
ROLES = frozenset({"member", "advancer", "recipient", "batch_owner"})


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _group(session: Session, owner_id: uuid.UUID) -> Context:
    context = Context(
        id=uuid.uuid4(), display_name="Nhóm đi ăn", created_by_id=owner_id
    )
    session.add(context)
    session.flush()
    return context


def _join(session, context_id, person_id, state=MembershipState.ACTIVE) -> Membership:
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


def _claiming(person_id: uuid.UUID, context_id: uuid.UUID) -> Actor:
    """An actor asserting the victim's group in its own header.

    This is the shape that matters. An intruder who honestly names a different
    group is refused by any check at all, including the one this change
    replaced -- so a test built that way stays green over the bug.
    """

    return Actor(id=person_id, roles=ROLES, context_ids=frozenset({context_id}))


def _bill_request(context_id: uuid.UUID) -> BillCreateRequest:
    return BillCreateRequest(
        context_id=context_id,
        printed_total_vnd=135_000,
        items_total_vnd=135_000,
        confidence=88,
        needs_review=False,
        items=[
            {
                "item_key": "i1",
                "name": "Phở bò",
                "quantity": 1,
                "unit_price_vnd": 135_000,
                "line_total_vnd": 135_000,
                "suggested_participant_ids": [],
            }
        ],
        surcharges=[],
        discounts=[],
    )


def test_a_stranger_claiming_the_group_is_refused_by_the_database(
    postgres_session: Session,
):
    """Nobody has ever put this person in this group, and they say otherwise."""

    owner = _person(postgres_session, "Nam")
    stranger = _person(postgres_session, "Ai đó")
    group = _group(postgres_session, owner.id)
    _join(postgres_session, group.id, owner.id)

    service = ApiService(SqlAlchemyApiRepository(postgres_session))

    with pytest.raises(ApiProblem) as refused:
        service.create_bill(_bill_request(group.id), _claiming(stranger.id, group.id))

    assert refused.value.status_code == 403
    assert refused.value.code == "permission_denied"


def test_a_member_who_left_is_refused_though_the_row_remains(
    postgres_session: Session,
):
    """The case the fake cannot hold and the header cannot represent.

    The membership row is still there -- `state='left'`, `left_at` set -- which
    is the schema working as intended. `is_member` has to read the state, not
    the existence of the row.
    """

    owner = _person(postgres_session, "Nam")
    former = _person(postgres_session, "Quyên")
    group = _group(postgres_session, owner.id)
    _join(postgres_session, group.id, owner.id)
    _join(postgres_session, group.id, former.id, state=MembershipState.LEFT)

    service = ApiService(SqlAlchemyApiRepository(postgres_session))

    with pytest.raises(ApiProblem) as refused:
        service.create_bill(_bill_request(group.id), _claiming(former.id, group.id))

    assert refused.value.status_code == 403
    # The row survives the refusal: leaving is recorded, not deleted.
    surviving = postgres_session.get(Membership, _open_membership_id(
        postgres_session, group.id, former.id
    ))
    assert surviving is not None
    assert surviving.state is MembershipState.LEFT


def _open_membership_id(session, context_id, person_id) -> uuid.UUID:
    membership = (
        session.query(Membership)
        .filter(
            Membership.context_id == context_id,
            Membership.person_id == person_id,
        )
        .one()
    )
    return membership.id


def test_an_invited_member_who_has_not_joined_is_refused(postgres_session: Session):
    """`invited` is not `active`, and the header has no word for the difference.

    A link recipient holds the group id before they have accepted anything, so
    this is the state a share link actually produces.
    """

    owner = _person(postgres_session, "Nam")
    invitee = _person(postgres_session, "Hà")
    group = _group(postgres_session, owner.id)
    _join(postgres_session, group.id, owner.id)
    _join(postgres_session, group.id, invitee.id, state=MembershipState.INVITED)

    service = ApiService(SqlAlchemyApiRepository(postgres_session))

    with pytest.raises(ApiProblem) as refused:
        service.create_bill(_bill_request(group.id), _claiming(invitee.id, group.id))

    assert refused.value.status_code == 403


def test_an_active_member_is_still_allowed(postgres_session: Session):
    """The positive control, on the same SQL predicate.

    Without it, a repository that answered `False` to every membership question
    would leave all three refusals above green.
    """

    owner = _person(postgres_session, "Nam")
    group = _group(postgres_session, owner.id)
    _join(postgres_session, group.id, owner.id)

    service = ApiService(SqlAlchemyApiRepository(postgres_session))

    created = service.create_bill(_bill_request(group.id), _claiming(owner.id, group.id))

    assert created.context_id == group.id


def test_an_active_member_who_omits_the_header_is_still_allowed(
    postgres_session: Session,
):
    """The other half of "the header is not the source of truth".

    If membership came from `X-Actor-Contexts`, an empty header would refuse a
    real member. It has to be irrelevant in both directions, or the check has
    merely moved rather than changed.
    """

    owner = _person(postgres_session, "Nam")
    group = _group(postgres_session, owner.id)
    _join(postgres_session, group.id, owner.id)

    service = ApiService(SqlAlchemyApiRepository(postgres_session))
    no_context_header = Actor(id=owner.id, roles=ROLES, context_ids=frozenset())

    created = service.create_bill(_bill_request(group.id), no_context_header)

    assert created.context_id == group.id
