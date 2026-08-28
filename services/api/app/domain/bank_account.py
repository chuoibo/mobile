"""Shape rules for a bank destination, decided before anything touches a DB.

The column widths and the two regex check constraints on `bank_recipients` are
the last line of defence, not the first. A 20-character account number that
reaches PostgreSQL raises a driver error, and the caller gets a 500 for what is
plainly a malformed request. So the shape is decided here, in a pure function,
and the constraints stay the backstop they were meant to be.

Nothing here claims the account belongs to anybody. Spec section 8.5 forbids
that claim outright -- there is no verification source we can reach -- and the
only real check is the account holder name the sender's own bank app shows them
before they press send.
"""

from __future__ import annotations

import re

__all__ = ["ACCOUNT_NAME_MAX", "BankAccountError", "normalise_destination"]

# Mirrors ck_bank_recipients_bank_bin_format.
_BANK_BIN = re.compile(r"^[0-9]{6}$")
# Mirrors ck_bank_recipients_account_number_format, whose upper bound is the
# String(19) column width.
_ACCOUNT_NUMBER = re.compile(r"^[A-Za-z0-9]{1,19}$")
_WHITESPACE = re.compile(r"\s+")

ACCOUNT_NAME_MAX = 255


class BankAccountError(Exception):
    """A malformed destination, carrying a wire-stable code.

    The code travels to the caller, so it has to stay stable. A message can be
    rewritten for whoever is reading it; a code cannot without breaking someone
    who branched on it.
    """

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def normalise_destination(payload: dict) -> dict:
    """Return the destination in the exact form storage will accept.

    Values are validated in declaration order, so a bad bank code is reported
    as a bad bank code even when the account number is bad too.
    """

    return {
        "bank_bin": _bank_bin(payload.get("bank_bin")),
        "account_number": _account_number(payload.get("account_number")),
        "account_name": _account_name(payload.get("account_name")),
    }


def _bank_bin(value: object) -> str:
    if not isinstance(value, str):
        raise BankAccountError("INVALID_BANK_BIN")
    candidate = value.strip()
    if not _BANK_BIN.match(candidate):
        raise BankAccountError("INVALID_BANK_BIN")
    return candidate


def _account_number(value: object) -> str:
    if not isinstance(value, str):
        raise BankAccountError("INVALID_ACCOUNT_NUMBER")
    # Vietnamese banking apps display "0000 0000 00TE ST" and that is what gets
    # copied. Refusing it as malformed teaches people to fight the form while
    # the digits they pasted were right all along.
    candidate = _WHITESPACE.sub("", value)
    if not _ACCOUNT_NUMBER.match(candidate):
        raise BankAccountError("INVALID_ACCOUNT_NUMBER")
    return candidate


def _account_name(value: object) -> str | None:
    # The name is a hint, never a proof, so its absence is allowed.
    if value is None:
        return None
    if not isinstance(value, str):
        raise BankAccountError("INVALID_ACCOUNT_NAME")
    # Diacritics are kept rather than transliterated: whatever the bank shows is
    # what the sender compares against, and guessing at an unaccented form
    # invents a name we cannot back.
    candidate = _WHITESPACE.sub(" ", value).strip()
    # Silently turning "   " into None would put an envelope in front of a
    # sender with no holder name on it, and nothing to compare against.
    if not candidate or len(candidate) > ACCOUNT_NAME_MAX:
        raise BankAccountError("INVALID_ACCOUNT_NAME")
    return candidate
