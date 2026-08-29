"""Arrange a scanned bill into the frozen ADR-0004 allocator input.

This module *arranges*; it never *computes*. Turning "who ate what" into a
per-person amount is the allocator's job and only the allocator's job, because
two divisions living in one product is the surest way to show two different
numbers for one meal.

Everything here is therefore either a rename (``item_key`` becomes ``item_id``),
a passthrough (surcharges and discounts already carry the ADR-0004 shape), or a
refusal. There is no division in this file and a test parses the AST to keep it
that way.

The second thing this module carries is the distinction between what a model
guessed and what a person decided. An AI assignment is a suggestion; it is
allowed to be previewed and it is not allowed to reach the ledger. Losing that
distinction would mean charging somebody for a dish nobody confirmed they ate.
"""

from __future__ import annotations

__all__ = [
    "SHARE_CONFIRMED",
    "SHARE_SUGGESTED",
    "BillError",
    "allocator_input_from_bill",
]


SHARE_SUGGESTED = "ai_suggested"
SHARE_CONFIRMED = "confirmed"

_SHARE_SOURCES = frozenset({SHARE_SUGGESTED, SHARE_CONFIRMED})


class BillError(Exception):
    """Report one stable bill-projection failure.

    Distinct from ``AllocationError`` on purpose: these are failures of the
    *draft*, raised before any allocation is attempted. Anything the frozen
    allocator contract already has a code for is left for the allocator to
    reject, so that the two layers can never disagree about which code comes
    back (ADR-0004 blocker V2-02).
    """

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _by_key(items):
    """Visit items in byte order of their key, never in input order.

    Same rule as the allocator (ADR-0004 decision 20): reordering the input
    must not change which error code comes back.
    """
    return sorted(items, key=lambda item: str(item["item_key"]).encode("utf-8"))


def allocator_input_from_bill(bill: dict) -> dict:
    """Project one bill draft onto ADR-0004 allocator input.

    Returns the allocator input alongside the two facts the caller needs to
    decide whether this may touch the ledger: whether every assignment was
    confirmed by a person, and which items are still only guesses.
    """

    items = bill["items"]
    if not items:
        # A scanned bill with no lines means the read failed. Falling back to
        # an even split would dress that failure up as an answer.
        raise BillError("BILL_HAS_NO_ITEMS")

    for item in _by_key(items):
        if not item["shares"]:
            # Defaulting to "shared by everyone" fabricates an obligation.
            # ADR-0004 decision 4 rejects an empty shared_by for this reason.
            raise BillError("ITEM_HAS_NO_ASSIGNEE")

    for item in _by_key(items):
        for share in item["shares"]:
            if share["source"] not in _SHARE_SOURCES:
                # Fail closed: a source this module cannot read is not a
                # decision, and must not be mistaken for one.
                raise BillError("INVALID_SHARE_SOURCE")

    suggested_item_keys = sorted(
        (
            item["item_key"]
            for item in items
            if any(share["source"] == SHARE_SUGGESTED for share in item["shares"])
        ),
        key=lambda key: str(key).encode("utf-8"),
    )

    surcharges = bill["surcharges"]
    discounts = bill["discounts"]

    printed_total_vnd = bill["printed_total_vnd"]
    if printed_total_vnd is None:
        # No total was read off the paper, so the listed lines define it. This
        # is addition of amounts that were already listed, not a split: it
        # cannot produce a different per-person number.
        total_vnd = (
            sum(item["amount_vnd"] for item in items)
            + sum(surcharge["amount_vnd"] for surcharge in surcharges)
            - sum(discount["amount_vnd"] for discount in discounts)
        )
    else:
        # The paper wins. If the lines do not reach it, the allocator answers
        # RECONCILIATION_MISMATCH -- quietly stretching the bill here would
        # change the amount the user already looked at (ADR-0004 decision 1).
        total_vnd = printed_total_vnd

    return {
        "expense": {
            "participants": list(bill["participants"]),
            "total_vnd": total_vnd,
            "items": [
                {
                    "item_id": item["item_key"],
                    "amount_vnd": item["amount_vnd"],
                    "shared_by": [share["participant_id"] for share in item["shares"]],
                }
                for item in items
            ],
            "surcharges": list(surcharges),
            "discounts": list(discounts),
            "advancer_id": bill["advancer_id"],
        },
        "assignment_state": (
            SHARE_SUGGESTED if suggested_item_keys else SHARE_CONFIRMED
        ),
        "suggested_item_keys": suggested_item_keys,
    }
