"""Differential test: the production plan against an independent brute force.

The golden corpus has ten vectors. Ten vectors cannot tell a general minimising
algorithm from one that happens to answer those ten correctly -- and an engine
that was handed the corpus and asked to make it green has every incentive to
fit it.

So this file never looks at the corpus. It generates balance vectors from a
fixed seed, computes the optimum with the brute-force partition search written
in `test_settlement_golden_selfcheck.py` (a separate transcription that knows
nothing about `ledger.py`), and asserts the production plan matches on every
one. Seeded, so a failure is reproducible rather than a Heisenbug.
"""

from __future__ import annotations

import random
import unittest

from app.domain.ledger import LedgerError, settlement_plan
from tests.domain.test_settlement_golden_selfcheck import (
    greedy_transfers,
    max_zero_sum_groups,
)


def random_balances(rng, people_count, magnitude):
    """A random zero-sum balance map, with the last person absorbing the rest."""
    names = [f"p{i:02d}" for i in range(people_count)]
    amounts = [rng.randint(-magnitude, magnitude) for _ in names[:-1]]
    amounts.append(-sum(amounts))
    return {
        name: amount for name, amount in zip(names, amounts, strict=True) if amount != 0
    }


def positions_cleared_by(transfers):
    rebuilt: dict[str, int] = {}
    for transfer in transfers:
        rebuilt[transfer["sender_id"]] = (
            rebuilt.get(transfer["sender_id"], 0) - transfer["amount_vnd"]
        )
        rebuilt[transfer["recipient_id"]] = (
            rebuilt.get(transfer["recipient_id"], 0) + transfer["amount_vnd"]
        )
    return {person: amount for person, amount in rebuilt.items() if amount != 0}


class PlanMatchesBruteForce(unittest.TestCase):
    def test_transfer_count_equals_n_minus_k_on_random_groups(self):
        rng = random.Random(20260829)
        checked = 0
        for _ in range(300):
            # Small magnitudes on purpose: they make exact coincidences common,
            # which is precisely where the greedy answer diverges from minimal.
            balances = random_balances(rng, rng.randint(2, 9), rng.choice([3, 5, 20]))
            if not balances:
                continue
            checked += 1
            expected = len(balances) - max_zero_sum_groups(balances)
            plan = settlement_plan(balances)
            self.assertEqual(
                plan["transfer_count"], expected, f"khong toi thieu voi {balances}"
            )
            self.assertTrue(plan["proven_minimal"])
        self.assertGreater(checked, 200, "sinh du lieu hong, gan nhu khong kiem gi")

    def test_random_plans_always_clear_the_balances_exactly(self):
        rng = random.Random(4200000)
        for _ in range(300):
            balances = random_balances(rng, rng.randint(2, 9), rng.choice([4, 50, 900000]))
            if not balances:
                continue
            plan = settlement_plan(balances)
            self.assertEqual(positions_cleared_by(plan["transfers"]), balances)
            moved = sum(t["amount_vnd"] for t in plan["transfers"])
            self.assertEqual(moved, -sum(a for a in balances.values() if a < 0))
            for transfer in plan["transfers"]:
                self.assertIsInstance(transfer["amount_vnd"], int)
                self.assertGreater(transfer["amount_vnd"], 0)
                self.assertLess(balances[transfer["sender_id"]], 0)
                self.assertGreater(balances[transfer["recipient_id"]], 0)

    def test_the_corpus_gap_is_not_a_fluke_of_ten_vectors(self):
        """Find, at random, cases where greedy is genuinely worse.

        If this finds none, either the generator is broken or the two
        algorithms are the same one -- both worth knowing.
        """
        rng = random.Random(27)
        strictly_better = 0
        for _ in range(400):
            balances = random_balances(rng, rng.randint(4, 9), rng.choice([3, 4, 6]))
            if not balances:
                continue
            plan = settlement_plan(balances)
            if plan["transfer_count"] < len(greedy_transfers(balances)):
                strictly_better += 1
        self.assertGreater(
            strictly_better,
            0,
            "khong tim duoc ca nao ke hoach tot hon greedy: hai thuat toan co the la mot",
        )


class NeverWorseThanGreedy(unittest.TestCase):
    def test_plan_is_never_longer_than_the_greedy_it_replaces(self):
        rng = random.Random(8)
        for _ in range(300):
            balances = random_balances(rng, rng.randint(2, 9), rng.choice([3, 7, 100]))
            if not balances:
                continue
            self.assertLessEqual(
                settlement_plan(balances)["transfer_count"], len(greedy_transfers(balances))
            )


class DeterminismUnderReordering(unittest.TestCase):
    def test_same_people_in_a_different_dict_order_give_the_same_plan(self):
        """Dict order must not reach the screen. Two members opening the same
        group must see the same list in the same order."""
        rng = random.Random(99)
        for _ in range(120):
            balances = random_balances(rng, rng.randint(2, 8), 6)
            if not balances:
                continue
            items = list(balances.items())
            rng.shuffle(items)
            self.assertEqual(settlement_plan(balances), settlement_plan(dict(items)))


class FallbackStaysHonest(unittest.TestCase):
    def test_large_group_is_correct_even_though_it_is_not_proven(self):
        rng = random.Random(1234)
        balances = random_balances(rng, 40, 500000)
        plan = settlement_plan(balances, exact_limit=15)
        self.assertFalse(plan["proven_minimal"])
        self.assertEqual(positions_cleared_by(plan["transfers"]), balances)
        self.assertLessEqual(plan["transfer_count"], len(balances) - 1)

    def test_raising_the_limit_turns_the_same_input_into_a_proven_plan(self):
        balances = {"a": -500000, "b": -400000, "c": 200000, "d": 300000, "e": 400000}
        self.assertFalse(settlement_plan(balances, exact_limit=4)["proven_minimal"])
        self.assertTrue(settlement_plan(balances, exact_limit=5)["proven_minimal"])
        self.assertEqual(settlement_plan(balances, exact_limit=5)["transfer_count"], 3)


class MoneyRulesHold(unittest.TestCase):
    def test_no_float_survives_anywhere_in_a_plan(self):
        rng = random.Random(5)
        for _ in range(200):
            balances = random_balances(rng, rng.randint(2, 8), 9)
            if not balances:
                continue
            for transfer in settlement_plan(balances)["transfers"]:
                self.assertIs(type(transfer["amount_vnd"]), int)

    def test_a_float_hidden_among_valid_integers_is_still_refused(self):
        with self.assertRaises(LedgerError) as caught:
            settlement_plan({"a": -100, "b": 50, "c": 50.0})
        self.assertEqual(caught.exception.code, "AMOUNT_NOT_INTEGER")

    def test_balances_off_by_one_dong_are_refused(self):
        """One dong of drift is the difference between a ledger and a guess."""
        with self.assertRaises(LedgerError) as caught:
            settlement_plan({"a": -100000, "b": 99999})
        self.assertEqual(caught.exception.code, "BALANCES_DO_NOT_NET_TO_ZERO")


if __name__ == "__main__":
    unittest.main()
