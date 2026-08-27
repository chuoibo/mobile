"""POST /expenses and POST /expenses/{id}/confirm."""

from __future__ import annotations

import uuid

from app.domain import permissions

from .helpers import ADVANCER_ID, actor_headers, expense_payload


def test_proposal_calls_allocator_but_does_not_write_the_ledger(client, repository):
    response = client.post("/expenses", json=expense_payload())

    assert response.status_code == 201
    body = response.json()
    assert sum(body["allocation"]["allocations"].values()) == 82000
    assert len(repository.expenses) == 1
    assert repository.confirmed == {}


def test_malformed_wire_money_never_reaches_domain_or_storage(client, repository):
    response = client.post("/expenses", json=expense_payload(total="82000"))

    assert response.status_code == 422
    assert repository.expenses == {}
    assert repository.confirmed == {}


def test_confirm_writes_version_and_allocations_and_calls_central_permissions(
    client, repository, monkeypatch
):
    proposed = client.post("/expenses", json=expense_payload()).json()
    calls = []
    real = permissions.denial_reason

    def recording_denial(action, roles, context=None):
        calls.append((action, set(roles), dict(context or {})))
        return real(action, roles, context)

    monkeypatch.setattr(permissions, "denial_reason", recording_denial)
    response = client.post(
        f"/expenses/{proposed['expense_id']}/confirm",
        headers=actor_headers(),
        json={
            "proposal": proposed["proposal"],
            "expected_allocations": proposed["allocation"]["allocations"],
            "acknowledge_as_advancer": True,
        },
    )

    assert response.status_code == 201
    body = response.json()
    stored = repository.confirmed[uuid.UUID(body["expense_version_id"])]
    assert sum(row.amount_vnd for row in stored.allocations) == 82000
    assert stored.payer_acknowledgement == "acknowledged"
    assert [call[0] for call in calls] == [
        "confirm_expense_proposal",
        "acknowledge_advancer_role",
    ]


def test_confirm_rejects_unreviewed_allocation_change(client, repository):
    proposed = client.post("/expenses", json=expense_payload()).json()
    allocations = proposed["allocation"]["allocations"]
    allocations[str(ADVANCER_ID)] += 1

    response = client.post(
        f"/expenses/{proposed['expense_id']}/confirm",
        headers=actor_headers(),
        json={
            "proposal": proposed["proposal"],
            "expected_allocations": allocations,
            "acknowledge_as_advancer": True,
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "proposal_changed"
    assert repository.confirmed == {}


def test_confirm_permission_is_not_an_inline_role_check(client, repository):
    proposed = client.post("/expenses", json=expense_payload()).json()
    response = client.post(
        f"/expenses/{proposed['expense_id']}/confirm",
        headers=actor_headers(roles="group_admin"),
        json={
            "proposal": proposed["proposal"],
            "expected_allocations": proposed["allocation"]["allocations"],
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        "code": "permission_denied",
        "detail": "role_not_permitted",
    }
    assert repository.confirmed == {}
