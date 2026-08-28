#!/usr/bin/env python3
"""Repro: a blurry receipt makes POST /receipts/scan invent items, silently.

Chạy ca đã làm #55 FAIL. Một tấm bill MỜ vẫn là bill: server không từ chối nó
như ảnh phong cảnh, nó đọc — và bịa ra món không có trên giấy. Bản bịa lại tự
khớp tổng, nên `totals_agree=true` và `warnings=[]`: trông SẠCH HƠN kết quả đọc
bill thật (bill thật lệch 151.000 nên có cảnh báo).

Kịch bản (oracle tự chứa, không cần hằng số cứng cho từng bill):

  1. Gửi ảnh bill NÉT một lần  -> lấy làm sự thật nền (ground truth).
  2. Gửi CÙNG tấm bill đó đã làm mờ, N lần.
  3. Mỗi lần mờ mà trả HTTP 200 với tiền KHÁC bản nét mà `warnings` RỖNG
     -> một lần bịa im lặng.

Đó là dạng khẳng định theo tính chất, không so chuỗi: nội dung model bịa đổi
mỗi lần, nhưng hành vi "bịa mà không cảnh báo gì" thì đo được.

Hành vi ĐẠT (script thoát 0) là bất kỳ cái nào dưới đây:
  * 422 receipt_unreadable  — từ chối ảnh không đủ rõ, hoặc
  * 200 kèm cảnh báo        — đọc nhưng nói thẳng là không chắc.
Chỉ "200 + tiền khác + không một chữ cảnh báo" mới bị tính là trượt.

Ảnh bill KHÔNG BAO GIỜ nằm trong repo. Script nhận đường dẫn ảnh nguồn từ
ngoài cây làm việc, dựng bản mờ trong thư mục tạm, và xoá khi xong.

Ví dụ:

    python3 scripts/qc/repro_bill_mo_gemini_bia_mon.py \
        --api-base http://127.0.0.1:8155 \
        --bill-image /duong/dan/ngoai/repo/bill.png \
        --runs 5 --blur-radius 20

Thoát 0 = cổng giữ được (XANH). Thoát 1 = tái lập được lỗi (ĐỎ).
Thoát 2 = không chạy được (thiếu ảnh, server chết) — không phải kết luận.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path

_BOUNDARY = "----mobileqcblurboundary"


def _post_scan(api_base: str, image_path: Path, actor_id: str) -> tuple[int, dict]:
    """Upload one image over real HTTP; return (status, decoded body)."""

    payload = image_path.read_bytes()
    head = (
        f"--{_BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode()
    tail = f"\r\n--{_BOUNDARY}--\r\n".encode()
    body = head + payload + tail

    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/receipts/scan",
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={_BOUNDARY}",
            "X-Actor-ID": actor_id,
            "X-Actor-Roles": "member",
            # A fresh key per call: replaying one key would return the cached
            # answer instead of calling the model again, which would fake
            # stability we did not measure.
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:  # 4xx/5xx carry the payload we want
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw[:200]}


def _money_fingerprint(body: dict) -> tuple:
    """Reduce a scan response to the numbers a user would see as money."""

    items = body.get("items") or []
    return (
        len(items),
        tuple(item.get("line_total_vnd") for item in items),
        body.get("items_total_vnd"),
        body.get("total_vnd"),
    )


def _blur(source: Path, target: Path, radius: float, upscale: int) -> None:
    """Write a defocused copy, the way a shaky phone photo comes out."""

    from PIL import Image, ImageFilter

    image = Image.open(source).convert("RGB")
    if upscale > 1:
        image = image.resize(
            (image.width * upscale, image.height * upscale),
            Image.LANCZOS,
        )
    if radius > 0:
        image = image.filter(ImageFilter.GaussianBlur(radius=radius))
    image.save(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", required=True)
    parser.add_argument(
        "--bill-image",
        required=True,
        help="Ảnh bill NÉT, phải nằm NGOÀI repo.",
    )
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--blur-radius", type=float, default=20.0)
    parser.add_argument("--upscale", type=int, default=4)
    parser.add_argument("--actor-id", default=str(uuid.uuid4()))
    args = parser.parse_args()

    source = Path(args.bill_image).resolve()
    if not source.is_file():
        print(f"KHÔNG CHẠY ĐƯỢC: không thấy ảnh {source}", file=sys.stderr)
        return 2
    repo_root = Path(__file__).resolve().parents[2]
    if repo_root in source.parents:
        print(
            "KHÔNG CHẠY ĐƯỢC: ảnh bill nằm trong repo. Ảnh bill không bao giờ "
            "được đưa vào cây làm việc.",
            file=sys.stderr,
        )
        return 2

    workdir = Path(tempfile.mkdtemp(prefix="qc-bill-mo-"))
    try:
        sharp = workdir / "sharp.png"
        blurred = workdir / "blurred.png"
        _blur(source, sharp, radius=0, upscale=args.upscale)
        _blur(source, blurred, radius=args.blur_radius, upscale=args.upscale)

        status, body = _post_scan(args.api_base, sharp, args.actor_id)
        if status != 200:
            print(
                f"KHÔNG CHẠY ĐƯỢC: ảnh NÉT trả {status} {body}. Không có sự "
                "thật nền để so, nên không kết luận gì về ảnh mờ.",
                file=sys.stderr,
            )
            return 2
        truth = _money_fingerprint(body)
        print(
            f"[nét ] 200 items={truth[0]} items_total={truth[2]} "
            f"total={truth[3]} agree={body.get('totals_agree')} "
            f"warnings={len(body.get('warnings') or [])} "
            f"confidence={body.get('confidence')}"
        )

        fabrications = 0
        for attempt in range(1, args.runs + 1):
            status, body = _post_scan(args.api_base, blurred, args.actor_id)
            if status != 200:
                print(
                    f"[mờ {attempt}] {status} {body.get('code')} — từ chối, ĐẠT"
                )
                continue
            fingerprint = _money_fingerprint(body)
            warnings = body.get("warnings") or []
            silent = fingerprint != truth and not warnings
            fabrications += int(silent)
            print(
                f"[mờ {attempt}] 200 items={fingerprint[0]} "
                f"items_total={fingerprint[2]} total={fingerprint[3]} "
                f"agree={body.get('totals_agree')} warnings={len(warnings)} "
                f"confidence={body.get('confidence')} "
                f"-> {'BỊA IM LẶNG' if silent else 'chấp nhận được'}"
            )

        print(f"\nBịa im lặng: {fabrications}/{args.runs} lần.")
        if fabrications:
            print(
                "ĐỎ — ảnh bill mờ ra tiền khác ảnh nét mà không một chữ cảnh "
                "báo. Người dùng không có cách nào biết."
            )
            return 1
        print("XANH — không lần nào trả tiền bịa mà im lặng.")
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONWARNINGS", "ignore")
    raise SystemExit(main())
