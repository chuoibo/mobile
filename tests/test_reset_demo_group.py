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

import contextlib
import importlib.util
import io
import os
import re
import sys
import unittest
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

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
        self.assertEqual(len(reset.IMMUTABLE_TABLES), 9)

    def test_only_deletes_from_idempotency_keys(self):
        deletes = re.findall(r"DELETE FROM (\w+)", RESET.read_text())
        self.assertEqual(deletes, ["idempotency_keys"])


class TheDatabaseItTouchesIsTheOneYouNamed(unittest.TestCase):
    """The script must go to the database the operator named, and say which.

    Written from a real accident on 2026-08-31. A lane ran

        MOBILE_DATABASE_URL=...@127.0.0.1:<cổng riêng>/mobile \\
          python3 scripts/reset_demo_group.py --yes

    and the script renamed the demo group on the SHARED database at port 5432.
    `MOBILE_DATABASE_URL` was read nowhere -- `seed_demo_data.py`,
    `app/db/session.py`, `app/db/migrations/env.py` and `e2e_slice.sh` all
    honour it, this script alone did not -- and nothing was printed, so the
    only trace was a key count ("xoá 0 / 1225 key") that reads as plausible
    unless you already suspect the target is wrong.

    These cases drive `main()` with `psycopg.connect` intercepted, so what they
    record is the DSN the script actually reaches for. Reading the source for
    the string `MOBILE_DATABASE_URL` would pass just as well on a script that
    mentions the variable and then ignores it.

    `os.environ` is replaced wholesale rather than updated: this machine
    frequently has `MOBILE_DATABASE_URL` exported already, and a case whose
    verdict depends on the ambient shell is not a case.
    """

    ENV_DSN = "postgresql+psycopg://mobile:mat-khau-gia@127.0.0.1:5449/mobile"
    ENV_HOSTPORT = "127.0.0.1:5449"
    CLI_DSN = "postgresql://mobile:mat-khau-gia@127.0.0.1:5479/mobile"
    SECRET = "mat-khau-gia"
    SHARED = ":5432/"

    def drive(self, argv: list[str], environ: dict[str, str]):
        """Run `main()` up to the connection and report where it aimed."""

        reset = load_reset()
        reached: list[str] = []

        def refuse(dsn, **kwargs):
            reached.append(dsn)
            # Fixed text: a message carrying the DSN would hand the redaction
            # case below its answer for free.
            raise RuntimeError("ca này không nối, chỉ ghi lại đích")

        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(reset.psycopg, "connect", refuse),
            mock.patch.object(sys, "argv", ["reset_demo_group.py", *argv]),
            mock.patch.dict(os.environ, environ, clear=True),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            code = reset.main()

        self.assertEqual(
            code,
            reset.EXIT_CANNOT_RUN,
            "ca này cố tình chặn ở lúc nối; mã khác nghĩa là nó chưa từng thử nối",
        )
        self.assertEqual(len(reached), 1, "phải thử nối đúng một lần")
        return reached[0], out.getvalue() + err.getvalue()

    def test_env_var_decides_the_target(self):
        dsn, _ = self.drive([], {"MOBILE_DATABASE_URL": self.ENV_DSN})
        self.assertIn(
            self.ENV_HOSTPORT,
            dsn,
            "đặt MOBILE_DATABASE_URL rồi mà script vẫn đi chỗ khác",
        )
        self.assertNotIn(self.SHARED, dsn, "nó vừa mở database DÙNG CHUNG của cả đội")

    def test_env_var_is_translated_for_libpq(self):
        """Everyone who exports this variable exports the SQLAlchemy spelling.

        `docker-compose.yml`, `e2e_slice.sh` and every `tests/postgres` fixture
        write `postgresql+psycopg://`. libpq rejects that scheme, so reading
        the variable without `seed.psycopg_dsn()` swaps a silent wrong database
        for a loud dead one -- better, but still not the fix.
        """

        dsn, _ = self.drive([], {"MOBILE_DATABASE_URL": self.ENV_DSN})
        self.assertNotIn("+psycopg", dsn)
        self.assertTrue(dsn.startswith("postgresql://"), dsn)

    def test_explicit_dsn_still_wins_over_the_env_var(self):
        dsn, _ = self.drive(
            ["--dsn", self.CLI_DSN], {"MOBILE_DATABASE_URL": self.ENV_DSN}
        )
        self.assertIn(":5479/", dsn, "--dsn gõ tay phải thắng biến môi trường")

    def test_saying_nothing_still_reaches_the_local_stack(self):
        """`make demo-reset` passes neither, and must keep working.

        The demo machine's stack publishes Postgres on the host's 5432, so the
        fallback is load-bearing. A fix that made the variable mandatory would
        trade this bug for a broken target.
        """

        dsn, _ = self.drive([], {})
        self.assertIn(self.SHARED, dsn)

    def test_it_prints_the_target_before_it_touches_anything(self):
        """The accident's real cost was that nothing on screen named the DSN."""

        _, printed = self.drive([], {"MOBILE_DATABASE_URL": self.ENV_DSN})
        self.assertIn(
            self.ENV_HOSTPORT,
            printed,
            "chạy xong không có dòng nào nói nó vừa mở database nào — "
            "đó chính là lý do lần đụng nhầm không ai nhận ra",
        )
        self.assertIn("MOBILE_DATABASE_URL", printed, "phải nói đích lấy từ đâu")

    def test_the_printed_target_carries_no_password(self):
        """It is printed on every run, and printed things end up in logs."""

        _, printed = self.drive([], {"MOBILE_DATABASE_URL": self.ENV_DSN})
        self.assertNotIn(self.SECRET, printed)


if __name__ == "__main__":
    unittest.main()
