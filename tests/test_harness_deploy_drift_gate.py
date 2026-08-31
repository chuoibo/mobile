"""The gate that asks whether the merged harness is the running harness.

`scripts/agent_supervisor.py` is executed from `~/agent-harness/`, never from
this tree, because switching branches deletes it from disk. The install step is
a person running `git show <ref>:scripts/... > ~/agent-harness/...`, and until
`scripts/check_harness_deploy_drift.py` nothing checked that they had.

Measured on 2026-08-31 against origin/main at b20cc4a: the installed supervisor
was **3 commits behind**, and the three it lacked included both #470 and #477 --
the two clock fixes. Reviewed, merged, and not running. #470 had been merged for
three days.

## What each case here is for

The cases split into two lists, and the split is the point. A detector is only
worth its exit code if it goes red on the thing it claims to catch AND stays
quiet on the neighbouring thing that merely looks like it. Both halves are
written out, because a gate with only the first half gets tuned into noise and
switched off, and a gate with only the second half is decoration.

PHAI BAT -- stale copy, hand-edited copy, absent copy, undeclared pair, an
emptied manifest, a manifest describing files the repo does not have.

PHAI THA -- byte-identical copy, a harness-only file with no counterpart in
`scripts/` at all, and a machine with nothing installed.

## The direction cases are the ones that matter

BEHIND and DIVERGED are both "the bytes differ" and they want opposite actions.
BEHIND means redeploy is free. DIVERGED means the live file holds the only copy
of somebody's edit and overwriting it destroys work -- a real risk in a harness
whose working tree IS production. `test_sua_tay_bao_DIVERGED...` pins that the
remediation text for a hand-edited file never tells anyone to overwrite it.

`test_clone_nong_bao_UNKNOWN...` covers the way this classification fails on
somebody else's machine. The BEHIND/DIVERGED split is decided by walking a
file's history; a shallow clone has no history to walk, so the honest answer is
UNKNOWN. Answering DIVERGED there would tell a person with no local edits that
they have unsaved work, which is the false alarm that gets a gate disabled.

## The real-artifact case asserts SHAPE, not today's answer

`test_quet_that_...` runs the checker against this machine's actual install. It
deliberately does not assert "agent_supervisor.py is BEHIND", because that
assertion goes green today and red the moment somebody fixes the drift -- a test
that breaks when the bug is fixed is a test that will be deleted. It asserts
that a real scan reaches a definite classification for every declared pair, so
the fixtures above are not the only thing this gate has ever run on.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CHECKER = REPO / "scripts" / "check_harness_deploy_drift.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("check_harness_deploy_drift", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def checker():
    return load_checker()


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
    )
    return proc.stdout


def build_repo(root: Path) -> Path:
    """A real git repo with three revisions of the supervisor.

    Real, not mocked: the BEHIND/DIVERGED split is decided by walking history,
    so a fake history would test the fake and not the walk.
    """
    repo = root / "repo"
    (repo / "scripts").mkdir(parents=True)
    git(root, "init", "--quiet", str(repo))
    git(repo, "config", "user.email", "gate@test")
    git(repo, "config", "user.name", "gate")

    (repo / "scripts" / "agent_checkpoint.py").write_text("checkpoint v1\n")

    for version in ("v1", "v2", "v3"):
        (repo / "scripts" / "agent_supervisor.py").write_text(f"supervisor {version}\n")
        git(repo, "add", "-A")
        git(repo, "commit", "--quiet", "-m", f"supervisor {version}")

    # Stand in for origin/main without needing a second repository on disk.
    git(repo, "branch", "-f", "pretend-main", "HEAD")
    return repo


def install(harness: Path, name: str, content: str) -> None:
    harness.mkdir(parents=True, exist_ok=True)
    (harness / name).write_text(content)


def run(checker, repo: Path, harness: Path, *extra: str) -> tuple[int, dict]:
    """Invoke the checker in JSON mode and return (exit_code, report)."""
    argv = [
        "--repo",
        str(repo),
        "--harness-root",
        str(harness),
        "--ref",
        "pretend-main",
        "--no-fetch",
        "--json",
        *extra,
    ]
    import io
    from contextlib import redirect_stdout

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = checker.main(argv)
    text = buffer.getvalue().strip()
    return code, (json.loads(text) if text else {})


def state_of(report: dict, name: str) -> str:
    for pair in report["pairs"]:
        if pair["name"] == name:
            return pair["state"]
    return "ABSENT_FROM_REPORT"


def full_install(repo: Path, harness: Path, ref: str = "pretend-main") -> None:
    """Install both declared pairs at their current ref content."""
    for name in ("agent_supervisor.py", "agent_checkpoint.py"):
        content = git(repo, "show", f"{ref}:scripts/{name}")
        install(harness, name, content)


# --------------------------------------------------------------------------
# PHAI BAT
# --------------------------------------------------------------------------


def test_ban_cu_bao_BEHIND_va_ke_ten_dung_so_commit_thieu(checker, tmp_path):
    """A stale copy is BEHIND, and the report names what it is missing.

    "They differ" is not actionable. The count and the commit subjects are what
    turn the report into a decision, and they are what showed that the live
    supervisor was missing both clock fixes rather than one cosmetic edit.
    """
    repo = build_repo(tmp_path)
    harness = tmp_path / "harness"
    full_install(repo, harness)
    install(harness, "agent_supervisor.py", "supervisor v1\n")

    code, report = run(checker, repo, harness)

    assert code == 2
    assert state_of(report, "agent_supervisor.py") == "BEHIND"
    pair = report["pairs"][0]
    assert pair["behind"] == 2, "v1 is two content changes behind v3"
    subjects = [s["subject"] for s in pair["skipped"]]
    assert subjects == ["supervisor v3", "supervisor v2"], subjects


def test_sua_tay_bao_DIVERGED_va_KHONG_bao_ai_ghi_de(checker, tmp_path):
    """A hand-edited live file must never be reported as merely stale.

    This is the case where a wrong answer costs work rather than time: the
    harness tree is production, so the live file can be the only copy of an
    edit. The remediation text is asserted, not just the label -- a correct
    label under an "overwrite it" instruction still loses the file.
    """
    repo = build_repo(tmp_path)
    harness = tmp_path / "harness"
    full_install(repo, harness)
    install(harness, "agent_supervisor.py", "supervisor v3 + sua tay tren may that\n")

    code, report = run(checker, repo, harness)

    assert code == 2
    assert state_of(report, "agent_supervisor.py") == "DIVERGED"

    text = checker.render(report)
    assert "DUNG ghi de" in text
    overwrite_lines = [
        line
        for line in text.splitlines()
        if "agent_supervisor.py" in line and ">" in line and "git show" in line
    ]
    assert not overwrite_lines, f"DIVERGED khong duoc goi y ghi de: {overwrite_lines}"


def test_khong_cai_dat_gi_bao_MISSING(checker, tmp_path):
    """A declared pair with nothing installed is red, not absent from the report.

    Dropping it from the report instead would shrink the denominator: the gate
    would pass because it stopped asking, which is the failure mode the floors
    below exist for.
    """
    repo = build_repo(tmp_path)
    harness = tmp_path / "harness"
    full_install(repo, harness)
    (harness / "agent_supervisor.py").unlink()

    code, report = run(checker, repo, harness)

    assert code == 2
    assert state_of(report, "agent_supervisor.py") == "MISSING"


def test_cap_moi_khong_ai_khai_bao_UNMANAGED(checker, tmp_path):
    """A new repo/install pair nobody declared must not stay unmeasured.

    This is the half of the manifest that notices growth. Without it, a third
    script installed tomorrow is silently outside the gate forever, and the
    gate reports green while measuring two thirds of the problem.
    """
    repo = build_repo(tmp_path)
    harness = tmp_path / "harness"
    full_install(repo, harness)

    (repo / "scripts" / "agent_newthing.py").write_text("newthing v1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "--quiet", "-m", "newthing")
    git(repo, "branch", "-f", "pretend-main", "HEAD")
    install(harness, "agent_newthing.py", "newthing v1\n")

    code, report = run(checker, repo, harness)

    assert code == 2
    assert state_of(report, "agent_newthing.py") == "UNMANAGED"


def test_manifest_rong_thi_TU_CHOI_chu_khong_xanh(checker, tmp_path, monkeypatch):
    """An emptied manifest must refuse, not pass.

    Every loop in the scan iterates over DECLARED_PAIRS. Empty it and the whole
    gate passes having measured nothing, wearing the same green as a clean
    machine. That is the exact shape this repository keeps rediscovering, so it
    is refused by name.
    """
    repo = build_repo(tmp_path)
    harness = tmp_path / "harness"
    full_install(repo, harness)

    monkeypatch.setattr(checker, "DECLARED_PAIRS", ())
    code, _ = run(checker, repo, harness)
    assert code == 2


def test_manifest_khai_file_khong_co_trong_repo_thi_TU_CHOI(
    checker, tmp_path, monkeypatch
):
    """A manifest naming files the repo lacks is a broken ruler, not a verdict."""
    repo = build_repo(tmp_path)
    harness = tmp_path / "harness"
    full_install(repo, harness)

    monkeypatch.setattr(
        checker, "DECLARED_PAIRS", ("agent_supervisor.py", "khong_he_ton_tai.py")
    )
    code, _ = run(checker, repo, harness)
    assert code == 2


def test_clone_nong_bao_UNKNOWN_chu_khong_bao_DIVERGED(checker, tmp_path):
    """Shallow clone: say "cannot tell", never guess DIVERGED.

    The stale copy here is genuinely a past revision, but a depth-1 clone holds
    no commit that proves it. Reporting DIVERGED would tell someone with no
    local edits that they have unsaved work; they would check, find nothing,
    and learn the gate lies.
    """
    repo = build_repo(tmp_path)
    shallow = tmp_path / "shallow"
    git(tmp_path, "clone", "--quiet", "--depth", "1", f"file://{repo}", str(shallow))
    git(shallow, "branch", "-f", "pretend-main", "HEAD")

    harness = tmp_path / "harness"
    full_install(shallow, harness)
    install(harness, "agent_supervisor.py", "supervisor v1\n")

    code, report = run(checker, shallow, harness)

    assert report["shallow"] is True
    assert code == 2
    assert state_of(report, "agent_supervisor.py") == "UNKNOWN"


# --------------------------------------------------------------------------
# PHAI THA
# --------------------------------------------------------------------------


def test_khop_tung_byte_thi_IN_SYNC_va_thoat_0(checker, tmp_path):
    """The clean case really is clean -- otherwise every case above proves nothing."""
    repo = build_repo(tmp_path)
    harness = tmp_path / "harness"
    full_install(repo, harness)

    code, report = run(checker, repo, harness)

    assert code == 0
    assert report["drifted"] == []
    assert state_of(report, "agent_supervisor.py") == "IN_SYNC"
    assert state_of(report, "agent_checkpoint.py") == "IN_SYNC"


def test_file_chi_song_trong_harness_khong_bi_bao(checker, tmp_path):
    """`lane.py` and friends have no counterpart in `scripts/` and must stay quiet.

    Nine of the eleven installed files live only in the harness repo, which has
    no remote. There is no merged version to compare them against, so reporting
    them would be a permanent red nobody can clear -- and a permanent red is a
    gate people learn to skip.
    """
    repo = build_repo(tmp_path)
    harness = tmp_path / "harness"
    full_install(repo, harness)
    install(harness, "lane.py", "chi song trong harness, khong co ban repo\n")
    install(harness, "brains.py", "cung vay\n")

    code, report = run(checker, repo, harness)

    assert code == 0
    names = [pair["name"] for pair in report["pairs"]]
    assert "lane.py" not in names
    assert "brains.py" not in names


def test_khong_co_thu_muc_cai_dat_thi_BO_QUA_nhung_NOI_RA(checker, tmp_path, capsys):
    """No install directory is a real pass -- announced, and escalatable.

    A machine with nothing installed has nothing stale, so green is correct.
    But silent green here is indistinguishable from a gate that never ran, so
    the reason and the path are printed, and --strict turns it red for the
    caller that requires the deploy to exist.
    """
    repo = build_repo(tmp_path)
    absent = tmp_path / "khong-ton-tai"

    code = checker.main(
        [
            "--repo",
            str(repo),
            "--harness-root",
            str(absent),
            "--ref",
            "pretend-main",
            "--no-fetch",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "BO QUA" in out
    assert str(absent) in out, "phai noi ra no da tim o dau"

    strict = checker.main(
        [
            "--repo",
            str(repo),
            "--harness-root",
            str(absent),
            "--ref",
            "pretend-main",
            "--no-fetch",
            "--strict",
        ]
    )
    assert strict == 1


# --------------------------------------------------------------------------
# Hien vat that
# --------------------------------------------------------------------------


def test_quet_that_tra_ve_phan_loai_dut_khoat(checker):
    """Run against this machine's real install; assert shape, not today's answer.

    Asserting "agent_supervisor.py is BEHIND" would go red the moment the drift
    is fixed, and a test that breaks when the bug is fixed gets deleted. What is
    pinned instead: a real scan classifies every declared pair definitely, and
    the pair count never falls under the floor.
    """
    known = {"IN_SYNC", "BEHIND", "DIVERGED", "MISSING", "UNMANAGED", "UNKNOWN"}
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--json", "--no-fetch"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)

    if report.get("skipped"):
        pytest.skip("may nay khong cai ban harness nao — da bao cao bang BO QUA")

    assert len(report["pairs"]) >= checker.MIN_PAIRS
    for pair in report["pairs"]:
        assert pair["state"] in known, pair
    assert result.returncode in (0, 2)
