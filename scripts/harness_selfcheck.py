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
import shutil
import subprocess
import sys
import time
from pathlib import Path

HARNESS = Path(os.environ.get("HARNESS_ROOT", Path.home() / "agent-harness"))

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


def cron_block(harness: Path, script: Path) -> str:
    """Generated, so the paths in the crontab cannot drift from this file."""
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
    script = Path(__file__).resolve()
    block = cron_block(harness, script)

    if not args.apply and not args.remove:
        print(block, end="")
        print(f"# Ghi that vao crontab:  {sys.argv[0]} install --apply")
        return 0
    if shutil.which("crontab") is None:
        print("tu-kiem: khong co lenh crontab tren may nay.", file=sys.stderr)
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

    ins = sub.add_parser("install", help="khoi crontab cho luot canh dinh ky")
    ins.add_argument("--apply", action="store_true", help="ghi that vao crontab")
    ins.add_argument("--remove", action="store_true", help="go khoi ra")
    ins.set_defaults(fn=cmd_install)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
