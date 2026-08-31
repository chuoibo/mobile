#!/usr/bin/env python3
"""Đo cả sáu ô của bảng "phán quyết hero-walk có buộc vào cây không" (#439).

## Vì sao có file này

`scripts/hero_walk.sh --status` từ chối một phán quyết không thuộc về cây đang
đứng. #439 thêm trường `tree` để đóng đúng cái lỗ đó, và lời văn của chính nó
nói ra điều nó chặn:

    "a walk driven by uncommitted edits recorded the untouched sha underneath
     them, so it vouched for code it never ran"

Bộ ca `tests/test_hero_walk_binds_to_the_tree_it_walked.py` có 11 ca và phủ
được năm trong sáu ô. Ô còn thiếu là ô hay xảy ra nhất:

    phán quyết ghi `tree: "clean"`, còn cây BÂY GIỜ đã có sửa chưa commit.

Trong `hero_walk.sh`, phép so `tree != now` nằm BÊN TRONG nhánh
`if tree != "clean":`. Nên một phán quyết ghi "clean" không bao giờ được đem so
với cây hiện tại — nó được nhận vô điều kiện. Đi bộ trên main sạch rồi bắt đầu
sửa là trạng thái làm việc bình thường của mọi lane, và từ lúc đó mọi
`make gate` đều nói ĐI ĐƯỢC về một cây chưa ai đi bộ.

Chiều ngược lại (`dirty` -> `dirty` khác) thì chặn đúng. Đây là bất đối xứng,
không phải cổng chết.

## Nó đo bằng cách nào

Dựng một repo git rời trong thư mục tạm, chép `scripts/hero_walk.sh` thật vào,
rồi gọi chính nó — không viết lại logic nào của nó. Vân tay cây cũng hỏi chính
bộ chạy (`--van-tay`) thay vì tự băm lại, vì một bản sao của phép băm chỉ chấm
điểm bản sao đó.

Chạy:
    python3 tests/qa/qa2-073146-muoi-cong/probe_hero_walk_cay_sach.py

Mã thoát: 0 nếu cả sáu ô ra đúng như MONG ĐỢI dưới đây, 1 nếu có ô lệch.
Lúc viết (main 2f8a301) ô `sach_nhung_cay_ban` ra 0 trong khi mong đợi 2.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
URL = "http://127.0.0.1:8099"

# Ô -> mã thoát đúng. `sach_nhung_cay_ban` là ô #439 nói nó chặn.
MONG_DOI = {
    "sach_va_cay_sach": 0,
    "sach_nhung_cay_ban": 2,
    "ban_va_van_tay_khop": 0,
    "ban_nhung_van_tay_da_doi": 2,
    "thieu_truong_tree": 2,
    "tree_la_dau_hoi": 2,
}


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )
    return done.stdout.strip()


def dung_cay(goc: Path) -> Path:
    """Một checkout git nhỏ có `scripts/hero_walk.sh` thật bên trong."""
    repo = goc / "cay"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "scripts" / "hero_walk.sh", repo / "scripts")
    (repo / "doc.txt").write_text("noi dung ban dau\n", encoding="utf-8")
    git(repo, "init", "-q")
    # No dot after `@`: repo guard's email rule fires on a real-looking address,
    # and a throwaway git identity is not worth an allowlist entry.
    git(repo, "config", "user.email", "probe@invalid")
    git(repo, "config", "user.name", "probe")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "khoi tao")
    return repo


def van_tay(repo: Path, thu_muc: Path) -> str:
    """Hỏi chính bộ chạy vân tay của cây, không tự băm lại."""
    done = subprocess.run(
        ["bash", str(repo / "scripts" / "hero_walk.sh"), "--van-tay"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(thu_muc)},
    )
    return done.stdout.strip()


def ghi_phan_quyet(repo: Path, thu_muc: Path, **truong) -> None:
    """Một phán quyết XANH hợp lệ, rồi đè lên đúng trường ô này đang đổi."""
    phan_quyet = {
        "ts": time.time(),
        "rc": 0,
        "url": URL,
        "sha": git(repo, "rev-parse", "--short", "HEAD"),
        "tree": "clean",
        "worktree": str(repo),
        "routes": "77",
        "anh": "/tmp/ro.jpg",
        "so_chang": "16/16",
        "so_mon": 5,
        "buoc_hong": None,
    }
    for ten, gia_tri in truong.items():
        if gia_tri is ...:
            phan_quyet.pop(ten, None)
        else:
            phan_quyet[ten] = gia_tri
    thu_muc.mkdir(parents=True, exist_ok=True)
    (thu_muc / "verdict.json").write_text(
        json.dumps(phan_quyet, ensure_ascii=False), encoding="utf-8"
    )


def chay_status(repo: Path, thu_muc: Path) -> tuple[int, str]:
    done = subprocess.run(
        ["bash", str(repo / "scripts" / "hero_walk.sh"), "--status"],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(thu_muc),
            "MOBILE_HERO_WALK_DIR": str(thu_muc),
        },
    )
    return done.returncode, (done.stdout + done.stderr).strip()


def lam_ban(repo: Path) -> None:
    (repo / "doc.txt").write_text("noi dung DA SUA\n", encoding="utf-8")


def do_mot_o(ten: str) -> tuple[int, str]:
    """Dựng một cây mới cho mỗi ô — dùng lại cây là cách hai ô nhiễm nhau."""
    with tempfile.TemporaryDirectory() as tam:
        goc = Path(tam)
        thu_muc = goc / "phan-quyet"
        repo = dung_cay(goc)

        if ten == "sach_va_cay_sach":
            ghi_phan_quyet(repo, thu_muc)
        elif ten == "sach_nhung_cay_ban":
            ghi_phan_quyet(repo, thu_muc)
            lam_ban(repo)
        elif ten == "ban_va_van_tay_khop":
            lam_ban(repo)
            ghi_phan_quyet(repo, thu_muc, tree=van_tay(repo, thu_muc))
        elif ten == "ban_nhung_van_tay_da_doi":
            lam_ban(repo)
            ghi_phan_quyet(repo, thu_muc, tree="dirty:deadbeefdeadbeef")
        elif ten == "thieu_truong_tree":
            ghi_phan_quyet(repo, thu_muc, tree=...)
        elif ten == "tree_la_dau_hoi":
            ghi_phan_quyet(repo, thu_muc, tree="?")
        else:  # pragma: no cover - lỗi lập trình, không phải kết quả đo
            raise AssertionError(f"ô lạ: {ten}")

        return chay_status(repo, thu_muc)


def main() -> int:
    print(f"Đối chiếu `hero_walk.sh --status` — cây thật ở {REPO_ROOT}")
    print(f"{'ô':<28} {'mong đợi':>9} {'đo được':>8}  phán quyết")
    lech = []
    for ten, muon in MONG_DOI.items():
        thuc, loi = do_mot_o(ten)
        dau = "ĐÚNG" if thuc == muon else "LỆCH"
        if thuc != muon:
            lech.append((ten, muon, thuc, loi.splitlines()[0] if loi else ""))
        print(f"{ten:<28} {muon:>9} {thuc:>8}  {dau}")

    print()
    if not lech:
        print("Cả sáu ô đúng — phán quyết buộc được vào cây ở mọi chiều.")
        return 0

    print(f"{len(lech)} ô LỆCH:")
    for ten, muon, thuc, dong in lech:
        print(f"  {ten}: mong đợi thoát {muon}, đo được {thuc}")
        if dong:
            print(f"      cổng nói: {dong}")
    print()
    print("Ô `sach_nhung_cay_ban` lệch nghĩa là: đi bộ trên cây sạch, rồi sửa gì")
    print("cũng được, và cổng vẫn bảo lãnh cho cây đã sửa. Trong hero_walk.sh,")
    print('phép so `tree != now` nằm bên trong nhánh `if tree != "clean":`,')
    print("nên nhánh 'clean' không bao giờ hỏi lại cây hiện tại.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
