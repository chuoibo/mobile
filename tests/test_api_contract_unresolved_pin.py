"""A call the route-existence gate cannot follow must be pinned, not dropped.

## The hole this closes

`scripts/check_api_contract.py` compares the paths `apps/mobile` calls against
the paths FastAPI reports, and that is the only thing in this repository that
compares the two halves of a request while GitHub Actions cannot start a job.

Until 2026-08-30 it dropped, in silence, every call site whose URL it could not
turn into a route. Its own comment named the tell and stopped there:

    "A request whose URL this reader cannot follow contributes nothing but its
     presence in the count. That number is the tell: it climbing while the path
     count falls is this checker going blind."

Nothing asserted on the tell. Measured on `main` at 15726d2, one route that
does not exist, written seven ways:

    literal · one const · "a" + b · `${base}/x` · object lookup   exit 1
    call<void>(path) with the path handed to a helper parameter   exit 0
    call<void>("/" + parts.join("-"))                             exit 0

The two that passed did so with `duong_dan_tim_thay` frozen at 36 while
`lan_goi_doc_duoc` climbed 45 -> 46 -- the tell firing, printed, and read by
nobody. Handing a path to a helper is the most ordinary refactor there is in a
client module, so this was not an exotic hole.

`scripts/check_actor_headers.py` -- the same reader over the same files,
answering the adjacent question -- has pinned its blind spots in
`.actor-header-unresolved.json` all along. This file holds the twin mechanism.

## What each part is for

`test_selftest_*` is the gate proving it can be red at all; a checker only ever
run against a healthy tree cannot tell green from dead.

`test_without_the_pin_file_*` is the load-bearing check. The pin file makes the
real tree pass, so every other test here would still pass if the mechanism were
deleted and replaced with `return []`. That test is the one that notices.

The count tests exist because the pin key is `file :: expression`, not a line
number -- deliberately, so an unrelated edit above a pinned call does not turn
the gate red for the wrong reason. The cost of that choice is that a second
occurrence of an already-pinned expression would otherwise slip in free, and
`count` is what closes it.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "check_api_contract.py"

SPEC = importlib.util.spec_from_file_location("check_api_contract_pin", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)

BLIND = "duong_dan_khong_phan_giai_duoc"


def a_contract() -> "gate.Contract":
    """A server offering one route, so `/khong-ton-tai` is genuinely absent."""
    contract = gate.Contract()
    key = gate.normalise("/healthz")
    contract.routes[key] = {"GET"}
    contract.spelling[key] = "/healthz"
    return contract


def scan(source: str) -> "gate.Scan":
    return gate.findings_for_source(textwrap.dedent(source), "snippet.ts", a_contract())


def blind_kinds(source: str, pins: dict[str, int] | None = None) -> list[str]:
    result = scan(source)
    return [f.kind for f in gate.unpinned_findings(result.unresolved, pins or {})]


class TheReaderAdmitsWhatItCannotRead(unittest.TestCase):
    def test_a_path_handed_to_a_helper_parameter_is_reported(self):
        # The shape measured passing on main at 15726d2.
        self.assertIn(
            BLIND,
            blind_kinds(
                """
                async function go(path: string) {
                  return call<void>(path, { method: "GET" });
                }
                export async function e() { return go("/khong-ton-tai"); }
                """
            ),
        )

    def test_a_path_joined_at_runtime_is_reported(self):
        self.assertIn(
            BLIND,
            blind_kinds(
                """
                const parts = ["khong-ton-tai", "canary"];
                export async function g() {
                  return call<void>("/" + parts.join("-"), { method: "GET" });
                }
                """
            ),
        )

    def test_a_path_the_reader_can_follow_is_not_reported(self):
        # Pairs with the two above: a probe that answered "blind" to everything
        # would pass them both and prove nothing.
        self.assertEqual(
            [],
            blind_kinds(
                """
                export async function h() {
                  return call<void>("/healthz", { method: "GET" });
                }
                """
            ),
        )

    def test_a_route_that_does_not_exist_is_still_the_other_finding(self):
        # The blind check must not have swallowed the original question.
        self.assertEqual(
            ["route_khong_ton_tai"],
            [
                f.kind
                for f in scan(
                    """
                    export async function a() {
                      return call<void>("/khong-ton-tai", { method: "GET" });
                    }
                    """
                ).findings
            ],
        )


class PinsAccountForBlindSpotsRatherThanHidingThem(unittest.TestCase):
    SOURCE = """
        async function go(path: string) {
          return call<void>(path, { method: "GET" });
        }
        export async function e() { return go("/khong-ton-tai"); }
        """

    def key(self) -> str:
        unresolved = scan(self.SOURCE).unresolved
        self.assertEqual(1, len(unresolved))
        return unresolved[0].where

    def test_a_pinned_shape_is_not_reported(self):
        self.assertEqual([], blind_kinds(self.SOURCE, {self.key(): 1}))

    def test_a_second_occurrence_of_a_pinned_shape_is_reported(self):
        doubled = self.SOURCE + textwrap.dedent(
            """
            export async function e2() { return go("/khong-ton-tai-nua"); }
            async function go2(path: string) {
              return call<void>(path, { method: "GET" });
            }
            """
        )
        # Two sites, one pinned: the pin must not cover both.
        self.assertEqual(2, len(scan(doubled).unresolved))
        self.assertIn(BLIND, blind_kinds(doubled, {self.key(): 1}))

    def test_fewer_sites_than_pinned_is_stale_and_not_a_finding(self):
        # Somebody made the client MORE readable. Reported, never fatal: a gate
        # that goes red for an improvement is a gate switched off within a day.
        self.assertEqual([], blind_kinds(self.SOURCE, {self.key(): 5}))
        self.assertEqual(
            [self.key()],
            gate.stale_pins(scan(self.SOURCE).unresolved, {self.key(): 5}),
        )

    def test_the_key_does_not_move_when_lines_above_it_move(self):
        # The reason the key is the expression rather than the line number.
        shifted = "\n// a comment somebody added\n" + textwrap.dedent(self.SOURCE)
        self.assertEqual(
            self.key(),
            gate.findings_for_source(shifted, "snippet.ts", a_contract())
            .unresolved[0]
            .where,
        )


class TheRealTreeAndTheRealPinFile(unittest.TestCase):
    def test_the_pin_file_accounts_for_every_blind_spot_in_the_tree(self):
        if not gate.CLIENT_ROOT.is_dir():
            self.skipTest("apps/mobile không có trên nhánh này")
        contract = a_contract()
        unresolved = []
        for path in gate.client_files():
            unresolved.extend(
                gate.findings_for_source(
                    path.read_text(encoding="utf-8"),
                    str(path.relative_to(REPO_ROOT)),
                    contract,
                ).unresolved
            )
        self.assertEqual(
            [],
            [f.message for f in gate.unpinned_findings(unresolved, gate.load_pins())],
            "có chỗ gọi API mà cổng không đọc nổi đường dẫn và cũng chưa ghim",
        )

    def test_without_the_pin_file_the_real_tree_is_red(self):
        """The mechanism is load bearing, not decoration.

        Every other test here would still pass if `unpinned_findings` returned
        `[]` unconditionally, because the pin file makes the real tree green.
        This one fails in that world.
        """
        if not gate.CLIENT_ROOT.is_dir():
            self.skipTest("apps/mobile không có trên nhánh này")
        contract = a_contract()
        unresolved = []
        for path in gate.client_files():
            unresolved.extend(
                gate.findings_for_source(
                    path.read_text(encoding="utf-8"),
                    str(path.relative_to(REPO_ROOT)),
                    contract,
                ).unresolved
            )
        self.assertGreater(
            len(gate.unpinned_findings(unresolved, {})),
            0,
            "không ghim gì mà cây vẫn sạch -- cơ chế ghim không gác gì cả",
        )

    def test_a_pin_without_a_reason_refuses_to_run(self):
        # An unexplained pin is the list becoming a parking lot. Refusing to
        # run is exit 2, and could-not-run is never a pass.
        with tempfile.TemporaryDirectory() as tmp:
            pin = Path(tmp) / "pins.json"
            pin.write_text(
                json.dumps({"unresolved": [{"where": "a.ts :: x", "count": 1}]}),
                encoding="utf-8",
            )
            original = gate.UNRESOLVED_PIN
            gate.UNRESOLVED_PIN = pin
            try:
                with self.assertRaises(RuntimeError):
                    gate.load_pins()
            finally:
                gate.UNRESOLVED_PIN = original

    def test_malformed_pin_json_refuses_to_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            pin = Path(tmp) / "pins.json"
            pin.write_text("{not json", encoding="utf-8")
            original = gate.UNRESOLVED_PIN
            gate.UNRESOLVED_PIN = pin
            try:
                with self.assertRaises(RuntimeError):
                    gate.load_pins()
            finally:
                gate.UNRESOLVED_PIN = original


class TheGateProvesItCanBeRed(unittest.TestCase):
    def test_selftest_exits_zero(self):
        done = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--selftest"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)

    def test_selftest_covers_both_failure_kinds(self):
        done = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--selftest"],
            capture_output=True,
            text=True,
        )
        self.assertIn("route_khong_ton_tai", done.stdout)
        self.assertIn(BLIND, done.stdout)
        # Every red canary paired with a clean one, or the selftest is a probe
        # that answers "violation" to everything.
        self.assertIn("mong đợi không có", done.stdout)


if __name__ == "__main__":
    unittest.main()
