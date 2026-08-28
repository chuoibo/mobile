"""Regression test for PR #57: the design-system page renders text below AA.

DESIGN.md measures 46 foreground/background pairs and states that none falls
below WCAG AA 4.5:1. That statement is true about the *tokens*. It is not true
about the page that showcases them: `.swatch .contrast` in design_system.css
paints its caption at `opacity: 0.9`, which blends the token foreground toward
the swatch background before it is ever drawn. The pair that DESIGN.md records
as 5.16:1 arrives on screen at 4.45:1, at 12px.

This is the same failure mode the PR itself describes catching for
`split` on `splitSoft` (4.46:1): a pair nobody thought to measure because the
token table said it was fine. The token table is not the rendered pixel.

Deterministic by construction -- it reads the two committed source files and
recomputes WCAG 2.x relative luminance from scratch. No browser, no network,
no clock, no randomness. Confirmed live with axe-core 4.11 + Chromium 1194,
which reports the same pairs at 4.44 and 4.46.

RED on 2fc6bba. Goes GREEN when the rendered caption reaches 4.5:1 -- either by
dropping the opacity blend or by lightening/darkening the caption token.
"""

from __future__ import annotations

import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parents[3]
CSS = REPO / "services/api/app/web/static/design_system.css"
HTML = REPO / "services/api/app/web/templates/design_system.html"
# The page links guest.css first, so the colour tokens come from there; the
# design-system sheet only adds the type/space scale on `.ds-page`.
GUEST_CSS = REPO / "services/api/app/web/static/guest.css"

AA_TEXT = 4.5


def _srgb(channel: int) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (_srgb(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    a, b = _luminance(fg), _luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def parse_hex(value: str) -> tuple[int, int, int]:
    h = value.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def composite(fg: tuple[int, int, int], bg: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    """What the compositor actually hands the contrast checker.

    CSS `opacity` on a text element blends the whole element against what is
    behind it. The declared colour is never the painted colour.
    """
    return tuple(round(alpha * fg[i] + (1 - alpha) * bg[i]) for i in range(3))  # type: ignore[return-value]


def custom_properties(css: str, selector: str) -> dict[str, str]:
    block = re.search(re.escape(selector) + r"\s*\{(.*?)\n\}", css, re.S)
    assert block, f"missing {selector} in {CSS.name}"
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", block.group(1)))


class RenderedCaptionContrast(unittest.TestCase):
    """The caption under each colour swatch must clear AA as painted."""

    def setUp(self) -> None:
        self.css = CSS.read_text(encoding="utf-8")
        self.html = HTML.read_text(encoding="utf-8")
        # Same cascade the browser sees: guest.css :root, then .ds-page.
        self.root = custom_properties(GUEST_CSS.read_text(encoding="utf-8"), ":root")
        self.root.update(custom_properties(self.css, ".ds-page"))

    def token(self, name: str) -> tuple[int, int, int]:
        value = self.root[f"--{name}"].strip()
        self.assertRegex(value, r"^#[0-9a-fA-F]{3,6}$", f"--{name} is not a flat hex: {value}")
        return parse_hex(value)

    def caption_alpha(self) -> float:
        block = re.search(r"\.swatch\s+\.contrast\s*\{(.*?)\}", self.css, re.S)
        self.assertIsNotNone(block, "missing .swatch .contrast rule")
        found = re.search(r"opacity:\s*([\d.]+)", block.group(1))
        return float(found.group(1)) if found else 1.0

    def test_caption_is_small_text_so_the_44_threshold_does_not_apply(self):
        """Guard the premise: if the caption were large text, 3:1 would be the bar."""
        block = re.search(r"\.swatch\s+\.contrast\s*\{(.*?)\}", self.css, re.S)
        self.assertIn("--type-micro", block.group(1))
        micro = self.root["--type-micro"].strip()
        px = float(re.match(r"([\d.]+)px", micro).group(1))
        self.assertLess(px, 18.66, "caption is small text; AA asks 4.5:1, not 3:1")

    def test_every_tone_swatch_caption_clears_aa_as_rendered(self):
        # (swatch modifier in design_system.html, background token, caption token)
        swatches = [
            ("accent", "accent", "accent-ink"),
            ("accent-end", "accent-end", "accent-ink"),
            ("accent-ink", "accent", "accent-ink"),
            ("split", "split", "split-ink"),
            ("split-ink", "split", "split-ink"),
            ("ai", "ai", "ai-ink"),
            ("ai-ink", "ai", "ai-ink"),
        ]
        alpha = self.caption_alpha()
        failures = []
        for modifier, bg_token, fg_token in swatches:
            # Only assert on swatches the page actually renders.
            if f"swatch--{modifier}" not in self.html:
                continue
            bg = self.token(bg_token)
            fg = self.token(fg_token)
            declared = contrast(fg, bg)
            painted = contrast(composite(fg, bg, alpha), bg)
            with self.subTest(swatch=modifier):
                if painted < AA_TEXT:
                    failures.append(
                        f"swatch--{modifier}: DESIGN.md records {declared:.2f}:1, "
                        f"opacity {alpha} paints it at {painted:.3f}:1 (AA needs {AA_TEXT})"
                    )
        self.assertEqual(
            failures,
            [],
            "rendered swatch captions below WCAG AA:\n  " + "\n  ".join(failures),
        )


if __name__ == "__main__":
    unittest.main()
