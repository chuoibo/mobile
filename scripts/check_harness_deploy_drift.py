#!/usr/bin/env python3
"""Is the harness that RUNS the same as the harness that was MERGED?

Two scripts in this repository are not executed from this repository. They are
executed from a hand-installed copy under `~/agent-harness/`, because the
repository is a place branches get switched, and switching a branch deletes a
file from disk for every branch that does not carry it. `agent_supervisor.py`
says so in its own docstring and gives the install command:

    git show <branch>:scripts/agent_supervisor.py > ~/agent-harness/agent_supervisor.py

That install is a person typing a command. Nothing has ever checked that they
did, and the gap is not hypothetical.

## The measurement that produced this file

Run 2026-08-31 against `origin/main` at b20cc4a:

    scripts/agent_supervisor.py   installed copy is 3 commits BEHIND main
        installed blob d2c98eb == 0389c58:scripts/agent_supervisor.py
        (committed 2026-08-28, at 15:43 — an ancestor of origin/main)
        The comma is load-bearing. `repo_guard.py` reads a digit run joined by
        spaces or hyphens as a possible account number, so a bare `YYYY-MM-DD
        HH` is ten digits to it and turns the guard red on a date written in a
        docstring. A comma is not one of the joiners, so it ends the run.
        commits it has not got:
            34d23da  #477  run_once measured its interval on the wall clock
            c749c98  #470  silence watchdog gagged by a BACKWARD clock step
            193fb3c  #32
    scripts/agent_checkpoint.py   IN SYNC

That count is three and not four, and the difference is a lesson about the
tool rather than trivia. `git log 0389c58..HEAD -- <path>` lists four commits,
because history simplification puts `3aaff52` in the range -- but `3aaff52` is
15:33 and `0389c58` is 15:43, so it is OLDER, not a commit the copy is missing.
The walk below compares blob against blob at each commit, which cannot make
that mistake, and that is why the report is built from the walk.

Both #470 and #477 are clock fixes. Both are merged. Neither is running, and
#470 had been merged for three days. Two engineers reviewed those patches, a
gate proved they were correct, `main` carries them -- and the file the harness
actually launches has never contained a single one of them. The review was real
and the merge was real; the deploy was a sentence in a docstring.

`brains.py:53` in the harness tree records the same accident from the other
direction, in a comment: a lesson "written down at agent_supervisor.py:99 but
never copied over here". So this had already happened at least once, was
noticed by one person, and was never turned into anything that would notice it
again. That is the shape this file exists to break.

## Direction is the whole question

"The two copies differ" is not actionable, and answering it wrong is expensive
in both directions. If the installed copy merely lags, overwriting it is free.
If it carries edits that were never committed, overwriting it destroys the only
copy -- and a harness whose working tree IS production is exactly where such
edits live.

So a difference is never reported as "drift". It is classified:

    IN_SYNC     installed blob == the blob at the anchor ref
    BEHIND      installed blob appears earlier in the anchor's history for that
                path. It is a real revision, just an old one. Nothing local,
                nothing to lose: redeploy is safe, and the report names every
                commit it is missing.
    DIVERGED    installed blob is in no commit that ever touched that path.
                Somebody edited the live file. DO NOT overwrite it blindly.
    MISSING     declared pair, nothing installed.
    UNMANAGED   an installed file that pairs with a tracked `scripts/` file but
                that no one declared. See the next section.
    UNKNOWN     the question could not be answered -- shallow clone, unreadable
                ref. Never silently folded into any of the above.

The BEHIND/DIVERGED split is decided by walking the commits that touched that
path and comparing blobs, not by `--find-object` heuristics. That walk is exact,
and it is what produces the "4 commits behind, here they are" list.

A shallow clone cannot see the history that distinguishes BEHIND from DIVERGED,
and would report every stale copy as DIVERGED -- a false alarm that says "you
have unsaved work" to somebody who has none. So shallowness is detected and
reported as UNKNOWN, which is red, but red for a stated reason.

## Why the pair list is declared AND discovered

Declared alone is a list that cannot notice what it is missing: install a third
script tomorrow and a hand-written manifest stays green forever, having measured
nothing about it.

Discovered alone is worse. Derive the pairs by scanning the install directory
and a pair vanishes from the report the moment somebody deletes the installed
file -- the check goes green precisely when the supervisor is gone. An empty
source list is not an empty problem; it is a gate that has quietly unhooked
itself.

So both, and they cross-check each other. The manifest makes deletion MISSING.
Discovery makes an undeclared pair UNMANAGED. A pair has to be in both lists to
be silent, and the floors below refuse to run at all on a manifest that has
been emptied or that points at files this repository does not have.

## What this does not check

It compares bytes against a git ref. It says nothing about whether the running
copy WORKS, and nothing about the nine files under `~/agent-harness/` that have
no counterpart in `scripts/` at all (`lane.py`, `brains.py`, `harnessd.py` and
friends). Those live in a repository with no remote, so there is no merged
version to compare them to -- the tree is production. They are deliberately not
reported here, and that gap is real: the clock fix in `lane.py` from #481 is
governed by nothing on this path.

It also cannot see a copy installed somewhere other than `AGENT_HARNESS`. It
reads the same environment variable `agy_test_pr.sh` reads, so it is looking
where the launcher looks, but a second launcher with a different path would be
invisible to it.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# The declared pairs. Repo path -> basename installed under the harness root.
#
# Keep this list and the discovery rule in `find_undeclared` in agreement: a
# file tracked at `scripts/<name>` whose twin sits in the harness root is a
# pair, and every pair belongs here. Adding one is one line; the cost of NOT
# adding it is that nothing measures whether it ships.
DECLARED_PAIRS = (
    "agent_supervisor.py",
    "agent_checkpoint.py",
)

# Floor. A manifest that has been emptied -- by an edit, a bad merge, a clever
# refactor -- makes every loop below iterate zero times and the whole gate pass
# without measuring anything. Passing on nothing is the failure this repository
# keeps re-finding, so it is named and refused rather than left to good luck.
MIN_PAIRS = 2

IN_SYNC = "IN_SYNC"
BEHIND = "BEHIND"
DIVERGED = "DIVERGED"
MISSING = "MISSING"
UNMANAGED = "UNMANAGED"
UNKNOWN = "UNKNOWN"

CLEAN_STATES = {IN_SYNC}


class Refuse(Exception):
    """The check cannot answer, and must not pretend the answer is 'fine'."""


def git(repo: Path, *args: str, check: bool = True) -> str:
    """Run git in `repo` and return stdout. Raises Refuse on failure if check."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise Refuse(
            f"git {' '.join(args)} -> rc={proc.returncode}: {proc.stderr.strip()}"
        )
    return proc.stdout


def blob_oid_of_file(repo: Path, path: Path) -> str:
    """Blob oid of a file on disk, computed the way git would compute it.

    Pure hashing -- it does not consult history, so it is the one measurement
    here that a shallow clone cannot distort.
    """
    return git(repo, "hash-object", "--", str(path)).strip()


def blob_oid_at_ref(repo: Path, ref: str, rel_path: str) -> str | None:
    """Blob oid recorded at `ref` for `rel_path`, or None if absent there."""
    proc = subprocess.run(
        ["git", "rev-parse", f"{ref}:{rel_path}"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def commits_touching(repo: Path, ref: str, rel_path: str) -> list[str]:
    """Commits reachable from `ref` that touched `rel_path`, newest first."""
    out = git(repo, "rev-list", ref, "--", rel_path)
    return [line for line in out.split("\n") if line]


def find_in_history(
    repo: Path, ref: str, rel_path: str, oid: str
) -> tuple[str, int, list[tuple[str, str]]] | None:
    """Locate `oid` among the blobs `rel_path` has held along `ref`.

    Returns (commit, commits_behind, skipped) where `skipped` is the list of
    (short_sha, subject) this installed copy has not got, newest first. Returns
    None when the blob was never that path's content -- which is what makes the
    copy DIVERGED rather than merely old.

    The walk is over one file's history, so it is short; being exact here is
    what lets the report say "these four commits" instead of "they differ".
    """
    history = commits_touching(repo, ref, rel_path)
    for index, commit in enumerate(history):
        if blob_oid_at_ref(repo, commit, rel_path) == oid:
            skipped = []
            for newer in history[:index]:
                subject = git(repo, "log", "-1", "--format=%h %s", newer).strip()
                short, _, text = subject.partition(" ")
                skipped.append((short, text))
            return commit, index, skipped
    return None


def is_shallow(repo: Path) -> bool:
    return git(repo, "rev-parse", "--is-shallow-repository").strip() == "true"


def find_undeclared(repo: Path, harness_root: Path) -> list[str]:
    """Installed files that pair with a tracked `scripts/` file but aren't declared.

    This is the half of the manifest that notices growth. It asks the question
    from the OTHER side -- start at what is installed, not at what was written
    down -- so a third script installed tomorrow cannot stay unmeasured just
    because nobody remembered to edit the tuple above.
    """
    if not harness_root.is_dir():
        return []
    tracked = set(git(repo, "ls-files", "scripts/").split("\n"))
    found = []
    for entry in sorted(harness_root.iterdir()):
        if not entry.is_file() or entry.suffix != ".py":
            continue
        if entry.name in DECLARED_PAIRS:
            continue
        if f"scripts/{entry.name}" in tracked:
            found.append(entry.name)
    return found


def classify_pair(
    repo: Path, harness_root: Path, ref: str, name: str, shallow: bool
) -> dict:
    """Classify one declared pair. Never returns a bare boolean."""
    rel_path = f"scripts/{name}"
    installed = harness_root / name
    result: dict = {
        "name": name,
        "repo_path": rel_path,
        "installed_path": str(installed),
    }

    ref_oid = blob_oid_at_ref(repo, ref, rel_path)
    if ref_oid is None:
        # Declared, but this repository does not carry it at the anchor. The
        # manifest is describing a world that does not exist; say so rather
        # than skipping the entry and shrinking the denominator.
        result.update(state=UNKNOWN, detail=f"{ref}:{rel_path} khong ton tai")
        return result
    result["ref_oid"] = ref_oid

    if not installed.is_file():
        result.update(state=MISSING, detail="khong co ban cai dat nao")
        return result

    installed_oid = blob_oid_of_file(repo, installed)
    result["installed_oid"] = installed_oid

    if installed_oid == ref_oid:
        result.update(state=IN_SYNC, detail="khop tung byte")
        return result

    located = find_in_history(repo, ref, rel_path, installed_oid)
    if located is not None:
        commit, behind, skipped = located
        result.update(
            state=BEHIND,
            detail=f"cham {behind} commit so voi {ref}",
            at_commit=commit,
            behind=behind,
            skipped=[{"sha": s, "subject": t} for s, t in skipped],
        )
        return result

    if shallow:
        # Not enough history to tell "old" from "edited". Reporting DIVERGED
        # here would tell somebody they have unsaved work when they may have
        # none, and that false alarm is how a gate gets switched off.
        result.update(
            state=UNKNOWN,
            detail="clone nong: khong du lich su de phan biet BEHIND voi DIVERGED",
        )
        return result

    result.update(
        state=DIVERGED,
        detail="blob nay chua bao gio la noi dung cua duong dan do — co sua tay",
    )
    return result


def scan(repo: Path, harness_root: Path, ref: str) -> dict:
    """Full scan. Raises Refuse when the check itself is not trustworthy."""
    if len(DECLARED_PAIRS) < MIN_PAIRS:
        raise Refuse(
            f"manifest chi con {len(DECLARED_PAIRS)} cap, san toi thieu la {MIN_PAIRS}. "
            "Mot manifest rong lam cong nay xanh ma khong do gi."
        )

    missing_from_repo = [
        n for n in DECLARED_PAIRS if not (repo / "scripts" / n).is_file()
    ]
    if missing_from_repo:
        raise Refuse(
            "manifest khai file khong co trong repo: " + ", ".join(missing_from_repo)
        )

    shallow = is_shallow(repo)
    pairs = [classify_pair(repo, harness_root, ref, n, shallow) for n in DECLARED_PAIRS]

    for name in find_undeclared(repo, harness_root):
        pairs.append(
            {
                "name": name,
                "repo_path": f"scripts/{name}",
                "installed_path": str(harness_root / name),
                "state": UNMANAGED,
                "detail": "co ca ban repo lan ban cai dat, nhung khong ai khai trong DECLARED_PAIRS",
            }
        )

    return {
        "ref": ref,
        "harness_root": str(harness_root),
        "shallow": shallow,
        "pairs": pairs,
        "drifted": [p["name"] for p in pairs if p["state"] not in CLEAN_STATES],
    }


def render(report: dict) -> str:
    lines = [
        f"Ban HARNESS dang CHAY vs ban da MERGE ({report['ref']})",
        f"  goc cai dat: {report['harness_root']}",
        "",
    ]
    for pair in report["pairs"]:
        lines.append(f"  {pair['state']:<9} {pair['name']}  — {pair['detail']}")
        for skipped in pair.get("skipped", []):
            lines.append(
                f"                 thieu: {skipped['sha']}  {skipped['subject']}"
            )
    lines.append("")

    if not report["drifted"]:
        lines.append("Moi cap khop. Thu dang chay DUNG la thu da duoc review.")
        return "\n".join(lines)

    lines.append(f"LECH: {', '.join(report['drifted'])}")
    lines.append("")
    for pair in report["pairs"]:
        state = pair["state"]
        if state == BEHIND:
            lines.append(
                f"  {pair['name']}: chi lag, KHONG co sua tay — chep de la an toan:\n"
                f"    git show {report['ref']}:{pair['repo_path']} > {pair['installed_path']}"
            )
        elif state == DIVERGED:
            lines.append(
                f"  {pair['name']}: co sua tay CHUA COMMIT. DUNG ghi de.\n"
                f"    git diff --no-index {pair['installed_path']} <(git show {report['ref']}:{pair['repo_path']})"
            )
        elif state == MISSING:
            lines.append(
                f"  {pair['name']}: chua cai dat bao gio:\n"
                f"    git show {report['ref']}:{pair['repo_path']} > {pair['installed_path']}"
            )
        elif state == UNMANAGED:
            lines.append(
                f"  {pair['name']}: them ten nay vao DECLARED_PAIRS trong "
                "scripts/check_harness_deploy_drift.py"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--harness-root",
        default=os.environ.get("AGENT_HARNESS") or str(Path.home() / "agent-harness"),
        help="thu muc chua ban cai dat (mac dinh: $AGENT_HARNESS hoac ~/agent-harness)",
    )
    parser.add_argument("--repo", default=".", help="goc repo")
    parser.add_argument("--ref", default="origin/main", help="moc so sanh")
    parser.add_argument(
        "--no-fetch", action="store_true", help="dung ref san co, khong fetch"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="coi 'khong co thu muc cai dat' la HONG thay vi bo qua",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--names-only", action="store_true", help="chi in ten cap bi lech"
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    harness_root = Path(args.harness_root).expanduser()

    if not harness_root.is_dir():
        # A machine with nothing installed has nothing stale. That is a real
        # pass, not a dodge -- but it is announced, with the path it looked at,
        # so "green" is never mistaken for "measured". --strict turns it red
        # for the one caller that requires the deploy to exist.
        message = (
            f"BO QUA: khong co {harness_root} — may nay khong cai ban harness nao, "
            "nen khong co gi de lech."
        )
        if args.json:
            print(json.dumps({"skipped": True, "reason": message}, ensure_ascii=False))
        elif not args.names_only:
            print(message)
        return 1 if args.strict else 0

    if not args.no_fetch:
        # Comparing against a stale origin/main would call a drifted copy
        # clean. Failure to fetch is not fatal -- offline is a normal state --
        # but it is said out loud, because the answer is then about an older
        # main than the caller thinks.
        proc = subprocess.run(
            ["git", "fetch", "--quiet", "origin"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0 and not args.names_only and not args.json:
            print(f"CANH BAO: git fetch that bai, dang so voi ban {args.ref} co san")

    try:
        report = scan(repo, harness_root, args.ref)
    except Refuse as exc:
        print(f"KHONG KIEM DUOC: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.names_only:
        for name in report["drifted"]:
            print(name)
    else:
        print(render(report))

    return 2 if report["drifted"] else 0


if __name__ == "__main__":
    sys.exit(main())
