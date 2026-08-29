"""A discount must declare a target exactly when its scope says it has one.

ADR-0004 already owns this rule and already has a code for it,
SCOPE_TARGET_MISMATCH, checked in the allocator's structural group. But a bill
draft is written to the database long before anything is allocated, and
`ck_bill_discounts_scope_target_match` refuses the incoherent row at INSERT
time -- so the allocator never gets to answer, and what the caller sees is
whatever `create_bill` does with an `IntegrityError`.

That makes an ordinary malformed body reachable straight through to a 500, a
status `routes/bills.py` does not declare, and it is the same defect as the
repeated `item_key`: the constraint is right and the shape of the refusal is
wrong. Structural validation belongs at the wire, before any write.

The two directions matter separately. `global_proportional` carrying a target
would silently apply to one item under one reading and to everybody under
another; `item` without a target has no item to subtract from.
"""

from __future__ import annotations

from tests.api.helpers import ADVANCER_ID, CONTEXT_ID, actor_headers


def bill_with_discount(discount):
    return {
        "context_id": str(CONTEXT_ID),
        "printed_total_vnd": 90000,
        "items_total_vnd": 100000,
        "confidence": 88,
        "needs_review": False,
        "items": [
            {
                "item_key": "com-tam",
                "name": "Cơm tấm",
                "quantity": 1,
                "unit_price_vnd": 100000,
                "line_total_vnd": 100000,
                "suggested_participant_ids": [str(ADVANCER_ID)],
            }
        ],
        "discounts": [discount],
    }


def test_a_global_discount_carrying_a_target_is_refused_at_the_wire(client):
    response = client.post(
        "/bills",
        headers=actor_headers(),
        json=bill_with_discount(
            {
                "discount_key": "voucher",
                "amount_vnd": 10000,
                "scope": "global_proportional",
                "item_key": "com-tam",
            }
        ),
    )

    assert response.status_code == 422, response.text


def test_an_item_discount_without_a_target_is_refused_at_the_wire(client):
    response = client.post(
        "/bills",
        headers=actor_headers(),
        json=bill_with_discount(
            {
                "discount_key": "voucher",
                "amount_vnd": 10000,
                "scope": "item",
            }
        ),
    )

    assert response.status_code == 422, response.text


def test_a_coherent_item_discount_is_still_accepted(client):
    """The control. A validator that refused everything would pass both cases
    above while breaking the feature."""

    response = client.post(
        "/bills",
        headers=actor_headers(),
        json=bill_with_discount(
            {
                "discount_key": "voucher",
                "amount_vnd": 10000,
                "scope": "item",
                "item_key": "com-tam",
            }
        ),
    )

    assert response.status_code == 201, response.text
    assert response.json()["discounts"] == [
        {
            "discount_key": "voucher",
            "amount_vnd": 10000,
            "scope": "item",
            "item_key": "com-tam",
        }
    ]
