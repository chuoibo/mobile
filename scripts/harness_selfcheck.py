#!/usr/bin/env python3
"""Run the harness's own test suite without waiting for somebody to restart it.

## The gap this fills

The harness has a self-check. `team.sh` calls it from `kiem_tra_harness()` and
refuses to launch four lanes on top of a broken harness. That guard is real and
it has fired.

But it is a bash function reachable only from `start` and `restart`. Between two
restarts -- hours, sometimes a whole day -- nothing runs it. And the harness has
no remote, no CI and no deploy step: the working tree IS production, so an edit
is live the moment it is saved.

Measured on 2026-08-31: a regression rode in on `f874225` and broke three skill
gates. It was found when the Lead happened to run `team.sh start` and saw red.
For the hours in between, `require_skills` was off and every signal was quiet.
The gate was not weak; it simply had no caller.

## What is different here

Two call sites already exist for the check (`team.sh start`, and now
`team.sh check`). Both need a human. This is the scheduled one, and it does
three things the bash function cannot:

  a floor       an empty `tests/` glob makes the bash loop report ĐẠT having
                run nothing -- measured, see `test_harness_selfcheck.py`. This
                refuses instead, because a suite that lost its files is the one
                case that must never read as green.
  a record      the verdict lands in `state/selfcheck.json` with a timestamp
                and a fingerprint of the code it was about.
  a fingerprint the record says WHICH harness it judged, so a green verdict
                about last week's lane.py cannot pass for a green verdict about
                the lane.py running now.

## The failure mode a scheduler ADDS

A periodic check can fail in a way a manual one cannot: the scheduler stops.
Crontab wiped, box rebooted, interpreter moved. When that happens this file
emits **nothing** -- and "no complaint" is byte-for-byte what "everything is
fine" looks like. Every dead detector on this machine has worn that costume: the
URL scanner with no Chrome returning `[]` and exit 0, `gh run view --log-failed`
printing "log not found" and exiting 0.

So `status` treats silence as failure, never as a pass:

    no record at all        -> exit 2, nothing has ever run
    record older than max   -> exit 2, the runner has stopped
    record unreadable       -> exit 2, never a 0
    record about other code  -> exit 2, it did not answer today's question

`status` is the half another gate calls. Asking `run` tells you about the
harness; asking `status` tells you about the harness AND about whether anybody
is still checking it.

## Why the fingerprint has a grace period

A mismatch means "no verified self-check exists for the code that is live right
now" -- true, but it is also true for the sixty seconds after any harness edit,
and this runs on a 15-minute cron. Failing there would paint a product-repo
branch gate red for a harness edit the branch did not make and cannot fix.

So a mismatch is a failure only once the newest guarded source file is older
than `--max-age`: by then the scheduler has had a full cycle to catch up, and
still has not. Inside that window the mismatch prints but does not fail. The
staleness check above is independent of it, so a dead runner is still caught
during the grace window.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HARNESS = Path(os.environ.get("HARNESS_ROOT", Path.home() / "agent-harness"))
# The durable checkout a crontab line may name. `team.sh` calls it HARNESS_REPO
# and builds every lane worktree from it, so it is the one path on this machine
# that outlives branches.
DEFAULT_REPO = Path(os.environ.get("HARNESS_REPO", Path.home() / "mobile"))

# The test files the harness is expected to have. A count floor alone would let
# a rename quietly shrink the suite; naming them means losing one is loud and
# adding one is free. Renaming a file is meant to cost this line -- that is the
# whole point, because a rename that drops coverage is exactly the hole.
REQUIRED_TESTS = (
    "test_bang_chung_im_lang.py",
    "test_dong_ho_nhay_khong_giet_lane.py",
    "test_duong_bao_dong.py",
    "test_khong_dot_hang_doi.py",
    "test_phat_hien_hong.py",
    "test_xoay_vong_log.py",
)

# Sources whose change could change the answer. Root-level only and not
# recursive: `wt/` holds product-repo worktrees, which are not the harness.
FINGERPRINT_GLOBS = ("*.py", "tests/*.py", "team.sh")

MIN_TEST_FILES = 6

PER_FILE_TIMEOUT = 300
DEFAULT_MAX_AGE = 3600
CRON_MINUTES = 15

CRON_BEGIN = "# >>> harness-selfcheck >>>"
CRON_END = "# <<< harness-selfcheck <<<"


class Refuse(Exception):
    """The check cannot be run at all. Never reported as a pass."""


def _stamp(unix: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(unix))


def guarded_sources(harness: Path) -> list[Path]:
    """Every file the fingerprint covers, deduplicated and ordered."""
    found: set[Path] = set()
    for pattern in FINGERPRINT_GLOBS:
        for path in harness.glob(pattern):
            if path.is_file() and "__pycache__" not in path.parts:
                found.add(path)
    return sorted(found)


def fingerprint(harness: Path) -> str:
    """Hash the harness sources by CONTENT, not mtime.

    A `touch` must not invalidate a good verdict, and a revert back to known
    text must land on the fingerprint that was already judged green.
    """
    digest = hashlib.sha256()
    for path in guarded_sources(harness):
        body = hashlib.sha256(path.read_bytes()).hexdigest()
        digest.update(f"{path.relative_to(harness)}:{body}\n".encode())
    return "sha256:" + digest.hexdigest()


def newest_source_age(harness: Path, now: float | None = None) -> float | None:
    """Seconds since the most recent edit to a guarded source, None if none."""
    sources = guarded_sources(harness)
    if not sources:
        return None
    newest = max(p.stat().st_mtime for p in sources)
    return (time.time() if now is None else now) - newest


def discover(harness: Path) -> list[Path]:
    """The test files to run, refusing every way the list can come up short.

    The bash loop this replaces iterated a glob and skipped what did not exist,
    so an empty `tests/` directory produced ĐẠT with zero tests run.
    """
    tests_dir = harness / "tests"
    if not tests_dir.is_dir():
        raise Refuse(f"KHONG KIEM DUOC: khong co thu muc {tests_dir}")

    # The manifest is checked before the tree, because it is the thing that says
    # what "complete" means. A floor of len(REQUIRED_TESTS) would be no floor at
    # all: empty the manifest and nothing is missing, so every later check
    # passes on a suite of zero. That is the same shape as the empty glob this
    # file exists to refuse -- a source list that shrank to nothing reading as
    # green -- so the floor is a literal that editing the manifest cannot move.
    if len(REQUIRED_TESTS) < MIN_TEST_FILES:
        raise Refuse(
            f"KHONG KIEM DUOC: REQUIRED_TESTS chi con {len(REQUIRED_TESTS)} "
            f"ten, san la {MIN_TEST_FILES}. Danh sach nguon tu ngan lai thi "
            f"cong tu thao, nen day la tu choi chu khong phai canh bao."
        )

    found = sorted(p for p in tests_dir.glob("test_*.py") if p.is_file())
    missing = [name for name in REQUIRED_TESTS if not (tests_dir / name).is_file()]
    if missing:
        raise Refuse(
            "KHONG KIEM DUOC: thieu ca test bat buoc: "
            + ", ".join(missing)
            + f"\n  Neu da doi ten that, sua REQUIRED_TESTS trong {__file__}"
            + " -- dung de danh sach tu ngan lai trong im lang."
        )
    return found


def _lock(harness: Path) -> Path | None:
    """Refuse a second concurrent run, but never let a corpse block forever."""
    path = harness / "state" / "selfcheck.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        try:
            held = time.time() - path.stat().st_mtime
        except FileNotFoundError:
            held = None
        # A run is bounded by len(tests) * PER_FILE_TIMEOUT. Past that the
        # holder is gone and the lock is litter, not a signal.
        budget = PER_FILE_TIMEOUT * (len(REQUIRED_TESTS) + 1)
        if held is not None and held > budget:
            path.unlink(missing_ok=True)
            return _lock(harness)
        return None
    os.write(fd, f"{os.getpid()}\n".encode())
    os.close(fd)
    return path


def run_one(harness: Path, test: Path) -> dict:
    """Run one harness test file the way `team.sh` runs it: as a script."""
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, str(test)],
            cwd=str(harness),
            capture_output=True,
            text=True,
            timeout=PER_FILE_TIMEOUT,
        )
        out, code = (proc.stdout or "") + (proc.stderr or ""), proc.returncode
    except subprocess.TimeoutExpired:
        out, code = f"TIMEOUT sau {PER_FILE_TIMEOUT}s", 124

    ran = 0
    for line in out.splitlines():
        if line.startswith("Ran ") and " test" in line:
            try:
                ran = int(line.split()[1])
            except (IndexError, ValueError):
                ran = 0
    head = [
        ln
        for ln in out.splitlines()
        if ln.startswith(("FAIL", "ERROR", "TIMEOUT")) or "Error" in ln
    ]
    return {
        "name": test.name,
        "ok": code == 0,
        "exit": code,
        "ran": ran,
        "seconds": round(time.monotonic() - started, 1),
        "why": head[:3],
    }


def emit_alert(harness: Path, event: dict) -> None:
    """Append to the road the Lead's feed already tails.

    `watch_for_lead.sh` follows `state/alerts.jsonl` and pipes it through
    `format_alert.py`, whose last branch renders unknown event types rather
    than dropping them -- so a new type reaches the Lead without a formatter
    change. O_APPEND because the watcher reads this file while we write it.
    """
    event.setdefault("ts", _stamp())
    line = (json.dumps(event, ensure_ascii=False) + "\n").encode()
    state = harness / "state"
    state.mkdir(parents=True, exist_ok=True)
    for name in ("events.jsonl", "alerts.jsonl"):
        fd = os.open(state / name, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)


def cmd_run(args: argparse.Namespace) -> int:
    harness = Path(args.harness)
    record = harness / "state" / "selfcheck.json"

    held = _lock(harness)
    if held is None:
        print("tu-kiem: mot luot khac dang chay, bo luot nay.")
        return 4
    try:
        try:
            tests = discover(harness)
        except Refuse as exc:
            # A refusal is louder than a red suite: red means one test failed,
            # this means nothing was measured at all.
            print(f"tu-kiem: {exc}", file=sys.stderr)
            code_fp = fingerprint(harness)
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text(
                json.dumps(
                    {
                        "ts": _stamp(),
                        "unix": time.time(),
                        "verdict": "TU_CHOI",
                        "reason": str(exc),
                        "code_fingerprint": code_fp,
                        "files": [],
                        "ran_tests": 0,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )
            if args.alert:
                emit_alert(
                    harness,
                    {
                        "type": "HARNESS_SELFCHECK_REFUSED",
                        "alert": True,
                        "severity": "critical",
                        "reason": str(exc),
                    },
                )
            return 3

        # Fingerprint BEFORE running, so the record names the code that was
        # actually judged. Taking it afterwards would attribute the verdict to
        # an edit that landed mid-run.
        code_fp = fingerprint(harness)
        results = [run_one(harness, t) for t in tests]
        bad = [r for r in results if not r["ok"]]
        verdict = "DO" if bad else "XANH"

        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(
            json.dumps(
                {
                    "ts": _stamp(),
                    "unix": time.time(),
                    "verdict": verdict,
                    "code_fingerprint": code_fp,
                    "files": results,
                    "ran_tests": sum(r["ran"] for r in results),
                    "interpreter": sys.executable,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )

        for r in results:
            mark = "✓" if r["ok"] else "✗"
            print(
                f"  {mark} {r['name']:<42} {r['ran']} test  {r['seconds']}s"
                + ("" if r["ok"] else f"  ĐỎ exit={r['exit']}")
            )
        total = sum(r["ran"] for r in results)
        if bad:
            print(
                f"\ntu-kiem: ĐỎ — {len(bad)}/{len(results)} file hỏng "
                f"({total} test đã chạy)",
                file=sys.stderr,
            )
            for r in bad:
                for line in r["why"]:
                    print(f"    {r['name']}: {line}", file=sys.stderr)
            if args.alert:
                emit_alert(
                    harness,
                    {
                        "type": "HARNESS_SELFCHECK_RED",
                        "alert": True,
                        "severity": "critical",
                        "files": [r["name"] for r in bad],
                        "note": "harness tu kiem DO — cay dang chay la production",
                    },
                )
            return 1
        print(f"\ntu-kiem: XANH — {len(results)} file, {total} test")
        return 0
    finally:
        held.unlink(missing_ok=True)


def _cron_installed() -> bool | None:
    """True/False if the crontab answered, None if it could not be asked.

    None is not False: "crontab is not installed on this box" must not be
    reported as "somebody removed the watcher".
    """
    if shutil.which("crontab") is None:
        return None
    try:
        out = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 and not out.stdout:
        # No crontab for this user at all -- an answer, and the answer is no.
        return False
    return CRON_BEGIN in out.stdout


def cmd_status(args: argparse.Namespace) -> int:
    """Report on the harness AND on whether anybody is still checking it."""
    harness = Path(args.harness)
    record = harness / "state" / "selfcheck.json"
    max_age = args.max_age

    if not record.exists():
        print(
            f"tu-kiem: CHUA CHAY LAN NAO — khong co {record}.\n"
            f"  Bat canh gac:  {sys.argv[0]} install --apply",
            file=sys.stderr,
        )
        return 2
    try:
        data = json.loads(record.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"tu-kiem: KHONG DOC DUOC ban ghi ({exc!r}) — khong bao gio la 0.",
            file=sys.stderr,
        )
        return 2

    age = time.time() - float(data.get("unix") or 0)
    if age > max_age:
        # "Never armed" and "armed then died" are both exit 2, but they send the
        # reader to different places -- and telling somebody the watcher stopped
        # when no watcher was ever installed costs them a hunt for a corpse that
        # does not exist. The distinction is the whole subject of this file, so
        # it is worth one `crontab -l`.
        if _cron_installed() is False:
            print(
                f"tu-kiem: CHUA CAI CANH GAC — ban ghi {int(age)}s > {max_age}s "
                f"va khong co khoi cron nao. Ban ghi nay la mot luot chay TAY.\n"
                f"  Bat:  python3 {Path(__file__).name} install --apply",
                file=sys.stderr,
            )
        else:
            print(
                f"tu-kiem: BAN GHI CU — {int(age)}s > {max_age}s. Canh gac da "
                f"dung chay.\n  Kiem:  crontab -l | grep -A2 '{CRON_BEGIN}'",
                file=sys.stderr,
            )
        return 2

    verdict = data.get("verdict")
    if verdict == "TU_CHOI":
        print(f"tu-kiem: TU CHOI — {data.get('reason')}", file=sys.stderr)
        return 2
    if verdict != "XANH":
        print(
            f"tu-kiem: ban ghi noi {verdict} — "
            f"{[f['name'] for f in data.get('files', []) if not f.get('ok')]}",
            file=sys.stderr,
        )
        return 1

    # Green, fresh -- but about which harness? A verdict can be on schedule and
    # green forever while measuring code that has since been replaced.
    live = fingerprint(harness)
    if data.get("code_fingerprint") != live:
        edited = newest_source_age(harness)
        if edited is not None and edited > max_age:
            print(
                f"tu-kiem: BAN GHI NOI VE MA KHAC — sua gan nhat "
                f"{int(edited)}s truoc, qua han {max_age}s ma canh gac chua "
                f"cham lai.\n  Chay tay:  {sys.argv[0]} run",
                file=sys.stderr,
            )
            return 2
        print(
            f"tu-kiem: XANH cho ban truoc; ma vua doi "
            f"{int(edited or 0)}s truoc, con trong an han {max_age}s."
        )
        return 0

    print(
        f"tu-kiem: XANH — {data.get('ran_tests')} test, "
        f"{int(age)}s truoc, dung ma dang chay."
    )
    return 0


def runner_in(repo: Path) -> Path:
    """The copy of this script cron should call: the one inside `repo`.

    Deliberately NOT `__file__`. This file is normally being run out of whatever
    lane worktree its author happened to be standing in, and those get deleted,
    rebased, and left on branches that never merge. A crontab line outlives all
    of that: it must name a checkout that will still be there next week and that
    picks up later fixes when the repo is updated.

    Same reasoning as `demo_watch.watcher_in`, whose cron line has pointed at
    ~/mobile rather than a worktree since the day it was written.
    """
    return repo / "scripts" / "harness_selfcheck.py"


def cron_block(harness: Path, repo: Path) -> str:
    """Generated, so the paths in the crontab cannot drift from this file."""
    script = runner_in(repo.resolve())
    log = Path.home() / ".cache" / "harness-selfcheck" / "cron.log"
    return (
        f"{CRON_BEGIN}\n"
        f"# Bo tu kiem cua harness phai chay ma khong cho ai khoi dong lai doi.\n"
        f"# Hoi ket qua:  {sys.executable} {script} status\n"
        f"*/{CRON_MINUTES} * * * * HARNESS_ROOT={harness} {sys.executable} "
        f"{script} run --alert >> {log} 2>&1\n"
        f"{CRON_END}\n"
    )


def _strip_block(current: str) -> str:
    """Drop our tagged block, leaving every other crontab line alone."""
    out, skipping = [], False
    for line in current.splitlines():
        if line.strip() == CRON_BEGIN:
            skipping = True
            continue
        if line.strip() == CRON_END:
            skipping = False
            continue
        if not skipping:
            out.append(line)
    return "\n".join(out).strip()


def cmd_install(args: argparse.Namespace) -> int:
    harness = Path(args.harness)
    repo = Path(args.repo)
    block = cron_block(harness, repo)

    if not args.apply and not args.remove:
        print(block, end="")
        print(f"# Ghi that vao crontab:  {sys.argv[0]} install --apply")
        return 0
    if shutil.which("crontab") is None:
        print("tu-kiem: khong co lenh crontab tren may nay.", file=sys.stderr)
        return 2
    # Refuse to install a line pointing at a file that is not there. Cron would
    # accept it, fail every 15 minutes into a log nobody opens, and `status`
    # would report "chua chay lan nao" forever -- a watcher that is installed
    # and dead, which is the exact costume this file exists to strip off.
    target = runner_in(repo.resolve())
    if not args.remove and not target.is_file():
        print(
            f"tu-kiem: TU CHOI CAI - khong co {target}\n"
            f"  Dong crontab phai tro vao mot checkout ben vung, khong phai cay\n"
            f"  worktree cua lane (no bi xoa, bi rebase, hoac o nhanh chua merge).\n"
            f"  Cai sau khi ban va da vao main va {repo} da cap nhat.",
            file=sys.stderr,
        )
        return 2

    current = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    kept = _strip_block(current.stdout if current.returncode == 0 else "")
    new = kept + ("\n\n" if kept else "") + ("" if args.remove else block)

    written = subprocess.run(
        ["crontab", "-"], input=new, capture_output=True, text=True
    )
    if written.returncode != 0:
        print(f"tu-kiem: crontab tu choi: {written.stderr.strip()}", file=sys.stderr)
        return 2

    # Read back. `crontab -` has been seen to accept input and store nothing.
    back = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if args.remove:
        if CRON_BEGIN in back.stdout:
            print("tu-kiem: da goi go nhung khoi van con.", file=sys.stderr)
            return 2
        print("Da go khoi canh gac khoi crontab.")
        return 0
    if CRON_BEGIN not in back.stdout:
        print("tu-kiem: crontab nhan xong ma khong luu khoi.", file=sys.stderr)
        return 2
    print(
        f"Da bat canh gac, moi {CRON_MINUTES} phut mot luot.\n"
        f"  Kiem:  crontab -l | grep -A3 '{CRON_BEGIN}'"
    )
    return 0


# --- the contract this repo assumes of the harness that is installed --------
#
# The three measurements below used to be test classes in
# `tests/test_harness_selfcheck.py`, reading `~/agent-harness` from inside the
# blocking suite. That made the suite's verdict a function of a directory
# outside this repository -- the defect QA blocked #487 for: same SHA, thirteen
# minutes apart, `1 failed` then `0 failed`.
#
# Measured again 2026-08-31 on the file QA had NOT flagged, and it was the same
# class. Repo byte-identical (`git status` empty), one extra test file in the
# harness tree, nothing else changed:
#
#     ~/agent-harness as it is today          43 passed
#     the same tree + one new test file       1 failed, 36 passed, 6 skipped
#
# The harness has no remote and its working tree is production, so "one extra
# test file" is not a hypothetical: it is what any lane adding a harness test
# does, and it would have painted this repo's gate red on a change this repo
# did not make and could not fix.
#
# The measurements are worth keeping -- nothing else reads the harness contract
# at all -- so they moved here, behind `gate.sh harness-contract`, which is
# labelled local-only for the same reason `harness-clock` is.

# The event `run --alert` writes. A formatter that has stopped rendering this
# shape is how a new kind of breakage becomes invisible to the Lead.
CONTRACT_ALERT_EVENT = {
    "type": "HARNESS_SELFCHECK_RED",
    "alert": True,
    "severity": "critical",
    "files": ["test_phat_hien_hong.py"],
    "note": "harness tu kiem DO",
}

# Floor on the denominator, and a literal on purpose. Every verdict below is
# accumulated in a list, and a list that came up short reads exactly like a
# list where everything passed -- the same shape `discover()` above refuses.
# Deleting a check has to cost this line.
MIN_CONTRACT_CHECKS = 7

_CONTRACT_PASS_TEST = """import unittest


class T(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
"""

_CONTRACT_FAIL_TEST = """import unittest


class T(unittest.TestCase):
    def test_no(self):
        self.fail("co y lam do")


if __name__ == "__main__":
    unittest.main()
"""


def fabricate_harness(
    root: Path, *, missing: tuple[str, ...] = (), failing: tuple[str, ...] = ()
) -> Path:
    """A harness-shaped tree to point the real `team.sh` at.

    `team.sh check` is measured against a fabricated tree rather than the live
    one because the question is what `check` DOES -- exit non-zero on a red
    file, on an empty directory, on a suite that shrank -- and the live tree is
    green, so it can only ever answer the first of those.
    """
    (root / "tests").mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_TESTS:
        if name in missing:
            continue
        body = _CONTRACT_FAIL_TEST if name in failing else _CONTRACT_PASS_TEST
        (root / "tests" / name).write_text(body, encoding="utf-8")
    (root / "lane.py").write_text("# lane gia\n", encoding="utf-8")
    (root / "team.sh").write_text("#!/usr/bin/env bash\necho gia\n", encoding="utf-8")
    return root


def _team_check(harness: Path, root: Path) -> subprocess.CompletedProcess:
    """Run the INSTALLED `team.sh check` against a fabricated root."""
    team = harness / "team.sh"
    return subprocess.run(
        ["bash", str(team), "check"],
        env={**os.environ, "HARNESS_ROOT": str(root)},
        capture_output=True,
        text=True,
        timeout=600,
    )


def _contract_manifest(harness: Path) -> str | None:
    """REQUIRED_TESTS must name the files the installed tree actually has.

    Both directions matter and they fail differently. A manifest naming a file
    that is gone makes `discover()` refuse forever; a manifest missing a file
    that exists leaves the floor lower than the tree, so losing that file later
    is silent.
    """
    tests_dir = harness / "tests"
    if not tests_dir.is_dir():
        raise Refuse(f"KHONG KIEM DUOC: khong co thu muc {tests_dir}")
    real = {p.name for p in tests_dir.glob("test_*.py") if p.is_file()}
    missing = sorted(set(REQUIRED_TESTS) - real)
    undeclared = sorted(real - set(REQUIRED_TESTS))
    if missing:
        return f"REQUIRED_TESTS tro vao file khong co that: {missing}"
    if undeclared:
        return (
            f"cay harness co file test chua khai trong REQUIRED_TESTS: "
            f"{undeclared} -- san dang thap hon thuc te"
        )
    return None


def _contract_alert(harness: Path) -> str | None:
    """`format_alert.py` must still render the event `run --alert` writes."""
    fmt = harness / "format_alert.py"
    if not fmt.is_file():
        raise Refuse(
            f"KHONG KIEM DUOC: khong co {fmt} -- duong bao dong khong do duoc, "
            "va im lang o day khong duoc doc thanh DAT"
        )
    p = subprocess.run(
        [sys.executable, str(fmt)],
        input=json.dumps(CONTRACT_ALERT_EVENT) + "\n",
        capture_output=True,
        text=True,
        timeout=60,
    )
    if p.returncode != 0:
        return f"format_alert.py thoat {p.returncode}: {p.stderr.strip()!r}"
    thieu = [
        s
        for s in (CONTRACT_ALERT_EVENT["type"], CONTRACT_ALERT_EVENT["files"][0])
        if s not in p.stdout
    ]
    if thieu:
        return (
            f"format_alert.py im lang voi su kien nay (thieu {thieu}) -- "
            "bao dong se khong toi Lead"
        )
    return None


def _contract_team_sh(harness: Path) -> list[tuple[str, str | None]]:
    """What `team.sh check` DOES, measured by exit code, not by grep.

    An earlier version of these read the source text of `team.sh` -- one
    demanded the string `SAN_TEST`, the other the string `check)`. Mutation
    killed both: lowering the floor to `-lt 0` leaves `SAN_TEST=6` declared at
    the top of the file, and commenting the case arm out leaves `check)` in the
    text. So each case below fabricates a tree and reads the exit code.
    """
    team = harness / "team.sh"
    if not team.is_file():
        raise Refuse(
            f"KHONG KIEM DUOC: khong co {team} -- khong do duoc `check` lam gi"
        )
    out: list[tuple[str, str | None]] = []

    with tempfile.TemporaryDirectory() as d:
        root = fabricate_harness(Path(d))
        p = _team_check(harness, root)
        if p.returncode != 0:
            out.append(("team.sh check: cay du va xanh -> 0", f"thoat {p.returncode}"))
        else:
            out.append(("team.sh check: cay du va xanh -> 0", None))
        # A ✓ with no number reads exactly like a file that ran zero tests; an
        # older team.sh matched only the plural "tests" and printed a blank.
        cham = re.findall(r"✓ (\S+)\s+Ran (\d+) test", p.stdout)
        if len(cham) != len(REQUIRED_TESTS) or not all(int(n) >= 1 for _, n in cham):
            out.append(
                (
                    "team.sh check: moi file hien kem SO test da chay",
                    f"doc duoc {len(cham)}/{len(REQUIRED_TESTS)} dong co so",
                )
            )
        else:
            out.append(("team.sh check: moi file hien kem SO test da chay", None))
        # `start` fetches, builds worktrees and wants tmux; `check` must not.
        out.append(
            (
                "team.sh check: khong dung toi wt/",
                f"check tao ra {root / 'wt'}" if (root / "wt").exists() else None,
            )
        )

    with tempfile.TemporaryDirectory() as d:
        root = fabricate_harness(Path(d), failing=(REQUIRED_TESTS[2],))
        rc = _team_check(harness, root).returncode
        out.append(
            (
                "team.sh check: mot file DO -> khac 0",
                "thoat 0 tren cay co file do -- `check` dang dem file chu khong chay test"
                if rc == 0
                else None,
            )
        )

    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "tests").mkdir()
        rc = _team_check(harness, Path(d)).returncode
        out.append(
            (
                "team.sh check: tests/ rong -> khac 0",
                "thoat 0 tren thu muc tests/ rong" if rc == 0 else None,
            )
        )

    with tempfile.TemporaryDirectory() as d:
        root = fabricate_harness(Path(d))
        for name in REQUIRED_TESTS[2:]:
            (root / "tests" / name).unlink()
        rc = _team_check(harness, root).returncode
        out.append(
            (
                "team.sh check: duoi san -> khac 0",
                "thoat 0 voi 2 file test con lai" if rc == 0 else None,
            )
        )

    return out


def cmd_contract(args: argparse.Namespace) -> int:
    harness = Path(args.harness)
    if not harness.is_dir():
        print(f"KHONG KIEM DUOC: khong co cay harness tai {harness}", file=sys.stderr)
        return 3
    try:
        checks: list[tuple[str, str | None]] = [
            ("manifest REQUIRED_TESTS khop cay that", _contract_manifest(harness)),
            (
                "format_alert.py hien duoc su kien SELFCHECK_RED",
                _contract_alert(harness),
            ),
        ]
        checks += _contract_team_sh(harness)
    except Refuse as exc:
        print(str(exc), file=sys.stderr)
        return 3

    if len(checks) < MIN_CONTRACT_CHECKS:
        print(
            f"KHONG KIEM DUOC: chi chay {len(checks)} phep kiem, san la "
            f"{MIN_CONTRACT_CHECKS} -- danh sach tu ngan lai doc y het khi moi "
            "phep deu dat, nen day la tu choi chu khong phai DAT",
            file=sys.stderr,
        )
        return 3

    hong = [(ten, ly_do) for ten, ly_do in checks if ly_do is not None]
    for ten, ly_do in checks:
        print(
            f"  {'HONG' if ly_do else 'dat '}  {ten}"
            + (f" -- {ly_do}" if ly_do else "")
        )
    if hong:
        print(
            f"\nDO: {len(hong)}/{len(checks)} phep kiem hong voi cay harness tai "
            f"{harness}.\nDay la cay DANG CHAY, khong phai ban da merge.",
            file=sys.stderr,
        )
        return 1
    print(f"\nXANH: {len(checks)}/{len(checks)} phep kiem, cay harness {harness}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Chay bo tu kiem cua harness, khong cho khoi dong lai."
    )
    parser.add_argument(
        "--harness",
        default=str(HARNESS),
        help="goc cay harness (mac dinh ~/agent-harness)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="chay bo tu kiem ngay")
    run.add_argument(
        "--alert", action="store_true", help="bao vao alerts.jsonl khi DO/TU CHOI"
    )
    run.set_defaults(fn=cmd_run)

    st = sub.add_parser("status", help="im lang bi coi la that bai")
    st.add_argument("--max-age", type=int, default=DEFAULT_MAX_AGE)
    st.set_defaults(fn=cmd_status)

    ct = sub.add_parser(
        "contract", help="cay harness DANG CAI co dung hop dong repo nay gia dinh khong"
    )
    ct.set_defaults(fn=cmd_contract)

    ins = sub.add_parser("install", help="khoi crontab cho luot canh dinh ky")
    ins.add_argument(
        "--repo",
        default=str(DEFAULT_REPO),
        help="checkout ben vung ma cron se goi (mac dinh ~/mobile, KHONG phai "
        "worktree cua lane)",
    )
    ins.add_argument("--apply", action="store_true", help="ghi that vao crontab")
    ins.add_argument("--remove", action="store_true", help="go khoi ra")
    ins.set_defaults(fn=cmd_install)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
