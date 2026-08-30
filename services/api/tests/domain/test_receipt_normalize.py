"""Money written on a Vietnamese receipt, turned into integer dong.

A vision model returns whatever the paper says. The paper says "219.000" in one
restaurant, "219,000" in the next, "219k" on a handwritten tab. All three are
the same 219000 dong, and the product is not allowed to guess differently on
different days.

Law 1 (integer dong) is enforced here rather than downstream: nothing that
cannot be read as an exact whole number of dong is permitted to become a
number at all. Ambiguous input fails closed, because inventing money silently
is worse than asking a human.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.domain.receipt import ReceiptError, normalize_vnd  # noqa: E402


class TheFourSpellingsTheTaskNames(unittest.TestCase):
    """The acceptance list, spelled out one test per form."""

    def test_dot_grouped(self):
        self.assertEqual(normalize_vnd("219.000"), 219000)

    def test_comma_grouped(self):
        self.assertEqual(normalize_vnd("219,000"), 219000)

    def test_k_suffix(self):
        self.assertEqual(normalize_vnd("219k"), 219000)

    def test_space_grouped(self):
        self.assertEqual(normalize_vnd("219 000"), 219000)

    def test_all_four_agree(self):
        readings = {
            normalize_vnd(spelling)
            for spelling in ("219.000", "219,000", "219k", "219 000")
        }
        self.assertEqual(readings, {219000})


class GroupedForms(unittest.TestCase):
    def test_two_groups(self):
        self.assertEqual(normalize_vnd("1.125.000"), 1125000)

    def test_two_groups_with_commas(self):
        self.assertEqual(normalize_vnd("1,125,000"), 1125000)

    def test_two_groups_with_spaces(self):
        self.assertEqual(normalize_vnd("1 125 000"), 1125000)

    def test_non_breaking_space_is_still_a_separator(self):
        """Copy-paste from a rendered page carries U+00A0, not a plain space."""
        self.assertEqual(normalize_vnd("1 125 000"), 1125000)

    def test_mixed_separators_are_ambiguous_and_rejected(self):
        with self.assertRaises(ReceiptError):
            normalize_vnd("1.125,000")

    def test_a_group_of_two_digits_is_not_a_thousands_group(self):
        """``219.00`` is a decimal somebody typed, not 21900 dong."""
        with self.assertRaises(ReceiptError):
            normalize_vnd("219.00")


class CurrencyMarkers(unittest.TestCase):
    def test_trailing_dong_sign(self):
        self.assertEqual(normalize_vnd("219.000đ"), 219000)

    def test_trailing_unicode_dong_sign(self):
        self.assertEqual(normalize_vnd("1.125.000 ₫"), 1125000)

    def test_trailing_vnd(self):
        self.assertEqual(normalize_vnd("219 000 VND"), 219000)

    def test_trailing_vnd_lowercase_with_diacritic(self):
        self.assertEqual(normalize_vnd("219.000 vnđ"), 219000)

    def test_leading_currency_marker(self):
        self.assertEqual(normalize_vnd("VND 219.000"), 219000)


class ThousandAndMillionSuffixes(unittest.TestCase):
    def test_uppercase_k(self):
        self.assertEqual(normalize_vnd("219K"), 219000)

    def test_k_with_a_space(self):
        self.assertEqual(normalize_vnd("219 k"), 219000)

    def test_nghin(self):
        self.assertEqual(normalize_vnd("219 nghìn"), 219000)

    def test_ngan(self):
        self.assertEqual(normalize_vnd("219 ngàn"), 219000)

    def test_trieu(self):
        self.assertEqual(normalize_vnd("2 triệu"), 2000000)

    def test_tr_abbreviation(self):
        self.assertEqual(normalize_vnd("2tr"), 2000000)

    def test_fractional_million_with_comma(self):
        """``1,5 triệu`` is how a Vietnamese speaker writes 1500000."""
        self.assertEqual(normalize_vnd("1,5 triệu"), 1500000)

    def test_fractional_million_with_dot(self):
        self.assertEqual(normalize_vnd("1.5tr"), 1500000)

    def test_fractional_thousand(self):
        self.assertEqual(normalize_vnd("28,5k"), 28500)

    def test_suffix_result_must_be_whole_dong(self):
        """0.0005 million is half a dong. There is no such coin."""
        with self.assertRaises(ReceiptError):
            normalize_vnd("1.0005k")

    def test_grouped_form_plus_suffix_is_ambiguous(self):
        """``219.000k`` means nothing. Refuse rather than pick a reading."""
        with self.assertRaises(ReceiptError):
            normalize_vnd("219.000k")


class PlainAndBoundaryForms(unittest.TestCase):
    def test_plain_digits(self):
        self.assertEqual(normalize_vnd("219000"), 219000)

    def test_zero(self):
        self.assertEqual(normalize_vnd("0"), 0)

    def test_small_bare_number_is_taken_literally(self):
        """``219`` is 219 dong.

        Multiplying it to 219000 because "no Vietnamese dish costs 219 dong"
        would be the product inventing money from a hunch. The number stays as
        printed; a human corrects it if the paper was misread.
        """
        self.assertEqual(normalize_vnd("219"), 219)

    def test_surrounding_whitespace_is_ignored(self):
        self.assertEqual(normalize_vnd("  219.000  "), 219000)


class RefusedInput(unittest.TestCase):
    def test_empty_string(self):
        with self.assertRaises(ReceiptError):
            normalize_vnd("")

    def test_whitespace_only(self):
        with self.assertRaises(ReceiptError):
            normalize_vnd("   ")

    def test_letters(self):
        with self.assertRaises(ReceiptError):
            normalize_vnd("không rõ")

    def test_negative(self):
        with self.assertRaises(ReceiptError):
            normalize_vnd("-219.000")

    def test_none(self):
        with self.assertRaises(ReceiptError):
            normalize_vnd(None)

    def test_float_input_is_refused_even_when_it_looks_round(self):
        """Law 1 has no exception for a float that happens to be integral."""
        with self.assertRaises(ReceiptError):
            normalize_vnd(219000.0)

    def test_int_input_is_refused(self):
        """This function reads what the model printed, which is always text."""
        with self.assertRaises(ReceiptError):
            normalize_vnd(219000)

    def test_absurdly_large_amount(self):
        with self.assertRaises(ReceiptError):
            normalize_vnd("9" * 40)

    def test_two_numbers_in_one_field(self):
        # Deliberately small amounts: two realistic VND figures side by side
        # form a 9+ digit run that the repo guard reads as an account number.
        with self.assertRaises(ReceiptError):
            normalize_vnd("1.000 2.000")

    def test_error_carries_a_stable_code(self):
        with self.assertRaises(ReceiptError) as caught:
            normalize_vnd("không rõ")
        self.assertEqual(caught.exception.code, "UNREADABLE_AMOUNT")


class TheUnitWrittenAsAWord(unittest.TestCase):
    """The unit is a word before it is a sign, and people type the word.

    The reader is instructed to preserve the money form exactly as written, so
    whatever a person typed in chat -- or a cashier printed on paper -- arrives
    here untouched. Accepting ``219.000đ`` while refusing ``219.000 đồng`` made
    the product blame the message for a reading it had got completely right
    (qa-tt-0034: 4 of 13 real spellings refused, three of them this one).
    """

    def test_plain_digits_followed_by_the_word(self):
        self.assertEqual(normalize_vnd("480000 đồng"), 480000)

    def test_grouped_digits_followed_by_the_word(self):
        self.assertEqual(normalize_vnd("480.000 đồng"), 480000)

    def test_word_without_diacritics(self):
        """A plain keyboard types "dong"; it is the same unit."""
        self.assertEqual(normalize_vnd("480000 dong"), 480000)

    def test_word_in_capitals(self):
        """Receipts print the unit in capitals under the total line."""
        self.assertEqual(normalize_vnd("480000 ĐỒNG"), 480000)

    def test_word_after_a_thousand_suffix(self):
        """One amount, not a thousand-suffix plus a leftover word."""
        self.assertEqual(normalize_vnd("480 nghìn đồng"), 480000)

    def test_the_word_alone_is_not_an_amount(self):
        with self.assertRaises(ReceiptError):
            normalize_vnd("đồng")

    def test_a_word_merely_containing_the_unit_is_still_refused(self):
        """A uniform is "đồng phục". Stripping a unit must not read a word."""
        with self.assertRaises(ReceiptError):
            normalize_vnd("đồng phục")


class HundredThousandWrittenAsACompound(unittest.TestCase):
    """The compound "trăm nghìn" names 200000 exactly; bare "trăm" does not."""

    def test_tram_nghin(self):
        self.assertEqual(normalize_vnd("2 trăm nghìn"), 200000)

    def test_tram_ngan(self):
        self.assertEqual(normalize_vnd("2 trăm ngàn"), 200000)

    def test_fractional_hundred_thousand_scales_by_a_hundred_thousand(self):
        """1,5 hundred-thousand is 150000.

        The regression this guards is arithmetic, not parsing: a fractional
        part scaled as if the multiplier were 1000 reads this as 100500 -- a
        wrong amount that still looks like money.
        """
        self.assertEqual(normalize_vnd("1,5 trăm nghìn"), 150000)

    def test_bare_tram_is_ambiguous_and_refused(self):
        """Bare "2 trăm" is 200 dong on paper and 200000 in speech."""
        with self.assertRaises(ReceiptError):
            normalize_vnd("2 trăm")

    def test_compound_with_the_unit_word(self):
        self.assertEqual(normalize_vnd("2 trăm nghìn đồng"), 200000)


class NoFloatEverAppears(unittest.TestCase):
    def test_every_accepted_form_returns_a_strict_int(self):
        """``type(...) is int`` on purpose: ``bool`` is an ``int`` subclass."""
        for spelling in (
            "219.000",
            "219,000",
            "219k",
            "219 000",
            "1,5 triệu",
            "28,5k",
            "0",
            "480000 đồng",
            "480 nghìn đồng",
            "2 trăm nghìn",
            "1,5 trăm nghìn",
        ):
            with self.subTest(spelling=spelling):
                self.assertIs(type(normalize_vnd(spelling)), int)


if __name__ == "__main__":
    unittest.main()
