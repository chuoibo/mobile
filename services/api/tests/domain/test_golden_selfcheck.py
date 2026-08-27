"""Check the golden corpus is internally consistent, without any allocator.

WHAT THIS PROVES, and what it does not.

It recomputes exact shares, the rounding ranking and the warning set from the
recorded input, following ADR-0004 sections 2, 4 and 6 transcribed by hand. So
it catches arithmetic slips and internal inconsistency in the corpus.

It does NOT prove the corpus author read the contract correctly. This file and
the vectors have the same author, so a consistent misreading of, say, the order
in which discounts compose would appear identically in both and stay green.
That gap is covered by a different artifact: an independent hand recomputation
by the reviewer, recorded with a signature. Neither layer alone is a gate.

Rewritten twice under review:
  ADR4-05 -- the first version checked only `allocation == floor + gainer` and
  the *count* of gainers, so mutants that moved the rounding dong to the wrong
  participant passed.
  V2-05 -- the second version still could not see composition order: Codex built
  a self-consistent mutant that applied the global discount before the item
  discount, recomputed every expected value coherently, and it passed clean.
"""

from __future__ import annotations

import json
import math
import pathlib
import re
import unittest
from fractions import Fraction

GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"

WARNING_VOCABULARY = (
    "advancer_not_participant",
    "proportional_fallback_to_even",
    "zero_share_participants",
)

ERROR_CODES = {
    "NO_PARTICIPANTS", "INVALID_PARTICIPANT_ID", "DUPLICATE_PARTICIPANT",
    "INVALID_ENTITY_ID", "DUPLICATE_ENTITY_ID", "NEGATIVE_AMOUNT", "ZERO_AMOUNT",
    "AMOUNT_TOO_LARGE", "INVALID_KIND", "INVALID_MODE", "INVALID_SCOPE",
    "SCOPE_TARGET_MISMATCH", "EMPTY_SHARED_BY", "DUPLICATE_SHARED_BY",
    "UNKNOWN_PARTICIPANT", "UNKNOWN_ITEM",
    "DISCOUNT_EXCEEDS_ITEM", "DISCOUNT_EXCEEDS_BASE",
    "RECONCILIATION_MISMATCH",
}


def load_vectors():
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        for vector in json.loads(path.read_text(encoding="utf-8")):
            yield path.name, vector


def parse_fraction(text: str) -> Fraction:
    numerator, denominator = text.split("/")
    return Fraction(int(numerator), int(denominator))


def recompute_exact_shares(vector) -> dict[str, Fraction]:
    """Recompute exact shares from the input, per ADR-0004 section 2.

    Five stages, transcribed from the contract prose. Written to catch the
    composition-order mutant of blocker V2-05, which stayed self-consistent
    across every other check in this file.
    """
    data = vector["input"]
    participants = data["participants"]
    n = len(participants)
    total = Fraction(data["total_vnd"])

    # Decision 2: EVEN_SPLIT is the one named special case.
    if not data["items"] and not data["surcharges"] and not data["discounts"]:
        return {p: total / n for p in participants}

    # Stage 1 -- item shares, net of item-scoped discounts, split evenly.
    item_net = {i["item_id"]: Fraction(i["amount_vnd"]) for i in data["items"]}
    for discount in data["discounts"]:
        if discount["scope"] == "item":
            item_net[discount["item_id"]] -= discount["amount_vnd"]

    base = {p: Fraction(0) for p in participants}
    for item in data["items"]:
        share = item_net[item["item_id"]] / len(item["shared_by"])
        for participant in item["shared_by"]:
            base[participant] += share

    # Stage 2 -- global discounts, proportional. Decision 22 guards B == 0.
    total_base = sum(base.values(), Fraction(0))
    global_discount = sum(
        Fraction(d["amount_vnd"])
        for d in data["discounts"]
        if d["scope"] == "global_proportional"
    )
    if total_base > 0:
        factor = (total_base - global_discount) / total_base
        base = {p: v * factor for p, v in base.items()}

    # Stage 3 -- surcharges.
    basis = sum(base.values(), Fraction(0))
    extra = {p: Fraction(0) for p in participants}
    for surcharge in data["surcharges"]:
        amount = Fraction(surcharge["amount_vnd"])
        if surcharge["mode"] == "even" or basis == 0:
            # Decision 15: no proportional basis means fall back to even.
            for participant in participants:
                extra[participant] += amount / n
        else:
            for participant in participants:
                extra[participant] += amount * base[participant] / basis

    # Stage 4.
    return {p: base[p] + extra[p] for p in participants}


def expected_rounding_gainers(vector) -> tuple[str, ...]:
    """Recompute the gainer tuple from ADR-0004 section 4, not from any allocator.

    Sort key, ascending: (-remainder, advancer_rank, utf8 bytes of the id).
    Python compares bytes lexicographically on unsigned octets and orders a
    shorter prefix first, which is exactly the ordering ADR-0004 section 6 fixes.
    """
    data = vector["input"]
    expect = vector["expect"]
    participants = data["participants"]
    advancer = data["advancer_id"]

    exact = {p: parse_fraction(t) for p, t in expect["exact_shares"].items()}
    floors = {p: math.floor(v) for p, v in exact.items()}
    deficit = data["total_vnd"] - sum(floors.values())

    def sort_key(participant: str):
        remainder = exact[participant] - floors[participant]
        is_advancer = advancer is not None and participant == advancer
        return (-remainder, 0 if is_advancer else 1, participant.encode("utf-8"))

    ranked = sorted(participants, key=sort_key)
    return tuple(ranked[:deficit])


def expected_warnings(vector) -> tuple[str, ...]:
    """Recompute the warning set from ADR-0004 decisions 7, 15, 19, 21 and 22."""
    data = vector["input"]
    expect = vector["expect"]
    warnings = set()

    advancer = data["advancer_id"]
    if advancer is not None and advancer not in data["participants"]:
        warnings.add("advancer_not_participant")

    # Decision 21: exact share zero, and only when the bill itself is non-zero.
    if data["total_vnd"] > 0 and any(
        parse_fraction(t) == 0 for t in expect["exact_shares"].values()
    ):
        warnings.add("zero_share_participants")

    # Decisions 15 and 22: a proportional surcharge with no proportional basis.
    item_net = {}
    for item in data["items"]:
        item_net[item["item_id"]] = item["amount_vnd"]
    for discount in data["discounts"]:
        if discount["scope"] == "item":
            item_net[discount["item_id"]] -= discount["amount_vnd"]
    base = sum(item_net.values())
    global_discount = sum(
        d["amount_vnd"] for d in data["discounts"] if d["scope"] == "global_proportional"
    )
    has_proportional = any(s["mode"] == "proportional" for s in data["surcharges"])
    if has_proportional and base - global_discount == 0:
        warnings.add("proportional_fallback_to_even")

    return tuple(sorted(warnings))


def permutation_signature(data):
    """Order-insensitive view of an input, for permutation-pair checks."""
    return (
        tuple(sorted(data["participants"])),
        data["total_vnd"],
        tuple(sorted(
            (i["item_id"], i["amount_vnd"], tuple(sorted(i["shared_by"])))
            for i in data["items"]
        )),
        tuple(sorted(
            (s["surcharge_id"], s["kind"], s["amount_vnd"], s["mode"])
            for s in data["surcharges"]
        )),
        tuple(sorted(
            (d["discount_id"], d["amount_vnd"], d["scope"], d["item_id"])
            for d in data["discounts"]
        )),
        data["advancer_id"],
    )


class GoldenCorpusSelfCheck(unittest.TestCase):
    def setUp(self):
        self.vectors = list(load_vectors())
        self.assertGreater(len(self.vectors), 0, "golden corpus is empty")
        self.success = [(n, v) for n, v in self.vectors if "expect" in v]
        self.errors = [(n, v) for n, v in self.vectors if "expect_error" in v]

    # ---- corpus hygiene -------------------------------------------------

    def test_ids_are_unique(self):
        ids = [v["id"] for _, v in self.vectors]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_vector_declares_success_or_error(self):
        for name, vector in self.vectors:
            with self.subTest(vector["id"], file=name):
                self.assertNotEqual("expect" in vector, "expect_error" in vector)
                if "expect_error" in vector:
                    self.assertIn(vector["expect_error"], ERROR_CODES)

    def test_amounts_stay_below_repo_guard_digit_threshold(self):
        # scripts/repo_guard.py blocks runs of nine or more digits. Extreme
        # values belong in generated property tests, never in stored literals.
        for name, vector in self.vectors:
            with self.subTest(vector["id"], file=name):
                for number in _all_integers(vector):
                    self.assertLess(abs(number), 100_000_000)

    # ---- arithmetic -----------------------------------------------------

    def test_exact_shares_sum_to_total(self):
        for name, vector in self.success:
            with self.subTest(vector["id"], file=name):
                total = sum(
                    (parse_fraction(v) for v in vector["expect"]["exact_shares"].values()),
                    Fraction(0),
                )
                self.assertEqual(total, Fraction(vector["input"]["total_vnd"]))

    def test_allocations_sum_to_total(self):
        for name, vector in self.success:
            with self.subTest(vector["id"], file=name):
                self.assertEqual(
                    sum(vector["expect"]["allocations"].values()),
                    vector["input"]["total_vnd"],
                )

    def test_allocation_equals_floor_plus_rounding_gain(self):
        for name, vector in self.success:
            with self.subTest(vector["id"], file=name):
                expect = vector["expect"]
                gainers = expect["rounding_gainers"]
                self.assertEqual(len(gainers), len(set(gainers)), "nobody may gain twice")
                for participant, allocated in expect["allocations"].items():
                    exact = parse_fraction(expect["exact_shares"][participant])
                    self.assertEqual(
                        allocated,
                        math.floor(exact) + (1 if participant in gainers else 0),
                    )

    # ---- the check that was missing (Codex ADR4-05) ---------------------

    def test_rounding_gainers_equal_the_recomputed_ranking(self):
        """ADR-0004 property 7: the exact tuple, not merely the right count.

        Without this, a mutant that hands the rounding dong to the wrong
        participant passes every other check in this file.
        """
        for name, vector in self.success:
            with self.subTest(vector["id"], file=name):
                self.assertEqual(
                    tuple(vector["expect"]["rounding_gainers"]),
                    expected_rounding_gainers(vector),
                )

    def test_exact_shares_equal_the_recomputed_pipeline(self):
        """ADR-0004 section 2: the five stages, in order.

        This is the check that sees composition order. Without it, applying the
        global discount before the item discount produces a corpus that is
        wrong yet passes every conservation and ranking check (blocker V2-05).
        """
        for name, vector in self.success:
            with self.subTest(vector["id"], file=name):
                recorded = {
                    p: parse_fraction(t)
                    for p, t in vector["expect"]["exact_shares"].items()
                }
                self.assertEqual(recorded, recompute_exact_shares(vector))

    def test_warnings_are_exactly_the_recomputed_set(self):
        """ADR-0004 property 8: if and only if, not merely a subset."""
        for name, vector in self.success:
            with self.subTest(vector["id"], file=name):
                self.assertEqual(
                    tuple(vector["expect"]["warnings"]),
                    expected_warnings(vector),
                )

    def test_warnings_use_the_closed_sorted_vocabulary(self):
        for name, vector in self.success:
            with self.subTest(vector["id"], file=name):
                warnings = vector["expect"]["warnings"]
                self.assertLessEqual(set(warnings), set(WARNING_VOCABULARY))
                self.assertEqual(warnings, sorted(warnings))
                self.assertEqual(len(warnings), len(set(warnings)))

    # ---- structural -----------------------------------------------------

    def test_deficit_matches_number_of_gainers(self):
        for name, vector in self.success:
            with self.subTest(vector["id"], file=name):
                expect = vector["expect"]
                floors = sum(
                    math.floor(parse_fraction(v)) for v in expect["exact_shares"].values()
                )
                deficit = vector["input"]["total_vnd"] - floors
                self.assertEqual(deficit, len(expect["rounding_gainers"]))
                self.assertGreaterEqual(deficit, 0)
                self.assertLess(deficit, max(1, len(vector["input"]["participants"])))

    def test_participant_sets_line_up(self):
        for name, vector in self.success:
            with self.subTest(vector["id"], file=name):
                participants = set(vector["input"]["participants"])
                expect = vector["expect"]
                self.assertEqual(set(expect["allocations"]), participants)
                self.assertEqual(set(expect["exact_shares"]), participants)
                self.assertLessEqual(set(expect["rounding_gainers"]), participants)

    def test_exact_shares_are_never_negative(self):
        for name, vector in self.success:
            with self.subTest(vector["id"], file=name):
                for text in vector["expect"]["exact_shares"].values():
                    self.assertGreaterEqual(parse_fraction(text), 0)

    def test_reconciliation_holds_for_every_successful_vector(self):
        for name, vector in self.success:
            with self.subTest(vector["id"], file=name):
                data = vector["input"]
                if not data["items"] and not data["surcharges"] and not data["discounts"]:
                    continue  # EVEN_SPLIT, decision 2
                listed = (
                    sum(i["amount_vnd"] for i in data["items"])
                    + sum(s["amount_vnd"] for s in data["surcharges"])
                    - sum(d["amount_vnd"] for d in data["discounts"])
                )
                self.assertEqual(listed, data["total_vnd"])

    # ---- permutation pairs ---------------------------------------------

    def test_permutation_pairs_expect_the_same_outcome(self):
        """ADR-0004 property 11: reordering elements must not change the code."""
        groups = {}
        for name, vector in self.vectors:
            base = re.sub(r"[a-z]$", "", vector["id"])
            groups.setdefault(base, []).append(vector)
        checked = 0
        for base, members in groups.items():
            if len(members) < 2:
                continue
            checked += 1
            with self.subTest(base):
                signatures = {permutation_signature(m["input"]) for m in members}
                self.assertEqual(len(signatures), 1, "not permutations of each other")
                outcomes = {
                    m.get("expect_error") or json.dumps(m["expect"], sort_keys=True)
                    for m in members
                }
                self.assertEqual(len(outcomes), 1)
        self.assertGreater(checked, 0, "corpus must contain at least one permutation pair")

    # ---- coverage -------------------------------------------------------

    def test_corpus_covers_the_cases_the_contract_calls_mandatory(self):
        ids = {v["id"] for _, v in self.vectors}
        for required in ("G22", "G23", "G24", "G25", "G26"):
            self.assertIn(required, ids)
        self.assertGreaterEqual(len(self.errors), 15)


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
