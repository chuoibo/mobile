"""Is #441's hero-walk gate table still measuring anything?

#441 (qa2, measured at `2f8a301`) reported ten gates, eight biting, and one
hole: `hero_walk.sh --status` accepted a verdict recording `tree: "clean"` even
after the working tree had been edited. Its evidence is a six-cell table in
`tests/qa/qa2-073146-muoi-cong/probe_hero_walk_cay_sach.py`.

Running that probe verbatim today exits 1 with all six cells at 2. The table has
stopped discriminating -- and the four cells that still read "ĐÚNG" are right for
a different reason than the one they were written to measure. That is the worst
kind of green: a row that still runs, still prints a table, and no longer asks
its question.

The cause is not rot in the probe. `hero_walk.sh` gained a REQUIRED `ngoai_git`
field (#444 -> #449 -> #454), checked for EVERY verdict and checked BEFORE the
tree comparison. The probe writes verdicts in the older shape, so every cell
dies at the earlier gate.

This file does NOT fork qa2's probe -- a second copy of a money-adjacent gate is
how two tables start disagreeing. It overlays two edits at runtime and REFUSES
LOUDLY if either anchor is gone, so the day qa2 fixes their file properly, this
one stops with a message instead of quietly grading a stale copy.

Run from the repo root:

    python3 tests/qa/qa3-101734/probe_441_con_do_duoc_khong.py
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
GOC = REPO / "tests/qa/qa2-073146-muoi-cong/probe_hero_walk_cay_sach.py"

# The out-of-git fingerprint must come from the runner itself. Rebuilding the
# string here would grade a copy of `ngoai_git_van_tay` instead of the runner,
# which is the same mistake one axis over.
NEO_HELPER = "def ghi_phan_quyet(repo: Path, thu_muc: Path, **truong) -> None:"
HELPER = '''def ngoai_van_tay(repo: Path, thu_muc: Path) -> str:
    """Ask the runner for its own out-of-git fingerprint; never rebuild it."""
    done = subprocess.run(
        ["bash", str(repo / "scripts" / "hero_walk.sh"), "--ngoai-git"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(thu_muc)},
    )
    return done.stdout.strip()


'''

NEO_TRUONG = '        "tree": "clean",\n        "worktree": str(repo),'
TRUONG = NEO_TRUONG + '\n        "ngoai_git": ngoai_van_tay(repo, thu_muc),'

NEO_ROOT = "REPO_ROOT = Path(__file__).resolve().parents[3]"


def main() -> int:
    if not GOC.exists():
        print(
            f"probe gốc của #441 không còn ở {GOC.relative_to(REPO)} — không đo được."
        )
        return 2

    goc = GOC.read_text(encoding="utf-8")

    thieu = [
        ten
        for ten, neo in (
            ("điểm chèn helper", NEO_HELPER),
            ("trường tree/worktree", NEO_TRUONG),
            ("REPO_ROOT", NEO_ROOT),
        )
        if neo not in goc
    ]
    if thieu:
        print("probe gốc của #441 đã đổi hình dạng — KHÔNG áp bản phủ lên nữa.")
        for t in thieu:
            print(f"  không tìm thấy: {t}")
        print(
            "  'Không áp được' KHÔNG đọc thành 'đã sửa'. Đọc lại file gốc rồi cập nhật neo."
        )
        return 2

    if '"ngoai_git"' in goc:
        print("probe gốc ĐÃ tự ghi `ngoai_git` — bản phủ này hết việc, xoá được.")
        return 0

    va = goc.replace(NEO_HELPER, HELPER + NEO_HELPER, 1)
    va = va.replace(NEO_TRUONG, TRUONG, 1)
    va = va.replace(NEO_ROOT, f"REPO_ROOT = Path({str(REPO)!r})", 1)

    with tempfile.TemporaryDirectory(prefix="qa3-441-") as tmp:
        dich = Path(tmp) / "probe_va.py"
        dich.write_text(va, encoding="utf-8")
        shutil.copystat(GOC, dich)

        print("== NGUYÊN VĂN (bộ ca của #441 như nó nằm trong repo) ==")
        a = subprocess.run(
            [sys.executable, str(GOC)],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=300,
        )
        print(a.stdout.strip() or a.stderr.strip())
        print(f"-> exit {a.returncode}\n")

        print("== BẢN PHỦ (thêm đúng trường `ngoai_git` mà bộ chạy đòi từ #444) ==")
        b = subprocess.run(
            [sys.executable, str(dich)],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=300,
        )
        print(b.stdout.strip() or b.stderr.strip())
        print(f"-> exit {b.returncode}\n")

    print("=" * 78)
    if a.returncode != 0 and b.returncode == 0:
        print("KẾT: bảng của #441 KHÔNG còn đo được nguyên văn, và đo được khi thêm")
        print("  `ngoai_git`. Nên hai điều cùng đúng:")
        print("   - con số 8/10 của #441 là số thật của cây 2f8a301, và nó ĐÃ CŨ;")
        print("   - lỗ #439 mà nó tố cáo (ô sach_nhung_cay_ban) nay ĐÃ ĐÓNG.")
        print("  Việc còn lại thuộc qa2: ghi `ngoai_git` vào chính probe trong repo.")
        return 0
    if a.returncode == 0 and b.returncode == 0:
        print("KẾT: bộ ca gốc đã chạy lại được — ai đó đã vá. Bản phủ này hết việc.")
        return 0
    print("KẾT: KHÔNG kết luận được — bản phủ cũng đỏ. Đọc hai đầu ra ở trên,")
    print("  đừng đọc con số nào từ trang bản đồ cho tới khi hiểu vì sao.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
