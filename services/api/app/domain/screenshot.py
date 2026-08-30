"""Pure validation for one model-read transaction screenshot.

The model may classify the application and transcribe merchant, money-shaped
text, and a printed date. Identity is deliberately absent: a screenshot is
evidence about a transaction, never authority for who paid or who will share it.
"""

from __future__ import annotations

import re
from datetime import date

from .contract import MAX_AMOUNT_VND
from .receipt import ReceiptError, normalize_vnd

__all__ = ["ScreenshotError", "read_screenshot"]

_TRANSACTION_SOURCES = frozenset({"grab", "shopeefood", "banking", "receipt"})
_CONTRACT_KEYS = frozenset(
    {"source", "merchant", "total_text", "occurred_on"}
)
_IDENTITY_KEY_FRAGMENTS = (
    "paidby",
    "payer",
    "person",
    "people",
    "sharedby",
    "sharedwith",
    "participant",
    "attendee",
    "author",
    "advancer",
    "beneficiar",
    "member",
    "recipient",
    "splitwith",
    "splitbetween",
    "whopaid",
)
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


class ScreenshotError(Exception):
    """Report one stable refusal from the screenshot boundary."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _unreadable() -> ScreenshotError:
    return ScreenshotError("UNREADABLE")


def _looks_like_identity_key(key: object) -> bool:
    if not isinstance(key, str) or key in _CONTRACT_KEYS:
        return False
    compact = re.sub(r"[^a-z0-9]", "", key.casefold())
    return any(fragment in compact for fragment in _IDENTITY_KEY_FRAGMENTS)


def _read_occurred_on(raw: dict) -> str | None:
    occurred_on = raw.get("occurred_on")
    if occurred_on is None:
        return None
    if not isinstance(occurred_on, str) or _DATE_PATTERN.fullmatch(occurred_on) is None:
        raise _unreadable()
    try:
        date.fromisoformat(occurred_on)
    except ValueError:
        raise _unreadable() from None
    return occurred_on


def read_screenshot(raw: dict) -> dict:
    """Normalize one raw reading without accepting identity from the model."""

    if not isinstance(raw, dict):
        raise _unreadable()
    if any(_looks_like_identity_key(key) for key in raw):
        raise ScreenshotError("MODEL_NAMED_A_PERSON")
    if any(not isinstance(key, str) for key in raw):
        raise _unreadable()

    source = raw.get("source")
    if source == "other":
        raise ScreenshotError("NOT_A_TRANSACTION")
    if source not in _TRANSACTION_SOURCES:
        raise _unreadable()

    merchant = raw.get("merchant")
    if not isinstance(merchant, str):
        raise _unreadable()
    merchant = merchant.strip()
    if not merchant:
        raise _unreadable()

    total_text = raw.get("total_text")
    if not isinstance(total_text, str):
        # Never stringify model money. An integral-looking float has already
        # broken the integer-dong boundary before normalization can inspect it.
        raise _unreadable()
    try:
        total_vnd = normalize_vnd(total_text)
    except ReceiptError:
        raise _unreadable() from None
    if total_vnd <= 0 or total_vnd > MAX_AMOUNT_VND:
        raise _unreadable()

    return {
        "source": source,
        "merchant": merchant,
        "total_vnd": total_vnd,
        "occurred_on": _read_occurred_on(raw),
        # A model reading is evidence for a draft, never confirmation of money.
        "needs_review": True,
    }
