#!/usr/bin/env python3
"""Make an agent's unfinished work survive the agent.

The problem this solves happened for real. Codex ran three streams of work,
produced three review documents and a working module, and never committed. Then
its job left the registry and no status could be asked for. Nothing failed and
nothing reported. The work was still there -- sitting in a working tree that
only got read because somebody went looking.

That recovery worked. It was not a system. This is the system.

Every `--interval` seconds this writes the agent's entire working tree into a
git ref, then pushes that ref somewhere the machine dying cannot reach. Two
properties matter and both are deliberate:

**It never touches what the agent is doing.** The snapshot is built through a
throwaway index file, so the agent's own index, HEAD, branch and working tree
are all left exactly as they were. An agent halfway through `git add` is not
disturbed, and cannot be corrupted by a checkpoint landing at a bad moment.

**Checkpoints chain.** Each one is a commit whose parent is the previous
checkpoint, so `refs/checkpoints/<agent>` is a readable history of the work as
it grew -- not a single overwritten blob. When an agent dies you can see what it
had at any minute, diff two moments, and recover a file it later broke.

For an agent with no repository -- agy writes loose files -- a checkpoint is a
hard-linked copy of its output directory, which costs almost nothing on disk
and is just as recoverable.

    scripts/agent_checkpoint.py watch codex --repo /home/lakiet/codex-repo \
        --mirror /home/lakiet/mobile --push origin
    scripts/agent_checkpoint.py watch agy --out-dir /tmp/agy-run
    scripts/agent_checkpoint.py list codex --repo /home/lakiet/codex-repo
    scripts/agent_checkpoint.py restore codex --repo /home/lakiet/codex-repo --to /tmp/rescued
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

CHECKPOINT_NS = "refs/checkpoints"


def emit(kind: str, message: str) -> None:
    print(f"{kind} [{time.strftime('%H:%M:%S')}] {message}", flush=True)


def git(repo: pathlib.Path, *args: str, env: dict | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **(env or {})},
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def try_git(repo: pathlib.Path, *args: str) -> str | None:
    try:
        return git(repo, *args)
    except RuntimeError:
        return None


def snapshot_repo(repo: pathlib.Path, agent: str, note: str) -> str | None:
    """Commit the whole working tree to refs/checkpoints/<agent>. Returns sha."""
    ref = f"{CHECKPOINT_NS}/{agent}"
    previous = try_git(repo, "rev-parse", ref)

    # A throwaway index, at a path that does not exist yet -- git refuses an
    # empty file as an index, so creating the file first would fail.
    # Staging into the agent's real index would fight with whatever it is
    # doing, and could leave it staged when it expected clean.
    with tempfile.TemporaryDirectory(prefix=f"ckpt-{agent}-") as scratch:
        env = {"GIT_INDEX_FILE": str(pathlib.Path(scratch) / "index")}
        # Ignored files are left out on purpose. `node_modules` alone would make
        # every checkpoint enormous, and build output is reproducible by
        # definition. What nearly got lost was untracked SOURCE -- review docs,
        # a new module -- and plain `-A` captures exactly that.
        git(repo, "add", "-A", ".", env=env)
        tree = git(repo, "write-tree", env=env)

    head = try_git(repo, "rev-parse", "HEAD")
    parents: list[str] = []
    for candidate in (previous, head):
        if candidate and candidate not in parents:
            parents.extend(["-p", candidate])

    if previous:
        # Nothing changed since the last checkpoint: writing another commit
        # would bury the real ones under noise.
        if git(repo, "rev-parse", f"{previous}^{{tree}}") == tree:
            return None

    message = f"checkpoint({agent}): {note}\n\nHEAD was {head or 'unborn'}"
    commit = git(repo, "commit-tree", tree, *parents, "-m", message)
    git(repo, "update-ref", ref, commit)
    return commit


def mirror_and_push(mirror: pathlib.Path, source: pathlib.Path, agent: str, remote: str) -> None:
    """Copy the ref into a clone that has network, then push it off the machine.

    Codex cannot reach GitHub from its sandbox, so it can never push its own
    safety net. Somebody with network has to carry it.
    """
    ref = f"{CHECKPOINT_NS}/{agent}"
    git(mirror, "fetch", "--force", str(source), f"{ref}:{ref}")
    git(mirror, "push", "--force", remote, f"{ref}:{ref}")


def snapshot_dir(out_dir: pathlib.Path, store: pathlib.Path) -> pathlib.Path | None:
    """Hard-link the output directory into a timestamped copy. Near-zero cost."""
    files = [p for p in out_dir.rglob("*") if p.is_file()]
    if not files:
        return None
    target = store / time.strftime("%Y%m%d-%H%M%S")
    if target.exists():
        return None
    shutil.copytree(out_dir, target, copy_function=os.link, dirs_exist_ok=True)
    return target


def cmd_watch(args: argparse.Namespace) -> int:
    if args.agent == "codex":
        repo = pathlib.Path(args.repo)
        mirror = pathlib.Path(args.mirror) if args.mirror else None
        emit("INFO", f"cham diem {args.agent} moi {args.interval}s tai {repo}")
        while True:
            try:
                sha = snapshot_repo(repo, args.agent, f"tu dong moi {args.interval}s")
                if sha:
                    dirty = len(git(repo, "status", "--porcelain").splitlines())
                    emit("CHECKPOINT", f"{args.agent} {sha[:10]} ({dirty} file chua commit)")
                    if mirror and args.push:
                        try:
                            mirror_and_push(mirror, repo, args.agent, args.push)
                            emit("PUSHED", f"{args.agent} {sha[:10]} -> {args.push}")
                        except RuntimeError as problem:
                            # Losing the off-machine copy is bad but not fatal:
                            # the local ref still holds the work.
                            emit("ALERT", f"khong day duoc checkpoint: {problem}")
            except RuntimeError as problem:
                emit("ALERT", f"cham diem that bai: {problem}")
            time.sleep(args.interval)

    out_dir = pathlib.Path(args.out_dir)
    store = pathlib.Path(args.store or (out_dir.parent / f".checkpoints-{args.agent}"))
    store.mkdir(parents=True, exist_ok=True)
    emit("INFO", f"cham diem {args.agent} moi {args.interval}s tai {out_dir}")
    seen = 0
    while True:
        files = [p for p in out_dir.rglob("*") if p.is_file()] if out_dir.exists() else []
        if len(files) != seen:
            target = snapshot_dir(out_dir, store)
            if target:
                emit("CHECKPOINT", f"{args.agent} {len(files)} file -> {target.name}")
            seen = len(files)
        time.sleep(args.interval)


def cmd_list(args: argparse.Namespace) -> int:
    repo = pathlib.Path(args.repo)
    ref = f"{CHECKPOINT_NS}/{args.agent}"
    log = try_git(repo, "log", "--format=%h %ci %s", "-20", ref)
    if not log:
        emit("INFO", f"chua co checkpoint nao cho {args.agent}")
        return 0
    print(log)
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    repo = pathlib.Path(args.repo)
    ref = args.sha or f"{CHECKPOINT_NS}/{args.agent}"
    target = pathlib.Path(args.to)
    target.mkdir(parents=True, exist_ok=True)
    # Extract, never check out: checking out would move the agent's HEAD and
    # could destroy the very working tree being rescued.
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", ref],
        capture_output=True,
        check=True,
    )
    subprocess.run(["tar", "-x", "-C", str(target)], input=archive.stdout, check=True)
    emit("OK", f"da buc {ref} ra {target}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    watch = sub.add_parser("watch", help="cham diem lien tuc")
    watch.add_argument("agent")
    watch.add_argument("--repo", default="/home/lakiet/codex-repo")
    watch.add_argument("--out-dir", default=".")
    watch.add_argument("--store", default=None)
    watch.add_argument("--interval", type=int, default=60)
    watch.add_argument("--mirror", default=None, help="clone co mang, de day ref di")
    watch.add_argument("--push", default=None, help="ten remote, vd origin")
    watch.set_defaults(func=cmd_watch)

    listing = sub.add_parser("list", help="xem cac checkpoint da co")
    listing.add_argument("agent")
    listing.add_argument("--repo", default="/home/lakiet/codex-repo")
    listing.set_defaults(func=cmd_list)

    restore = sub.add_parser("restore", help="buc mot checkpoint ra thu muc")
    restore.add_argument("agent")
    restore.add_argument("--repo", default="/home/lakiet/codex-repo")
    restore.add_argument("--sha", default=None)
    restore.add_argument("--to", required=True)
    restore.set_defaults(func=cmd_restore)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
