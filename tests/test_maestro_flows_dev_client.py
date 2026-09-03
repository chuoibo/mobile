"""The Maestro flows must not point at a bundle the harness did not start.

`scripts/mobile_native.sh` proves that Metro serves this tree and that the
device bundled from it. Both proofs are void the moment a flow opens its own
URL: `openLink: exp://localhost:8095` drives whatever Metro answers on that
port -- another lane's, measured on this machine -- while the two anchors stay
green because they read the log of *this* Metro. The fix that shipped with the
development build is structural: flows say `launchApp`, the dev client reopens
the bundle the harness handed it, and no flow carries a URL or an app id the
harness did not choose.

This file pins that shape so it cannot drift back one flow at a time:

  * every flow declares the dev client's application id;
  * no non-comment line opens `exp://` or names Expo Go;
  * the two entry flows guard against the dev-client launcher, which is what
    `pm clear` leaves behind and what a dead bundle looks like;
  * the smoke flow asserts the per-run tree fingerprint (NEO 2b).

It reads YAML as text on purpose: the assertions are about literal tokens, and
a YAML parser would happily normalise the very strings this is looking for.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FLOWS = REPO_ROOT / "apps" / "mobile" / ".maestro"
APP_ID = "com.lakiet.rudi"


def code_lines(path: Path) -> list[str]:
    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


class MaestroFlowsDriveTheDevClient(unittest.TestCase):
    def setUp(self) -> None:
        if not FLOWS.is_dir():
            self.skipTest("không có apps/mobile/.maestro trong cây này")
        self.flows = sorted(FLOWS.glob("*.yaml"))
        self.assertTrue(
            self.flows, "thư mục flow rỗng -- một bảng rỗng không phải bảng xanh"
        )

    def test_every_flow_names_the_dev_client(self) -> None:
        for flow in self.flows:
            with self.subTest(flow=flow.name):
                self.assertIn(f"appId: {APP_ID}", code_lines(flow)[0:2])

    def test_no_flow_opens_a_metro_url_or_names_expo_go(self) -> None:
        bad = re.compile(r"exp://|host\.exp\.exponent|expo-development-client")
        for flow in self.flows:
            for line in code_lines(flow):
                self.assertIsNone(bad.search(line), f"{flow.name}: {line.strip()}")

    def test_entry_flows_refuse_the_launcher(self) -> None:
        for name in ("_vao-app.yaml", "_vao-app-sach.yaml"):
            lines = code_lines(FLOWS / name)
            self.assertIn("- launchApp", lines, name)
            self.assertIn(
                '- assertNotVisible: "Fetch development servers"', lines, name
            )

    def test_smoke_flow_asserts_the_tree_fingerprint(self) -> None:
        lines = code_lines(FLOWS / "00-smoke-deeplink.yaml")
        self.assertIn('- assertVisible: ".*${TREE_FINGERPRINT}.*"', lines)

    def test_harness_passes_the_fingerprint_and_checks_it_bites(self) -> None:
        script = (REPO_ROOT / "scripts" / "mobile_native.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('-e TREE_FINGERPRINT="$DAU_VAN"', script)
        self.assertIn("KHONG_CO_DAU_VAN_NAY", script)
        self.assertIn("EXPO_PUBLIC_TREE_FINGERPRINT", script)


if __name__ == "__main__":
    unittest.main()
