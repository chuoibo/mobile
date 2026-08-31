"""`scripts/check_harness_clock.py` -- and every case here is repo-pure.

This file replaces `tests/test_harness_deploy_dong_ho.py`, which asked the same
question by scanning `~/agent-harness` directly from inside the blocking suite.
That was the defect QA blocked #487 on, and it is worth stating precisely
because the fix is only correct if it does not come back:

    `python3 -m pytest services/api/tests tests -q` is the command every lane
    runs and the Lead reads to decide a merge. Its verdict has to be a function
    of what is in the repository at that SHA. The old file made it a function
    of a directory outside the repository, with no remote, whose working tree
    is production and which other lanes write to WHILE a gate is running.

    Measured, same SHA `7ed5984`, same machine, 13 minutes apart:
    `1 failed` then `0 failed`. Reproduced deterministically here before the
    fix by pointing `AGENT_HARNESS` at two copies differing by one function:
    `3 passed` against the clean copy, `1 failed` against the dirty one.

So the scan moved to `gate.sh harness-clock`, and what stays in the blocking
suite is this: cases that build their own harness under `tmp_path`. Every one
of them would give the same answer on a machine that has never heard of
`~/agent-harness`, which is the property the old file lacked.

The positive controls matter more than the greens. `check_harness_clock.py`
prints "no findings" both when the harness is clean and when the detector never
ran, so `test_bat_duoc_dang_da_tim_thay_tren_cay_that` -- feeding it the exact
shape found at `agent_supervisor.py:209` -- is the case that tells those apart.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER = REPO_ROOT / "scripts" / "check_harness_clock.py"

# The exact shape found at `agent_supervisor.py:209` on the running harness.
# Kept verbatim rather than paraphrased: a paraphrase that stops matching would
# turn this positive control green while the real defect walks past.
CANARY_HONG = """
import time


def run_once(agent):
    started = time.time()
    code = go(agent)
    emit("INFO", f"{agent} ket thuc sau {int(time.time() - started)}s")
    return code
"""

# The shape the detector must NOT flag: one end of the subtraction comes from
# outside the scope, so it is a fabricated stamp, not an elapsed-time measure.
# Pinned here as well as in the detector because this checker scans the
# harness's own `tests/`, where fixtures do exactly this.
CANARY_SACH = """
import time


def fixture_cu():
    ts = time.time() - 3600
    return {"created_at": ts}
"""


def _dung_harness(goc: Path, so_file: int = 12, them: str = "") -> Path:
    """Build a git tree that looks enough like the harness to be scanned."""
    goc.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(goc), "init", "-q"], check=True)
    for i in range(so_file):
        (goc / f"m{i}.py").write_text(
            f"def f{i}():\n    return {i}\n", encoding="utf-8"
        )
    if them:
        (goc / "agent_supervisor.py").write_text(them, encoding="utf-8")
    subprocess.run(["git", "-C", str(goc), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(goc),
            "-c",
            "user.email=x@y",
            "-c",
            "user.name=x",
            "commit",
            "-qm",
            "base",
        ],
        check=True,
    )
    return goc


def _chay(
    goc: Path | str, env_harness: str | None = None
) -> subprocess.CompletedProcess:
    """Run the checker with `--harness`, never inheriting this machine's answer."""
    import os

    env = dict(os.environ)
    # Scrub the ambient variable so a developer with a harness installed and one
    # without get the same result from this file. Leaving it inherited is how a
    # "pure" test quietly stops being pure.
    env.pop("AGENT_HARNESS", None)
    if env_harness is not None:
        env["AGENT_HARNESS"] = env_harness
        argv = [sys.executable, str(CHECKER)]
    else:
        argv = [sys.executable, str(CHECKER), "--harness", str(goc)]
    return subprocess.run(argv, capture_output=True, text=True, env=env)


def test_bat_duoc_dang_da_tim_thay_tren_cay_that(tmp_path):
    """Positive control: the exact defect found on the running harness goes red.

    Without this case every green below is unreadable -- a checker that cannot
    fire and a harness that is clean print the same thing.
    """
    goc = _dung_harness(tmp_path / "ban", them=CANARY_HONG)
    ra = _chay(goc)
    assert ra.returncode == 2, (
        f"cổng KHÔNG đỏ trên chính hình dạng đã tìm thấy: {ra.stdout}{ra.stderr}"
    )
    assert "agent_supervisor.py" in ra.stderr, ra.stderr
    assert "run_once" in ra.stderr, ra.stderr


def test_cay_sach_thi_xanh_va_in_ra_mau_so(tmp_path):
    """A clean tree passes -- and says how many files it looked at.

    A gate that can only go red is a gate people delete. The denominator on the
    green line is what separates "scanned 12, found none" from "scanned none".
    """
    goc = _dung_harness(tmp_path / "sach")
    ra = _chay(goc)
    assert ra.returncode == 0, ra.stderr
    assert "XANH" in ra.stdout
    assert "12 file" in ra.stdout, ra.stdout


def test_dau_thoi_gian_bia_khong_bi_bao_nham(tmp_path):
    """`time.time() - 3600` is a fabricated stamp, not an elapsed-time measure.

    The harness's own `tests/` are in scope for this scan, and they do this
    legitimately. Flagging it is how a gate trains people to add ignores.
    """
    goc = _dung_harness(tmp_path / "fixture", them=CANARY_SACH)
    ra = _chay(goc)
    assert ra.returncode == 0, f"báo nhầm dấu thời gian bịa: {ra.stderr}"


def test_duoi_san_file_thi_do_chu_khong_xanh(tmp_path):
    """An empty or near-empty file list must not read as a clean harness."""
    goc = _dung_harness(tmp_path / "it", so_file=3)
    ra = _chay(goc)
    assert ra.returncode == 2, f"3 file mà vẫn xanh: {ra.stdout}"
    assert "sàn" in ra.stderr, ra.stderr


def test_chi_vao_hu_khong_thi_khong_duoc_xanh(tmp_path):
    """Aiming the gate at a path that does not exist is refused, not passed."""
    ra = _chay(tmp_path / "khong-he-co")
    assert ra.returncode == 2
    assert "không có" in ra.stderr or "hư không" in ra.stderr, ra.stderr


def test_khong_phai_git_repo_thi_tu_choi_chu_khong_di_bo_cay(tmp_path):
    """Refuse rather than fall back to walking the filesystem.

    A walk would sweep gitignored runtime directories and this repository's own
    worktrees under `wt/`, and report findings that belong to someone else's
    tree -- a red at the wrong address, which is the class this whole fix is
    about.
    """
    goc = tmp_path / "khong-git"
    goc.mkdir()
    for i in range(12):
        (goc / f"m{i}.py").write_text(CANARY_HONG, encoding="utf-8")
    ra = _chay(goc)
    assert ra.returncode == 2
    assert "ls-files" in ra.stderr, ra.stderr
    # The refusal must be about git, not a findings report produced by a walk.
    assert "run_once" not in ra.stderr, "đã đi bộ cây thay vì từ chối: " + ra.stderr


def test_file_bi_gitignore_khong_bi_quet(tmp_path):
    """`wt/` holds this repo's worktrees; a finding from there is not the harness."""
    goc = _dung_harness(tmp_path / "cogitignore")
    (goc / ".gitignore").write_text("wt/\n", encoding="utf-8")
    (goc / "wt").mkdir()
    (goc / "wt" / "cua_lane_khac.py").write_text(CANARY_HONG, encoding="utf-8")
    ra = _chay(goc)
    assert ra.returncode == 0, f"quét cả cây bị gitignore: {ra.stderr}"


def test_mat_may_do_thi_do_chu_khong_bao_khong_co_gi(tmp_path, monkeypatch):
    """Detector gone: refuse. Zero findings from a detector that never ran is a lie."""
    goc = _dung_harness(tmp_path / "sach2", them=CANARY_HONG)
    import importlib.util

    spec = importlib.util.spec_from_file_location("_ckhc", CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "MAY_DO_PATH", tmp_path / "khong-co-may-do.py")
    ma = mod.main(["--harness", str(goc)])
    assert ma == 2


def test_bien_moi_truong_tro_sai_cho_thi_noi_ro_la_bi_chi_vao_hu_khong(tmp_path):
    """`AGENT_HARNESS` is the path `gate.sh` and `agy_test_pr.sh` both resolve.

    Pointed at nothing it must refuse with the message that names the cause,
    not with the "this machine has no harness" one -- those are different
    accidents and only one of them is somebody's typo.
    """
    ra = _chay(tmp_path, env_harness=str(tmp_path / "khong-he-co"))
    assert ra.returncode == 2
    assert "hư không" in ra.stderr, ra.stderr


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
