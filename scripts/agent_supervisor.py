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
import time

CODEX_COMPANION = pathlib.Path(
    "/home/lakiet/.claude/plugins/cache/openai-codex/codex/1.0.6/scripts/codex-companion.mjs"
)
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
NO_RETRY_PATTERNS = re.compile(
    r"usage limit|quota exceeded|insufficient.quota"
    r"|\b(?:401|403)\b"
    r"|user denied permission"
    r"|invalid.api.key|authentication",
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
    """Files this run touched, not counting the ones we wrote ourselves.

    Two exclusions, both learned the hard way. The scratch directory is shared
    across every project on the machine, so counting all of it reported
    thousands of files of somebody else's work as this agent's progress. And
    the resume prompt is written BY THIS SUPERVISOR before a retry -- counting
    it meant a run that produced nothing came back as "OK, and it made
    something", because the something was ours.
    """
    found: list[pathlib.Path] = []
    for directory in agy_dirs(out_dir):
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if not path.is_file() or path.stat().st_mtime < since:
                continue
            if path.name.startswith(".resume-"):
                continue
            found.append(path)
    return found


def dir_progress(out_dir: pathlib.Path, since: float) -> tuple[str, int]:
    files = recent_files(out_dir, since)
    newest = max((p.stat().st_mtime for p in files), default=0.0)
    # The count alone is not enough. A file being rewritten -- the report grown
    # by another section -- moves the clock without moving the count, and that
    # is still progress.
    return f"{newest:.0f}", len(files)


def run_once(agent: str, prompt: str, args: argparse.Namespace) -> tuple[int, str]:
    """Run the agent to completion. Returns (exit code, combined output)."""
    if agent == "codex":
        command = [
            "node", str(CODEX_COMPANION), "task",
            "--prompt-file", prompt,
            "--cwd", args.cwd,
            "--write",
        ]
    else:
        # The output directory is stated as an ABSOLUTE path, every run.
        # agy resolves relative paths against its trusted workspace rather
        # than the cwd it is given, so "write to the current directory" put a
        # file in the product repository -- the one directory the prompt had
        # forbidden it to touch. Saying where, exactly, removes the ambiguity
        # instead of relying on the agent to guess the same way twice.
        body = (
            f"THU MUC LAM VIEC CUA BAN: {pathlib.Path(args.out_dir).resolve()}\n"
            "Moi file ban tao phai ghi bang DUONG DAN TUYET DOI bat dau bang thu\n"
            "muc do. Dung ghi vao thu muc hien tai, dung ghi vao scratch cua\n"
            "chinh ban, va tuyet doi khong ghi vao /home/lakiet/mobile.\n\n"
            + pathlib.Path(prompt).read_text(encoding="utf-8")
        )
        # Foreground on purpose. Backgrounding is how run 2 disappeared: the
        # job left the registry and its status could no longer be asked for.
        command = [
            str(AGY), "--output-format", "text",
            "--print-timeout", args.print_timeout,
            "--dangerously-skip-permissions",
            f"-p={body}",
        ]

    started = time.time()
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
        output = (expired.stdout or b"").decode("utf-8", "replace") if expired.stdout else ""
        code = 124
        emit("ALERT", f"{agent} vuot qua {args.timeout}s, da giet")

    emit("INFO", f"{agent} ket thuc sau {int(time.time() - started)}s, exit={code}")
    return code, output


PRODUCT_REPO = pathlib.Path("/home/lakiet/mobile")


def repo_strays(args: argparse.Namespace) -> list[str]:
    """Untracked files an agent left in the product repository.

    Only meaningful for agents that are not supposed to be working there. For
    codex, whose whole job is editing a checkout, this is noise -- so it is
    skipped.
    """
    if args.agent == "codex":
        return []
    dirty = git(PRODUCT_REPO, "status", "--porcelain", "--untracked-files=normal")
    names = [
        line[3:]
        for line in dirty.splitlines()
        if line.startswith("??") and not line[3:].startswith("apps/")
    ]
    return names[:5]


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
    parser.add_argument("--mirror", default=None, help="clone co mang, de day checkpoint di")
    parser.add_argument("--push", default=None, help="ten remote nhan checkpoint")
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    repo = pathlib.Path(args.cwd)

    since = time.time()

    def snapshot() -> tuple[str, int]:
        return codex_progress(repo) if args.agent == "codex" else dir_progress(out_dir, since)

    prompt_path = pathlib.Path(args.prompt_file)
    base_prompt = prompt_path.read_text(encoding="utf-8")

    checkpointer = None
    if args.checkpoint:
        watch = [
            sys.executable,
            str(pathlib.Path(__file__).with_name("agent_checkpoint.py")),
            "watch", args.agent, "--interval", str(args.checkpoint),
        ]
        if args.agent == "codex":
            watch += ["--repo", args.cwd]
            if args.mirror and args.push:
                watch += ["--mirror", args.mirror, "--push", args.push]
        else:
            watch += ["--out-dir", str(out_dir)]
        checkpointer = subprocess.Popen(watch, stdout=sys.stdout, stderr=subprocess.STDOUT)
        emit("INFO", f"cham diem moi {args.checkpoint}s, pid={checkpointer.pid}")

    attempt = 0
    while attempt <= args.max_restarts:
        before = snapshot()
        emit("START", f"{args.agent} lan {attempt + 1}/{args.max_restarts + 1}, moc={before}")

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

        code, output = run_once(args.agent, str(prompt_for_run), args)

        for hit in sorted(set(FATAL_PATTERNS.findall(output))):
            emit("ALERT", f"{args.agent} chu ky loi: {hit!r}")

        blocked = NO_RETRY_PATTERNS.search(output)
        if blocked:
            # Report the whole line, not the matched fragment: a quota message
            # carries the time it resets, and that is the only part a person can
            # actually act on.
            line = next(
                (l.strip() for l in output.splitlines() if blocked.group(0).lower() in l.lower()),
                blocked.group(0),
            )
            emit("ALERT", f"{args.agent} KHONG THE THU LAI: {line}")
            emit("ALERT", f"{args.agent} dung han, khong dot them lan chay nao")
            if checkpointer:
                checkpointer.terminate()
            return 2

        strays = repo_strays(args)
        if strays:
            # The prompt forbids it, and a prompt is not an enforcement
            # mechanism. Saying so out loud beats discovering it in a diff.
            emit("ALERT", f"{args.agent} da ghi vao repo san pham: {strays}")

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

    emit("ALERT", f"{args.agent} CHET HAN sau {args.max_restarts + 1} lan. Can nguoi vao xem.")
    if args.checkpoint:
        emit("INFO", "viec cua no KHONG mat: agent_checkpoint.py restore " + args.agent + " --to <dir>")
    if checkpointer:
        checkpointer.terminate()
    return 1


if __name__ == "__main__":
    sys.exit(main())
