"""Measure receipt-reading reliability with and without the #209 sanitiser.

rd-qa-37 measured one number and could not explain it: the same file, byte for
byte, read back 6 times out of 11. #209 wired `sanitize_image` into
`/receipts/scan` for a privacy reason, and the lead then measured 22/22 on a
different bill. Either the privacy patch accidentally fixed a reliability bug on
the hero path, or the two measurements used different inputs and agree about
nothing.

This runner answers that by holding everything else still. One process, one
image, one reader; the only variable is whether `sanitize_image` runs. The
"before" arm is not a story about old code -- it is the exact body
`run_receipt_skill` had before #209, replayed here:

    if not image: EMPTY_IMAGE
    if mime not allowed: UNSUPPORTED_IMAGE_TYPE
    if len(image) > MAX: IMAGE_TOO_LARGE
    result = read_scanned_document(reader.read(image, mime_type))

so a difference between the arms can only come from the one call between them.
That makes this a revert-to-verify, not a comparison of two eras.

Every outcome is recorded as its ReceiptError CODE, never as receipt content:
these fixtures are generated, but the habit is the point -- a bill is private
data and the code is the only part worth keeping.

A backend fault (rate limit, transport) surfaces as RuntimeError from the reader
and is counted in its own bucket. Folding an HTTP 429 into "unreadable" would
manufacture exactly the flakiness this run exists to measure.
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "services/api"))

from app.api.receipt_skill import (  # noqa: E402
    ALLOWED_MIME_TYPES,
    MAX_IMAGE_BYTES,
    run_receipt_skill,
)
from app.api.vision_gemini import GeminiReceiptReader  # noqa: E402
from app.domain.receipt import ReceiptError, read_scanned_document  # noqa: E402


def truoc_209(image: bytes, mime_type: str, *, reader) -> dict:
    """Replay `run_receipt_skill` exactly as it stood before #209."""

    if not image:
        raise ReceiptError("EMPTY_IMAGE")
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ReceiptError("UNSUPPORTED_IMAGE_TYPE")
    if len(image) > MAX_IMAGE_BYTES:
        raise ReceiptError("IMAGE_TOO_LARGE")
    result = read_scanned_document(reader.read(image, mime_type))
    result.pop("confidence", None)
    return result


def _reencode(raw: bytes, quality: int, optimize: bool) -> bytes:
    """Re-encode without the sanitiser, to separate re-encoding from quality."""

    with Image.open(io.BytesIO(raw)) as src:
        src.load()
        out = io.BytesIO()
        src.convert("RGB").save(out, format="JPEG", quality=quality, optimize=optimize)
        return out.getvalue()


ARMS = {
    # The two arms that answer the question. Everything else is diagnosis.
    "truoc": lambda raw, reader: truoc_209(raw, "image/jpeg", reader=reader),
    "sau": lambda raw, reader: run_receipt_skill(raw, "image/jpeg", reader=reader),
    # Was it the re-encode itself, or specifically quality 88 + optimize? This
    # arm re-encodes at the fixture's own quality and skips the sanitiser.
    "q92": lambda raw, reader: truoc_209(
        _reencode(raw, 92, False), "image/jpeg", reader=reader
    ),
}


def mot_lan(arm: str, raw: bytes, reader, i: int) -> dict:
    """Run one call and describe it by outcome code only."""

    t0 = time.monotonic()
    try:
        result = ARMS[arm](raw, reader)
    except ReceiptError as exc:
        return {
            "lan": i,
            "arm": arm,
            "ket": "LOI",
            "ma": exc.code,
            "giay": round(time.monotonic() - t0, 2),
        }
    except Exception as exc:  # reader transport / rate limit, not a bad photo
        return {
            "lan": i,
            "arm": arm,
            "ket": "HATANG",
            "ma": type(exc).__name__ + ":" + str(exc)[:40],
            "giay": round(time.monotonic() - t0, 2),
        }
    return {
        "lan": i,
        "arm": arm,
        "ket": "OK",
        "ma": None,
        "so_mon": len(result.get("items", [])),
        "tong": result.get("total_vnd"),
        "can_duyet": result.get("needs_review"),
        "giay": round(time.monotonic() - t0, 2),
    }


def wilson(k: int, n: int) -> tuple[float, float]:
    """95% Wilson interval -- honest at the boundaries where normal-approx is not."""

    if n == 0:
        return (0.0, 1.0)
    z = 1.959964
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("anh", help="path to the fixture")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--arms", default="truoc,sau")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--nhan", default="")
    ap.add_argument("--ra", default="/tmp/rd-qa-38-kq")
    args = ap.parse_args()

    raw = pathlib.Path(args.anh).read_bytes()
    reader = GeminiReceiptReader()
    ten = args.nhan or pathlib.Path(args.anh).name
    out = pathlib.Path(args.ra)
    out.mkdir(parents=True, exist_ok=True)

    with Image.open(io.BytesIO(raw)) as im:
        kich = im.size
    print(f"# {ten}  {len(raw):,d} bytes  {kich[0]}x{kich[1]}  n={args.n}/arm")

    tat_ca = []
    for arm in args.arms.split(","):
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            ket = list(
                pool.map(lambda i: mot_lan(arm, raw, reader, i), range(1, args.n + 1))
            )
        ket.sort(key=lambda r: r["lan"])
        tat_ca.extend(ket)

        ok = [r for r in ket if r["ket"] == "OK"]
        loi = [r for r in ket if r["ket"] == "LOI"]
        ha = [r for r in ket if r["ket"] == "HATANG"]
        n_that = len(ok) + len(loi)  # infra faults are not evidence about reading
        lo, hi = wilson(len(ok), n_that) if n_that else (0.0, 1.0)

        ma_dem: dict[str, int] = {}
        for r in loi:
            ma_dem[r["ma"]] = ma_dem.get(r["ma"], 0) + 1
        tong_set = {r["tong"] for r in ok}
        mon_set = {r["so_mon"] for r in ok}

        print(
            f"{arm:6s} doc duoc {len(ok):2d}/{n_that:2d}"
            f"  = {len(ok) / n_that * 100 if n_that else 0:5.1f}%"
            f"  [95% CI {lo * 100:.1f}-{hi * 100:.1f}]"
            f"  ma loi={ma_dem or '-'}  hatang={len(ha)}"
        )
        print(f"       tong khi doc duoc={tong_set or '-'}  so mon={mon_set or '-'}")
        if ha:
            print(f"       HA TANG: {[r['ma'] for r in ha][:3]}")

    (out / f"{ten}.json").write_text(json.dumps(tat_ca, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
