"""`scripts/gate_merge.sh` must not print a green verdict over a skipped stage.

## The hole this closes

`scripts/gate.sh` ends a run that skipped anything with a sentence addressed to
exactly one reader:

    BỎ QUA KHÔNG PHẢI ĐẠT. Trước khi merge chạy lại với --strict.

`gate_merge.sh` is the before-a-merge run. It printed that line, said nothing
about it, and closed three lines later with an unconditional
"ĐẠT ... cho cây xanh" and exit 0. Measured on 2026-08-30 at ef2f5e8, with the
postgres image name pointed at something unresolvable so the two heaviest
stages skip the way they do on any machine without the image:

    scripts/gate_merge.sh --no-fetch -- guard postgres e2e
      ĐẠT     guard (6s)
      BỎ QUA  postgres -- chưa có ảnh postgres tại máy
      BỎ QUA  e2e      -- chưa có ảnh postgres tại máy
      ĐẠT 1   HỎNG 0   BỎ QUA 2
      BỎ QUA KHÔNG PHẢI ĐẠT. Trước khi merge chạy lại với --strict.
      ĐẠT  gộp ... vào origin/main cho cây xanh.              exit 0

`e2e` is the only stage where the client and the server are both real, and
`postgres` is the only proof of any SQL, index, view or trigger in this
repository. Neither ran. The last line a person reads before clicking merge
said the tree was fine, and the exit code agreed.

This is the shape `do_ruff` had already named, one file over: "a warning on
line three of a thirteen-stage run, under a summary that ends ĐẠT, is a warning
nobody reads." Same root cause, second location -- which is the reason this is
a test and not a one-line patch.

## What is being pinned

Three verdicts, not two. `gate_merge.sh` now answers 0 (green, everything ran),
1 (a stage failed), or 4 (nothing failed, something did not run). The third is
the one that was missing, and the distinction it carries is real: "your branch
is broken" and "this run did not answer" send the reader to different places.

The counts arrive over `GATE_SUMMARY_FILE` rather than by grepping the banner,
so a merge decision does not depend on the wording of a heading. An absent or
unparseable file is "cannot tell" and is also refused -- fail closed, because a
caller that reads silence as good news rebuilds the original bug one level up.

## Why the fixture is synthetic, and why one test is not

The verdict logic belongs to `gate_merge.sh` and not to any stage, so it is
exercised against a stand-in gate whose only job is to report a chosen number
of passes, failures and skips. A canary wired to the real `postgres` stage
would go red the day somebody installs an image, and a canary that fails for
unrelated reasons gets deleted.

But a synthetic stand-in can only prove `gate_merge.sh` reads the contract. It
cannot prove the real `scripts/gate.sh` writes it -- and if it quietly stopped,
every merge would land in the fail-closed branch and the honest answer would be
buried in noise. `TheRealGateWritesTheSummaryItPromises` runs the real gate and
checks the file against the gate's own printed banner, so the two halves of the
contract are pinned to each other rather than to a number typed here.
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE_MERGE = REPO_ROOT / "scripts" / "gate_merge.sh"
GATE = REPO_ROOT / "scripts" / "gate.sh"

# A stand-in gate. `want` over `limit` is a stage that failed; `skips.txt` is
# how many stages never ran. Both are files in the tree, so a branch can set
# them and the merged tree carries them -- the way the real gate reads the real
# tree rather than its arguments.
STANDIN_GATE = """#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

strict=0
for a in "$@"; do [ "$a" = "--strict" ] && strict=1; done

limit=$(cat limit.txt)
want=$(cat want.txt)
skips=$(cat skips.txt)

passed=0; failed=0
if [ "$want" -gt "$limit" ]; then
  echo "HONG: want=$want vuot limit=$limit"; failed=1
else
  echo "DAT: want=$want <= limit=$limit"; passed=1
fi

# --strict turns every skip into a failure, the way the real gate does. Here to
# prove the flag arrives at all, not to re-test the real gate's handling of it.
if [ "$strict" -eq 1 ] && [ "$skips" -gt 0 ]; then
  echo "strict: $skips bo qua tinh la hong"
  failed=$((failed + skips)); skips=0
fi

i=0
while [ "$i" -lt "$skips" ]; do echo "BO QUA chang$i"; i=$((i + 1)); done
echo "DAT $passed   HONG $failed   BO QUA $skips"

if [ -n "${GATE_SUMMARY_FILE:-}" ] && [ ! -f khong-ghi-summary ]; then
  {
    echo "passed=$passed"
    echo "failed=$failed"
    echo "skipped=$skips"
    i=0
    while [ "$i" -lt "$skips" ]; do
      echo "skipped-stage=chang$i: thieu cong cu"; i=$((i + 1))
    done
  } > "$GATE_SUMMARY_FILE"
fi

[ "$failed" -eq 0 ] || exit 1
exit 0
"""


def git(*args: str, cwd: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def commit_all(repo: pathlib.Path, message: str) -> None:
    git("add", "-A", cwd=repo)
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


class GateMergeRefusesToCallASkipGreen(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.assertTrue(GATE_MERGE.exists(), f"{GATE_MERGE} không tồn tại")
        # Not prefixed "gate-merge-": the sibling canary's leak check greps
        # `git worktree list` for that string, and a fixture path containing it
        # reports a leak on every run.
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="gmskip-"))
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
        (self.repo / "skips.txt").write_text("0\n")
        commit_all(self.repo, "main")

        # A base that has moved on, so every run below is a real merge of two
        # commits rather than a fast-forward that never builds a tree.
        git("checkout", "-q", "-b", "base", cwd=self.repo)
        (self.repo / "base-marker.txt").write_text("base\n")
        commit_all(self.repo, "base: da di truoc")
        git("checkout", "-q", "main", cwd=self.repo)

    def make_head(
        self,
        name: str,
        *,
        skips: int = 0,
        want: int = 10,
        writes_summary: bool = True,
    ) -> None:
        git("checkout", "-q", "-b", name, "main", cwd=self.repo)
        # Always something to commit. Without it the default head is
        # byte-identical to main, `git commit` finds nothing, and the fixture
        # dies before it can ask the question.
        (self.repo / "head-marker.txt").write_text(f"{name}\n")
        (self.repo / "skips.txt").write_text(f"{skips}\n")
        (self.repo / "want.txt").write_text(f"{want}\n")
        if not writes_summary:
            (self.repo / "khong-ghi-summary").write_text("cong ban cu\n")
        commit_all(self.repo, f"head {name}")

    def run_gate_merge(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["./scripts/gate_merge.sh", "--no-fetch", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
        )

    def test_everything_ran_and_passed_is_still_green(self) -> None:
        """The contrast. Without it, refusing skips could just be refusing
        everything, and a gate that is red for every input is as useless as one
        that is never red -- it only wastes more of the reader's time first."""
        self.make_head("clean", skips=0)
        result = self.run_gate_merge("--base", "base", "clean")
        self.assertEqual(
            result.returncode,
            0,
            "Không chặng nào bỏ qua, không chặng nào hỏng, mà vẫn không ĐẠT.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("cho cây xanh", result.stdout)

    def test_a_skipped_stage_is_not_a_green_merge(self) -> None:
        """The point of the whole file."""
        self.make_head("skipping", skips=2)
        result = self.run_gate_merge("--base", "base", "skipping")
        self.assertEqual(
            result.returncode,
            4,
            "Cổng gộp bỏ qua chặng mà vẫn thoát như đã kiểm xong.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertNotIn(
            "cho cây xanh",
            result.stdout,
            "Có chặng KHÔNG CHẠY mà vẫn tuyên bố cây xanh — đúng câu đã "
            "khiến hai chặng nặng nhất lọt qua một lần merge.",
        )

    def test_it_names_the_stages_that_did_not_run(self) -> None:
        """A verdict that says "2 chặng không chạy" without saying which sends
        the reader back to scroll a thirteen-stage log, which is how the
        original warning came to be ignored in the first place."""
        self.make_head("skipping", skips=2)
        result = self.run_gate_merge("--base", "base", "skipping")
        for stage in ("chang0", "chang1"):
            self.assertIn(
                stage,
                result.stdout,
                f"Kết luận không nêu tên chặng {stage} đã bỏ qua.\n{result.stdout}",
            )
        self.assertIn(
            "thieu cong cu",
            result.stdout,
            "Nêu tên chặng nhưng không nêu lý do nó không chạy.",
        )

    def test_a_gate_that_writes_no_summary_is_not_green_either(self) -> None:
        """Fail closed.

        The merged tree can carry a `scripts/gate.sh` older than this contract,
        and then nothing is written at all. Reading that silence as "nothing
        was skipped" would rebuild the bug one level up, with the added charm
        of being invisible.
        """
        self.make_head("cong-cu", skips=0, writes_summary=False)
        result = self.run_gate_merge("--base", "base", "cong-cu")
        self.assertEqual(
            result.returncode,
            4,
            "Cổng không nói được nó đã chạy gì, mà vẫn ĐẠT.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertNotIn("cho cây xanh", result.stdout)

    def test_a_failing_stage_is_still_reported_as_a_failure(self) -> None:
        """The new branch must not swallow the old answer. A failure and an
        unanswered question are different, and 1 stays 1."""
        self.make_head("hong", skips=2, want=5000)
        result = self.run_gate_merge("--base", "base", "hong")
        self.assertEqual(
            result.returncode,
            1,
            "Chặng HỎNG bị báo cáo thành 'chưa kết luận được'.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("want=5000", result.stdout)

    def test_strict_reaches_the_gate_through_the_dash_dash(self) -> None:
        """The escape hatch the verdict points at has to actually work.

        Telling the reader "thêm '-- --strict'" is only useful if the flag
        arrives; `gate_merge.sh` parses its own arguments before `--` and has
        rejected unknown dashes before now.
        """
        self.make_head("skipping", skips=2)
        result = self.run_gate_merge("--base", "base", "skipping", "--", "--strict")
        self.assertEqual(
            result.returncode,
            1,
            "'-- --strict' không tới được cổng: bỏ qua vẫn không thành hỏng.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("strict:", result.stdout)


class TheRealGateWritesTheSummaryItPromises(unittest.TestCase):
    """The other half of the contract, against the real scripts/gate.sh.

    Everything above would keep passing if `gate.sh` stopped writing the file:
    `gate_merge.sh` would fail closed on every merge, which is safe and also
    useless. This asks the real gate for a run and checks that the file it
    writes says the same thing as the banner it prints.
    """

    maxDiff = None

    BANNER = re.compile(r"^ĐẠT (\d+)\s+HỎNG (\d+)\s+BỎ QUA (\d+)$", re.MULTILINE)

    def test_the_file_says_what_the_banner_says(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gatesummary-") as tmp:
            summary = pathlib.Path(tmp) / "summary.txt"
            env = dict(os.environ)
            env["GATE_SUMMARY_FILE"] = str(summary)
            # Force a skip that costs nothing and touches nothing: an image tag
            # that cannot resolve is the documented skip path for both heavy
            # stages. An inherited connection string would send `postgres` off
            # to a real database instead, so it goes.
            env["MOBILE_TEST_POSTGRES_IMAGE"] = "postgres:00-canary-khong-ton-tai"
            env.pop("MOBILE_TEST_DATABASE_URL", None)
            result = subprocess.run(
                ["bash", str(GATE), "shared", "postgres"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                env=env,
                timeout=600,
            )

            self.assertTrue(
                summary.exists(),
                "scripts/gate.sh không ghi GATE_SUMMARY_FILE — cổng gộp sẽ "
                "fail closed trên MỌI merge và câu trả lời thật bị chôn.\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )
            text = summary.read_text()
            values = dict(
                line.split("=", 1) for line in text.splitlines() if "=" in line
            )

            match = self.BANNER.search(result.stdout)
            self.assertIsNotNone(
                match,
                f"Không đọc được dòng tổng kết của gate.sh:\n{result.stdout}",
            )
            assert match is not None
            banner = {
                "passed": match.group(1),
                "failed": match.group(2),
                "skipped": match.group(3),
            }
            self.assertEqual(
                {k: values.get(k) for k in banner},
                banner,
                "File tổng kết và dòng tổng kết in ra không khớp nhau — cổng "
                f"gộp đang đọc một con số khác con số người đọc thấy.\n{text}",
            )

            # Not vacuous: comparing 0 against 0 would pass on a gate that
            # never skips anything and prove nothing about the skip path.
            self.assertGreater(
                int(banner["skipped"]),
                0,
                "Không chặng nào bỏ qua, nên phép so trên chưa chạm đường bỏ "
                f"qua. Ảnh postgres giả lẽ ra phải làm postgres bỏ qua.\n{result.stdout}",
            )
            named = [
                line for line in text.splitlines() if line.startswith("skipped-stage=")
            ]
            self.assertEqual(
                len(named),
                int(banner["skipped"]),
                "Số chặng bỏ qua không khớp số dòng nêu tên chặng bỏ qua — cổng "
                f"gộp sẽ đếm được mà không kể được tên.\n{text}",
            )


if __name__ == "__main__":
    unittest.main()
