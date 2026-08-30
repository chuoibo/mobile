"""PROBE -- not a gate. Measures what `for_ledger` actually withholds.

Deleted before commit. Written to answer one question with numbers instead of
reading: does refusing `for_ledger=True` keep an unconfirmed split away from
the ledger, or only away from callers who volunteer the flag?
"""

from __future__ import annotations

import uuid

from tests.api.helpers import ADVANCER_ID, CONTEXT_ID, SENDER_ID, actor_headers
from tests.api.test_bills import bill_payload, confirm_all, create_bill


def test_probe(client):
    print("\n=== PROBE: what does for_ledger withhold? ===")

    bill = create_bill(client)
    print(f"bill created, assignment_state={bill['assignment_state']!r}")

    # A. the flag is set -> refused
    refused = client.post(
        f"/bills/{bill['id']}/split",
        headers=actor_headers(),
        json={"for_ledger": True, "paid_by_id": str(ADVANCER_ID)},
    )
    print(f"A. for_ledger=True   -> {refused.status_code} {refused.json().get('code')}")

    # B. the same bill, flag omitted
    preview = client.post(
        f"/bills/{bill['id']}/split",
        headers=actor_headers(),
        json={"paid_by_id": str(ADVANCER_ID)},
    )
    print(f"B. flag omitted      -> {preview.status_code}")
    b_alloc = preview.json()["allocation"]["allocations"]
    print(f"   allocations       = {b_alloc}")
    print(f"   assignment_state  = {preview.json()['assignment_state']!r}")

    # C. now confirm the very same assignments and ask again with the flag
    confirm_all(client, bill["id"])
    allowed = client.post(
        f"/bills/{bill['id']}/split",
        headers=actor_headers(),
        json={"for_ledger": True, "paid_by_id": str(ADVANCER_ID)},
    )
    c_alloc = allowed.json()["allocation"]["allocations"]
    print(f"C. confirmed + flag  -> {allowed.status_code}")
    print(f"   allocations       = {c_alloc}")
    print(f"   B == C ?          = {b_alloc == c_alloc}")

    # D. can the numbers from B reach the ledger? Nothing links a bill to an
    #    expense, so the ledger route never sees the bill at all.
    fresh = create_bill(client)
    unconfirmed = client.post(
        f"/bills/{fresh['id']}/split",
        headers=actor_headers(),
        json={"paid_by_id": str(ADVANCER_ID)},
    ).json()
    print(f"D. fresh bill state  = {unconfirmed['assignment_state']!r}")

    proposed = client.post(
        "/expenses",
        headers=actor_headers(),
        json={
            "context_id": str(CONTEXT_ID),
            "description": "Bill chua ai xac nhan",
            "recorded_by_id": str(ADVANCER_ID),
            "paid_by_id": str(ADVANCER_ID),
            "verification_scope": "totals_only",
            "occurred_at": "2030-08-27T12:00:00+07:00",
            "participants": [str(SENDER_ID), str(ADVANCER_ID)],
            "total_amount_vnd": unconfirmed["total_amount_vnd"],
            "items": [
                {
                    "item_id": "i1",
                    "amount_vnd": 65000,
                    "shared_by": [str(SENDER_ID)],
                },
                {
                    "item_id": "i2",
                    "amount_vnd": 70000,
                    "shared_by": [str(ADVANCER_ID)],
                },
            ],
            "surcharges": [],
            "discounts": [],
        },
    )
    print(f"   POST /expenses    -> {proposed.status_code}")
    if proposed.status_code < 300:
        body = proposed.json()
        expense_id = body["expense_id"]
        print(f"   allocations       = {body['allocation']['allocations']}")
        print(f"   same as B ?       = {body['allocation']['allocations'] == b_alloc}")
        confirmed = client.post(
            f"/expenses/{expense_id}/confirm",
            headers=actor_headers(),
            json={"expected_version": body["version"], "idempotency_key": str(uuid.uuid4())},
        )
        print(f"   POST confirm      -> {confirmed.status_code}")
        if confirmed.status_code >= 300:
            print(f"   confirm body      = {confirmed.text[:300]}")

    print("=== END PROBE ===")
