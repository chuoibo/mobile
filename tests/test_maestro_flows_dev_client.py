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

    def test_every_launch_is_followed_by_the_dev_menu_skip(self) -> None:
        # The dev client shows «This is the developer menu» on the first cold
        # open after install; a flow that launches and does not dismiss it reads
        # the sheet as «no button». Measured 2026-09-03.
        for flow in self.flows:
            lines = code_lines(flow)
            for i, line in enumerate(lines):
                if line.strip() != "- launchApp":
                    continue
                sau = lines[i + 1 : i + 3]
                self.assertTrue(
                    any("_bo-qua-dev-menu.yaml" in x for x in sau),
                    f"{flow.name}: launchApp ở dòng {i} không có _bo-qua-dev-menu ngay sau",
                )

    def test_otp_flows_take_number_and_code_from_the_harness(self) -> None:
        for name in (
            "22-dang-nhap-otp.yaml",
            "23-phien-song-qua-lan-tat.yaml",
            "24-nhom-thanh-vien-va-ho-so.yaml",
            "25-ban-be-hai-nguoi.yaml",
            "30-chat-that.yaml",
            "31-ban-phim-mo.yaml",
            "40-ai-plan.yaml",
        ):
            text = (FLOWS / name).read_text(encoding="utf-8")
            self.assertRegex(text, r"\$\{OTP_PHONE(_[BCD])?\}", name)
            self.assertIn("${OTP_CODE}", text, name)
            # A phone number in a flow file is a phone number in Git.
            self.assertIsNone(
                re.search(r"\d[\d .-]{8,}\d", text),
                f"{name}: có dãy số dài như số điện thoại",
            )
            self.assertIn(
                'assertNotVisible: "Vào bản trải nghiệm Team Đà Lạt"',
                text.replace("- ", ""),
                name,
            ) if name.startswith("22") else None

    def test_harness_otp_mode_probes_the_debug_code_and_hides_the_fixture_door(
        self,
    ) -> None:
        script = (REPO_ROOT / "scripts" / "mobile_native.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("--otp) OTP=1", script)
        self.assertIn("kiem_ma_debug", script)
        self.assertIn("/auth/otp/verify", script)
        self.assertIn('-e OTP_PHONE="$OTP_PHONE"', script)
        self.assertIn(
            'if [ "$OTP" = 0 ]; then\n    export EXPO_PUBLIC_RUDI_FIXTURE=1',
            script,
        )
        self.assertIn("canary_otp", script)
        self.assertIn('22-*|23-*|24-*|25-*|30-*|31-*) [ "$OTP" = 1 ] || continue', script)
        self.assertIn("do_ban_phim.py", script)
        self.assertIn("kiem_khoa_ai", script)

    def test_a_red_flow_does_not_end_the_table(self) -> None:
        # `chay_flow` must not turn errexit back on before returning a non-zero
        # rc: set -e is global, so the caller's `set +e` would be undone and the
        # table would stop at the first red flow with no summary line.
        script = (REPO_ROOT / "scripts" / "mobile_native.sh").read_text(
            encoding="utf-8"
        )
        body = script[script.index("chay_flow() {") : script.index("\n}\n", script.index("chay_flow() {"))]
        self.assertIn("set +e", body)
        self.assertNotIn("\n  set -e\n", body, "chay_flow bật lại set -e trước khi return rc")
        self.assertIn('40-*)        [ "$OTP" = 1 ] && [ "$AI" = 1 ] || continue', script)
        self.assertIn("kiem_may_chu_sau_30", script)
        self.assertIn("kiem_may_chu_sau_24", script)
        self.assertIn("kiem_may_chu_sau_25", script)

    def test_harness_passes_the_fingerprint_and_checks_it_bites(self) -> None:
        script = (REPO_ROOT / "scripts" / "mobile_native.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('-e TREE_FINGERPRINT="$DAU_VAN"', script)
        self.assertIn("KHONG_CO_DAU_VAN_NAY", script)
        self.assertIn("EXPO_PUBLIC_TREE_FINGERPRINT", script)


if __name__ == "__main__":
    unittest.main()
