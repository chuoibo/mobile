"""Pure validation for one model-read expense mention in group chat.

The model may transcribe intent, a title, and money-shaped text. Identity is
deliberately absent: the API owns authorship and the active roster, so letting
an untrusted model add a person-shaped field would create a second authority
for who paid or who gets charged.
"""

from __future__ import annotations

import re

from .contract import MAX_AMOUNT_VND
from .receipt import ReceiptError, normalize_vnd

__all__ = [
    "MAX_CHAT_EXPENSE_TITLE_LENGTH",
    "ChatExpenseError",
    "read_chat_expense",
]

MAX_CHAT_EXPENSE_TITLE_LENGTH = 200

_CONTRACT_KEYS = frozenset({"is_expense", "title", "amount_text"})
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


class ChatExpenseError(Exception):
    """Report one stable refusal from the chat-expense boundary."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _looks_like_identity_key(key: object) -> bool:
    if not isinstance(key, str) or key in _CONTRACT_KEYS:
        return False
    compact = re.sub(r"[^a-z0-9]", "", key.casefold())
    return any(fragment in compact for fragment in _IDENTITY_KEY_FRAGMENTS)


def _unreadable() -> ChatExpenseError:
    return ChatExpenseError("UNREADABLE")


def read_chat_expense(raw: dict) -> dict:
    """Normalize one raw reading without accepting identity from the model."""

    if not isinstance(raw, dict):
        raise _unreadable()
    if any(_looks_like_identity_key(key) for key in raw):
        raise ChatExpenseError("MODEL_NAMED_A_PERSON")
    if any(not isinstance(key, str) for key in raw):
        raise _unreadable()

    is_expense = raw.get("is_expense")
    if type(is_expense) is not bool:
        raise _unreadable()
    if not is_expense:
        return {
            "is_expense": False,
            "title": None,
            "amount_vnd": None,
            "needs_review": False,
        }

    title = raw.get("title")
    if not isinstance(title, str):
        raise _unreadable()
    title = title.strip()
    if not title or len(title) > MAX_CHAT_EXPENSE_TITLE_LENGTH:
        raise _unreadable()

    amount_text = raw.get("amount_text")
    if not isinstance(amount_text, str):
        # Do not stringify a number here. In particular, 180000.0 is a float
        # that has already crossed the money boundary, even if it is integral.
        raise _unreadable()
    try:
        amount_vnd = normalize_vnd(amount_text)
    except ReceiptError:
        raise _unreadable() from None
    if amount_vnd <= 0 or amount_vnd > MAX_AMOUNT_VND:
        raise _unreadable()

    return {
        "is_expense": True,
        "title": title,
        "amount_vnd": amount_vnd,
        # Every model-derived amount is a draft. There is no confidence
        # threshold that may turn this into an automatic financial action.
        "needs_review": True,
    }
