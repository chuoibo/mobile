"""Rules for a bank destination, decided before anything touches a database.

The column widths and the two regex check constraints on `bank_recipients` are
the last line, not the first: a 20-character account number that reaches
PostgreSQL raises a driver error and the caller gets a 500 for what is plainly
a malformed request. So the shape is decided here, in a pure function, and the
constraints stay as the backstop they were meant to be.

Nothing here claims the account belongs to anybody. Spec section 8.5 forbids
that claim outright -- there is no verification source -- and the only real
check is the account holder name the sender's own bank app shows them.
"""

from __future__ import annotations

import pytest

from app.domain.bank_account import BankAccountError, normalise_destination


def _destination(**overrides) -> dict:
    payload = {
        # Synthetic throughout: a real BIN paired with an account number that
        # is not one. Nothing in this repo may carry a real account.
        "bank_bin": "970418",
        "account_number": "0000000000TEST",
        "account_name": "NGUYEN VAN NAM",
    }
    payload.update(overrides)
    return payload


def test_a_well_formed_destination_survives_unchanged():
    assert normalise_destination(_destination()) == {
        "bank_bin": "970418",
        "account_number": "0000000000TEST",
        "account_name": "NGUYEN VAN NAM",
    }


def test_the_spaces_a_banking_app_puts_in_an_account_number_are_removed():
    """Vietnamese banking apps display "0000 0000 00TE ST" and that is what
    gets copied. Refusing it as malformed teaches people to fight the form
    while the digits they pasted were right all along."""
    result = normalise_destination(_destination(account_number=" 0000 0000 00TEST "))

    assert result["account_number"] == "0000000000TEST"


def test_a_bank_code_that_is_not_six_digits_is_refused():
    for wrong in ("97041", "9704188", "97041a", "970 418", "", None):
        with pytest.raises(BankAccountError) as caught:
            normalise_destination(_destination(bank_bin=wrong))
        assert caught.value.code == "INVALID_BANK_BIN", wrong


def test_a_missing_bank_code_is_refused_rather_than_defaulted():
    with pytest.raises(BankAccountError) as caught:
        normalise_destination({"account_number": "0000000000TEST"})

    assert caught.value.code == "INVALID_BANK_BIN"


def test_an_account_number_wider_than_the_column_is_refused_here():
    """Nineteen is the width of `bank_recipients.account_number`. Twenty
    characters must come back as a 422 naming the field, not as whatever
    psycopg raises when the string will not fit."""
    with pytest.raises(BankAccountError) as caught:
        normalise_destination(_destination(account_number="1" * 20))

    assert caught.value.code == "INVALID_ACCOUNT_NUMBER"


def test_nineteen_characters_still_fits():
    result = normalise_destination(_destination(account_number="1" * 19))

    assert result["account_number"] == "1" * 19


def test_an_account_number_that_is_not_alphanumeric_is_refused():
    """The VietQR builder refuses these too, but it refuses them at publish
    time -- long after the batch froze around a destination nobody can pay."""
    for wrong in ("0123-4567", "0123.4567", "tài-khoản", "", None):
        with pytest.raises(BankAccountError) as caught:
            normalise_destination(_destination(account_number=wrong))
        assert caught.value.code == "INVALID_ACCOUNT_NUMBER", wrong


def test_an_absent_account_name_is_allowed():
    """The name is a hint, never a proof. Section 8.5 rules out the word
    "verified" entirely, and the sender's own bank app is the real check."""
    result = normalise_destination(
        {"bank_bin": "970418", "account_number": "0000000000TEST"}
    )

    assert result["account_name"] is None


def test_an_account_name_of_only_whitespace_is_refused_rather_than_dropped():
    """Silently turning "   " into None puts an envelope in front of a sender
    with no holder name on it, and the sender has nothing to compare against
    what their bank shows."""
    with pytest.raises(BankAccountError) as caught:
        normalise_destination(_destination(account_name="   "))

    assert caught.value.code == "INVALID_ACCOUNT_NAME"


def test_an_account_name_is_trimmed_and_its_inner_runs_of_space_collapsed():
    result = normalise_destination(_destination(account_name="  NGUYEN   VAN NAM "))

    assert result["account_name"] == "NGUYEN VAN NAM"


def test_an_account_name_wider_than_the_column_is_refused():
    assert normalise_destination(_destination(account_name="A" * 255))
    with pytest.raises(BankAccountError) as caught:
        normalise_destination(_destination(account_name="A" * 256))

    assert caught.value.code == "INVALID_ACCOUNT_NAME"


def test_diacritics_in_an_account_name_are_kept():
    """Not transliterated. Whatever the bank shows is what the sender compares
    against, and guessing at an unaccented form invents a name we cannot back."""
    result = normalise_destination(_destination(account_name="Nguyễn Văn Nam"))

    assert result["account_name"] == "Nguyễn Văn Nam"


def test_the_error_carries_a_code_not_a_sentence():
    """The code goes on the wire, so it has to be stable. A message can be
    rewritten for the reader; a code cannot without breaking a caller."""
    with pytest.raises(BankAccountError) as caught:
        normalise_destination(_destination(bank_bin="abc"))

    assert caught.value.code == "INVALID_BANK_BIN"
    assert str(caught.value) == "INVALID_BANK_BIN"
