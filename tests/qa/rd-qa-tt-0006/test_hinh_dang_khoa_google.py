"""Shape coverage for the ``google-api-key`` rule added in #233.

#233 proved the rule fires on three shapes -- a ``.env`` line, a Python
literal, and prose -- and that is what made the rule worth merging. This file
pins the next question down: the shapes a Gemini key can realistically land in
by accident, so that a later "simplification" of the regex cannot quietly
shrink the coverage back while the tree stays green.

Every fixture key is assembled at runtime from a prefix and a body. A literal
39-character key in this source would be blocked by the very rule under test,
and ``google-api-key`` sits in ``SECRET_RULES``, so it cannot be allowlisted --
concatenation is the only way a test can carry a key of the real shape.

What this file does NOT claim: it does not prove the gate runs anywhere. The
gate that runs it is ``repo_guard.py tree HEAD`` in ``scripts/gate.sh``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "repo_guard.py"
SPEC = importlib.util.spec_from_file_location("repo_guard", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
repo_guard = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = repo_guard
SPEC.loader.exec_module(repo_guard)


# Assembled, never written whole: see the module docstring.
KEY = "AIza" + "SyB3nQ7vK9mR2tLwX8cD1fH4jP6sT0uYzQw"

# Same frame, different rule. If this stops firing the harness is broken and
# every "no finding" result below would read as coverage when it is silence.
CANARY_TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"

# A body carrying a marker word. The rule deliberately exempts these so test
# fixtures of the real shape do not turn the tree red -- see repo_guard.py.
EXEMPT_KEY = "AIza" + "FAKE7vK9mR2tLwX8cD1fH4jP6sT0uY"


class ScanHelper(unittest.TestCase):
    """Just the helper. Inheriting a suite would re-run every one of its tests."""

    def scan_text(self, text: str, path: str = "safe-note.txt"):
        raw = text.encode("utf-8")
        return repo_guard.content_findings(
            path=path,
            raw=raw,
            file_number=1,
            config=repo_guard.GuardConfig(artifacts=()),
            digest=hashlib.sha256(raw).hexdigest(),
            line_numbers=None,
            commit=None,
        )

    def rules_for(self, text: str) -> set[str]:
        return {finding.rule for finding in self.scan_text(text)}


class GoogleKeyShapeTests(ScanHelper):
    """Each shape is a way the key reaches a file without anyone meaning it to."""

    def test_canary_token_still_fires(self):
        # Guards every assertion below: a dead scanner reports no findings, and
        # "no findings" is indistinguishable from "clean" without this.
        self.assertIn("github-token", self.rules_for(f"token={CANARY_TOKEN}"))

    def test_every_accidental_shape_is_caught(self):
        shapes = {
            "dotenv": f"GEMINI_API_KEY={KEY}",
            "python-literal": f'GEMINI_API_KEY = "{KEY}"',
            "prose": f"Khoa cua minh la {KEY} nhe.",
            "url-query": (
                "URL = "
                '"https://generativelanguage.googleapis.com'
                f'/v1beta/models/gemini:generateContent?key={KEY}"'
            ),
            "json-one-line": f'{{"gemini_api_key": "{KEY}"}}',
            "docker-compose": f"    environment:\n      - GEMINI_API_KEY={KEY}",
            "shell-export": f"export GEMINI_API_KEY='{KEY}'",
            "log-line": f"2026-08-30T04:00:00Z INFO gemini key={KEY} status=200",
            "sentence-end": f"Dat khoa thanh {KEY}.",
            "gha-workflow": f"env:\n  GEMINI_API_KEY: {KEY}",
            "http-header": f"x-goog-api-key: {KEY}",
            "csv-column": f"name,key\ngemini,{KEY}",
        }
        for label, text in shapes.items():
            with self.subTest(shape=label):
                self.assertIn("google-api-key", self.rules_for(text))

    def test_marker_body_stays_exempt(self):
        # The exemption is what keeps the rule alive: without it the tree is red
        # on its own fixtures and the rule gets switched off within a day.
        self.assertNotIn("google-api-key", self.rules_for(f"KEY = '{EXEMPT_KEY}'"))

    def test_finding_never_carries_the_value(self):
        # A gate that prints the secret it caught has leaked it into the log.
        # Asserting only that the value is ABSENT would pass on an empty
        # string, so the redaction marker is asserted present first.
        findings = self.scan_text(f"GEMINI_API_KEY={KEY}")
        self.assertEqual(len(findings), 1)
        rendered = findings[0].render()
        self.assertIn("<redacted-secret>", rendered)
        self.assertNotIn(KEY, rendered)
        self.assertNotIn(KEY[4:], rendered)

    def test_rule_stays_outside_the_allowlist(self):
        # The claim #233 rests on: a secret can never be waved through by
        # pinning it in .repo-guard-allowlist.json. Dropping the rule from
        # SECRET_RULES silently reopens that door while the tree stays green.
        self.assertIn("google-api-key", repo_guard.SECRET_RULES)
        self.assertNotIn("google-api-key", repo_guard.ALLOWLISTABLE_RULES)


if __name__ == "__main__":
    unittest.main()
