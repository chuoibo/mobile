"""Application boundary for pluggable ``money_skill`` extraction backends."""

from __future__ import annotations

from copy import deepcopy
from typing import Protocol

from app.domain.money_skill import (
    DEFAULT_MAX_MESSAGES,
    validate_context,
    validate_extraction,
)

__all__ = ["MoneyExtractor", "run_money_skill"]


class MoneyExtractor(Protocol):
    """Extract raw candidates without allocation, persistence, or side effects.

    Implementations must run inside the approved data boundary. Raw chat and
    participant identity may not be forwarded to an external service.
    """

    def extract(self, context: dict) -> dict:
        """Return raw ``expenses`` and ``questions`` for one frozen snapshot."""
        ...


def run_money_skill(
    context: dict,
    *,
    extractor: MoneyExtractor,
    max_messages: int = DEFAULT_MAX_MESSAGES,
) -> dict:
    """Run one extraction behind a replaceable backend, then fail closed.

    Context validation happens before the backend call so an over-limit or
    unauditable snapshot never reaches extraction. The validator runs after
    extraction and never delegates grounding back to that backend.
    """

    snapshot = deepcopy(context)
    validate_context(snapshot, max_messages=max_messages)
    extraction = extractor.extract(deepcopy(snapshot))
    return validate_extraction(snapshot, extraction)
