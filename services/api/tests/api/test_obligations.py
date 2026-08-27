"""POST /obligations/{id}/confirm-receipt."""

from __future__ import annotations

import uuid

from .helpers import (
    ADVANCER_ID,
    OTHER_ID,
    actor_headers,
    create_batch,
    propose_and_confirm,
)


def _obligation(client, repository):
    propose_and_confirm(client)
    return create_batch(client, repository)["obligations"][0]


def test_only_exact_recipient_can_confirm_receipt(client, repository):
    obligation = _obligation(client, repository)
    response = client.post(
        f"/obligations/{obligation['obligation_id']}/confirm-receipt",
        headers=actor_headers(actor_id=OTHER_ID, roles="recipient"),
        json={
            "amount_vnd": obligation["amount_vnd"],
            "idempotency_key": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "is_recipient_of_this_obligation"
    assert repository.receipts == {}


def test_recipient_confirmation_derives_confirmed_status_from_event_sum(
    client, repository
):
    obligation = _obligation(client, repository)
    response = client.post(
        f"/obligations/{obligation['obligation_id']}/confirm-receipt",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="recipient"),
        json={
            "amount_vnd": obligation["amount_vnd"],
            "idempotency_key": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 201
    assert response.json()["obligation_status"] == "confirmed"
    assert len(repository.receipts) == 1
    assert not hasattr(next(iter(repository.obligations.values())), "status")


def test_receipt_money_rejects_string_before_repository(client, repository):
    obligation = _obligation(client, repository)
    response = client.post(
        f"/obligations/{obligation['obligation_id']}/confirm-receipt",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="recipient"),
        json={
            "amount_vnd": str(obligation["amount_vnd"]),
            "idempotency_key": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 422
    assert repository.receipts == {}


def test_receipt_confirmation_is_idempotent(client, repository):
    obligation = _obligation(client, repository)
    key = str(uuid.uuid4())
    payload = {"amount_vnd": obligation["amount_vnd"], "idempotency_key": key}
    url = f"/obligations/{obligation['obligation_id']}/confirm-receipt"
    headers = actor_headers(actor_id=ADVANCER_ID, roles="recipient")

    first = client.post(url, headers=headers, json=payload)
    second = client.post(url, headers=headers, json=payload)

    assert first.status_code == second.status_code == 201
    assert (
        first.json()["receipt_confirmation_id"]
        == second.json()["receipt_confirmation_id"]
    )
    assert len(repository.receipts) == 1
