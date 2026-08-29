"""The stack has to hand the API the key that hides telephone numbers.

Sibling of `test_stack_carries_gemini_key.py`, and it exists for the same
measured reason: Compose forwards NOTHING from the host by itself. A variable
crosses into a container only because a service lists it. The Gemini key was
missing from that list for weeks and nothing looked wrong -- API up, /healthz
200, every screen rendering, and the hero feature answering `422` in 2.5ms.

This key fails louder, which is deliberate. Without it `POST
/identity/person-id` answers 503 and nobody signs in. The alternative -- a
default key committed here, or a fallback to the unkeyed digest -- is
bug-140342 itself: `people.id` was FNV-1a of the number, and a group member
could enumerate 5x10^8 Vietnamese mobile numbers and read everybody else's.
Measured at 257,316 candidates/second on one core.
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
COMPOSE = REPO_ROOT / "docker-compose.yml"
KEY = "MOBILE_PERSON_ID_KEY"


class TheComposeFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = COMPOSE.read_text(encoding="utf-8")

    def test_the_api_service_passes_the_key_the_deriver_reads(self):
        self.assertIn(f"{KEY}: ${{{KEY}:-}}", self.text)

    def test_the_value_is_interpolated_from_the_host_not_written_down(self):
        """A literal here would be a committed secret AND a public key.

        The whole fix is that the attacker does not hold the key. Writing one
        into a tracked file hands it to everybody who can clone.
        """

        for line in self.text.splitlines():
            if KEY in line and ":" in line and not line.strip().startswith("#"):
                self.assertIn("${", line, line)

    def test_the_unset_case_interpolates_to_empty_rather_than_erroring(self):
        """`${KEY:-}` and not `${KEY:?}`.

        A stack that refuses to come up takes Postgres and the API away from
        every other worktree on this machine, none of which needs this key.
        """

        self.assertNotIn(f"${{{KEY}:?", self.text)

    def test_the_key_is_not_in_the_shared_anchor(self):
        """`migrate` and `seed` derive no ids; a secret goes where it is used."""

        anchor = self.text.split("services:", 1)[0]
        self.assertNotIn(KEY, anchor)


class TheEnvExampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")

    def test_it_documents_the_name_the_code_reads(self):
        """#89's scar, and the reason that PR exists at all.

        `.env.example` named MOBILE_GEMINI_API_KEY while the code read
        GEMINI_API_KEY, so anybody who followed the file exactly ended up with
        a key that looked set and was never read.
        """

        self.assertRegex(self.text, rf"(?m)^{KEY}=")

    def test_it_carries_no_key_shaped_value(self):
        """An example file with a real-looking key gets copied and used."""

        for line in self.text.splitlines():
            if line.startswith(f"{KEY}="):
                self.assertEqual(line, f"{KEY}=")

    def test_it_tells_the_reader_to_generate_rather_than_invent(self):
        """A key somebody thought up is a key somebody can guess, and guessing
        it returns the whole reverse map at once."""

        self.assertIn("secrets.token_urlsafe", self.text)


class TheIdentityKeyCheckerTests(unittest.TestCase):
    """The warning, run for real, without Docker."""

    SCRIPT = REPO_ROOT / "scripts" / "check_identity_key.sh"

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="id-key-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "scripts").mkdir()
        self.script = self.root / "scripts" / "check_identity_key.sh"
        shutil.copy2(self.SCRIPT, self.script)
        shutil.copy2(
            REPO_ROOT / "scripts" / "env_value.sh",
            self.root / "scripts" / "env_value.sh",
        )

    def run_check(self, *args: str, key=None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.pop(KEY, None)
        if key is not None:
            env[KEY] = key
        return subprocess.run(
            [str(self.script), *args],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def said(self, *args: str, **kwargs) -> str:
        result = self.run_check(*args, **kwargs)
        return result.stdout + result.stderr

    def test_a_missing_key_names_the_variable(self):
        self.assertIn(KEY, self.said())

    def test_a_missing_key_says_what_actually_breaks(self):
        """ "MOBILE_PERSON_ID_KEY is unset" alone tells nobody what to expect."""

        self.assertIn("đăng nhập", self.said().lower())

    def test_a_missing_key_warns_rather_than_refusing(self):
        self.assertEqual(self.run_check().returncode, 0)

    def test_a_present_key_produces_no_output_at_all(self):
        self.assertEqual(self.said(key="k" * 40), "")

    def test_a_short_key_is_treated_as_a_problem(self):
        """Set-but-too-short fails at the first sign-in with the same 503.

        Being told "it is set" while the door is shut is the confusion this
        family of scripts exists to remove.
        """

        said = self.said(key="k" * 31)
        self.assertNotEqual(said, "")
        self.assertIn("32", said)

    def test_the_key_value_is_never_printed(self):
        sentinel = "SECRET-DO-NOT-LEAK-" + "z" * 20
        self.assertNotIn(sentinel, self.said(key=sentinel[:10]))

    def test_the_warning_goes_to_stderr_so_a_piped_build_still_shows_it(self):
        self.assertEqual(self.run_check().stdout, "")
        self.assertNotEqual(self.run_check().stderr, "")

    def test_the_brief_form_still_names_the_variable(self):
        self.assertIn(KEY, self.said("--brief"))

    def test_a_key_that_only_dot_env_knows_about_is_not_missing(self):
        """The regression that made the Gemini check untrustworthy.

        Someone who did exactly what the warning told them -- write it to
        `.env` -- was warned again anyway. A gate that fires on correct
        behaviour gets switched off.
        """

        (self.root / ".env").write_text(f"{KEY}=" + "k" * 40 + "\n", encoding="utf-8")
        self.assertEqual(self.said(), "")

    def test_a_short_key_in_dot_env_is_still_caught(self):
        (self.root / ".env").write_text(f"{KEY}=short\n", encoding="utf-8")
        self.assertNotEqual(self.said(), "")

    def test_a_shell_variable_beats_dot_env_the_way_compose_does(self):
        (self.root / ".env").write_text(f"{KEY}=" + "k" * 40 + "\n", encoding="utf-8")
        self.assertNotEqual(self.said(key=""), "")


class TheMakefileTests(unittest.TestCase):
    def test_make_up_runs_the_identity_check(self):
        """Before `docker build`, not after: a build takes minutes and a
        warning printed afterwards has scrolled away."""

        text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
        up = text.split("\nup:", 1)[1].split("\ndown:", 1)[0]
        self.assertIn("IDENTITY_KEY_CHECK", up)

        recipe = [line for line in up.splitlines() if line.startswith("\t")]
        build_at = next(
            (i for i, line in enumerate(recipe) if "up -d --build" in line), None
        )
        check_at = next(
            (i for i, line in enumerate(recipe) if "IDENTITY_KEY_CHECK" in line), None
        )
        self.assertIsNotNone(build_at)
        self.assertIsNotNone(check_at)
        self.assertLess(check_at, build_at)


class NoUnkeyedDerivationSurvivesTests(unittest.TestCase):
    """The old algorithm must be gone, not merely unused.

    A dead copy of a reversible derivation is a live one as soon as somebody
    imports it "just for the tests".
    """

    FNV_PRIME = "0x100000001b3"
    FNV_OFFSET = "0xcbf29ce484222325"

    def test_the_client_no_longer_carries_the_hash(self):
        source = (REPO_ROOT / "apps" / "mobile" / "src").rglob("*.ts*")
        for path in source:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(self.FNV_PRIME, text, str(path))
            self.assertNotIn(self.FNV_OFFSET, text, str(path))

    def test_no_source_file_derives_an_id_without_a_key(self):
        """`hmac` or nothing, in the module that mints person ids."""

        deriver = (
            REPO_ROOT / "services" / "api" / "app" / "api" / "person_identity.py"
        ).read_text(encoding="utf-8")
        body = deriver.split("def derive_person_id", 1)[1]
        self.assertIn("hmac.new", body)
        # A bare `hashlib.sha256(` inside the deriver would be the mutant this
        # module was tested against: a digest with the key argument ignored.
        self.assertIsNone(re.search(r"\n    digest = hashlib\.", body), body)


if __name__ == "__main__":
    unittest.main()
