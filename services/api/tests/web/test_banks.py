"""BIN to bank name.

The guest page rendered "Ngân hàng 970407" until the whole slice was run
against a real database. Every existing test asserted the account number; none
asserted that the bank could be named, so nothing failed.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.web.banks import BANKS, bank_display_name  # noqa: E402


def test_a_known_bin_becomes_a_name_a_person_can_act_on():
    assert bank_display_name("970407") == "Techcombank"
    assert bank_display_name("970436") == "Vietcombank"


def test_an_unknown_bin_keeps_the_number_and_says_it_is_a_code():
    """Inventing a name is worse than showing the code: it sends somebody
    confidently into the wrong app, and only the transfer failing tells them."""
    result = bank_display_name("123456")
    assert "123456" in result
    assert result.startswith("Mã ngân hàng")


def test_every_bin_is_six_digits():
    for bin_code in BANKS:
        assert len(bin_code) == 6 and bin_code.isdigit(), bin_code


def test_no_duplicate_bank_names():
    """Two BINs mapping to the same name means one of them is wrong."""
    names = list(BANKS.values())
    assert len(names) == len(set(names))
