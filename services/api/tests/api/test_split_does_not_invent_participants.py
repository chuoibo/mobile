"""`split_bill` must not turn unchecked shares into the roster.

`split_bill` reads the roster and, when it came back with nobody active, used
the ids already stored on the bill instead:

    app/api/service.py
        if not participant_ids:
            participant_ids = {
                share.participant_id for item in record.items for share in item.shares
            }

Those ids are the ones `POST /bills` accepted, and until the guard added
alongside this file, nothing had checked them against the group. So the one
question `split` asks about ownership -- the allocator's `UNKNOWN_PARTICIPANT`
-- was answered with the same unchecked list it was supposed to be judging, and
the answer was always yes.

**Why this is a service-level test and not an HTTP one.** Today no request can
reach that branch. `_bill_for_actor` requires `is_member`, which is ACTIVE and
not left; a context with such a member has at least one active row, so the
roster `split_bill` reads is never empty. That upstream check arrived in `#253`
-- *after* this branch was measured live at `431dd7c` -- and it closes the
route by accident, from a different door, for a different reason. The branch
itself was never changed.

That makes the fallback dead code with a live edge: it is one loosened
permission away from paying strangers again, and nothing would have said so.
The divergence below (a roster that answers empty while `is_member` still says
yes) is therefore constructed on purpose rather than reached through a route.
It states the invariant `split_bill` owns by itself -- *the participants of a
split are the group's roster, never the bill's own shares* -- so the property
stays pinned at the layer that holds it instead of resting on a caller two
doors upstream continuing to behave.
"""

from __future__ import annotations

import uuid

import pytest

from app.api.deps import Actor
from app.api.errors import ApiProblem
from app.api.schemas import BillCreateRequest, BillSplitRequest
from app.api.service import ApiService
from tests.api.helpers import ADVANCER_ID, CONTEXT_ID, SENDER_ID
from tests.api.test_bills import bill_payload


def _actor() -> Actor:
    return Actor(
        id=SENDER_ID,
        roles=frozenset({"member", "advancer"}),
        context_ids=frozenset({CONTEXT_ID}),
    )


def _bill_named_by_members(service: ApiService) -> uuid.UUID:
    """A perfectly ordinary bill: every id on it is a member of the group."""

    created = service.create_bill(
        BillCreateRequest.model_validate(bill_payload()), _actor()
    )
    return created.id


def test_an_empty_roster_does_not_make_the_bills_own_shares_the_roster(repository):
    """The roster goes empty between writing the bill and splitting it.

    `is_member` keeps answering yes, so the permission check still passes and
    `split_bill` is entered -- exactly the state the fallback was written for.
    It must refuse rather than pay out to the ids it was meant to be checking.
    """

    service = ApiService(repository)
    bill_id = _bill_named_by_members(service)

    repository.list_members = lambda context_id: []

    with pytest.raises(ApiProblem) as refusal:
        service.split_bill(bill_id, BillSplitRequest(for_ledger=False), _actor())

    assert refusal.value.status_code == 422


def test_a_group_with_a_roster_still_splits_its_own_bill(repository):
    """Negative control.

    Without it, deleting `split_bill` entirely satisfies the case above. This
    is the same two-dish bill, left alone, and it must still pay both diners
    the printed total.
    """

    service = ApiService(repository)
    bill_id = _bill_named_by_members(service)

    split = service.split_bill(bill_id, BillSplitRequest(for_ledger=False), _actor())

    allocations = dict(split.allocation.allocations)
    assert set(allocations) == {SENDER_ID, ADVANCER_ID}
    assert sum(allocations.values()) == 135000
