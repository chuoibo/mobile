"""Drive the hand-computed settlement corpus through the production code.

The corpus in `golden_settlement/` was written and self-checked before this
algorithm existed (see `test_settlement_golden_selfcheck.py`). This file is the
other half: it asserts the production code reproduces those hand answers.

The load-bearing assertion is `test_transfer_count_is_the_hand_computed_minimum`.
Vectors S05 and S10 are the ones the greedy already in `ledger.py` gets wrong --
4 transfers where 3 suffice, and 5 where 4 suffice. Any implementation that
merely clears the balances passes every other test in this file and fails that
one.
"""

from __future__ import annotations

import json
import pathlib
import unittest

from app.domain.ledger import (
    LedgerError,
    group_balances,
    settlement_plan,
    settlement_suggestions,
)

GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden_settlement"


def load_vectors():
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        for vector in json.loads(path.read_text(encoding="utf-8")):
            yield path.name, vector


def positions_cleared_by(transfers):
    """Net effect of a transfer list, as a balance map."""
    rebuilt: dict[str, int] = {}
    for transfer in transfers:
        rebuilt[transfer["sender_id"]] = (
            rebuilt.get(transfer["sender_id"], 0) - transfer["amount_vnd"]
        )
        rebuilt[transfer["recipient_id"]] = (
            rebuilt.get(transfer["recipient_id"], 0) + transfer["amount_vnd"]
        )
    return {person: amount for person, amount in rebuilt.items() if amount != 0}


class BalancesComeFromTheLedger(unittest.TestCase):
    def test_group_balances_reproduces_every_hand_computed_balance(self):
        for name, vector in load_vectors():
            with self.subTest(vector=f"{name}:{vector['id']}"):
                receipts = {
                    (r["sender_id"], r["recipient_id"]): r["amount_vnd"]
                    for r in vector["input"]["receipts"]
                }
                self.assertEqual(
                    group_balances(vector["input"]["obligations"], receipts),
                    vector["expect"]["balances"],
                )


class MinimumTransfers(unittest.TestCase):
    def test_transfer_count_is_the_hand_computed_minimum(self):
        for name, vector in load_vectors():
            with self.subTest(vector=f"{name}:{vector['id']}"):
                plan = settlement_plan(vector["expect"]["balances"])
                self.assertEqual(
                    plan["transfer_count"],
                    vector["expect"]["chuyen_toi_thieu"],
                    f"{vector['id']}: {vector['expect']['can_duoi']}",
                )
                self.assertTrue(plan["proven_minimal"])

    def test_transfers_clear_exactly_the_recorded_balances(self):
        for name, vector in load_vectors():
            with self.subTest(vector=f"{name}:{vector['id']}"):
                plan = settlement_plan(vector["expect"]["balances"])
                self.assertEqual(
                    positions_cleared_by(plan["transfers"]), vector["expect"]["balances"]
                )

    def test_total_owed_equals_total_due_with_zero_difference(self):
        for name, vector in load_vectors():
            with self.subTest(vector=f"{name}:{vector['id']}"):
                plan = settlement_plan(vector["expect"]["balances"])
                moved = sum(t["amount_vnd"] for t in plan["transfers"])
                debts = -sum(a for a in vector["expect"]["balances"].values() if a < 0)
                credits = sum(a for a in vector["expect"]["balances"].values() if a > 0)
                self.assertEqual(debts, credits)
                self.assertEqual(moved, debts, "so tien chuyen phai bang dung tong no")

    def test_every_amount_is_a_positive_integer_dong(self):
        for name, vector in load_vectors():
            with self.subTest(vector=f"{name}:{vector['id']}"):
                for transfer in settlement_plan(vector["expect"]["balances"])["transfers"]:
                    amount = transfer["amount_vnd"]
                    self.assertIsInstance(amount, int)
                    self.assertNotIsInstance(amount, bool)
                    self.assertGreater(amount, 0)

    def test_nobody_pays_themselves(self):
        for name, vector in load_vectors():
            with self.subTest(vector=f"{name}:{vector['id']}"):
                for transfer in settlement_plan(vector["expect"]["balances"])["transfers"]:
                    self.assertNotEqual(transfer["sender_id"], transfer["recipient_id"])

    def test_only_debtors_send_and_only_creditors_receive(self):
        """A minimal plan must not route money through a person who is square.

        Spec section 8.8: changing who pays whom is a social change. Dragging an
        uninvolved member into the chain to save a transfer is exactly that.
        """
        for name, vector in load_vectors():
            with self.subTest(vector=f"{name}:{vector['id']}"):
                balances = vector["expect"]["balances"]
                for transfer in settlement_plan(balances)["transfers"]:
                    self.assertLess(balances[transfer["sender_id"]], 0)
                    self.assertGreater(balances[transfer["recipient_id"]], 0)

    def test_plan_is_deterministic(self):
        """A percentage or a name that moves between two identical calls is a
        random number on the screen. Same input, same plan, every time."""
        for name, vector in load_vectors():
            with self.subTest(vector=f"{name}:{vector['id']}"):
                balances = vector["expect"]["balances"]
                first = settlement_plan(balances)
                for _ in range(5):
                    self.assertEqual(settlement_plan(balances), first)


class SuggestionsUseTheSameAlgorithm(unittest.TestCase):
    """One settlement path, not two.

    Two money algorithms in one product is how two screens end up showing two
    different answers for the same meal. `settlement_suggestions` is the public
    name; it must return the minimal plan, not a second opinion.
    """

    def test_suggestions_are_minimal_too(self):
        for name, vector in load_vectors():
            with self.subTest(vector=f"{name}:{vector['id']}"):
                transfers = settlement_suggestions(vector["expect"]["balances"])
                self.assertEqual(len(transfers), vector["expect"]["chuyen_toi_thieu"])

    def test_suggestions_stay_shaped_as_drafts(self):
        for transfer in settlement_suggestions({"a": -70, "b": 70}):
            self.assertEqual(transfer["kind"], "offset_proposal_draft")


class Refusals(unittest.TestCase):
    def test_float_balance_is_refused(self):
        with self.assertRaises(LedgerError) as caught:
            settlement_plan({"a": -0.5, "b": 0.5})
        self.assertEqual(caught.exception.code, "AMOUNT_NOT_INTEGER")

    def test_bool_balance_is_refused(self):
        """`isinstance(True, int)` is True in Python, so True would be one dong."""
        with self.assertRaises(LedgerError) as caught:
            settlement_plan({"a": True, "b": -1})
        self.assertEqual(caught.exception.code, "AMOUNT_NOT_INTEGER")

    def test_balances_that_do_not_net_to_zero_are_refused(self):
        with self.assertRaises(LedgerError) as caught:
            settlement_plan({"a": -10, "b": 5})
        self.assertEqual(caught.exception.code, "BALANCES_DO_NOT_NET_TO_ZERO")

    def test_everyone_square_needs_no_transfer(self):
        plan = settlement_plan({})
        self.assertEqual(plan["transfers"], [])
        self.assertEqual(plan["transfer_count"], 0)
        self.assertTrue(plan["proven_minimal"])


class LargeGroupsSayWhenTheyAreNotProven(unittest.TestCase):
    """Exhaustive search is exponential. Above the cap the plan must still be
    correct and must SAY it is not proven minimal, rather than quietly
    returning a greedy answer under a name that promises the minimum."""

    def test_beyond_the_exact_limit_the_plan_is_flagged_unproven(self):
        balances = {f"p{i:02d}": 1000 for i in range(20)}
        balances.update({f"q{i:02d}": -1000 for i in range(20)})
        plan = settlement_plan(balances, exact_limit=15)
        self.assertFalse(plan["proven_minimal"])
        self.assertEqual(positions_cleared_by(plan["transfers"]), balances)
        self.assertLessEqual(plan["transfer_count"], len(balances) - 1)

    def test_within_the_exact_limit_the_plan_is_proven(self):
        plan = settlement_plan({"a": -500000, "b": -400000, "c": 200000, "d": 300000, "e": 400000})
        self.assertTrue(plan["proven_minimal"])
        self.assertEqual(plan["transfer_count"], 3)


if __name__ == "__main__":
    unittest.main()
