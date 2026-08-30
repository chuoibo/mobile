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

So these tests hold three lines, and the last two are the ones that matter:

  - The stage is REACHABLE. `scripts/gate.sh` delegates to
    `scripts/postgres_tier.sh`, `make test-db` calls it, and the stage no
    longer demands a connection string before it will do anything.
  - The stage REACHES EVERY LIVE CASE, not just the ones under
    `services/api/tests/postgres`. Three lanes put live cases under
    `tests/qa/` instead, and until `bug-082455` no stage of any gate ran those
    with a database. See `LiveCasesOutsideTestsPostgresAlsoRun` below for the
    measurement.
  - The stage cannot go QUIET. `MOBILE_REQUIRE_POSTGRES_TESTS=1` is what turns
    the conftest's `pytest.skip` into `pytest.fail`; without it an unreachable
    database exits 0 having proved nothing, which is the exact defect being
    removed. `test_unreachable_database_is_red_not_skipped` runs the script for
    real to check that, and needs no Docker to do it. A skip arriving by any
    other route -- a `skipif`, an `importorskip`, a marker somebody adds
    tomorrow -- is caught by `test_a_run_that_only_skipped_is_not_a_pass`,
    which does not care where the skip came from.

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
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "postgres_tier.sh"
GATE = REPO_ROOT / "scripts" / "gate.sh"
MAKEFILE = REPO_ROOT / "Makefile"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "postgres-repository.yml"

# A URL nothing can connect to, and deliberately still PostgreSQL: the conftest
# rejects a non-PostgreSQL backend before it ever dials, so a sqlite URL would
# make these tests pass for the wrong reason. Port 1 is never a database.
UNREACHABLE_POSTGRES = "postgresql+psycopg://mobile:x@127.0.0.1:1/none"


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


class LiveCasesOutsideTestsPostgresAlsoRun(unittest.TestCase):
    """`tests/qa/` holds live cases too, and no gate stage ever ran them.

    Measured on main at 9590e51, and again at bef0524 after `#263` added two
    more:

        cd services/api
        python3 -m pytest ../../tests/qa -q      -> 69 passed, 18 skipped, 2 xfailed
        ... with the two variables set           -> 85 passed, 4 xfailed

    Sixteen cases and two xfail pins about who owns money, who is in a group
    and what a guest link may open, none of which had ever executed anywhere.
    `grep -c tests/qa scripts/postgres_tier.sh scripts/gate.sh` answered 0 and
    0, and the count settled it: the stage ran 306 cases, which is exactly what
    `tests/postgres` collects on its own.

    Three lanes each believed their case was guarding something. A skip exits
    0, so all three readings were of the same green.
    """

    # The three files that carry `pytest.mark.postgres` under tests/qa today.
    # Named rather than discovered on purpose: a discovery loop that finds
    # nothing passes, which is the shape being removed here. If a lane deletes
    # one of these, this list is where the deletion has to be argued.
    LIVE_QA_FILES = (
        "tests/qa/qa-tt-0011/test_split_tra_tien_cho_nguoi_la_postgres.py",
        "tests/qa/rd-qa-13/test_link_ton_dong_van_nang_quyen.py",
        "tests/qa/rd-qa-40/test_dinh_danh_nguoi_tu_than_request.py",
    )

    def _collect(self) -> subprocess.CompletedProcess[str]:
        """What the runner would execute, asked of the runner itself.

        `--collect-only` is passed through to pytest, which reaches collection
        without instantiating a single fixture -- so the unreachable URL above
        is never dialled and this needs neither Docker nor a database. Reading
        the node ids the real invocation produces is the difference between
        proving the runner covers the tree and proving somebody typed its name
        into a comment.
        """
        env = dict(os.environ)
        env["MOBILE_TEST_DATABASE_URL"] = UNREACHABLE_POSTGRES
        return subprocess.run(
            [str(RUNNER), "--collect-only", "-q"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )

    def test_the_runner_collects_the_live_cases_under_tests_qa(self) -> None:
        result = self._collect()
        missing = [f for f in self.LIVE_QA_FILES if f not in result.stdout]
        self.assertEqual(
            missing,
            [],
            "runner không thu thập ca tầng live nào dưới tests/qa — chúng sẽ bỏ qua "
            "trên mọi lần chạy cổng, và bỏ qua thoát 0"
            f"\n--- stdout ---\n{result.stdout[-4000:]}"
            f"\n--- stderr ---\n{result.stderr[-2000:]}",
        )

    def test_the_runner_still_collects_the_repository_tier(self) -> None:
        # The other half of the same claim. Adding a tree must not replace one.
        result = self._collect()
        self.assertIn(
            "tests/postgres/",
            result.stdout,
            "runner thôi thu thập tests/postgres — tầng repository là lý do nó tồn tại"
            f"\n--- stdout ---\n{result.stdout[-4000:]}",
        )

    def test_a_run_that_only_skipped_is_not_a_pass(self) -> None:
        """The anti-regression check the bug report asked for.

        `MOBILE_REQUIRE_POSTGRES_TESTS=1` only converts the ONE skip that
        `tests/postgres/conftest.py` raises. Every other route to a skip --
        `skipif`, `importorskip`, a marker added tomorrow -- still exits 0, and
        `0 skipped` is the only thing that separates "ran" from "could not
        build anything to run".

        The canary forces that state through a pytest plugin instead of by
        editing a test file: nothing in the tree is touched, so this cannot
        leave a mutation behind, and skipped cases never reach fixture setup so
        no database is needed.
        """
        plugin = (
            '"""Skip every collected case: a run that proves nothing."""\n'
            "\n"
            "import pytest\n"
            "\n"
            "\n"
            "def pytest_collection_modifyitems(items):\n"
            "    for item in items:\n"
            '        item.add_marker(pytest.mark.skip(reason="canary"))\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "canary_skip_everything.py").write_text(
                plugin, encoding="utf-8"
            )
            env = dict(os.environ)
            env["MOBILE_TEST_DATABASE_URL"] = UNREACHABLE_POSTGRES
            env["PYTHONPATH"] = tmp + os.pathsep + env.get("PYTHONPATH", "")
            result = subprocess.run(
                [str(RUNNER), "-q", "-p", "canary_skip_everything"],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=600,
            )
        self.assertNotEqual(
            result.returncode,
            0,
            "mọi ca đều bỏ qua mà runner vẫn thoát 0 — đó là 'xanh vì không chạy gì'"
            f"\n--- stdout ---\n{result.stdout[-4000:]}"
            f"\n--- stderr ---\n{result.stderr[-2000:]}",
        )


class WorkflowAndRunnerCannotDrift(unittest.TestCase):
    """One definition of what the live tier is, not two.

    The workflow used to spell the tier out itself (`pytest tests/postgres
    -q`), so widening the tier locally left CI narrower with nothing to notice.
    `tests/test_gate_covers_every_inline_step.py` pins the step's bytes and
    asks for a re-review when they change, which catches drift in one
    direction; delegating removes the direction entirely.
    """

    def test_the_workflow_runs_the_same_runner(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "scripts/postgres_tier.sh",
            workflow,
            "postgres-repository.yml phải gọi scripts/postgres_tier.sh, "
            "nếu không CI và cổng máy này định nghĩa 'tầng live' theo hai cách",
        )


if __name__ == "__main__":
    unittest.main()
