"""Run the hand-computed golden corpus against the production allocator.

These 41 vectors were computed by hand from ADR-0004 before any allocator
existed, and independently recomputed by the reviewer. They are the corpus the
implementation was never allowed to influence.
"""

from __future__ import annotations

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.domain.allocator import allocate  # noqa: E402
from app.domain.contract import AllocationError  # noqa: E402

GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"


def load_vectors():
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        for vector in json.loads(path.read_text(encoding="utf-8")):
            yield path.name, vector


class GoldenCorpus(unittest.TestCase):
    def setUp(self):
        self.vectors = list(load_vectors())
        self.assertGreater(len(self.vectors), 0)

    def test_success_vectors_match_exactly(self):
        checked = 0
        for name, vector in self.vectors:
            if "expect" not in vector:
                continue
            checked += 1
            with self.subTest(vector["id"], file=name, note=vector.get("note", "")):
                result = allocate(vector["input"])
                expect = vector["expect"]
                self.assertEqual(result["allocations"], expect["allocations"])
                self.assertEqual(result["exact_shares"], expect["exact_shares"])
                self.assertEqual(result["rounding_gainers"], expect["rounding_gainers"])
                self.assertEqual(result["warnings"], expect["warnings"])
        self.assertEqual(checked, 23)

    def test_error_vectors_raise_the_declared_code(self):
        checked = 0
        for name, vector in self.vectors:
            if "expect_error" not in vector:
                continue
            checked += 1
            with self.subTest(vector["id"], file=name, note=vector.get("note", "")):
                with self.assertRaises(AllocationError) as caught:
                    allocate(vector["input"])
                self.assertEqual(caught.exception.code, vector["expect_error"])
        self.assertEqual(checked, 18)

    def test_allocations_always_sum_to_the_total(self):
        """Spec section 4, invariant 1. No exceptions, ever."""
        for name, vector in self.vectors:
            if "expect" not in vector:
                continue
            with self.subTest(vector["id"], file=name):
                result = allocate(vector["input"])
                self.assertEqual(
                    sum(result["allocations"].values()), vector["input"]["total_vnd"]
                )

    def test_every_allocation_is_an_int_never_a_float(self):
        """Spec section 4, invariant 2. `isinstance(True, int)` is also True,
        so bools are rejected explicitly rather than slipping through."""
        for name, vector in self.vectors:
            if "expect" not in vector:
                continue
            with self.subTest(vector["id"], file=name):
                for amount in allocate(vector["input"])["allocations"].values():
                    self.assertIsInstance(amount, int)
                    self.assertNotIsInstance(amount, bool)


if __name__ == "__main__":
    unittest.main()
