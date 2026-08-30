"""The demo-group reset has to free the name, clear the right keys, and stop there.

No database is touched. What these cases pin down is the part a database run
would not show you anyway: that the key list is *derived* from the fixture
rather than copied out of it, and that the one DELETE in the script cannot
wander into the ledger.

Measured for real, both directions, on an isolated stack (dodemo, port 5449) --
recorded in the pull request rather than here, because a test that agrees with
its own fake is not evidence that the script works on Postgres.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
import uuid
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
RESET = SCRIPTS / "reset_demo_group.py"
SEED = SCRIPTS / "seed_demo_data.py"

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)

# Keyed on an id the server mints during the run, so a later run cannot collide
# with them and the reset has no business deleting them.
DYNAMIC_PREFIXES = {"receipt", "receipt-call"}


def load_reset():
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("reset_demo_group", RESET)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KeysAreDerivedFromTheFixture(unittest.TestCase):
    """The list must not be able to fall behind the fixture silently."""

    def test_a_fourth_outing_moves_the_key_set(self):
        reset = load_reset()
        before = reset.fixture_write_slugs(NOW)

        real_outings = reset.seed.outings
        extra = dict(real_outings(NOW)[0])
        extra["slug"] = "thang-9"
        extra["expenses"] = [dict(e) for e in extra["expenses"]]
        for index, expense in enumerate(extra["expenses"]):
            expense["slug"] = f"mon-moi-{index}"
        try:
            reset.seed.outings = lambda now: [*real_outings(now), extra]
            after = reset.fixture_write_slugs(NOW)
        finally:
            reset.seed.outings = real_outings

        self.assertGreater(
            len(after),
            len(before),
            "thêm một chuyến vào fixture mà danh sách key không đổi — "
            "nghĩa là nó đang chép cứng, và lần reset sau sẽ xoá thiếu",
        )
        self.assertIn("outing:thang-9", after)
        self.assertIn("expense:mon-moi-0", after)

    def test_an_eighth_person_moves_the_key_set(self):
        reset = load_reset()
        before = reset.fixture_write_slugs(NOW)

        real_people = reset.seed.PEOPLE
        newcomer = uuid.uuid5(reset.seed.DEMO_NAMESPACE, "person:moi")
        try:
            reset.seed.PEOPLE = [*real_people, (newcomer, "Mới")]
            after = reset.fixture_write_slugs(NOW)
        finally:
            reset.seed.PEOPLE = real_people

        self.assertEqual(len(after) - len(before), 4, "mỗi người có 4 lượt ghi")
        for prefix in ("person", "invite", "accept", "bank"):
            self.assertIn(f"{prefix}:{newcomer}", after)

    def test_every_static_write_in_the_fixture_is_covered(self):
        """A hand-written list does not know when it has gone stale.

        This reads the fixture's own source for `idempotency_key(...)` call
        sites and demands the reset account for every static family it finds.
        Add a new kind of write to the seed and forget it here, and the next
        reset under-clears -- which surfaces as the same HTTP 422 the whole
        script exists to remove, one table further along.
        """

        reset = load_reset()
        source = SEED.read_text()
        found = set(re.findall(r'idempotency_key\(\s*f?"([a-z-]+)(?::|")', source))
        self.assertTrue(
            found, "không đọc được call site nào — regex hỏng, không phải fixture"
        )

        covered = {slug.split(":", 1)[0] for slug in reset.fixture_write_slugs(NOW)}
        missing = (found - DYNAMIC_PREFIXES) - covered
        self.assertEqual(
            missing,
            set(),
            f"fixture ghi thêm loại key mới mà reset chưa biết: {sorted(missing)}",
        )

    def test_dynamic_keys_are_left_alone(self):
        reset = load_reset()
        covered = {slug.split(":", 1)[0] for slug in reset.fixture_write_slugs(NOW)}
        self.assertEqual(covered & DYNAMIC_PREFIXES, set())


class TheRenameHasToFreeTheLookup(unittest.TestCase):
    def test_archive_name_no_longer_matches_the_fixture(self):
        reset = load_reset()
        self.assertNotEqual(reset.archive_name(NOW), reset.seed.GROUP_NAME)

    def test_archive_name_says_do_not_demo_this(self):
        reset = load_reset()
        self.assertIn("KHÔNG dùng để demo", reset.archive_name(NOW))


class TheLedgerIsOffLimits(unittest.TestCase):
    def test_never_writes_to_an_append_only_table(self):
        reset = load_reset()
        self.assertEqual(reset.TABLES_WRITTEN & reset.IMMUTABLE_TABLES, set())

    def test_the_ledger_table_is_actually_in_the_guarded_set(self):
        """Guard the guard: an empty IMMUTABLE_TABLES would satisfy the test above."""

        reset = load_reset()
        self.assertIn("confirmed_allocations", reset.IMMUTABLE_TABLES)
        self.assertIn("expense_versions", reset.IMMUTABLE_TABLES)
        self.assertEqual(len(reset.IMMUTABLE_TABLES), 10)

    def test_only_deletes_from_idempotency_keys(self):
        deletes = re.findall(r"DELETE FROM (\w+)", RESET.read_text())
        self.assertEqual(deletes, ["idempotency_keys"])


if __name__ == "__main__":
    unittest.main()
