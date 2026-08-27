"""Property tests for the allocator, ADR-0004 section 7.

The generator builds inputs relationally and *derives* `total_vnd` from what it
built, so reconciliation holds by construction and the generated cases actually
exercise the arithmetic instead of piling up in the error paths (ADR-0004
section 5.1). Seeds are fixed, so a failure is replayable.
"""

from __future__ import annotations

import math
import pathlib
import random
import sys
import unittest
from fractions import Fraction

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.domain.allocator import allocate  # noqa: E402
from app.domain.contract import ERROR_PRECEDENCE, MAX_AMOUNT_VND, AllocationError  # noqa: E402

# Deliberately awkward: Vietnamese diacritics, ids differing only by a mark,
# a prefix pair, and one outside the Basic Multilingual Plane.
ID_ALPHABET = [
    "a", "aa", "b", "z", "á", "an", "án", "Bảo", "bảo", "cường",
    "Hà", "ha", "nam", "Nam", "x1", "x10", "😀", "ω", "_", "-",
]


def _parse(text: str) -> Fraction:
    numerator, denominator = text.split("/")
    return Fraction(int(numerator), int(denominator))


def generate_valid_expense(rng: random.Random) -> dict:
    participants = rng.sample(ID_ALPHABET, rng.randint(1, min(12, len(ID_ALPHABET))))

    if rng.random() < 0.15:  # EVEN_SPLIT, the one named special case
        return {
            "participants": participants,
            "total_vnd": rng.choice([0, 1, 3, 7, rng.randint(1, 10**7), MAX_AMOUNT_VND]),
            "items": [], "surcharges": [], "discounts": [], "advancer_id": _advancer(rng, participants),
        }

    items = []
    for index in range(rng.randint(1, 8)):
        shared = rng.sample(participants, rng.randint(1, len(participants)))
        items.append({
            "item_id": f"i{index}",
            "amount_vnd": rng.randint(1, 500_000),
            "shared_by": shared,
        })

    discounts = []
    for index in range(rng.randint(0, 3)):  # item-scoped: 0..3
        item = rng.choice(items)
        headroom = item["amount_vnd"] - sum(
            d["amount_vnd"] for d in discounts if d.get("item_id") == item["item_id"]
        )
        if headroom <= 0:
            continue
        discounts.append({
            "discount_id": f"di{index}",
            "amount_vnd": rng.randint(1, headroom),
            "scope": "item",
            "item_id": item["item_id"],
        })

    base = sum(item["amount_vnd"] for item in items) - sum(
        d["amount_vnd"] for d in discounts if d["scope"] == "item"
    )
    for index in range(rng.randint(0, 2)):  # global: 0..2
        spent = sum(d["amount_vnd"] for d in discounts if d["scope"] == "global_proportional")
        headroom = base - spent
        if headroom <= 0:
            continue
        discounts.append({
            "discount_id": f"dg{index}",
            "amount_vnd": rng.randint(1, headroom),
            "scope": "global_proportional",
            "item_id": None,
        })

    surcharges = [
        {
            "surcharge_id": f"s{index}",
            "kind": rng.choice(["fee", "vat", "shipping", "unlisted"]),
            "amount_vnd": rng.randint(1, 50_000),
            "mode": rng.choice(["proportional", "even"]),
        }
        for index in range(rng.randint(0, 5))
    ]

    total = (
        sum(i["amount_vnd"] for i in items)
        + sum(s["amount_vnd"] for s in surcharges)
        - sum(d["amount_vnd"] for d in discounts)
    )
    return {
        "participants": participants,
        "total_vnd": total,
        "items": items,
        "surcharges": surcharges,
        "discounts": discounts,
        "advancer_id": _advancer(rng, participants),
    }


def _advancer(rng: random.Random, participants):
    roll = rng.random()
    if roll < 0.45:
        return rng.choice(participants)
    if roll < 0.75:
        return None
    return "outsider"


def permuted(expense: dict, rng: random.Random) -> dict:
    shuffled = dict(expense)
    shuffled["participants"] = rng.sample(expense["participants"], len(expense["participants"]))
    shuffled["surcharges"] = rng.sample(expense["surcharges"], len(expense["surcharges"]))
    shuffled["discounts"] = rng.sample(expense["discounts"], len(expense["discounts"]))
    items = []
    for item in rng.sample(expense["items"], len(expense["items"])):
        copy = dict(item)
        copy["shared_by"] = rng.sample(item["shared_by"], len(item["shared_by"]))
        items.append(copy)
    shuffled["items"] = items
    return shuffled


SEEDS = range(400)


class AllocatorProperties(unittest.TestCase):
    def cases(self):
        for seed in SEEDS:
            rng = random.Random(seed)
            yield seed, generate_valid_expense(rng)

    def test_p1_sum_equals_total(self):
        for seed, expense in self.cases():
            with self.subTest(seed=seed):
                self.assertEqual(
                    sum(allocate(expense)["allocations"].values()), expense["total_vnd"]
                )

    def test_p2_integers_and_non_negative(self):
        for seed, expense in self.cases():
            with self.subTest(seed=seed):
                for amount in allocate(expense)["allocations"].values():
                    self.assertIsInstance(amount, int)
                    self.assertNotIsInstance(amount, bool)
                    self.assertGreaterEqual(amount, 0)

    def test_p3_keys_match_participants_and_shares_non_negative(self):
        for seed, expense in self.cases():
            with self.subTest(seed=seed):
                result = allocate(expense)
                expected = set(expense["participants"])
                self.assertEqual(set(result["allocations"]), expected)
                self.assertEqual(set(result["exact_shares"]), expected)
                for text in result["exact_shares"].values():
                    self.assertGreaterEqual(_parse(text), 0)

    def test_p4_outside_advancer_gets_no_share(self):
        for seed, expense in self.cases():
            if expense["advancer_id"] in (None, *expense["participants"]):
                continue
            with self.subTest(seed=seed):
                self.assertNotIn(expense["advancer_id"], allocate(expense)["allocations"])

    def test_p5_exact_shares_sum_to_total(self):
        for seed, expense in self.cases():
            with self.subTest(seed=seed):
                shares = allocate(expense)["exact_shares"].values()
                self.assertEqual(
                    sum((_parse(t) for t in shares), Fraction(0)),
                    Fraction(expense["total_vnd"]),
                )

    def test_p6_allocation_is_floor_plus_gain(self):
        for seed, expense in self.cases():
            with self.subTest(seed=seed):
                result = allocate(expense)
                gainers = set(result["rounding_gainers"])
                for participant, amount in result["allocations"].items():
                    exact = _parse(result["exact_shares"][participant])
                    self.assertEqual(
                        amount, math.floor(exact) + (1 if participant in gainers else 0)
                    )

    def test_p7_gainers_are_the_exact_ranked_tuple(self):
        """Largest remainder, advancer breaking ties only, then UTF-8 bytes.

        This is the property that pins the algorithm itself; the conservation
        checks above all pass on a wrong answer.
        """
        for seed, expense in self.cases():
            with self.subTest(seed=seed):
                result = allocate(expense)
                exact = {p: _parse(t) for p, t in result["exact_shares"].items()}
                floors = {p: math.floor(v) for p, v in exact.items()}
                deficit = expense["total_vnd"] - sum(floors.values())
                advancer = expense["advancer_id"]

                def rank(participant):
                    return (
                        -(exact[participant] - floors[participant]),
                        0 if advancer is not None and participant == advancer else 1,
                        participant.encode("utf-8"),
                    )

                expected = sorted(expense["participants"], key=rank)[:deficit]
                self.assertEqual(result["rounding_gainers"], expected)

    def test_p8_warnings_if_and_only_if(self):
        for seed, expense in self.cases():
            with self.subTest(seed=seed):
                result = allocate(expense)
                warnings = set(result["warnings"])
                self.assertEqual(result["warnings"], sorted(warnings))

                advancer = expense["advancer_id"]
                self.assertEqual(
                    "advancer_not_participant" in warnings,
                    advancer is not None and advancer not in expense["participants"],
                )
                zero_share = any(_parse(t) == 0 for t in result["exact_shares"].values())
                self.assertEqual(
                    "zero_share_participants" in warnings,
                    zero_share and expense["total_vnd"] > 0,
                )

    def test_p9_metamorphic_permutation_changes_nothing(self):
        for seed, expense in self.cases():
            with self.subTest(seed=seed):
                rng = random.Random(seed + 10_000)
                self.assertEqual(allocate(expense), allocate(permuted(expense, rng)))

    def test_p10_p11_errors_are_stable_codes_under_permutation(self):
        broken = 0
        for seed in SEEDS:
            rng = random.Random(seed + 50_000)
            expense = generate_valid_expense(rng)
            if not expense["items"]:
                continue
            expense = dict(expense)
            expense["total_vnd"] = expense["total_vnd"] + 1  # force a mismatch
            broken += 1
            with self.subTest(seed=seed):
                with self.assertRaises(AllocationError) as first:
                    allocate(expense)
                self.assertIn(first.exception.code, ERROR_PRECEDENCE)
                with self.assertRaises(AllocationError) as second:
                    allocate(permuted(expense, random.Random(seed)))
                self.assertEqual(first.exception.code, second.exception.code)
        self.assertGreater(broken, 50)

    def test_boundary_pair_generated_at_runtime(self):
        """Kept out of the golden JSON: repo_guard blocks nine-digit runs."""
        base = {"participants": ["a", "b"], "items": [], "surcharges": [], "discounts": [], "advancer_id": "a"}
        ok = allocate({**base, "total_vnd": MAX_AMOUNT_VND})
        self.assertEqual(sum(ok["allocations"].values()), MAX_AMOUNT_VND)
        with self.assertRaises(AllocationError) as caught:
            allocate({**base, "total_vnd": MAX_AMOUNT_VND + 1})
        self.assertEqual(caught.exception.code, "AMOUNT_TOO_LARGE")


if __name__ == "__main__":
    unittest.main()
