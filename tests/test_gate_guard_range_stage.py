"""The local gate must scan what a branch *committed*, not just what it ships.

## The hole this closes

`repo-guard.yml` runs two scans, and until 2026-08-29 `scripts/gate.sh` ran
only the first:

    repo_guard.py tree HEAD              -> gate.sh stage `guard`
    repo_guard.py range <base> <head>    -> nothing, locally

They are not the same question. `tree HEAD` asks what the branch delivers.
`range` asks what it ever wrote down. A secret committed and then deleted one
commit later is absent from the first and present forever in the second.

Measured on 2026-08-29 against a branch built exactly that way -- add a key,
delete it in the next commit:

    repo_guard.py tree HEAD      passed tracked tree: 632 file scan(s)   exit 0
    scripts/gate.sh guard        DAT                                      exit 0
    repo_guard.py range b..h     blocked: 1 finding across 1265 scans     exit 1

Three things could have caught it, and while GitHub Actions is down none of
them did. The pre-commit hook is walked past by `--no-verify` and does not
exist at all until somebody runs `scripts/setup-hooks.sh` -- CLAUDE.md already
records that as discipline, not enforcement. The workflow step cannot start.
So on a repository whose stated rule is that bill photos, account numbers and
real participant names never enter Git, and where `.gitignore` is explicitly
not a safe place to keep them, the only check that reads history ran nowhere.

## What this proves and what it does not

Every case below builds a standalone repository in a temporary directory and
runs the real `scripts/gate.sh` against it. It does not touch this checkout,
and it needs no network: `refs/remotes/origin/main` is written directly.

It proves the stage is red on a branch that committed a secret, green on one
that did not, and that neither answer is an accident of the stage never
running. It does not prove the workflow and the gate stay in step -- nobody
can prove that while Actions cannot execute -- and it says nothing about
findings already in this repository's history, which is why the stage scans a
branch's own commits and not `history`.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "scripts" / "gate.sh"

# AWS publishes this in its own documentation as an example. It is not a
# credential, and it matches AWS_ACCESS_KEY_ID_RE in scripts/repo_guard.py --
# a real one must never be written into a test for the reason the guard exists.
FAKE_KEY = "AKIA" + "IOSFODNN7EXAMPLE"


class GuardRangeStage(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.repo = pathlib.Path(tempfile.mkdtemp(prefix="gate-guard-range-"))
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

        # Only the two scripts the stage touches. Copying the whole tree would
        # drag this checkout's own history in and make the fixture unreadable.
        (self.repo / "scripts").mkdir(parents=True)
        for name in ("gate.sh", "repo_guard.py"):
            shutil.copy2(REPO_ROOT / "scripts" / name, self.repo / "scripts" / name)
        allowlist = REPO_ROOT / ".repo-guard-allowlist.json"
        if allowlist.is_file():
            shutil.copy2(allowlist, self.repo / allowlist.name)

        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "gate@test")
        self.git("config", "user.name", "gate")
        # core.hooksPath is inherited from the environment in a worktree; an
        # empty setting here keeps the pre-commit guard out of the fixture, so
        # what is being measured is the gate and not the hook.
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
            raise AssertionError(f"git {' '.join(args)} -> {result.returncode}\n{result.stderr}")
        return result.stdout

    def commit_file(self, name: str, body: str, message: str) -> None:
        (self.repo / name).write_text(body, encoding="utf-8")
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

    def run_guard(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python3", str(self.repo / "scripts" / "repo_guard.py"), *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            timeout=600,
        )

    def leak_then_delete(self) -> None:
        """The shape a lane produces when it notices its own mistake: commit a
        secret, remove it in the next commit, and ship a clean-looking tree."""
        self.commit_file("leak.txt", f"AWS_ACCESS_KEY_ID={FAKE_KEY}\n", "lo secret")
        self.git("rm", "-q", "leak.txt")
        self.git("commit", "-q", "-m", "xoa lai")

    # --- the hole ---------------------------------------------------------

    def test_tree_head_alone_does_not_see_a_deleted_secret(self):
        """Why the stage exists. If this ever fails, `tree` grew a history scan
        and `guard-range` may be redundant -- check before deleting it."""
        self.leak_then_delete()
        self.assertEqual(
            [], [p for p in self.repo.glob("leak.txt")], "fixture still has the file"
        )
        tree = self.run_guard("tree", "HEAD")
        self.assertEqual(
            tree.returncode,
            0,
            "the premise of this whole file is that `tree HEAD` is green here:\n"
            + tree.stdout
            + tree.stderr,
        )

    # --- the stage --------------------------------------------------------

    def test_stage_is_red_when_a_commit_carried_a_secret(self):
        self.leak_then_delete()
        gate = self.run_gate("guard-range")
        self.assertEqual(
            gate.returncode,
            1,
            "gate.sh guard-range passed a branch that committed a secret:\n"
            + gate.stdout
            + gate.stderr,
        )
        self.assertIn("HỎNG", gate.stdout, gate.stdout)

    def test_stage_is_green_on_a_branch_that_committed_nothing_bad(self):
        """The other canary. Without it, a stage that is red unconditionally --
        or red because it crashed -- would pass the test above and read as a
        working gate."""
        self.commit_file("note.md", "khong co gi nhay cam\n", "them ghi chu")
        gate = self.run_gate("guard-range")
        self.assertEqual(
            gate.returncode,
            0,
            "gate.sh guard-range failed a clean branch:\n" + gate.stdout + gate.stderr,
        )
        self.assertIn("ĐẠT", gate.stdout, gate.stdout)
        self.assertIn("1 commit", gate.stdout, "the stage must say what it scanned")

    # --- the empty range --------------------------------------------------

    def test_an_empty_range_is_not_reported_as_a_pass(self):
        """`repo_guard.py range X X` prints "passed commit range: 0 file
        scan(s)" and exits 0. Letting that through as DAT would rebuild the
        green-because-nothing-ran failure inside the stage written to stop it.
        """
        empty = self.run_guard("range", self.base, "HEAD")
        self.assertEqual(empty.returncode, 0, "premise: an empty range exits 0")
        self.assertIn("0 file scan", empty.stdout, empty.stdout)

        gate = self.run_gate("guard-range")
        # "ĐẠT 0" is in the summary counts either way, so the pass list is what
        # distinguishes them: gate.sh prints "  đạt:" only when one passed.
        self.assertNotIn(
            "đạt:",
            gate.stdout,
            "an empty range was reported as a pass:\n" + gate.stdout,
        )
        self.assertIn("ĐẠT 0   HỎNG 0   BỎ QUA 1", gate.stdout, gate.stdout)
        self.assertIn("BỎ QUA", gate.stdout, gate.stdout)
        # Exit 2, not 0: gate.sh refuses to exit 0 when no stage ran at all.
        self.assertEqual(gate.returncode, 2, gate.stdout + gate.stderr)

    def test_strict_turns_the_empty_range_skip_into_a_failure(self):
        """Before a merge a skip must not be usable as evidence."""
        gate = self.run_gate("--strict", "guard-range")
        self.assertEqual(
            gate.returncode,
            1,
            "--strict let an empty range through:\n" + gate.stdout + gate.stderr,
        )
        self.assertIn("HỎNG", gate.stdout, gate.stdout)


if __name__ == "__main__":
    unittest.main()
