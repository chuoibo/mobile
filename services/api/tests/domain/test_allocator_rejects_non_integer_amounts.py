"""Every đồng slot the allocator reads must refuse `float` and `bool`.

Money law 1 says a sum of đồng is an integer number of đồng -- "no float
anywhere, not even in intermediates". `allocator.py` says so in its own module
docstring. It did not enforce it: `_validate_structure` checked `< 0`, `== 0`
and `> MAX_AMOUNT_VND` and never checked the *shape* of the number at all, so
on `origin/main@bf7cc78` the heart of the product did this:

    total_vnd=True,  item amount_vnd=True   ->  allocations {a: 1, b: 0}

`True` became one đồng, silently, with no error -- the exact hazard
`money._not_an_integer` was written to close, in the one file that actually
divides the money. And a float did not corrupt quietly, it crashed:

    total_vnd=300.5, item amount_vnd=300.5  ->  TypeError from `ranked[:deficit]`

which breaks ADR-0004 section 7.2 property 10: `allocate` raises
`AllocationError` with a code from the closed list, never a bare `TypeError`.

Two gates already on main are both blind here, and for a reason worth writing
down. `test_one_money_check.py` counts *duplicate spellings* of the predicate,
so a place with no predicate at all offers it no shape to count. The ledger
gate walks ledger's own call arguments and never reaches `app/domain/allocator`.
Neither answers the question this file asks, which is not "is the check
copied?" but "is there a check at all?".

WHAT THIS GATE COUNTS, and why the unit resists a later editor:

The đồng slots are not written down here. They are DERIVED from the 41 frozen
golden vectors -- every leaf in a vector's `input` whose key ends in `_vnd`.
A fifth money field cannot enter the allocator contract without golden vectors
carrying it (ADR-0004 makes the corpus the oracle), so the slot list grows by
itself and this gate covers the new field the day it is declared. That is the
unit two earlier counts in this repo converged on only after a hand-written
list and an export-name count each missed something.

The count is derived a SECOND, independent way per vector --
`1 + len(items) + len(surcharges) + len(discounts)` -- and the two derivations
must agree. A walker that quietly returns nothing is the failure mode that
turns a gate into decoration; disagreement is what catches it.

WHAT IT DOES NOT PROVE:

  * It does not cover money slots that never appear in any golden vector. A
    field declared with a `None` default and left out of the corpus is invisible
    to a walker over values -- the same blind spot QA measured on the ledger
    gate (#445, mutation D-B2). The self-check below pins the two-way count so
    the gap stays visible rather than silent.
  * It says nothing about `app/api/` or `app/db/`. Pydantic at the HTTP edge is
    a separate boundary with its own tests; this file is about the domain
    holding on its own, which is the premise the layer split rests on.
"""

from __future__ import annotations

import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.domain.allocator import allocate  # noqa: E402
from app.domain.contract import ERROR_PRECEDENCE, AllocationError  # noqa: E402

GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"

# The code a non-integer đồng amount must produce. Pinned on purpose: a gate
# that accepts "any AllocationError" is satisfied by RECONCILIATION_MISMATCH,
# which is what a float item amount already produced before this fix -- the
# right-code-for-the-wrong-reason trap.
NOT_INTEGER_CODE = "AMOUNT_NOT_INTEGER"


def money_slots(node, path=()):
    """Paths to every `_vnd`-suffixed leaf, found by walking, not by listing."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, dict | list):
                yield from money_slots(value, (*path, key))
            elif key.endswith("_vnd"):
                yield (*path, key)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from money_slots(value, (*path, index))


def replace_at(payload, path, value):
    """Deep copy of `payload` with `path` set to `value`."""
    updated = copy.deepcopy(payload)
    cursor = updated
    for step in path[:-1]:
        cursor = cursor[step]
    cursor[path[-1]] = value
    return updated


def success_vectors():
    for file in sorted(GOLDEN_DIR.glob("*.json")):
        for vector in json.loads(file.read_text(encoding="utf-8")):
            if "expect" in vector:
                yield file.name, vector


class TheWalkerItselfWorks(unittest.TestCase):
    """Without these, a green run below could mean 'safe' or 'walker broken'."""

    def test_it_finds_a_money_key_at_a_depth_it_has_never_seen(self):
        """A fifth slot, nested deeper than anything in the corpus today."""
        payload = {"total_vnd": 1, "rebates": [{"tiers": [{"cap_vnd": 5}]}]}
        self.assertEqual(
            set(money_slots(payload)),
            {("total_vnd",), ("rebates", 0, "tiers", 0, "cap_vnd")},
        )

    def test_it_ignores_keys_that_are_not_money(self):
        payload = {"total_vnd": 1, "item_id": "i1", "shared_by": ["a"], "count": 2}
        self.assertEqual(set(money_slots(payload)), {("total_vnd",)})

    def test_replace_at_does_not_mutate_the_original(self):
        payload = {"items": [{"amount_vnd": 10}]}
        replace_at(payload, ("items", 0, "amount_vnd"), 0.5)
        self.assertEqual(payload["items"][0]["amount_vnd"], 10)


class EveryGoldenVectorExposesItsMoneySlots(unittest.TestCase):
    """Two independent counts of the same thing must agree."""

    def test_walker_agrees_with_the_structural_count(self):
        checked = 0
        for name, vector in success_vectors():
            payload = vector["input"]
            structural = (
                1
                + len(payload["items"])
                + len(payload["surcharges"])
                + len(payload["discounts"])
            )
            with self.subTest(vector["id"], file=name):
                found = list(money_slots(payload))
                self.assertEqual(
                    len(found),
                    structural,
                    f"walker found {found}, structure says {structural} slots",
                )
                self.assertGreater(len(found), 0)
            checked += 1
        self.assertGreater(checked, 0, "no success vectors loaded -- gate disarmed")


class AllocateRefusesNonIntegerAmounts(unittest.TestCase):
    """The measurement that was red before this fix, on every derived slot."""

    def test_the_code_is_in_the_frozen_vocabulary(self):
        self.assertIn(NOT_INTEGER_CODE, ERROR_PRECEDENCE)

    def test_non_integer_before_reconciliation(self):
        """Precedence: a bad shape outranks the totals not adding up.

        Both are wrong at once whenever a single item amount is poisoned, and
        reporting the mismatch would send the reader to look at arithmetic that
        is not the problem.
        """
        payload = {
            "participants": ["a", "b"],
            "total_vnd": 300,
            "items": [{"item_id": "i1", "amount_vnd": 300.5, "shared_by": ["a", "b"]}],
            "surcharges": [],
            "discounts": [],
            "advancer_id": "a",
        }
        with self.assertRaises(AllocationError) as caught:
            allocate(payload)
        self.assertEqual(caught.exception.code, NOT_INTEGER_CODE)

    def test_every_money_slot_of_every_golden_vector_refuses_float_and_bool(self):
        poisons = [
            ("float", lambda original: original + 0.5),
            # A float that equals the integer. This is the sneaky one: it
            # passes every `<`, `==` and `>` test the allocator used to run.
            ("float_whole", float),
            # `isinstance(True, int)` is true in Python, so an ordinary integer
            # check lets `True` through as one đồng.
            ("bool_true", lambda original: True),
            ("bool_false", lambda original: False),
        ]
        checked = 0
        for name, vector in success_vectors():
            payload = vector["input"]
            for slot in money_slots(payload):
                original = payload
                for step in slot:
                    original = original[step]
                for label, poison in poisons:
                    checked += 1
                    with self.subTest(
                        vector["id"],
                        file=name,
                        slot=".".join(map(str, slot)),
                        poison=label,
                    ):
                        with self.assertRaises(AllocationError) as caught:
                            allocate(replace_at(payload, slot, poison(original)))
                        self.assertEqual(caught.exception.code, NOT_INTEGER_CODE)
        self.assertGreater(checked, 0, "no slots poisoned -- gate disarmed")


if __name__ == "__main__":
    unittest.main()
