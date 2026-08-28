"""The gate that stops a restaurant MENU from being read as a bill.

rd-qa-03 photographed a printed menu and posted it to ``/receipts/scan``. The
answer was HTTP 200, eight items, ``items_total_vnd`` 340.000, ``confidence``
95-100, ``warnings`` empty. Nobody ordered those eight dishes and nobody paid
340.000 dong. In a restaurant the menu lies on the table next to the bill, so
this is the easiest wrong photograph a real person can take.

The confidence gate cannot catch it. QA measured why: confidence tracks how
LEGIBLE the text is, not how TRUE the numbers are. A menu is printed larger and
cleaner than any receipt, so the model is genuinely, correctly confident -- about
something that is not a transaction. Confidence even drifted between calls on the
same image at temperature 0 (1.00/1.00/0.95/0.95/0.95), so no threshold placed
anywhere would have refused it.

The root cause was in the question, not the answer: the prompt opened with "Read
this receipt", which asserts the premise the model was supposed to test. So the
reader now classifies the document first and the domain refuses everything that
is not an explicit ``receipt``.

Fail-closed on purpose: only the exact string ``receipt`` gets through. A reading
with no ``document_type``, or with one this module does not recognise, is refused
too -- a backend that did not answer the question has not established anything.

Ordering matters and is asserted below. Legibility is checked BEFORE the document
type, because under the floor the classification is exactly as untrustworthy as
the amounts, and "photograph it again" is the truer instruction than "that is not
a receipt".
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.domain.receipt import (  # noqa: E402
    CONFIDENCE_FLOOR,
    DOCUMENT_TYPE_RECEIPT,
    ReceiptError,
    read_receipt,
    read_scanned_document,
)


def raw(**overrides) -> dict:
    """One well-formed reading of an actual receipt; overrides break it."""
    reading = {
        "document_type": DOCUMENT_TYPE_RECEIPT,
        "items": [
            {"name": "Sườn nướng Mỹ", "quantity_text": "1", "line_total_text": "219.000"},
            {"name": "Ba chỉ heo", "quantity_text": "1", "line_total_text": "149.000"},
        ],
        "total_text": "368.000",
        "confidence": 0.98,
    }
    reading.update(overrides)
    return reading


# The menu reading rd-qa-03 actually got back, shortened to four of the eight
# lines. Everything that made it look trustworthy is preserved: high confidence,
# clean transcription, and no printed total for anything to disagree with.
MENU_READING = {
    "document_type": "price_list",
    "items": [
        {"name": "Phở bò tái", "line_total_text": "65.000"},
        {"name": "Bún chả Hà Nội", "line_total_text": "70.000"},
        {"name": "Cơm tấm sườn", "line_total_text": "60.000"},
        {"name": "Gỏi cuốn", "line_total_text": "45.000"},
    ],
    "total_text": None,
    "confidence": 0.95,
}


class AMenuIsRefused(unittest.TestCase):
    """The rd-qa-03 reproduction, at the layer that decides."""

    def test_the_menu_reading_raises(self):
        with self.assertRaises(ReceiptError) as caught:
            read_scanned_document(MENU_READING)
        self.assertEqual(caught.exception.code, "NOT_A_RECEIPT_PRICE_LIST")

    def test_high_confidence_does_not_rescue_it(self):
        """95-100 is what the live run returned; a threshold never sees this."""
        for percent in (95, 98, 100):
            with self.subTest(confidence=percent):
                with self.assertRaises(ReceiptError):
                    read_scanned_document(
                        dict(MENU_READING, confidence=percent / 100)
                    )

    def test_a_price_list_that_does_print_a_total_is_still_refused(self):
        """A set-menu board can print a total. It is still nobody's bill."""
        with self.assertRaises(ReceiptError) as caught:
            read_scanned_document(
                dict(MENU_READING, total_text="240.000", confidence=0.98)
            )
        self.assertEqual(caught.exception.code, "NOT_A_RECEIPT_PRICE_LIST")

    def test_no_amounts_survive_the_refusal(self):
        """Refusing means refusing. No list to rubber-stamp, no total to anchor on."""
        with self.assertRaises(ReceiptError):
            read_scanned_document(MENU_READING)


class AnythingNotDeclaredAReceiptIsRefused(unittest.TestCase):
    """Fail closed: the only way through is an explicit ``receipt``."""

    def test_other_is_refused(self):
        with self.assertRaises(ReceiptError) as caught:
            read_scanned_document(raw(document_type="other"))
        self.assertEqual(caught.exception.code, "NOT_A_RECEIPT")

    def test_a_missing_document_type_is_refused(self):
        """A backend that did not answer the question established nothing."""
        reading = raw()
        del reading["document_type"]
        with self.assertRaises(ReceiptError) as caught:
            read_scanned_document(reading)
        self.assertEqual(caught.exception.code, "NOT_A_RECEIPT")

    def test_an_unrecognised_document_type_is_refused(self):
        """A future model inventing its own label must not open the gate."""
        with self.assertRaises(ReceiptError) as caught:
            read_scanned_document(raw(document_type="invoice_maybe"))
        self.assertEqual(caught.exception.code, "NOT_A_RECEIPT")

    def test_a_non_string_document_type_is_refused(self):
        for value in (None, 1, True, ["receipt"], {"type": "receipt"}):
            with self.subTest(document_type=value):
                with self.assertRaises(ReceiptError) as caught:
                    read_scanned_document(raw(document_type=value))
                self.assertEqual(caught.exception.code, "NOT_A_RECEIPT")

    def test_the_match_is_exact_not_fuzzy(self):
        """"receipts", " receipt", "Receipt" are not the contract."""
        for value in ("receipts", " receipt", "Receipt", "receipt-ish"):
            with self.subTest(document_type=value):
                with self.assertRaises(ReceiptError):
                    read_scanned_document(raw(document_type=value))

    def test_a_non_dict_reading_is_refused(self):
        for value in (None, [], "receipt", 7):
            with self.subTest(reading=value):
                with self.assertRaises(ReceiptError):
                    read_scanned_document(value)


class ARealReceiptStillGetsThrough(unittest.TestCase):
    """The gate refuses; it does not become a second normalizer."""

    def test_a_declared_receipt_is_read(self):
        result = read_scanned_document(raw())
        self.assertEqual(result["items_total_vnd"], 368_000)
        self.assertEqual(result["total_vnd"], 368_000)

    def test_the_result_is_exactly_what_the_normalizer_returns(self):
        """Law 2 lives in ``read_receipt``; the gate may not touch its output."""
        reading = raw()
        self.assertEqual(read_scanned_document(reading), read_receipt(reading))

    def test_the_declared_type_is_not_echoed_into_the_result(self):
        self.assertNotIn("document_type", read_scanned_document(raw()))


class LegibilityIsCheckedBeforeTheDocumentType(unittest.TestCase):
    """Under the floor, the classification is as unreliable as the amounts.

    A real bill photographed too badly to read may well come back labelled
    ``other`` -- the model could not see it either. Telling that person "this is
    not a receipt" sends them looking for a different piece of paper; telling
    them "photograph it again" is both true and useful.
    """

    def test_a_blurry_unclassifiable_photo_is_reported_as_blur(self):
        with self.assertRaises(ReceiptError) as caught:
            read_scanned_document(raw(document_type="other", confidence=0.10))
        self.assertEqual(caught.exception.code, "RECEIPT_TOO_BLURRY")

    def test_a_blurry_reading_with_no_document_type_is_reported_as_blur(self):
        reading = raw(confidence=0.10)
        del reading["document_type"]
        with self.assertRaises(ReceiptError) as caught:
            read_scanned_document(reading)
        self.assertEqual(caught.exception.code, "RECEIPT_TOO_BLURRY")

    def test_a_blurry_declared_receipt_is_still_reported_as_blur(self):
        with self.assertRaises(ReceiptError) as caught:
            read_scanned_document(raw(confidence=0.10))
        self.assertEqual(caught.exception.code, "RECEIPT_TOO_BLURRY")

    def test_at_the_floor_the_document_type_decides_again(self):
        """Exactly on the floor the reading is admissible, so the type rules."""
        with self.assertRaises(ReceiptError) as caught:
            read_scanned_document(
                raw(document_type="other", confidence=CONFIDENCE_FLOOR / 100)
            )
        self.assertEqual(caught.exception.code, "NOT_A_RECEIPT")

    def test_a_malformed_confidence_is_refused_before_anything_else(self):
        """No confidence means no admissibility decision at all."""
        reading = raw(document_type="price_list")
        del reading["confidence"]
        with self.assertRaises(ReceiptError) as caught:
            read_scanned_document(reading)
        self.assertEqual(caught.exception.code, "INVALID_CONFIDENCE")


if __name__ == "__main__":
    unittest.main()
