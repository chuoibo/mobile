"""The PostgreSQL tier must be runnable without being told anything.

## Why

`services/api/tests/postgres` is 224 cases and it is the only place any SQL,
index, view or trigger in this repository is executed. CLAUDE.md's own table
says so: the API tier runs on a fake repository and proves "khong bat ky cau
SQL, index, view, trigger nao".

It ran almost nowhere. In CI it reported 147 skips and 0 runs. Locally
`scripts/gate.sh postgres` printed BO QUA on every invocation, because the
stage refused to start without `MOBILE_TEST_DATABASE_URL` and nothing set it.
A skip is not a pass -- and this is the third time this repository has been bitten
by the same shape, after a detector with no browser returning `[]` and exit 0.

So these tests hold two lines, and the second is the one that matters:

  - The stage is REACHABLE. `scripts/gate.sh` delegates to
    `scripts/postgres_tier.sh`, `make test-db` calls it, and the stage no
    longer demands a connection string before it will do anything.
  - The stage cannot go QUIET. `MOBILE_REQUIRE_POSTGRES_TESTS=1` is what turns
    the conftest's `pytest.skip` into `pytest.fail`; without it an unreachable
    database exits 0 having proved nothing, which is the exact defect being
    removed. `test_unreachable_database_is_red_not_skipped` runs the script for
    real to check that, and needs no Docker to do it.

## What this does NOT prove

It does not run the tier -- `make test-db` does that, and its evidence is a
count of passing cases, not this file. It does not prove the provisioned
container matches production tuning; it does not, deliberately (`fsync=off`).
The Docker path is asserted by reading the script rather than by starting a
container, so that this file itself never becomes a test that skips when the
daemon is down -- the failure it exists to prevent.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "postgres_tier.sh"
GATE = REPO_ROOT / "scripts" / "gate.sh"
MAKEFILE = REPO_ROOT / "Makefile"


class RunnerIsWiredIn(unittest.TestCase):
    def test_runner_exists_and_is_executable(self) -> None:
        self.assertTrue(RUNNER.is_file(), f"{RUNNER} không tồn tại")
        self.assertTrue(
            os.access(RUNNER, os.X_OK),
            "scripts/postgres_tier.sh phải chạy được trực tiếp (chmod +x)",
        )

    def test_gate_delegates_to_the_runner(self) -> None:
        gate = GATE.read_text(encoding="utf-8")
        body = gate.split("do_postgres()", 1)
        self.assertEqual(len(body), 2, "scripts/gate.sh mất hàm do_postgres")
        stage = body[1].split("\n}", 1)[0]
        self.assertIn(
            "scripts/postgres_tier.sh",
            stage,
            "chặng postgres phải gọi scripts/postgres_tier.sh, không tự chế lệnh riêng",
        )

    def test_gate_no_longer_refuses_without_a_connection_string(self) -> None:
        # The old prerequisite returned 1 -- a skip -- whenever the variable was
        # unset, which was every run. Reaching the provisioning path is the
        # whole change; a revert to the old form would put the stage back to
        # BO QUA and this is what would notice.
        gate = GATE.read_text(encoding="utf-8")
        # assertTrue rather than assertIn on purpose: assertIn prints the whole
        # haystack, and gate.sh is 20 KB. A gate whose red output has to be
        # scrolled past is one people learn to skim.
        self.assertTrue(
            'MOBILE_TEST_DATABASE_URL:-}" ] && return 0' in gate,
            "chặng postgres phải đi tiếp khi chưa có URL, thay vì bỏ qua",
        )

    def test_make_exposes_the_tier(self) -> None:
        makefile = MAKEFILE.read_text(encoding="utf-8")
        self.assertIn("test-db:", makefile, "Makefile thiếu target test-db")
        self.assertIn(
            "scripts/postgres_tier.sh",
            makefile,
            "target test-db phải gọi scripts/postgres_tier.sh",
        )
        phony = next(
            line for line in makefile.splitlines() if line.startswith(".PHONY")
        )
        self.assertIn("test-db", phony, "test-db phải nằm trong .PHONY")


class RunnerCannotGoQuiet(unittest.TestCase):
    def test_runner_forces_the_require_flag(self) -> None:
        # Without this variable the conftest calls pytest.skip when it cannot
        # reach a database, and the run exits 0. That is the failure mode the
        # whole file exists to remove, so it is asserted rather than trusted.
        self.assertTrue(
            "MOBILE_REQUIRE_POSTGRES_TESTS=1" in RUNNER.read_text(encoding="utf-8"),
            "runner phải đặt MOBILE_REQUIRE_POSTGRES_TESTS=1, nếu không tầng này bỏ qua và thoát 0",
        )

    def test_unreachable_database_is_red_not_skipped(self) -> None:
        # Runs the script for real against a URL that cannot work. No Docker and
        # no database are needed: the point is that the answer is a failure and
        # not a silent success. A skip here would exit 0 and read as green.
        env = dict(os.environ)
        env["MOBILE_TEST_DATABASE_URL"] = "sqlite:///not-postgres.db"
        result = subprocess.run(
            [str(RUNNER), "-q"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertNotEqual(
            result.returncode,
            0,
            "database không dùng được mà vẫn thoát 0 — đúng lỗi 'bỏ qua đọc thành xanh'"
            f"\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}",
        )


class RunnerCannotTouchAnotherLanesStack(unittest.TestCase):
    """The reason `scripts/gate.sh` used to refuse to provision at all.

    Its objection was that a guessed connection string would land on the shared
    `mobile-local` database every worktree uses. The runner answers it by
    construction rather than by promise: it never speaks Compose, so there is no
    project whose volume it could remove.
    """

    def test_runner_never_speaks_compose(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")
        code = "\n".join(
            line for line in source.splitlines() if not line.lstrip().startswith("#")
        )
        for forbidden in ("docker compose", "docker-compose", "COMPOSE_PROJECT_NAME"):
            self.assertNotIn(
                forbidden,
                code,
                f"runner nhắc tới '{forbidden}' — nó có thể chạm vào bộ container của lane khác",
            )

    def test_runner_removes_its_container(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")
        self.assertTrue(
            "trap cleanup EXIT" in source,
            "phải dọn container kể cả khi bị Ctrl-C — máy này đã có hàng chục container",
        )
        self.assertTrue("docker rm -f" in source, "cleanup phải thật sự xoá container")

    def test_runner_publishes_on_loopback_only(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")
        self.assertTrue(
            "-p 127.0.0.1::5432" in source,
            "database tạm chỉ được publish trên loopback, và phải để docker chọn cổng trống",
        )


if __name__ == "__main__":
    unittest.main()
