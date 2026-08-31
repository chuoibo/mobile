"""Peel every command out of the page's own table and run it VERBATIM.

The page's law is "a row belongs in column 1 only if it carries a command
someone else can paste and re-run". A page can satisfy that law on the surface
-- every row HAS a backticked command -- and still fail it in fact, because the
command text drifted from the command that was actually run. Nobody notices,
because reading a command is not running one.

So this does not check "is there a command". It pastes each one and demands an
exit code.

Two kinds of row are NOT failures and are named here rather than quietly
tolerated, because a harness that silently forgives is the thing it is meant to
replace:

  * BO_QUA -- the page itself states out loud the row was not re-run this turn.
  * MONG_DOI -- the measured result IS a non-zero exit (`make hero-walk-status`
    refusing a stale verdict; `grep -c` printing 0). Scoring those as red would
    make the harness demand the opposite of what the row proves.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TRANG = REPO / "docs/claude/2026-08-31/qa3-093210-da-do-duoc-gi-va-chua-do-duoc-gi.md"

BO_QUA = {"11": "make e2e dựng cả stack — trang đã tự khai KHÔNG chạy lại lượt này"}

# row -> (expected exit code, why a non-zero code is the measurement itself)
MONG_DOI = {
    "16": (2, "cổng TỪ CHỐI một phán quyết của cây khác — thoát 2 là kết quả"),
    "18": (1, "`grep -c` thoát 1 khi đếm ra 0, và 0 chính là con số hàng này khai"),
}


def khoi_lenh(o: str) -> list[str]:
    ra = []
    for m in re.finditer(r"`([^`]+)`", o):
        s = m.group(1).strip().replace("\\|", "|")
        if s.startswith(("python3", "cd ", "make ", "grep", "find", "node", "MOBILE_")):
            ra.append(s)
    return ra


def o_cua_hang(dong: str) -> list[str]:
    # Split on pipes that are NOT escaped: a `\|` inside a cell is one pipe
    # character of the command, not a column boundary. Splitting naively cut a
    # `find ... | wc -l` in half and reported the page as broken when the page
    # was fine -- a harness bug that reads exactly like a real finding.
    return [c.strip() for c in re.split(r"(?<!\\)\|", dong.strip().strip("|"))]


def main() -> int:
    dong = [
        d
        for d in TRANG.read_text(encoding="utf-8").splitlines()
        if re.match(r"^\|\s*\d+\s*\|", d)
    ]
    print(f"Bảng CỘT 1A có {len(dong)} hàng\n")

    hong = []
    for d in dong:
        o = o_cua_hang(d)
        so, lenh_o = o[0], o[2]
        if so in BO_QUA:
            print(f"[hàng {so:>2}] BỎ QUA — {BO_QUA[so]}")
            continue
        lenhs = khoi_lenh(lenh_o)
        if not lenhs:
            print(
                f"[hàng {so:>2}] KHÔNG CÓ LỆNH NÀO bóc ra được  <== vi phạm luật trang"
            )
            hong.append((so, "không có lệnh"))
            continue
        mong, vi_sao = MONG_DOI.get(so, (0, ""))
        for lenh in lenhs:
            done = subprocess.run(
                ["bash", "-c", lenh],
                cwd=REPO,
                capture_output=True,
                text=True,
                timeout=900,
            )
            rc = done.returncode
            dat = rc == mong
            dau = "OK " if dat else "ĐỎ"
            ghi = f"  (mong {mong}: {vi_sao})" if vi_sao else ""
            print(f"[hàng {so:>2}] {dau} rc={rc}  $ {lenh[:80]}{ghi}")
            if not dat:
                cuoi = (done.stdout + done.stderr).strip().splitlines()[-1:] or [""]
                print(f"           {cuoi[0][:120]}")
                hong.append((so, lenh))

    print()
    if hong:
        print(f"{len(hong)} lệnh KHÔNG chạy nguyên văn được:")
        for so, lenh_hong in hong:
            print(f"  hàng {so}: {lenh_hong[:100]}")
        return 1
    print(
        f"Mọi lệnh trong bảng chạy nguyên văn được ({len(dong) - len(BO_QUA)}/{len(dong)} hàng)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
