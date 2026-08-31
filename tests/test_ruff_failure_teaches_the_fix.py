"""The ruff gate has to say what to type next, not just that it is unhappy.

Five people hit this stage in one night -- backend #372, devops #410, qa2 #411,
frontend #397, backend #450 -- and every one of them needed a human to explain
the same four things:

  1. the half that is red is usually `ruff format --check`, not `ruff check`,
     and the two are fixed by different commands;
  2. `scripts/ruff_pinned.sh` PRINTS A PATH and lints nothing, so it has to be
     wrapped in `$( )`; typed bare it exits 64 having checked nothing;
  3. the verdict comes from the PINNED ruff, not whatever is on PATH -- two
     formatter versions disagree;
  4. only the files this change touches, because `ruff format` over the tree
     produces a 27-file diff that buries the real change.

All four were already written down -- in `scripts/ruff_changed.sh`'s header, in
`scripts/ruff_pinned.sh`'s header, in CLAUDE.md. None of it is on screen at the
moment the stage goes red, which is the only moment anybody is reading. What was
on screen was one line:

    ::error::ruff rejected files this change touches -- fix them, or narrow the change

That line is a verdict with no instruction in it. This file pins the instruction.

## What these prove, and what they do not

The load-bearing case is `test_pasted_block_actually_fixes_the_failure`: it
lifts the printed command out of the gate's own output, runs it verbatim, and
re-runs the gate. A message that merely *reads* helpfully cannot pass that --
the command has to have the right quoting, the right binary and the right file
list, or the second run stays red. Wording assertions alone would be satisfied
by a paragraph that sounds right and does not work.

They do not prove a human understands the message. They prove that a human who
copies it gets a green gate.

Each case builds a throwaway git repository carrying `scripts/ruff_pinned.sh`
and the real `services/api/requirements-dev.txt`, so the pasted block resolves
the pin exactly the way it would in this repo rather than against a stub.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "scripts" / "ruff_changed.sh"
PINNED = REPO_ROOT / "scripts" / "ruff_pinned.sh"
REQUIREMENTS = REPO_ROOT / "services" / "api" / "requirements-dev.txt"

# F401, unused import: in ruff's default rule set and marked `[*]` fixable, so
# `ruff check --fix` clears it. A rule ruff cannot fix on its own would make
# `test_pasted_block_actually_fixes_the_failure` red for an honest reason and
# prove nothing about the message.
LINT_ERROR = "import os\n"

# Lint-clean under the default rules, and not formatted the way ruff formats.
# Keeps the two halves distinguishable: this is caught by `ruff format --check`
# and never by `ruff check`.
FORMAT_ERROR = "x = [1,2,3]\n"

CLEAN = 'print("hello")\n'

# The gate fences its copy-paste block with these so a reader knows exactly what
# to select, and so this file can lift it back out without guessing at
# indentation. Matched on the prefix: the opening marker also carries "(đứng ở
# gốc repo)", which is instruction for the human and not part of the contract.
BLOCK_START = "=== DÁN TỪ ĐÂY"
BLOCK_END = "=== ĐẾN ĐÂY"


def pinned_version() -> str:
    """The version `services/api/requirements-dev.txt` pins, read not repeated.

    Hard-coding "0.9.2" here would make this file agree with itself and stop
    agreeing with the repository the day somebody bumps the pin.
    """
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        if line.startswith("ruff=="):
            return line[len("ruff==") :].strip()
    raise AssertionError(f"no ruff== pin in {REQUIREMENTS}")


class TeachingHarness(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp(prefix="ruff-teaches-"))
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.git("init", "-q", "-b", "main")
        # Assembled rather than written literally: the repo guard reads an
        # address-shaped string as a real one.
        self.git("config", "user.email", "gate" + "@" + "test.invalid")
        self.git("config", "user.name", "gate")

        # The pasted block says `scripts/ruff_pinned.sh`, a repo-relative path.
        # For the paste to be runnable here, this throwaway repo has to carry
        # the same two files at the same two places. copy2 keeps the exec bit.
        (self.repo / "scripts").mkdir()
        shutil.copy2(PINNED, self.repo / "scripts" / "ruff_pinned.sh")
        (self.repo / "services" / "api").mkdir(parents=True)
        shutil.copy2(REQUIREMENTS, self.repo / "services" / "api")

    def git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=self.repo, check=True, capture_output=True, text=True
        )

    def write(self, name: str, body: str) -> None:
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    def base(self) -> str:
        """A commit with pre-existing debt already in it.

        The debt matters: it is what makes a green second run meaningful. The
        pasted command has to clean the touched files without being handed the
        whole tree, and this file would be swept up by a whole-tree fix.
        """
        self.write("legacy_dirty.py", LINT_ERROR + FORMAT_ERROR)
        self.write("README.md", "# repo\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base with pre-existing debt")
        return self.git("rev-parse", "HEAD").stdout.strip()

    def run_gate(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(GATE), *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            env=dict(os.environ),
            timeout=300,
        )

    def output(self, result: subprocess.CompletedProcess) -> str:
        return result.stdout + result.stderr

    def flat(self, result: subprocess.CompletedProcess) -> str:
        """Output with runs of whitespace collapsed to one space.

        The explanations are wrapped prose, so where the line breaks fall is a
        typography decision that should not be able to fail a test about what
        the message says. Asserting on the raw text pins the wrapping instead of
        the wording.
        """
        return " ".join(self.output(result).split())

    def paste_block(self, result: subprocess.CompletedProcess) -> str:
        """Everything between the two fences, which is what a human selects."""
        text = self.output(result)
        lines = text.splitlines()
        starts = [i for i, line in enumerate(lines) if line.startswith(BLOCK_START)]
        ends = [i for i, line in enumerate(lines) if line.startswith(BLOCK_END)]
        self.assertTrue(
            starts and ends,
            "cổng đỏ mà không in khối dán được -- người đọc không biết gõ gì.\n"
            f"--- toàn bộ output ---\n{text}",
        )
        self.assertLess(starts[0], ends[0], f"khối dán bị đảo đầu đuôi:\n{text}")
        return "\n".join(lines[starts[0] + 1 : ends[0]])


class TheBlockIsRunnable(TeachingHarness):
    def test_pasted_block_actually_fixes_the_failure(self) -> None:
        """Copy what it printed, run it, and the gate has to go green.

        This is the case that cannot be satisfied by prose. It fails if the
        block quotes wrongly, resolves the wrong binary, or names the wrong
        files.
        """
        base = self.base()
        self.write("touched_lint.py", LINT_ERROR)
        self.write("touched_fmt.py", FORMAT_ERROR)

        first = self.run_gate(base)
        self.assertEqual(first.returncode, 1, self.output(first))

        block = self.paste_block(first)
        pasted = subprocess.run(
            ["bash", "-c", block],
            cwd=self.repo,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(
            pasted.returncode,
            0,
            f"khối dán chạy không nổi:\n--- khối ---\n{block}\n"
            f"--- stdout ---\n{pasted.stdout}\n--- stderr ---\n{pasted.stderr}",
        )

        second = self.run_gate(base)
        self.assertEqual(
            second.returncode,
            0,
            "dán đúng lệnh nó bảo mà cổng vẫn đỏ:\n"
            f"--- khối ---\n{block}\n--- lần hai ---\n{self.output(second)}",
        )

    def test_pasted_block_does_not_touch_untouched_debt(self) -> None:
        """Point 4, measured rather than asserted.

        The whole-tree fix is the thing the message tells people not to run, so
        the command it hands them must not be that command wearing a disguise.
        `legacy_dirty.py` is committed dirty and is not in the change; it has to
        come out of the paste byte-identical.
        """
        base = self.base()
        before = (self.repo / "legacy_dirty.py").read_bytes()
        self.write("touched_fmt.py", FORMAT_ERROR)

        block = self.paste_block(self.run_gate(base))
        subprocess.run(
            ["bash", "-c", block], cwd=self.repo, capture_output=True, timeout=300
        )

        self.assertEqual(
            (self.repo / "legacy_dirty.py").read_bytes(),
            before,
            "khối dán đã sửa file nhánh này không hề chạm -- đó đúng là cái "
            "CLAUDE.md cấm, và cổng vừa tự bảo người ta làm",
        )


class TheMessageNamesTheRightHalf(TeachingHarness):
    def test_format_only_failure_prescribes_format_not_fix(self) -> None:
        """Điểm 1: hai nửa hỏng khác nhau và sửa bằng hai lệnh khác nhau."""
        base = self.base()
        self.write("touched_fmt.py", FORMAT_ERROR)

        result = self.run_gate(base)
        self.assertEqual(result.returncode, 1, self.output(result))
        block = self.paste_block(result)

        self.assertIn("format", block)
        self.assertIn("touched_fmt.py", block)
        self.assertNotIn(
            "--fix",
            block,
            "chỉ nửa format đỏ mà lại bảo chạy `check --fix` -- đó là câu trả "
            f"lời cho nửa kia:\n{block}",
        )

    def test_lint_only_failure_prescribes_fix_not_format(self) -> None:
        base = self.base()
        self.write("touched_lint.py", LINT_ERROR)

        result = self.run_gate(base)
        self.assertEqual(result.returncode, 1, self.output(result))
        block = self.paste_block(result)

        self.assertIn("--fix", block)
        self.assertIn("touched_lint.py", block)

    def test_the_failing_half_is_named_and_the_passing_half_is_not_blamed(
        self,
    ) -> None:
        base = self.base()
        self.write("touched_fmt.py", FORMAT_ERROR)

        text = self.output(self.run_gate(base))
        self.assertIn("ruff format --check", text)
        # The verdict per half, so the reader does not have to infer it from
        # ruff's own output forty lines up.
        self.assertRegex(text, r"ruff check.*(ĐẠT|đạt|PASS|sạch)")

    def test_only_the_offending_file_is_named_not_every_changed_file(self) -> None:
        """A file that is in the change and already clean is not a fix target.

        Naming it would be the whole-tree mistake in miniature, and would
        teach the reader that the list is noise.
        """
        base = self.base()
        self.write("touched_fmt.py", FORMAT_ERROR)
        self.write("touched_clean.py", CLEAN)

        block = self.paste_block(self.run_gate(base))
        self.assertIn("touched_fmt.py", block)
        self.assertNotIn("touched_clean.py", block)


class TheMessageCarriesTheFourExplanations(TeachingHarness):
    def setUp(self) -> None:
        super().setUp()
        base = self.base()
        self.write("touched_fmt.py", FORMAT_ERROR)
        self.write("touched_lint.py", LINT_ERROR)
        self.result = self.run_gate(base)
        self.assertEqual(self.result.returncode, 1, self.output(self.result))
        self.text = self.output(self.result)
        self.wrapped = self.flat(self.result)

    def test_point_two_the_dollar_paren_wrapping(self) -> None:
        """`scripts/ruff_pinned.sh` in a bare command position lints nothing."""
        self.assertIn('"$(scripts/ruff_pinned.sh)"', self.text)
        # And says WHY, or the wrapping reads as decoration and gets dropped
        # the first time somebody retypes the command from memory.
        self.assertRegex(self.wrapped, r"(IN RA|in ra).{0,40}(ĐƯỜNG DẪN|đường dẫn)")
        self.assertRegex(self.wrapped, r"(KHÔNG|không) (lint|kiểm)")

    def test_point_three_the_pin_not_whatever_is_on_path(self) -> None:
        self.assertIn(pinned_version(), self.text)
        self.assertIn("requirements-dev.txt", self.text)
        self.assertRegex(self.wrapped, r"PATH")

    def test_point_four_do_not_format_the_whole_tree(self) -> None:
        self.assertRegex(
            self.wrapped, r"(ĐỪNG|đừng|KHÔNG|không).{0,80}(cả cây|toàn cây)"
        )

    def test_it_offers_the_one_command_alternative(self) -> None:
        """`make ruff-fix` is the version nobody can mis-type."""
        self.assertIn("make ruff-fix", self.text)


class TheAdvertisedCommandsExist(TeachingHarness):
    """A gate that recommends a command that is not there teaches a dead end.

    The failure message is the one screen somebody stuck reads, so every
    `make <target>` on it has to resolve. This binds the message to the
    Makefile instead of to a comment saying they should agree.
    """

    def make_targets(self) -> set[str]:
        targets = set()
        for line in (REPO_ROOT / "Makefile").read_text(encoding="utf-8").splitlines():
            match = re.match(r"^([a-z][a-z0-9-]*):", line)
            if match:
                targets.add(match.group(1))
        return targets

    def test_every_make_target_the_message_names_is_defined(self) -> None:
        base = self.base()
        self.write("touched_fmt.py", FORMAT_ERROR)
        text = self.output(self.run_gate(base))

        named = set(re.findall(r"\bmake ([a-z][a-z0-9-]*)\b", text))
        self.assertTrue(named, f"thông điệp không mời gọi lệnh make nào:\n{text}")

        missing = sorted(named - self.make_targets())
        self.assertEqual(
            missing,
            [],
            f"cổng bảo người ta gõ {missing}, mà Makefile không có target đó",
        )

    def test_the_fixer_script_the_target_points_at_is_executable(self) -> None:
        fixer = REPO_ROOT / "scripts" / "ruff_fix.sh"
        self.assertTrue(fixer.exists(), f"{fixer} không tồn tại")
        self.assertTrue(os.access(fixer, os.X_OK), f"{fixer} không có bit thực thi")


class TheFixerAgreesWithTheGate(unittest.TestCase):
    """`make ruff-fix` must fix exactly what the gate grades -- no more.

    A fixer with a wider idea of scope than the gate is the whole-tree mistake
    with a friendlier name: it would rewrite files the author never opened while
    reporting success. So this builds a repo with committed debt outside the
    change and checks the debt survives.

    `scripts/ruff_fix.sh` resolves its own repo root and `origin/main`, so the
    throwaway repo here carries the three scripts at their real paths and a real
    bare remote rather than a stand-in ref.
    """

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="ruff-fixer-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.repo = self.root / "work"
        origin = self.root / "origin.git"

        subprocess.run(
            ["git", "init", "-q", "--bare", str(origin)],
            check=True,
            capture_output=True,
        )
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "gate" + "@" + "test.invalid")
        self.git("config", "user.name", "gate")

        (self.repo / "scripts").mkdir()
        for name in ("ruff_fix.sh", "ruff_changed.sh", "ruff_pinned.sh"):
            shutil.copy2(REPO_ROOT / "scripts" / name, self.repo / "scripts" / name)
        (self.repo / "services" / "api").mkdir(parents=True)
        shutil.copy2(REQUIREMENTS, self.repo / "services" / "api")

        # Committed debt that the change does not touch. This is the file a
        # whole-tree fixer would quietly rewrite.
        (self.repo / "legacy_dirty.py").write_text(
            LINT_ERROR + FORMAT_ERROR, encoding="utf-8"
        )
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base with pre-existing debt")
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "-q", "-u", "origin", "main")

    def git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=self.repo, check=True, capture_output=True, text=True
        )

    def run_fixer(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", "scripts/ruff_fix.sh", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            env=dict(os.environ),
            timeout=300,
        )

    def test_it_fixes_the_touched_file_and_leaves_the_rest_alone(self) -> None:
        debt_before = (self.repo / "legacy_dirty.py").read_bytes()
        (self.repo / "touched.py").write_text(LINT_ERROR + FORMAT_ERROR, "utf-8")

        result = self.run_fixer()
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)

        self.assertNotIn(
            "import os",
            (self.repo / "touched.py").read_text(encoding="utf-8"),
            f"file nhánh chạm vẫn còn lỗi sau khi fixer báo ĐẠT:\n{combined}",
        )
        self.assertEqual(
            (self.repo / "legacy_dirty.py").read_bytes(),
            debt_before,
            f"fixer đã sửa nợ cũ ngoài phạm vi thay đổi:\n{combined}",
        )

    def test_its_scope_is_the_gates_scope(self) -> None:
        """Two enumerations of "what changed" would drift; this pins them equal."""
        (self.repo / "touched.py").write_text(FORMAT_ERROR, encoding="utf-8")
        (self.repo / "also_touched.py").write_text(CLEAN, encoding="utf-8")

        base = self.git("merge-base", "origin/main", "HEAD").stdout.strip()
        listed = subprocess.run(
            ["bash", "scripts/ruff_changed.sh", "--list", base],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()

        dry = self.run_fixer("--dry-run")
        self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
        for path in listed:
            self.assertIn(path, dry.stdout, f"{path} có trong cổng mà fixer bỏ qua")

    def test_nothing_to_fix_is_not_reported_as_a_fix(self) -> None:
        result = self.run_fixer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("không đổi file Python nào", result.stdout)


class ItStaysQuietWhenItPasses(TeachingHarness):
    def test_a_clean_change_prints_no_teaching_block(self) -> None:
        """A lesson printed on every run is a banner, and banners go unread.

        The four explanations are worth their screen space precisely because
        they only appear at the moment somebody is stuck.
        """
        base = self.base()
        self.write("touched_clean.py", CLEAN)

        result = self.run_gate(base)
        self.assertEqual(result.returncode, 0, self.output(result))
        text = self.output(result)
        self.assertNotIn(BLOCK_START, text)
        self.assertNotIn("make ruff-fix", text)


if __name__ == "__main__":
    unittest.main()
