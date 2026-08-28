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
  * 422 (receipt_too_blurry / receipt_unreadable / not_a_receipt) — server ĐÃ
    đọc ảnh rồi mới từ chối, hoặc
  * 200 kèm cảnh báo — đọc nhưng nói thẳng là không chắc.
Chỉ "200 + tiền khác + không một chữ cảnh báo" mới bị tính là trượt.

Mọi mã còn lại KHÔNG phải là ĐẠT và cũng không phải là trượt: 413
`image_too_large`, 415 `unsupported_image_type`, 5xx, hay lỗi mạng đều là từ
chối/hỏng TRƯỚC khi ảnh tới model — cổng đang được kiểm không chạy lần nào, nên
lượt đó là KHÔNG KẾT LUẬN (thoát 2), không được in XANH.

Kèm theo: mờ NHẸ làm PNG TO hơn (gradient nén kém hơn giấy phẳng), nên chính hai
mức mờ nhẹ — ca "ảnh chụp tay run", nguy hiểm nhất — là hai mức dễ vượt giới hạn
8 MB nhất. Script tự hạ độ phóng cho tới khi CẢ ảnh nét lẫn ảnh mờ lọt dưới giới
hạn rồi mới đo, và in rõ nó đã chạy ở độ phóng nào.

Ảnh bill KHÔNG BAO GIỜ nằm trong repo. Script nhận đường dẫn ảnh nguồn từ
ngoài cây làm việc, dựng bản mờ trong thư mục tạm, và xoá khi xong.

Ví dụ:

    python3 scripts/qc/repro_bill_mo_gemini_bia_mon.py \
        --api-base http://127.0.0.1:8155 \
        --bill-image /duong/dan/ngoai/repo/bill.png \
        --runs 5 --blur-radius 20

Thoát 0 = cổng giữ được (XANH). Thoát 1 = tái lập được lỗi (ĐỎ).
Thoát 2 = không chạy được hoặc không kết luận được (thiếu ảnh, server chết, ảnh
bị chặn vì dung lượng) — không phải một dấu xanh.
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

# Must match MAX_IMAGE_BYTES in services/api/app/api/receipt_skill.py. The
# server checks the uploaded bytes, not the multipart envelope, so this is the
# budget for the PNG alone.
_SERVER_MAX_IMAGE_BYTES = 8 * 1024 * 1024

# Statuses that mean "the reader ran and said no". Only these count as ĐẠT: a
# 422 is a judgement about the picture, which the server can only make after
# looking at it.
_SEMANTIC_REFUSAL = 422

# Why a non-200, non-422 answer proves nothing about the gate under test.
_NOT_A_VERDICT = {
    0: "không gọi được server",
    401: "chưa xác thực — chưa tới cổng đọc bill",
    413: "server chặn theo dung lượng, ảnh chưa tới model",
    415: "server từ chối định dạng, ảnh chưa tới model",
    500: "server lỗi, cổng không chạy",
    502: "reader không gọi được, cổng không chạy",
    503: "server không phục vụ, cổng không chạy",
}


def _post_scan(api_base: str, image_path: Path, actor_id: str) -> tuple[int, dict]:
    """Upload one image over real HTTP; return (status, decoded body).

    Status 0 means the request never reached an HTTP answer (connection
    refused, timeout). That is not a verdict either, so it is reported as a
    status the caller must treat as inconclusive rather than raised — an
    unhandled traceback would exit 1 and read as "the bug reproduced".
    """

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
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, {"code": "khong_goi_duoc_server", "detail": str(exc)[:200]}


def _money_fingerprint(body: dict) -> tuple:
    """Reduce a scan response to the numbers a user would see as money."""

    items = body.get("items") or []
    return (
        len(items),
        tuple(item.get("line_total_vnd") for item in items),
        body.get("items_total_vnd"),
        body.get("total_vnd"),
    )


def _blur(source: Path, target: Path, radius: float, scale: float) -> None:
    """Write a defocused copy, the way a shaky phone photo comes out."""

    from PIL import Image, ImageFilter

    image = Image.open(source).convert("RGB")
    if scale != 1:
        image = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            Image.LANCZOS,
        )
    if radius > 0:
        image = image.filter(ImageFilter.GaussianBlur(radius=radius))
    image.save(target)


def _scale_candidates(start: int):
    """Scales to try, biggest first: whole steps down to 1, then fractions."""

    scale = float(max(1, start))
    while scale >= 1:
        yield scale
        scale -= 1
    for fraction in (0.75, 0.5, 0.35, 0.25):
        yield fraction


def _fit_pair(
    source: Path,
    workdir: Path,
    radius: float,
    upscale: int,
    max_bytes: int,
) -> tuple[float, Path, Path] | None:
    """Render sharp+blurred at the biggest scale where BOTH payloads fit.

    The blurred copy has to be measured too, not just the source: blurring a
    document turns flat paper into gradients, and a lightly blurred PNG can be
    larger than the sharp one it came from. Sending an oversized payload buys a
    413 that tests nothing.
    """

    sharp = workdir / "sharp.png"
    blurred = workdir / "blurred.png"
    for scale in _scale_candidates(upscale):
        _blur(source, sharp, radius=0, scale=scale)
        _blur(source, blurred, radius=radius, scale=scale)
        sizes = (sharp.stat().st_size, blurred.stat().st_size)
        fits = max(sizes) <= max_bytes
        print(
            f"[dựng] scale={scale:g} nét={sizes[0] / 1e6:.2f} MB "
            f"mờ={sizes[1] / 1e6:.2f} MB giới hạn={max_bytes / 1e6:.2f} MB "
            f"-> {'dùng' if fits else 'quá to, hạ độ phóng'}"
        )
        if fits:
            return scale, sharp, blurred
    return None


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
    parser.add_argument(
        "--max-image-bytes",
        type=int,
        default=_SERVER_MAX_IMAGE_BYTES,
        help="Giới hạn ảnh của server đang kiểm; mặc định khớp MAX_IMAGE_BYTES.",
    )
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
        fitted = _fit_pair(
            source,
            workdir,
            radius=args.blur_radius,
            upscale=args.upscale,
            max_bytes=args.max_image_bytes,
        )
        if fitted is None:
            print(
                "KHÔNG CHẠY ĐƯỢC: ngay ở độ phóng nhỏ nhất, ảnh vẫn vượt giới "
                f"hạn {args.max_image_bytes} byte của server. Cổng đọc bill "
                "không chạy được lần nào nên không kết luận gì.",
                file=sys.stderr,
            )
            return 2
        scale, sharp, blurred = fitted
        if scale != args.upscale:
            print(
                f"[chú ý] chạy ở scale={scale:g} chứ không phải {args.upscale} "
                "— bản mờ ở độ phóng yêu cầu vượt giới hạn dung lượng."
            )

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
        untested = 0
        for attempt in range(1, args.runs + 1):
            status, body = _post_scan(args.api_base, blurred, args.actor_id)
            if status == _SEMANTIC_REFUSAL:
                print(
                    f"[mờ {attempt}] {status} {body.get('code')} — đọc rồi mới "
                    "từ chối, ĐẠT"
                )
                continue
            if status != 200:
                untested += 1
                why = _NOT_A_VERDICT.get(status, "cổng đọc bill không chạy")
                print(
                    f"[mờ {attempt}] {status} {body.get('code')} — KHÔNG KẾT "
                    f"LUẬN: {why}"
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

        print(
            f"\nBịa im lặng: {fabrications}/{args.runs} lần. "
            f"Không kết luận: {untested}/{args.runs} lần."
        )
        if fabrications:
            print(
                "ĐỎ — ảnh bill mờ ra tiền khác ảnh nét mà không một chữ cảnh "
                "báo. Người dùng không có cách nào biết."
            )
            return 1
        if untested:
            print(
                "KHÔNG KẾT LUẬN — có lượt server chặn trước khi model đọc ảnh, "
                "nên cổng đang được kiểm không chạy đủ. Đây KHÔNG phải xanh: "
                "sửa nguyên nhân (dung lượng, định dạng, reader) rồi chạy lại."
            )
            return 2
        print("XANH — không lần nào trả tiền bịa mà im lặng.")
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONWARNINGS", "ignore")
    raise SystemExit(main())
