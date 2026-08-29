"""Assigning a dish to somebody is the moment a name becomes a debt.

`#235` closed this hole at `confirm_expense`. It closed it at exactly one call
site. `PUT /bills/{id}/assignments` is the other one, and on the demo path it is
the one people actually touch: scan the bill, tap a dish, tap a face. The tap is
the decision -- the shares it writes are `human_confirmed`, not `ai_suggested`,
so they are ledger-eligible by construction.

`confirm_bill_assignments` proved the *actor* belongs to the context through
`_bill_for_actor` and then handed `assignment.participant_ids` to the repository
untouched. No layer underneath re-asks. `ExpenseItemShare.participant_id` carries
no foreign key into `people`, so a UUID naming nobody is stored intact, and
`POST /bills/{id}/split` then divides real money across it -- every arithmetic
invariant satisfied, the total reconciling to the last dong, against a person the
group has never contained.

The actor check and the participant check answer different questions. "May you
write here" is not "may this name be charged", and only the first one was asked.
"""

from __future__ import annotations

import uuid

from tests.api.helpers import ADVANCER_ID, SENDER_ID, actor_headers
from tests.api.test_bills import create_bill

# Well-formed and unknown on purpose: a parseable UUID is not evidence of a
# person, and a person is not evidence of a member.
STRANGER_ID = uuid.UUID("9ee00000-eeee-4eee-8eee-0000e0000009")
SECOND_STRANGER_ID = uuid.UUID("8ff00000-ffff-4fff-8fff-0000f0000008")


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


def _assign_second_item(client, bill_id, participant_ids):
    """The same request with the suspect name on the *second* dish.

    Every other case in this file puts the stranger on `i1`. A gate that only
    inspected `request.assignments[0]` passed all of them -- caught by mutation
    `only the first assignment checked`, which left both layers green. A bill is
    many lines and the stranger lands on whichever dish they were tapped onto.
    """

    return client.put(
        f"/bills/{bill_id}/assignments",
        headers=actor_headers(),
        json={
            "assignments": [
                {"item_key": "i1", "participant_ids": [str(SENDER_ID)]},
                {
                    "item_key": "i2",
                    "participant_ids": [str(pid) for pid in participant_ids],
                },
            ]
        },
    )


def _shares_of(repository, bill_id, item_key):
    bill = repository.bills[uuid.UUID(bill_id)]
    item = next(item for item in bill.items if item.item_key == item_key)
    return [share.participant_id for share in item.shares]


def test_assignment_refuses_a_participant_the_group_does_not_contain(
    client, repository
):
    bill = create_bill(client)

    response = _assign(client, bill["id"], [STRANGER_ID])

    assert response.status_code == 422
    assert response.json()["code"] == "participant_not_in_context"
    # Refused before the write, not tidied up after it. The suggestion the bill
    # was created with must still be the stored answer.
    assert _shares_of(repository, bill["id"], "i1") == [SENDER_ID]


def test_assignment_names_every_stranger_at_once_not_just_the_first(client, repository):
    """One refusal per unknown name turns the roster into something guessable,
    and gives a screen no way to say how many names are left to fix."""

    bill = create_bill(client)

    response = _assign(client, bill["id"], [STRANGER_ID, SECOND_STRANGER_ID])

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert str(STRANGER_ID) in detail
    assert str(SECOND_STRANGER_ID) in detail


def test_assignment_refuses_a_stranger_standing_beside_real_members(client, repository):
    """The realistic shape of the bug: a dish shared by two real people and one
    id that drifted in. A gate that only looked at the first participant, or
    only fired when *every* name was unknown, would let this through."""

    bill = create_bill(client)

    response = _assign(client, bill["id"], [SENDER_ID, STRANGER_ID, ADVANCER_ID])

    assert response.status_code == 422
    assert response.json()["code"] == "participant_not_in_context"
    assert _shares_of(repository, bill["id"], "i1") == [SENDER_ID]


def test_assignment_still_accepts_participants_who_are_all_members(client, repository):
    """Without this the whole file stays green if the route starts answering
    422 to every assignment, which would break the demo path outright."""

    bill = create_bill(client)

    response = _assign(client, bill["id"], [SENDER_ID, ADVANCER_ID])

    assert response.status_code == 200, response.text
    assert _shares_of(repository, bill["id"], "i1") == [SENDER_ID, ADVANCER_ID]


def test_assignment_refuses_a_stranger_on_a_later_dish_not_only_the_first(
    client, repository
):
    """Found by mutation, not by reading: restricting the gate to
    `request.assignments[:1]` left every other case in this file green, on both
    the fake and the live layer. The rule is about the whole request."""

    bill = create_bill(client)

    response = _assign_second_item(client, bill["id"], [ADVANCER_ID, STRANGER_ID])

    assert response.status_code == 422
    assert response.json()["code"] == "participant_not_in_context"
    assert str(STRANGER_ID) in response.json()["detail"]
    assert _shares_of(repository, bill["id"], "i2") == [ADVANCER_ID]
