#!/usr/bin/env python3
"""Chạy lại bảng đột biến mà `test_tran_quet_bill.py` dựa vào.

Cổng nào cũng chỉ đáng tin bằng lần cuối có người thấy nó đỏ. Script này là
lần đó, để dành: nó sửa `app/api/search_rate_limit.py` từng đột biến một, chạy
lại cổng, rồi khôi phục cây.

Chạy từ gốc repo::

    python3 tests/qa/qa-tt-0005/dot-bien-tran-quet-bill.py           # chỉ cổng mới
    python3 tests/qa/qa-tt-0005/dot-bien-tran-quet-bill.py --day-du  # cả bộ test

Kỳ vọng: mọi đột biến ĐỎ, và ca đối chứng `N1` (sửa 30 thành 30) XANH. Ca N1
tồn tại vì một bộ đột biến toàn đỏ cũng là thứ mà một cổng hỏng-luôn sinh ra.

Hai chi tiết đã cắn người viết repo này trước đây và được xử lý ở đây:

* cây được khôi phục bằng cách ghi lại nguyên văn nội dung cũ, không phải
  ``git checkout --`` — lệnh đó khôi phục về HEAD và sẽ xoá luôn bản sửa chưa
  commit của người đang chạy;
* ``__pycache__`` bị xoá sau mỗi lượt, vì một tệp ``.pyc`` cũ đọc y hệt một
  đột biến đã dính.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
NGUON = ROOT / "services" / "api" / "app" / "api" / "search_rate_limit.py"
CONG = "../../tests/qa/qa-tt-0005"
CA_BO = ["tests", str(ROOT / "tests")]

TRAN = "RECEIPT_SCAN_LIMIT_PER_WINDOW = 30"
CUA_SO = "RECEIPT_SCAN_WINDOW_SECONDS = 60"
DUNG_TRAN = "        limit=RECEIPT_SCAN_LIMIT_PER_WINDOW,"
DUNG_CUA_SO = "        window_seconds=RECEIPT_SCAN_WINDOW_SECONDS,"

# (tên, cũ, mới, có phải ca đối chứng phải-xanh không)
DOT_BIEN = [
    ("M09  trần 30 → 3000 (trần biến mất)", TRAN, TRAN.replace("30", "3000"), False),
    ("M09b trần 30 → 61 (vừa quá chặn trên)", TRAN, TRAN.replace("30", "61"), False),
    ("M10  trần 30 → 1 (hero chết ở lượt 2)", TRAN, TRAN.replace("30", "1"), False),
    ("M10b trần 30 → 19 (vừa dưới chặn dưới)", TRAN, TRAN.replace("30", "19"), False),
    (
        "M11  cửa sổ 60 → 1 (trần/phút → /giây)",
        CUA_SO,
        CUA_SO.replace("60", "1"),
        False,
    ),
    (
        "M11b cửa sổ 60 → 3600 (chặn cả tiếng)",
        CUA_SO,
        CUA_SO.replace("60", "3600"),
        False,
    ),
    # Cùng vi phạm, viết bằng hình dạng khác: hằng số còn nguyên, chỗ dùng bị
    # sửa. Một cổng chỉ đọc hằng số sẽ mù với cả ba ca dưới đây.
    (
        "C1   factory nhân trần lên 100 lần",
        DUNG_TRAN,
        f"{DUNG_TRAN[:-1]} * 100,",
        False,
    ),
    (
        "C2   factory hạ cửa sổ xuống 1 giây",
        DUNG_CUA_SO,
        "        window_seconds=1,",
        False,
    ),
    (
        "C3   factory dùng lại cấu hình của SEARCH",
        DUNG_TRAN,
        "        limit=SEARCH_LIMIT_PER_WINDOW,",
        False,
    ),
    ("N1   ĐỐI CHỨNG: giữ nguyên 30", TRAN, TRAN, True),
]


def _xoa_pycache() -> None:
    for thu_muc in ROOT.rglob("__pycache__"):
        shutil.rmtree(thu_muc, ignore_errors=True)


def _chay(duong_dan: list[str]) -> tuple[bool, str]:
    ket_qua = subprocess.run(
        [sys.executable, "-m", "pytest", *duong_dan, "-q", "--no-header", "--tb=line"],
        cwd=ROOT / "services" / "api",
        capture_output=True,
        text=True,
    )
    dong = [d for d in ket_qua.stdout.splitlines() if d.strip()]
    return ket_qua.returncode == 0, dong[-1] if dong else "(không có output)"


def main() -> int:
    duong_dan = CA_BO if "--day-du" in sys.argv else [CONG]
    goc = NGUON.read_text(encoding="utf-8")

    _xoa_pycache()
    xanh, dong = _chay(duong_dan)
    print(f"NỀN (chưa đột biến): {'XANH' if xanh else 'ĐỎ'} — {dong}\n")
    if not xanh:
        print("nền không xanh, dừng lại — mọi con số phía dưới sẽ vô nghĩa")
        return 1

    sai = 0
    try:
        for ten, cu, moi, phai_xanh in DOT_BIEN:
            if goc.count(cu) != 1:
                print(f"BỎ QUA | {ten} — neo khớp {goc.count(cu)} lần")
                sai += 1
                continue
            NGUON.write_text(goc.replace(cu, moi), encoding="utf-8")
            _xoa_pycache()
            xanh, dong = _chay(duong_dan)
            NGUON.write_text(goc, encoding="utf-8")
            _xoa_pycache()

            dat = xanh if phai_xanh else not xanh
            sai += 0 if dat else 1
            nhan = "XANH" if xanh else "ĐỎ  "
            print(f"{'   ' if dat else '!!!'} {nhan} | {ten}\n           → {dong}")
    finally:
        NGUON.write_text(goc, encoding="utf-8")
        _xoa_pycache()

    print(f"\n{'ĐẠT' if sai == 0 else f'KHÔNG ĐẠT: {sai} ca sai kỳ vọng'}")
    return 0 if sai == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
