"""Check the golden corpus is internally consistent, without any allocator.

The golden vectors are hand-computed by a human against ADR-0004. They are the
defence against "both implementations agree and both are wrong", so an
arithmetic slip in the corpus itself would silently disarm that defence.

This file deliberately does NOT import an allocator. It only checks that the
numbers written down are consistent with each other and with the contract.
"""

from __future__ import annotations

import json
import math
import pathlib
import unittest
from fractions import Fraction

GOLDEN_DIR = pathlib.Path(__file__).resolve().parents[1] / "golden"

WARNING_VOCABULARY = {
    "advancer_not_participant",
    "proportional_fallback_to_even",
    "zero_share_participants",
}

ERROR_CODES = {
    "RECONCILIATION_MISMATCH", "EMPTY_SHARED_BY", "DISCOUNT_EXCEEDS_ITEM",
    "DISCOUNT_EXCEEDS_BASE", "DUPLICATE_PARTICIPANT", "NO_PARTICIPANTS",
    "NEGATIVE_AMOUNT", "AMOUNT_TOO_LARGE", "UNKNOWN_PARTICIPANT",
    "UNKNOWN_ITEM", "INVALID_MODE", "INVALID_SCOPE",
}


def load_vectors():
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        for vector in json.loads(path.read_text(encoding="utf-8")):
            yield path.name, vector


def parse_fraction(text: str) -> Fraction:
    numerator, denominator = text.split("/")
    return Fraction(int(numerator), int(denominator))


class GoldenCorpusSelfCheck(unittest.TestCase):
    def setUp(self):
        self.vectors = list(load_vectors())
        self.assertGreater(len(self.vectors), 0, "golden corpus is empty")

    def test_ids_are_unique(self):
        ids = [vector["id"] for _, vector in self.vectors]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_vector_declares_success_or_error(self):
        for name, vector in self.vectors:
            with self.subTest(vector["id"], file=name):
                has_expect = "expect" in vector
                has_error = "expect_error" in vector
                self.assertNotEqual(has_expect, has_error, "exactly one of expect/expect_error")
                if has_error:
                    self.assertIn(vector["expect_error"], ERROR_CODES)

    def test_amounts_stay_below_repo_guard_digit_threshold(self):
        # scripts/repo_guard.py blocks runs of nine or more digits. Extreme
        # values belong in generated property tests, never in stored literals.
        for name, vector in self.vectors:
            with self.subTest(vector["id"], file=name):
                for number in _all_integers(vector):
                    self.assertLess(abs(number), 100_000_000, "would trip repo-guard long-number")

    def test_exact_shares_sum_to_total(self):
        for name, vector in self.vectors:
            if "expect" not in vector:
                continue
            with self.subTest(vector["id"], file=name):
                shares = vector["expect"]["exact_shares"]
                total = sum((parse_fraction(v) for v in shares.values()), Fraction(0))
                self.assertEqual(total, Fraction(vector["input"]["total_vnd"]))

    def test_allocations_sum_to_total(self):
        for name, vector in self.vectors:
            if "expect" not in vector:
                continue
            with self.subTest(vector["id"], file=name):
                allocations = vector["expect"]["allocations"]
                self.assertEqual(sum(allocations.values()), vector["input"]["total_vnd"])

    def test_allocation_equals_floor_plus_rounding_gain(self):
        for name, vector in self.vectors:
            if "expect" not in vector:
                continue
            with self.subTest(vector["id"], file=name):
                expect = vector["expect"]
                gainers = expect["rounding_gainers"]
                self.assertEqual(len(gainers), len(set(gainers)), "nobody may gain twice")
                for participant, allocated in expect["allocations"].items():
                    exact = parse_fraction(expect["exact_shares"][participant])
                    expected = math.floor(exact) + (1 if participant in gainers else 0)
                    self.assertEqual(allocated, expected)

    def test_deficit_matches_number_of_gainers(self):
        for name, vector in self.vectors:
            if "expect" not in vector:
                continue
            with self.subTest(vector["id"], file=name):
                expect = vector["expect"]
                floors = sum(math.floor(parse_fraction(v)) for v in expect["exact_shares"].values())
                deficit = vector["input"]["total_vnd"] - floors
                self.assertEqual(deficit, len(expect["rounding_gainers"]))
                self.assertGreaterEqual(deficit, 0)
                self.assertLess(deficit, max(1, len(vector["input"]["participants"])))

    def test_no_zero_remainder_participant_gains_while_a_positive_one_misses(self):
        # ADR-0004 invariant 8.
        for name, vector in self.vectors:
            if "expect" not in vector:
                continue
            with self.subTest(vector["id"], file=name):
                expect = vector["expect"]
                gainers = set(expect["rounding_gainers"])
                remainders = {
                    participant: parse_fraction(text) - math.floor(parse_fraction(text))
                    for participant, text in expect["exact_shares"].items()
                }
                gained_with_zero = [p for p in gainers if remainders[p] == 0]
                missed_with_positive = [
                    p for p, r in remainders.items() if r > 0 and p not in gainers
                ]
                if gained_with_zero:
                    self.assertEqual(missed_with_positive, [])

    def test_participant_sets_line_up(self):
        for name, vector in self.vectors:
            if "expect" not in vector:
                continue
            with self.subTest(vector["id"], file=name):
                participants = set(vector["input"]["participants"])
                expect = vector["expect"]
                self.assertEqual(set(expect["allocations"]), participants)
                self.assertEqual(set(expect["exact_shares"]), participants)
                self.assertLessEqual(set(expect["rounding_gainers"]), participants)

    def test_warnings_use_the_closed_sorted_vocabulary(self):
        for name, vector in self.vectors:
            if "expect" not in vector:
                continue
            with self.subTest(vector["id"], file=name):
                warnings = vector["expect"]["warnings"]
                self.assertLessEqual(set(warnings), WARNING_VOCABULARY)
                self.assertEqual(warnings, sorted(warnings))
                self.assertEqual(len(warnings), len(set(warnings)))

    def test_declared_warnings_match_the_conditions_that_produce_them(self):
        for name, vector in self.vectors:
            if "expect" not in vector:
                continue
            with self.subTest(vector["id"], file=name):
                data = vector["input"]
                expect = vector["expect"]
                warnings = set(expect["warnings"])

                advancer = data["advancer_id"]
                expected_advancer_warning = (
                    advancer is not None and advancer not in data["participants"]
                )
                self.assertEqual(
                    "advancer_not_participant" in warnings, expected_advancer_warning
                )

                # ADR-0004 #21: exact share zero, and only when the bill is non-zero.
                zero_share = any(
                    parse_fraction(text) == 0 for text in expect["exact_shares"].values()
                )
                expected_zero_warning = zero_share and data["total_vnd"] > 0
                self.assertEqual(
                    "zero_share_participants" in warnings, expected_zero_warning
                )

    def test_reconciliation_holds_for_every_successful_vector(self):
        for name, vector in self.vectors:
            if "expect" not in vector:
                continue
            with self.subTest(vector["id"], file=name):
                data = vector["input"]
                is_even_split = not data["items"] and not data["surcharges"] and not data["discounts"]
                if is_even_split:
                    continue
                listed = (
                    sum(item["amount_vnd"] for item in data["items"])
                    + sum(surcharge["amount_vnd"] for surcharge in data["surcharges"])
                    - sum(discount["amount_vnd"] for discount in data["discounts"])
                )
                self.assertEqual(listed, data["total_vnd"])


def _all_integers(node):
    if isinstance(node, bool):
        return
    if isinstance(node, int):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _all_integers(value)
    elif isinstance(node, list):
        for value in node:
            yield from _all_integers(value)


if __name__ == "__main__":
    unittest.main()
