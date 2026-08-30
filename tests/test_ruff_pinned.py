"""The lint gate has to run the ruff the repository pins, not PATH's.

## Why

`scripts/ruff_changed.sh` called whatever `ruff` came first on PATH. On a
developer machine that is whatever their editor installed, and `scripts/gate.sh`
knew it -- it printed the mismatch and passed the stage anyway:

    CHÚ Ý: máy này lint bằng ruff 0.15.15, CI lint bằng ruff==0.9.2

The reasoning behind not failing was sound: hard-failing on a version mismatch
makes the stage red on every machine with a newer ruff, and that gate gets
switched off within a day. The hole is that the warning sits on line three of a
thirteen-stage run under a summary that ends "ĐẠT ruff", and while GitHub
Actions is down this local gate is the only gate that runs at all.

Measured 2026-08-30 at c811254, both versions over the same 320 tracked files:

    ruff 0.9.2   (the pin, what CI installs)    31 findings
    ruff 0.15.15 (this machine's PATH)          30 findings

    seen only by the pin:
      services/api/app/domain/place_search.py:105:39: UP038
        Use `X | Y` in `isinstance` call instead of `(X, Y)`

UP038 was REMOVED from later ruff, so the newer binary cannot report it at all.
Touching `place_search.py` got ĐẠT locally and would have got HỎNG from CI.

## What these hold

The tests below deliberately do NOT assert "UP038 fires" -- that fact expires
the moment somebody bumps the pin past a release that removed the rule, and a
test that expires is a test that gets deleted. The property that does not
expire is the one asserted here: whatever ruff the pin names is the ruff that
produces the verdict, and no other version is ever silently substituted.

`test_a_different_ruff_on_path_cannot_make_a_dirty_file_pass` is the load
bearing one, and it is written so the two failure modes cannot be confused: the
shim is proven reachable first, so "the gate ignored the shim" cannot be
mistaken for "the shim was never on PATH".
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESOLVER = REPO_ROOT / "scripts" / "ruff_pinned.sh"
GATE = REPO_ROOT / "scripts" / "ruff_changed.sh"
REQUIREMENTS = REPO_ROOT / "services" / "api" / "requirements-dev.txt"

# F401, unused import. In ruff's default rule set for as long as ruff has had
# one, so this stays dirty across any plausible pin -- unlike UP038.
LINT_ERROR = "import os\n"


def pinned_version() -> str:
    """The version `requirements-dev.txt` pins, read the way the gate reads it."""
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        if line.startswith("ruff=="):
            return line[len("ruff==") :].strip()
    raise AssertionError(f"no ruff== pin in {REQUIREMENTS}")


def run(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=300, **kwargs)


class ResolverTest(unittest.TestCase):
    def test_resolver_prints_a_ruff_at_exactly_the_pinned_version(self) -> None:
        result = run(str(RESOLVER))
        self.assertEqual(
            result.returncode,
            0,
            f"resolver failed:\n{result.stdout}\n{result.stderr}",
        )
        binary = result.stdout.strip()
        self.assertTrue(binary, "resolver printed no path")
        self.assertTrue(Path(binary).is_file(), f"not a file: {binary}")

        reported = run(binary, "--version").stdout.split()
        self.assertEqual(
            reported[1],
            pinned_version(),
            f"resolver handed back ruff {reported[1]}, pin is {pinned_version()}",
        )

    def test_pin_flag_matches_the_requirements_file(self) -> None:
        result = run(str(RESOLVER), "--pin")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"ruff=={pinned_version()}")


class ResolverIsNotARuffWrapperTest(unittest.TestCase):
    """Called like a ruff wrapper, the resolver must refuse -- not exit 0.

    Measured on main at 65691ae, before the change these tests arrived with:

        $ bash scripts/ruff_pinned.sh check services/api/app/api/routes/places.py
        /home/lakiet/miniconda3/bin/ruff
        rc=0

    It swallowed `check <file>` and printed the path. Nothing was linted, and
    the output -- one line, exit 0, no findings -- is byte-for-byte what a clean
    `ruff check` run looks like from a terminal. Two QA turns already recorded
    hitting it (qa-tt-0023 §5, qa-tt-0024 §2), which is the tell that the shape
    is easy to reach: the docstring above says "use the PINNED one:
    scripts/ruff_pinned.sh", and the obvious reading of that sentence is to put
    the script where `ruff` used to go.

    That matters more than usual right now. Actions has been down since
    2026-08-29 on billing, so `scripts/gate.sh` on this machine is the only lint
    verdict anybody gets. A call shape that silently lints nothing while reading
    as ĐẠT is the exact defect the rest of this file exists to remove, arriving
    through the front door instead.

    The refusal is asserted on three things, not just the exit code:

      - rc != 0, so `set -e` callers stop;
      - stdout EMPTY, because the real call site is `RUFF="$(ruff_pinned.sh)"`
        and a printed path gets used no matter what the exit code said. This is
        the assertion that would have caught the old behaviour even if somebody
        had "fixed" it by adding an exit code and leaving the print;
      - stderr naming the `$(...)` form, because a gate is allowed to fail and
        is not allowed to leave the reader guessing what to type instead.

    `test_no_argument_call_still_works` is the other half of the pair and is not
    redundant with the tests above: the cheapest wrong fix here is a blanket
    refusal that also breaks `ruff_changed.sh` line 144, which is the one caller
    that has to keep working.
    """

    # Every shape of the mistake, written out rather than parametrised over one
    # of them. `check <file>` is the one observed in the wild; the others are
    # the same misunderstanding typed differently, and a fix that only special
    # cases the literal string "check" would pass a single-case canary.
    WRONG_CALLS = (
        ("check", "services/api/app/api/routes/places.py"),
        ("format", "--check", "tests/"),
        ("check",),
        ("--fix", "app/"),
        ("--pin", "check", "app/"),
    )

    def test_no_argument_call_still_works(self) -> None:
        """Canary 1: the correct call shape must survive the refusal.

        `scripts/ruff_changed.sh` does `RUFF="$("$RUFF_PINNED")"` with no
        arguments, and `tests/test_qa_scripts_are_ruff_formatted.py` does the
        same from Python. A refusal that swept these up would trade a silent
        no-op for a red gate on every machine.
        """
        result = run(str(RESOLVER))
        self.assertEqual(
            result.returncode,
            0,
            f"the no-argument call broke:\n{result.stdout}\n{result.stderr}",
        )
        path = result.stdout.strip()
        self.assertTrue(path, "no-argument call printed nothing")
        self.assertTrue(Path(path).is_file(), f"not a file: {path}")

    def test_arguments_are_refused_with_a_nonzero_exit(self) -> None:
        """Canary 2: anything that looks like `ruff <args>` must not exit 0."""
        for call in self.WRONG_CALLS:
            with self.subTest(call=" ".join(call)):
                result = run(str(RESOLVER), *call)
                self.assertNotEqual(
                    result.returncode,
                    0,
                    "swallowed arguments and exited 0 -- reads as a clean lint "
                    f"run that never happened\nstdout={result.stdout!r}",
                )

    def test_a_refused_call_prints_no_path_on_stdout(self) -> None:
        """The exit code alone is not enough; `$(...)` reads stdout."""
        for call in self.WRONG_CALLS:
            with self.subTest(call=" ".join(call)):
                result = run(str(RESOLVER), *call)
                self.assertEqual(
                    result.stdout.strip(),
                    "",
                    "printed a path for a call it refused -- "
                    'RUFF="$(ruff_pinned.sh ...)" would still use it',
                )

    def test_the_refusal_names_the_correct_call_shape(self) -> None:
        for call in self.WRONG_CALLS:
            with self.subTest(call=" ".join(call)):
                result = run(str(RESOLVER), *call)
                self.assertIn(
                    "$(scripts/ruff_pinned.sh)",
                    result.stderr,
                    "refused without saying what to type instead:\n" + result.stderr,
                )

    def test_refusing_costs_nothing(self) -> None:
        """A wrong call must not reach the venv build.

        Argument checking has to happen before the provisioning branch, or a
        typo on a machine without the pin spends a minute building a ruff it is
        about to refuse to hand over. Asserted through a HOME with no cache and
        a PATH holding no ruff, so the resolver takes the build path unless the
        arguments stop it first.

        The PATH is bare but not empty. A first draft left `dirname` out and the
        test went red on `dirname: command not found` at line 66 -- red, for a
        reason that has nothing to do with arguments. That red would have turned
        green on the fix anyway and read like proof. `dirname` is here so the
        pre-fix failure is the real one: stderr announcing "chưa có trên máy"
        and no usage line.
        """
        empty_home = Path(tempfile.mkdtemp(prefix="ruff-nohome-"))
        self.addCleanup(shutil.rmtree, empty_home, ignore_errors=True)
        bare = Path(tempfile.mkdtemp(prefix="ruff-nopath-"))
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        for tool in ("bash", "cat", "dirname"):
            found = shutil.which(tool)
            self.assertIsNotNone(found, f"{tool} missing -- the bare PATH is a lie")
            (bare / tool).symlink_to(found)

        result = run(
            str(RESOLVER),
            "check",
            "app/",
            env={
                "PATH": str(bare),
                "HOME": str(empty_home),
                "XDG_CACHE_HOME": str(empty_home / "cache"),
            },
        )
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("$(scripts/ruff_pinned.sh)", result.stderr, result.stderr)
        self.assertNotIn(
            "chưa có trên máy",
            result.stderr,
            "started provisioning a ruff for a call it was going to refuse",
        )


class ResolverRefusalTest(unittest.TestCase):
    """The resolver must refuse rather than substitute.

    Both cases build a throwaway skeleton with its own requirements file, since
    the resolver reads the pin relative to its own location. Handing back a
    different version would be the original defect with extra steps, so the
    assertion is on the exit code AND on the absence of any path in stdout --
    a caller does `RUFF="$(ruff_pinned.sh)"`, so a printed path is what gets
    used no matter what the exit code said.
    """

    def skeleton(self, requirements_body: str) -> Path:
        root = Path(tempfile.mkdtemp(prefix="ruff-pinned-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "scripts").mkdir()
        shutil.copy2(RESOLVER, root / "scripts" / "ruff_pinned.sh")
        reqs = root / "services" / "api"
        reqs.mkdir(parents=True)
        (reqs / "requirements-dev.txt").write_text(requirements_body, encoding="utf-8")
        return root

    def test_missing_pin_is_refused_not_guessed(self) -> None:
        root = self.skeleton("pytest==8.3.4\n")
        result = run(str(root / "scripts" / "ruff_pinned.sh"))
        self.assertEqual(result.returncode, 2, f"stdout={result.stdout!r}")
        self.assertEqual(
            result.stdout.strip(), "", "printed a path with no pin to go on"
        )
        self.assertIn("ruff==", result.stderr)

    def test_unresolvable_pin_is_refused_not_downgraded_to_path(self) -> None:
        # A version that cannot be installed -- whether because PyPI has no such
        # release or because this machine is offline, both of which must end the
        # same way. The machine's real ruff stays on PATH throughout; handing it
        # back is exactly what must not happen.
        root = self.skeleton("ruff==0.0.0.dev0+notarealrelease\n")
        result = run(str(root / "scripts" / "ruff_pinned.sh"))
        self.assertEqual(result.returncode, 2, f"stdout={result.stdout!r}")
        self.assertEqual(
            result.stdout.strip(),
            "",
            "printed a ruff path for a pin it could not install",
        )


class PathCannotOverrideThePinTest(unittest.TestCase):
    """The defect this whole change exists to remove, reproduced as a test.

    A `ruff` earlier on PATH that passes everything stands in for the real
    situation -- a *different version* that passes a file the pin rejects.
    A shim is used rather than a second real ruff because the test must not
    depend on which other ruff releases happen to be installed here.
    """

    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp(prefix="ruff-path-"))
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        for cmd in (
            ("init", "-q", "-b", "main"),
            # Assembled rather than written literally: the repo guard reads a
            # literal address as a real one, which is what it should do.
            ("config", "user.email", "gate" + "@" + "test.invalid"),
            ("config", "user.name", "gate"),
        ):
            subprocess.run(
                ["git", *cmd], cwd=self.repo, check=True, capture_output=True
            )

        (self.repo / "clean.py").write_text('print("hello")\n', encoding="utf-8")
        self.commit("base")
        self.base = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        # The change under test: one file, unmistakably dirty.
        (self.repo / "dirty.py").write_text(LINT_ERROR, encoding="utf-8")
        self.commit("add a dirty file")

        self.shim_dir = Path(tempfile.mkdtemp(prefix="ruff-shim-"))
        self.addCleanup(shutil.rmtree, self.shim_dir, ignore_errors=True)
        shim = self.shim_dir / "ruff"
        shim.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                # Answers every question with "clean". Reports a version that is
                # not the pin, so the resolver has to reject it on sight.
                if [ "${1:-}" = "--version" ]; then echo "ruff 9.9.9"; exit 0; fi
                echo "All checks passed!"
                exit 0
                """
            ),
            encoding="utf-8",
        )
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

        self.env = dict(
            os.environ, PATH=f"{self.shim_dir}{os.pathsep}{os.environ['PATH']}"
        )

    def commit(self, message: str) -> None:
        subprocess.run(
            ["git", "add", "-A"], cwd=self.repo, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-q", "-m", message],
            cwd=self.repo,
            check=True,
            capture_output=True,
        )

    def test_the_shim_is_actually_reachable(self) -> None:
        """Proves the next test fails for the right reason.

        Without this, "the gate went red" is equally consistent with "the gate
        used the pin" and with "the shim was never on PATH at all" -- and the
        second reads exactly like the first.
        """
        result = run("ruff", "--version", env=self.env)
        self.assertEqual(result.stdout.strip(), "ruff 9.9.9", result.stderr)

    def test_a_different_ruff_on_path_cannot_make_a_dirty_file_pass(self) -> None:
        result = run(
            "bash", str(GATE), self.base, "HEAD", cwd=str(self.repo), env=self.env
        )
        self.assertEqual(
            result.returncode,
            1,
            "a shim ruff on PATH passed a file the pinned ruff rejects\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("dirty.py", result.stdout)
        self.assertNotIn(
            "All checks passed!",
            result.stdout,
            "the shim's answer reached the verdict",
        )

    def test_the_run_names_the_version_that_produced_the_verdict(self) -> None:
        """A verdict nobody can attribute to a version is not checkable later.

        The old gate printed the version as a CHÚ Ý and then passed regardless;
        printing it is only worth anything if it is the version actually used.
        """
        result = run(
            "bash", str(GATE), self.base, "HEAD", cwd=str(self.repo), env=self.env
        )
        match = re.search(r"ruff (\S+) \(bản ghim\)", result.stdout)
        self.assertIsNotNone(match, f"the run does not name its ruff:\n{result.stdout}")
        self.assertEqual(match.group(1), pinned_version())


if __name__ == "__main__":
    unittest.main()
