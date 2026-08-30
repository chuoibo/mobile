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
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _workflow_step_exec import FILE, WorkflowStepSandbox  # noqa: E402
from _workflow_steps import run_steps  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "postgres_tier.sh"
GATE = REPO_ROOT / "scripts" / "gate.sh"
MAKEFILE = REPO_ROOT / "Makefile"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "postgres-repository.yml"

# A URL nothing can connect to, and deliberately still PostgreSQL: the conftest
# rejects a non-PostgreSQL backend before it ever dials, so a sqlite URL would
# make these tests pass for the wrong reason. Port 1 is never a database.
UNREACHABLE_POSTGRES = "postgresql+psycopg://mobile:x@127.0.0.1:1/none"


def _looks_like_pytest(inv) -> bool:
    """Does this invocation start a pytest run?

    Read off the argv the shell actually built, so continuations, variables and
    `cd` are already applied. It is still a judgement about names, and so the
    weaker of the two halves below: `python -c "import pytest; pytest.main()"`
    would not be recognised. The half that carries the weight is
    `test_the_workflow_actually_executes_the_runner`, which asks which FILE ran
    and cannot be fooled by spelling at all.
    """
    if os.path.basename(inv.name) in ("pytest", "py.test"):
        return True
    args = list(inv.args)
    return any(
        flag == "-m" and value in ("pytest", "py.test")
        for flag, value in zip(args, args[1:])
    )


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

    ## Why this runs the steps instead of reading them

    This is the third round of one mistake, and the first two are worth naming
    because the third looks nothing like them until you write it down.

    Round one asked `assertIn("scripts/postgres_tier.sh", <whole file>)`.
    Round two (`#271`) found what that misses -- write the drift back in as

        run: |
          # was: scripts/postgres_tier.sh -q
          cd services/api && python3 -m pytest tests/postgres -q

    and the assertion is satisfied by the COMMENT while the step runs the
    narrow tier again. The diagnosis was exactly right: "a substring over a
    whole file cannot tell a command from a mention of one." The repair
    narrowed the search from the file to the `run:` body and kept the
    substring -- but a comment inside a `run:` block is part of that body, so
    every word of the diagnosis stayed true one level down.

    Round three is `bug-095404`, which measured what survived: five shapes,
    five green. One ran nothing at all and named the runner only in a comment.
    The other four wrote the same inline `pytest tests/postgres` with a shell
    line-continuation, with one more `cd`, with a `./` prefix, and with the
    path in a variable -- none of which a per-line regex can see, because in
    each of them it is the SHELL that assembles the command, at run time.

    So this class stops reading the workflow and runs it. `_workflow_step_exec`
    executes each `run:` body in a throwaway tree where every command is a
    recorder, and reports what was actually invoked and from which directory.
    Two facts follow that no amount of pattern-matching could establish:

      - The runner's identity comes from THE FILE THAT RAN, not from how it was
        spelled. `scripts/postgres_tier.sh`, `./scripts/postgres_tier.sh`,
        `bash scripts/postgres_tier.sh` and `$RUNNER` all record the same file;
        a comment naming it records nothing.
      - Arguments are resolved against the directory the command really ran in,
        so `cd services/api/tests && pytest postgres` and `cd services/api &&
        pytest ./tests/postgres` and `pytest "$TIER"` are one fact, not three
        spellings.

    The cost is that this executes shell out of a workflow file on a laptop.
    `_workflow_step_exec` defuses it -- empty `PATH`, `HOME` and cwd inside a
    temporary tree, every script replaced by a stub -- and says so at length.
    """

    LIVE_TIER_TREES = ("services/api/tests/postgres", "tests/qa")
    """The trees `scripts/postgres_tier.sh` exists to run as one unit.

    A step naming either of them is writing the second definition of the live
    tier that this class exists to prevent -- that is how the sixteen cases
    under `tests/qa/` came to run nowhere.
    """

    RUNNER_REL = "scripts/postgres_tier.sh"

    @classmethod
    def setUpClass(cls) -> None:
        cls._sandbox = WorkflowStepSandbox()
        cls._executed: dict[str, list] | None = None

    @classmethod
    def tearDownClass(cls) -> None:
        cls._sandbox.close()

    def _postgres_workflow_steps(self) -> list:
        steps = [s for s in run_steps() if s.workflow == WORKFLOW.name]
        # run_steps() raises rather than returning empty, but it cannot know
        # this particular workflow was expected -- a rename would leave the
        # list legitimately empty and every assertion below vacuously true.
        self.assertNotEqual(
            steps,
            [],
            f"không đọc được bước `run:` nào từ {WORKFLOW.name} — "
            "phép kiểm dưới đây sẽ đúng một cách rỗng tuếch",
        )
        return steps

    def _executed_steps(self) -> list:
        """(step, invocations) for every `run:` step of the workflow.

        Run once per class: the sandbox is a stub tree, so a step's answer
        cannot change between two calls, and the pip step in this workflow has
        no reason to be replayed for each assertion.
        """
        if type(self)._executed is None:
            type(self)._executed = [
                (step, self._sandbox.run(step.body, step.working_directory))
                for step in self._postgres_workflow_steps()
            ]
        return type(self)._executed

    def _ran_the_runner(self, invocations: list) -> bool:
        return any(
            inv.kind == FILE and inv.name == self.RUNNER_REL for inv in invocations
        )

    def _reaches_the_live_tier(self, inv) -> list:
        """Arguments of `inv` that point into a tree the runner owns."""
        hits = []
        for arg in inv.args:
            resolved = inv.resolved(arg)
            for tree in self.LIVE_TIER_TREES:
                if resolved == tree or resolved.startswith(tree + "/"):
                    hits.append(f"{arg} -> {resolved}")
        return hits

    def test_the_measuring_instrument_answers_both_ways(self) -> None:
        """Before believing either verdict below, check the instrument.

        A sandbox that recorded nothing would report "the runner never ran" for
        a healthy workflow, and one that recorded indiscriminately would report
        a violation for every step. Neither failure is visible from the result
        alone, so both directions are forced here on synthetic bodies.

        The dirty body is deliberately the HEAVIEST shape this class claims to
        cover, not the most convenient one: a comment naming the runner, a
        variable holding the path, a `cd` two levels deep, and a
        line-continuation splitting the command -- all four evasions of
        `bug-095404` stacked into one step. A canary run on the easy shape
        would license conclusions about the hard ones it never touched.
        """
        dirty = (
            "# was: scripts/postgres_tier.sh -q\n"
            "TIER=postgres\n"
            "cd services/api/tests && python3 -m pytest \\\n"
            '  "$TIER" -q'
        )
        clean = "bash ./scripts/postgres_tier.sh -q"

        dirty_invocations = self._sandbox.run(dirty)
        self.assertFalse(
            self._ran_the_runner(dirty_invocations),
            "máy đo nói bước KHÔNG chạy runner đã chạy nó — nó đang đọc chữ "
            f"trong comment\n{[str(i) for i in dirty_invocations]}",
        )
        self.assertNotEqual(
            [h for inv in dirty_invocations for h in self._reaches_the_live_tier(inv)],
            [],
            "máy đo không thấy `pytest` trỏ vào tầng live dù bốn hình dạng né "
            "được xếp chồng trong một bước — mọi số 0 dưới đây là số 0 của một "
            f"máy đo chết\n{[str(i) for i in dirty_invocations]}",
        )

        clean_invocations = self._sandbox.run(clean)
        self.assertTrue(
            self._ran_the_runner(clean_invocations),
            "máy đo không nhận ra runner khi nó thật sự chạy — cổng sẽ đỏ với "
            f"mọi cách viết hợp lệ\n{[str(i) for i in clean_invocations]}",
        )
        self.assertEqual(
            [h for inv in clean_invocations for h in self._reaches_the_live_tier(inv)],
            [],
            "máy đo tố một bước hợp lệ — cổng này sẽ bị tắt trong một tuần"
            f"\n{[str(i) for i in clean_invocations]}",
        )

    def test_the_workflow_actually_executes_the_runner(self) -> None:
        """Not "names the runner" -- executes it.

        This is the half that catches all five shapes of `bug-095404` at once,
        including the one that ran nothing at all, because in every one of them
        the file `scripts/postgres_tier.sh` is never reached.
        """
        executed = self._executed_steps()
        calling = [step for step, invs in executed if self._ran_the_runner(invs)]
        self.assertNotEqual(
            calling,
            [],
            "chạy hết các bước `run:` của postgres-repository.yml mà "
            "scripts/postgres_tier.sh KHÔNG hề được thực thi — nhắc tên nó "
            "trong một comment không phải là gọi nó, và CI với cổng máy này "
            "đang định nghĩa 'tầng live' theo hai cách"
            "\n--- những gì các bước thật sự chạy ---\n"
            + "\n".join(
                f"[{step.label}]\n  "
                + ("\n  ".join(str(i) for i in invs) or "(không chạy lệnh nào)")
                for step, invs in executed
            ),
        )

    def test_no_step_reaches_the_live_tier_by_itself(self) -> None:
        """The other half: delegating is only one edit away from being undone.

        Asserted on the argv the shell actually built, so the four spellings
        `bug-095404` used are the same fact here. A step that runs pytest at
        all is included even when it names no path, because pytest with no
        target is a third definition of the tier -- the widest one.
        """
        offenders = []
        for step, invocations in self._executed_steps():
            for inv in invocations:
                if inv.kind == FILE and inv.name == self.RUNNER_REL:
                    continue  # arguments handed TO the runner are the runner's
                hits = self._reaches_the_live_tier(inv)
                if _looks_like_pytest(inv):
                    hits.append("chạy pytest trực tiếp")
                if hits:
                    offenders.append(f"[{step.label}] {inv}  <- {', '.join(hits)}")
        self.assertEqual(
            offenders,
            [],
            "một bước tự chạy tầng live thay vì gọi runner — đó là hai định "
            "nghĩa của 'tầng live' trở lại, và cây tests/qa không nằm trong "
            "định nghĩa thứ hai\n" + "\n".join(offenders),
        )

    def test_no_step_of_this_workflow_is_conditional(self) -> None:
        """A step behind `if:` may never run, and nothing here can tell.

        The sandbox executes a body regardless of its condition, so
        `if: ${{ false }}` on the runner's step would leave every assertion
        above green while CI ran nothing -- the same class of defect as the
        five shapes, reached through YAML instead of through shell.

        Nothing in this repository evaluates GitHub expressions, and a gate
        that guessed would be worse than one that refuses. So this is the
        refusal: a condition anywhere in this workflow is CHƯA KẾT LUẬN ĐƯỢC,
        reported as a failure rather than folded into a pass.
        """
        conditional = [
            f"{s.label}: if: {s.condition}"
            for s in self._postgres_workflow_steps()
            if s.condition
        ]
        # Job-level `if:` sits at four spaces, above the `steps:` list, so the
        # step parser never sees it. Matching the key here is not the mistake
        # this class was written about: `if` is a declarative YAML key with one
        # spelling, not a shell command a comment can imitate.
        text = WORKFLOW.read_text(encoding="utf-8")
        jobs = text.split("\njobs:", 1)[-1]
        conditional += [
            f"job-level: {line.strip()}"
            for line in jobs.splitlines()
            if re.match(r"^    if:", line)
        ]
        self.assertEqual(
            conditional,
            [],
            "postgres-repository.yml có `if:` — phép kiểm ở trên chạy thân "
            "bước bất kể điều kiện, nên nó KHÔNG kết luận được là CI có chạy "
            "tầng live hay không. Đây là 'chưa biết', không phải 'đạt'."
            f"\n{conditional}",
        )


if __name__ == "__main__":
    unittest.main()
