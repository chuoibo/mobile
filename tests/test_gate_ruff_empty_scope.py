"""The gate must not report ĐẠT for a ruff run that checked zero files.

## The hole this closes

`scripts/ruff_changed.sh` is a ratchet: it lints the Python files a change
touches, and when a change touches none it prints "no Python files changed --
nothing for ruff to check" and exits 0. That exit code is correct and must
stay: a docs-only or TypeScript-only pull request has nothing to lint, and
`test.yml`'s lint job going red on those would be a gate switched off within a
day.

What was wrong is what `scripts/gate.sh` *did* with that answer. It rendered
"nothing to check" as ĐẠT, so the summary said "Tất cả chặng đã chạy đều ĐẠT"
for a stage that ran ruff over no files at all. That is the
green-because-nothing-ran shape the whole file was written to remove, and the
same file already refuses it one stage earlier: `guard-range` meets the
identical empty-range condition and reports BỎ QUA with a reason, so `--strict`
can make it loud (tests/test_gate_guard_range_stage.py).

## It was not hypothetical -- it was hiding a real defect on main

Measured 2026-08-30 against main at 15b0e5c, the same commit both times:

    scripts/gate.sh ruff, worktree standing on origin/main
      "no Python files changed -- nothing for ruff to check"
      ĐẠT     ruff (0s)                                        exit 0

    make gate, fresh clone of the same commit whose merge base is one
    commit back, so the five files #207 added are in scope
      ruff over 5 changed Python file(s)
      --- ruff format --check ---
      Would reformat: tests/qa/rd-qa-37/doc-wire.py
      Would reformat: tests/qa/rd-qa-37/tao-anh-bill.py
      Would reformat: tests/qa/rd-qa-37/test_exif_duong_bill.py
      ::error::ruff rejected files this change touches
      HỎNG    ruff                                             exit 1

Three files that ruff rejects are on main right now. CI would have caught them
on the pull request; it could not, because GitHub Actions has not started a job
since the billing failure on 2026-08-29. The local gate was the last thing
standing, and standing on main it answered ĐẠT -- because on main the merge
base is HEAD and the scope is empty. The one moment you most want to ask "is
main clean?" is the exact moment this stage was structurally unable to answer.

## What this proves and what it does not

Every case builds a standalone repository in a temporary directory and runs the
real `scripts/gate.sh` against it. It touches no checkout and needs no network:
`refs/remotes/origin/main` is written directly.

It proves the stage skips rather than passes when nothing Python is in scope,
that `--strict` turns that skip into a failure, and -- the half that keeps the
first two from being satisfied by a stage that never runs -- that the stage is
still green on a clean Python file and still red on one ruff rejects.

It does not prove the three files above are fixed; they belong to the QA lane
and are reported separately. It does not check `ruff_changed.sh`'s own file
enumeration, which is tests/test_ruff_changed.py's job, and it says nothing
about whether the workflow and the gate stay in step -- nobody can check that
while Actions cannot execute.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# A file ruff accepts on both halves: `ruff check` finds nothing and
# `ruff format --check` reports it already formatted. Verified 2026-08-30.
CLEAN_PY = "VALUE = 1\n"

# F401, an unused import. In ruff's default rule set, so the fixture needs no
# pyproject.toml of its own -- one more file to drift out of step.
DIRTY_PY = "import os\n"


class GateRuffEmptyScope(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        if shutil.which("ruff") is None:
            self.skipTest("ruff is not installed")

        self.repo = pathlib.Path(tempfile.mkdtemp(prefix="gate-ruff-scope-"))
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

        # Only the scripts the stage touches, for the reason the guard-range
        # fixture gives: copying the tree drags this checkout's own history in
        # and makes the fixture unreadable.
        #
        # `ruff_pinned.sh` is here because `ruff_changed.sh` resolves the pinned
        # ruff through it rather than taking PATH's. Leaving it out made this
        # fixture red with "No such file or directory" -- correct behaviour from
        # the script and a broken fixture, which is worth saying out loud: the
        # list has to track what the stage actually needs.
        (self.repo / "scripts").mkdir(parents=True)
        for name in ("gate.sh", "ruff_changed.sh", "ruff_pinned.sh"):
            shutil.copy2(REPO_ROOT / "scripts" / name, self.repo / "scripts" / name)

        # `do_ruff` refuses to run without a ruff== pin to name, which is its
        # own gate (test.yml installs that exact version). Give the fixture one.
        (self.repo / "services" / "api").mkdir(parents=True)
        (self.repo / "services" / "api" / "requirements-dev.txt").write_text(
            "ruff==0.9.2\n", encoding="utf-8"
        )

        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "gate@test")
        self.git("config", "user.name", "gate")
        # core.hooksPath is inherited from the environment inside a worktree;
        # pointing it at nothing keeps the pre-commit guard out of the fixture,
        # so what is measured is the gate and not the hook.
        self.git("config", "core.hooksPath", str(self.repo / "no-such-hooks"))
        (self.repo / "README.md").write_text("nen\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "nen")
        # The branch point, written directly: no remote, no network.
        self.base = self.git("rev-parse", "HEAD").strip()
        self.git("update-ref", "refs/remotes/origin/main", self.base)

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            timeout=120,
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

    def run_gate(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.repo / "scripts" / "gate.sh"), *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            timeout=600,
        )

    def run_ruff_changed(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.repo / "scripts" / "ruff_changed.sh"), *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            timeout=600,
        )

    # --- the premise ------------------------------------------------------

    def test_ruff_changed_still_exits_zero_when_no_python_is_in_scope(self):
        """The contract `test.yml` depends on, pinned so this fix cannot be
        "solved" by making the script itself red. A docs-only pull request must
        not fail the lint job."""
        self.commit_file("docs/ghi-chu.md", "chi la tai lieu\n", "them tai lieu")
        result = self.run_ruff_changed(self.base)
        self.assertEqual(
            result.returncode,
            0,
            "ruff_changed.sh must stay green when there is nothing to lint:\n"
            + result.stdout
            + result.stderr,
        )
        self.assertIn("nothing for ruff to check", result.stdout, result.stdout)

    # --- the hole ---------------------------------------------------------

    def test_a_branch_with_no_python_changes_is_not_reported_as_a_pass(self):
        """The realistic shape: a frontend or docs branch. The stage checked no
        Python and must not claim it did."""
        self.commit_file("docs/ghi-chu.md", "chi la tai lieu\n", "them tai lieu")
        gate = self.run_gate("ruff")
        # "ĐẠT 0" appears in the summary counts either way, so the pass list is
        # what separates them: gate.sh prints "  đạt:" only when one passed.
        self.assertNotIn(
            "đạt:",
            gate.stdout,
            "ruff over zero files was reported as a pass:\n" + gate.stdout,
        )
        self.assertIn("ĐẠT 0   HỎNG 0   BỎ QUA 1", gate.stdout, gate.stdout)
        self.assertIn("BỎ QUA", gate.stdout, gate.stdout)
        # Exit 2, not 0: gate.sh refuses to exit 0 when no stage ran at all.
        self.assertEqual(gate.returncode, 2, gate.stdout + gate.stderr)

    def test_standing_on_main_itself_is_not_reported_as_a_pass(self):
        """The case that hid three unformatted files on main: no commits beyond
        origin/main at all, so the scope is empty for a second reason."""
        gate = self.run_gate("ruff")
        self.assertNotIn(
            "đạt:",
            gate.stdout,
            "an empty scope on main was reported as a pass:\n" + gate.stdout,
        )
        self.assertIn("BỎ QUA", gate.stdout, gate.stdout)
        self.assertEqual(gate.returncode, 2, gate.stdout + gate.stderr)

    def test_the_skip_says_why(self):
        """A skip without a reason is the same lie one step quieter."""
        self.commit_file("docs/ghi-chu.md", "chi la tai lieu\n", "them tai lieu")
        gate = self.run_gate("ruff")
        self.assertIn(
            "ruff:", gate.stdout, "the skip must name its stage:\n" + gate.stdout
        )
        self.assertIn(
            "Python",
            gate.stdout,
            "the reason must say what was missing:\n" + gate.stdout,
        )

    def test_strict_turns_the_empty_scope_skip_into_a_failure(self):
        """Before a merge a skip must not be usable as evidence."""
        self.commit_file("docs/ghi-chu.md", "chi la tai lieu\n", "them tai lieu")
        gate = self.run_gate("--strict", "ruff")
        self.assertEqual(
            gate.returncode,
            1,
            "--strict let an empty ruff scope through:\n" + gate.stdout + gate.stderr,
        )
        self.assertIn("HỎNG", gate.stdout, gate.stdout)

    # --- the canaries -----------------------------------------------------
    #
    # Without these, a stage that skipped unconditionally -- or crashed -- would
    # satisfy every case above and read as a working gate.

    def test_stage_is_green_when_it_actually_checked_a_clean_file(self):
        self.commit_file("sach.py", CLEAN_PY, "them file python sach")
        gate = self.run_gate("ruff")
        self.assertEqual(
            gate.returncode,
            0,
            "the stage failed a clean Python file:\n" + gate.stdout + gate.stderr,
        )
        self.assertIn("ĐẠT", gate.stdout, gate.stdout)
        self.assertIn(
            "1 changed Python file",
            gate.stdout,
            "the stage must say what it checked:\n" + gate.stdout,
        )

    def test_stage_is_red_on_a_file_ruff_rejects(self):
        self.commit_file("ban.py", DIRTY_PY, "them file python ban")
        gate = self.run_gate("ruff")
        self.assertEqual(
            gate.returncode,
            1,
            "the stage passed a file ruff rejects:\n" + gate.stdout + gate.stderr,
        )
        self.assertIn("HỎNG", gate.stdout, gate.stdout)

    def test_an_uncommitted_dirty_file_is_still_caught(self):
        """The local gate's whole advantage over CI is that it can see the
        working tree. A skip decided from committed files alone would throw
        that away and report BỎ QUA over a dirty file sitting right there."""
        (self.repo / "chua-commit.py").write_text(DIRTY_PY, encoding="utf-8")
        gate = self.run_gate("ruff")
        self.assertEqual(
            gate.returncode,
            1,
            "an uncommitted dirty file was not caught:\n" + gate.stdout + gate.stderr,
        )
        self.assertIn("HỎNG", gate.stdout, gate.stdout)

    # --- what the skip must not swallow -----------------------------------
    #
    # The skip above decides from the changed-file list alone. `do_ruff` opens
    # with an assertion that has no file list in it: `services/api/
    # requirements-dev.txt` must carry a `ruff==` pin, because test.yml's lint
    # job installs that exact version and fails with "::error::no ruff== pin"
    # when it is gone.
    #
    # Deleting that pin edits a .txt file. No Python moves, so the scope is
    # empty, so the stage skipped -- and the assertion written to catch exactly
    # that deletion never ran. Measured on main, the same edit both times:
    #
    #   @ 23455e7 (pin check in, skip not yet)
    #     không có dòng ruff== trong services/api/requirements-dev.txt
    #     HỎNG    ruff (0s)                                          exit 1
    #   @ ae45575 (both in)
    #     BỎ QUA  ruff -- nhánh không đổi file Python nào so với origin/main
    #     ĐẠT 0   HỎNG 0   BỎ QUA 1                                  exit 2
    #
    # The second run is not merely quieter, it is wrong: the branch did change
    # something this stage is responsible for, and the gate answered that it
    # did not. Under --strict it is red with a reason that sends the reader to
    # the wrong file, which costs more than a plain red.

    def delete_the_pin(self) -> None:
        """The edit under test: remove the pin, touch no Python file."""
        (self.repo / "services" / "api" / "requirements-dev.txt").write_text(
            "pytest==8.3.3\n", encoding="utf-8"
        )
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "go pin ruff")

    def test_the_pin_assertion_bites_when_the_stage_actually_runs(self):
        """The half that proves the assertion exists at all. Without it the
        case below could be satisfied by a stage that is red for any reason."""
        self.delete_the_pin()
        self.commit_file("mo_dun.py", CLEAN_PY, "them python sach")
        gate = self.run_gate("ruff")
        combined = gate.stdout + gate.stderr
        self.assertIn("không có dòng ruff==", combined, combined)
        self.assertEqual(gate.returncode, 1, combined)

    def test_a_deleted_pin_is_not_hidden_by_the_empty_scope_skip(self):
        """The hole itself: the pin is gone, no Python is in scope, and the
        stage must still say so rather than skip."""
        self.delete_the_pin()
        gate = self.run_gate("ruff")
        combined = gate.stdout + gate.stderr
        self.assertIn(
            "không có dòng ruff==",
            combined,
            "the pin was deleted and the gate answered 'no Python changed' "
            "instead -- the reader is sent to the wrong file:\n" + combined,
        )
        self.assertEqual(gate.returncode, 1, combined)

    def test_a_deleted_pin_is_named_correctly_under_strict(self):
        """--strict was already red here, but for the wrong reason. A red with
        a wrong diagnosis costs more than a red at the right file."""
        self.delete_the_pin()
        gate = self.run_gate("--strict", "ruff")
        combined = gate.stdout + gate.stderr
        self.assertEqual(gate.returncode, 1, combined)
        self.assertIn("không có dòng ruff==", combined, combined)
        self.assertNotIn(
            "nhánh không đổi file Python nào",
            combined,
            "--strict named the wrong cause:\n" + combined,
        )

    # --- the two outcomes the prereq already gets right --------------------
    #
    # Both were correct in the shipped code and neither had a test. They are
    # the same rule as the case above -- a prereq may turn a run into a skip
    # only when it is certain there is nothing to do -- so they belong here,
    # where changing that rule is what breaks them.

    def test_no_merge_base_runs_the_body_rather_than_skipping(self):
        """No origin/main to compare against is an unanswerable question, and
        an unanswerable question is a failure, not an absence."""
        self.git("update-ref", "-d", "refs/remotes/origin/main")
        gate = self.run_gate("ruff")
        combined = gate.stdout + gate.stderr
        # "BỎ QUA 0" is in the summary counts either way, so the skip list --
        # printed only when something actually skipped -- is what separates the
        # two outcomes.
        self.assertIn("BỎ QUA 0", gate.stdout, combined)
        self.assertNotIn("bỏ qua:", gate.stdout, combined)
        self.assertIn("không tìm được merge base", combined, combined)
        self.assertEqual(gate.returncode, 1, combined)

    def test_a_broken_list_call_runs_the_body_rather_than_skipping(self):
        """The prereq asks `ruff_changed.sh --list` what is in scope. If that
        call errors it has learnt nothing, and "I could not tell" must not be
        rendered as "there was nothing"."""
        (self.repo / "scripts" / "ruff_changed.sh").write_text(
            '#!/usr/bin/env bash\necho "vo hieu" >&2\nexit 3\n', encoding="utf-8"
        )
        self.commit_file("docs/ghi-chu.md", "chi la tai lieu\n", "them tai lieu")
        gate = self.run_gate("ruff")
        combined = gate.stdout + gate.stderr
        self.assertIn("BỎ QUA 0", gate.stdout, combined)
        self.assertNotIn(
            "bỏ qua:",
            gate.stdout,
            "a broken scope query was rendered as an empty scope:\n" + combined,
        )
        self.assertEqual(gate.returncode, 1, combined)


if __name__ == "__main__":
    unittest.main()
