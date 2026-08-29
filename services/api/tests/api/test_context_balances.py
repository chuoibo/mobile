"""GET /contexts/{context_id}/balances orchestration tests."""

from __future__ import annotations

import uuid

from app.api.repository import AllocationRow, ConfirmedExpense

from .helpers import (
    ADVANCER_ID,
    CONTEXT_ID,
    OTHER_ID,
    SENDER_ID,
    actor_headers,
    create_batch,
    propose_and_confirm,
)


def _allow_member(repository, person_id=ADVANCER_ID):
    repository.active_memberships.add((CONTEXT_ID, person_id))


def _seed_expense(repository, *, paid_by_id, allocations):
    version_id = uuid.uuid4()
    repository.confirmed[version_id] = ConfirmedExpense(
        version_id=version_id,
        context_id=CONTEXT_ID,
        paid_by_id=paid_by_id,
        payer_acknowledgement="acknowledged",
        allocations=tuple(
            AllocationRow(
                id=uuid.uuid4(),
                participant_id=participant_id,
                amount_vnd=amount_vnd,
            )
            for participant_id, amount_vnd in allocations.items()
        ),
    )
    return version_id


def test_multiple_expenses_produce_stable_net_balances_and_minimal_plan(
    client, repository
):
    _allow_member(repository)
    _seed_expense(
        repository,
        paid_by_id=ADVANCER_ID,
        allocations={ADVANCER_ID: 20_000, SENDER_ID: 30_000, OTHER_ID: 50_000},
    )
    _seed_expense(
        repository,
        paid_by_id=SENDER_ID,
        allocations={ADVANCER_ID: 10_000, SENDER_ID: 40_000, OTHER_ID: 20_000},
    )

    response = client.get(f"/contexts/{CONTEXT_ID}/balances", headers=actor_headers())

    assert response.status_code == 200
    assert response.json() == {
        "balances": [
            {"person_id": str(ADVANCER_ID), "net_vnd": 70_000},
            {"person_id": str(OTHER_ID), "net_vnd": -70_000},
        ],
        "transfers": [
            {
                "sender_id": str(OTHER_ID),
                "recipient_id": str(ADVANCER_ID),
                "amount_vnd": 70_000,
            }
        ],
        "proven_minimal": True,
        "transfer_count": 1,
    }


def test_non_member_cannot_read_balances_even_with_forged_context_header(
    client, repository
):
    _allow_member(repository)

    response = client.get(
        f"/contexts/{CONTEXT_ID}/balances",
        headers=actor_headers(actor_id=OTHER_ID, roles="member"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "is_group_member"


def test_recipient_confirmed_receipt_reduces_balance(client, repository):
    _allow_member(repository)
    propose_and_confirm(client)
    obligation = create_batch(client, repository)["obligations"][0]
    balance_url = f"/contexts/{CONTEXT_ID}/balances"

    before = client.get(balance_url, headers=actor_headers())
    confirmation = client.post(
        f"/obligations/{obligation['obligation_id']}/confirm-receipt",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="recipient"),
        json={"amount_vnd": 10_000, "idempotency_key": str(uuid.uuid4())},
    )
    after = client.get(balance_url, headers=actor_headers())

    assert before.status_code == 200
    assert confirmation.status_code == 201
    assert after.status_code == 200
    assert before.json()["balances"] == [
        {"person_id": str(ADVANCER_ID), "net_vnd": 41_000},
        {"person_id": str(SENDER_ID), "net_vnd": -41_000},
    ]
    assert after.json()["balances"] == [
        {"person_id": str(ADVANCER_ID), "net_vnd": 31_000},
        {"person_id": str(SENDER_ID), "net_vnd": -31_000},
    ]
    assert after.json()["transfers"] == [
        {
            "sender_id": str(SENDER_ID),
            "recipient_id": str(ADVANCER_ID),
            "amount_vnd": 31_000,
        }
    ]


def test_zero_net_group_has_no_balances_or_transfer_proposals(client, repository):
    _allow_member(repository)
    _seed_expense(
        repository,
        paid_by_id=ADVANCER_ID,
        allocations={ADVANCER_ID: 50_000, SENDER_ID: 50_000},
    )
    _seed_expense(
        repository,
        paid_by_id=SENDER_ID,
        allocations={ADVANCER_ID: 50_000, SENDER_ID: 50_000},
    )

    response = client.get(f"/contexts/{CONTEXT_ID}/balances", headers=actor_headers())

    assert response.status_code == 200
    assert response.json() == {
        "balances": [],
        "transfers": [],
        "proven_minimal": True,
        "transfer_count": 0,
    }
