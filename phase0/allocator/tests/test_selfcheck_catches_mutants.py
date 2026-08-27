"""Prove the golden self-check has teeth.

Codex blocker ADR4-05 showed the first self-check passed mutants that moved the
rounding dong to the wrong participant: it verified `allocation == floor +
gainer` and the *count* of gainers, but never recomputed the ranking. A test
suite that cannot fail on a wrong answer is not a gate.

Each mutant below is a corruption of a hand-computed vector that a plausible
misreading of ADR-0004 would produce. Every one must make the self-check fail.
"""

from __future__ import annotations

import copy
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve()
GOLDEN_DIR = HERE.parents[1] / "golden"
SELFCHECK = HERE.parent / "test_golden_selfcheck.py"


def mutate_g02_move_dong_off_the_advancer(vector):
    vector["expect"]["allocations"].update({"a": 33334, "b": 33333})
    vector["expect"]["rounding_gainers"] = ["a"]


def mutate_g16_use_vietnamese_collation_instead_of_bytes(vector):
    vector["expect"]["allocations"].update({"z": 1, "á": 2})
    vector["expect"]["rounding_gainers"] = ["á"]


def mutate_g21_let_the_advancer_beat_a_larger_remainder(vector):
    vector["expect"]["allocations"].update({"a": 6, "b": 5, "c": 4})
    vector["expect"]["rounding_gainers"] = ["a", "c"]


def mutate_g15_drop_the_fallback_warning(vector):
    vector["expect"]["warnings"] = []


def mutate_g25_give_the_dong_to_a_zero_remainder_advancer(vector):
    vector["expect"]["allocations"].update({"a": 50, "c": 1})
    vector["expect"]["rounding_gainers"] = ["c"]


def mutate_g22_swap_composition_order(vector):
    # Applying the global discount before the item discount changes the shares.
    vector["expect"]["exact_shares"]["c"] = "229499/7"
    vector["expect"]["exact_shares"]["a"] = "207250/7"


MUTANTS = [
    ("G02", mutate_g02_move_dong_off_the_advancer),
    ("G16", mutate_g16_use_vietnamese_collation_instead_of_bytes),
    ("G21", mutate_g21_let_the_advancer_beat_a_larger_remainder),
    ("G15", mutate_g15_drop_the_fallback_warning),
    ("G25", mutate_g25_give_the_dong_to_a_zero_remainder_advancer),
    ("G22", mutate_g22_swap_composition_order),
]


def load_corpus():
    return {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(GOLDEN_DIR.glob("*.json"))
    }


def run_selfcheck_against(corpus) -> int:
    workspace = pathlib.Path(tempfile.mkdtemp())
    try:
        (workspace / "golden").mkdir()
        (workspace / "tests").mkdir()
        for name, vectors in corpus.items():
            (workspace / "golden" / name).write_text(
                json.dumps(vectors, ensure_ascii=False, indent=1), encoding="utf-8"
            )
        shutil.copy(SELFCHECK, workspace / "tests" / "selfcheck.py")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(workspace / "tests" / "selfcheck.py"), "-q"],
            capture_output=True,
            text=True,
        )
        return result.returncode
    finally:
        shutil.rmtree(workspace)


class SelfCheckIsAGate(unittest.TestCase):
    def test_unmutated_corpus_passes(self):
        self.assertEqual(run_selfcheck_against(load_corpus()), 0)

    def test_every_mutant_is_caught(self):
        for vector_id, mutate in MUTANTS:
            with self.subTest(vector_id, mutation=mutate.__name__):
                corpus = copy.deepcopy(load_corpus())
                found = False
                for vectors in corpus.values():
                    for vector in vectors:
                        if vector["id"] == vector_id:
                            mutate(vector)
                            found = True
                self.assertTrue(found, f"{vector_id} missing from corpus")
                self.assertNotEqual(
                    run_selfcheck_against(corpus),
                    0,
                    f"self-check did not catch the {vector_id} mutant",
                )


if __name__ == "__main__":
    unittest.main()
