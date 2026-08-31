#!/usr/bin/env python3
"""Keep an agent working, and shout the moment it stops.

Written after three silent deaths in one day, each of which looked like
progress from the outside:

1. Codex died on `.git/FETCH_HEAD: Read-only file system` because its sandbox
   only grants write to one workspace. Job status said **completed**.
2. Codex ran three parallel streams, produced review docs and a working module,
   never committed, and the background job vanished from the registry entirely.
   Nothing failed. Nothing reported. The work sat in a checkout nobody read.
3. agy drove a browser through a 42-cell QA matrix, then hit its own
   `--print-timeout` before writing the report. Every screenshot survived; the
   conclusions did not.

The common shape is that **an exit code is not a progress signal**. So this
supervisor never asks "did it exit cleanly". It asks "is there more work in the
world than there was before", and it defines that per agent:

    codex  -> new commits in its repo, or new untracked files
    agy    -> new files in its output directory

Every event goes to stdout as one line so a watcher can turn it into an alert.
Lines starting with ALERT are the ones a person needs to see.

    scripts/agent_supervisor.py codex --prompt-file p.md --cwd /home/lakiet/codex-repo
    scripts/agent_supervisor.py agy   --prompt-file p.md --out-dir /tmp/agy-run

**Install a copy outside any working tree before relying on it.** This script
lives in the repository, and the repository is a place branches get switched.
Doing that deletes the file from disk for every branch that does not carry it --
which killed a launch mid-command, twice, with `No such file or directory`. The
same switch also took `packages/shared/money.mjs` out from under a running dev
server and left an agent testing a 500. A supervisor that stops existing when
somebody checks out a branch is not supervising anything:

    mkdir -p ~/agent-harness
    git show <branch>:scripts/agent_supervisor.py > ~/agent-harness/agent_supervisor.py
    git show <branch>:scripts/agent_checkpoint.py > ~/agent-harness/agent_checkpoint.py

Restarts on death, up to --max-restarts. A restart is only useful if the agent
knows what it already did, so `--checkpoint` pairs this with
`agent_checkpoint.py`: work is snapshotted into a git ref every minute, and the
resume prompt carries the list of files that snapshot holds. Without that, a
restarted agent begins from nothing and redoes work sitting on disk -- exactly
what happened to agy, which re-drove a browser through a matrix it had already
finished and ran out of time again before writing anything down.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys
import threading
import time

# `codex exec` directly, not the companion wrapper.
#
# The wrapper talks to a long-lived `app-server-broker` over a unix socket, and
# that pair hangs: eleven minutes of zero CPU, no child processes, blocked in
# `epoll_wait`, watching a working tree that never changed. Killing every stale
# broker and starting a fresh one did not fix it -- the next run hung the same
# way after six minutes.
#
# The test that settled it: `codex exec` in the same directory, on the same
# account, answered in seconds. The agent works; the transport does not.
# Nothing here needs the broker's session sharing, and a layer that can hang
# silently is worse than no layer at all.
CODEX = pathlib.Path("/home/lakiet/.npm-global/bin/codex")
AGY = pathlib.Path("/home/lakiet/.local/bin/agy")

# Signatures worth waking someone for. Each one is a failure that has actually
# happened here, not a guess about what might.
FATAL_PATTERNS = re.compile(
    r"Read-only file system"
    r"|permission denied"
    r"|user denied permission"
    r"|needs an import attribute"
    r"|usage limit|quota exceeded|rate.?limit"
    r"|timeout waiting for response"
    # Non-capturing on purpose. `re.findall` with a capture group returns the
    # GROUP, so every match of a different alternative came back as an empty
    # string and the alert read `chu ky loi: ''`. A watchdog that says nothing
    # useful at the moment it fires is worse than one that stays quiet.
    r"|\b(?:401|403)\b"
    r"|Traceback \(most recent call last\)"
    r"|panic:",
    re.IGNORECASE,
)

# Failures another attempt cannot fix. Retrying a quota wall burns three more
# launches against the same wall and buries the one line that mattered under
# identical noise -- which is exactly what happened the first time a real usage
# limit hit. A watchdog that keeps retrying an unretryable error is not
# resilient, it is loud.
# Deliberately NOT bare "401", "403" or "authentication". A QA agent's whole
# job is to write about status codes, and the first time one filed a security
# report the supervisor read its own agent's prose -- "Thiếu X-Actor-ID -> trả
# về 401 Unauthorized" -- as proof the agent was locked out, and stopped it
# mid-run. The signal has to be the provider refusing US, which is phrased in
# ways a report about someone else's 401 is not.
NO_RETRY_PATTERNS = re.compile(
    r"usage limit|quota exceeded|insufficient.quota|out of credits"
    r"|user denied permission"
    r"|invalid[_ ]?api[_ ]?key|incorrect api key"
    r"|authentication[_ ]?(?:failed|error)",
    re.IGNORECASE,
)


def emit(kind: str, message: str) -> None:
    """One line per event. ALERT lines are what a watcher should surface."""
    stamp = time.strftime("%H:%M:%S")
    print(f"{kind} [{stamp}] {message}", flush=True)


def git(repo: pathlib.Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    return result.stdout.strip()


def codex_progress(repo: pathlib.Path) -> tuple[str, int]:
    """(HEAD sha, number of files git does not already know about)."""
    head = git(repo, "rev-parse", "HEAD")
    dirty = git(repo, "status", "--porcelain")
    return head, len([line for line in dirty.splitlines() if line.strip()])


# agy does not always write where you point it. Told to write into the current
# directory it may divert everything into its own scratch instead, which is how
# a run that produced a 16 KB report and 128 screenshots was measured as having
# produced nothing at all. Watch both, and count the union.
AGY_SCRATCH = pathlib.Path.home() / ".gemini/antigravity-cli/scratch"


def agy_dirs(out_dir: pathlib.Path) -> list[pathlib.Path]:
    return [out_dir, AGY_SCRATCH]


def recent_files(out_dir: pathlib.Path, since: float) -> list[pathlib.Path]:
    """Files this run touched. The scratch directory is shared across every
    project on the machine, so counting all of it would report thousands of
    files of somebody else's work as this agent's progress."""
    found: list[pathlib.Path] = []
    for directory in agy_dirs(out_dir):
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path.stat().st_mtime >= since:
                found.append(path)
    return found


def dir_progress(out_dir: pathlib.Path, since: float) -> tuple[str, int]:
    files = recent_files(out_dir, since)
    newest = max((p.stat().st_mtime for p in files), default=0.0)
    # The count alone is not enough. A file being rewritten -- the report grown
    # by another section -- moves the clock without moving the count, and that
    # is still progress.
    return f"{newest:.0f}", len(files)


def clear_stale_codex_sessions() -> list[str]:
    """Kill leftover brokers before starting Codex, and say which ones.

    Codex talks to a long-lived `app-server-broker` over a unix socket, and
    those brokers outlive the sessions that made them. Four were found alive at
    once here: three pinned to directories that had since been deleted, and one
    that had been up since the previous day with an empty log.

    That last one is the shape that matters. It was the RIGHT broker, it held
    an open connection, and it had burned two seconds of CPU across twelve
    minutes -- so the companion sat in `epoll_wait` producing nothing while the
    supervisor watched a working tree that never changed. Not a crash, not a
    refusal. A conversation with something that had stopped answering.

    A fresh broker per run costs a second of startup. A stale one costs the
    hour nobody noticed.
    """
    killed = []
    for pattern in ("codex-companion.mjs", "app-server-broker.mjs"):
        found = subprocess.run(
            ["pgrep", "-f", pattern], capture_output=True, text=True, check=False
        )
        for pid in found.stdout.split():
            if pid == str(os.getpid()):
                continue
            subprocess.run(["kill", "-9", pid], check=False)
            killed.append(f"{pattern}:{pid}")
    if killed:
        time.sleep(2)
        subprocess.run("rm -rf /tmp/cxc-*", shell=True, check=False)
    return killed


def watch_for_silence(
    agent: str,
    args: argparse.Namespace,
    out_dir: pathlib.Path,
    repo: pathlib.Path,
    stop,
) -> None:
    """Say something while an agent goes quiet, not after it finishes.

    A hung session exits cleanly and produces nothing, so waiting for the run
    to end means learning about an hour of silence an hour late. This watches
    the same signal the supervisor grades on -- did the world change -- and
    reports the gap AS IT GROWS.

    It never kills anything. Long thinking is legitimate; the point is that
    somebody knows it is happening.

    The gap is measured on `time.monotonic`, and that is load-bearing rather
    than stylistic. `time.time` is not an interval; it is a number the rest of
    the system is allowed to move, and on this machine it moves for two
    ordinary reasons -- an NTP step correction, and the WSL2 host suspending
    and resuming overnight. Neither says anything about the agent.

    Both directions were wrong, and the quiet one is the dangerous one:

        forward step  -> a working agent reported silent for an interval
                         nobody observed, naming a number that never happened
        backward step -> `quiet` goes NEGATIVE, `quiet >= heartbeat` is never
                         true, and a genuinely dead agent produces no alert

    A watchdog silenced by a clock step prints nothing, and printing nothing is
    also what a healthy watchdog does -- the same costume worn by the URL
    scanner with no Chrome that returned `[]` and exit 0. Measured against a
    600s backward step, this loop stayed silent through 360s of real silence at
    a 180s threshold.
    """
    # Wall clock ON PURPOSE, and it must stay that way: `since` is a watermark
    # compared against `path.stat().st_mtime` in `recent_files`, and file
    # mtimes are wall-clock. A monotonic value here would match no file ever.
    since = time.time()

    def world() -> tuple[str, int]:
        return (
            codex_progress(repo) if agent == "codex" else dir_progress(out_dir, since)
        )

    last, last_change = world(), time.monotonic()
    warned_at = 0.0
    while not stop.is_set():
        stop.wait(30)
        if stop.is_set():
            return
        now = world()
        if now != last:
            quiet = int(time.monotonic() - last_change)
            if quiet > args.heartbeat:
                emit("INFO", f"{agent} noi lai sau {quiet}s im lang")
            last, last_change, warned_at = now, time.monotonic(), 0.0
            continue
        quiet = time.monotonic() - last_change
        # Warn once per heartbeat window rather than every poll: an alert that
        # repeats every thirty seconds is an alert people mute.
        if quiet >= args.heartbeat and quiet - warned_at >= args.heartbeat:
            warned_at = quiet
            emit("ALERT", f"{agent} im lang {int(quiet)}s — khong doi mot byte nao")


def run_once(agent: str, prompt: str, args: argparse.Namespace) -> tuple[int, str]:
    """Run the agent to completion. Returns (exit code, combined output)."""
    if agent == "codex":
        stale = clear_stale_codex_sessions()
        if stale:
            emit("INFO", f"don phien codex cu: {', '.join(stale)}")
        command = [
            str(CODEX),
            "exec",
            "--cd",
            args.cwd,
            "--skip-git-repo-check",
            # `workspace-write`, not `--dangerously-bypass-approvals-and-sandbox`.
            # Codex only ever needs to write inside its own checkout, and the
            # bypass flag would also hand it the rest of the machine. The
            # narrow option is available and does the job.
            "--sandbox",
            "workspace-write",
            pathlib.Path(prompt).read_text(encoding="utf-8"),
        ]
    else:
        # Foreground on purpose. Backgrounding is how run 2 disappeared: the
        # job left the registry and its status could no longer be asked for.
        command = [
            str(AGY),
            "--output-format",
            "text",
            "--print-timeout",
            args.print_timeout,
            "--dangerously-skip-permissions",
            f"-p={pathlib.Path(prompt).read_text(encoding='utf-8')}",
        ]

    # Monotonic for the same reason as `watch_for_silence`: this is an
    # interval, and the wall clock is not one. The two ordinary steps on this
    # machine -- an NTP correction and the WSL2 host resuming -- both land
    # inside a long run, and both are silent.
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=args.timeout,
            cwd=args.out_dir if agent == "agy" else None,
            check=False,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        code = completed.returncode
    except subprocess.TimeoutExpired as expired:
        output = (
            (expired.stdout or b"").decode("utf-8", "replace") if expired.stdout else ""
        )
        code = 124
        emit("ALERT", f"{agent} vuot qua {args.timeout}s, da giet")

    elapsed = int(time.monotonic() - started)
    # A hung session exits cleanly and says nothing. Both parts are needed:
    # a fast quiet run is fine, a long quiet one is a conversation with
    # something that stopped answering.
    #
    # `elapsed` is the only thing separating those two, so a stepped clock does
    # not merely mislabel this run -- it decides whether failure #3 in the
    # module docstring gets reported at all. Backward: `elapsed` went negative,
    # the test never fired, and a dead session logged `ket thuc sau -300s`.
    # Forward: a 10s run was paged as a 3610s hang.
    if code == 0 and elapsed > 300 and len(output.strip()) < 200:
        emit(
            "ALERT",
            f"{agent} chay {elapsed}s ma gan nhu khong noi gi — nghi treo phien",
        )
    emit("INFO", f"{agent} ket thuc sau {elapsed}s, exit={code}")
    return code, output


def existing_work(
    args: argparse.Namespace, out_dir: pathlib.Path, repo: pathlib.Path, since: float
) -> str:
    """A concrete list, not a reassurance. The agent has to be able to act on it."""
    if args.agent == "codex":
        dirty = git(repo, "status", "--porcelain")
        names = [line[3:] for line in dirty.splitlines() if line.strip()]
        head = git(repo, "log", "--oneline", "-1")
        shown = "\n".join(f"  {name}" for name in names[:40]) or "  (khong co gi)"
        more = f"\n  ... va {len(names) - 40} file nua" if len(names) > 40 else ""
        return f"HEAD: {head}\nFile da tao/sua nhung CHUA COMMIT:\n{shown}{more}"
    named = sorted(str(p) for p in recent_files(out_dir, since))
    shown = "\n".join(f"  {name}" for name in named[:40]) or "  (khong co gi)"
    more = f"\n  ... va {len(named) - 40} file nua" if len(named) > 40 else ""
    return f"File ban da tao (KE CA trong scratch cua chinh ban):\n{shown}{more}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("agent", choices=["codex", "agy"])
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--cwd", default="/home/lakiet/codex-repo", help="codex only")
    parser.add_argument("--out-dir", default=".", help="agy only: where its files land")
    parser.add_argument("--timeout", type=int, default=2400, help="hard kill, seconds")
    parser.add_argument("--print-timeout", default="30m", help="agy only")
    parser.add_argument("--max-restarts", type=int, default=3)
    parser.add_argument(
        "--checkpoint", type=int, default=0, help="giay giua hai lan cham diem; 0 = tat"
    )
    parser.add_argument(
        "--heartbeat",
        type=int,
        default=180,
        help=(
            "giay im lang toi da truoc khi bao dong. Mot phien treo thoat sach "
            "va khong noi gi, nen cho toi luc no ket thuc moi biet la muon."
        ),
    )
    parser.add_argument(
        "--mirror", default=None, help="clone co mang, de day checkpoint di"
    )
    parser.add_argument("--push", default=None, help="ten remote nhan checkpoint")
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    repo = pathlib.Path(args.cwd)

    since = time.time()

    def snapshot() -> tuple[str, int]:
        return (
            codex_progress(repo)
            if args.agent == "codex"
            else dir_progress(out_dir, since)
        )

    prompt_path = pathlib.Path(args.prompt_file)
    base_prompt = prompt_path.read_text(encoding="utf-8")

    checkpointer = None
    if args.checkpoint:
        watch = [
            sys.executable,
            str(pathlib.Path(__file__).with_name("agent_checkpoint.py")),
            "watch",
            args.agent,
            "--interval",
            str(args.checkpoint),
        ]
        if args.agent == "codex":
            watch += ["--repo", args.cwd]
            if args.mirror and args.push:
                watch += ["--mirror", args.mirror, "--push", args.push]
        else:
            watch += ["--out-dir", str(out_dir)]
        checkpointer = subprocess.Popen(
            watch, stdout=sys.stdout, stderr=subprocess.STDOUT
        )
        emit("INFO", f"cham diem moi {args.checkpoint}s, pid={checkpointer.pid}")

    attempt = 0
    while attempt <= args.max_restarts:
        before = snapshot()
        emit(
            "START",
            f"{args.agent} lan {attempt + 1}/{args.max_restarts + 1}, moc={before}",
        )

        prompt_for_run = prompt_path
        if attempt:
            # Resuming. Naming the files that already exist is the whole point:
            # "you were interrupted" tells an agent nothing it can act on, while
            # "these 27 files are already on disk" tells it where to carry on.
            # Absolute. codex-companion resolves --prompt-file against the
            # agent's own --cwd rather than the supervisor's, so a relative
            # path here became ENOENT inside the agent repo -- and every
            # restart then failed instantly for a reason unrelated to the
            # original death.
            resumed = (out_dir / f".resume-{args.agent}-{attempt}.md").resolve()
            resumed.write_text(
                "LUU Y: lan chay truoc cua ban bi ngat giua chung.\n\n"
                "Cong viec da lam VAN CON TREN DIA:\n\n"
                f"{existing_work(args, out_dir, repo, since)}\n\n"
                "Kiem tra chung truoc, tiep tuc tu do, DUNG LAM LAI TU DAU.\n"
                "Uu tien VIET KET QUA ra file truoc khi lam them viec moi — lan truoc "
                "ban het gio dung luc sap ket luan va mat toan bo ket luan.\n\n"
                + base_prompt,
                encoding="utf-8",
            )
            prompt_for_run = resumed

        stop = threading.Event()
        heartbeat = None
        if args.heartbeat:
            heartbeat = threading.Thread(
                target=watch_for_silence,
                args=(args.agent, args, out_dir, repo, stop),
                daemon=True,
            )
            heartbeat.start()

        code, output = run_once(args.agent, str(prompt_for_run), args)

        stop.set()
        if heartbeat:
            heartbeat.join(timeout=2)

        for hit in sorted(set(FATAL_PATTERNS.findall(output))):
            emit("ALERT", f"{args.agent} chu ky loi: {hit!r}")

        blocked = NO_RETRY_PATTERNS.search(output)
        if blocked:
            # Report the whole line, not the matched fragment: a quota message
            # carries the time it resets, and that is the only part a person can
            # actually act on.
            line = next(
                (
                    ln.strip()
                    for ln in output.splitlines()
                    if blocked.group(0).lower() in ln.lower()
                ),
                blocked.group(0),
            )
            emit("ALERT", f"{args.agent} KHONG THE THU LAI: {line}")
            emit("ALERT", f"{args.agent} dung han, khong dot them lan chay nao")
            if checkpointer:
                checkpointer.terminate()
            return 2

        after = snapshot()
        progressed = after != before
        if args.agent == "codex" and after[0] != before[0]:
            emit("PROGRESS", f"codex commit moi: {git(repo, 'log', '--oneline', '-1')}")
        elif progressed:
            emit("PROGRESS", f"{args.agent} co thay doi: {before} -> {after}")

        if code == 0 and progressed:
            emit("OK", f"{args.agent} xong va CO san pham")
            return 0

        # This is the case that fooled us three times: a clean exit with an
        # empty world behind it. Treat it as failure, loudly, and retry.
        if code == 0 and not progressed:
            emit("ALERT", f"{args.agent} bao THANH CONG nhung KHONG RA SAN PHAM NAO")
        else:
            emit("ALERT", f"{args.agent} that bai exit={code}")
            tail = "\n".join(output.strip().splitlines()[-4:])
            if tail:
                emit("INFO", f"duoi log: {tail}")

        attempt += 1
        if attempt <= args.max_restarts:
            emit("RESTART", f"khoi dong lai {args.agent} sau 10s")
            time.sleep(10)

    emit(
        "ALERT",
        f"{args.agent} CHET HAN sau {args.max_restarts + 1} lan. Can nguoi vao xem.",
    )
    if args.checkpoint:
        emit(
            "INFO",
            "viec cua no KHONG mat: agent_checkpoint.py restore "
            + args.agent
            + " --to <dir>",
        )
    if checkpointer:
        checkpointer.terminate()
    return 1


if __name__ == "__main__":
    sys.exit(main())
