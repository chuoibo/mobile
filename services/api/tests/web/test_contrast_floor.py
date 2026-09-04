"""The non-text contrast floor, WCAG 2.2 SC 1.4.11.

The 46-pair table in DESIGN.md measures TEXT on background and nothing else.
That left a hole big enough to ship a bug through: the quiet button has
`backgroundColor: "transparent"`, so its 1px border is the only thing that
says "this is a button", and that border was drawn with `line` at 1.21:1
against the page ground. A text-only contrast gate reads perfectly green
while the control is invisible to anyone who is not looking straight at it.

So this file measures the other half. Two rules, and the difference between
them is the whole point:

  * A boundary that identifies a CONTROL is covered by SC 1.4.11 and owes
    3:1 against whatever it sits on. Buttons, inputs, radio chips.
  * A boundary that merely decorates a CONTAINER is not a user interface
    component and owes nothing. Card edges, dividers, the blockquote rail.
    Forcing 3:1 on those would darken every hairline in the product to fix
    a problem they do not have.

The table below is not a list of tokens; it reads the token out of the real
source file and then measures it. A token that meets the floor but that no
component uses cannot satisfy this test, and a component that quietly moves
back to a decorative token fails it again.
"""

from __future__ import annotations

import json
import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parents[4]
TOKENS_PATH = REPO / "packages/shared/tokens.json"
KIT_PATH = REPO / "apps/mobile/src/rudi/ui.tsx"
CSS_PATH = REPO / "services/api/app/web/static/guest.css"
DESIGN_PATH = REPO / "DESIGN.md"

# SC 1.4.11 Non-text Contrast, level AA.
NON_TEXT_FLOOR = 3.0
# SC 1.4.3 Contrast (Minimum), level AA, for normal-size text.
TEXT_FLOOR = 4.5

TOKENS = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
KIT = KIT_PATH.read_text(encoding="utf-8")
CSS = CSS_PATH.read_text(encoding="utf-8")
DESIGN = DESIGN_PATH.read_text(encoding="utf-8")


def relative_luminance(value: str) -> float:
    """WCAG 2.x relative luminance of an #rrggbb colour."""
    raw = value.lstrip("#")
    channels = [int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    ]
    red, green, blue = linear
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(foreground: str, background: str) -> float:
    """WCAG 2.x contrast ratio. Order does not matter."""
    high, low = sorted(
        (relative_luminance(foreground), relative_luminance(background)), reverse=True
    )
    return (high + 0.05) / (low + 0.05)


def palette(mode: str) -> dict[str, str]:
    return TOKENS["color"][mode]


def kit_component(name: str) -> str:
    """Source of one exported component, up to the next top-level export."""
    marker = f"export function {name}("
    start = KIT.find(marker)
    assert start != -1, f"{name} is no longer exported from src/rudi/ui.tsx"
    rest = KIT[start + len(marker) :]
    end = rest.find("\nexport ")
    return rest if end == -1 else rest[:end]


def css_rule(selector: str) -> str:
    """Declaration block of one CSS rule, by exact selector."""
    match = re.search(re.escape(selector) + r"\s*\{(.*?)\}", CSS, re.S)
    assert match is not None, f"{selector} is no longer in guest.css"
    return match.group(1)


def css_border_token(block: str) -> str:
    """The token a declaration block draws its border with, as a JSON token name."""
    match = re.search(
        r"border(?:-(?:top|right|bottom|left))?(?:-color)?:\s*[^;]*var\(--([a-z-]+)\)",
        block,
    )
    assert match is not None, f"no var()-driven border in block: {block.strip()[:80]}"
    return re.sub(r"-([a-z])", lambda m: m.group(1).upper(), match.group(1))


def css_scrollbar_thumb_token(block: str) -> str:
    """`scrollbar-color: <thumb> <track>` -- the thumb is the first colour."""
    match = re.search(r"scrollbar-color:\s*var\(--([a-z-]+)\)", block)
    assert match is not None, "scrollbar-color is no longer set on body"
    return re.sub(r"-([a-z])", lambda m: m.group(1).upper(), match.group(1))


def kit_border_token(pattern: str, block: str) -> str:
    match = re.search(pattern, block, re.S)
    assert match is not None, (
        f"border declaration not found; ui.tsx shape changed: {pattern}"
    )
    return match.group(1)


# Every boundary in the product whose job is to identify a control.
# (label, token actually used, background token it sits on)
def interactive_boundaries() -> list[tuple[str, str, str]]:
    # The RuDi shell's primitives (App B's Kit.tsx left with App B, 2026-09-04).
    button = kit_component("RudiButton")
    field = kit_component("Field")
    chip = kit_component("Chip")
    return [
        # App. The outline button and the unselected chip have a card fill at
        # most, so the border is the affordance; it must clear the surface it
        # sits on (ground) and the fill it encloses (card).
        (
            "app: nút outline RudiButton, viền trên nền trang",
            kit_border_token(
                r'variant === "outline" && \{[^}]*borderColor:\s*(?:tone === "accent" \? )?colors\.(\w+)',
                button,
            ),
            "ground",
        ),
        (
            "app: nút outline RudiButton, viền trên thẻ",
            kit_border_token(
                r'variant === "outline" && \{[^}]*borderColor:\s*(?:tone === "accent" \? )?colors\.(\w+)',
                button,
            ),
            "card",
        ),
        (
            "app: ô nhập Field, viền trên thẻ",
            kit_border_token(r"borderColor:\s*colors\.(\w+)", field),
            "card",
        ),
        (
            "app: chip Chip chưa chọn, viền trên thẻ",
            kit_border_token(
                r"borderColor:\s*selected\s*\?\s*toneColor\(colors, tone\)\s*:\s*colors\.(\w+)",
                chip,
            ),
            "card",
        ),
        (
            "app: chip Chip chưa chọn, viền trên nền trang",
            kit_border_token(
                r"borderColor:\s*selected\s*\?\s*toneColor\(colors, tone\)\s*:\s*colors\.(\w+)",
                chip,
            ),
            "ground",
        ),
        # Guest page. All three live inside <section class="card">.
        (
            "khách: nút .btn--quiet, viền trên thẻ",
            css_border_token(css_rule(".btn--quiet")),
            "card",
        ),
        (
            "khách: nút số tiền .amount, viền trên thẻ",
            css_border_token(css_rule(".amount")),
            "card",
        ),
        (
            "khách: nút .copy, viền trên thẻ",
            css_border_token(css_rule(".copy")),
            "card",
        ),
        (
            "khách: con trượt thanh cuộn, trên rãnh của nó",
            css_scrollbar_thumb_token(css_rule("body")),
            "ground",
        ),
    ]


# Boundaries that decorate a container. SC 1.4.11 does not reach these, and
# pushing them to 3:1 would darken every hairline in the product.
DECORATIVE_BOUNDARIES = [
    (
        "app: cạnh thẻ Card",
        lambda: kit_border_token(
            r"borderColor:\s*tone\s*\?\s*toneSoftColor\(colors, tone\)\s*:\s*colors\.(\w+)",
            kit_component("Card"),
        ),
    ),
    ("khách: cạnh .card--quiet", lambda: css_border_token(css_rule(".card--quiet"))),
    ("khách: đường kẻ .transfer", lambda: css_border_token(css_rule(".transfer"))),
]


class NonTextContrast(unittest.TestCase):
    """SC 1.4.11: the visual boundary of a control needs 3:1."""

    def test_every_control_boundary_clears_three_to_one(self):
        for label, token, background in interactive_boundaries():
            for mode in ("light", "dark"):
                colours = palette(mode)
                with self.subTest(control=label, mode=mode, token=token):
                    self.assertIn(
                        token,
                        colours,
                        f"{label} draws its border with `{token}`, which is not a colour token",
                    )
                    ratio = contrast(colours[token], colours[background])
                    self.assertGreaterEqual(
                        round(ratio, 2),
                        NON_TEXT_FLOOR,
                        f"{label} [{mode}]: `{token}` {colours[token]} trên `{background}` "
                        f"{colours[background]} = {ratio:.2f}:1, dưới sàn {NON_TEXT_FLOOR}:1 "
                        f"của WCAG 1.4.11. Nút không có nền thì viền là thứ duy nhất cho biết "
                        f"nó là nút.",
                    )

    def test_a_control_boundary_never_reuses_the_decorative_hairline(self):
        """`line` is sized for card edges. A control that borrows it regresses."""
        for label, token, _background in interactive_boundaries():
            with self.subTest(control=label):
                self.assertNotEqual(
                    token,
                    "line",
                    f"{label} dùng `line`, token trang trí cho cạnh thẻ. Ranh giới của "
                    f"một control phải dùng token đạt sàn 3:1.",
                )

    def test_container_edges_stay_on_the_decorative_hairline(self):
        """The other half of the rule. `line` exists so cards keep a soft edge.

        Without this, the cheapest way to make the test above pass is to move
        every border to `lineStrong`, which would trade a real accessibility
        fix for a product where every card is outlined in tan.
        """
        for label, extract in DECORATIVE_BOUNDARIES:
            with self.subTest(container=label):
                self.assertEqual(
                    extract(),
                    "line",
                    f"{label} không còn dùng `line`. Cạnh của một container là trang trí; "
                    f"đẩy nó lên sàn 3:1 là làm nặng cả sản phẩm để sửa lỗi nó không có.",
                )


class DesignDocRecordsWhatWasMeasured(unittest.TestCase):
    """A design system that does not measure a thing cannot stop it."""

    def test_design_md_has_a_non_text_floor_section(self):
        self.assertIn(
            "1.4.11",
            DESIGN,
            "DESIGN.md không nhắc WCAG 1.4.11. Bảng 46 cặp chỉ đo CHỮ trên nền, nên "
            "không có gì chặn được viền 1.21:1 của nút quiet.",
        )

    def test_design_md_records_every_control_boundary_token(self):
        for label, token, background in interactive_boundaries():
            with self.subTest(control=label):
                self.assertRegex(
                    DESIGN,
                    rf"`{token}`[^|\n]*trên[^|\n]*`{background}`",
                    f"{label}: cặp `{token}` trên `{background}` không có dòng nào trong "
                    f"DESIGN.md. Token không được đo thì lần sau lại trượt.",
                )

    def test_design_md_records_the_decorative_hairline_and_its_real_number(self):
        """`line` stays below 3:1 on purpose. Say so, with the number."""
        self.assertRegex(
            DESIGN,
            r"`line`[^|\n]*trên[^|\n]*`ground`",
            "DESIGN.md không ghi số đo của `line`, nên người sau không biết nó ở đâu so "
            "với sàn 3:1 và sẽ lại dùng nó cho một cái nút.",
        )

    def test_every_ratio_printed_in_design_md_matches_the_tokens(self):
        """The table is generated from tokens.json, so it must never disagree with it."""
        rows = re.findall(
            r"\|\s*`(\w+)`\s*(#[0-9a-fA-F]{6})\s*trên\s*`(\w+)`\s*(#[0-9a-fA-F]{6})\s*\|"
            r"[^|]*\|\s*\*\*([\d.]+):1\*\*",
            DESIGN,
        )
        self.assertGreater(len(rows), 40, "bảng số đo trong DESIGN.md đã biến mất")
        for fg_name, fg_hex, bg_name, bg_hex, printed in rows:
            with self.subTest(pair=f"{fg_name} on {bg_name}"):
                mode = (
                    "light" if fg_hex.lower() in palette("light").values() else "dark"
                )
                colours = palette(mode)
                self.assertEqual(
                    colours.get(fg_name, "").lower(),
                    fg_hex.lower(),
                    f"DESIGN.md ghi `{fg_name}` = {fg_hex} nhưng tokens.json không khớp",
                )
                self.assertEqual(
                    colours.get(bg_name, "").lower(),
                    bg_hex.lower(),
                    f"DESIGN.md ghi `{bg_name}` = {bg_hex} nhưng tokens.json không khớp",
                )
                self.assertAlmostEqual(
                    float(printed),
                    contrast(fg_hex, bg_hex),
                    places=1,
                    msg=f"DESIGN.md ghi {printed}:1 cho `{fg_name}` trên `{bg_name}`, "
                    f"đo lại được {contrast(fg_hex, bg_hex):.2f}:1",
                )


class TextContrastStillHolds(unittest.TestCase):
    """Guard the pairs the old table did cover, so the fix cannot trade them away."""

    def test_placeholder_tone_clears_the_text_floor(self):
        for mode in ("light", "dark"):
            colours = palette(mode)
            with self.subTest(mode=mode):
                ratio = contrast(colours["inkFaint"], colours["card"])
                self.assertGreaterEqual(
                    round(ratio, 2),
                    TEXT_FLOOR,
                    f"placeholder `inkFaint` {colours['inkFaint']} trên `card` "
                    f"{colours['card']} = {ratio:.2f}:1",
                )


if __name__ == "__main__":
    unittest.main()
