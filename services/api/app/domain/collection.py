"""Collection batch: the state machine around getting money back.

Product spec section 8. The batch, not the expense, is the unit that goes out
to people -- because issuing a payment link for every 35k bunch of vegetables
turns the app into a spam machine (section 8.1).

Pure functions over plain dicts. No I/O, no ORM, no framework.
"""

from __future__ import annotations

from datetime import datetime, timedelta

__all__ = [
    "CollectionError",
    "STATES",
    "unmet_freeze_requirements",
    "unmet_publish_gates",
    "transition",
    "terminal_state_for",
    "progress",
    "is_stale",
    "counts_toward_collection_rate",
]

# Section 8.4 offers exactly two answers, so an arbitrary truthy string is not
# one of them. Accepting "anything" let a batch freeze on a choice nobody made.
UNREADY_CHOICES = ("wait_for_all_recipients", "split_blocked_recipient_setup")

STATES = (
    "accruing",
    "frozen",
    "published",
    "collecting",
    "completed",
    "closed_with_exceptions",
    "cancelled",
)

_ALLOWED = {
    "accruing": {"freeze": "frozen", "cancel": "cancelled"},
    "frozen": {"publish": "published", "reopen": "accruing", "cancel": "cancelled"},
    # `expose_capability` is the moment a link could have left the app, so it
    # is what starts collecting -- not a "delivered" state, which the product
    # deliberately does not have (section 8.5).
    "published": {"expose_capability": "collecting", "cancel": "cancelled"},
    "collecting": {"close": None, "cancel": "cancelled"},
    "completed": {},
    "closed_with_exceptions": {},
    "cancelled": {},
}


class CollectionError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def unmet_freeze_requirements(context: dict) -> list[str]:
    """Section 8.4: an unready recipient must be handled explicitly.

    The organiser has to choose out loud -- wait for everyone, or move the
    unready obligations into a separate `blocked_recipient_setup` batch.
    Blocked obligations must never be quietly slipped into an envelope that has
    already gone out.
    """
    unmet = []
    if context.get("has_unready_recipient"):
        if context.get("unready_recipient_choice") not in UNREADY_CHOICES:
            unmet.append("unready_recipient_choice_required")
    if not context.get("obligations"):
        unmet.append("no_obligations")
    return unmet


def unmet_publish_gates(context: dict) -> list[str]:
    """The three gates of section 8.3.

    Gate 1 (the caller confirmed the expense) happens upstream, before the
    expense reaches a batch, and does NOT substitute for gate 2. If it did, a
    malicious member could raise collections in someone else's name.
    """
    unmet = []
    if not context.get("advancer_acknowledged"):
        unmet.append("advancer_acknowledgement_required")
    if not context.get("bank_recipient_snapshot_valid"):
        unmet.append("valid_bank_recipient_snapshot_required")
    if not context.get("delivery_method_chosen"):
        unmet.append("delivery_method_required")
    return unmet


def transition(state: str, event: str, context: dict | None = None) -> str:
    """Advance the batch. Raises rather than silently staying put."""
    context = context or {}
    if state not in _ALLOWED:
        raise CollectionError("UNKNOWN_STATE")
    allowed = _ALLOWED[state]
    if event not in allowed:
        raise CollectionError("ILLEGAL_TRANSITION")

    if event == "freeze":
        unmet = unmet_freeze_requirements(context)
        if unmet:
            raise CollectionError(unmet[0].upper())
    if event == "publish":
        unmet = unmet_publish_gates(context)
        if unmet:
            raise CollectionError(unmet[0].upper())

    if event == "cancel" and context.get("capability_exposed_at") is not None:
        # Section 9.1: once an envelope could have left the app, the batch
        # owner cannot unilaterally erase the obligations inside it. People
        # have already been asked for money; withdrawing that quietly rewrites
        # a social expectation without anyone agreeing.
        if not context.get("all_affected_parties_consented"):
            raise CollectionError("CANCEL_AFTER_EXPOSURE_NEEDS_CONSENT")

    if event == "close":
        # Invariant 7 of the spec: `completed` is produced by a domain
        # transition, never by a "mark as done" button. Which terminal state
        # this is depends on the obligations, not on what anyone clicks.
        return terminal_state_for(context.get("obligations", []))

    return allowed[event]


def terminal_state_for(obligations: list[dict]) -> str:
    """`completed` only when every effective obligation actually ended cleanly.

    Section 8.1: a batch carrying waivers, disputes or cancelled obligations
    closes as `closed_with_exceptions`. Collapsing the two would let a batch
    where somebody was written off look identical to one where everybody paid.
    """
    if not obligations:
        raise CollectionError("NO_OBLIGATIONS")

    has_exception = False
    for obligation in obligations:
        status = obligation["status"]
        if status in {"waived", "disputed", "cancelled"}:
            has_exception = True
        elif status not in {"confirmed", "over_confirmed"}:
            raise CollectionError("OBLIGATIONS_STILL_OPEN")
    return "closed_with_exceptions" if has_exception else "completed"


def progress(obligations: list[dict]) -> dict:
    """Section 8.7: count transfers first, people second.

    Counting only people is wrong the moment one person has to pay two
    different recipients. The advancer is not in the denominator unless they
    themselves have somewhere to send money -- and since obligations are the
    denominator, that falls out for free.
    """
    # The two denominators are not the same question, so they do not share a
    # definition of "done". A waived obligation is not a completed transfer --
    # no money moved -- but the person who was forgiven has nothing left to do.
    transferred = {"confirmed", "over_confirmed"}
    nothing_left_to_do = transferred | {"waived", "cancelled"}

    transfers_total = len(obligations)
    transfers_done = sum(1 for o in obligations if o["status"] in transferred)

    by_person: dict[str, list[str]] = {}
    for obligation in obligations:
        by_person.setdefault(obligation["sender_id"], []).append(obligation["status"])
    people_total = len(by_person)
    people_done = sum(
        1 for statuses in by_person.values()
        if all(s in nothing_left_to_do for s in statuses)
    )
    return {
        "transfers_done": transfers_done,
        "transfers_total": transfers_total,
        "people_done": people_done,
        "people_total": people_total,
    }


def is_stale(now: datetime, due_at: datetime, last_meaningful_activity_at: datetime) -> bool:
    """Section 8.9: past due by 14 days AND quiet for 7. Both, not either.

    `stale` is a UI label derived from time. It is not `archived` (hidden but
    the ledger unchanged) and not `abandoned` (an audited business outcome).
    Any real action clears it, so this is a pure function of timestamps.
    """
    return (now - due_at) > timedelta(days=14) and (now - last_meaningful_activity_at) > timedelta(days=7)


def counts_toward_collection_rate(batch: dict) -> bool:
    """Anti-cosmetics rule of section 8.9.

    A batch abandoned AFTER publication stays in the denominator of the
    collection-rate metric. Only a batch cancelled BEFORE any capability was
    exposed may be dropped -- because before that moment nobody was ever asked
    for money, so there was nothing to fail at.
    """
    if batch.get("capability_exposed_at") is not None:
        return True
    return batch.get("state") != "cancelled"
