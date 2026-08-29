"""What the local-stack Makefile is allowed to destroy, and when.

`docker-compose.yml` pins one project name for the whole machine on purpose:
every worktree talks to the same Postgres and the same API on 8099, so a guest
link printed in one worktree opens in another. The cost of that choice is that
`make clean` is not local to the caller -- `docker compose down -v` from any
directory deletes the volume every lane is working against.

These tests pin the guard on that. They never start Docker: `COMPOSE` is
overridden with a stub that records the argv it was called with, so a test that
fails still leaves everybody's database alone. The Docker-backed cases at the
bottom check the one thing a stub cannot -- how Compose itself resolves the
project name -- and say so out loud when they skip.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Written by the stub, one line per invocation. `make` runs several recipe
# lines, so the log is a list and the assertions look at all of it. The exit
# code is a knob so a test can play "docker refused" without a busy port.
STUB = """#!/bin/sh
printf '%s\\n' "$*" >> "$COMPOSE_CALL_LOG"
exit EXIT_CODE
"""


class MakeHarness(unittest.TestCase):
    def setUp(self) -> None:
        self.workdir = Path(tempfile.mkdtemp(prefix="make-targets-"))
        self.addCleanup(shutil.rmtree, self.workdir, ignore_errors=True)
        self.stub = self.workdir / "compose-stub.sh"
        self.set_stub_exit(0)
        self.log = self.workdir / "calls.log"

    def set_stub_exit(self, code: int) -> None:
        self.stub.write_text(STUB.replace("EXIT_CODE", str(code)), encoding="utf-8")
        self.stub.chmod(0o755)

    def run_make(self, *targets: str, **overrides: str) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["COMPOSE_CALL_LOG"] = str(self.log)
        # A leaked COMPOSE_PROJECT_NAME from the caller's shell would silently
        # change what the guard is guarding.
        env.pop("COMPOSE_PROJECT_NAME", None)
        env.pop("MOBILE_PROJECT", None)
        args = ["make", *targets, f"COMPOSE={self.stub}"]
        args += [f"{key}={value}" for key, value in overrides.items()]
        return subprocess.run(
            args, cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120
        )

    def compose_calls(self) -> list[str]:
        if not self.log.exists():
            return []
        return [
            line for line in self.log.read_text(encoding="utf-8").splitlines() if line
        ]

    def assertComposeCalled(self, fragment: str) -> None:
        calls = self.compose_calls()
        self.assertTrue(
            any(fragment in call for call in calls),
            f"no compose call contained {fragment!r}; calls were {calls}",
        )

    def assertNothingDestroyed(self) -> None:
        destructive = [call for call in self.compose_calls() if "-v" in call.split()]
        self.assertEqual(
            destructive,
            [],
            "make issued a volume-deleting compose call it should have refused",
        )


class CleanIsGuardedTests(MakeHarness):
    def test_clean_refuses_when_nobody_confirmed(self):
        result = self.run_make("clean")

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNothingDestroyed()

    def test_clean_refusal_names_the_project_it_would_have_destroyed(self):
        result = self.run_make("clean")

        # The refusal has to say *what* would die, or the next person just
        # re-runs it with whatever flag makes the message go away.
        self.assertIn("mobile-local", result.stdout + result.stderr)

    def test_clean_refuses_a_confirmation_that_is_not_the_project_name(self):
        result = self.run_make("clean", CONFIRM="yes")

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNothingDestroyed()

    def test_clean_destroys_only_after_the_project_name_is_typed(self):
        result = self.run_make("clean", CONFIRM="mobile-local")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertComposeCalled("down -v")

    def test_confirmation_tracks_the_overridden_project_not_a_fixed_string(self):
        """`MOBILE_PROJECT=qa47 make clean CONFIRM=mobile-local` must refuse.

        Otherwise the muscle memory built on the default name would blow away
        an isolated stack the caller deliberately named something else.
        """

        wrong = self.run_make("clean", MOBILE_PROJECT="qa47", CONFIRM="mobile-local")
        self.assertNotEqual(wrong.returncode, 0, wrong.stdout + wrong.stderr)
        self.assertNothingDestroyed()

        right = self.run_make("clean", MOBILE_PROJECT="qa47", CONFIRM="qa47")
        self.assertEqual(right.returncode, 0, right.stdout + right.stderr)
        self.assertComposeCalled("down -v")


class NonDestructiveTargetsTests(MakeHarness):
    def test_down_keeps_the_volume_and_needs_no_confirmation(self):
        result = self.run_make("down")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertComposeCalled("down")
        self.assertNothingDestroyed()

    def test_down_says_the_stack_is_shared_by_every_worktree(self):
        result = self.run_make("down")

        self.assertIn("mobile-local", result.stdout + result.stderr)

    def test_help_warns_that_clean_reaches_past_this_worktree(self):
        result = self.run_make("help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = (result.stdout + result.stderr).lower()
        self.assertIn("clean", text)
        self.assertIn("worktree", text)


class UpFailureTests(MakeHarness):
    """A busy port is the number one way `make up` fails on this machine, and
    docker's own line for it scrolls past inside a wall of build output."""

    def test_a_failed_up_names_the_two_port_variables_that_fix_it(self):
        self.set_stub_exit(1)

        result = self.run_make("up")

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        text = result.stdout + result.stderr
        self.assertIn("MOBILE_API_PORT", text)
        self.assertIn("MOBILE_POSTGRES_PORT", text)

    def test_a_failed_up_does_not_go_on_to_seed_and_smoke(self):
        self.set_stub_exit(1)

        self.run_make("up")

        self.assertEqual(
            [call for call in self.compose_calls() if "run --rm" in call],
            [],
            "make up kept going after the stack failed to come up",
        )


def _docker_compose_available() -> bool:
    if shutil.which("docker") is None:
        return False
    probe = subprocess.run(
        ["docker", "compose", "version"], capture_output=True, text=True
    )
    return probe.returncode == 0


class ComposeProjectNameTests(unittest.TestCase):
    """Only Compose can answer how Compose resolves a project name."""

    def setUp(self) -> None:
        if not _docker_compose_available():
            self.skipTest(
                "docker compose not available -- project-name resolution unverified"
            )

    def resolved(self, **env_overrides: str) -> dict:
        env = dict(os.environ)
        env.pop("COMPOSE_PROJECT_NAME", None)
        env.pop("MOBILE_PROJECT", None)
        env.update(env_overrides)
        result = subprocess.run(
            ["docker", "compose", "config", "--format", "json"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_default_project_stays_the_one_shared_stack(self):
        self.assertEqual(self.resolved()["name"], "mobile-local")

    def test_mobile_project_env_var_moves_the_whole_stack(self):
        config = self.resolved(MOBILE_PROJECT="qa-probe")

        self.assertEqual(config["name"], "qa-probe")
        # Same knob has to move the volume too, or an "isolated" run still
        # shares the database it was supposed to leave alone.
        self.assertTrue(
            any(
                volume.get("name", "").startswith("qa-probe")
                for volume in config.get("volumes", {}).values()
            ),
            config.get("volumes"),
        )

    def test_config_renders_with_no_unset_variable_warnings(self):
        env = dict(os.environ)
        env.pop("COMPOSE_PROJECT_NAME", None)
        env.pop("MOBILE_PROJECT", None)
        result = subprocess.run(
            ["docker", "compose", "config"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("variable is not set", result.stderr)


if __name__ == "__main__":
    unittest.main()
