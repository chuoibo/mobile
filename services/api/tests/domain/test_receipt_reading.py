"""Turning one raw vision reading into a receipt the product may show.

The rule this file exists to defend: the sum of the line items and the total
printed on the paper are two different facts. Tax, service charge, a discount
the waiter applied by hand, or simply a model misreading one digit will make
them disagree. Forcing them to agree changes a number the user already saw on
their own receipt, so both are reported and the disagreement is named.

Everything here is pure: ``dict`` in, ``dict`` out, no model and no network.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.domain.receipt import ReceiptError, read_receipt  # noqa: E402


def raw(**overrides) -> dict:
    """One well-formed vision reading; each test perturbs a single field."""
    reading = {
        "items": [
            {"name": "Sườn nướng Mỹ", "quantity_text": "1", "line_total_text": "219.000"},
            {"name": "Ba chỉ heo", "quantity_text": "1", "line_total_text": "149.000"},
        ],
        "total_text": "368.000",
        "confidence": 0.92,
    }
    reading.update(overrides)
    return reading


class HappyPath(unittest.TestCase):
    def test_items_are_normalized_to_integer_dong(self):
        result = read_receipt(raw())
        self.assertEqual(
            [item["line_total_vnd"] for item in result["items"]], [219000, 149000]
        )

    def test_names_are_preserved_verbatim(self):
        result = read_receipt(raw())
        self.assertEqual(result["items"][0]["name"], "Sườn nướng Mỹ")

    def test_items_total_is_the_sum_we_computed_ourselves(self):
        self.assertEqual(read_receipt(raw())["items_total_vnd"], 368000)

    def test_printed_total_is_reported_separately(self):
        self.assertEqual(read_receipt(raw())["total_vnd"], 368000)

    def test_agreement_is_stated_explicitly(self):
        result = read_receipt(raw())
        self.assertIs(result["totals_agree"], True)
        self.assertEqual(result["total_difference_vnd"], 0)

    def test_confidence_becomes_an_integer_percent(self):
        self.assertEqual(read_receipt(raw())["confidence"], 92)

    def test_no_warnings_when_everything_lines_up(self):
        self.assertEqual(read_receipt(raw())["warnings"], [])


class TotalsThatDisagree(unittest.TestCase):
    """The heart of this module. Nothing here may be silently reconciled."""

    def test_both_numbers_survive(self):
        result = read_receipt(raw(total_text="1.125.000"))
        self.assertEqual(result["items_total_vnd"], 368000)
        self.assertEqual(result["total_vnd"], 1125000)

    def test_disagreement_is_flagged(self):
        result = read_receipt(raw(total_text="1.125.000"))
        self.assertIs(result["totals_agree"], False)

    def test_difference_is_signed_from_the_printed_total(self):
        result = read_receipt(raw(total_text="1.125.000"))
        self.assertEqual(result["total_difference_vnd"], 1125000 - 368000)

    def test_printed_total_below_the_lines_gives_a_negative_difference(self):
        """A discount applied at the till. Still not ours to reconcile."""
        result = read_receipt(raw(total_text="300.000"))
        self.assertEqual(result["total_difference_vnd"], 300000 - 368000)

    def test_a_warning_names_the_disagreement(self):
        result = read_receipt(raw(total_text="1.125.000"))
        self.assertEqual(len(result["warnings"]), 1)

    def test_no_line_item_is_edited_to_close_the_gap(self):
        result = read_receipt(raw(total_text="1.125.000"))
        self.assertEqual(
            [item["line_total_vnd"] for item in result["items"]], [219000, 149000]
        )

    def test_items_total_is_never_replaced_by_the_printed_total(self):
        result = read_receipt(raw(total_text="1.125.000"))
        self.assertNotEqual(result["items_total_vnd"], result["total_vnd"])


class MissingPrintedTotal(unittest.TestCase):
    def test_absent_total_is_none_not_a_guess(self):
        result = read_receipt(raw(total_text=None))
        self.assertIsNone(result["total_vnd"])

    def test_items_total_is_still_computed(self):
        self.assertEqual(read_receipt(raw(total_text=None))["items_total_vnd"], 368000)

    def test_agreement_is_unknown_rather_than_true(self):
        result = read_receipt(raw(total_text=None))
        self.assertIsNone(result["totals_agree"])

    def test_difference_is_none_when_there_is_nothing_to_compare(self):
        self.assertIsNone(read_receipt(raw(total_text=None))["total_difference_vnd"])


class Quantities(unittest.TestCase):
    def test_quantity_is_an_integer(self):
        result = read_receipt(
            raw(
                items=[
                    {
                        "name": "Pepsi",
                        "quantity_text": "2",
                        "line_total_text": "28.000",
                    }
                ],
                total_text="28.000",
            )
        )
        self.assertEqual(result["items"][0]["quantity"], 2)

    def test_unit_price_is_derived_only_when_the_division_is_exact(self):
        result = read_receipt(
            raw(
                items=[
                    {
                        "name": "Pepsi",
                        "quantity_text": "2",
                        "line_total_text": "28.000",
                    }
                ],
                total_text="28.000",
            )
        )
        self.assertEqual(result["items"][0]["unit_price_vnd"], 14000)

    def test_inexact_division_leaves_unit_price_unknown(self):
        """14000.333 dong is not a price. Report nothing rather than round."""
        result = read_receipt(
            raw(
                items=[
                    {
                        "name": "Lẩu kim chi",
                        "quantity_text": "3",
                        "line_total_text": "100.000",
                    }
                ],
                total_text="100.000",
            )
        )
        self.assertIsNone(result["items"][0]["unit_price_vnd"])

    def test_a_printed_unit_price_is_used_as_printed(self):
        result = read_receipt(
            raw(
                items=[
                    {
                        "name": "Tiger bạc",
                        "quantity_text": "3",
                        "unit_price_text": "18.000",
                        "line_total_text": "54.000",
                    }
                ],
                total_text="54.000",
            )
        )
        self.assertEqual(result["items"][0]["unit_price_vnd"], 18000)

    def test_a_printed_unit_price_that_contradicts_the_line_total_warns(self):
        """3 x 20.000 is not 54.000. Say so; do not pick a winner."""
        result = read_receipt(
            raw(
                items=[
                    {
                        "name": "Tiger bạc",
                        "quantity_text": "3",
                        "unit_price_text": "20.000",
                        "line_total_text": "54.000",
                    }
                ],
                total_text="54.000",
            )
        )
        self.assertEqual(result["items"][0]["line_total_vnd"], 54000)
        self.assertEqual(result["items"][0]["unit_price_vnd"], 20000)
        self.assertTrue(result["warnings"])

    def test_missing_quantity_defaults_to_one(self):
        result = read_receipt(
            raw(
                items=[{"name": "Cơm chiên trứng", "line_total_text": "79.000"}],
                total_text="79.000",
            )
        )
        self.assertEqual(result["items"][0]["quantity"], 1)

    def test_zero_quantity_is_refused(self):
        with self.assertRaises(ReceiptError):
            read_receipt(
                raw(
                    items=[
                        {
                            "name": "Pepsi",
                            "quantity_text": "0",
                            "line_total_text": "28.000",
                        }
                    ]
                )
            )

    def test_unreadable_quantity_is_refused(self):
        with self.assertRaises(ReceiptError):
            read_receipt(
                raw(
                    items=[
                        {
                            "name": "Pepsi",
                            "quantity_text": "vài",
                            "line_total_text": "28.000",
                        }
                    ]
                )
            )


class RefusedReadings(unittest.TestCase):
    def test_not_a_dict(self):
        with self.assertRaises(ReceiptError):
            read_receipt("219.000")

    def test_missing_items_key(self):
        with self.assertRaises(ReceiptError):
            read_receipt({"total_text": "219.000", "confidence": 0.9})

    def test_no_items_at_all(self):
        """An empty read is a failed read, not a zero-dong receipt."""
        with self.assertRaises(ReceiptError) as caught:
            read_receipt(raw(items=[]))
        self.assertEqual(caught.exception.code, "NO_ITEMS_READ")

    def test_item_without_a_name(self):
        with self.assertRaises(ReceiptError):
            read_receipt(raw(items=[{"line_total_text": "219.000"}]))

    def test_item_with_a_blank_name(self):
        with self.assertRaises(ReceiptError):
            read_receipt(raw(items=[{"name": "   ", "line_total_text": "219.000"}]))

    def test_item_without_a_line_total(self):
        with self.assertRaises(ReceiptError):
            read_receipt(raw(items=[{"name": "Pepsi", "quantity_text": "2"}]))

    def test_unreadable_line_total(self):
        with self.assertRaises(ReceiptError):
            read_receipt(
                raw(items=[{"name": "Pepsi", "line_total_text": "khoảng 28 nghìn gì đó"}])
            )

    def test_unreadable_printed_total(self):
        with self.assertRaises(ReceiptError):
            read_receipt(raw(total_text="hơn một triệu"))

    def test_missing_confidence(self):
        reading = raw()
        del reading["confidence"]
        with self.assertRaises(ReceiptError):
            read_receipt(reading)

    def test_confidence_outside_the_unit_interval(self):
        with self.assertRaises(ReceiptError):
            read_receipt(raw(confidence=1.4))

    def test_confidence_that_is_not_a_number(self):
        with self.assertRaises(ReceiptError):
            read_receipt(raw(confidence="cao"))


class ConfidenceIsHonest(unittest.TestCase):
    def test_a_low_reading_is_refused_not_returned(self):
        """A 20% read is refused now, not merely passed through honestly.

        Once a caller receives items, it cannot tell an invented list from one
        actually read from the receipt.
        """
        with self.assertRaises(ReceiptError) as caught:
            read_receipt(raw(confidence=0.2))
        self.assertEqual(caught.exception.code, "RECEIPT_TOO_BLURRY")

    def test_zero_confidence_is_refused(self):
        with self.assertRaises(ReceiptError) as caught:
            read_receipt(raw(confidence=0.0))
        self.assertEqual(caught.exception.code, "RECEIPT_TOO_BLURRY")

    def test_an_above_floor_reading_is_reported_verbatim(self):
        """A 75% read must not be dressed up as the 90% review threshold."""
        result = read_receipt(raw(confidence=0.75))
        self.assertEqual(result["confidence"], 75)
        self.assertIs(result["needs_review"], True)

    def test_rounding_is_deterministic(self):
        self.assertEqual(read_receipt(raw(confidence=0.925))["confidence"], 92)

    def test_a_disagreeing_total_lowers_nothing_by_itself(self):
        """Confidence describes legibility, not arithmetic. Keep them apart."""
        result = read_receipt(raw(total_text="1.125.000", confidence=0.98))
        self.assertEqual(result["confidence"], 98)
        self.assertIs(result["totals_agree"], False)


class TheReadingIsACopy(unittest.TestCase):
    def test_the_caller_input_is_not_mutated(self):
        reading = raw()
        before = repr(reading)
        read_receipt(reading)
        self.assertEqual(repr(reading), before)

    def test_every_money_field_is_a_strict_int(self):
        result = read_receipt(raw(total_text="1.125.000"))
        self.assertIs(type(result["items_total_vnd"]), int)
        self.assertIs(type(result["total_vnd"]), int)
        self.assertIs(type(result["total_difference_vnd"]), int)
        for item in result["items"]:
            self.assertIs(type(item["line_total_vnd"]), int)
            self.assertIs(type(item["quantity"]), int)


if __name__ == "__main__":
    unittest.main()
