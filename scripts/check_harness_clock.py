#!/usr/bin/env python3
"""Does the harness that RUNS measure intervals with a wall clock?

`tests/test_khong_do_khoang_bang_dong_ho_treo_tuong.py` states the rule and
then says, in its own list of what it does not cover:

    It is scoped to THIS repository, and the third occurrence was not in it.
    `lane.py` lives in `~/agent-harness/`, which has no remote and whose
    working tree is production; nothing here can scan it. [...] no gate in
    this repo runs on every change to the harness, and that gap is real.

`scripts/check_harness_deploy_drift.py` names the same hole from the other
side: it compares bytes for the two files that have a counterpart in
`scripts/`, and says nothing at all about the nine harness files that have
none.

This checker measures whether that hole is empty. It was not.

## The measurement that produced this file

Run 2026-08-31 against the installed harness at `~/agent-harness`, using the
detector from the module above, unmodified:

    agent_supervisor.py:209             run_once, `int(time.time() - started)`
    tests/test_phat_hien_hong.py:104    assertLess(time.time() - started, 30)
    tests/test_phat_hien_hong.py:368    took = time.time() - started

    3 findings over 17 files

The first one is the same defect #477 fixed and merged. `main` has carried the
fix since 2026-08-31; the installed copy is byte-identical to `0389c58`, three
commits older, and has never contained it. Two reviews and a merge produced a
patch that is not running. The other two silence the assertions that measure
how FAST the harness notices a hung lane -- a backward clock step makes
`time.time() - started` negative, `assertLess(negative, 30)` passes
unconditionally, and a detector that got slower cannot be seen getting slower.

## Why this is a gate stage and not a test under `tests/`

It was a test under `tests/` first, and that was wrong. Its verdict is a
function of `~/agent-harness`, a directory outside this repository, with no
remote, whose working tree is production and which other lanes write to while
a gate is running. QA measured the consequence on 2026-08-31 (#487 verdict):

    same SHA 7ed5984, same machine, same command, 13 minutes apart
    -> `1 failed`  then  `0 failed`

`python3 -m pytest services/api/tests tests -q` is the command every lane runs
and the Lead reads to decide a merge, so it has to be a function of what is in
the repository and nothing else. It was not, and the red it produced pointed at
whichever PR happened to be running -- a red at the wrong address is worse than
no red, because somebody spends a turn on it.

So the measurement lives here, behind `gate.sh harness-clock`, next to
`harness-deploy` and `harness-selfcheck`, which ask their own machine-local
questions and are already labelled `(máy này thôi)`.

## Why this scans the harness's `tests/` too

The in-repo scan deliberately skips `tests/`, because tests legitimately
fabricate wall-clock stamps for fixtures and flagging those trains people to
add ignores. That argument does not transfer here, and the detector is the
reason: it only fires when BOTH ends of the subtraction were produced in the
same scope, so `ts = time.time() - 3600` is not flagged and is pinned as such
in the detector's own `PHAI_THA`. What is left in a test file is a real
elapsed-time assertion, and those are exactly the two found above.

## What this does not prove

It reads source shape, not behaviour, so it proves nobody TYPED the pattern.
It says nothing about the harness files it cannot see: anything under a
gitignored directory, and any second install somewhere other than the path
`agy_test_pr.sh` resolves. And it is one machine's answer -- the harness has no
remote, so there is no ref to check this against and no CI that could.

Exit codes: 0 clean, 2 for findings AND for every question it cannot answer.
"Cannot answer" is never a 0 here; a checker that exits 0 when it failed to
look is the failure this whole family of gates exists to refuse.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The detector lives in the module that states the rule, and is loaded rather
# than re-implemented. A second copy of the matching logic would only ever
# prove that the copy agrees with itself, which is the failure this repository
# has already paid for once. The direction is unusual -- a script reaching into
# `tests/` -- and it is still the cheaper of the two mistakes available.
MAY_DO_PATH = REPO_ROOT / "tests" / "test_khong_do_khoang_bang_dong_ho_treo_tuong.py"

# Floor on the denominator. The scan is a loop, and a loop over an empty list
# is green without measuring anything -- the same green a clean tree produces.
# The installed harness had 17 Python files when this was written; ten is well
# under that and still far from zero, so a genuine reorganisation does not trip
# it but an unhooked scan does.
MIN_FILES = 10


class KhongTraLoiDuoc(Exception):
    """The question could not be answered, and must not be read as 'fine'."""


def nap_may_do():
    """Import the detector by path, and say plainly when that fails."""
    if not MAY_DO_PATH.exists():
        raise KhongTraLoiDuoc(f"không thấy máy dò tại {MAY_DO_PATH}")
    spec = importlib.util.spec_from_file_location("_may_do_dong_ho", MAY_DO_PATH)
    if spec is None or spec.loader is None:
        raise KhongTraLoiDuoc(f"không nạp được {MAY_DO_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    ham = getattr(module, "do_khoang_bang_dong_ho_treo_tuong", None)
    if ham is None:
        raise KhongTraLoiDuoc(
            f"{MAY_DO_PATH.name} không còn hàm do_khoang_bang_dong_ho_treo_tuong"
        )
    return ham


def goc_cai_dat(khai_bao: str | None = None) -> tuple[Path, bool]:
    """Where the launcher looks. Returns (path, whether it was named explicitly).

    `agy_test_pr.sh` resolves the supervisor as
    `${AGENT_HARNESS:-$HOME/agent-harness}/agent_supervisor.py`, and this reads
    the same variable so that the two cannot point at different trees.

    The second element separates two situations a single "does it exist" check
    would flatten: a machine that simply has no harness installed, and a
    machine where somebody pointed `AGENT_HARNESS` at a path that is not there.
    Both are refused here, but only the second is somebody aiming the gate at
    nothing, so it gets its own message.
    """
    named = khai_bao if khai_bao is not None else os.environ.get("AGENT_HARNESS")
    if named:
        return Path(named).expanduser(), True
    return Path.home() / "agent-harness", False


def file_python(goc: Path) -> list[str]:
    """Harness `.py` paths, asked of git: tracked plus untracked-not-ignored.

    Tracked alone is wrong here in a way it is not wrong in a normal repo. This
    tree has no remote and is production, so a file that has been written but
    not yet `git add`ed is nonetheless RUNNING, and `ls-files` without
    `--others` is blind to it until somebody stages it.

    `--exclude-standard` is what keeps the scan off `wt/` -- the harness's
    `.gitignore` excludes it, and it holds this repository's own worktrees.
    Walking the filesystem instead would pull those in and report findings from
    the very tree doing the scanning.
    """
    try:
        ra = subprocess.run(
            [
                "git",
                "-C",
                str(goc),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                "*.py",
            ],
            capture_output=True,
            text=True,
        )
    except OSError as loi:  # pragma: no cover - git missing is not this gate's bug
        raise KhongTraLoiDuoc(f"không chạy được git: {loi}") from loi
    if ra.returncode != 0:
        # No fallback to rglob on purpose. A fallback would sweep gitignored
        # runtime directories and this repo's worktrees under `wt/`, and would
        # report findings that belong to somebody else's tree. "Cannot answer"
        # is a red with a reason, never a green.
        raise KhongTraLoiDuoc(
            f"{goc} không trả lời được git ls-files (rc={ra.returncode}): "
            f"{ra.stderr.strip()!r} — không suy ra danh sách file bằng cách khác, "
            "vì cách khác sẽ quét cả cây worktree nằm trong đó"
        )
    return sorted(d for d in ra.stdout.split() if d.strip())


def quet(goc: Path) -> tuple[list[str], list[str]]:
    """Return (findings, files scanned). Raises KhongTraLoiDuoc rather than guessing."""
    ham = nap_may_do()
    files = file_python(goc)
    if len(files) < MIN_FILES:
        raise KhongTraLoiDuoc(
            f"chỉ thấy {len(files)} file .py dưới {goc} (sàn {MIN_FILES}) — lượt "
            "quét này đang tự tháo chính nó; danh sách rỗng đọc y hệt cây sạch"
        )
    loi: list[str] = []
    for rel in files:
        duong = goc / rel
        try:
            nguon = duong.read_text(encoding="utf-8")
        except OSError as e:
            raise KhongTraLoiDuoc(f"không đọc được {duong}: {e}") from e
        loi += ham(nguon, rel)
    return loi, files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--harness",
        default=None,
        help="gốc bản harness cần quét (mặc định: $AGENT_HARNESS, rồi ~/agent-harness)",
    )
    args = parser.parse_args(argv)

    goc, khai_bao = goc_cai_dat(args.harness)
    if not goc.is_dir():
        if khai_bao:
            print(
                f"KHÔNG TRẢ LỜI ĐƯỢC: chỉ vào {goc}, chỗ đó không có — cổng này "
                "không được xanh chỉ vì bị chỉ vào hư không",
                file=sys.stderr,
            )
        else:
            print(
                f"KHÔNG TRẢ LỜI ĐƯỢC: máy này không cài harness tại {goc}; không "
                "có bản đang chạy để đo",
                file=sys.stderr,
            )
        return 2

    try:
        loi, files = quet(goc)
    except KhongTraLoiDuoc as e:
        print(f"KHÔNG TRẢ LỜI ĐƯỢC: {e}", file=sys.stderr)
        return 2

    if loi:
        print(
            f"bản harness ĐANG CHẠY tại {goc} đo khoảng bằng đồng hồ treo tường "
            f"({len(loi)} chỗ trên {len(files)} file):",
            file=sys.stderr,
        )
        for d in loi:
            print(f"  {d}", file=sys.stderr)
        print(
            "\nĐây là bản được thi hành, không phải bản đã merge. Sửa tại chỗ đó; "
            "với file có bản gốc trong scripts/, "
            "scripts/check_harness_deploy_drift.py nói bản đang chạy thiếu commit nào.",
            file=sys.stderr,
        )
        return 2

    # The denominator is printed on the green line on purpose: "0 findings" and
    # "scanned nothing" are the same sentence otherwise.
    print(
        f"XANH — {len(files)} file .py dưới {goc}, không chỗ nào đo khoảng bằng time.time()"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
