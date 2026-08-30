#!/usr/bin/env python3
"""Run the demo-vs-main gate on a schedule, and refuse to be silently dead.

## Why a second call site and not a flag on the first one

`check_demo_matches_main.py` answers the right question. Nothing calls it.

On 2026-08-30 the demo machine on port 8099 served 58 routes while `origin/main`
declared 62, for sixteen commits, and every signal on the box was green. It was
found because a human opened the demo and got a 404 -- not because anything
asked. A gate with no caller is decoration; it only fires once you already
suspect the answer, and by then you did not need it.

`make demo-check` (added with the gate) is a manual call site. This is the
scheduled one.

## The failure mode a scheduler ADDS, and why half this file is about it

A periodic check has a way to fail that a manual one does not: the scheduler
stops. Crontab wiped, box rebooted, python moved, checkout deleted. When that
happens the watcher emits **nothing** -- and "no complaint" is byte-for-byte
what "everything is fine" looks like. Every dead detector in this repo has worn
that costume: the URL scanner with no Chrome returning `[]` and exit 0, the lint
wrapper printing a path and exiting 0.

So `run` records its verdict with a timestamp, and `status` treats **silence as
a failure**, not a pass:

    no status file at all   -> exit 2, the watcher has never run
    status older than max   -> exit 2, the watcher has stopped
    status unreadable       -> exit 2, never a 0

`status` is the half you put in a dashboard or another gate. Asking `run`
directly only tells you about the demo; asking `status` tells you about the
demo AND about whether anybody is still watching it.

## Why it runs the gate out of a freshly fetched `main` worktree

The reference side of the comparison already comes from `origin/main` -- the
gate builds its own worktree for that. This goes one step further and runs *the
gate itself* from that fresh tree, rather than from whatever checkout cron
happens to point at.

That is not belt-and-braces, it is the same bug one layer up. The original
incident was a stale checkout at `/home/lakiet/mobile`, and a cron line naming
some path on disk is exactly the sort of thing that is still pointing there a
month later. Pinning the *checking logic* to `origin/main` means a stale
checkout can at worst fail loudly, not check the wrong thing quietly.

The consequence is worth stating plainly: until this gate is merged to `main`,
`run` exits 2 saying `main` has no gate yet. That is the honest answer. Use
`--ref` to point at the branch while it is still open.

## What it does NOT prove

- Nothing here calls a product route. A demo serving every path of `main` and
  answering 500 to all of them passes. `make smoke` and the hero-path walk are
  what answer that.
- It says nothing about the mobile bundle, which is built separately and can be
  older than the API on the same machine.
- `status` proves a check RAN and what it said. It cannot prove the box was
  reachable in between two runs.

Usage:
  scripts/demo_watch.py run                      # one round, records the verdict
  scripts/demo_watch.py status                   # what did the last round say, and was it recent
  scripts/demo_watch.py install                  # print the crontab block
  scripts/demo_watch.py install --apply          # install it
  scripts/demo_watch.py install --remove         # take it back out

Exit codes, the same three the gate uses:
0 the demo matches, 1 it differs, 2 the check could not be made -- and could not
be made is never a pass.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_URL = "http://127.0.0.1:8099"
DEFAULT_REF = "origin/main"

EXIT_OK = 0
EXIT_DIFFERS = 1
EXIT_CANNOT_RUN = 2

STATE_MATCH = "khop"
STATE_DIFFERS = "lech"
STATE_CANNOT = "khong-doi-chieu-duoc"

# Bumped whenever the recorded shape changes. `status` refuses to interpret a
# record it does not recognise -- reading an old shape with new rules is how a
# check starts answering confidently about a field that is no longer there.
SCHEMA = 1

# Cron every 10 minutes, and "stale" at 30. Two consecutive misses are tolerated
# so a single slow round does not page anybody; three means it has stopped.
CRON_SCHEDULE = "*/10 * * * *"
DEFAULT_MAX_AGE = 1800

# A tagged block so --apply is idempotent and --remove is exact. Editing a
# user's crontab by regex over bare lines is how unrelated entries disappear.
CRON_BEGIN = "# >>> mobile-demo-watch >>>"
CRON_END = "# <<< mobile-demo-watch <<<"

GATE_RELPATH = "scripts/check_demo_matches_main.py"

# Rendering main's OpenAPI imports the whole app; the gate allows 180s for it.
GATE_TIMEOUT = 300


def state_dir() -> Path:
    """Where the verdict lives. Outside the repo: it is machine state, not code."""
    env = os.environ.get("MOBILE_DEMO_WATCH_DIR")
    if env:
        return Path(env)
    return Path.home() / ".cache" / "mobile-demo-watch"


def status_path(directory: Path | None = None) -> Path:
    return (directory or state_dir()) / "status.json"


def git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run git, capturing both streams so a failure can be quoted verbatim."""
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=300
    )


def parse_report(stdout: str) -> dict | None:
    """The gate's JSON object, or None if there is not one to read.

    `--json` makes the gate print a JSON object and then keep talking: a human
    summary line on the pass path. Feeding all of that to `json.loads` raises,
    and the first version of this file swallowed the exception into an empty
    dict -- which then printed "KHỚP ... None route" and exited 0. Reading the
    leading value and stopping is the fix; returning None rather than {} is
    what keeps the caller from mistaking "unreadable" for "nothing missing".
    """
    text = stdout.strip()
    if not text:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def remote_for(ref: str, repo: Path) -> str:
    """Which remote to refresh before trusting `ref`.

    `origin/main` splits into a real remote. A local branch called
    `devops/canh-may-demo` splits into a remote that does not exist, and
    `git fetch devops` fails -- which would report "cannot compare" for a ref
    that is perfectly resolvable. So the first segment counts only if it is
    actually a configured remote; otherwise refresh `origin`, which is harmless
    and still the right thing to do before reading any ref in this repo.
    """
    first = ref.split("/", 1)[0] if "/" in ref else ""
    if not first:
        return "origin"
    listed = git("remote", cwd=repo)
    remotes = set(listed.stdout.split()) if listed.returncode == 0 else set()
    return first if first in remotes else "origin"


def write_status(path: Path, payload: dict) -> None:
    """Write the verdict atomically.

    A half-written status file read by `status` is a third kind of answer nobody
    wants to reason about, and cron guarantees the interleaving eventually.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def record(path: Path, *, state: str, code: int, detail: dict) -> None:
    now = time.time()
    write_status(
        path,
        {
            "schema": SCHEMA,
            "ts": now,
            "ts_iso": datetime.fromtimestamp(now, timezone.utc).isoformat(),
            "state": state,
            "exit": code,
            **detail,
        },
    )


def cmd_run(args: argparse.Namespace) -> int:
    """One round: fetch, render `ref`, ask the demo, write down what happened."""
    repo = Path(args.repo).resolve()
    out = status_path(Path(args.state_dir) if args.state_dir else None)

    def cannot(reason: str, **detail) -> int:
        record(
            out,
            state=STATE_CANNOT,
            code=EXIT_CANNOT_RUN,
            detail={"reason": reason, **detail},
        )
        print(f"demo_watch: KHÔNG ĐỐI CHIẾU ĐƯỢC — {reason}", file=sys.stderr)
        print(f"   (đã ghi vào {out}; mã 2, không phải 0)", file=sys.stderr)
        return EXIT_CANNOT_RUN

    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        return cannot(f"{repo} không phải cây git")

    if not args.no_fetch:
        fetched = git("fetch", remote_for(args.ref, repo), "--quiet", cwd=repo)
        if fetched.returncode != 0:
            return cannot(
                "không fetch được, nên không biết ref có mới không: "
                + fetched.stderr.strip()[-300:]
            )

    resolved = git("rev-parse", "--verify", f"{args.ref}^{{commit}}", cwd=repo)
    if resolved.returncode != 0:
        return cannot(
            f"không phân giải được ref '{args.ref}': {resolved.stderr.strip()[-300:]}"
        )
    sha = resolved.stdout.strip()

    tmp = Path(tempfile.mkdtemp(prefix="demo-watch-"))
    tree = tmp / "tree"
    try:
        add = git("worktree", "add", "--detach", "--quiet", str(tree), sha, cwd=repo)
        if add.returncode != 0:
            return cannot(
                f"không dựng được worktree cho {sha[:12]}: {add.stderr.strip()[-300:]}"
            )

        gate = tree / GATE_RELPATH
        if not gate.is_file():
            # Honest, and the expected answer until this lands on main.
            return cannot(
                f"{args.ref} ({sha[:12]}) chưa có {GATE_RELPATH} — chưa merge thì chưa canh được. "
                "Đang mở PR thì trỏ --ref vào nhánh đó.",
                ref=args.ref,
                ref_sha=sha,
            )

        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(gate),
                    "--url",
                    args.url,
                    "--ref",
                    sha,
                    "--no-fetch",
                    "--json",
                ],
                cwd=str(tree),
                capture_output=True,
                text=True,
                timeout=GATE_TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return cannot(f"cổng không chạy xong: {exc}", ref=args.ref, ref_sha=sha)

        # The gate prints its JSON and THEN a human line, so `json.loads` on the
        # whole stream fails. Decode just the leading value and ignore the rest.
        report = parse_report(proc.stdout)
        if report is None:
            # A verdict whose numbers we cannot read is a half-answer, and half
            # an answer recorded as "match" is how a check that stopped
            # measuring keeps reporting success. It printed "None route" once;
            # that is the shape being refused here.
            return cannot(
                "không đọc được báo cáo JSON của cổng — không đếm được route thì "
                f"không khẳng định được là khớp. stdout: {proc.stdout.strip()[:300]}",
                ref=args.ref,
                ref_sha=sha,
            )

        detail = {
            "url": args.url,
            "ref": args.ref,
            "ref_sha": sha,
            "ref_routes": report.get("ref_routes"),
            "served": report.get("served"),
            "missing": report.get("missing", []),
            "extra": report.get("extra", []),
            "gate_stderr": proc.stderr.strip()[-2000:],
        }

        if proc.returncode == EXIT_OK:
            record(out, state=STATE_MATCH, code=EXIT_OK, detail=detail)
            print(
                f"demo_watch: KHỚP — {args.url} phục vụ đúng {detail['served']} route "
                f"của {args.ref} ({sha[:12]})."
            )
            return EXIT_OK

        if proc.returncode == EXIT_DIFFERS:
            record(out, state=STATE_DIFFERS, code=EXIT_DIFFERS, detail=detail)
            miss, extra = detail["missing"], detail["extra"]
            print(
                f"demo_watch: LỆCH — {args.url} thiếu {len(miss)}, thừa {len(extra)} "
                f"so với {args.ref} ({sha[:12]}).",
                file=sys.stderr,
            )
            print(proc.stderr.strip()[-2000:], file=sys.stderr)
            return EXIT_DIFFERS

        # Anything else is the gate saying it could not answer. Keep its words.
        return cannot(
            f"cổng trả mã {proc.returncode}: {proc.stderr.strip()[-300:]}",
            ref=args.ref,
            ref_sha=sha,
        )
    finally:
        git("worktree", "remove", "--force", str(tree), cwd=repo)
        shutil.rmtree(tmp, ignore_errors=True)


def ago(seconds: float) -> str:
    """A duration a human can act on.

    Integer minutes floor sub-minute gaps to "0 phút", so a real red read
    "cách đây 0 phút, quá hạn 0 phút" -- which looks like the check is broken,
    and a gate that looks broken gets switched off.
    """
    seconds = max(0.0, seconds)
    if seconds < 90:
        return f"{int(seconds)} giây"
    if seconds < 5400:
        return f"{int(seconds // 60)} phút"
    return f"{seconds / 3600:.1f} giờ"


def cmd_status(args: argparse.Namespace) -> int:
    """Report the last verdict, and call silence a failure.

    This is the half that makes the schedule honest. A watcher that stopped
    emits nothing, and nothing is what a healthy watcher emits too.
    """
    path = status_path(Path(args.state_dir) if args.state_dir else None)

    def cannot(message: str) -> int:
        print(f"demo_watch: KHÔNG ĐỐI CHIẾU ĐƯỢC — {message}", file=sys.stderr)
        return EXIT_CANNOT_RUN

    if not path.is_file():
        return cannot(
            f"chưa có {path}. Canh gác chưa từng chạy — đây KHÔNG phải 'không có vấn đề'.\n"
            "   Bật lên:  scripts/demo_watch.py install --apply"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return cannot(f"{path} không đọc được: {exc}")
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return cannot(
            f"{path} không đúng schema {SCHEMA} — không diễn giải bừa một bản ghi lạ."
        )

    ts = data.get("ts")
    if not isinstance(ts, (int, float)):
        return cannot(f"{path} không có mốc thời gian hợp lệ.")

    age = time.time() - ts
    if args.json:
        print(
            json.dumps(
                {**data, "age_seconds": round(age, 1)}, ensure_ascii=False, indent=2
            )
        )

    if age > args.max_age:
        return cannot(
            f"lần canh gần nhất cách đây {ago(age)}, quá hạn {ago(args.max_age)}.\n"
            "   Canh gác đã dừng. Im lặng của nó đọc y hệt 'máy demo vẫn đúng' — không phải.\n"
            f"   Kiểm:  crontab -l | grep -A2 '{CRON_BEGIN}'"
        )

    state = data.get("state")
    if state == STATE_MATCH:
        print(
            f"demo_watch: KHỚP {ago(age)} trước — {data.get('served')} route, "
            f"{data.get('ref')} ({str(data.get('ref_sha'))[:12]})."
        )
        return EXIT_OK
    if state == STATE_DIFFERS:
        miss = data.get("missing") or []
        extra = data.get("extra") or []
        print(
            f"demo_watch: LỆCH {ago(age)} trước — thiếu {len(miss)}, thừa {len(extra)}.",
            file=sys.stderr,
        )
        for path_name in miss:
            print(f"      THIẾU {path_name}", file=sys.stderr)
        for path_name in extra:
            print(f"      THỪA  {path_name}", file=sys.stderr)
        return EXIT_DIFFERS
    return cannot(
        f"lần canh gần nhất không đối chiếu được: {data.get('reason', '(không ghi)')}"
    )


def watcher_in(repo: Path) -> Path:
    """The copy of this script cron should call: the one inside `repo`.

    Deliberately NOT `__file__`. This file is usually being run out of whatever
    lane worktree its author happened to be standing in, and those get deleted.
    A crontab line is long-lived; it must name a checkout that will still be
    there next week, and one that picks up later fixes to this shim when the
    repo is updated.
    """
    return repo / "scripts" / "demo_watch.py"


def cron_block(args: argparse.Namespace) -> str:
    """The crontab lines, generated so the paths cannot drift from this file."""
    script = watcher_in(Path(args.repo).resolve())
    log = state_dir() / "watch.log"
    schedule = getattr(args, "schedule", None) or CRON_SCHEDULE
    ref = getattr(args, "ref", None) or DEFAULT_REF
    return (
        f"{CRON_BEGIN}\n"
        f"# Máy demo phải phục vụ đúng bộ route của main. Sinh bởi {script.name}.\n"
        f"# Hỏi kết quả:  {script} status\n"
        f"{schedule} {sys.executable} {script} run --url {args.url} "
        f"--ref {ref} --repo {Path(args.repo).resolve()} >> {log} 2>&1\n"
        f"{CRON_END}"
    )


def strip_block(existing: str) -> str:
    """Drop our tagged block, leaving every other line of the crontab alone."""
    keep, inside = [], False
    for line in existing.splitlines():
        if line.strip() == CRON_BEGIN:
            inside = True
            continue
        if line.strip() == CRON_END:
            inside = False
            continue
        if not inside:
            keep.append(line)
    return "\n".join(keep).strip()


def cmd_install(args: argparse.Namespace) -> int:
    block = cron_block(args)
    if not args.apply and not args.remove:
        print(block)
        print()
        print(
            "Chưa cài gì. Cài:  scripts/demo_watch.py install --apply", file=sys.stderr
        )
        return EXIT_OK

    if shutil.which("crontab") is None:
        print("demo_watch: không có lệnh crontab trên máy này.", file=sys.stderr)
        return EXIT_CANNOT_RUN

    # Cài một dòng cron trỏ vào file không tồn tại là dựng đúng thứ file này
    # phản đối: mỗi 10 phút một lần thất bại không ai đọc, và bảng theo dõi thì
    # trống — trống đọc y hệt "không có vấn đề".
    script = watcher_in(Path(args.repo).resolve())
    if not args.remove and not script.is_file():
        print(f"demo_watch: {script} không tồn tại.", file=sys.stderr)
        print(
            "   Cron phải trỏ vào một checkout ổn định ĐÃ CÓ file này — tức là sau khi\n"
            "   nó vào main. Chưa merge thì chưa cắm lịch được.",
            file=sys.stderr,
        )
        return EXIT_CANNOT_RUN

    current = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = current.stdout if current.returncode == 0 else ""
    body = strip_block(existing)

    if args.remove:
        new = body + "\n" if body else ""
    else:
        new = (body + "\n\n" if body else "") + block + "\n"

    written = subprocess.run(
        ["crontab", "-"], input=new, capture_output=True, text=True
    )
    if written.returncode != 0:
        print(f"demo_watch: crontab từ chối: {written.stderr.strip()}", file=sys.stderr)
        return EXIT_CANNOT_RUN

    if args.remove:
        print("Đã gỡ khối canh gác khỏi crontab.")
        return EXIT_OK

    # Read back. A writer that reports success without re-reading is the same
    # trust-the-tool mistake this whole file argues against.
    back = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if CRON_BEGIN not in back.stdout:
        print(
            "demo_watch: ghi xong nhưng đọc lại không thấy khối. Không coi là đã cài.",
            file=sys.stderr,
        )
        return EXIT_CANNOT_RUN
    # Nhịp phải đọc ra từ dòng vừa ghi, không phải từ hằng số: in một con số
    # khác con số đã cài là cách người ta tin vào nhịp không tồn tại.
    print(f"Đã cài. Chạy {args.schedule}, log ở {state_dir() / 'watch.log'}.")
    print(f"Hỏi kết quả:  {Path(__file__).resolve()} status")
    print("Gỡ:           scripts/demo_watch.py install --remove")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Canh máy demo theo main, định kỳ.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="một lượt canh, ghi lại phán quyết")
    run.add_argument("--url", default=DEFAULT_URL)
    run.add_argument("--ref", default=DEFAULT_REF)
    run.add_argument("--repo", default=str(REPO_ROOT))
    run.add_argument("--state-dir", default=None)
    run.add_argument("--no-fetch", action="store_true")
    run.set_defaults(func=cmd_run)

    status = sub.add_parser("status", help="lượt canh gần nhất nói gì, và có mới không")
    status.add_argument("--state-dir", default=None)
    status.add_argument("--max-age", type=int, default=DEFAULT_MAX_AGE)
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    install = sub.add_parser("install", help="khối crontab cho lượt canh định kỳ")
    install.add_argument("--url", default=DEFAULT_URL)
    install.add_argument("--repo", default=str(REPO_ROOT))
    install.add_argument("--ref", default=DEFAULT_REF)
    install.add_argument(
        "--schedule",
        default=CRON_SCHEDULE,
        help=f"nhịp cron, mặc định '{CRON_SCHEDULE}'",
    )
    install.add_argument("--apply", action="store_true", help="ghi thật vào crontab")
    install.add_argument(
        "--remove", action="store_true", help="gỡ khối ra khỏi crontab"
    )
    install.set_defaults(func=cmd_install)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
