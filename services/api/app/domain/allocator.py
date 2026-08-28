"""Split one expense into integer VND obligations.

Implements ADR-0004, frozen 2026-08-27 after four review rounds with Codex.
The contract is the specification; this file is one reading of it. Where the two
disagree, the contract wins and this file is wrong.

Two hard rules from the product spec section 4:

  * money is integer dong -- no float anywhere, not even in intermediates
  * the allocations sum to the expense total exactly, 100% of the time

`Fraction` carries exact rational arithmetic through the pipeline so that
rounding happens once, at the end, and never accumulates.
"""

from __future__ import annotations

from fractions import Fraction

from .contract import (
    DISCOUNT_SCOPES,
    MAX_AMOUNT_VND,
    MAX_ID_BYTES,
    SURCHARGE_MODES,
    AllocationError,
)

__all__ = ["allocate"]


# --------------------------------------------------------------------------
# validation -- ADR-0004 section 6, one total function
#
# Precedence is: structural, then referential, then arithmetic, then
# reconciliation. Within a group, elements are visited in byte order of their
# id, never in input order, so that reordering the input cannot change which
# code comes back (ADR-0004 decision 20, property 11).
# --------------------------------------------------------------------------


def _is_valid_id(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if value != value.strip():
        return False
    return len(value.encode("utf-8")) <= MAX_ID_BYTES


def _by_id(elements, key):
    return sorted(elements, key=lambda e: str(e.get(key, "")).encode("utf-8"))


def _validate_structure(expense) -> None:
    participants = expense["participants"]
    items = expense["items"]
    surcharges = expense["surcharges"]
    discounts = expense["discounts"]

    if not participants:
        raise AllocationError("NO_PARTICIPANTS")

    for participant in sorted(participants, key=lambda p: str(p).encode("utf-8")):
        if not _is_valid_id(participant):
            raise AllocationError("INVALID_PARTICIPANT_ID")

    if len(set(participants)) != len(participants):
        raise AllocationError("DUPLICATE_PARTICIPANT")

    # Three separate namespaces: an item and a discount may share an id.
    for elements, key in ((items, "item_id"), (surcharges, "surcharge_id"), (discounts, "discount_id")):
        for element in _by_id(elements, key):
            if not _is_valid_id(element[key]):
                raise AllocationError("INVALID_ENTITY_ID")
    for elements, key in ((items, "item_id"), (surcharges, "surcharge_id"), (discounts, "discount_id")):
        ids = [element[key] for element in elements]
        if len(set(ids)) != len(ids):
            raise AllocationError("DUPLICATE_ENTITY_ID")

    amounts = [("total", expense["total_vnd"])]
    amounts += [(i["item_id"], i["amount_vnd"]) for i in _by_id(items, "item_id")]
    amounts += [(s["surcharge_id"], s["amount_vnd"]) for s in _by_id(surcharges, "surcharge_id")]
    amounts += [(d["discount_id"], d["amount_vnd"]) for d in _by_id(discounts, "discount_id")]

    for _, amount in amounts:
        if amount < 0:
            raise AllocationError("NEGATIVE_AMOUNT")
    # Zero is rejected for line items but allowed for the expense total: a bill
    # of zero splits into zeroes, while a line item of zero is a data error.
    for name, amount in amounts:
        if name != "total" and amount == 0:
            raise AllocationError("ZERO_AMOUNT")
    for _, amount in amounts:
        if amount > MAX_AMOUNT_VND:
            raise AllocationError("AMOUNT_TOO_LARGE")

    for surcharge in _by_id(surcharges, "surcharge_id"):
        kind = surcharge["kind"]
        if not isinstance(kind, str) or not kind or len(kind.encode("utf-8")) > 32:
            raise AllocationError("INVALID_KIND")
    for surcharge in _by_id(surcharges, "surcharge_id"):
        if surcharge["mode"] not in SURCHARGE_MODES:
            raise AllocationError("INVALID_MODE")

    for discount in _by_id(discounts, "discount_id"):
        if discount["scope"] not in DISCOUNT_SCOPES:
            raise AllocationError("INVALID_SCOPE")
    for discount in _by_id(discounts, "discount_id"):
        targets_item = discount["scope"] == "item"
        has_target = discount.get("item_id") is not None
        if targets_item != has_target:
            raise AllocationError("SCOPE_TARGET_MISMATCH")

    for item in _by_id(items, "item_id"):
        if not item["shared_by"]:
            raise AllocationError("EMPTY_SHARED_BY")
    for item in _by_id(items, "item_id"):
        shared_by = item["shared_by"]
        if len(set(shared_by)) != len(shared_by):
            raise AllocationError("DUPLICATE_SHARED_BY")


def _validate_references(expense) -> None:
    """Declarations are validated; references are resolved (ADR-0004 V2-02).

    So `shared_by = [""]` is UNKNOWN_PARTICIPANT rather than an invalid id, and
    `advancer_id = ""` is not an error at all -- it becomes a warning. Choosing
    otherwise reopens the fork this rule exists to close.
    """
    participants = set(expense["participants"])
    for item in _by_id(expense["items"], "item_id"):
        for participant in sorted(item["shared_by"], key=lambda p: str(p).encode("utf-8")):
            if participant not in participants:
                raise AllocationError("UNKNOWN_PARTICIPANT")

    item_ids = {item["item_id"] for item in expense["items"]}
    for discount in _by_id(expense["discounts"], "discount_id"):
        if discount["scope"] == "item" and discount["item_id"] not in item_ids:
            raise AllocationError("UNKNOWN_ITEM")


# --------------------------------------------------------------------------
# pipeline -- ADR-0004 section 2, five stages, one rounding point
# --------------------------------------------------------------------------


def _item_net(expense) -> dict[str, Fraction]:
    net = {item["item_id"]: Fraction(item["amount_vnd"]) for item in expense["items"]}
    for discount in expense["discounts"]:
        if discount["scope"] == "item":
            net[discount["item_id"]] -= discount["amount_vnd"]
    for item in _by_id(expense["items"], "item_id"):
        if net[item["item_id"]] < 0:
            raise AllocationError("DISCOUNT_EXCEEDS_ITEM")
    return net


def _exact_shares(expense) -> tuple[dict[str, Fraction], list[str]]:
    participants = expense["participants"]
    count = len(participants)
    warnings: list[str] = []

    is_even_split = not expense["items"] and not expense["surcharges"] and not expense["discounts"]
    if is_even_split:
        total = Fraction(expense["total_vnd"])
        return {p: total / count for p in participants}, warnings

    # Stage 1 -- item shares, net of item-scoped discounts, split evenly.
    net = _item_net(expense)
    base = {p: Fraction(0) for p in participants}
    for item in expense["items"]:
        share = net[item["item_id"]] / len(item["shared_by"])
        for participant in item["shared_by"]:
            base[participant] += share

    # Stage 2 -- global discounts, proportional.
    total_base = sum(base.values(), Fraction(0))
    global_discount = sum(
        (Fraction(d["amount_vnd"]) for d in expense["discounts"] if d["scope"] == "global_proportional"),
        Fraction(0),
    )
    if global_discount > total_base:
        raise AllocationError("DISCOUNT_EXCEEDS_BASE")
    if total_base > 0:
        factor = (total_base - global_discount) / total_base
        base = {p: value * factor for p, value in base.items()}

    # Reconciliation is checked here, after the arithmetic group, because a
    # discount that overshoots almost always drags the totals apart too, and
    # reporting the mismatch would point the user at the wrong place.
    listed = (
        sum(item["amount_vnd"] for item in expense["items"])
        + sum(s["amount_vnd"] for s in expense["surcharges"])
        - sum(d["amount_vnd"] for d in expense["discounts"])
    )
    if listed != expense["total_vnd"]:
        raise AllocationError("RECONCILIATION_MISMATCH")

    # Stage 3 -- surcharges.
    basis = sum(base.values(), Fraction(0))
    extra = {p: Fraction(0) for p in participants}
    for surcharge in expense["surcharges"]:
        amount = Fraction(surcharge["amount_vnd"])
        if surcharge["mode"] == "even" or basis == 0:
            if surcharge["mode"] == "proportional":
                # No proportional basis exists, so even is the only defensible
                # distribution. Say so out loud rather than dividing by zero.
                if "proportional_fallback_to_even" not in warnings:
                    warnings.append("proportional_fallback_to_even")
            for participant in participants:
                extra[participant] += amount / count
        else:
            for participant in participants:
                extra[participant] += amount * base[participant] / basis

    # Stage 4.
    return {p: base[p] + extra[p] for p in participants}, warnings


# --------------------------------------------------------------------------
# stage 5 -- largest remainder, the only rounding point
# --------------------------------------------------------------------------


def _apportion(total_vnd: int, exact: dict[str, Fraction], advancer_id):
    floors = {p: value.numerator // value.denominator for p, value in exact.items()}
    deficit = total_vnd - sum(floors.values())

    def rank(participant: str):
        remainder = exact[participant] - floors[participant]
        is_advancer = advancer_id is not None and participant == advancer_id
        return (0 if is_advancer else 1, -remainder, participant.encode("utf-8"))

    # The advancer wins ties only. Remainder is the primary key, so a larger
    # remainder always beats the advancer -- "wins the tie-break" is not a
    # global priority. Winning means taking the extra dong, so the person who
    # fronted the money absorbs the rounding.
    ranked = sorted(exact, key=rank)
    gainers = ranked[:deficit]

    allocations = {p: floors[p] + (1 if p in set(gainers) else 0) for p in exact}
    return allocations, gainers


def allocate(expense: dict) -> dict:
    """Split `expense` into integer VND per participant.

    Raises AllocationError with a code from contract.ERROR_PRECEDENCE.
    """
    _validate_structure(expense)
    _validate_references(expense)

    exact, warnings = _exact_shares(expense)
    total_vnd = expense["total_vnd"]

    if sum(exact.values(), Fraction(0)) != Fraction(total_vnd):
        # Unreachable if the stages above are correct. Kept because a silent
        # violation here would produce obligations that do not sum to the bill.
        raise AssertionError("exact shares do not sum to the expense total")

    allocations, gainers = _apportion(total_vnd, exact, expense["advancer_id"])

    advancer = expense["advancer_id"]
    if advancer is not None and advancer not in expense["participants"]:
        warnings.append("advancer_not_participant")
    if total_vnd > 0 and any(value == 0 for value in exact.values()):
        warnings.append("zero_share_participants")

    return {
        "allocations": allocations,
        "exact_shares": {p: f"{v.numerator}/{v.denominator}" for p, v in exact.items()},
        "rounding_gainers": list(gainers),
        "warnings": sorted(set(warnings)),
    }
