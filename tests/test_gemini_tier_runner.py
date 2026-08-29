"""The live model tier must run somewhere, and must not be able to go quiet.

## Why

`services/api/tests/live` is 34 cases and it is the only tier in this
repository that calls a real model. "AI là THẬT" is the first of the two things
settled with the leader; the demo path is the model end to end -- it suggests a
place, reads the bill, names every item, and the split follows. Every other test
of those features runs against a fake reader and a fake suggester, which proves
orchestration and proves nothing about the model.

Measured on this branch's merge base, it ran nowhere at all: no workflow job, no
`scripts/gate.sh` stage, no Makefile target set either of the two variables that
turn the tier on. `python3 -m pytest services/api/tests tests -q` reported
`1278 passed, 285 skipped`, and 33 of those skips were this tier:

    23  live Gemini tier: needs GEMINI_API_KEY and MOBILE_REQUIRE_GEMINI_TESTS=1
    10  live Gemini test is opt-in: set MOBILE_LIVE_GEMINI=1

A skip is not a pass. This is the same shape that has now bitten this repository
four times -- a detector with no browser returning `[]` and exit 0, a postgres
tier reporting 147 skips, a migration that switched off the loggers a test then
searched for a secret in, and this.

So these tests hold two lines, and the second is the one that matters:

  - The tier is REACHABLE. `scripts/gate.sh` has a stage that delegates to
    `scripts/gemini_tier.sh`, `make test-ai` calls it, and the runner finds the
    key by itself instead of demanding the caller export one.
  - The tier cannot go QUIET. `MOBILE_REQUIRE_GEMINI_TESTS` does not require
    anything -- with no key the cases skip even when it is set to 1 -- so the
    runner counts what actually ran and calls a skipped case a failure.
    `test_a_run_where_everything_skipped_is_red` proves that against the real
    script, with no key and no network.

## What this does NOT prove

It does not run the tier against the model. `make test-ai` does that, and its
evidence is a count of passing cases, not this file. Every test here is
deliberately hermetic: it uses a fake key and a fixture path that does not
exist, so it costs no quota and cannot fail because a rate limit was hit. That
is the point -- a file that guards the live tier must not itself become a test
that goes red when the network is slow, or it gets switched off and is not there
on the day it would have been right.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "gemini_tier.sh"
GATE = REPO_ROOT / "scripts" / "gate.sh"
MAKEFILE = REPO_ROOT / "Makefile"

# Never a real key. Long enough not to collide with ordinary output, and shaped
# so that a leak is unmistakable when it shows up in a diff or a pull request.
FAKE_KEY = "NOT-A-REAL-KEY-2f4b8c1e9a7d"


def _run(args: list[str], env_extra: dict[str, str], timeout: int = 300):
    env = dict(os.environ)
    env.update(env_extra)
    return subprocess.run(
        [str(RUNNER), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class RunnerIsWiredIn(unittest.TestCase):
    def test_runner_exists_and_is_executable(self) -> None:
        self.assertTrue(RUNNER.is_file(), f"{RUNNER} không tồn tại")
        self.assertTrue(
            os.access(RUNNER, os.X_OK),
            "scripts/gemini_tier.sh phải chạy được trực tiếp (chmod +x)",
        )

    def test_gate_delegates_to_the_runner(self) -> None:
        gate = GATE.read_text(encoding="utf-8")
        body = gate.split("do_gemini()", 1)
        self.assertEqual(len(body), 2, "scripts/gate.sh mất hàm do_gemini")
        stage = body[1].split("\n}", 1)[0]
        self.assertIn(
            "scripts/gemini_tier.sh",
            stage,
            "chặng gemini phải gọi scripts/gemini_tier.sh, không tự chế lệnh riêng",
        )

    def test_the_gate_lists_the_stage(self) -> None:
        # Asked of the gate rather than grepped out of it: a STAGES array that
        # still matches a regex after the script stopped working is exactly the
        # kind of evidence this directory refuses.
        result = subprocess.run(
            ["bash", str(GATE), "--list"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "gemini",
            result.stdout,
            "scripts/gate.sh --list không nhắc tới chặng gemini",
        )

    def test_make_exposes_the_tier(self) -> None:
        makefile = MAKEFILE.read_text(encoding="utf-8")
        self.assertIn("test-ai:", makefile, "Makefile thiếu target test-ai")
        self.assertIn(
            "scripts/gemini_tier.sh",
            makefile,
            "target test-ai phải gọi scripts/gemini_tier.sh",
        )
        phony = next(
            line for line in makefile.splitlines() if line.startswith(".PHONY")
        )
        self.assertIn("test-ai", phony, "test-ai phải nằm trong .PHONY")

    def test_runner_sets_both_flags(self) -> None:
        # Two different variables guard this tier: the places and suggestion
        # suites read MOBILE_REQUIRE_GEMINI_TESTS, the receipt suite reads
        # MOBILE_LIVE_GEMINI. Setting one runs half the tier and looks complete,
        # which is worse than running none of it.
        source = RUNNER.read_text(encoding="utf-8")
        for flag in ("MOBILE_REQUIRE_GEMINI_TESTS=1", "MOBILE_LIVE_GEMINI=1"):
            self.assertIn(
                flag,
                source,
                f"runner không đặt {flag} — một nửa tầng sẽ bỏ qua mà vẫn xanh",
            )


class RunnerCannotGoQuiet(unittest.TestCase):
    def test_a_run_where_everything_skipped_is_red(self) -> None:
        """The defect, reproduced and then refused.

        `pytest tests/live` exits 0 when every case skips. Here the receipt
        suite is pointed at a mockup that does not exist, so all ten cases skip
        before any network call is made -- the run costs nothing and needs no
        key that works. Plain pytest answers 0. The runner must answer non-zero,
        and must name the cases that did not run.
        """
        result = _run(
            ["-q", "-k", "receipt"],
            {
                "GEMINI_API_KEY": FAKE_KEY,
                "MOBILE_RECEIPT_MOCKUP": "/nonexistent/mockup-for-this-test.png",
            },
        )
        combined = result.stdout + result.stderr
        self.assertNotEqual(
            result.returncode,
            0,
            "mọi ca đều bỏ qua mà vẫn thoát 0 — đúng lỗi 'bỏ qua đọc thành xanh'"
            f"\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}",
        )
        self.assertIn(
            "BỎ QUA",
            combined,
            "runner phải nói ra rằng có ca bỏ qua, không chỉ thoát khác 0",
        )
        self.assertIn(
            "test_it_finds_eight_items",
            combined,
            "runner phải kể tên ca không chạy, nếu không người đọc phải tự đi tìm",
        )

    def test_no_key_anywhere_is_could_not_run_not_failed(self) -> None:
        """Exit 2 and exit 1 mean different things and `scripts/gate.sh` reads
        the difference: 2 is an absence it reports as BỎ QUA with a reason, 1 is
        a red stage. Somebody working on money or migrations has no use for the
        key, and a gate that goes red on them gets switched off.

        Run against a copy outside any checkout, so no `.env` -- this one's or
        the main worktree's -- can be found.
        """
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp) / "checkout"
            (fake_root / "scripts").mkdir(parents=True)
            for name in ("gemini_tier.sh", "env_value.sh"):
                shutil.copy(REPO_ROOT / "scripts" / name, fake_root / "scripts" / name)
            env = {
                key: value
                for key, value in os.environ.items()
                if key not in ("GEMINI_API_KEY", "MOBILE_ENV_FILE")
            }
            result = subprocess.run(
                [str(fake_root / "scripts" / "gemini_tier.sh"), "--check"],
                cwd=str(fake_root),
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
        self.assertEqual(
            result.returncode,
            2,
            "không có khoá ở đâu cả thì phải là 'không chạy được' (2), "
            f"không phải hỏng (1) hay đạt (0)\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn(
            "GEMINI_API_KEY",
            result.stdout + result.stderr,
            "phải nói ra tên biến còn thiếu",
        )


class TheKeyNeverReachesTheScreen(unittest.TestCase):
    """The one rule with no exceptions.

    CLAUDE.md and the role brief both say it: the key is never committed, never
    logged, never put in an error message. Lanes paste gate output into pull
    requests as evidence, so "what this script prints" and "what ends up on
    GitHub" are the same question.
    """

    def test_check_mode_never_prints_the_value(self) -> None:
        result = _run(["--check"], {"GEMINI_API_KEY": FAKE_KEY}, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(
            FAKE_KEY,
            result.stdout + result.stderr,
            "--check in ra giá trị khoá",
        )

    def test_the_key_is_stripped_out_of_the_tier_output(self) -> None:
        """A real leak path, driven end to end rather than asserted by reading.

        pytest quotes the values it was given back into its skip reasons, so
        pointing the fixture at a path built out of the key makes the tier
        print the key on two separate routes: the pytest pipe, and the runner's
        own list of skipped cases. The second one was unfiltered when this test
        was written, and this is what found it.
        """
        result = _run(
            ["-q", "-k", "receipt"],
            {
                "GEMINI_API_KEY": FAKE_KEY,
                "MOBILE_RECEIPT_MOCKUP": f"/nonexistent/{FAKE_KEY}.png",
            },
        )
        combined = result.stdout + result.stderr
        self.assertNotIn(
            FAKE_KEY,
            combined,
            "khoá lọt ra output của tầng — đây là thứ được dán vào PR làm bằng chứng"
            f"\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}",
        )
        self.assertIn(
            "<GEMINI_API_KEY>",
            combined,
            "không thấy dấu vết đã che — kiểm tra xem bộ lọc có thật sự chạy không",
        )

    def test_the_key_is_never_passed_on_a_command_line(self) -> None:
        """`ps` is world-readable and this machine runs five lanes at once, so a
        key in argv is a key every other process can read. Checked by reading
        the script: there is no way to observe the absence of an argument."""
        source = RUNNER.read_text(encoding="utf-8")
        code = "\n".join(
            line for line in source.splitlines() if not line.lstrip().startswith("#")
        )
        for forbidden in ('sed "s/$KEY', "sed 's/$KEY", "--key=", '-c "$KEY'):
            self.assertNotIn(
                forbidden,
                code,
                f"runner có vẻ đưa khoá lên dòng lệnh qua {forbidden!r}",
            )


if __name__ == "__main__":
    unittest.main()
