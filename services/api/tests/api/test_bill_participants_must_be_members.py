"""Assigning a bill item may only name people the group actually contains.

`#235` closed this hole on `POST /expenses/{id}/confirm`: the permission check
proved the *actor* belonged to the context, and then `proposal.participants`
came out of the request body unchecked, so money was written against people
nobody had ever added. `_require_participants_are_members` is the guard that
fixed it.

It is called in exactly one place. The bill path -- which is the one the PoC
demo actually walks, `CHỤP BILL → AI đọc từng món → gán món cho người` -- never
asks. `confirm_bill_assignments` proves the actor may touch this bill and then
hands `assignment.participant_ids` straight to the repository.

The arithmetic stays perfect while this is wrong, which is why no money rule
catches it: `ExpenseItemShare.participant_id` carries no foreign key into
`people`, so a well-formed UUID naming nobody is stored intact and comes back
out of `GET /bills/{id}` as somebody's dish.

`POST /bills/{id}/split` does refuse afterwards, but only by accident of
ordering: `split_bill` builds `participants` from the roster, so the allocator
finds a `shared_by` id it was not given and answers `UNKNOWN_PARTICIPANT`. That
is a late, unnamed refusal of a decision the product already accepted and drew
on screen -- and it is reachable only while the roster is non-empty, which is
the condition `split_bill`'s own fallback removes.

Ownership is a separate invariant from arithmetic and needs its own gate on
every path that writes a name, not just on the first one somebody noticed.
"""

from __future__ import annotations

import uuid

from tests.api.helpers import ADVANCER_ID, SENDER_ID, actor_headers
from tests.api.test_bills import create_bill

# Well-formed and deliberately unknown: a valid UUID is not evidence of a
# person, and a person is not evidence of a member.
STRANGER_ID = uuid.UUID("9ee00000-eeee-4eee-8eee-0000e000000b")


def _assign(client, bill_id, participant_ids):
    return client.put(
        f"/bills/{bill_id}/assignments",
        headers=actor_headers(),
        json={
            "assignments": [
                {
                    "item_key": "i1",
                    "participant_ids": [str(pid) for pid in participant_ids],
                },
                {"item_key": "i2", "participant_ids": [str(ADVANCER_ID)]},
            ]
        },
    )


def test_assigning_an_item_refuses_a_participant_the_group_does_not_contain(client):
    bill = create_bill(client)

    response = _assign(client, bill["id"], [STRANGER_ID])

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "participant_not_in_context"


def test_the_refusal_happens_before_the_share_is_stored(client):
    """A rejected assignment must not be readable afterwards.

    Refusing at `split` instead would leave `GET /bills/{id}` showing the dish
    as the stranger's -- the screen a person looks at while deciding whether
    the split is right.
    """

    bill = create_bill(client)

    _assign(client, bill["id"], [STRANGER_ID])

    stored = client.get(f"/bills/{bill['id']}", headers=actor_headers()).json()
    named = {
        share["participant_id"] for item in stored["items"] for share in item["shares"]
    }
    assert str(STRANGER_ID) not in named


def test_every_stranger_is_named_at_once_not_just_the_first(client):
    """One refusal per round trip would teach the roster by enumeration."""

    bill = create_bill(client)
    second_stranger = uuid.UUID("9ee00000-eeee-4eee-8eee-0000e000000c")

    response = _assign(client, bill["id"], [STRANGER_ID, second_stranger])

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert str(STRANGER_ID) in detail
    assert str(second_stranger) in detail


def test_an_assignment_naming_only_members_is_still_accepted(client):
    """The guard must refuse strangers without refusing the ordinary case."""

    bill = create_bill(client)

    response = _assign(client, bill["id"], [SENDER_ID])

    assert response.status_code == 200, response.text
    stored = {
        item["item_key"]: [share["participant_id"] for share in item["shares"]]
        for item in response.json()["items"]
    }
    assert stored["i1"] == [str(SENDER_ID)]
