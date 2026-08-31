"""An empty SECRET_RULES must stop the guard, not quietly widen the allowlist.

`scripts/repo_guard.py` computes

    ALLOWLISTABLE_RULES = (CONTENT_RULES - SECRET_RULES) | {...}

at import. The subtraction is the only thing keeping `google-api-key`,
`github-token` and the two AWS rules out of the set a lane may name in
`.repo-guard-allowlist.json`. Empty `SECRET_RULES` and the subtraction removes
nothing: every credential rule becomes something a lane can pin by path and
digest, and the scanner then walks past a real key and exits 0 -- "clean".

Measured before this gate existed, by qa2's probe at
`tests/qa/qa2-080313-o-rong/do_o_rong.py`:

    nguyên vẹn : google-api-key allowlist được? False
    bảng RỖNG  : google-api-key allowlist được? True

The empty table said "no rule is a secret" with the same value that says "there
are no secret rules to protect". Only one of those two meanings is safe, and it
is not the silent one. So the cases below pin both directions:

  * table intact  -> the module loads and secrets stay unallowlistable
  * table emptied -> the module REFUSES TO LOAD, and the CLI refuses to run

Each mutation asserts it actually changed the source before it draws any
conclusion. A `str.replace` that matches nothing produces an unmutated module
that loads fine, which reads exactly like "the floor held".
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO / "scripts" / "repo_guard.py"

# The names this repository is pinned to treat as credentials. Written out here
# rather than imported from the module so that gutting the module's own floor
# cannot also gut the test that checks it -- two files must be edited in step.
PINNED_SECRET_RULES = frozenset(
    {
        "aws-access-key-id",
        "aws-secret-access-key",
        "github-token",
        "google-api-key",
    }
)

# The line that derives the allowlist. Both the module and these mutations key
# off it, so if it is ever reworded the mutations become no-ops -- which is why
# every case asserts its own mutation landed.
DERIVATION = "ALLOWLISTABLE_RULES = (CONTENT_RULES - SECRET_RULES)"


def source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


class SecretRulesFloorTests(unittest.TestCase):
    def mutate(self, old: str, new: str) -> str:
        """Return the module source with one substitution, or fail loudly."""

        original = source()
        self.assertIn(
            old, original, "mutation target is gone; this case measures nothing"
        )
        mutated = original.replace(old, new, 1)
        self.assertNotEqual(mutated, original, "mutation was a no-op")
        return mutated

    def load(self, src: str, name: str) -> dict:
        namespace: dict = {}
        exec(compile(src, name, "exec"), namespace)  # noqa: S102 - the subject
        return namespace

    def assert_refuses(self, src: str, name: str) -> str:
        """The module must raise on import. Returns the message."""

        with self.assertRaises(Exception) as caught:
            self.load(src, name)
        message = str(caught.exception)
        self.assertNotIsInstance(
            caught.exception,
            (SyntaxError, NameError),
            f"module broke instead of refusing: {message}",
        )
        self.assertIn("refuses to run", message)
        return message

    # -- the positive control: unmutated source must still load and be strict --

    def test_intact_module_loads_and_keeps_secrets_unallowlistable(self):
        namespace = self.load(source(), "repo_guard_intact")
        allowlistable = set(namespace["ALLOWLISTABLE_RULES"])
        self.assertEqual(PINNED_SECRET_RULES & allowlistable, set())
        self.assertTrue(PINNED_SECRET_RULES <= set(namespace["SECRET_RULES"]))

    def test_floor_table_itself_is_not_empty(self):
        """The anchor cannot be hollowed out in one file and stay green."""

        namespace = self.load(source(), "repo_guard_anchor")
        self.assertEqual(set(namespace["REQUIRED_SECRET_RULES"]), PINNED_SECRET_RULES)
        self.assertEqual(
            namespace["REQUIRED_SECRET_RULE_COUNT"], len(PINNED_SECRET_RULES)
        )

    # -- the case the probe found: emptying SECRET_RULES --

    def test_emptied_secret_rules_refuses_to_load(self):
        mutated = self.mutate(DERIVATION, f"SECRET_RULES = frozenset()\n{DERIVATION}")
        message = self.assert_refuses(mutated, "repo_guard_no_secret_rules")
        self.assertIn("SECRET_RULES", message)

    def test_shrunk_secret_rules_refuses_to_load(self):
        """Dropping one name is the same hole, one rule wide."""

        mutated = self.mutate(
            '    "google-api-key",\n}\nALLOWLISTABLE_RULES',
            "}\nALLOWLISTABLE_RULES",
        )
        message = self.assert_refuses(mutated, "repo_guard_partial_secret_rules")
        self.assertIn("google-api-key", message)

    # -- the floor must not be disarmable by gutting its own anchor --

    def test_emptied_anchor_refuses_to_load(self):
        mutated = self.mutate(
            "REQUIRED_SECRET_RULES = frozenset(",
            "REQUIRED_SECRET_RULES = frozenset() or frozenset(",
        )
        # `frozenset() or X` still yields X, so force a genuinely empty anchor.
        mutated = mutated.replace(
            "REQUIRED_SECRET_RULES = frozenset() or frozenset(",
            "REQUIRED_SECRET_RULES = frozenset()\n_UNUSED_REQUIRED = frozenset(",
            1,
        )
        message = self.assert_refuses(mutated, "repo_guard_no_anchor")
        self.assertIn("REQUIRED_SECRET_RULES", message)

    # -- the floor watches the consequence, not only the input --

    def test_allowlist_rewritten_to_swallow_secrets_refuses_to_load(self):
        """SECRET_RULES stays full; the derivation stops subtracting it."""

        mutated = self.mutate(DERIVATION, "ALLOWLISTABLE_RULES = (CONTENT_RULES)")
        message = self.assert_refuses(mutated, "repo_guard_no_subtraction")
        self.assertIn("allowlistable", message)

    def test_secret_rule_dropped_from_content_rules_refuses_to_load(self):
        """A secret name absent from CONTENT_RULES makes the subtraction moot."""

        mutated = self.mutate(
            '    "google-api-key",\n    "aws-access-key-id",',
            '    "aws-access-key-id",',
        )
        message = self.assert_refuses(mutated, "repo_guard_content_drift")
        self.assertIn("CONTENT_RULES", message)

    # -- "refuses to run" means the CLI, not just an import --

    def test_cli_exits_non_zero_when_secret_rules_is_empty(self):
        mutated = self.mutate(DERIVATION, f"SECRET_RULES = frozenset()\n{DERIVATION}")
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "repo_guard.py"
            script.write_text(mutated, encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(script), "tree", "HEAD"],
                cwd=REPO,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(
            completed.returncode,
            0,
            "guard scanned and reported success with an empty SECRET_RULES",
        )
        self.assertIn("refuses to run", completed.stderr)

    def test_cli_still_runs_and_exits_clean_on_the_intact_module(self):
        """The reverse case: a full table must not turn the guard red."""

        completed = subprocess.run(
            [sys.executable, str(MODULE_PATH), "tree", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"intact guard is not clean on HEAD:\n{completed.stdout}\n{completed.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
