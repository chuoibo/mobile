#!/usr/bin/env python3
"""Bảng đột biến cho `demo_watch.py`: cái gì thật sự được gác, cái gì không.

`tests/test_demo_watch.py` xanh không chứng minh gì. Bảng này hỏi câu còn lại:
hỏng cái gì thì nó đỏ, và hỏng cái gì thì nó vẫn xanh.

Một bảng TOÀN ĐỎ cũng không phân biệt được gì — nó chỉ nói "bộ test nhạy", chứ
không nói nhạy với TÍNH CHẤT hay nhạy với một hằng số đi ngang qua. Nên có một
hàng GIỮ tính chất mà đổi hằng số (`GIU-NGUONG`), và hàng đó PHẢI xanh. Nếu nó
đỏ thì bộ test đang ghim con số 1800 chứ không ghim luật "có ngưỡng quá hạn".

Mỗi đột biến được neo bằng chuỗi có thật, đọc ra từ file, và script tự dừng nếu
neo không khớp đúng một lần — đoán tên rồi thấy đỏ vì NameError là cách một
bảng đột biến tự khen mình.

Chạy:  python3 scripts/dot_bien_demo_watch.py
Mã 0 nếu mọi hàng ra đúng màu đã khai; mã 1 nếu có hàng lệch.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "scripts" / "demo_watch.py"
SUITE = REPO_ROOT / "tests" / "test_demo_watch.py"

RED, GREEN = "ĐỎ", "XANH"

# (tên, kỳ vọng, tính chất bị phá, neo, thay bằng)
MUTATIONS = [
    (
        "THIEU-FILE-LA-DAT",
        RED,
        "chưa có bản ghi nào bị đọc thành 'không có vấn đề'",
        '    if not path.is_file():\n        return cannot(\n            f"chưa có {path}.',
        '    if not path.is_file():\n        return EXIT_OK\n        return cannot(\n            f"chưa có {path}.',
    ),
    (
        "BO-NGUONG-QUA-HAN",
        RED,
        "canh gác đã dừng nhưng phán quyết cũ vẫn được coi là còn giá trị",
        "    if age > args.max_age:",
        "    if False:",
    ),
    (
        "KHONG-SO-DUOC-LA-DAT",
        RED,
        "lượt canh 'không đối chiếu được' bị đọc thành khớp",
        '    if data.get("state") == STATE_CANNOT:\n        return khong_doi_chieu_duoc()',
        '    if data.get("state") == STATE_CANNOT:\n        return EXIT_OK',
    ),
    (
        "LY-DO-BI-NUOT-BOI-KIEM-REF",
        RED,
        "bản ghi hỏng rơi vào phép kiểm --expect-ref, ra 'phán quyết về None' và "
        "nuốt lý do thật — mã đúng, chẩn đoán sai",
        '    if data.get("state") == STATE_CANNOT:\n        return khong_doi_chieu_duoc()\n\n',
        "",
    ),
    (
        "TRANG-THAI-LA-LA-DAT",
        RED,
        "state lạ (bản ghi của bản sau, hoặc bị sửa tay) bị đọc thành khớp",
        "    # Any state that is neither khop nor lech: a record this version does not\n"
        "    # know how to read is not a pass.\n"
        "    return khong_doi_chieu_duoc()",
        "    return EXIT_OK",
    ),
    (
        "BAN-GHI-LA-VAN-DOC",
        RED,
        "bản ghi sai schema vẫn được diễn giải như bản ghi hợp lệ",
        '    if not isinstance(data, dict) or data.get("schema") != SCHEMA:',
        "    if False:",
    ),
    (
        "CONG-LAY-TU-CAY-DANG-DUNG",
        RED,
        "chạy cổng của checkout đang đứng thay vì của ref vừa fetch",
        "        gate = tree / GATE_RELPATH",
        "        gate = repo / GATE_RELPATH",
    ),
    (
        "GOP-MA-2-VAO-MA-1",
        RED,
        "'không chạy được' tụt xuống thành 'lệch' — ba trạng thái còn hai",
        '        return cannot(\n            f"cổng trả mã {proc.returncode}',
        '        return EXIT_DIFFERS\n        return cannot(\n            f"cổng trả mã {proc.returncode}',
    ),
    (
        "NUOT-JSON-HONG-THANH-RONG",
        RED,
        "đúng lỗi bản đầu: 'KHỚP — phục vụ đúng None route' kèm mã 0",
        "    try:\n        value, _ = json.JSONDecoder().raw_decode(text)\n"
        "    except json.JSONDecodeError:\n        return None",
        "    try:\n        value = json.loads(text)\n"
        "    except json.JSONDecodeError:\n        return {}",
    ),
    (
        "XOA-CA-CRONTAB-NGUOI-KHAC",
        RED,
        "gỡ khối canh gác nuốt luôn mục crontab không liên quan",
        "        if not inside:",
        "        if False:",
    ),
    (
        "GIU-NGUONG-DOI-HANG-SO",
        GREEN,
        "(giữ tính chất) đổi mặc định 30 phút -> 60 phút",
        "DEFAULT_MAX_AGE = 1800",
        "DEFAULT_MAX_AGE = 3600",
    ),
]


def run_suite() -> tuple[bool, str]:
    done = subprocess.run(
        [sys.executable, "-m", "pytest", str(SUITE), "-q", "--no-header", "-x"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=900,
    )
    return done.returncode == 0, done.stdout.strip().splitlines()[
        -1
    ] if done.stdout else ""


def main() -> int:
    original = TARGET.read_text(encoding="utf-8")

    ok, line = run_suite()
    if not ok:
        print(f"Cây sạch đã ĐỎ sẵn — bảng này vô nghĩa cho tới khi sửa:\n{line}")
        return 1
    print(f"cây sạch: XANH  ({line})\n")

    rows, failures = [], 0
    try:
        for name, expect, prop, anchor, replacement in MUTATIONS:
            count = original.count(anchor)
            if count != 1:
                print(f"!! neo của {name} khớp {count} lần, phải đúng 1. Dừng.")
                return 1
            TARGET.write_text(
                original.replace(anchor, replacement, 1), encoding="utf-8"
            )
            passed, last = run_suite()
            got = GREEN if passed else RED
            agree = got == expect
            failures += 0 if agree else 1
            rows.append((name, expect, got, agree, prop, last))
    finally:
        TARGET.write_text(original, encoding="utf-8")

    width = max(len(r[0]) for r in rows)
    print(f"{'ĐỘT BIẾN'.ljust(width)}  KỲ VỌNG  THỰC TẾ  ĐÚNG  TÍNH CHẤT")
    for name, expect, got, agree, prop, _ in rows:
        mark = "v" if agree else "X"
        print(
            f"{name.ljust(width)}  {expect.ljust(7)}  {got.ljust(7)}  {mark}     {prop}"
        )

    print()
    restored_ok, line = run_suite()
    print(f"khôi phục: {'XANH' if restored_ok else 'ĐỎ'}  ({line})")
    if not restored_ok:
        print("!! khôi phục xong mà vẫn đỏ — file gốc chưa về đúng chỗ.")
        return 1
    if failures:
        print(f"!! {failures} hàng lệch kỳ vọng.")
        return 1
    print(f"{len(rows)} hàng đúng kỳ vọng.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
