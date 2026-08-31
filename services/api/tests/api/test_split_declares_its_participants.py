"""`POST /bills/{id}/split` must name the set it divided the bill between.

The server picks that set by itself. `BillSplitRequest` carries `for_ledger`
and `paid_by_id` and nothing else, so the roster reaching the allocator is
`list_members(context_id)` filtered to `active` -- a list the caller never
sent and, until this file, never got back under a name.

A screen measured by qa2 shows what that costs. Three rows adding to 320.000d
sit under a total printed as 480.000d, and the fourth diner is not on the
screen at all: no row, no name, not even an id. The client renders its own
member list and looks each person's amount up by id, so a participant the
server split for but the client has never heard of is dropped silently, and
160.000d with them -- next to a button that writes the result to the ledger.

The information is not, strictly, absent today: `allocation.allocations` is
keyed by exactly the split set, zero-amount members included, so a client
could derive it. That derivation is a convention nothing states and nothing
tests, and it is invisible to somebody reading the schema, where
`allocations` reads as *amounts*. These cases give the set a name, and give
the roster rows the split deliberately left out one too, because those are
the ones no field of the response mentions at all.

Additive on purpose: no new request field. Requiring `participants` on the
way in would 422 every client shipped before it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.api.deps import Actor
from app.api.repository import MembershipRecord
from app.api.schemas import BillCreateRequest, BillSplitRequest
from app.api.service import ApiService
from tests.api.helpers import ADVANCER_ID, CONTEXT_ID, OTHER_ID, SENDER_ID
from tests.api.test_bills import bill_payload

WATCHER_ID = uuid.UUID("5ee00000-eeee-4eee-8eee-0000e0000001")


def _actor() -> Actor:
    return Actor(
        id=SENDER_ID,
        roles=frozenset({"member", "advancer"}),
        context_ids=frozenset({CONTEXT_ID}),
    )


def _membership(person_id: uuid.UUID, state: str) -> MembershipRecord:
    return MembershipRecord(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"{CONTEXT_ID}/{person_id}/{state}"),
        context_id=CONTEXT_ID,
        person_id=person_id,
        display_name=f"Thành viên {str(person_id)[:8]}",
        state=state,
        role="member",
        origin="named",
        invited_by_id=None,
        joined_at=datetime(2030, 8, 27, 12, tzinfo=UTC) if state == "active" else None,
        left_at=None,
        created_at=datetime(2030, 8, 27, 12, tzinfo=UTC),
    )


def _roster(*rows: MembershipRecord):
    """Replace the roster read, leaving `is_member` alone.

    `_bill_for_actor` asks `is_member`, which the fixture already answers for
    the standard cast. Stubbing only `list_members` is what lets a roster hold
    a person the fake has no other way to express -- it hardcodes `active` for
    everybody it knows about, so `invited` cannot be reached through it.
    """

    return lambda context_id: list(rows)


def _bill(service: ApiService) -> uuid.UUID:
    """The standard two-dish bill: SENDER eats one, ADVANCER the other."""

    created = service.create_bill(
        BillCreateRequest.model_validate(bill_payload()), _actor()
    )
    return created.id


def test_split_names_a_member_who_is_on_no_dish(repository):
    """The set is the roster, so somebody who ordered nothing is still in it.

    This is the case that separates "the participants" from "whoever the bill
    names": OTHER_ID appears on no item, eats nothing and is allocated 0d, and
    a `participant_ids` computed from the bill's own shares would leave them
    out. The bill still totals 135.000d between the two who ate.
    """

    service = ApiService(repository)
    bill_id = _bill(service)
    repository.list_members = _roster(
        _membership(SENDER_ID, "active"),
        _membership(ADVANCER_ID, "active"),
        _membership(OTHER_ID, "active"),
    )

    split = service.split_bill(bill_id, BillSplitRequest(for_ledger=False), _actor())

    assert set(split.participant_ids) == {SENDER_ID, ADVANCER_ID, OTHER_ID}
    assert split.allocation.allocations[OTHER_ID] == 0
    assert sum(split.allocation.allocations.values()) == 135000


def test_participant_ids_is_exactly_the_set_the_money_was_divided_between(repository):
    """The named set and the keys carrying money cannot drift apart.

    Without this, `participant_ids` could be filled from any roster read at
    all -- a second call, an unfiltered one -- and still look right in the
    case above, where every active member happens to be allocated something.
    """

    service = ApiService(repository)
    bill_id = _bill(service)
    repository.list_members = _roster(
        _membership(SENDER_ID, "active"),
        _membership(ADVANCER_ID, "active"),
        _membership(OTHER_ID, "active"),
    )

    split = service.split_bill(bill_id, BillSplitRequest(for_ledger=False), _actor())

    assert set(split.participant_ids) == set(split.allocation.allocations)


def test_split_names_the_roster_rows_it_left_out(repository):
    """An invited member is on the client's roster and out of the split.

    `GET /contexts/{id}/members` returns every row with `left_at IS NULL`,
    invitations included, and `split_bill` keeps only `active`. So a client
    rendering that roster shows a person the server never divided anything
    between, and today's response says nothing whatsoever about them -- they
    are absent from `allocations` in the same way a person the client has
    never heard of is absent, which is the ambiguity this field removes.
    """

    service = ApiService(repository)
    bill_id = _bill(service)
    repository.list_members = _roster(
        _membership(SENDER_ID, "active"),
        _membership(ADVANCER_ID, "active"),
        _membership(WATCHER_ID, "invited"),
    )

    split = service.split_bill(bill_id, BillSplitRequest(for_ledger=False), _actor())

    assert split.excluded_member_ids == [WATCHER_ID]
    assert WATCHER_ID not in split.participant_ids
    assert WATCHER_ID not in split.allocation.allocations


def test_nobody_is_named_in_both_lists(repository):
    """Negative control for the case above.

    `excluded_member_ids = participant_ids` satisfies "the invited member is
    named" and says the opposite of what the field means. The two lists
    partition the roster; they never overlap.
    """

    service = ApiService(repository)
    bill_id = _bill(service)
    repository.list_members = _roster(
        _membership(SENDER_ID, "active"),
        _membership(ADVANCER_ID, "active"),
        _membership(WATCHER_ID, "invited"),
    )

    split = service.split_bill(bill_id, BillSplitRequest(for_ledger=False), _actor())

    assert not set(split.participant_ids) & set(split.excluded_member_ids)


def test_an_ordinary_group_leaves_nobody_out(repository):
    """Negative control for the field itself.

    A hardcoded `excluded_member_ids` -- every id the roster carries, say --
    passes the invited case above. Here the roster is all active, so the
    honest answer is an empty list.
    """

    service = ApiService(repository)
    bill_id = _bill(service)

    split = service.split_bill(bill_id, BillSplitRequest(for_ledger=False), _actor())

    assert split.excluded_member_ids == []
    assert set(split.participant_ids) == {SENDER_ID, ADVANCER_ID}
