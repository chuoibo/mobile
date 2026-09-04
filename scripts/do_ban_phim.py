#!/usr/bin/env python3
"""Đo hình học bàn phím trên máy ảo Android (V3, M3): ô soạn và bong bóng cuối
có nằm TRÊN mép bàn phím không.

Không tin thư viện, không tin prop `behavior`: đọc ba nguồn thật của hệ điều hành
sau khi một flow đã mở bàn phím và dừng lại (flow 31):

  1. `dumpsys input_method` → IME có đang hiện không (`mInputShown=true`).
     Không hiện thì KHÔNG ĐO ĐƯỢC (exit 2), không phải ĐẠT: một phép đo trên màn
     không có bàn phím sẽ luôn xanh.
  2. `dumpsys window` → khung của IME (InsetsSource ime, `frame=[l,t][r,b]`),
     lấy mép trên nhỏ nhất trong các khung có chiều cao > 0.
  3. `uiautomator dump` → bounds của ô soạn (content-desc = --composer) và của
     bong bóng thấp nhất (content-desc bắt đầu bằng --bubble-prefix).

ĐẠT khi composer.bottom <= imeTop - 8 và (nếu có bong bóng) bubble.bottom <= imeTop.
In bốn số để người đọc tự kiểm. Exit 0 ĐẠT, 1 HỎNG, 2 KHÔNG ĐO ĐƯỢC.

Đối chứng âm: chạy với app có EXPO_PUBLIC_QA_TAT_KAV=1 (tắt KeyboardAvoidingView)
thì phép đo này phải HỎNG; xanh ở đó là phép đo mù.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


def adb(serial: str, *args: str) -> str:
    cmd = ["adb"] + (["-s", serial] if serial else []) + list(args)
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return out.stdout


def ime_shown(serial: str) -> bool:
    text = adb(serial, "shell", "dumpsys", "input_method")
    return bool(re.search(r"mInputShown=true|mIsInputViewShown=true", text))


def ime_top(serial: str) -> int | None:
    text = adb(serial, "shell", "dumpsys", "window")
    tops: list[int] = []
    for line in text.splitlines():
        if "ime" not in line.lower() or "frame=[" not in line:
            continue
        for m in re.finditer(r"frame=\[(\d+),(\d+)\]\[(\d+),(\d+)\]", line):
            trai, t, r, b = map(int, m.groups())
            if b - t > 0 and r - trai > 0:
                tops.append(t)
    return min(tops) if tops else None


def bounds_of(node: ET.Element) -> tuple[int, int, int, int]:
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.attrib.get("bounds", ""))
    if not m:
        raise ValueError("bounds")
    return tuple(int(x) for x in m.groups())  # type: ignore[return-value]


def ui_tree(serial: str) -> ET.Element:
    adb(serial, "shell", "uiautomator", "dump", "/sdcard/rudi-ui.xml")
    xml = adb(serial, "shell", "cat", "/sdcard/rudi-ui.xml")
    return ET.fromstring(xml)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default="")
    ap.add_argument("--composer", default="Ô soạn tin")
    ap.add_argument("--bubble-prefix", default="Tin nhắn: ")
    ap.add_argument(
        "--khe", type=int, default=8, help="khe tối thiểu giữa ô soạn và bàn phím (px)"
    )
    a = ap.parse_args()

    if not ime_shown(a.serial):
        print(
            "KHÔNG ĐO ĐƯỢC: bàn phím không đang hiện (mInputShown=false). Chạy flow 31 trước."
        )
        return 2
    top = ime_top(a.serial)
    if top is None:
        print("KHÔNG ĐO ĐƯỢC: không đọc được khung IME từ dumpsys window.")
        return 2
    try:
        tree = ui_tree(a.serial)
    except ET.ParseError:
        print("KHÔNG ĐO ĐƯỢC: uiautomator dump không ra XML.")
        return 2
    composer = None
    bubbles = []
    for node in tree.iter("node"):
        desc = node.attrib.get("content-desc", "")
        if desc == a.composer:
            composer = bounds_of(node)
        elif desc.startswith(a.bubble_prefix):
            bubbles.append(bounds_of(node))
    if composer is None:
        print(
            f"KHÔNG ĐO ĐƯỢC: không thấy ô soạn (content-desc «{a.composer}») trong cây UI."
        )
        return 2
    bubble_bottom = max((b[3] for b in bubbles), default=None)
    print(
        f"imeTop={top} composerBottom={composer[3]} lastBubbleBottom={bubble_bottom} khe={top - composer[3]}"
    )
    ok = composer[3] <= top - a.khe and (bubble_bottom is None or bubble_bottom <= top)
    if ok:
        print("ĐẠT: ô soạn và bong bóng cuối nằm trên mép bàn phím.")
        return 0
    print("HỎNG: bàn phím che ô soạn hoặc bong bóng cuối.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
