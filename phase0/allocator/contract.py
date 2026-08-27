"""Shared boundary for the two blind allocator implementations.

ADR-0004 blocker V2-03: without a neutral interoperable representation, impl_a
(pure integer) and impl_b (Fraction) would return different concrete types for
the same arithmetic, the differential harness would compare unequal, and whoever
wrote the harness would have to read both implementations to build adapters --
destroying the blindness the whole exercise depends on.

This module contains constants and an exception class ONLY. No logic, ever.
Sharing logic between the two implementations would defeat the differential.
"""

from __future__ import annotations

MAX_AMOUNT_VND = 10**12
MAX_ID_BYTES = 64

# ADR-0004 section 6, the single canonical precedence. Order is significant.
ERROR_PRECEDENCE = (
    # group 1: structural
    "NO_PARTICIPANTS",
    "INVALID_PARTICIPANT_ID",
    "DUPLICATE_PARTICIPANT",
    "INVALID_ENTITY_ID",
    "DUPLICATE_ENTITY_ID",
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
