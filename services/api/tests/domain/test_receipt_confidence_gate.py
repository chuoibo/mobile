"""The gate that stops a blurry photo from becoming confident-looking money.

A blurry receipt is still a receipt: the model does not refuse it the way it
refuses a landscape photo. It reads it, invents plausible line items, and --
because the invented lines add up to the invented total -- reports
``totals_agree`` with an empty ``warnings`` list. The fabrication comes back
looking CLEANER than a correct reading of a real bill, which genuinely
disagrees with its own printed total.

The only signal that moved was ``confidence``, and nothing consulted it:
a reading at 10 and a reading at 98 produced the same HTTP 200 and the same
shape. This file makes confidence a decision input instead of a decoration.

Thresholds come from measurement, not taste. Sweeping Gaussian blur over one
receipt crop and calling Gemini for real (28 readings), plus a second sweep of
the degradations a real phone photo actually has (18 readings: 1x-6x scale,
JPEG q30-q80, mild shake):

    legitimately readable photo   confidence 95-98   (18/18 observations)
    money wrong but plausible     confidence 60-88
    money catastrophically wrong  confidence 10-40   (silent fabrications here)

Two empty bands separate those groups: nothing was ever observed in (40, 60)
and nothing in (88, 95). The thresholds are placed in those gaps.

What confidence does NOT do is certify correctness. It tracks how legible the
text is, which is exactly what the prompt asks it for. Measured
counterexamples: at confidence 98 one line came back 40.000 short, and at 95
one line came back 10.000 short. So ``needs_review=False`` means "no signal
fired", never "these numbers are right" -- see the band tests below.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.domain.receipt import (  # noqa: E402
    CONFIDENCE_FLOOR,
    CONFIDENCE_REVIEW,
    ReceiptError,
    read_receipt,
)


def raw(**overrides) -> dict:
    """One well-formed reading whose numbers agree, so only the gate can fail it."""
    reading = {
        "items": [
            {"name": "Sườn nướng Mỹ", "quantity_text": "1", "line_total_text": "219.000"},
            {"name": "Ba chỉ heo", "quantity_text": "1", "line_total_text": "149.000"},
        ],
        "total_text": "368.000",
        "confidence": 0.98,
    }
    reading.update(overrides)
    return reading


class TheThresholdsSitInTheMeasuredGaps(unittest.TestCase):
    """If these move, the measurement behind them has to be redone."""

    def test_floor_is_below_every_legitimate_reading_observed(self):
        self.assertEqual(CONFIDENCE_FLOOR, 50)

    def test_review_bar_is_below_the_typical_readable_photo(self):
        self.assertEqual(CONFIDENCE_REVIEW, 90)

    def test_the_floor_leaves_room_under_the_review_bar(self):
        self.assertLess(CONFIDENCE_FLOOR, CONFIDENCE_REVIEW)


class ABlurryReadingIsRefusedOutright(unittest.TestCase):
    """Below the floor the product returns no items at all.

    Returning a fabricated list for the user to "just confirm" is worse than
    refusing: it anchors them on numbers nobody read off the paper.
    """

    def test_a_reading_under_the_floor_raises(self):
        with self.assertRaises(ReceiptError) as caught:
            read_receipt(raw(confidence=0.10))
        self.assertEqual(caught.exception.code, "RECEIPT_TOO_BLURRY")

    def test_the_catastrophic_band_from_the_sweep_is_refused(self):
        """10, 15, 20, 30, 40 were all observed with wildly wrong money."""
        for percent in (10, 15, 20, 30, 40):
            with self.subTest(confidence=percent):
                with self.assertRaises(ReceiptError) as caught:
                    read_receipt(raw(confidence=percent / 100))
                self.assertEqual(caught.exception.code, "RECEIPT_TOO_BLURRY")

    def test_refusal_beats_the_self_agreeing_fabrication(self):
        """The exact shape that fooled the eye: invented lines that agree.

        Sum is 660.000 and the printed total reads 660.000, so nothing
        disagrees and no warning would ever be produced. Only confidence
        distinguishes this from a real reading.
        """
        fabricated = raw(
            items=[
                {"name": "Món 1", "quantity_text": "1", "line_total_text": "330.000"},
                {"name": "Món 2", "quantity_text": "1", "line_total_text": "330.000"},
            ],
            total_text="660.000",
            confidence=0.20,
        )
        with self.assertRaises(ReceiptError) as caught:
            read_receipt(fabricated)
        self.assertEqual(caught.exception.code, "RECEIPT_TOO_BLURRY")

    def test_the_floor_itself_is_not_refused(self):
        result = read_receipt(raw(confidence=CONFIDENCE_FLOOR / 100))
        self.assertEqual(result["confidence"], CONFIDENCE_FLOOR)

    def test_blur_is_reported_as_blur_even_when_no_items_were_read(self):
        """A blurry photo that yielded nothing should say so, not say 'no items'."""
        with self.assertRaises(ReceiptError) as caught:
            read_receipt(raw(items=[], confidence=0.10))
        self.assertEqual(caught.exception.code, "RECEIPT_TOO_BLURRY")

    def test_an_empty_reading_at_good_confidence_still_reports_no_items(self):
        with self.assertRaises(ReceiptError) as caught:
            read_receipt(raw(items=[]))
        self.assertEqual(caught.exception.code, "NO_ITEMS_READ")


class TheMiddleBandComesBackFlagged(unittest.TestCase):
    """Readable enough to show, not trustworthy enough to accept silently."""

    def test_the_middle_band_sets_needs_review(self):
        """60-88 was observed returning eight plausible items and wrong money."""
        for percent in (50, 60, 70, 75, 88):
            with self.subTest(confidence=percent):
                result = read_receipt(raw(confidence=percent / 100))
                self.assertIs(result["needs_review"], True)

    def test_the_middle_band_still_returns_the_items(self):
        result = read_receipt(raw(confidence=0.75))
        self.assertEqual(len(result["items"]), 2)

    def test_the_flag_is_explained_in_words_the_user_can_read(self):
        result = read_receipt(raw(confidence=0.75))
        self.assertTrue(
            any("kiểm" in warning or "rõ" in warning for warning in result["warnings"]),
            f"no Vietnamese review warning in {result['warnings']}",
        )

    def test_a_confident_reading_is_not_flagged(self):
        result = read_receipt(raw(confidence=0.98))
        self.assertIs(result["needs_review"], False)

    def test_the_review_bar_itself_is_not_flagged(self):
        result = read_receipt(raw(confidence=CONFIDENCE_REVIEW / 100))
        self.assertIs(result["needs_review"], False)

    def test_needs_review_is_always_present(self):
        """The app branches on this field, so it may never be absent."""
        self.assertIn("needs_review", read_receipt(raw()))


class NothingToCrossCheckAlsoNeedsReview(unittest.TestCase):
    """A price list read as a bill came back at confidence 95-100, warnings empty.

    When the paper prints no total, the item sum has nothing to disagree with,
    so the one existing warning can never fire. High confidence plus no
    cross-check is the other way a fabrication arrives looking clean.
    """

    def test_a_reading_without_a_printed_total_is_flagged(self):
        result = read_receipt(raw(total_text=None, confidence=0.98))
        self.assertIs(result["needs_review"], True)

    def test_it_is_flagged_even_at_full_confidence(self):
        result = read_receipt(raw(total_text=None, confidence=1.0))
        self.assertIs(result["needs_review"], True)

    def test_the_missing_cross_check_is_explained(self):
        result = read_receipt(raw(total_text=None, confidence=0.98))
        self.assertTrue(result["warnings"], "a reading with no cross-check said nothing")


class TheGateDoesNotTouchTheMoney(unittest.TestCase):
    """Law 2: the gate decides whether to answer, never what the numbers are."""

    def test_amounts_are_unchanged_when_flagged(self):
        result = read_receipt(raw(confidence=0.75))
        self.assertEqual(
            [item["line_total_vnd"] for item in result["items"]], [219000, 149000]
        )
        self.assertEqual(result["items_total_vnd"], 368000)
        self.assertEqual(result["total_vnd"], 368000)

    def test_every_amount_is_still_an_integer(self):
        result = read_receipt(raw(confidence=0.75))
        for item in result["items"]:
            self.assertIs(type(item["line_total_vnd"]), int)
        self.assertIs(type(result["items_total_vnd"]), int)

    def test_the_disagreement_warning_survives_alongside_the_review_flag(self):
        result = read_receipt(raw(total_text="400.000", confidence=0.75))
        self.assertIs(result["totals_agree"], False)
        self.assertEqual(result["total_difference_vnd"], 32000)
        self.assertIs(result["needs_review"], True)


if __name__ == "__main__":
    unittest.main()
