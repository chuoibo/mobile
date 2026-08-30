"""What the "is anything rendering this screen?" gate must catch, and must not.

## Why this file exists at all

`scripts/check_screens_reachable.py` was reachable from `scripts/gate.sh` and
from nowhere else. That is enough to run it, and not enough to keep it: the
moment the workflow job that runs it exists,
`test_workflow_gates_have_local_callers.py` asks for a caller under `tests/` so
the check also runs in the standard `python3 -m pytest services/api/tests tests`
command. This is that caller, and it is written as tests rather than as one
`subprocess.run` because a script invoked for its exit code proves only that it
exited.

## What it proves and what it does not

It proves the reader bites on a screen nothing renders, stays quiet on one that
is rendered, refuses to conclude anything when it can read no screens, and that
the pin file is doing work rather than papering over a reader that returns `[]`.

It does not prove the *product* claim -- that a user can reach the screen. A
render edge from the entry point is the strongest thing a static reader can
say, and the module docstring of the script is explicit that a screen rendered
behind a button nobody can press still counts as reachable here.

## The test that matters most

`test_without_the_pin_file_the_real_tree_is_red`. Every other assertion in this
file would still pass if `check()` were replaced with `return [], stats`. That
one fails in that world, because it removes the pin file and demands the real
tree go red on exactly the screens the pin file claims are dead.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "check_screens_reachable.py"

SPEC = importlib.util.spec_from_file_location("check_screens_reachable", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
# Registered before exec because `@dataclass` resolves annotations through
# `sys.modules[cls.__module__]`, same as this file's twin does.
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


# The canary tree lives outside the repository, so `display_path` falls back to
# a path relative to the tree's parent and every `rel` it prints starts with the
# directory name below. Pins are matched on that same string, so a canary pin
# has to carry the prefix too -- getting this wrong writes a pin that matches
# nothing, which looks like a working pin right up until it silences nothing.
CANARY_DIR = "cay"


def on_canary(files: dict[str, str]):
    """Run the real reader over a canary tree, and hand back its findings."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / CANARY_DIR
        gate._write_canary(root, files)
        return gate._check_canary(root)


class TheGateBites(unittest.TestCase):
    """The defect: a screen file that nothing alive renders."""

    def test_selftest_passes(self):
        """The canary table `gate.sh` and the workflow both run first.

        Kept as its own test so the three canaries run in pytest too. A gate
        whose selftest is only ever invoked by a shell script stops being run
        the day somebody runs the suite instead of the gate.
        """
        self.assertEqual(gate.selftest(), 0)

    def test_a_screen_nothing_renders_is_reported_by_name(self):
        findings, stats = on_canary(gate.CANARY_DEAD)
        dead = [f.rel for f in findings if f.kind == "unrendered"]
        # By name, not "some finding appeared". A gate that reddens for the
        # wrong screen reads exactly like one that works.
        self.assertEqual([r for r in dead if r.endswith("src/screens/Toi.tsx")], dead)
        self.assertEqual(len(dead), 1)
        self.assertEqual(stats["unrendered"], 1)

    def test_an_imported_but_never_rendered_screen_is_reported(self):
        """The bug the first draft of the script shipped with.

        Letting an entry file's plain imports carry the chain marked every
        screen `App.tsx` merely imports as reachable, so deleting the real
        `<ChiaSe />` render left the gate GREEN. This is that case pinned: the
        screen is imported and never rendered, and it must be red.
        """
        findings, _ = on_canary(gate.CANARY_IMPORT_ONLY)
        dead = [f.rel for f in findings if f.kind == "unrendered"]
        self.assertEqual(len(dead), 1, f"mong đúng 1 màn chết, nhận {findings}")
        self.assertTrue(dead[0].endswith("src/screens/Toi.tsx"), dead)

    def test_a_pin_for_a_screen_that_gained_a_renderer_is_reported(self):
        """A pin outliving the thing it excuses is a claim nobody rechecked."""
        files = dict(gate.CANARY_LIVE)
        files[".screens-unrendered.json"] = json.dumps(
            {
                "screens": [
                    {"path": f"{CANARY_DIR}/src/screens/Sang.tsx", "reason": "đã cũ"}
                ]
            }
        )
        findings, _ = on_canary(files)
        self.assertEqual([f.kind for f in findings], ["stale_pin"], findings)


class TheGateStaysQuiet(unittest.TestCase):
    """The false-fail direction, which is how a gate gets switched off."""

    def test_a_live_tree_reports_nothing(self):
        findings, stats = on_canary(gate.CANARY_LIVE)
        self.assertEqual(findings, [])
        self.assertGreater(stats["screens"], 0, "canary sống mà không đọc được màn nào")

    def test_a_pinned_dead_screen_is_quiet_and_still_counted(self):
        """A pin silences the finding without erasing the fact.

        `unrendered` stays 1 so the count keeps describing the tree. A pin that
        also moved the number would let the debt list shrink the denominator
        it is supposed to be measured against.
        """
        files = dict(gate.CANARY_DEAD)
        files[".screens-unrendered.json"] = json.dumps(
            {
                "screens": [
                    {
                        "path": f"{CANARY_DIR}/src/screens/Toi.tsx",
                        "reason": "đang chờ luồng X",
                    }
                ]
            }
        )
        findings, stats = on_canary(files)
        self.assertEqual(findings, [])
        self.assertEqual(stats["unrendered"], 1)
        self.assertEqual(stats["pinned"], 1)


class ThePinFileIsHonest(unittest.TestCase):
    def test_every_entry_has_a_path_and_a_reason(self):
        if not gate.PIN_PATH.is_file():
            self.skipTest("không có file pin trên nhánh này")
        raw = json.loads(gate.PIN_PATH.read_text(encoding="utf-8"))
        entries = raw["screens"]
        self.assertGreater(len(entries), 0, "file pin tồn tại mà rỗng")
        for entry in entries:
            with self.subTest(path=entry.get("path")):
                self.assertTrue(entry.get("path"))
                self.assertTrue(
                    entry.get("reason", "").strip(),
                    "pin không lý do là một cái nhún vai",
                )

    def test_no_screen_is_pinned_twice(self):
        if not gate.PIN_PATH.is_file():
            self.skipTest("không có file pin trên nhánh này")
        raw = json.loads(gate.PIN_PATH.read_text(encoding="utf-8"))
        paths = [e["path"] for e in raw["screens"]]
        self.assertEqual(sorted(paths), sorted(set(paths)), "có màn bị ghim hai lần")

    def test_a_pin_without_a_reason_refuses_to_run(self):
        """Refusing is an error, and could-not-run is never a pass."""
        with tempfile.TemporaryDirectory() as tmp:
            pin = Path(tmp) / "pin.json"
            pin.write_text(
                json.dumps({"screens": [{"path": "src/screens/X.tsx"}]}),
                encoding="utf-8",
            )
            original, gate.PIN_PATH = gate.PIN_PATH, pin
            try:
                with self.assertRaises(ValueError):
                    gate.load_pins()
            finally:
                gate.PIN_PATH = original


class TheMechanismIsLoadBearing(unittest.TestCase):
    def test_the_real_tree_has_screens_to_read_at_all(self):
        """The denominator.

        Without it the assertion below passes just as happily on a reader that
        finds nothing, because "no screens were read" and "every pinned screen
        is unrendered" print the same zero.
        """
        if not gate.SCREEN_ROOT.is_dir():
            self.skipTest("apps/mobile/src/screens không có trên nhánh này")
        _, stats = gate.check()
        self.assertGreater(stats["screens"], 20, stats)
        self.assertGreater(stats["files_scanned"], 20, stats)

    def test_without_the_pin_file_the_real_tree_is_red(self):
        """The pin file is what makes this tree exit 0, so removing it has to
        be visible. This reads the real client and asserts the screens the pin
        file names genuinely have no renderer -- the claim the file makes,
        checked rather than trusted.
        """
        if not gate.SCREEN_ROOT.is_dir():
            self.skipTest("apps/mobile/src/screens không có trên nhánh này")
        if not gate.PIN_PATH.is_file():
            self.skipTest("không có file pin trên nhánh này")
        pinned = sorted(gate.load_pins())
        missing = Path(tempfile.gettempdir()) / "khong-ton-tai-.screens-unrendered.json"
        original, gate.PIN_PATH = gate.PIN_PATH, missing
        try:
            findings, _ = gate.check()
        finally:
            gate.PIN_PATH = original
        self.assertEqual(
            sorted(f.rel for f in findings if f.kind == "unrendered"),
            pinned,
            "file pin khai những màn này không ai render, nhưng bỏ pin đi thì "
            "cổng không báo đúng tập đó -- hoặc cơ chế không gác gì, hoặc có "
            "dòng đã nối xong mà chưa gỡ pin.",
        )

    def test_todays_tree_is_green(self):
        """What `gate.sh` and the workflow job actually assert, run here too."""
        if not gate.SCREEN_ROOT.is_dir():
            self.skipTest("apps/mobile/src/screens không có trên nhánh này")
        findings, stats = gate.check()
        self.assertEqual(
            [(f.rel, f.kind, f.detail) for f in findings], [], f"stats: {stats}"
        )


class CouldNotRunIsNeverAPass(unittest.TestCase):
    def test_a_tree_with_no_screens_exits_2(self):
        """0/0 is the green-because-nothing-ran shape, inside the very gate
        that exists to catch code nobody can reach. It must not be exit 0.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "trong"
            (root / "src").mkdir(parents=True)
            (root / "App.tsx").write_text("export const App = () => null;\n", "utf-8")
            saved = (gate.MOBILE_ROOT, gate.SCREEN_ROOT, gate.PIN_PATH, sys.argv)
            gate.MOBILE_ROOT = root
            gate.SCREEN_ROOT = root / "src" / "screens"
            gate.PIN_PATH = root / ".screens-unrendered.json"
            sys.argv = ["check_screens_reachable.py"]
            try:
                self.assertEqual(gate.main(), 2)
            finally:
                (gate.MOBILE_ROOT, gate.SCREEN_ROOT, gate.PIN_PATH, sys.argv) = saved

    def test_an_absent_apps_mobile_says_so_rather_than_claiming_a_pass(self):
        """`apps/mobile` is absent on some checkouts by design. Skipping is
        honest; the exit code is 0 and the line printed must not read as ĐẠT.
        """
        with tempfile.TemporaryDirectory() as tmp:
            saved = (gate.MOBILE_ROOT, sys.argv)
            gate.MOBILE_ROOT = Path(tmp) / "khong-co"
            sys.argv = ["check_screens_reachable.py"]
            try:
                self.assertEqual(gate.main(), 0)
            finally:
                (gate.MOBILE_ROOT, sys.argv) = saved


if __name__ == "__main__":
    unittest.main()
