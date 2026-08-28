"""A bill draft becomes allocator input -- and nothing else.

rd-be-03 joins the receipt reader to the money that already works. The danger
this file exists to prevent is stated in the task: two divisions living in one
product is the surest way to show two different numbers for one meal. So the
projection is allowed to *arrange* facts into the frozen ADR-0004 shape and is
forbidden from *computing* a share. Every test below is either about that
boundary or about the suggested/confirmed distinction.
"""

from __future__ import annotations

import ast
import pathlib
import unittest

from app.domain.allocator import allocate
from app.domain.bill import (
    SHARE_CONFIRMED,
    SHARE_SUGGESTED,
    BillError,
    allocator_input_from_bill,
)

DOMAIN = pathlib.Path(__file__).resolve().parents[2] / "app" / "domain"


def _share(participant_id: str, source: str = SHARE_CONFIRMED) -> dict:
    return {"participant_id": participant_id, "source": source}


def _bill(**overrides) -> dict:
    """One two-person meal: pho for an, bun for binh, both confirmed."""
    bill = {
        "participants": ["an", "binh"],
        "printed_total_vnd": 135_000,
        "items": [
            {"item_key": "i1", "amount_vnd": 65_000, "shares": [_share("an")]},
            {"item_key": "i2", "amount_vnd": 70_000, "shares": [_share("binh")]},
        ],
        "surcharges": [],
        "discounts": [],
        "advancer_id": "an",
    }
    bill.update(overrides)
    return bill


class ProjectionFeedsTheFrozenAllocator(unittest.TestCase):
    """The output is allocator input. Not a result, not a second opinion."""

    def test_projection_output_is_accepted_by_the_allocator_unchanged(self):
        projected = allocator_input_from_bill(_bill())

        result = allocate(projected["expense"])

        self.assertEqual(result["allocations"], {"an": 65_000, "binh": 70_000})

    def test_item_shares_become_the_shared_by_set_of_adr_0004(self):
        projected = allocator_input_from_bill(_bill())

        self.assertEqual(
            projected["expense"]["items"],
            [
                {"item_id": "i1", "amount_vnd": 65_000, "shared_by": ["an"]},
                {"item_id": "i2", "amount_vnd": 70_000, "shared_by": ["binh"]},
            ],
        )

    def test_one_dish_split_between_two_people_is_divided_by_the_allocator(self):
        """The odd dong here is the whole point.

        65.001 over two people is not an integer. If the projection ever grows
        its own division, this is the case where its answer and the allocator's
        would start to differ -- and the allocator's tie-break (the advancer
        absorbs the rounding) would be lost.
        """
        bill = _bill(
            printed_total_vnd=65_001,
            items=[
                {
                    "item_key": "i1",
                    "amount_vnd": 65_001,
                    "shares": [_share("an"), _share("binh")],
                }
            ],
        )

        result = allocate(allocator_input_from_bill(bill)["expense"])

        self.assertEqual(sum(result["allocations"].values()), 65_001)
        self.assertEqual(result["rounding_gainers"], ["an"])

    def test_the_bill_path_and_the_hand_built_path_agree_to_the_dong(self):
        """Two screens, one meal, one number -- proven, not asserted in prose.

        The right-hand side is exactly what POST /expenses builds today via
        `_allocator_input`. If the bill path ever stops routing through the
        allocator, this is the test that goes red.
        """
        bill = _bill(
            printed_total_vnd=157_000,
            items=[
                {
                    "item_key": "i1",
                    "amount_vnd": 65_000,
                    "shares": [_share("an"), _share("binh")],
                },
                {"item_key": "i2", "amount_vnd": 70_000, "shares": [_share("binh")]},
            ],
            surcharges=[
                {
                    "surcharge_id": "s1",
                    "kind": "vat",
                    "amount_vnd": 22_000,
                    "mode": "proportional",
                }
            ],
        )
        hand_built = {
            "participants": ["an", "binh"],
            "total_vnd": 157_000,
            "items": [
                {"item_id": "i1", "amount_vnd": 65_000, "shared_by": ["an", "binh"]},
                {"item_id": "i2", "amount_vnd": 70_000, "shared_by": ["binh"]},
            ],
            "surcharges": [
                {
                    "surcharge_id": "s1",
                    "kind": "vat",
                    "amount_vnd": 22_000,
                    "mode": "proportional",
                }
            ],
            "discounts": [],
            "advancer_id": "an",
        }

        self.assertEqual(
            allocate(allocator_input_from_bill(bill)["expense"]),
            allocate(hand_built),
        )

    def test_projection_never_invents_or_loses_a_dong(self):
        """Amount-preserving: every amount out was an amount in, verbatim."""
        bill = _bill(
            surcharges=[
                {
                    "surcharge_id": "s1",
                    "kind": "phi phuc vu",
                    "amount_vnd": 15_000,
                    "mode": "even",
                }
            ],
            discounts=[
                {
                    "discount_id": "d1",
                    "amount_vnd": 5_000,
                    "scope": "global_proportional",
                    "item_id": None,
                }
            ],
            printed_total_vnd=145_000,
        )

        expense = allocator_input_from_bill(bill)["expense"]

        self.assertEqual([i["amount_vnd"] for i in expense["items"]], [65_000, 70_000])
        self.assertEqual([s["amount_vnd"] for s in expense["surcharges"]], [15_000])
        self.assertEqual([d["amount_vnd"] for d in expense["discounts"]], [5_000])
        self.assertEqual(expense["total_vnd"], 145_000)


class TheTotalComesFromThePaper(unittest.TestCase):
    def test_printed_total_is_carried_through_even_when_the_lines_disagree(self):
        """Do not quietly stretch the bill to make it add up.

        ADR-0004 decision 1: an implicit stretch materially changes the amount
        the user already looked at. The projection hands both numbers to the
        allocator and lets RECONCILIATION_MISMATCH be the answer.
        """
        bill = _bill(printed_total_vnd=200_000)

        expense = allocator_input_from_bill(bill)["expense"]

        self.assertEqual(expense["total_vnd"], 200_000)

    def test_a_bill_whose_lines_do_not_reach_the_printed_total_is_refused(self):
        from app.domain.contract import AllocationError

        bill = _bill(printed_total_vnd=200_000)

        with self.assertRaises(AllocationError) as caught:
            allocate(allocator_input_from_bill(bill)["expense"])

        self.assertEqual(caught.exception.code, "RECONCILIATION_MISMATCH")

    def test_an_explicit_unlisted_surcharge_closes_the_gap_and_stays_visible(self):
        """The escape hatch ADR-0004 decision 1 names, and only that one.

        The difference becomes a line the drill-down can show, accepted by a
        person. It is never a hidden field inside the total.
        """
        bill = _bill(
            printed_total_vnd=200_000,
            surcharges=[
                {
                    "surcharge_id": "unlisted",
                    "kind": "unlisted",
                    "amount_vnd": 65_000,
                    "mode": "even",
                }
            ],
        )

        result = allocate(allocator_input_from_bill(bill)["expense"])

        self.assertEqual(sum(result["allocations"].values()), 200_000)

    def test_without_a_printed_total_the_listed_lines_define_the_total(self):
        """A bill whose total line was never read still splits."""
        bill = _bill(printed_total_vnd=None)

        expense = allocator_input_from_bill(bill)["expense"]

        self.assertEqual(expense["total_vnd"], 135_000)
        self.assertEqual(
            allocate(expense)["allocations"], {"an": 65_000, "binh": 70_000}
        )


class SuggestedIsNotConfirmed(unittest.TestCase):
    """An AI guess and a person's decision must never look the same."""

    def test_a_fully_confirmed_bill_reports_confirmed(self):
        projected = allocator_input_from_bill(_bill())

        self.assertEqual(projected["assignment_state"], SHARE_CONFIRMED)
        self.assertEqual(projected["suggested_item_keys"], [])

    def test_one_ai_suggested_share_makes_the_whole_projection_suggested(self):
        bill = _bill(
            items=[
                {"item_key": "i1", "amount_vnd": 65_000, "shares": [_share("an")]},
                {
                    "item_key": "i2",
                    "amount_vnd": 70_000,
                    "shares": [_share("binh", SHARE_SUGGESTED)],
                },
            ]
        )

        projected = allocator_input_from_bill(bill)

        self.assertEqual(projected["assignment_state"], SHARE_SUGGESTED)
        self.assertEqual(projected["suggested_item_keys"], ["i2"])

    def test_a_suggested_bill_still_projects_so_the_app_can_preview_it(self):
        """Refusing to preview would force the user to confirm blind.

        Suggested assignments must be *labelled*, not withheld. What they must
        not do is reach the ledger -- that gate lives in the service layer.
        """
        bill = _bill(
            items=[
                {
                    "item_key": "i1",
                    "amount_vnd": 65_000,
                    "shares": [_share("an", SHARE_SUGGESTED)],
                },
                {
                    "item_key": "i2",
                    "amount_vnd": 70_000,
                    "shares": [_share("binh", SHARE_SUGGESTED)],
                },
            ]
        )

        projected = allocator_input_from_bill(bill)

        self.assertEqual(
            allocate(projected["expense"])["allocations"],
            {"an": 65_000, "binh": 70_000},
        )
        self.assertEqual(projected["assignment_state"], SHARE_SUGGESTED)

    def test_suggested_item_keys_are_in_byte_order_not_input_order(self):
        bill = _bill(
            items=[
                {
                    "item_key": "z",
                    "amount_vnd": 65_000,
                    "shares": [_share("an", SHARE_SUGGESTED)],
                },
                {
                    "item_key": "a",
                    "amount_vnd": 70_000,
                    "shares": [_share("binh", SHARE_SUGGESTED)],
                },
            ]
        )

        self.assertEqual(
            allocator_input_from_bill(bill)["suggested_item_keys"], ["a", "z"]
        )

    def test_an_unknown_share_source_is_refused_rather_than_treated_as_confirmed(self):
        """Fail closed. A source this module cannot read is not a decision."""
        bill = _bill(
            items=[
                {
                    "item_key": "i1",
                    "amount_vnd": 135_000,
                    "shares": [_share("an", "probably")],
                }
            ]
        )

        with self.assertRaises(BillError) as caught:
            allocator_input_from_bill(bill)

        self.assertEqual(caught.exception.code, "INVALID_SHARE_SOURCE")


class ThingsTheProjectionRefusesToGuess(unittest.TestCase):
    def test_an_item_nobody_is_assigned_to_is_refused_not_shared_by_everyone(self):
        """Defaulting to "everyone" fabricates an obligation.

        ADR-0004 decision 4 rejects an empty `shared_by` for exactly this
        reason. Charging somebody for a dish they did not order is the worst
        failure mode this product has.
        """
        bill = _bill(
            items=[
                {"item_key": "i1", "amount_vnd": 65_000, "shares": [_share("an")]},
                {"item_key": "i2", "amount_vnd": 70_000, "shares": []},
            ]
        )

        with self.assertRaises(BillError) as caught:
            allocator_input_from_bill(bill)

        self.assertEqual(caught.exception.code, "ITEM_HAS_NO_ASSIGNEE")

    def test_a_bill_with_no_items_is_refused_rather_than_split_evenly(self):
        """EVEN_SPLIT is a real allocator case, but it is not a *bill*.

        A scanned bill with zero lines means the read failed. Splitting the
        printed total evenly would dress that failure up as an answer.
        """
        bill = _bill(items=[])

        with self.assertRaises(BillError) as caught:
            allocator_input_from_bill(bill)

        self.assertEqual(caught.exception.code, "BILL_HAS_NO_ITEMS")

    def test_a_participant_outside_the_group_is_left_for_the_allocator_to_reject(self):
        """References are resolved by the allocator, not re-validated here.

        ADR-0004 V2-02 froze this: a second validation pass is a second place
        for the two layers to disagree about which error code comes back.
        """
        from app.domain.contract import AllocationError

        bill = _bill(
            items=[
                {
                    "item_key": "i1",
                    "amount_vnd": 135_000,
                    "shares": [_share("nguoi-la")],
                }
            ]
        )

        with self.assertRaises(AllocationError) as caught:
            allocate(allocator_input_from_bill(bill)["expense"])

        self.assertEqual(caught.exception.code, "UNKNOWN_PARTICIPANT")


class TheProjectionContainsNoSecondDivision(unittest.TestCase):
    """Enforced by parsing, not by promising -- the repo's house style.

    `test_import_boundary.py` guards the layer boundary the same way. Division
    is singled out because that is where a competing split would have to live:
    addition of listed amounts cannot produce a different per-person number,
    but a division can.
    """

    def test_bill_module_performs_no_division_and_touches_no_inexact_number(self):
        source = (DOMAIN / "bill.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp):
                self.assertNotIsInstance(
                    node.op,
                    (ast.Div, ast.FloorDiv),
                    "bill.py divides -- that is a second split, see ADR-0004",
                )
            if isinstance(node, ast.Name):
                self.assertNotIn(
                    node.id,
                    {"Fraction", "Decimal", "float", "round"},
                    f"bill.py reaches for {node.id}; money is integer dong",
                )

    def test_bill_module_does_not_import_the_allocator(self):
        """Arranging input must not become orchestrating the split.

        The service layer calls the allocator. If this module did it too there
        would be two entry points to keep in step.
        """
        from app.domain import bill as bill_module

        imported = {
            name
            for node in ast.walk(ast.parse(pathlib.Path(bill_module.__file__).read_text(encoding="utf-8")))
            if isinstance(node, ast.ImportFrom) and node.module
            for name in [node.module]
        }
        self.assertNotIn("app.domain.allocator", imported)
        self.assertNotIn(".allocator", imported)


if __name__ == "__main__":
    unittest.main()
