"""The clock rule must also be read against the harness that is RUNNING.

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

This file measures whether that hole is empty. It was not.

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
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The detector lives in the module that states the rule, and is loaded rather
# than re-implemented. A second copy of the matching logic would only ever
# prove that the copy agrees with itself, which is the failure this repository
# has already paid for once.
MAY_DO_PATH = REPO_ROOT / "tests" / "test_khong_do_khoang_bang_dong_ho_treo_tuong.py"

# Floor on the denominator. Every assertion below is over a loop, and a loop
# over an empty list is green without measuring anything -- the same green a
# clean tree produces. The installed harness had 17 Python files when this was
# written; ten is well under that and still far from zero, so a genuine
# reorganisation does not trip it but an unhooked scan does.
MIN_FILES = 10

# The exact shape found at `agent_supervisor.py:209`, kept here as a positive
# control. If the detector cannot be loaded, or is loaded but does not fire,
# the real scan below returns zero findings and reads as a clean harness. This
# case makes that failure loud instead.
CANARY_HONG = """
import time
def run_once(agent):
    started = time.time()
    code = go(agent)
    emit("INFO", f"{agent} ket thuc sau {int(time.time() - started)}s")
    return code
"""


class KhongTraLoiDuoc(Exception):
    """The question could not be answered, and must not be read as 'fine'."""


def _nap_may_do():
    """Import the detector by path, and say plainly when that fails.

    By path rather than by module name because a bare `import` here depends on
    how pytest was invoked -- running this one file directly puts a different
    directory on `sys.path` than running the suite from the repo root does, and
    a gate that only works under one invocation is a gate people learn to skip.
    """
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


def _goc_cai_dat() -> tuple[Path, bool]:
    """Where the launcher looks. Returns (path, whether it was named explicitly).

    `agy_test_pr.sh` resolves the supervisor as
    `${AGENT_HARNESS:-$HOME/agent-harness}/agent_supervisor.py`, and this reads
    the same variable so that the two cannot point at different trees.

    The second element separates two situations a single "does it exist" check
    would flatten: a machine that simply has no harness installed, and a
    machine where somebody pointed `AGENT_HARNESS` at a path that is not there.
    The first is an honest skip; the second is a way to make this gate green by
    aiming it at nothing, so it is refused instead.
    """
    khai_bao = os.environ.get("AGENT_HARNESS")
    if khai_bao:
        return Path(khai_bao).expanduser(), True
    return Path.home() / "agent-harness", False


def _file_python(goc: Path) -> list[str]:
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


def _phai_co_goc() -> Path:
    goc, khai_bao = _goc_cai_dat()
    if not goc.is_dir():
        if khai_bao:
            raise KhongTraLoiDuoc(
                f"AGENT_HARNESS trỏ vào {goc}, chỗ đó không có — cổng này không "
                "được xanh chỉ vì bị chỉ vào hư không"
            )
        pytest.skip(
            f"máy này không cài harness tại {goc}; không có bản đang chạy để đo. "
            "Đây là BỎ QUA, không phải ĐẠT."
        )
    return goc


def test_may_do_that_su_bat_duoc_dang_da_tim_thay():
    """Positive control, and it does not skip when the harness is absent.

    Everything else here reports "no findings" both when the harness is clean
    and when the detector never ran. This case is the only thing that tells
    those two apart, so it is deliberately independent of the install.
    """
    ham = _nap_may_do()
    loi = ham(CANARY_HONG, "canary")
    assert loi, (
        "máy dò KHÔNG bắt được chính hình dạng đã tìm thấy ở "
        "agent_supervisor.py:209 — nên số 0 của lượt quét thật dưới đây không "
        "có nghĩa gì cả"
    )


def test_co_file_de_quet():
    """Guard the denominator before trusting any green below it."""
    goc = _phai_co_goc()
    files = _file_python(goc)
    assert len(files) >= MIN_FILES, (
        f"chỉ thấy {len(files)} file .py dưới {goc} (sàn {MIN_FILES}) — lượt "
        "quét này đang tự tháo chính nó; danh sách rỗng đọc y hệt cây sạch"
    )


def test_harness_dang_chay_khong_do_khoang_bang_dong_ho_treo_tuong():
    """The real scan, against the copy that actually runs."""
    goc = _phai_co_goc()
    ham = _nap_may_do()
    files = _file_python(goc)
    assert len(files) >= MIN_FILES, f"danh sách file rỗng bất thường: {files}"

    loi: list[str] = []
    for rel in files:
        duong = goc / rel
        try:
            nguon = duong.read_text(encoding="utf-8")
        except OSError as e:  # pragma: no cover
            raise KhongTraLoiDuoc(f"không đọc được {duong}: {e}") from e
        loi += ham(nguon, rel)

    assert not loi, (
        f"bản harness ĐANG CHẠY tại {goc} đo khoảng bằng đồng hồ treo tường "
        f"({len(loi)} chỗ trên {len(files)} file):\n"
        + "\n".join(loi)
        + "\n\nĐây là bản được thi hành, không phải bản đã merge. Sửa tại chỗ "
        "đó; với file có bản gốc trong scripts/, "
        "scripts/check_harness_deploy_drift.py nói bản đang chạy thiếu commit nào."
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
