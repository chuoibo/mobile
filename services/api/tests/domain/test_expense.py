"""Confirmed-expense scalar roll-ups stay in the pure domain layer."""

from __future__ import annotations

from app.domain.expense import component_rollups


def test_pure_even_split_projects_total_to_subtotal():
    assert component_rollups(
        {
            "items": [],
            "surcharges": [],
            "discounts": [],
            "total_vnd": 82000,
        }
    ) == {
        "subtotal_amount_vnd": 82000,
        "fee_amount_vnd": 0,
        "vat_amount_vnd": 0,
        "shipping_amount_vnd": 0,
        "discount_amount_vnd": 0,
        "total_amount_vnd": 82000,
    }


def test_itemized_rollups_keep_vat_shipping_and_catch_all_fee_separate():
    result = component_rollups(
        {
            "items": [{"amount_vnd": 100000}, {"amount_vnd": 50000}],
            "surcharges": [
                {"kind": "VAT", "amount_vnd": 12000},
                {"kind": "shipping", "amount_vnd": 5000},
                {"kind": "service", "amount_vnd": 3000},
            ],
            "discounts": [{"amount_vnd": 10000}],
            "total_vnd": 160000,
        }
    )

    assert result == {
        "subtotal_amount_vnd": 150000,
        "fee_amount_vnd": 3000,
        "vat_amount_vnd": 12000,
        "shipping_amount_vnd": 5000,
        "discount_amount_vnd": 10000,
        "total_amount_vnd": 160000,
    }
    assert all(isinstance(value, int) for value in result.values())
