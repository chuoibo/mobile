"""Pure projections needed when a confirmed expense enters the ledger."""

from __future__ import annotations

__all__ = ["component_rollups"]


def component_rollups(expense: dict) -> dict[str, int]:
    """Derive the scalar database roll-ups without losing child-line facts.

    ``ExpenseSurcharge.kind`` remains the source of detail. The legacy ``fee``
    roll-up is the catch-all for surcharge kinds other than VAT and shipping;
    otherwise an allocator-valid service charge could not be represented by the
    current five-column projection. A pure even split has no item lines, so its
    total is its subtotal.

    Callers run the allocator first. This function intentionally performs no
    second, competing validation pass.
    """

    items = expense["items"]
    surcharges = expense["surcharges"]
    discounts = expense["discounts"]

    subtotal = sum(item["amount_vnd"] for item in items)
    if not items and not surcharges and not discounts:
        subtotal = expense["total_vnd"]

    vat = sum(
        surcharge["amount_vnd"]
        for surcharge in surcharges
        if surcharge["kind"].casefold() == "vat"
    )
    shipping = sum(
        surcharge["amount_vnd"]
        for surcharge in surcharges
        if surcharge["kind"].casefold() == "shipping"
    )
    fee = sum(
        surcharge["amount_vnd"]
        for surcharge in surcharges
        if surcharge["kind"].casefold() not in {"vat", "shipping"}
    )
    discount = sum(line["amount_vnd"] for line in discounts)
    return {
        "subtotal_amount_vnd": subtotal,
        "fee_amount_vnd": fee,
        "vat_amount_vnd": vat,
        "shipping_amount_vnd": shipping,
        "discount_amount_vnd": discount,
        "total_amount_vnd": expense["total_vnd"],
    }
