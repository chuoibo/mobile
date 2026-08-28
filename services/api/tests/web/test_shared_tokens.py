"""The two surfaces must not drift apart.

A guest opens a link on their phone; the organiser sees the same obligation in
the app. If the app formats 82000 as "82,000" and the link shows "82.000", or
if the two greens differ, the product looks like two products.

These tests bind both surfaces to one file each, rather than to a promise.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.web.guest_view import format_vnd  # noqa: E402

SHARED = pathlib.Path(__file__).resolve().parents[4] / "packages/shared"
CSS = pathlib.Path(__file__).resolve().parents[2] / "app/web/static/guest.css"


class MoneyFormatting(unittest.TestCase):
    def test_python_matches_the_shared_golden_cases(self):
        cases = json.loads((SHARED / "money-format.cases.json").read_text(encoding="utf-8"))["cases"]
        self.assertGreaterEqual(len(cases), 10)
        for case in cases:
            with self.subTest(amount=case["amount_vnd"]):
                self.assertEqual(format_vnd(case["amount_vnd"]), case["display"])


class DesignTokens(unittest.TestCase):
    def setUp(self):
        self.tokens = json.loads((SHARED / "tokens.json").read_text(encoding="utf-8"))
        self.css = CSS.read_text(encoding="utf-8")

    def css_block(self, selector: str) -> str:
        match = re.search(re.escape(selector) + r"\s*\{(.*?)\}", self.css, re.S)
        self.assertIsNotNone(match, f"missing {selector}")
        return match.group(1)

    def test_light_palette_matches_the_shared_tokens(self):
        block = self.css_block(":root")
        for name, value in self.tokens["color"]["light"].items():
            css_name = "--" + re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), name)
            with self.subTest(token=css_name):
                self.assertRegex(block, re.escape(css_name) + r":\s*" + re.escape(value))

    def test_dark_palette_matches_the_shared_tokens(self):
        match = re.search(r"prefers-color-scheme: dark\s*\)\s*\{\s*:root\s*\{(.*?)\}", self.css, re.S)
        self.assertIsNotNone(match)
        for name, value in self.tokens["color"]["dark"].items():
            css_name = "--" + re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), name)
            with self.subTest(token=css_name):
                self.assertRegex(match.group(1), re.escape(css_name) + r":\s*" + re.escape(value))

    def test_radius_matches(self):
        block = self.css_block(":root")
        self.assertIn(f"--radius: {self.tokens['radius']['base']}px", block)
        self.assertIn(f"--radius-sm: {self.tokens['radius']['small']}px", block)


if __name__ == "__main__":
    unittest.main()
