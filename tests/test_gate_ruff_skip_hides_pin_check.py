"""The empty-scope skip must not swallow `do_ruff`'s ruff== pin assertion.

## What this is

Two changes landed on main within an hour of each other, touched the same
function, and merged without a textual conflict. Together they opened a hole
neither one opens alone.

`#206` put an assertion at the top of `do_ruff`: `services/api/requirements-dev.txt`
must carry a `ruff==` pin, because `test.yml`'s lint job installs that exact
version. Its own comment says why it was worth adding -- delete the pin and
"CI is the only thing that notices, which, while Actions cannot start a job,
means nothing notices."

`#210` then made `check_prereq ruff` skip the stage when no Python file is in
scope, which is right on its own terms and is what
tests/test_gate_ruff_empty_scope.py pins.

But `check_prereq` runs *before* the stage body. When it skips, `do_ruff` never
executes, so #206's pin assertion never executes either. Deleting the pin is an
edit to a `.txt` file: it changes no Python, so the scope is empty, so the
stage skips, so the check built to catch exactly that deletion does not run.

## Measured, same edit both times: delete the ruff== pin, touch no .py

    main @ 23455e7   (#206 in, #210 not yet)
      không có dòng ruff== trong services/api/requirements-dev.txt
      HỎNG    ruff (0s)                                          exit 1

    main @ 7e1ed4b   (both in)
      BỎ QUA  ruff -- nhánh không đổi file Python nào so với origin/main
      ĐẠT 0   HỎNG 0   BỎ QUA 1                                  exit 2

The second run is not merely quieter. Its stated reason is wrong: the branch
did change a file the ruff stage cares about, and the gate reports that it did
not. Under `--strict` the run is still red, but red with a diagnosis that sends
the reader to the wrong file.

## The xfail(strict=True) marker is gone -- this is a live guard now

It was filed xfail rather than red for the reason tests/qa/rd-qa-37 gave: a
permanently red suite is one everybody learns to scroll past, and `scripts/`
belongs to the devops lane, not to QA. Strict made the marker self-clearing --
the day `check_prereq` stopped hiding the pin assertion this XPASSed, strict
turned that into a failure, and whoever fixed it was told to delete the marker
and keep the guard.

That day is now. `check_prereq ruff` consults `ruff_pin()` before it is allowed
to skip, so the case below passes on its own terms and the marker has been
removed rather than the case weakened. Deleting the marker is the second half
of the fix: leaving it on would have turned this XPASS into a red main.

The marker was verified to be a real gate rather than a decorative line before
it came off, by applying the fix and taking it away again:

    1 xfailed                     # main @ 9564684, untouched
    1 xpassed -> failed (strict)  # + pin checked before the skip decision
    1 xfailed                     # fix reverted, tree clean again

## What this proves and what it does not

It proves that the pin assertion is reachable when the stage runs, and
unreachable when the empty-scope skip fires. It does not propose which side
should change: moving the pin check into `check_prereq`, or narrowing the skip,
are both open to the owning lane. It says nothing about whether the pinned
version and the local ruff agree -- `do_ruff` deliberately only warns there.

It also does not re-prove #210. The skip itself is correct and
tests/test_gate_ruff_empty_scope.py already holds it; the canary below exists
so this file cannot be satisfied by simply undoing that.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# F401, an unused import: in ruff's default rule set, so the fixture needs no
# pyproject.toml of its own.
DIRTY_PY = "import os\n"

PIN_MISSING = "không có dòng ruff=="
SKIPPED_FOR_EMPTY_SCOPE = "nhánh không đổi file Python nào"


class GateRuffSkipHidesPinCheck(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        if shutil.which("ruff") is None:
            self.skipTest("ruff is not installed")

        self.repo = pathlib.Path(tempfile.mkdtemp(prefix="gate-ruff-pin-"))
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

        # Only the two scripts the stage touches: copying the tree drags this
        # checkout's own history in and makes the fixture unreadable.
        (self.repo / "scripts").mkdir(parents=True)
        for name in ("gate.sh", "ruff_changed.sh"):
            shutil.copy2(REPO_ROOT / "scripts" / name, self.repo / "scripts" / name)

        (self.repo / "services" / "api").mkdir(parents=True)
        self.requirements = self.repo / "services" / "api" / "requirements-dev.txt"
        self.requirements.write_text("ruff==0.9.2\n", encoding="utf-8")

        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "gate@test")
        self.git("config", "user.name", "gate")
        # core.hooksPath is inherited inside a worktree; point it at nothing so
        # what is measured is the gate and not the pre-commit hook.
        self.git("config", "core.hooksPath", str(self.repo / "no-such-hooks"))
        (self.repo / "README.md").write_text("nen\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "nen")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.git("update-ref", "refs/remotes/origin/main", self.base)

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.repo, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise AssertionError(
                f"git {' '.join(args)} -> {result.returncode}\n{result.stderr}"
            )
        return result.stdout

    def commit_file(self, name: str, body: str, message: str) -> None:
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        self.git("add", name)
        self.git("commit", "-q", "-m", message)

    def delete_the_pin(self) -> None:
        """The edit under test: remove the pin, touching no Python file."""
        self.requirements.write_text("pytest==8.3.3\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "go pin ruff")

    def run_gate(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.repo / "scripts" / "gate.sh"), *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            timeout=600,
        )

    # --- the canaries -----------------------------------------------------
    #
    # Without these, the case below could be satisfied by a stage that never
    # skips at all -- which would be undoing #210, not fixing this.

    def test_the_pin_assertion_works_when_the_stage_actually_runs(self):
        """A missing pin IS caught when something Python is in scope. This is
        the half that proves the assertion exists and bites."""
        self.delete_the_pin()
        self.commit_file("mo_dun.py", DIRTY_PY, "them python")

        result = self.run_gate("ruff")
        combined = result.stdout + result.stderr
        self.assertIn(PIN_MISSING, combined, combined)
        self.assertEqual(result.returncode, 1, combined)

    def test_the_skip_still_happens_when_the_pin_is_present(self):
        """#210's behaviour, unchanged. Pinned here so a fix for this file
        cannot simply delete the skip."""
        self.commit_file("docs/ghi-chu.md", "chi la tai lieu\n", "them tai lieu")

        result = self.run_gate("ruff")
        combined = result.stdout + result.stderr
        self.assertIn(SKIPPED_FOR_EMPTY_SCOPE, combined, combined)

    # --- the hole ---------------------------------------------------------

    # Was xfail(strict=True) until check_prereq stopped deciding the skip from
    # the changed-Python-file list alone. The assertion is unchanged; only the
    # marker came off.
    def test_a_deleted_ruff_pin_is_not_hidden_by_the_empty_scope_skip(self):
        self.delete_the_pin()

        result = self.run_gate("ruff")
        combined = result.stdout + result.stderr

        self.assertIn(
            PIN_MISSING,
            combined,
            "the pin was deleted and the gate did not say so -- it answered "
            "'no Python changed' instead, which sends the reader to the wrong "
            "file:\n" + combined,
        )
        self.assertEqual(result.returncode, 1, combined)


if __name__ == "__main__":
    unittest.main()
