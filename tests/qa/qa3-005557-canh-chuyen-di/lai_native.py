"""Drive the real app on a real Android emulator through adb + uiautomator.

This is NOT Chrome and NOT React Native Web. Every tap below is an
`input tap x y` on the emulator, and every screen reading comes from
`uiautomator dump` — the same accessibility tree TalkBack reads.

What it can prove
    A person holding this build can REACH the screen by tapping, and the app
    called route R while getting there.

What it cannot prove
    That the screen is correct, that it is readable, or that any of it behaves
    the same on a real ARM phone. An x86_64 emulator differs in codec, camera,
    performance and permissions.

The black bar trap
    React Native's LogBox notification sits on top of the tab bar and eats the
    tap. A tab that "does not react" is usually this, not a missing screen, so
    `dismiss_logbox` runs before every tap and is counted, not silent.
"""

from __future__ import annotations

import html
import os
import re
import subprocess
import time
import unicodedata

# This lane runs its OWN AVD on its OWN port. Measured the hard way on
# 01/09: while a measurement was mid-run on the shared `rudi` at 5554, another
# lane's `android-down` killed it and every following tap reported "device not
# found" — which reads exactly like "the screen does not exist". A measurement
# that cannot name the machine it ran on cannot be trusted by anyone else.
SERIAL = os.environ.get("ANDROID_SERIAL", "emulator-5560")
ADB = "/home/lakiet/Android/Sdk/platform-tools/adb"


def adb(*args: str, timeout: int = 60) -> str:
    out = subprocess.run(
        [ADB, "-s", SERIAL, *args], capture_output=True, timeout=timeout
    )
    return out.stdout.decode("utf-8", "replace")


NODE_RE = re.compile(r"<node\b([^>]*)/?>")
ATTR_RE = re.compile(r'(\S+?)="([^"]*)"')
BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


class Node:
    __slots__ = ("text", "desc", "cls", "clickable", "enabled", "bounds")

    def __init__(self, attrs: dict):
        self.text = html.unescape(attrs.get("text", ""))
        self.desc = html.unescape(attrs.get("content-desc", ""))
        self.cls = attrs.get("class", "")
        self.clickable = attrs.get("clickable") == "true"
        self.enabled = attrs.get("enabled") == "true"
        m = BOUNDS_RE.search(attrs.get("bounds", ""))
        self.bounds = tuple(int(g) for g in m.groups()) if m else (0, 0, 0, 0)

    @property
    def center(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.bounds
        return (x1 + x2) // 2, (y1 + y2) // 2

    @property
    def label(self) -> str:
        return self.text or self.desc

    def __repr__(self) -> str:
        return f"Node({self.label!r} click={self.clickable} {self.bounds})"


def dump() -> list[Node]:
    """Screen as a node list. Retries: uiautomator refuses while a frame animates."""
    for _ in range(6):
        adb("shell", "uiautomator", "dump", "/sdcard/u.xml")
        xml = adb("shell", "cat", "/sdcard/u.xml")
        if "<node" in xml:
            return [Node(dict(ATTR_RE.findall(a))) for a in NODE_RE.findall(xml)]
        time.sleep(1.5)
    return []


def fold(s: str) -> str:
    """Casefold + strip accents: the tree sometimes differs from the source in both."""
    return "".join(
        c
        for c in unicodedata.normalize("NFD", s.casefold())
        if unicodedata.category(c) != "Mn"
    )


def screen_text(nodes: list[Node]) -> str:
    return " · ".join(n.label for n in nodes if n.label.strip())


def find(nodes: list[Node], needle: str, clickable_only: bool = False) -> Node | None:
    """Smallest matching node — the smallest one is the actual control, not its card.

    `clickable_only` defaults to FALSE on purpose, and this is the single most
    important line in the file. Measured on Expo Go 57 / Android 15: the whole
    developer-menu screen, "Continue" button included, reports
    clickable="false" — React Native maps `Pressable` onto a plain View and
    uiautomator has nothing to mark. Filtering on `clickable` would have made
    this meter answer "no such button" for buttons that a finger can press,
    which is the exact lie the meter exists to catch. So the rule is: tap the
    coordinates, then check whether the SCREEN changed. Clickability is a hint
    for ranking, never a verdict.
    """
    f = fold(needle)
    hits = [
        n
        for n in nodes
        if f in fold(n.label) and (n.clickable or not clickable_only) and n.enabled
    ]
    if not hits:
        return None

    # Rank exact label first, then prefix, then plain substring. Bare substring
    # ranking cost a run on 01/09: the needle "Ẩn" folds to "an", which is
    # inside "Scan QR Code", so the driver tapped Expo Go's own scanner, left
    # the app entirely, and the next step honestly reported the button missing.
    # A meter that can leave the app under test and keep reporting is worse
    # than one that stops.
    def rank(n: Node) -> tuple:
        lab = fold(n.label)
        kind = 0 if lab == f else (1 if lab.startswith(f) else 2)
        area = (n.bounds[2] - n.bounds[0]) * (n.bounds[3] - n.bounds[1])
        return (kind, not n.clickable, area)

    return min(hits, key=rank)


# The LogBox notification labels itself "<count>, <first warning text>".
LOGBOX_RE = re.compile(r"^\d+,\s")


def dismiss_logbox(nodes: list[Node]) -> bool:
    """Close RN's LogBox bar if it is covering the tab bar. Returns True if it acted.

    Measured on this build, Khám phá screen, 1080x2400: the bar occupies
    [26,2146]-[1054,2271] while the tab bar starts at y=2253. The four tab
    labels sit at y≈2311 and survive, but the centre "Tạo mới" button is
    [469,2195]-[611,2337], centre y=2266 — INSIDE the bar. So a tap on the one
    control that opens the create flow lands on a dev-tools warning and does
    nothing: no error, no navigation, no log. Identical on screen to "that
    feature does not exist", which is why this runs before every tap.
    """
    for n in nodes:
        if LOGBOX_RE.match(n.label) and n.clickable:
            tap(n, settle=2.5)
            opened = dump()
            btn = find(opened, "Dismiss")
            if btn is not None:
                tap(btn, settle=1.5)
            else:
                back()
            return True
    return False


def tap(node: Node, settle: float = 2.0) -> None:
    x, y = node.center
    adb("shell", "input", "tap", str(x), str(y))
    time.sleep(settle)


def tap_text(needle: str, settle: float = 2.0) -> tuple[bool, list[Node]]:
    """Tap the control carrying `needle`. Returns (tapped?, screen after)."""
    nodes = dump()
    n = find(nodes, needle)
    if n is None:
        return False, nodes
    tap(n, settle)
    return True, dump()


def back(settle: float = 1.5) -> list[Node]:
    adb("shell", "input", "keyevent", "4")
    time.sleep(settle)
    return dump()
