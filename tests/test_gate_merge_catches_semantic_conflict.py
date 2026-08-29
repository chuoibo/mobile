"""`scripts/gate_merge.sh` must go red on a merge that git calls clean.

## Why this test exists

The gate it guards is only worth running if it catches the one thing nothing
else catches. Everything else in this repository already reports green on a
semantic conflict:

  * git reports a conflict when two branches touch the same lines. When one
    branch tightens a rule and another branch adds a caller that breaks it, the
    files differ, the merge is clean, and git says nothing.
  * `scripts/gate.sh` runs the gates on the tree you are standing in. Run on
    either branch alone it is green, because on either branch alone the tree
    really is fine.
  * GitHub Actions would have caught it on the merge commit -- but `test.yml`
    triggers only on `push: branches: [main]`, so it only ever spoke *after*
    the merge, and since the billing failure on 2026-08-29 it does not speak at
    all.

So a gate that quietly lost the ability to detect this would look exactly like
a gate that was working. That is the failure mode this repository keeps
producing -- a detector with no browser returning `[]` and exit 0, a postgres
tier reporting 254 skips that read as green, a ruff gate passing a run that
checked no files. This test is the canary that keeps `gate_merge.sh` honest.

## Why the fixture is synthetic

The canary is built as a throwaway git repository with a two-line stand-in for
`scripts/gate.sh`, not out of the real tree. A canary written against
`packages/shared/money.mjs` would break the day somebody legitimately edits
`formatVnd`, and a canary that breaks for unrelated reasons gets deleted. The
property under test belongs to `gate_merge.sh` and not to any particular file:
given two branches that merge without conflict into a tree that fails, does it
say so.

The same conflict was also reproduced once against the real tree, by hand, to
confirm the synthetic shape is the real shape: base added a MAX check to
`formatVnd` in `money.mjs`, head appended an assertion to `money.test.mjs`
pinning the old behaviour, no file in common, `git merge-tree` exit 0, both
branches green under `gate.sh`, and `gate_merge.sh` red on the `shared` stage.

## What this proves and what it does not

It proves `gate_merge.sh` builds the merge, runs the gate on the merged tree,
and propagates the failure -- and that a branch-only run of the same gate is
green, which is the contrast that makes it worth having. It does not prove the
real `scripts/gate.sh` stages catch any particular defect; that is each stage's
own business.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE_MERGE = REPO_ROOT / "scripts" / "gate_merge.sh"

# A stand-in gate: the tree is good when the number asked for fits under the
# limit. Two files, so two branches can each change one and never collide.
STANDIN_GATE = """#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2
limit=$(cat limit.txt)
want=$(cat want.txt)
if [ "$want" -gt "$limit" ]; then
  echo "HONG: want=$want vuot limit=$limit"
  exit 1
fi
echo "DAT: want=$want <= limit=$limit"
"""


def git(*args: str, cwd: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def commit_all(repo: pathlib.Path, message: str) -> None:
    git("add", "-A", cwd=repo)
    # -c so the fixture does not depend on the machine having a git identity,
    # and --no-verify because the fixture repo has no hooks worth running.
    result = git(
        "-c",
        "user.name=canary",
        "-c",
        "user.email=canary@local",
        "commit",
        "--no-verify",
        "-qm",
        message,
        cwd=repo,
    )
    assert result.returncode == 0, result.stderr


class GateMergeCatchesSemanticConflict(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.assertTrue(GATE_MERGE.exists(), f"{GATE_MERGE} không tồn tại")
        # Deliberately NOT prefixed "gate-merge-": the leak check below looks
        # for that string in `git worktree list`, and a fixture path containing
        # it reported a leak on every run -- a canary failing for its own
        # naming is worse than no canary.
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="gmcanary-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = self.tmp / "repo"
        (self.repo / "scripts").mkdir(parents=True)

        git("init", "-q", "-b", "main", str(self.repo), cwd=self.tmp)
        gate = self.repo / "scripts" / "gate.sh"
        gate.write_text(STANDIN_GATE)
        gate.chmod(0o755)
        shutil.copy2(GATE_MERGE, self.repo / "scripts" / "gate_merge.sh")
        (self.repo / "limit.txt").write_text("1000\n")
        (self.repo / "want.txt").write_text("10\n")
        commit_all(self.repo, "main")

        # base: tightens the limit. Alone it is green -- nothing on base asks
        # for more than 100.
        git("checkout", "-q", "-b", "base", cwd=self.repo)
        (self.repo / "limit.txt").write_text("100\n")
        commit_all(self.repo, "base: siet limit")

        # head: asks for more. Alone it is green -- on head the limit is still
        # 1000. Touches a different file, so the merge cannot conflict.
        git("checkout", "-q", "main", cwd=self.repo)
        git("checkout", "-q", "-b", "head", cwd=self.repo)
        (self.repo / "want.txt").write_text("500\n")
        commit_all(self.repo, "head: xin nhieu hon")

    def run_gate_merge(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["./scripts/gate_merge.sh", "--no-fetch", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=False,
        )

    def run_standin_gate(self, branch: str) -> subprocess.CompletedProcess:
        git("checkout", "-q", branch, cwd=self.repo)
        return subprocess.run(
            ["./scripts/gate.sh"],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_git_itself_reports_no_conflict(self) -> None:
        """The premise. If git flagged this, no new gate would be needed."""
        merged = git("merge-tree", "--write-tree", "head", "base", cwd=self.repo)
        self.assertEqual(
            merged.returncode,
            0,
            "Canary hỏng: git coi đây là xung đột, nên nó không còn là ca "
            f"xung đột ngữ nghĩa.\n{merged.stdout}\n{merged.stderr}",
        )

    def test_each_branch_alone_is_green(self) -> None:
        """The contrast. Without this, red on the merge proves nothing."""
        for branch in ("head", "base"):
            with self.subTest(branch=branch):
                result = self.run_standin_gate(branch)
                self.assertEqual(
                    result.returncode,
                    0,
                    f"Canary hỏng: nhánh {branch} đứng một mình đã đỏ sẵn.\n"
                    f"{result.stdout}\n{result.stderr}",
                )

    def test_merge_result_is_red(self) -> None:
        """The point of the whole file."""
        result = self.run_gate_merge("--base", "base", "head")
        self.assertEqual(
            result.returncode,
            1,
            "gate_merge.sh KHÔNG đỏ trên một cây gộp hỏng — cổng đã mất đúng "
            "cái khả năng nó tồn tại vì nó.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn(
            "want=500",
            result.stdout,
            "Đỏ nhưng không in ra lỗi của chặng — một cổng đỏ không nói được "
            "vì sao thì người nhận không sửa được.",
        )

    def test_refuses_a_branch_already_in_the_base(self) -> None:
        """Nothing to merge is not a pass, and must not exit 0."""
        result = self.run_gate_merge("--base", "head", "head")
        self.assertEqual(
            result.returncode,
            3,
            "Nhánh đã nằm trong base phải thoát 3, không phải ĐẠT.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("KHÔNG CÓ GÌ ĐỂ GỘP", result.stdout)
        self.assertNotIn(
            "cho cây xanh",
            result.stdout,
            "Không có gì để gộp mà vẫn tuyên bố cây xanh.",
        )

    def test_conflicting_merge_fails_and_names_the_files(self) -> None:
        """A merge it cannot build is a failure, not a silent skip."""
        git("checkout", "-q", "-b", "clash", "main", cwd=self.repo)
        (self.repo / "limit.txt").write_text("777\n")
        commit_all(self.repo, "clash: cung sua limit.txt")

        result = self.run_gate_merge("--base", "base", "clash")
        self.assertEqual(
            result.returncode,
            1,
            f"Gộp xung đột phải HỎNG.\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}",
        )
        self.assertIn("limit.txt", result.stdout, "Phải nêu tên file xung đột.")

    def test_leaves_no_worktree_behind(self) -> None:
        """It builds the merge in a worktree; it must remove it on every path."""
        for args in (("--base", "base", "head"), ("--base", "head", "head")):
            with self.subTest(args=args):
                self.run_gate_merge(*args)
                listed = git("worktree", "list", cwd=self.repo).stdout
                extra = [line for line in listed.splitlines() if "gate-merge-" in line]
                self.assertEqual(extra, [], f"Còn sót worktree tạm:\n{listed}")


if __name__ == "__main__":
    unittest.main()
