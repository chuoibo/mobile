"""Point an INDEPENDENT decoder at the two QR codes this product draws.

## The claim this file attacks

Two QA reports of mine, and the `e2e-testing` skill itself, say the same thing:
"khong agent nao quet duoc ma QR" -- no agent can scan a QR code, so F05 and
F29 can only ever be filed as shells. That is half true, and the half that is
false is the expensive half.

What genuinely needs a human with a phone is *acceptance*: whether a Vietnamese
banking app takes the payload, resolves the acquirer through NAPAS and offers a
transfer. No amount of local computation touches that.

What does NOT need a phone is *decodability*: whether the square this product
paints, at the size it paints it, reads back as the exact string it was built
from. That is a machine question, and OpenCV (`cv2.QRCodeDetector`, installed
on this machine) answers it. Filing it under "needs a real phone" left a real
gap unmeasured, because the two codes here are painted by two different
encoders and one of them is written by hand in this repository:

  F29  services/api/app/web/qr.py       -> segno, a maintained library
  F05  apps/mobile/src/ui/qr.ts         -> ~400 lines of hand-rolled bit
                                           packing, Reed-Solomon and masking

A hand-rolled encoder that gets a mask penalty or an RS generator subtly wrong
still produces a square that looks exactly like a QR code in a screenshot and
in every `toBeDefined()` test. It fails only under a decoder. Nothing in this
repository has ever run one.

## The positive control matters more than usual here

`cv2.QRCodeDetector().detectAndDecode()` returns `""` for "I could not read
this". A broken OpenCV, a missing codec, a wrong dtype -- all of them return
`""` too, which is indistinguishable from "the product's QR is invalid" and
would let this file report a spectacular false bug. So every run first decodes
a square built by segno from the same payload. If that control does not come
back, the run refuses to report anything about the product.

Usage: python3 quet-ma-f05-f29.py
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import segno
from PIL import Image, ImageFilter

REPO = Path(__file__).resolve().parents[3]
MOBILE = REPO / "apps" / "mobile"

FAILURES: list[str] = []
NOTES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")
    return ok


def decode(image: Image.Image) -> str:
    """Read a QR out of a PIL image with OpenCV. '' means 'could not read'."""

    array = np.array(image.convert("RGB"))[:, :, ::-1]  # RGB -> BGR
    text, _points, _straight = cv2.QRCodeDetector().detectAndDecode(array)
    return text or ""


def matrix_to_png(matrix: list[list[bool]], px: int, quiet: int) -> Image.Image:
    """Paint a module matrix the way the React component paints it.

    `MaCuaToi.tsx` draws one `View` per run of dark modules at `px` device
    pixels each, on white, with `quiet` modules of margin. Reproducing those
    three numbers is the whole point: a QR that decodes at 20px per module and
    fails at the 2px floor the component can fall back to is a QR that works in
    a screenshot and fails on a phone.
    """

    size = len(matrix)
    side = (size + quiet * 2) * px
    image = Image.new("RGB", (side, side), (255, 255, 255))
    pixels = image.load()
    for r in range(size):
        for col in range(size):
            if not matrix[r][col]:
                continue
            x0 = (col + quiet) * px
            y0 = (r + quiet) * px
            for dx in range(px):
                for dy in range(px):
                    pixels[x0 + dx, y0 + dy] = (0, 0, 0)
    return image


def f05_matrix(payload: str) -> tuple[list[list[bool]], int]:
    """Run the product's OWN encoder, through node, and hand back its matrix.

    Importing the compiled `dist-test/ui/qr.js` rather than reimplementing the
    encoding in Python is deliberate: a Python reimplementation would be a
    second encoder, and this file would then be comparing two of my own guesses
    instead of measuring the one the app ships.
    """

    script = (
        "import { encodeQr } from './dist-test/ui/qr.js';\n"
        "const m = encodeQr(process.argv[2]);\n"
        "console.log(JSON.stringify({ size: m.size, modules: m.modules }));\n"
    )
    path = MOBILE / "__qa2_qr_dump.mjs"
    path.write_text(script)
    try:
        out = subprocess.run(
            ["node", str(path), payload],
            cwd=MOBILE,
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        path.unlink(missing_ok=True)
    if out.returncode != 0:
        raise RuntimeError(f"node that bai: {out.stderr[:500]}")
    data = json.loads(out.stdout.strip().splitlines()[-1])
    raw = data["modules"]
    size = data["size"]
    # `QrMatrix.modules` is a flat array in the shipped type; accept both shapes
    # rather than pinning to one and mis-reading a future refactor as a bug.
    if raw and isinstance(raw[0], list):
        matrix = [[bool(v) for v in row] for row in raw]
    else:
        matrix = [[bool(raw[r * size + c]) for c in range(size)] for r in range(size)]
    return matrix, size


def degrade(image: Image.Image, scale: float, blur: float) -> Image.Image:
    """Approximate a phone camera: fewer pixels, then softened edges."""

    # segno hands back a 1-bit image and GaussianBlur refuses that mode, so the
    # conversion is load-bearing, not tidying.
    side = max(21, int(image.width * scale))
    small = image.convert("RGB").resize((side, side), Image.LANCZOS)
    return small.filter(ImageFilter.GaussianBlur(blur)) if blur else small


def main() -> int:
    # ---------------------------------------------------------------- control
    control_payload = "QA2-DOI-CHUNG-DUONG-" + "x" * 40
    control = segno.make(control_payload, error="m")
    buffer = io.BytesIO()
    control.save(buffer, kind="png", scale=6, border=4)
    control_image = Image.open(io.BytesIO(buffer.getvalue()))
    control_read = decode(control_image)
    if not check(
        "DOI CHUNG DUONG: cv2 doc duoc mot ma QR do segno dung",
        control_read == control_payload,
        f"doc duoc {len(control_read)} ky tu, khop={control_read == control_payload}",
    ):
        print("\nMay quet hong -> TU CHOI bao cao bat ky ket luan nao ve san pham.")
        return 2

    # ------------------------------------------------------------------- F29
    # The payload comes from the product's own EMVCo builder, and the PNG from
    # the product's own renderer. Nothing here is rebuilt by this file.
    sys.path.insert(0, str(REPO / "services" / "api"))
    from app.payments.vietqr import build_payload  # noqa: E402
    from app.web.qr import payload_to_png_data_uri  # noqa: E402

    import base64

    payload_29 = build_payload(
        bank_bin="970415",
        # Synthetic, and deliberately the SAME shape as tests/web/test_qr.py so the
        # payload length here matches what the product actually encodes. No such
        # account exists. repo-guard: allow=long-number reason=so-tai-khoan-tong-hop-cho-phep-do-QR
        account_number="113366668888",
        amount_vnd=235000,
        note="RUDI test",
    )
    NOTES.append(f"F29 payload dai {len(payload_29)} ky tu")

    uri = payload_to_png_data_uri(payload_29)
    png = base64.b64decode(uri.split(",", 1)[1])
    image_29 = Image.open(io.BytesIO(png))
    read_29 = decode(image_29)
    check(
        "F29 anh VietQR do CHINH san pham ve, cv2 doc lai RA DUNG chuoi EMVCo",
        read_29 == payload_29,
        f"kich thuoc={image_29.size} doc={len(read_29)}/{len(payload_29)} ky tu khop={read_29 == payload_29}",
    )

    # ------------------------------------------------------------------- F05
    person_id = "3f2a91c4-5b6d-4e7f-8a9b-0c1d2e3f4a5b"
    payload_05 = f"rudi://ban/{person_id}?ten=Nguyen%20Van%20A"
    matrix, size = f05_matrix(payload_05)
    NOTES.append(f"F05 ma tran {size}x{size} modules, payload {len(payload_05)} ky tu")

    # The exact geometry MaCuaToi.tsx computes: TARGET 200, QUIET 4.
    px = max(2, (200) // (size + 8))
    image_05 = matrix_to_png(matrix, px=px, quiet=4)
    read_05 = decode(image_05)
    check(
        "F05 ma tran do BO MA HOA TU VIET cua repo, cv2 doc lai RA DUNG payload",
        read_05 == payload_05,
        f"px={px} anh={image_05.size} doc={read_05[:60]!r} khop={read_05 == payload_05}",
    )

    # ------------------------------------------------- margin under degrading
    # A clean 1:1 PNG is the easiest case a decoder ever sees. These rows say
    # how much room is left before it stops reading -- the closest a machine
    # gets to "will it scan across a table".
    print("\n-- bien do con lai khi lam xau anh (gan dung dieu kien camera) --")
    for label, image, want in (
        ("F29", image_29, payload_29),
        ("F05", image_05, payload_05),
    ):
        row = []
        for scale, blur in (
            (1.0, 0.0),
            (0.5, 0.0),
            (0.5, 1.0),
            (0.35, 1.0),
            (0.25, 1.5),
        ):
            got = decode(degrade(image, scale, blur))
            row.append(f"{int(scale * 100)}%/blur{blur}={'OK' if got == want else 'X'}")
        print(f"  {label}: " + "  ".join(row))
        NOTES.append(f"{label} bien do: " + " ".join(row))

    print("\n==================== TONG KET ====================")
    for note in NOTES:
        print("ghi chu:", note)
    if FAILURES:
        print(f"\nFAIL: {len(FAILURES)} phep kiem hong")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("\nOK: tat ca phep kiem xanh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
