"""`make up` has to hand the AI credential to the container, or say it cannot.

Compose does not forward the host environment into a container. Only what a
service lists under ``environment:`` crosses that boundary. ``x-api-env``
listed ``MOBILE_DATABASE_URL`` and nothing else, so every stack built by
``make up`` -- including the shared ``mobile-local`` one the whole team calls --
ran the receipt reader with no key.

Nothing looked wrong. The API was up, ``/healthz`` answered 200, every screen
rendered. Only the hero feature was silently dead, and it failed in the one
shape that reads as the user's own fault (see
``services/api/tests/api/test_receipts_scan_unconfigured.py``).

Two independent things are pinned here, because fixing either alone still
ships a demo that dies:

  1. the variable crosses into the container, and its value comes from the
     host rather than from a committed literal;
  2. a stack built without the key says so at build time, naming the variable,
     instead of letting the first bill photo discover it.

The YAML cases parse the file directly so they gate on a machine with no
Docker. The Compose-backed cases check the one thing a parser cannot -- how
Compose itself interpolates -- and skip out loud when Docker is absent.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

# The name the code actually reads. `services/api/app/api/vision_gemini.py`
# does `os.environ["GEMINI_API_KEY"]`; every other spelling is a variable
# nobody consumes, which is worse than an unset one because it looks configured.
KEY = "GEMINI_API_KEY"

STUB = """#!/bin/sh
printf '%s\\n' "$*" >> "$COMPOSE_CALL_LOG"
exit 0
"""


def _compose_document() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


class TheKeyReachesTheContainerTests(unittest.TestCase):
    """Parsed straight from the file; no Docker needed to run these."""

    def setUp(self) -> None:
        self.document = _compose_document()

    def api_environment(self) -> dict:
        return dict(self.document["services"]["api"]["environment"])

    def test_the_api_service_passes_the_key_the_reader_reads(self):
        self.assertIn(KEY, self.api_environment())

    def test_the_value_is_interpolated_from_the_host_not_written_down(self):
        """A literal here would be a committed credential. It must be a `${...}`."""
        value = self.api_environment()[KEY]
        self.assertRegex(str(value), r"^\$\{" + KEY + r"[:\-}]")

    def test_no_credential_shaped_literal_is_committed_in_the_file(self):
        # Google API keys are `AIza` + 35 chars. Catch a paste before review does.
        text = COMPOSE_FILE.read_text(encoding="utf-8")
        self.assertIsNone(
            re.search(r"AIza[0-9A-Za-z_\-]{20,}", text),
            "docker-compose.yml looks like it contains a real API key",
        )

    def test_the_unset_case_interpolates_to_empty_rather_than_erroring(self):
        """`:?` would break `docker compose config` for everyone without a key.

        The stack is designed to survive a missing key -- the structured path
        still works. So the default is empty, and loudness is the Makefile's
        job, not an interpolation error nobody can read.
        """
        self.assertTrue(str(self.api_environment()[KEY]).startswith("${" + KEY + ":-"))

    def test_env_example_documents_the_name_the_code_reads(self):
        """`.env.example` said MOBILE_GEMINI_API_KEY. Nothing reads that name.

        Following the example file exactly produced a key under a name no code
        consumes -- a second way to get a silently AI-less stack, and the one a
        fresh clone hits first.
        """
        names = {
            line.split("=", 1)[0].strip()
            for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
            if "=" in line and not line.lstrip().startswith("#")
        }
        self.assertIn(KEY, names)

    def test_env_example_declares_nothing_under_the_name_nobody_reads(self):
        """The old name may be explained in a comment; it may not be assignable.

        Asserting on the raw text would forbid the comment that says why the
        name changed, which is the part that stops it coming back.
        """
        declarations = [
            line
            for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
            if "=" in line and not line.lstrip().startswith("#")
        ]

        self.assertEqual(
            [line for line in declarations if "MOBILE_GEMINI_API_KEY" in line], []
        )


class TheKeyCheckerTests(unittest.TestCase):
    """The warning itself, exercised directly.

    It lives in a script rather than inline in a recipe so it can be run --
    and asserted on -- without Docker and without starting the shared stack.
    """

    SCRIPT = REPO_ROOT / "scripts" / "check_ai_key.sh"

    def run_check(self, *args: str, key=None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.pop(KEY, None)
        if key is not None:
            env[KEY] = key
        return subprocess.run(
            [str(self.SCRIPT), *args],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def said(self, **kwargs) -> str:
        result = self.run_check(**kwargs)
        return result.stdout + result.stderr

    def test_a_missing_key_names_the_variable(self):
        self.assertIn(KEY, self.said())

    def test_a_missing_key_says_which_feature_goes_dark(self):
        """"GEMINI_API_KEY is unset" alone does not tell anyone what breaks."""
        self.assertIn("bill", self.said().lower())

    def test_a_missing_key_warns_rather_than_refusing(self):
        """The structured money path works without a key; do not block it.

        Hard-failing would make the local stack unusable for everyone working
        on money or migrations, which is most of the repo.
        """
        self.assertEqual(self.run_check().returncode, 0)

    def test_an_empty_key_is_treated_as_missing(self):
        """`${GEMINI_API_KEY:-}` writes an empty string, not an absent variable."""
        self.assertIn(KEY, self.said(key=""))

    def test_a_present_key_produces_no_output_at_all(self):
        """Otherwise the warning is wallpaper and stops being read."""
        self.assertEqual(self.said(key="AIzaSyFAKEfakeFAKEfakeFAKEfakeFAKEfake1"), "")

    def test_the_key_value_is_never_printed(self):
        """Naming the variable is the point. Echoing it is how keys reach logs."""
        sentinel = "AIzaSySENTINELsentinelSENTINELsentinel12"

        self.assertNotIn(sentinel, self.said(key=sentinel))

    def test_the_brief_form_still_names_the_variable(self):
        """`smoke` repeats the warning after the build, where space is short."""
        self.assertIn(KEY, self.said_from("--brief"))

    def said_from(self, *args: str) -> str:
        result = self.run_check(*args)
        return result.stdout + result.stderr

    def test_the_warning_goes_to_stderr_so_a_piped_build_still_shows_it(self):
        """`make up | tee build.log` must not swallow the one line that matters."""
        self.assertEqual(self.run_check().stdout, "")
        self.assertIn(KEY, self.run_check().stderr)


class MakeUpWarnsBeforeItBuildsTests(unittest.TestCase):
    """The criterion verbatim: warn at build time, not at the first bill photo.

    Compose is stubbed, so these never start Docker and never touch the shared
    stack. A stubbed `up` cannot reach `seed`, so what is pinned here is the
    part a stub can prove: the warning arrives BEFORE the handoff to Compose,
    early enough to interrupt a two-minute build. That the warning is also the
    last thing a real `make up` prints is checked in `TheKeyCheckerTests` plus
    the `smoke` case below.
    """

    def setUp(self) -> None:
        self.workdir = Path(tempfile.mkdtemp(prefix="gemini-key-"))
        self.addCleanup(shutil.rmtree, self.workdir, ignore_errors=True)
        self.stub = self.workdir / "compose-stub.sh"
        self.stub.write_text(STUB, encoding="utf-8")
        self.stub.chmod(0o755)
        self.log = self.workdir / "calls.log"

    def run_make(self, *targets: str, key=None, merged=False):
        env = dict(os.environ)
        env["COMPOSE_CALL_LOG"] = str(self.log)
        env.pop("COMPOSE_PROJECT_NAME", None)
        env.pop("MOBILE_PROJECT", None)
        env.pop(KEY, None)
        if key is not None:
            env[KEY] = key
        return subprocess.run(
            ["make", *targets, f"COMPOSE={self.stub}"],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if merged else subprocess.PIPE,
            text=True,
            timeout=120,
        )

    def test_a_keyless_up_names_the_missing_variable(self):
        result = self.run_make("up")

        self.assertIn(KEY, result.stdout + result.stderr)

    def test_the_warning_lands_before_compose_is_called(self):
        """After `docker build` scrolls past, nobody reads the top of the log.

        Streams are merged here rather than concatenated: the warning goes to
        stderr and the recipe's banner to stdout, so only the interleaved view
        can answer which one a person saw first.
        """
        said = self.run_make("up", merged=True).stdout
        # The recipe's own first line. The warning has to precede it.
        marker = "Project compose:"

        self.assertLess(said.index(KEY), said.index(marker))

    def test_warning_does_not_stop_the_stack_from_building(self):
        """Warn, do not refuse -- Compose still got its `up`."""
        self.run_make("up")

        self.assertIn("up -d --build", self.log.read_text(encoding="utf-8"))

    def test_a_keyless_smoke_repeats_the_warning(self):
        """`smoke` is the last thing `up` runs, so it owns the final screen."""
        result = self.run_make("smoke")

        self.assertIn(KEY, result.stdout + result.stderr)

    def test_a_key_that_is_present_produces_no_warning_in_up(self):
        result = self.run_make("up", key="AIzaSyFAKEfakeFAKEfakeFAKEfakeFAKEfake1")

        self.assertNotIn(KEY, result.stdout + result.stderr)


def _docker_compose_available() -> bool:
    if shutil.which("docker") is None:
        return False
    probe = subprocess.run(
        ["docker", "compose", "version"], capture_output=True, text=True
    )
    return probe.returncode == 0


class ComposeInterpolationTests(unittest.TestCase):
    """Only Compose can answer what Compose actually puts in the container."""

    def setUp(self) -> None:
        if not _docker_compose_available():
            self.skipTest(
                "docker compose not available -- key propagation unverified"
            )

    def rendered_api_env(self, **env_overrides: str) -> dict:
        env = dict(os.environ)
        env.pop("COMPOSE_PROJECT_NAME", None)
        env.pop("MOBILE_PROJECT", None)
        env.pop(KEY, None)
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
        config = json.loads(result.stdout)
        return dict(config["services"]["api"]["environment"])

    def test_the_host_value_lands_in_the_api_container(self):
        sentinel = "AIzaSySENTINELsentinelSENTINELsentinel12"

        self.assertEqual(self.rendered_api_env(GEMINI_API_KEY=sentinel)[KEY], sentinel)

    def test_the_variable_is_present_even_when_the_host_has_none(self):
        """Absent-vs-empty must not be two code paths inside the container."""
        self.assertEqual(self.rendered_api_env().get(KEY), "")

    def test_an_unset_key_produces_no_compose_warning(self):
        env = dict(os.environ)
        env.pop("COMPOSE_PROJECT_NAME", None)
        env.pop("MOBILE_PROJECT", None)
        env.pop(KEY, None)
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
