"""A confirmed expense may only charge people the group actually contains.

The three money rules in `CLAUDE.md` are all arithmetic: integer dong, the
allocations sum to the total, the balance recomputes from the ledger. An
expense naming a stranger satisfies every one of them. `41` golden vectors
stay green, the sum still reconciles to the last dong, and the ledger still
replays -- onto a person who was never in the group.

That is not hypothetical. On 2026-08-29 the split screen minted a fresh
`person` per typed name and wrote `329_667 + 329_667 + 329_666 = 989_000`,
perfect to the dong, to three people who did not exist. The real person's
balance did not move. The client half of that has since changed; the server
half had not, and the server is the half that decides what the ledger says.

`confirm_expense` proved the *actor* belongs to the context and then took
`proposal.participants` from the request body unchecked. Nothing downstream
re-asks: `ConfirmedAllocation.participant_id` and `ExpenseItemShare.participant_id`
carry no foreign key into `people`, so not even PostgreSQL refuses a UUID
nobody has ever seen.

Ownership is a separate invariant from arithmetic, and it needs its own gate.
"""

from __future__ import annotations

import uuid

from .helpers import ADVANCER_ID, SENDER_ID, actor_headers, expense_payload

# Deliberately well-formed and deliberately unknown: the point is that a valid
# UUID is not evidence of a person, and a person is not evidence of a member.
STRANGER_ID = uuid.UUID("9ee00000-eeee-4eee-8eee-0000e0000009")


def _propose_and_confirm(client, participants):
    proposed = client.post(
        "/expenses", json=expense_payload(participants=participants)
    ).json()
    return client.post(
        f"/expenses/{proposed['expense_id']}/confirm",
        headers=actor_headers(),
        json={
            "proposal": proposed["proposal"],
            "expected_allocations": proposed["allocation"]["allocations"],
            "acknowledge_as_advancer": True,
        },
    )


def test_confirm_refuses_a_participant_the_group_does_not_contain(client, repository):
    response = _propose_and_confirm(client, [ADVANCER_ID, STRANGER_ID])

    assert response.status_code == 422
    assert response.json()["code"] == "participant_not_in_context"
    # The refusal has to happen before the write, not be cleaned up after it.
    assert repository.confirmed == {}


def test_confirm_names_every_stranger_at_once_not_just_the_first(client, repository):
    """One round trip per unknown name would teach the roster by enumeration.

    It is also just bad to use: a screen fixing names one at a time cannot
    tell the person how many are left.
    """
    second_stranger = uuid.UUID("8ff00000-ffff-4fff-8fff-0000f0000008")

    response = _propose_and_confirm(client, [ADVANCER_ID, STRANGER_ID, second_stranger])

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert str(STRANGER_ID) in detail
    assert str(second_stranger) in detail
    assert repository.confirmed == {}


def test_confirm_still_accepts_an_expense_whose_participants_are_all_members(
    client, repository
):
    """The negative case above proves nothing if the positive case cannot pass.

    Without this, deleting the whole feature and answering 422 to every
    confirmation would leave the file green.
    """
    response = _propose_and_confirm(client, [ADVANCER_ID, SENDER_ID])

    assert response.status_code == 201
    stored = repository.confirmed[uuid.UUID(response.json()["expense_version_id"])]
    assert sum(row.amount_vnd for row in stored.allocations) == 82000
