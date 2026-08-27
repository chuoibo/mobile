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
    """Apply the global discount BEFORE the item discount, self-consistently.

    Codex blocker V2-05 built this one and proved the previous self-check passed
    it clean. Every derived value below is recomputed to match the wrong order,
    so conservation, floor-plus-gainer, ranking, warnings and reconciliation all
    still hold. Only recomputing the pipeline from the input can see it.

    Sum still equals 92000, so `test_exact_shares_sum_to_total` cannot catch it.
    """
    vector["expect"]["exact_shares"] = {
        "a": "177325/6",
        "b": "177325/6",
        "c": "98675/3",
    }
    vector["expect"]["allocations"] = {"a": 29554, "b": 29554, "c": 32892}
    vector["expect"]["rounding_gainers"] = ["c"]
    vector["expect"]["warnings"] = []


def mutate_g11_split_even_surcharge_only_among_eaters(vector):
    """Decision 14 read backwards: split the even surcharge only among people
    who actually ate, instead of among every participant.

    Made fully self-consistent under blocker V3-02 -- the previous version left
    the warning list stale, so it could have been caught for the wrong reason.
    Here a and b absorb the whole 10000 shipping fee, c drops to an exact share
    of zero, the sum still equals 100000, there is no deficit, and the
    zero_share_participants warning is added exactly as decision 21 requires.
    Only recomputing stage 3 from the input can see that this is wrong.
    """
    vector["expect"]["exact_shares"] = {"a": "50000/1", "b": "50000/1", "c": "0/1"}
    vector["expect"]["allocations"] = {"a": 50000, "b": 50000, "c": 0}
    vector["expect"]["rounding_gainers"] = []
    vector["expect"]["warnings"] = ["zero_share_participants"]


MUTANTS = [
    ("G02", mutate_g02_move_dong_off_the_advancer),
    ("G16", mutate_g16_use_vietnamese_collation_instead_of_bytes),
    ("G21", mutate_g21_let_the_advancer_beat_a_larger_remainder),
    ("G15", mutate_g15_drop_the_fallback_warning),
    ("G25", mutate_g25_give_the_dong_to_a_zero_remainder_advancer),
    ("G22", mutate_g22_swap_composition_order),
    ("G11", mutate_g11_split_even_surcharge_only_among_eaters),
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
