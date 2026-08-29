"""Decode this app's own QR output with somebody else's decoder.

`src/ui/qr.ts` is a from-scratch QR encoder: bit stream, Reed-Solomon, mask
selection, the lot. Golden matrices checked against that same encoder would
only prove it still does what it did yesterday, which is the trap CLAUDE.md
names -- the same author writing both the answer and the answer key.

So the answer key comes from OpenCV, which shares no code, no author and no
assumptions with `qr.ts`. The payloads come from the server's own builder
(`app/payments/vietqr.py`), so what is being round-tripped is the real string a
real publish would emit, not a convenient one.

What this proves: the modules `qr.ts` produces decode back to the exact bytes
that went in, through an independent implementation.

What it does NOT prove: that a particular bank's app accepts the result. That
needs a phone, a bank account and a camera, and no script can stand in for it.

Run from the repo root:

    python3 apps/mobile/tools/qr-roundtrip.py
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[3]
MOBILE = ROOT / "apps" / "mobile"
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.payments.vietqr import build_payload  # noqa: E402

# Deliberately spread over bank codes, account lengths and amounts, including
# the one-dong floor and an amount long enough to push the symbol up a version.
#
# The account numbers are invented, and the repo guard is right to flag a long
# digit run on sight -- it cannot tell a fabricated account from a real one.
# The exemptions are per line and named rather than the file being allowlisted.
CASES = [
    # repo-guard: allow=long-number reason=synthetic-test-account-number
    dict(bank_bin="970422", account_number="9999888877", amount_vnd=262500, note="TT 1a2b3c4d"),
    # repo-guard: allow=long-number reason=synthetic-test-account-number
    dict(bank_bin="970415", account_number="113366668888", amount_vnd=1125000, note="TT deadbeef"),
    # repo-guard: allow=long-number reason=synthetic-test-account-number
    dict(bank_bin="970436", account_number="1017328912", amount_vnd=1, note="TT 00000001"),
    # repo-guard: allow=long-number reason=synthetic-test-account-number
    dict(bank_bin="970418", account_number="21610000123456", amount_vnd=99999999, note="TT ffffffff"),
]

DUMP = """
import { encodeQr } from "%s/dist-test/ui/qr.js";
const out = JSON.parse(process.argv[2]).map((text) => {
  const m = encodeQr(text);
  return { text, size: m.size, rows: m.modules.map((r) => r.map((b) => (b ? 1 : 0)).join("")) };
});
console.log(JSON.stringify(out));
"""


def render(entry: dict, quiet: int = 4, scale: int = 8) -> np.ndarray:
    """Paint a matrix as a bitmap, with the quiet zone a scanner needs."""
    size = entry["size"]
    n = size + quiet * 2
    img = np.ones((n, n), dtype=np.uint8) * 255
    for r, row in enumerate(entry["rows"]):
        for c, ch in enumerate(row):
            if ch == "1":
                img[r + quiet, c + quiet] = 0
    return cv2.resize(img, (n * scale, n * scale), interpolation=cv2.INTER_NEAREST)


def main() -> int:
    payloads = [build_payload(**case) for case in CASES]

    script = MOBILE / "dist-test" / "_qr_roundtrip_dump.mjs"
    if not (MOBILE / "dist-test" / "ui" / "qr.js").exists():
        print("dist-test is not built. Run: cd apps/mobile && npm test", file=sys.stderr)
        return 2
    script.write_text(DUMP % MOBILE)
    try:
        raw = subprocess.run(
            ["node", str(script), json.dumps(payloads)],
            capture_output=True, text=True, check=True,
        ).stdout
    finally:
        script.unlink(missing_ok=True)

    detector = cv2.QRCodeDetector()
    failures = 0
    for entry in json.loads(raw):
        decoded, _, _ = detector.detectAndDecode(render(entry))
        ok = decoded == entry["text"]
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {entry['size']}x{entry['size']} "
              f"{len(entry['text'])} bytes")
        if not ok:
            print(f"     in : {entry['text']}")
            print(f"     out: {decoded}")

    print(f"{len(CASES) - failures}/{len(CASES)} exact round-trips via OpenCV "
          f"{cv2.__version__}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
