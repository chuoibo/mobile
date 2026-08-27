"""Who can see what, and the rule that stops context from leaking.

Spec section 10. One sentence carries most of the weight:

    Output is never broader than its most sensitive input, unless the output
    has been redacted AND the owner consented.

Everything else here is that rule applied to specific surfaces, plus the three
conditions history access has to satisfy at once.

Pure functions over plain dicts. No I/O, no ORM, no framework.
"""

from __future__ import annotations

__all__ = [
    "LEVELS",
    "DEFAULT_VISIBILITY",
    "VisibilityError",
    "rank",
    "permitted_output_visibility",
    "check_no_context_laundering",
    "declassify",
    "can_view_history",
    "SETTLEMENT_VIEW_FIELDS",
    "settlement_view",
]

# Ordered from narrowest to widest. The middle one is the default.
LEVELS = ("private_to_invoker", "group_summary_private_details", "group_visible")

DEFAULT_VISIBILITY = {
    "invocation_event": "group_summary_private_details",
    "user_typed_text": "private_to_invoker",
    # Bills routinely contain a bank account number and a phone number, so
    # widening one is an explicit action that must carry a warning.
    "attachment": "private_to_invoker",
    "bot_clarification_question": "group_summary_private_details",
    "bot_clarification_answer": "private_to_invoker",
    "output_summary": "group_summary_private_details",
    "output_per_person_allocation": "private_to_invoker",
    "bank_account_number": "private_to_invoker",
}

# Not a default that may be widened -- a ceiling. An account number reaches
# exactly one person: the one who has to transfer to it.
NEVER_GROUP_VISIBLE = frozenset({"bank_account_number"})


class VisibilityError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def rank(level: str) -> int:
    if level not in LEVELS:
        raise VisibilityError("UNKNOWN_LEVEL")
    return LEVELS.index(level)


def permitted_output_visibility(input_levels: list[str]) -> str:
    """The widest an output may be, given what went into it."""
    if not input_levels:
        raise VisibilityError("NO_INPUTS")
    return min(input_levels, key=rank)


def check_no_context_laundering(
    component: str,
    requested_level: str,
    input_levels: list[str],
    *,
    redacted: bool = False,
    owner_consented: bool = False,
) -> None:
    """Raise unless the requested level is honestly reachable.

    Redaction alone is not enough and consent alone is not enough. Redaction
    without consent takes a decision that belongs to the owner of the data;
    consent without redaction just moves the sensitive bytes somewhere wider.
    """
    if component in NEVER_GROUP_VISIBLE and requested_level == "group_visible":
        raise VisibilityError("NEVER_GROUP_VISIBLE")

    ceiling = permitted_output_visibility(input_levels)
    if rank(requested_level) <= rank(ceiling):
        return
    if redacted and owner_consented:
        return
    raise VisibilityError("CONTEXT_LAUNDERING")


# A closed vocabulary of what redaction can mean. An arbitrary dict was a
# label rather than a projection: it let a caller widen a field while claiming
# it had been redacted, without anything being removed.
REDACTABLE = frozenset({
    "mask_bank_account",
    "mask_phone",
    "mask_full_name",
    "drop_other_allocations",
    "drop_attachment",
})


def declassify(field: dict, to_level: str, *, actor_id: str, redaction: dict) -> dict:
    """Produce a redacted derivative. Never touches the original's ACL.

    Spec section 10.3. Widening the original in place would retroactively
    expose every earlier reader boundary; a derivative leaves the original
    exactly as it was and makes the wider copy a separate, auditable object.
    """
    if field.get("owner_id") != actor_id:
        raise VisibilityError("NOT_FIELD_OWNER")
    if not redaction:
        raise VisibilityError("REDACTION_REQUIRED")
    applied = redaction.get("applied")
    if not applied or not set(applied) <= REDACTABLE:
        raise VisibilityError("UNKNOWN_REDACTION")
    check_no_context_laundering(
        field["component"], to_level, [field["visibility"]],
        redacted=True, owner_consented=True,
    )
    return {
        "derived_from_id": field["id"],
        "component": field["component"],
        "visibility": to_level,
        "redaction": redaction,
        "declassified_by": actor_id,
        # The source keeps its own visibility. Stated in the returned object so
        # a caller cannot claim it did not know.
        "source_visibility_unchanged": field["visibility"],
    }


def can_view_history(
    *,
    object_visibility: str,
    viewer_joined_at,
    viewer_left_at,
    object_created_at,
    audience_snapshot: set[str] | frozenset[str],
    viewer_id: str,
) -> bool:
    """All three conditions at once, per spec section 10.4.

    Membership at the time is not sufficient on its own: a private invocation
    does not become visible merely because the viewer happened to be a member
    when it happened.
    """
    # Fail closed on anything unproven. The earlier version let a viewer with
    # no known join date through as long as they appeared in the snapshot the
    # caller supplied, and let an unrecognised visibility string through as if
    # it were permissive. Both readings turn a missing fact into a permission.
    if object_visibility not in LEVELS:
        return False
    if viewer_joined_at is None:
        return False
    if object_created_at < viewer_joined_at:
        return False  # new members see nothing from before they joined
    if viewer_left_at is not None and object_created_at > viewer_left_at:
        return False  # departed members see nothing created after they left
    if object_visibility == "private_to_invoker":
        return False
    return viewer_id in audience_snapshot


# Spec section 10.4. Deliberately short: this is what a former member or an
# out-of-window participant keeps, and nothing else.
SETTLEMENT_VIEW_FIELDS = (
    "own_amount_vnd",
    "recipient_and_transfer_instructions",
    "calculation_basis_summary",
    "versions_that_changed_own_obligation",
    "own_dispute_and_receipt_events",
)


def settlement_view(obligation: dict) -> dict:
    """Project an obligation down to the minimal settlement view.

    Whitelist, not blacklist. A blacklist grows a hole the first time someone
    adds a field and forgets to exclude it -- and the field they forget will be
    somebody else's allocation.
    """
    missing = [field for field in SETTLEMENT_VIEW_FIELDS if field not in obligation]
    if missing:
        raise VisibilityError("INCOMPLETE_SETTLEMENT_VIEW")
    return {field: obligation[field] for field in SETTLEMENT_VIEW_FIELDS}
