"""The vertical slice must be runnable, and must not be able to go quiet.

## Why

`apps/mobile/tests/e2e/vertical-slice.test.mjs` is the only test in this
repository where both sides of a request are real. Everything else holds one
side fixed and fakes the other: `services/api/tests/api/` runs on a fake
repository, `apps/mobile`'s suite injects a fake fetch, and `check_actor_headers`
and `check_api_contract` compare two files without executing either. A defect
living in the seam -- a body key the client spells differently from the server,
a field the server stopped returning -- is green in all of them.

It ran nowhere. Measured 2026-08-30 at 1649c16:

  - `apps/mobile/package.json`'s `scripts.test` prunes `tests/e2e` by
    construction, so the 55 files it runs are exactly the ones that fake the
    server.
  - `.github/workflows/test.yml`'s mobile job runs that same `npm test`.
  - `scripts/gate.sh` had no stage for it.
  - `grep -rn test:e2e` over every .yml, .sh, .py, .json and .md in the
    repository found one definition in package.json and not one caller. Every
    other hit is a QA report written by hand, and several of those record the
    times nobody ran it: "chua chay", "khong chay trong luot nay".

So these tests hold two lines, and as with the postgres tier the second is the
one that matters:

  - The slice is REACHABLE. `scripts/gate.sh` has an `e2e` stage that delegates
    to `scripts/e2e_slice.sh`, `make e2e` calls the same script, and
    `.github/workflows/test.yml` has a job that calls it too.
  - The slice cannot go QUIET, in two different ways it could:
      * `MOBILE_REQUIRE_E2E=1` turns "no server" from `t.skip` into a failure.
        Without it the runner could provision a stack, fail to reach it, and
        report success.
      * `EXPO_PUBLIC_API_URL` is pinned. `apps/mobile/src/api.ts` falls back to
        `http://localhost:8099`, which on this machine is the shared `make up`
        stack every worktree uses. Measured while writing this: that container
        served 52 routes and this tree renders 58. An unpinned run reports a
        colour about code no reader can identify.

## What this does NOT prove

It does not run the slice -- `make e2e` does that, and its evidence is a count
of passing cases, not this file. The Docker and Node paths are asserted by
reading the script rather than by starting anything, so that this file never
becomes a test that skips when the daemon is down: that is the failure it
exists to refuse. The one test here that executes the runner is written so that
it needs neither Docker nor Node, because every way it can fail to provision is
supposed to end in a non-zero exit.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "e2e_slice.sh"
GATE = REPO_ROOT / "scripts" / "gate.sh"
MAKEFILE = REPO_ROOT / "Makefile"
SLICE = REPO_ROOT / "apps" / "mobile" / "tests" / "e2e" / "vertical-slice.test.mjs"


def _runner_source() -> str:
    return RUNNER.read_text(encoding="utf-8")


def _runner_code() -> str:
    """The runner with comment lines removed.

    Every assertion about what the script *does* has to read this rather than
    the raw text, or a sentence in a comment satisfies a check about behaviour.
    This file is largely prose, so that is not a hypothetical.
    """
    return "\n".join(
        line
        for line in _runner_source().splitlines()
        if not line.lstrip().startswith("#")
    )


class SliceIsWiredIn(unittest.TestCase):
    def test_runner_exists_and_is_executable(self) -> None:
        self.assertTrue(RUNNER.is_file(), f"{RUNNER} không tồn tại")
        self.assertTrue(
            os.access(RUNNER, os.X_OK),
            "scripts/e2e_slice.sh phải chạy được trực tiếp (chmod +x)",
        )

    def test_the_slice_itself_is_still_there(self) -> None:
        # Guard the guard. Every claim below is about running this file; if it
        # were deleted the rest would still pass while nothing ran.
        self.assertTrue(
            SLICE.is_file(),
            f"{SLICE} không còn — không còn gì chứng minh client và server nối được",
        )

    def test_gate_delegates_to_the_runner(self) -> None:
        gate = GATE.read_text(encoding="utf-8")
        body = gate.split("do_e2e()", 1)
        self.assertEqual(len(body), 2, "scripts/gate.sh mất hàm do_e2e")
        stage = body[1].split("\n}", 1)[0]
        self.assertIn(
            "scripts/e2e_slice.sh",
            stage,
            "chặng e2e phải gọi scripts/e2e_slice.sh, không tự chế lệnh riêng",
        )

    def test_make_exposes_the_slice(self) -> None:
        makefile = MAKEFILE.read_text(encoding="utf-8")
        self.assertIn("e2e:", makefile, "Makefile thiếu target e2e")
        self.assertIn(
            "scripts/e2e_slice.sh",
            makefile,
            "target e2e phải gọi scripts/e2e_slice.sh",
        )
        phony = next(
            line for line in makefile.splitlines() if line.startswith(".PHONY")
        )
        self.assertIn("e2e", phony, "e2e phải nằm trong .PHONY")

    def test_npm_test_still_does_not_cover_the_slice(self) -> None:
        """The reason this stage has to exist, asserted rather than remembered.

        If `scripts.test` ever stops pruning `tests/e2e`, the slice runs inside
        the mobile job and a reader could reasonably retire this stage. Until
        then, anybody who assumes `npm test` covers it is wrong, and that
        assumption is exactly how the slice went a week unproven.
        """
        package_json = (REPO_ROOT / "apps" / "mobile" / "package.json").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "tests/e2e -prune",
            package_json,
            "scripts.test không còn cắt tests/e2e — kiểm lại xem chặng e2e còn cần "
            "riêng không, đừng bỏ nó đi mà không đọc",
        )


class RunnerCannotGoQuiet(unittest.TestCase):
    def test_runner_forces_the_require_flag(self) -> None:
        # Without this the slice calls `t.skip` when it cannot reach a server
        # and the run exits 0 -- so the runner would provision a whole stack,
        # fail to reach it, and report success.
        self.assertIn(
            "MOBILE_REQUIRE_E2E=1",
            _runner_code(),
            "runner phải đặt MOBILE_REQUIRE_E2E=1, nếu không 'không có server' "
            "thành bỏ qua và thoát 0",
        )

    def test_the_slice_honours_the_require_flag(self) -> None:
        # The flag is only worth setting if the file reads it. Asserted here
        # because the runner and the slice are owned by different lanes, and
        # the runner's guarantee is only as good as the other half.
        source = SLICE.read_text(encoding="utf-8")
        self.assertIn(
            "MOBILE_REQUIRE_E2E",
            source,
            "lát cắt không còn đọc MOBILE_REQUIRE_E2E — cờ trong runner thành vô nghĩa",
        )

    def test_runner_pins_the_api_url(self) -> None:
        # `src/api.ts` falls back to http://localhost:8099, the shared stack
        # every worktree on this machine uses. A slice aimed there tests
        # whatever was built last.
        self.assertIn(
            "EXPO_PUBLIC_API_URL=",
            _runner_code(),
            "runner phải ghim EXPO_PUBLIC_API_URL vào API nó tự dựng",
        )
        self.assertNotIn(
            "8099",
            _runner_code(),
            "runner không được nhắc tới 8099 — đó là stack dùng chung của cả máy",
        )

    def test_it_refuses_rather_than_passing_when_it_cannot_provision(self) -> None:
        """Run it for real, with a database image that cannot exist.

        Needs neither Docker nor Node: every route to not-provisioning is
        supposed to end non-zero. No Node exits 2, no Docker exits 2, no image
        exits 2. The one answer this must never give is 0, which is what a
        silent skip would look like from the outside.
        """
        env = dict(os.environ)
        env["MOBILE_TEST_POSTGRES_IMAGE"] = "mobile-e2e-image-that-does-not-exist:0"
        result = subprocess.run(
            [str(RUNNER)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertNotEqual(
            result.returncode,
            0,
            "không dựng được stack mà vẫn thoát 0 — đúng lỗi 'bỏ qua đọc thành xanh'"
            f"\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}",
        )


class RunnerCannotTouchAnotherLanesStack(unittest.TestCase):
    """Same objection `scripts/gate.sh` raised against the postgres tier.

    A guessed connection string lands on the shared `mobile-local` database
    every worktree uses, and this runner migrates a schema. It answers by
    construction rather than by promise: it never speaks Compose, so there is
    no project whose volume it could touch.
    """

    def test_runner_never_speaks_compose(self) -> None:
        code = _runner_code()
        for forbidden in ("docker compose", "docker-compose", "COMPOSE_PROJECT_NAME"):
            self.assertNotIn(
                forbidden,
                code,
                f"runner nhắc tới '{forbidden}' — nó có thể chạm vào bộ container "
                "của lane khác",
            )

    def test_runner_always_sets_the_database_url(self) -> None:
        # `app/db/session.py` and `app/db/migrations/env.py` both fall back to
        # the shared dev database on localhost:5432 when MOBILE_DATABASE_URL is
        # unset. Leaving it unset for either the migration or the server would
        # migrate a database five other worktrees are using.
        code = _runner_code()
        self.assertGreaterEqual(
            code.count("MOBILE_DATABASE_URL="),
            2,
            "cả alembic lẫn uvicorn đều phải được đặt MOBILE_DATABASE_URL tường minh; "
            "để trống là trỏ vào database dùng chung của cả máy",
        )

    def test_runner_cleans_up_everything_it_started(self) -> None:
        code = _runner_code()
        self.assertIn(
            "trap cleanup EXIT",
            code,
            "phải dọn kể cả khi bị Ctrl-C — máy này đã có hàng chục container",
        )
        self.assertIn("docker rm -f", code, "cleanup phải thật sự xoá container")
        self.assertIn(
            "kill",
            code,
            "cleanup phải tắt uvicorn — một API sống sót sẽ giữ cổng và trả lời "
            "/healthz cho lượt đo sau",
        )

    def test_runner_publishes_on_loopback_only(self) -> None:
        code = _runner_code()
        self.assertIn(
            "-p 127.0.0.1::5432",
            code,
            "database tạm chỉ được publish trên loopback, và phải để docker chọn cổng trống",
        )
        self.assertIn(
            "--host 127.0.0.1",
            code,
            "API tạm chỉ được nghe trên loopback",
        )


if __name__ == "__main__":
    unittest.main()
