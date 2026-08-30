"""The demo-data gate has to bite, and has to bite for the right reason.

These tests never touch a database. `psycopg.connect` is replaced with a fake
whose row counts the test chooses, so the cases below can describe a demo
machine in any state -- including states that would take half an hour to build
for real -- without going near the shared Postgres every lane is working on.

The one thing a fake cannot speak for is whether the gate reads a real machine
correctly, and that was measured by hand instead, both directions, recorded in
the pull request: red on the actual demo machine on 8099 (8 đợt thu, 0 buổi đi)
and green on a freshly seeded stack on 8299. A fake that agrees with itself is
not evidence, so the numbers in `COMPLETE` below are the ones the real seeded
machine reported, not numbers invented here.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "scripts" / "check_demo_data.py"

# What `make demo` actually produced on a clean stack on 2026-08-30, read back
# out of Postgres. Kept here as the definition of "complete" so a test that goes
# green is agreeing with a machine, not with its own assumptions.
COMPLETE = {"outings": 3, "batches": 3, "members": 7, "expenses": 5}

# The state the demo machine was really in when this gate was written.
BROKEN = {"outings": 0, "batches": 8, "members": 9, "expenses": 22}

GROUP_ID = "3423b032-9bbd-4ecf-809b-4ff4ede2d2b2"


def load_gate():
    spec = importlib.util.spec_from_file_location("check_demo_data", GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    """Answers the four counts and the group lookup, and nothing else.

    Routing is by substring of the SQL rather than by call order: a gate that
    starts asking its questions in a different order should not silently start
    reading the batch count as the outing count.
    """

    def __init__(self, counts, group_id=GROUP_ID, raise_on=None):
        self.counts = counts
        self.group_id = group_id
        self.raise_on = raise_on

    def execute(self, sql, params=None):
        if self.raise_on and self.raise_on in sql:
            raise RuntimeError(f'relation "{self.raise_on.lower()}" does not exist')
        if "FROM contexts" in sql:
            return FakeResult(None if self.group_id is None else (self.group_id,))
        for table, key in (
            ("FROM outings", "outings"),
            ("FROM collection_batches", "batches"),
            ("FROM memberships", "members"),
            ("FROM expenses", "expenses"),
        ):
            if table in sql:
                return FakeResult((self.counts[key],))
        raise AssertionError(f"câu SQL không nằm trong kịch bản: {sql}")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class DemoDataGate(unittest.TestCase):
    def setUp(self):
        self.gate = load_gate()

    def run_gate(self, connection, argv=None):
        with mock.patch("psycopg.connect", return_value=connection):
            return self.gate.main(argv or [])

    # -- the two answers that matter -------------------------------------

    def test_complete_dataset_passes(self):
        self.assertEqual(self.run_gate(FakeConnection(COMPLETE)), 0)

    def test_the_real_broken_machine_fails(self):
        """The exact shape the demo machine was in, and it must be exit 1."""
        self.assertEqual(self.run_gate(FakeConnection(BROKEN)), 1)

    # -- each count on its own, so a pass cannot lean on the others -------

    def test_each_missing_count_is_caught_alone(self):
        for key in COMPLETE:
            with self.subTest(key=key):
                counts = dict(COMPLETE)
                counts[key] = 0
                self.assertEqual(self.run_gate(FakeConnection(counts)), 1)

    def test_overbuilt_is_caught_not_just_underbuilt(self):
        """`>= 1` would have called the eight-round machine healthy."""
        for key in COMPLETE:
            with self.subTest(key=key):
                counts = dict(COMPLETE)
                counts[key] = COMPLETE[key] + 5
                self.assertEqual(self.run_gate(FakeConnection(counts)), 1)

    def test_missing_group_fails(self):
        self.assertEqual(self.run_gate(FakeConnection(COMPLETE, group_id=None)), 1)

    # -- could not run is never a pass, and never a failure either --------

    def test_old_schema_is_cannot_run_not_a_difference(self):
        """Regression: the first version let this escape as a traceback + exit 1.

        A stack built before the `outings` table existed answers the first count
        with UndefinedTable. Reporting that as 1 tells the reader the demo data
        is wrong, and sends them to reseed a machine whose schema is the actual
        problem.
        """
        connection = FakeConnection(COMPLETE, raise_on="FROM outings")
        self.assertEqual(self.run_gate(connection), 2)

    def test_unreachable_database_is_cannot_run(self):
        with mock.patch("psycopg.connect", side_effect=RuntimeError("timeout")):
            self.assertEqual(self.gate.main([]), 2)

    # -- the anti-drift property this gate is built on -------------------

    def test_expectations_track_the_seed_script(self):
        """Numbers come from `seed_demo_data.py`, so they cannot go stale.

        If the builder grows a fourth trip, this gate must expect four without
        anybody editing it. A hardcoded 3 would keep passing while the demo
        quietly lost a trip -- the failure this repository keeps finding.
        """
        expected = self.gate.expectations()
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import seed_demo_data as seed

        from datetime import UTC, datetime

        trips = seed.outings(datetime.now(UTC))
        self.assertEqual(expected["outings"], len(trips))
        self.assertEqual(expected["batches"], len(trips))
        self.assertEqual(expected["members"], len(seed.PEOPLE))
        self.assertEqual(expected["expenses"], sum(len(t["expenses"]) for t in trips))

    def test_a_fourth_trip_moves_the_expectation(self):
        """The drift guard, exercised rather than asserted about."""
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import seed_demo_data as seed

        real = seed.outings

        def one_more(now):
            trips = list(real(now))
            extra = dict(trips[-1])
            extra["expenses"] = list(extra["expenses"])
            trips.append(extra)
            return trips

        with mock.patch.object(seed, "outings", one_more):
            expected = self.gate.expectations()
        self.assertEqual(
            expected["outings"],
            len(real(__import__("datetime").datetime.now(__import__("datetime").UTC)))
            + 1,
        )

    # -- the message has to be actionable --------------------------------

    def test_failure_names_the_screens_that_go_empty(self):
        """A count nobody can act on is a number, not a gate."""
        import io
        from contextlib import redirect_stderr

        buffer = io.StringIO()
        with redirect_stderr(buffer):
            self.run_gate(FakeConnection(BROKEN))
        message = buffer.getvalue()
        self.assertIn("F13", message)
        self.assertIn("RỖNG", message)
        # and it must not send the reader to the command that wipes the shared DB
        self.assertIn("hỏi cả đội trước", message)


if __name__ == "__main__":
    unittest.main()
