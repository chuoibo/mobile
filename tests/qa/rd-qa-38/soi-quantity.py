"""Capture what the model actually puts in quantity_text, run after run.

The reliability runner reports codes. This one answers the next question: when
the code is INVALID_QUANTITY, what string did the reader send that the domain
refused? `_read_quantity` rejects the WHOLE receipt when any one item carries a
quantity_text that is not pure digits, so a single "x4" is enough to turn a bill
the model read correctly into "Không đọc được bill" for the person holding it.

Only run this on generated fixtures. It prints transcribed field values, which
on a real bill would be private data that must never reach a log.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "services/api"))

from app.api.vision_gemini import GeminiReceiptReader  # noqa: E402
from app.media.images import sanitize_image  # noqa: E402


def mot(reader, raw: bytes, sanitise: bool, i: int) -> dict:
    payload, mime = raw, "image/jpeg"
    if sanitise:
        s = sanitize_image(raw)
        payload, mime = s.data, s.content_type
    try:
        return {"lan": i, "raw": reader.read(payload, mime)}
    except Exception as exc:
        return {"lan": i, "loi": type(exc).__name__}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("anh")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--sanitise", action="store_true")
    args = ap.parse_args()

    raw = pathlib.Path(args.anh).read_bytes()
    reader = GeminiReceiptReader()
    with ThreadPoolExecutor(max_workers=6) as pool:
        ket = list(pool.map(lambda i: mot(reader, raw, args.sanitise, i), range(args.n)))

    hinh_dang = Counter()
    for r in ket:
        if "loi" in r:
            hinh_dang["<reader loi>"] += 1
            continue
        items = r["raw"].get("items", [])
        for it in items:
            if "quantity_text" not in it:
                hinh_dang["<khong co truong>"] += 1
            else:
                q = it["quantity_text"]
                ok = isinstance(q, str) and q.strip().isdigit()
                hinh_dang[f"{q!r} {'HOP LE' if ok else 'BI TU CHOI'}"] += 1

    print(f"# {pathlib.Path(args.anh).name}  sanitise={args.sanitise}  n={args.n}")
    for k, v in hinh_dang.most_common():
        print(f"  {v:3d}x  {k}")

    xau = sum(
        1
        for r in ket
        if "raw" in r
        and any(
            "quantity_text" in it
            and not (
                isinstance(it["quantity_text"], str)
                and it["quantity_text"].strip().isdigit()
            )
            for it in r["raw"].get("items", [])
        )
    )
    print(f"\nlan co it nhat MOT quantity_text bi tu choi: {xau}/{args.n}")


if __name__ == "__main__":
    main()
