"""A stage reported HỎNG must say why, in the report people actually read.

## Why

`scripts/gate.sh` ends with a failure report: for every failed stage it prints
a header promising the last 30 lines of that stage's log, then the log, then
the directory holding all of them. That is the part a reader scrolls to, and
on a long run it is the only part they read.

Two stages can fail *without ever running*, and so without ever writing a log:

  - `--strict` turns a skipped prerequisite into a failure
    ("strict: bỏ qua bị tính là hỏng -- packages/shared không có trên nhánh này")
  - a prerequisite is present but broken, which refuses to skip by design
    ("packages/shared có mặt nhưng thiếu money.test.mjs -- từ chối bỏ qua")

In both cases the report printed the header and then nothing at all, and named
a log directory that holds no log for that stage. Measured on f995873:

    ---- 30 dòng cuối của chặng hỏng: shared ----
                                                     <- silence
    Log đầy đủ: /tmp/tmp.Y7nZmSe00X                  <- no shared.log in it

The reason does get printed, but on stderr and far above, next to the stage
banner. Once stdout and stderr are separated -- redirected to a file, captured
by a job runner, pasted into a pull request -- the failure report says a stage
failed and offers nothing about why.

This repository keeps getting bitten by exactly this shape: a detector with no
browser returning `[]` and exit 0, a postgres tier whose 147 skips read as
green, an `imp detect` URL scan that cannot tell "clean" from "the scanner is
dead". Silence that looks like content is the defect. A gate whose own failure
report is silent has no standing to enforce that rule on anyone else.

## What this does NOT prove

It does not prove the reasons are accurate -- `check_prereq` decides those and
is asserted elsewhere. It does not run any real stage: the tree here holds
nothing but a copy of `gate.sh`, deliberately, so that this file can never
become a test that needs Docker, node, or a database and skips when they are
missing. That is the failure it exists to prevent.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "scripts" / "gate.sh"


def _bare_tree(tmp: Path) -> Path:
    """A tree holding only gate.sh.

    gate.sh resolves its repo root from its own location, so every stage's
    prerequisite is missing here and nothing can accidentally run for real.
    """
    (tmp / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(GATE, tmp / "scripts" / "gate.sh")
    return tmp


def _run(tree: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["scripts/gate.sh", *args],
        cwd=tree,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _section_for(stdout: str, stage: str) -> str:
    """A stage's whole entry in the failure report, header line included.

    Matching the header loosely rather than by its exact wording keeps these
    tests about what the report *tells* the reader, not about the sentence it
    happens to use today. Returning only this section -- rather than searching
    the whole output -- is the point: the reason printed next to the banner on
    stderr does not count, because that is the part that goes missing when the
    two streams are separated.
    """
    match = re.search(
        rf"^(----.*\b{re.escape(stage)}\b.*----)\n(.*?)(?=\n----|\nLog đầy đủ:|\Z)",
        stdout,
        re.S | re.M,
    )
    if match is None:
        raise AssertionError(
            f"báo cáo hỏng không có mục nào cho chặng {stage!r}.\n--- stdout ---\n{stdout}"
        )
    return f"{match.group(1)}\n{match.group(2)}".strip()


def _body_for(stdout: str, stage: str) -> str:
    """Just the evidence under the header -- what the report actually offers."""
    section = _section_for(stdout, stage)
    return section.split("\n", 1)[1].strip() if "\n" in section else ""


class FailureReportNamesTheReason(unittest.TestCase):
    def test_strict_converted_skip_says_why_in_the_report(self):
        """--strict makes a missing prerequisite a failure. The report must say so."""
        with tempfile.TemporaryDirectory() as tmp:
            tree = _bare_tree(Path(tmp))
            result = _run(tree, "--strict", "shared")

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        evidence = _body_for(result.stdout, "shared")
        self.assertNotEqual(
            "",
            evidence,
            "chặng hỏng nhưng phần bằng chứng rỗng -- đúng lỗi đang gỡ.\n"
            f"--- stdout ---\n{result.stdout}",
        )
        self.assertIn(
            "packages/shared",
            evidence,
            f"phần bằng chứng không nhắc tới lý do thật:\n{evidence!r}",
        )

    def test_broken_prerequisite_says_why_in_the_report(self):
        """Present-but-broken refuses to skip. That refusal must carry its reason."""
        with tempfile.TemporaryDirectory() as tmp:
            tree = _bare_tree(Path(tmp))
            # Present, but missing the file the stage runs -- `return 2`, and a
            # failure even without --strict.
            (tree / "packages" / "shared").mkdir(parents=True)
            result = _run(tree, "shared")

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        evidence = _body_for(result.stdout, "shared")
        self.assertNotEqual(
            "",
            evidence,
            "chặng hỏng vì thiếu file, nhưng phần bằng chứng rỗng.\n"
            f"--- stdout ---\n{result.stdout}",
        )
        self.assertIn(
            "money.test.mjs",
            evidence,
            f"phần bằng chứng không nhắc tới file còn thiếu:\n{evidence!r}",
        )

    def test_report_does_not_promise_a_log_that_was_never_written(self):
        """Naming a log directory that holds no log for the stage is a false lead.

        The reader follows it, finds nothing, and is left where they started.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tree = _bare_tree(Path(tmp))
            result = _run(tree, "--strict", "shared")

        section = _section_for(result.stdout, "shared")
        self.assertNotIn(
            "30 dòng cuối",
            section,
            f"vẫn hứa 30 dòng log cho một chặng chưa hề chạy:\n{section!r}",
        )
        # The stage never ran, so the report must not send the reader to a file
        # that does not exist.
        self.assertRegex(
            section,
            r"KHÔNG CHẠY|không chạy",
            f"báo cáo không nói rõ chặng này chưa hề chạy:\n{section!r}",
        )


class RealStagesStillShowTheirLog(unittest.TestCase):
    """The fix must not cost the case that already worked."""

    def test_a_stage_that_ran_still_prints_its_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = _bare_tree(Path(tmp))
            # `guard` has no prerequisite check, so it runs for real and fails
            # on the missing script -- producing a log, the normal path.
            result = _run(tree, "guard")

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        section = _section_for(result.stdout, "guard")
        self.assertIn(
            "repo_guard.py",
            section,
            f"log thật của chặng đã chạy không còn được in ra:\n{section!r}",
        )
        self.assertIn(
            "30 dòng cuối",
            section,
            f"chặng đã chạy thì vẫn phải hứa và in log của nó:\n{section!r}",
        )


if __name__ == "__main__":
    unittest.main()
