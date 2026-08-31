"""Decode the F05 friend-code square with somebody else's decoder.

`apps/mobile/tools/qr-roundtrip.py` already does this for F29: it feeds the
server's VietQR payloads through `src/ui/qr.ts` and asks OpenCV to read the
modules back. It is a good check and it passes. What it does not cover is the
*other* caller of the same encoder.

`ui/qr.ts` is imported in exactly two places:

    ui/MaVietQr.tsx           F29, an EMVCo payment string
    screens/ca-nhan/MaCuaToi  F05, a friend link built by `linkMaBan`

Only the first has ever been round-tripped. That matters more than "one caller
was missed", because the two use different parts of the encoder. The four
VietQR cases land on 45x45 and 49x49 -- versions 7 and 8. `chooseVersion`
claims versions 1 through 15. So eleven of the fifteen version branches, and
the whole alignment-pattern table that changes shape with them, have never had
an independent reader look at their output.

A wrong module in a version nobody decodes is invisible in exactly the way
this repository keeps finding: the square renders, it looks like a QR code,
the layout test confirms it sits inside the viewport, and the first person to
learn it is unreadable is holding a phone.

What this proves: for every version the ladder reaches, the modules `qr.ts`
produces decode back through OpenCV to the exact string that went in, for the
real payload `linkMaBan` builds.

What it does NOT prove: that a phone's camera app resolves the link, that the
friend actually gets added, or that a bank accepts the F29 string. The first
two are `ket-ban-web.test.mjs`'s ground; the third needs a bank.

## Why the answer is read at several renderings and not one

The first draft of this probe painted every symbol one way -- quiet zone 4,
eight pixels per module, the same numbers `tools/qr-roundtrip.py` uses -- and
one rung came back unreadable. It looked like an encoder bug.

It was not. Two controls settled it. `segno`, an encoder that shares nothing
with `qr.ts`, produces a symbol for that same string that OpenCV *also* fails
to read at masks 0 and 2. And `qr.ts`'s own symbol for that string reads back
fine at quiet 4 / scale 4, and at quiet 8 / scale 8. Same modules, same
decoder, different answer -- so what the single rendering measured was
`cv2.QRCodeDetector`'s robustness on one bitmap, not what `qr.ts` encoded.

A one-rendering oracle is therefore wrong in both directions: it can call a
correct encoder broken, and the red it produces reads exactly like an encoder
regression to whoever sees it next. So a rung passes here if the exact string
comes back at *any* of the standard renderings below, and the canary has to
fail at *all* of them -- which is what keeps the check from turning into a
rubber stamp.

Run from the repo root (needs `apps/mobile/dist-test`, see --help):

    python3 tests/qa/qa3-ruot-nam-hang/probe_ma_qr_giai_nguoc.py
    python3 tests/qa/qa3-ruot-nam-hang/probe_ma_qr_giai_nguoc.py --canary
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[3]
MOBILE = ROOT / "apps" / "mobile"

# A real id this product could have minted. `linkMaBan` refuses anything that
# is not shaped like one, so a placeholder would measure the refusal path
# instead of the encoder.
ID = "9f2c41ab-7d63-8e15-a204-6b83cf90d712"

# Display names chosen to walk the version ladder rather than to be pretty.
# The Vietnamese ones matter on their own: `URLSearchParams` percent-encodes
# every diacritic to three ASCII characters, so a name that is short on screen
# is long in the payload -- "Nguyễn Thị Hà" is 13 characters and 43 bytes of
# link. That inflation is what pushes a friend code up a version, and it is
# invisible to anyone reading the name.
NAMES = [
    "Hà",
    "Minh Anh",
    "Nguyễn Thị Hà",
    "Nguyễn Thị Hồng Nhung",
    "Nguyễn Thị Hồng Nhung Phương Thảo",
    "N" * 60,
    "Nguyễn Thị Hồng Nhung " * 4,
    "N" * 160,
    "Nguyễn Thị Hồng Nhung " * 8,
    "N" * 200,
]

# Ask the product's own modules for both the payload and the matrix. Rebuilding
# either one here would score the encoder against a copy of itself, which is
# the failure CLAUDE.md names about the golden corpus.
DUMP = """
import { linkMaBan } from "%(mobile)s/dist-test/screens/vao-cua/ma-ban.js";
import { encodeQr } from "%(mobile)s/dist-test/ui/qr.js";
const out = [];
for (const ten of JSON.parse(process.argv[2])) {
  let text;
  try {
    text = linkMaBan("%(id)s", ten, "https://ru-di.app");
  } catch (e) {
    out.push({ ten, refused: "linkMaBan: " + e.message });
    continue;
  }
  try {
    const m = encodeQr(text);
    out.push({
      ten, text, size: m.size, version: m.version, mask: m.mask,
      rows: m.modules.map((r) => r.map((b) => (b ? 1 : 0)).join("")),
    });
  } catch (e) {
    // MaCuaToi.tsx turns this into "Tên hiển thị dài quá mức vẽ được thành mã".
    // A refusal is a real outcome, not a gap -- record it and keep walking.
    out.push({ ten, text, refused: "encodeQr: " + (e.code ?? e.message) });
  }
}
console.log(JSON.stringify(out));
"""


# Quiet zone 4 is the spec's minimum; the scales bracket what a phone screen
# actually shows (MaCuaToi targets 200px across the whole symbol).
RENDERINGS = [(4, 4), (4, 8), (6, 8), (8, 8), (8, 12)]


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


def doc_lai(detector, entry: dict) -> tuple[int, str]:
    """Read one symbol at every standard rendering.

    Returns how many agreed exactly, and one disagreeing answer to print. A
    rung needs one agreement to pass; the canary needs zero.
    """
    khop = 0
    khac = ""
    for quiet, scale in RENDERINGS:
        decoded, _, _ = detector.detectAndDecode(render(entry, quiet, scale))
        if decoded == entry["text"]:
            khop += 1
        elif not khac:
            khac = decoded
    return khop, khac


#: Flip one module in every STRIDE, in row-major order. See `corrupt`.
STRIDE = 5


def corrupt(entry: dict) -> dict:
    """Flip every STRIDE-th module, spread across the whole symbol.

    Two earlier shapes of this canary both reported the probe alive when it was
    not, and both were wrong for the same underlying reason -- worth keeping,
    because the reason is the thing that makes QR hard to canary at all.

    The first walked outward from the centre in concentric squares and
    revisited inner cells on every pass, flipping them back; the count said 40
    and almost nothing changed.

    The second fixed the double-flip and still decoded clean. That one was not
    a coding mistake: 40 *distinct* modules packed into one 7x7 blob at the
    centre land inside only a handful of codewords, and level M carries enough
    Reed-Solomon to rebuild a handful of codewords exactly. The symbol came
    back byte-identical because error correction did its job.

    So damage has to be spread, not concentrated. At one module in five, every
    block of the symbol is hit and the count of broken codewords goes far past
    what any EC level can rebuild -- which is the shape a genuinely wrong
    encoder would produce, and the only shape that proves this probe can say
    no.
    """

    hurt = dict(entry)
    rows = [list(r) for r in entry["rows"]]
    size = entry["size"]
    flipped = 0
    for r in range(size):
        for c in range(size):
            if (r * size + c) % STRIDE == 0:
                rows[r][c] = "0" if rows[r][c] == "1" else "1"
                flipped += 1

    hurt["rows"] = ["".join(row) for row in rows]
    hurt["flipped"] = flipped
    return hurt


def dump() -> list[dict]:
    if not (MOBILE / "dist-test" / "ui" / "qr.js").exists():
        print(
            "dist-test chưa dựng. Chạy:\n"
            "  cd apps/mobile && npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs",
            file=sys.stderr,
        )
        raise SystemExit(2)
    # The scratch module goes in a temp directory, not in `dist-test`, even
    # though `dist-test` is a build output and git ignores it. #424 landed the
    # general form of this on main the same day: a check that writes into the
    # real client tree races anything else building there, and the red it
    # produces is not reproducible afterwards. The imports below are absolute,
    # so node resolves them from anywhere and nothing is lost by moving out.
    with tempfile.TemporaryDirectory(prefix="qa3-qr-") as tmp:
        script = pathlib.Path(tmp) / "dump.mjs"
        script.write_text(DUMP % {"mobile": MOBILE, "id": ID})
        done = subprocess.run(
            ["node", str(script), json.dumps(NAMES)],
            capture_output=True,
            text=True,
            check=True,
        )
    return json.loads(done.stdout)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--canary",
        action="store_true",
        help="corrupt the modules first; every ladder rung must then DISAGREE",
    )
    args = ap.parse_args()

    entries = dump()
    detector = cv2.QRCodeDetector()
    drawn = [e for e in entries if "rows" in e]
    refused = [e for e in entries if "rows" not in e]

    if args.canary:
        # 40 modules is comfortably past level-M error correction at every
        # version this ladder reaches, so a decoder that still agrees is not
        # reading the modules at all.
        print(
            f"CANARY: cứ {STRIDE} module lật 1, rải khắp symbol — mọi bậc PHẢI "
            f"lệch ở CẢ {len(RENDERINGS)} cách vẽ\n"
        )
        still_agree = 0
        for entry in drawn:
            pha = corrupt(entry)
            khop, khac = doc_lai(detector, pha)
            still_agree += khop > 0
            if khop:
                # Never print a decoder answer here: with khop > 0 the symbol
                # still read back as the original, and any string shown beside
                # it would be read as the corruption having landed.
                noi = "VAN KHOP — bản phá vẫn đọc ra đúng chuỗi gốc"
            else:
                noi = "lech     " + (
                    "(không giải được)" if khac == "" else repr(khac[:40])
                )
            print(
                f"v{entry['version']:>2} {entry['size']}x{entry['size']} "
                f"lật {pha['flipped']:>4} module  khớp {khop}/{len(RENDERINGS)}  {noi}"
            )
        print(
            f"\n{len(drawn) - still_agree}/{len(drawn)} bậc lệch khi bị phá. "
            f"{'PHÉP ĐO SỐNG.' if still_agree == 0 else 'PHÉP ĐO CHẾT — có bậc vẫn khớp.'}"
        )
        return 1 if still_agree else 0

    failures = 0
    versions = set()
    for entry in drawn:
        khop, khac = doc_lai(detector, entry)
        ok = khop > 0
        failures += not ok
        versions.add(entry["version"])
        print(
            f"{'ok  ' if ok else 'FAIL'} v{entry['version']:>2} "
            f"{entry['size']}x{entry['size']} mask{entry['mask']} "
            f"{len(entry['text']):>3} bytes  tên {len(entry['ten']):>3} ký tự  "
            f"khớp {khop}/{len(RENDERINGS)} cách vẽ"
        )
        if not ok:
            print(f"     vào : {entry['text']}")
            print(f"     ra  : {khac}")

    for entry in refused:
        # Not a failure. MaCuaToi renders a sentence for this, and a square that
        # refuses to be drawn is safer than one drawn half-finished.
        print(f"tu choi  tên {len(entry['ten']):>3} ký tự  {entry['refused']}")

    print(
        f"\n{len(drawn) - failures}/{len(drawn)} giải ngược khớp tuyệt đối qua "
        f"OpenCV {cv2.__version__}"
    )
    print(
        f"version chạm được: {sorted(versions)}  ({len(refused)} bậc bị encoder từ chối)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
