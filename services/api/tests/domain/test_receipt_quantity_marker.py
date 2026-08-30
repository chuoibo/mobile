"""Quantities printed with a multiplication marker: "X4" means four.

rd-qa-37 measured the hero path answering 422 for 5 of 11 uploads of one
unchanged file (sha256 43bcfa4a056f, 52.806 bytes). The cause is in this
module, not in the model. Instrumenting the seam over 12 real calls showed the
reader transcribing the same paper two ways, both faithful:

    7/12   {"name": "Trà đá", "quantity_text": "X4", "line_total_text": "20.000"}
    5/12   {"name": "Trà đá X4",                     "line_total_text": "20.000"}

Every call read document_type=receipt, 5 items and total 235.000. The money was
never in doubt. What differed was only whether the quantity arrived in its own
field -- and ``_read_quantity`` accepted bare digits only, so the *better* of
the two readings, the one that separates the count from the dish name, was the
one refused. The refusal surfaced as the generic ``receipt_unreadable``, which
tells the person their photograph was bad and to shoot it again. Re-shooting
cannot help: the paper says "Trà đá X4".

The bill prints the marker, so this module has to read it. What it must not do
is guess: "vài" and "0" stay refused below, because a quantity that cannot be
read exactly would change the unit price shown next to a real dish.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.domain.receipt import ReceiptError, read_receipt  # noqa: E402

# Verbatim from a failing call, /tmp/rd-be-21-diag/records.json attempt 1.
# Kept whole rather than trimmed to one line: the assertion that matters is
# that this exact document, which the product refused, adds up to 235.000.
LIVE_REFUSED_READING = {
    "document_type": "receipt",
    "items": [
        {
            "name": "Cơm tấm sườn bì chả",
            "unit_price_text": None,
            "line_total_text": "65.000",
        },
        {
            "name": "Cơm tấm sườn nướng",
            "unit_price_text": None,
            "line_total_text": "55.000",
        },
        {
            "name": "Canh chua cá lóc",
            "unit_price_text": None,
            "line_total_text": "45.000",
        },
        {
            "name": "Trà đá",
            "quantity_text": "X4",
            "unit_price_text": None,
            "line_total_text": "20.000",
        },
        {
            "name": "Bia Sài Gòn",
            "quantity_text": "X2",
            "unit_price_text": None,
            "line_total_text": "50.000",
        },
    ],
    "total_text": "235.000",
    "confidence": 0.95,
}


def raw(**overrides) -> dict:
    reading = {
        "items": [
            {"name": "Trà đá", "quantity_text": "X4", "line_total_text": "20.000"},
        ],
        "total_text": "20.000",
        "confidence": 0.95,
    }
    reading.update(overrides)
    return reading


def one(quantity_text: str) -> dict:
    return raw(
        items=[
            {
                "name": "Trà đá",
                "quantity_text": quantity_text,
                "line_total_text": "20.000",
            }
        ]
    )


class TheReadingThatWasRefusedLive(unittest.TestCase):
    """The exact payload behind 5 of 11 failures must now be readable."""

    def test_it_is_read_at_all(self):
        result = read_receipt(LIVE_REFUSED_READING)
        self.assertEqual(len(result["items"]), 5)

    def test_the_money_is_the_money_the_paper_prints(self):
        result = read_receipt(LIVE_REFUSED_READING)
        self.assertEqual(result["items_total_vnd"], 235000)
        self.assertEqual(result["total_vnd"], 235000)
        self.assertTrue(result["totals_agree"])

    def test_the_marker_is_read_as_a_count(self):
        result = read_receipt(LIVE_REFUSED_READING)
        quantities = [item["quantity"] for item in result["items"]]
        self.assertEqual(quantities, [1, 1, 1, 4, 2])

    def test_the_line_total_is_never_multiplied_by_the_count(self):
        """A line total is transcribed, not computed. 20.000 stays 20.000."""
        result = read_receipt(LIVE_REFUSED_READING)
        tra_da = result["items"][3]
        self.assertEqual(tra_da["line_total_vnd"], 20000)
        self.assertEqual(tra_da["unit_price_vnd"], 5000)


class MarkersThisModuleReads(unittest.TestCase):
    def test_forms_that_mean_a_number(self):
        for text, expected in [
            ("4", 4),
            ("X4", 4),
            ("x4", 4),
            ("4x", 4),
            ("4X", 4),
            ("x 4", 4),
            ("4 x", 4),
            (" x4 ", 4),
            # The multiplication sign, which is what a printer sets when the
            # menu was typeset rather than typed.
            ("×4", 4),
            ("4×", 4),
        ]:
            with self.subTest(quantity_text=text):
                result = read_receipt(one(text))
                self.assertEqual(result["items"][0]["quantity"], expected)


class MarkersThisModuleRefuses(unittest.TestCase):
    """Reading a marker must not become guessing at a quantity."""

    def test_forms_with_no_exact_count_stay_refused(self):
        for text in [
            "vài",
            "0",
            "x0",
            "0x",
            "x",
            "xx",
            # "" and "   " used to sit here. rd-qa-38 measured what that cost on
            # the hero path -- a blank is how the model says "this line prints
            # no quantity", and refusing it threw away the whole bill. They now
            # read as 1; see test_the_blank_forms_moved_to_reading_as_one below
            # and tests/domain/test_receipt_quantity_absent.py.
            "-1",
            "x-1",
            "2.5",
            "x2.5",
            "một",
            "4 phần",
            "x4x",
            "4x4",
        ]:
            with self.subTest(quantity_text=text):
                with self.assertRaises(ReceiptError) as caught:
                    read_receipt(one(text))
                self.assertEqual(caught.exception.code, "INVALID_QUANTITY")

    def test_the_blank_forms_moved_to_reading_as_one(self):
        """Kept here so the move out of the list above is deliberate, not lost.

        Refusing a blank is a one-character change away, and this file is where
        someone would make it. Reading 1 invents no number: the line total is
        transcribed on its own, so `line_total // 1` is the identity.
        """

        for text in ["", "   "]:
            with self.subTest(quantity_text=text):
                self.assertEqual(read_receipt(one(text))["items"][0]["quantity"], 1)
