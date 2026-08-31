"""Frozen vocabulary of the allocator contract (ADR-0004).

Promoted from phase0/allocator/ to product code by ADR-0006. The blind
two-implementation exercise was dropped there; what carries over is the frozen
contract, the 41 hand-computed golden vectors and the property tests.

Constants and an exception class only. No logic.
"""

from __future__ import annotations

MAX_AMOUNT_VND = 10**12
MAX_ID_BYTES = 64

# ADR-0004 section 6, the single canonical precedence. Order is significant.
#
# `AMOUNT_NOT_INTEGER` was added by ADR-0012. It sits immediately before the
# three amount codes because sign and ceiling are questions you can only ask
# about a value that is already an integer number of dong: `True < 0` and
# `0.5 > MAX_AMOUNT_VND` both answer False, which is how a bool used to reach
# the arithmetic as one dong. No golden vector changes -- the 41 frozen vectors
# carry integer amounts, so none of them can reach this code.
ERROR_PRECEDENCE = (
    # group 1: structural
    "NO_PARTICIPANTS",
    "INVALID_PARTICIPANT_ID",
    "DUPLICATE_PARTICIPANT",
    "INVALID_ENTITY_ID",
    "DUPLICATE_ENTITY_ID",
    "AMOUNT_NOT_INTEGER",
    "NEGATIVE_AMOUNT",
    "ZERO_AMOUNT",
    "AMOUNT_TOO_LARGE",
    "INVALID_KIND",
    "INVALID_MODE",
    "INVALID_SCOPE",
    "SCOPE_TARGET_MISMATCH",
    "EMPTY_SHARED_BY",
    "DUPLICATE_SHARED_BY",
    # group 2: referential
    "UNKNOWN_PARTICIPANT",
    "UNKNOWN_ITEM",
    # group 3: arithmetic
    "DISCOUNT_EXCEEDS_ITEM",
    "DISCOUNT_EXCEEDS_BASE",
    # group 4: reconciliation, always last
    "RECONCILIATION_MISMATCH",
)

WARNINGS = (
    "advancer_not_participant",
    "proportional_fallback_to_even",
    "zero_share_participants",
)

SURCHARGE_MODES = ("proportional", "even")
DISCOUNT_SCOPES = ("global_proportional", "item")


class AllocationError(Exception):
    """Raised by allocate() with a code from ERROR_PRECEDENCE.

    Differential comparison uses `code` only. Messages are never compared, so
    the two implementations are free to word them differently.
    """

    def __init__(self, code: str):
        if code not in ERROR_PRECEDENCE:
            raise ValueError(f"unknown allocation error code: {code!r}")
        super().__init__(code)
        self.code = code
