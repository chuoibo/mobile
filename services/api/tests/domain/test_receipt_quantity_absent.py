"""A line with no quantity written on it means one, not "throw the bill away".

#213 taught this module to read "Trà đá X4". The Lead then re-measured the same
hero path on the rebuilt demo box and it still failed 4 times in 10 direct
calls. Instrumenting the reader seam over 8 live readings showed why:

    8x  quantity_text='X4'   -> read by the marker pattern (#213)
    8x  quantity_text='X2'   -> read by the marker pattern (#213)
    5x  quantity_text='1'    -> read by the plain pattern
    3x  quantity_text=''     -> read by NOTHING, so INVALID_QUANTITY

The empty string is the remaining 40%. Gemini has two ways of saying "this line
does not state a count" -- omit the key, or send it empty -- and this module
gave the two opposite outcomes: ``_read_quantity`` already returned 1 for an
absent key, and refused the whole document for an empty one. That divergence
was an accident of shape, not a policy about money.

Why one is the safe reading, and why this is NOT the guessing that #213
forbids: a quantity never multiplies into a line total here. ``read_receipt``
transcribes ``line_total_text`` independently, and the bill total is the sum of
those line totals, so no count this module chooses can move the money. A count
is used for exactly two things -- cross-checking a printed unit price, and
deriving a unit price when the bill printed none. Choosing 1 makes that
derivation ``line_total // 1``, the identity: it invents no number. Choosing 4
for "X4" genuinely divides a real total, which is why *that* one had to be read
exactly and why "vài" and "0" stay refused below.

The alternative the Lead offered -- carry quantity=None and have the screen ask
-- was declined for this reason: it changes the wire contract the app already
consumes, to re-ask a question whose answer on paper is almost always one, and
it does not make any number more correct than the identity already is.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.domain.receipt import ReceiptError, read_receipt  # noqa: E402

# Shaped after the bill the Lead sent 10 times: two marker lines that #213
# fixed, plus the empty-quantity line that still killed the whole document.
READING_WITH_AN_EMPTY_QUANTITY = {
    "document_type": "receipt",
    "items": [
        {
            "name": "Cơm tấm sườn bì chả",
            "quantity_text": "",
            "unit_price_text": None,
            "line_total_text": "65.000",
        },
        {
            "name": "Trà đá",
            "quantity_text": "X4",
            "unit_price_text": None,
            "line_total_text": "20.000",
        },
        {
            "name": "Cơm trắng",
            "quantity_text": "X2",
            "unit_price_text": None,
            "line_total_text": "10.000",
        },
    ],
    "total_text": "95.000",
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


def one_line(**item_overrides) -> dict:
    item = {"name": "Cơm tấm", "line_total_text": "65.000"}
    item.update(item_overrides)
    return raw(items=[item], total_text="65.000")


class TheReadingThatStillFailedAfter213(unittest.TestCase):
    """The 3-in-8 shape must stop taking the other lines down with it."""

    def test_the_whole_bill_is_no_longer_thrown_away(self):
        result = read_receipt(READING_WITH_AN_EMPTY_QUANTITY)
        self.assertEqual(len(result["items"]), 3)

    def test_an_unwritten_count_reads_as_one(self):
        result = read_receipt(READING_WITH_AN_EMPTY_QUANTITY)
        quantities = [item["quantity"] for item in result["items"]]
        self.assertEqual(quantities, [1, 4, 2])

    def test_the_money_is_the_money_the_paper_prints(self):
        result = read_receipt(READING_WITH_AN_EMPTY_QUANTITY)
        self.assertEqual(result["items_total_vnd"], 95000)
        self.assertEqual(result["total_vnd"], 95000)
        self.assertTrue(result["totals_agree"])

    def test_the_empty_line_keeps_its_own_total_untouched(self):
        """Reading the count as 1 must not compute anything from it."""
        result = read_receipt(READING_WITH_AN_EMPTY_QUANTITY)
        com_tam = result["items"][0]
        self.assertEqual(com_tam["line_total_vnd"], 65000)
        # line_total // 1 -- the identity, not an invented unit price.
        self.assertEqual(com_tam["unit_price_vnd"], 65000)


class ShapesThatAllMeanNoCountWasWritten(unittest.TestCase):
    """Absent, null and empty are one statement, so they get one answer."""

    def test_they_all_read_as_one(self):
        for label, item in [
            ("key absent", {}),
            ("empty string", {"quantity_text": ""}),
            ("blank string", {"quantity_text": "   "}),
            ("tab and newline", {"quantity_text": "\t\n"}),
            ("json null", {"quantity_text": None}),
        ]:
            with self.subTest(shape=label):
                result = read_receipt(one_line(**item))
                self.assertEqual(result["items"][0]["quantity"], 1)

    def test_they_all_agree_with_each_other(self):
        """The outcome must not depend on which shape the model happened to send."""
        readings = [
            read_receipt(one_line())["items"][0],
            read_receipt(one_line(quantity_text=""))["items"][0],
            read_receipt(one_line(quantity_text=None))["items"][0],
        ]
        self.assertEqual({item["quantity"] for item in readings}, {1})
        self.assertEqual({item["line_total_vnd"] for item in readings}, {65000})
        self.assertEqual({item["unit_price_vnd"] for item in readings}, {65000})


class ARefusalIsStillARefusal(unittest.TestCase):
    """Widening "not written" must not widen "written and unreadable"."""

    def test_a_count_that_is_present_but_wrong_stays_refused(self):
        for text in [
            "vài",
            "0",
            "x0",
            "0x",
            "x",
            "xx",
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
                    read_receipt(one_line(quantity_text=text))
                self.assertEqual(caught.exception.code, "INVALID_QUANTITY")

    def test_a_quantity_of_the_wrong_type_stays_refused(self):
        """None means "not written"; 4 and [] are a broken contract, not a blank."""
        for value in [4, 4.0, [], {}, True]:
            with self.subTest(quantity_text=value):
                with self.assertRaises(ReceiptError) as caught:
                    read_receipt(one_line(quantity_text=value))
                self.assertEqual(caught.exception.code, "INVALID_QUANTITY")


if __name__ == "__main__":
    unittest.main()
