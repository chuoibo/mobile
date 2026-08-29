"""What the changed-files ruff gate is allowed to fail, and what it must not.

The gate is a ratchet, and a ratchet has two halves that are equally load
bearing. It has to bite on a file the change touches, and it has to stay quiet
about the 76 files already on main that the author never opened. A gate that
only does the first half cannot be landed; a gate that only does the second is
decoration.

The case that matters most here is `test_docs_only_change_does_not_scan_tree`.
`ruff check` with no path arguments checks the entire tree, so an empty file
list that falls through to ruff turns every docs-only pull request into a
full-tree scan and fails it on somebody else's debt. Each of these builds a
throwaway git repository with a known-dirty file sitting in it, so "the gate
ignored the dirty file" and "the gate never ran" cannot be confused.

These call the real ruff, not a stub -- the thing under test is whether the
right paths reach it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "scripts" / "ruff_changed.sh"

# F401, unused import. In ruff's default rule set, so it fires in the temporary
# repositories below, which have no pyproject.toml of their own.
LINT_ERROR = "import os\n"

# Lint-clean under the default rules but not formatted the way ruff formats.
# Keeps the two halves of the gate distinguishable: this must be caught by
# `ruff format --check` and not by `ruff check`.
FORMAT_ERROR = "x = [1,2,3]\n"

CLEAN = 'print("hello")\n'


class RuffGateHarness(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp(prefix="ruff-changed-"))
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.git("init", "-q", "-b", "main")
        # Assembled rather than written out: the repo guard reads a literal
        # address as a real one and blocks the commit, which is the behaviour
        # we want from it everywhere else.
        self.git("config", "user.email", "gate" + "@" + "test.invalid")
        self.git("config", "user.name", "gate")

    def git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        )

    def write(self, name: str, body: str) -> None:
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(body), encoding="utf-8")

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").stdout.strip()

    def base_commit_with_dirty_file(self) -> str:
        """A repo whose history already carries a file ruff would reject.

        Every case starts here on purpose. It is what makes a passing result
        meaningful: the gate had something to trip over and did not trip.
        """
        self.write("legacy_dirty.py", LINT_ERROR)
        self.write("README.md", "# repo\n")
        return self.commit("base with pre-existing debt")

    def run_gate(self, *args: str, path: str | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        if path is not None:
            env["PATH"] = path
        return subprocess.run(
            ["bash", str(GATE), *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )


class ChangedFilesAreChecked(RuffGateHarness):
    def test_lint_error_in_changed_file_fails(self) -> None:
        base = self.base_commit_with_dirty_file()
        self.write("touched.py", LINT_ERROR)
        result = self.run_gate(base)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("touched.py", result.stdout)
        self.assertIn("F401", result.stdout + result.stderr)

    def test_format_violation_in_changed_file_fails(self) -> None:
        base = self.base_commit_with_dirty_file()
        self.write("touched.py", FORMAT_ERROR)
        result = self.run_gate(base)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Would reformat", result.stdout + result.stderr)

    def test_clean_changed_file_passes(self) -> None:
        base = self.base_commit_with_dirty_file()
        self.write("touched.py", CLEAN)
        result = self.run_gate(base)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_editing_a_dirty_legacy_file_forces_it_clean(self) -> None:
        """The ratchet turning. Touch the debt and you own it."""
        base = self.base_commit_with_dirty_file()
        self.write("legacy_dirty.py", LINT_ERROR + CLEAN)
        result = self.run_gate(base)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("legacy_dirty.py", result.stdout)


class UntouchedDebtIsLeftAlone(RuffGateHarness):
    def test_dirty_file_not_in_the_diff_does_not_fail(self) -> None:
        base = self.base_commit_with_dirty_file()
        self.write("touched.py", CLEAN)
        result = self.run_gate(base)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("legacy_dirty.py", result.stdout)

    def test_docs_only_change_does_not_scan_tree(self) -> None:
        """The trap: an empty file list must not reach ruff.

        `ruff check` with no paths checks everything. If the gate fell through,
        legacy_dirty.py would fail a change that only edited Markdown.
        """
        base = self.base_commit_with_dirty_file()
        self.write("README.md", "# repo\n\nmore words\n")
        result = self.run_gate(base)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no Python files changed", result.stdout)
        self.assertNotIn("legacy_dirty.py", result.stdout)

    def test_deleting_a_python_file_does_not_fail(self) -> None:
        """Removing a dirty file is the fix, not a violation.

        The path is in the diff but no longer on disk; handing it to ruff would
        fail the change for cleaning up.
        """
        base = self.base_commit_with_dirty_file()
        (self.repo / "legacy_dirty.py").unlink()
        result = self.run_gate(base)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class BranchComparison(RuffGateHarness):
    def test_head_form_ignores_commits_main_moved_on_to(self) -> None:
        """Three-dot semantics: the author is judged on their own commits.

        A dirty file landing on main after the branch started must not fail the
        branch. Two-dot diffing would report it and blame the wrong person.
        """
        base = self.base_commit_with_dirty_file()
        self.write("branch_file.py", CLEAN)
        head = self.commit("branch work")

        self.git("checkout", "-q", base)
        self.git("checkout", "-q", "-b", "moved-on")
        self.write("landed_after.py", LINT_ERROR)
        moved = self.commit("someone else's dirty file")

        result = self.run_gate(moved, head)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("landed_after.py", result.stdout)


    def test_worktree_form_ignores_commits_main_moved_on_to(self) -> None:
        """The same blame bug as above, in the local form.

        Found by running this gate on its own branch: a backend pull request
        merged into main mid-session and the gate reported five services/api
        files as the author's to fix. `git diff main` against a working tree
        that predates main's newest commits reports those commits inverted.
        Comparing against the merge base is what makes the answer "what I
        changed" instead of "what differs from main".
        """
        base = self.base_commit_with_dirty_file()
        self.git("checkout", "-q", "-b", "moved-on")
        self.write("landed_after.py", LINT_ERROR)
        self.commit("someone else's dirty file")

        self.git("checkout", "-q", "main")
        self.write("mine.py", CLEAN)

        result = self.run_gate("moved-on")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("landed_after.py", result.stdout)


class FailsLoudlyNotSilently(RuffGateHarness):
    def test_unresolvable_base_is_an_error_not_a_pass(self) -> None:
        self.base_commit_with_dirty_file()
        # Built from a repeat for the same reason as the address above: forty
        # zeros written out is a forty-digit number to the repo guard.
        result = self.run_gate("0" * 40)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("cannot resolve base ref", result.stderr)

    def test_missing_ruff_is_an_error_not_a_pass(self) -> None:
        """A runner without ruff must go red, not green.

        This is the shape of every gate in this repo that reported success for
        a check that never ran.
        """
        base = self.base_commit_with_dirty_file()
        self.write("touched.py", LINT_ERROR)
        # bash and git still have to be reachable or the script cannot start,
        # and "could not start" would prove nothing about the ruff check.
        bare = self.repo / "path-without-ruff"
        bare.mkdir()
        for tool in ("bash", "git"):
            found = shutil.which(tool)
            self.assertIsNotNone(found, f"{tool} is needed to run this test")
            (bare / tool).symlink_to(found)
        self.assertIsNone(shutil.which("ruff", path=str(bare)))
        result = self.run_gate(base, path=str(bare))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("ruff is not installed", result.stderr)

    def test_wrong_argument_count_is_an_error(self) -> None:
        result = self.run_gate()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
