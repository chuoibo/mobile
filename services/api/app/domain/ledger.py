"""The ledger: who owes whom, derived from confirmed allocations.

Product spec section 4 and section 8. Three rules shape everything here:

  * The ledger is the source of truth and balances are always recomputable.
    Nothing in this module caches a balance, and nothing accepts one as input.
  * An obligation is a single directed edge, sender -> recipient. Obligations
    for the same pair inside one batch are summed. Obligations toward
    *different* recipients are never offset against each other.
  * A sender saying "I transferred" changes nothing. Only the recipient
    confirming receipt moves an obligation, and even then that confirmation is
    not bank evidence -- it is a human pressing a button.

Pure functions over plain dicts. No I/O, no ORM, no framework.
"""

from __future__ import annotations

from collections import defaultdict

__all__ = [
    "LedgerError",
    "require_vnd",
    "obligations_from_allocations",
    "merge_obligations",
    "confirmed_total",
    "obligation_status",
    "group_balances",
    "settlement_suggestions",
]


class LedgerError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def require_vnd(value, *, positive: bool = False) -> int:
    """One validator, used by every entry point that touches money.

    Every function here used to check amounts differently, or not at all, and
    review found three ways in: an advancer's negative allocation skipped
    because the advancer branch ran first, a negative amount summed inside
    merge, and a float surviving all the way into a suggested transfer.

    `bool` is rejected explicitly because `isinstance(True, int)` is True in
    Python, and `True` would silently become one dong.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise LedgerError("AMOUNT_NOT_INTEGER")
    if value < 0:
        raise LedgerError("NEGATIVE_AMOUNT")
    if positive and value == 0:
        raise LedgerError("NON_POSITIVE_AMOUNT")
    return value


def obligations_from_allocations(
    allocations: dict[str, int],
    advancer_id: str | None,
    expense_version_id: str,
) -> list[dict]:
    """Turn one expense version's confirmed allocations into directed edges.

    The advancer fronted the money, so everyone else owes them their share.
    The advancer's own share creates no obligation -- they already paid it.

    An advancer who is not among the participants still gets no share (see
    ADR-0004 decision 7) but is still the creditor: they are the one out of
    pocket.
    """
    if advancer_id is None:
        # Without knowing who fronted the money there is no creditor, and an
        # obligation with no creditor is a debt owed to nobody.
        raise LedgerError("NO_ADVANCER")

    # Validate the whole map first. Skipping the advancer before validating
    # meant a negative allocation on the advancer never got checked at all.
    for amount in allocations.values():
        require_vnd(amount)

    obligations = []
    for participant, amount in allocations.items():
        if participant == advancer_id:
            continue
        if amount == 0:
            # Someone who owes nothing gets no payment request. Sending a
            # zero-dong obligation would be pure noise.
            continue
        obligations.append({
            "sender_id": participant,
            "recipient_id": advancer_id,
            "amount_vnd": amount,
            "source_expense_version_id": expense_version_id,
        })
    return obligations


def merge_obligations(obligations: list[dict]) -> list[dict]:
    """Sum obligations sharing a (sender, recipient) pair. Never across pairs.

    Spec section 8.2. Two dinners where Ha owes Nam become one request to Ha.
    But Ha owing Nam and Nam owing Ha stay two separate obligations, because
    cancelling them is an offset, and section 8.8 makes an offset a social
    agreement that every affected party has to accept -- not an arithmetic
    convenience the system may apply on its own.
    """
    totals: dict[tuple[str, str], int] = defaultdict(int)
    sources: dict[tuple[str, str], list[str]] = defaultdict(list)
    for obligation in obligations:
        sender = obligation["sender_id"]
        recipient = obligation["recipient_id"]
        if sender == recipient:
            raise LedgerError("SELF_OBLIGATION")
        pair = (sender, recipient)
        totals[pair] += require_vnd(obligation["amount_vnd"], positive=True)
        sources[pair].append(obligation["source_expense_version_id"])

    merged = []
    for (sender, recipient) in sorted(totals, key=lambda p: (p[0].encode(), p[1].encode())):
        merged.append({
            "sender_id": sender,
            "recipient_id": recipient,
            "amount_vnd": totals[(sender, recipient)],
            "source_expense_version_ids": tuple(sorted(set(sources[(sender, recipient)]))),
        })
    return merged


def confirmed_total(receipt_confirmations: list[dict]) -> int:
    """Sum of amounts the recipient has confirmed receiving."""
    total = 0
    for confirmation in receipt_confirmations:
        amount = confirmation["amount_vnd"]
        if amount <= 0:
            raise LedgerError("NON_POSITIVE_CONFIRMATION")
        total += amount
    return total


def obligation_status(declared_amount_vnd: int, receipt_confirmations: list[dict]) -> str:
    """Derive status from confirmed amounts. Never stored as an enum.

    Spec section 8.2 is explicit that obligation state is derived from the sum
    of confirmed amounts. Storing a status column invites it to drift from the
    events that justify it.

    `PaymentReport` -- the sender saying they transferred -- is deliberately
    not an input. Spec section 8.6: self-report never closes an obligation.

    `over_confirmed` is not an error. A recipient can fat-finger the amount, or
    a sender can overpay, and the ledger must be able to show that rather than
    clamp it out of sight.
    """
    if declared_amount_vnd <= 0:
        raise LedgerError("NON_POSITIVE_OBLIGATION")
    confirmed = confirmed_total(receipt_confirmations)
    if confirmed == 0:
        return "outstanding"
    if confirmed < declared_amount_vnd:
        return "partially_confirmed"
    if confirmed == declared_amount_vnd:
        return "confirmed"
    return "over_confirmed"


def group_balances(obligations: list[dict], receipts: dict[tuple[str, str], int] | None = None) -> dict[str, int]:
    """Netted per-person position, for DISPLAY ONLY.

    Spec section 8.8: the group balance is always shown netted. That is a
    display rule, and it is the opposite of the batch rule two functions up.

    Positive means the group owes this person; negative means they owe.

    The output of this function must never be turned back into obligations. A
    netted position implies pairings nobody agreed to -- exactly the social
    change section 8.8 requires everyone affected to accept first.
    """
    receipts = receipts or {}

    # Sum by pair BEFORE subtracting. The previous version subtracted the pair
    # receipt from every obligation in that pair, so two obligations of 60 and
    # 40 against a receipt of 50 showed a remaining 10 instead of 50: the same
    # payment counted twice. A balance that reads low is the dangerous
    # direction, because nobody chases what they think they already received.
    owed: dict[tuple[str, str], int] = defaultdict(int)
    for obligation in obligations:
        sender, recipient = obligation["sender_id"], obligation["recipient_id"]
        if sender == recipient:
            raise LedgerError("SELF_OBLIGATION")
        owed[(sender, recipient)] += require_vnd(obligation["amount_vnd"], positive=True)

    positions: dict[str, int] = defaultdict(int)
    for (sender, recipient), total in owed.items():
        remaining = total - require_vnd(receipts.get((sender, recipient), 0))
        if remaining <= 0:
            continue
        positions[sender] -= remaining
        positions[recipient] += remaining
    return {person: amount for person, amount in sorted(positions.items()) if amount != 0}


def settlement_suggestions(balances: dict[str, int]) -> list[dict]:
    """Propose a smaller set of transfers that clears the same net positions.

    SUGGESTIONS ONLY. Spec section 8.8: routing A's payment to C instead of B
    is not a routing optimisation, it is a change to who owes whom. It may only
    be applied once every person whose counterparty changes has agreed, and it
    goes through the Offset lifecycle with its own audit record.

    Nothing in this module applies the result. The name says `suggestions` and
    the caller has to walk it through consent.
    """
    for amount in balances.values():
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise LedgerError("AMOUNT_NOT_INTEGER")
    if sum(balances.values()) != 0:
        raise LedgerError("BALANCES_DO_NOT_NET_TO_ZERO")

    debtors = sorted(((p, -a) for p, a in balances.items() if a < 0), key=lambda x: (-x[1], x[0]))
    creditors = sorted(((p, a) for p, a in balances.items() if a > 0), key=lambda x: (-x[1], x[0]))

    transfers = []
    debtor_index = creditor_index = 0
    while debtor_index < len(debtors) and creditor_index < len(creditors):
        debtor, owed = debtors[debtor_index]
        creditor, due = creditors[creditor_index]
        amount = min(owed, due)
        transfers.append({
            # Shaped as a draft, never as an obligation. An obligation-shaped
            # dict invites a caller to persist it, and section 8.8 requires
            # every affected party to accept an offset first.
            "kind": "offset_proposal_draft",
            "sender_id": debtor,
            "recipient_id": creditor,
            "amount_vnd": amount,
        })
        debtors[debtor_index] = (debtor, owed - amount)
        creditors[creditor_index] = (creditor, due - amount)
        if debtors[debtor_index][1] == 0:
            debtor_index += 1
        if creditors[creditor_index][1] == 0:
            creditor_index += 1
    return transfers
