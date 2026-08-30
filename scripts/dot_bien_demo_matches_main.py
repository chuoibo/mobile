#!/usr/bin/env python3
"""Bảng đột biến cho `check_demo_matches_main.py`: cổng gác được cái gì.

`tests/test_demo_matches_main_gate.py` xanh không chứng minh gì. Bảng này hỏi
câu còn lại: hỏng cái gì thì bộ test đỏ, và hỏng cái gì thì nó vẫn xanh.

Nguồn gốc: qa-tt-0033 đo bộ test này ra **7/11 = 64%** và để lại bốn lỗ hổng.
Bốn hàng dưới đây đúng là bốn cái đó, giữ nguyên tên qa3 đặt, để lần chạy sau
so được với con số cũ:

    VE-THAM-CHIEU-JOINPATH   lỗ hổng 1 — canary neo vào hình dạng chữ
    BO-KIEM-CONTENT-TYPE     lỗ hổng 2 — lọt về phía XANH GIẢ
    BO-HAN-FETCH             lỗ hổng 3 — nửa fetch không có ca nào
    FETCH-HONG-VAN-DI-TIEP   lỗ hổng 4 — cùng chỗ, hướng còn lại

Một bảng TOÀN ĐỎ cũng không phân biệt được gì — nó chỉ nói "bộ test nhạy", chứ
không nói nhạy với TÍNH CHẤT hay nhạy với một hằng số đi ngang qua. Nên có một
hàng GIỮ tính chất mà đổi hằng số (`GIU-TINH-CHAT-DOI-HANG-SO`), và hàng đó
PHẢI xanh.

Mỗi đột biến neo bằng chuỗi có thật đọc ra từ file, và script tự dừng nếu neo
không khớp đúng một lần — đoán tên rồi thấy đỏ vì NameError là cách một bảng
đột biến tự khen mình.

Chạy:  python3 scripts/dot_bien_demo_matches_main.py
Mã 0 nếu mọi hàng ra đúng màu đã khai; mã 1 nếu có hàng lệch.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "scripts" / "check_demo_matches_main.py"
SUITE = REPO_ROOT / "tests" / "test_demo_matches_main_gate.py"

RED, GREEN = "ĐỎ", "XANH"

# (tên, kỳ vọng, tính chất bị phá, neo, thay bằng)
MUTATIONS = [
    (
        "BO-HUONG-THIEU",
        RED,
        "demo đứng sau main không còn bị bắt",
        "    missing = sorted(declared - served)",
        "    missing = []",
    ),
    (
        "BO-HUONG-THUA",
        RED,
        "demo khoe route của nhánh chưa merge không còn bị bắt",
        "    extra = sorted(served - declared)",
        "    extra = []",
    ),
    (
        "ZERO-ROUTE-LA-DAT",
        RED,
        "máy chủ khai 0 route bị đọc thành khớp",
        '    if not paths:\n        die(f"{doc_url} khai 0 route.',
        '    if False:\n        die(f"{doc_url} khai 0 route.',
    ),
    (
        "GOP-MA-2-VAO-MA-1",
        RED,
        "'không chạy được' tụt xuống thành 'lệch' — ba trạng thái còn hai",
        "EXIT_CANNOT_RUN = 2",
        "EXIT_CANNOT_RUN = 1",
    ),
    (
        "KHONG-IN-TEN-ROUTE-THIEU",
        RED,
        "cổng đỏ mà không nói thiếu route nào — người đọc mù",
        "            for path in missing:",
        "            for path in []:",
    ),
    (
        "VE-THAM-CHIEU-JOINPATH",
        RED,
        "lỗ hổng 1 qa-tt-0033: đọc services/api của CÂY ĐANG ĐỨNG, viết bằng "
        ".joinpath nên canary đọc-chữ không thấy",
        '        api_dir = tree / "services" / "api"',
        '        api_dir = REPO_ROOT.joinpath("services", "api")',
    ),
    (
        "BO-KIEM-CONTENT-TYPE",
        RED,
        "lỗ hổng 2 qa-tt-0033: JSON hợp lệ + content-type nói dối ra mã 0",
        '    if ctype != "application/json":',
        "    if False:",
    ),
    (
        "DOC-LA-LIST-KHONG-KIEM",
        RED,
        "JSON top-level là list -> AttributeError, Python thoát mã 1 = 'lệch'",
        "    if not isinstance(doc, dict):",
        "    if False:",
    ),
    (
        "BO-HAN-FETCH",
        RED,
        "lỗ hổng 3 qa-tt-0033: không fetch nữa, so với origin/main có thể đã cũ",
        "    else:\n        fetch_ref(args.ref)",
        "    else:\n        pass",
    ),
    (
        "FETCH-HONG-VAN-DI-TIEP",
        RED,
        "lỗ hổng 4 qa-tt-0033: fetch hỏng mà vẫn so tiếp với ref không rõ tuổi",
        '    if out.returncode != 0:\n        die(\n            f"không fetch được',
        '    if False:\n        die(\n            f"không fetch được',
    ),
    (
        "GIU-TINH-CHAT-DOI-HANG-SO",
        GREEN,
        "(giữ tính chất) nới hạn dựng OpenAPI 180 -> 300 giây",
        "RENDER_TIMEOUT = 180",
        "RENDER_TIMEOUT = 300",
    ),
]


def target_is_committed() -> tuple[bool, str]:
    """Refuse to mutate a file that has uncommitted work in it.

    This script rewrites `TARGET` in place and puts it back in a `finally`. A
    Ctrl-C between those two, or a lane whose turn ends mid-run, leaves a
    mutated file on disk. If the file was committed first that is one
    `git checkout --` away; if it was not, the author's unsaved fix is gone and
    the only trace left is a deliberately broken guard.
    """
    done = subprocess.run(
        ["git", "status", "--porcelain", "--", str(TARGET)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if done.returncode != 0:
        return False, f"không hỏi được git: {done.stderr.strip()}"
    dirty = done.stdout.strip()
    return (not dirty), dirty


def run_suite() -> tuple[bool, str]:
    done = subprocess.run(
        [sys.executable, "-m", "pytest", str(SUITE), "-q", "--no-header"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=900,
    )
    last = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else ""
    return done.returncode == 0, last


def main() -> int:
    committed, dirty = target_is_committed()
    if not committed:
        print(
            f"!! {TARGET.relative_to(REPO_ROOT)} có thay đổi CHƯA COMMIT:\n"
            f"   {dirty}\n"
            "   Bảng này ghi đè file rồi khôi phục; đứt giữa chừng là mất bản sửa\n"
            "   đó vĩnh viễn. Commit trước rồi chạy lại."
        )
        return 1

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

    killed = sum(1 for _, expect, got, _, _, _ in rows if expect == RED and got == RED)
    total_red = sum(1 for _, expect, _, _, _, _ in rows if expect == RED)
    print(f"\nđột biến không-tương-đương bị giết: {killed}/{total_red}")

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
