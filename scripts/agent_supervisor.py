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

Restarts on death, up to --max-restarts, and tells the agent it is resuming so
it does not begin again from nothing.
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
    r"|\b(401|403)\b"
    r"|Traceback \(most recent call last\)"
    r"|panic:",
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


def dir_progress(out_dir: pathlib.Path) -> tuple[str, int]:
    if not out_dir.exists():
        return "", 0
    files = [p for p in out_dir.rglob("*") if p.is_file()]
    return "", len(files)


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
        # Foreground on purpose. Backgrounding is how run 2 disappeared: the
        # job left the registry and its status could no longer be asked for.
        command = [
            str(AGY), "--output-format", "text",
            "--print-timeout", args.print_timeout,
            "--dangerously-skip-permissions",
            f"-p={pathlib.Path(prompt).read_text(encoding='utf-8')}",
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("agent", choices=["codex", "agy"])
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--cwd", default="/home/lakiet/codex-repo", help="codex only")
    parser.add_argument("--out-dir", default=".", help="agy only: where its files land")
    parser.add_argument("--timeout", type=int, default=2400, help="hard kill, seconds")
    parser.add_argument("--print-timeout", default="30m", help="agy only")
    parser.add_argument("--max-restarts", type=int, default=3)
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    repo = pathlib.Path(args.cwd)

    def snapshot() -> tuple[str, int]:
        return codex_progress(repo) if args.agent == "codex" else dir_progress(out_dir)

    prompt_path = pathlib.Path(args.prompt_file)
    base_prompt = prompt_path.read_text(encoding="utf-8")

    attempt = 0
    while attempt <= args.max_restarts:
        before = snapshot()
        emit("START", f"{args.agent} lan {attempt + 1}/{args.max_restarts + 1}, moc={before}")

        prompt_for_run = prompt_path
        if attempt:
            # Resuming: say so, or the agent starts from nothing and the work
            # already on disk is done a second time.
            resumed = out_dir / f".resume-{args.agent}-{attempt}.md"
            resumed.write_text(
                "LUU Y: lan chay truoc cua ban bi ngat giua chung. Cong viec da lam "
                "van con tren dia — kiem tra truoc, tiep tuc tu do, dung lam lai tu dau. "
                "Uu tien VIET KET QUA ra file truoc khi lam them viec moi.\n\n" + base_prompt,
                encoding="utf-8",
            )
            prompt_for_run = resumed

        code, output = run_once(args.agent, str(prompt_for_run), args)

        for hit in sorted(set(FATAL_PATTERNS.findall(output))):
            emit("ALERT", f"{args.agent} chu ky loi: {hit!r}")

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
    return 1


if __name__ == "__main__":
    sys.exit(main())
