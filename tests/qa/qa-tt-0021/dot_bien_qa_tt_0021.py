"""QA mutation table (qa-tt-0021) for PR #283 -- against MY walk, not the PR's.

`walk_f40_f41.py` came back 16/16 on the first honest run. A gate that has only
ever been green is not yet evidence: it has not been shown it can go red, or
that it goes red for the RIGHT reason. This table breaks one property at a time
and states in advance which of my own checks must fail.

Two kinds of row, and both are load-bearing:

  BREAKS   -- removes a property. My walk MUST go red, and the named check must
              be among the failures. Red for some other reason is a miss, not a
              catch, so the expected check name is compared, not just the count.
  KEEPS    -- changes the code while preserving the property (a rename, a
              constant, an equivalent query). My walk MUST stay green. A table
              with no green rows cannot tell "guards the property" apart from
              "reacts to any edit at all", and a gate that reddens on a rename
              gets switched off within a week.

Guards against traps this repo has actually been bitten by:
  * an anchor matching zero or many times aborts the row instead of running it
    (zero matches = the mutation never happened; many = the wrong copy patched)
  * every restore is from bytes captured in memory, never `git checkout`, which
    would also delete uncommitted work
  * `__pycache__` is purged after each restore, or stale bytecode reads as a
    surviving mutant

Run from `services/api/`:
    MOBILE_TEST_DATABASE_URL=... python3 ../../tests/qa/qa-tt-0021/dot_bien_qa_tt_0021.py
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]  # tests/qa/qa-tt-0021 -> repo root
API = ROOT / "services" / "api"
REPO = API / "app" / "api" / "repository.py"
SERVICE = API / "app" / "api" / "service.py"
WALK = HERE / "walk_f40_f41.py"

DB = os.environ["MOBILE_TEST_DATABASE_URL"]

# (label, file, anchor, replacement, kind, expected-failing-check-substring)
ROWS = [
    (
        "1. lookup before permission -- reopens the 403/404 oracle",
        SERVICE,
        """        _require_permission(
            action,
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        memory = self.repository.get_context_memory(context_id, memory_id)
        if memory is None:
            raise ApiProblem(404, "memory_not_found", "Memory does not exist")""",
        """        memory = self.repository.get_context_memory(context_id, memory_id)
        if memory is None:
            raise ApiProblem(404, "memory_not_found", "Memory does not exist")
        _require_permission(
            action,
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )""",
        "BREAKS",
        "one single code",
    ),
    (
        "2. memory lookup ignores the context -- cross-group wall reachable",
        REPO,
        """            select(Memory).where(
                Memory.id == memory_id, Memory.context_id == context_id
            )""",
        """            select(Memory).where(
                Memory.id == memory_id
            )""",
        "BREAKS",
        "via A's path",
    ),
    (
        "3. membership read from the HEADER claim, not the database (#253)",
        SERVICE,
        """            action,
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},""",
        """            action,
            actor,
            {"is_group_member": context_id in actor.context_ids},""",
        "BREAKS",
        "claiming membership",
    ),
    (
        "4. count hearts by joining comments too -- 2 x 2 reads 4",
        REPO,
        """                select(MemoryReaction.memory_id, func.count(MemoryReaction.id))
                .where(MemoryReaction.memory_id.in_(memory_ids))
                .group_by(MemoryReaction.memory_id)""",
        """                select(MemoryReaction.memory_id, func.count(MemoryReaction.id))
                .join(
                    MemoryComment,
                    MemoryComment.memory_id == MemoryReaction.memory_id,
                )
                .where(MemoryReaction.memory_id.in_(memory_ids))
                .group_by(MemoryReaction.memory_id)""",
        "BREAKS",
        "reads 2/2",
    ),
    (
        "5. comment is filed under the photo's author, not the caller",
        SERVICE,
        """        self._memory_of_member(context_id, memory_id, actor, "post_group_memory")
        record = self.repository.create_memory_comment(
            memory_id=memory_id,
            author_id=actor.id,
            body=request.body,""",
        """        memory = self._memory_of_member(
            context_id, memory_id, actor, "post_group_memory"
        )
        record = self.repository.create_memory_comment(
            memory_id=memory_id,
            author_id=memory.author_id,
            body=request.body,""",
        "BREAKS",
        "filed under the caller",
    ),
    # ---- rows that KEEP the property: these must stay green -----------------
    (
        "6. KEEPS: count(id) becomes count() on the comment side",
        REPO,
        """                select(MemoryComment.memory_id, func.count(MemoryComment.id))""",
        """                select(MemoryComment.memory_id, func.count())""",
        "KEEPS",
        "",
    ),
    (
        "7. KEEPS: the 409 refusal is worded differently",
        SERVICE,
        """                    "This person has already reacted to this memory",""",
        """                    "Ban da tha tim cho ky niem nay roi",""",
        "KEEPS",
        "",
    ),
    (
        "8. KEEPS: the 404 detail is worded differently",
        SERVICE,
        """            raise ApiProblem(404, "memory_not_found", "Memory does not exist")""",
        """            raise ApiProblem(404, "memory_not_found", "Khong tim thay ky niem")""",
        "KEEPS",
        "",
    ),
]


def purge_pycache() -> None:
    for path in API.rglob("__pycache__"):
        shutil.rmtree(path, ignore_errors=True)


def reset_tables() -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import psycopg;"
            f"c=psycopg.connect({DB.replace('+psycopg', '')!r}, autocommit=True);"
            "cur=c.cursor();"
            "[cur.execute('delete from '+t) for t in "
            "('memory_comments','memory_reactions','memories','memberships','contexts','people')]",
        ],
        check=True,
        capture_output=True,
    )


def run_walk() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(WALK)],
        cwd=API,
        capture_output=True,
        text=True,
        env={**os.environ, "MOBILE_TEST_DATABASE_URL": DB},
    )
    return proc.returncode, proc.stdout + proc.stderr


def failing_checks(output: str) -> list[str]:
    return [
        line.strip()[6:]
        for line in output.splitlines()
        if line.strip().startswith("FAIL")
    ]


def main() -> int:
    purge_pycache()
    reset_tables()
    print(
        "=== CONTROL: clean tree must be green before any colour below means anything ==="
    )
    rc, out = run_walk()
    if rc != 0:
        print(out[-3000:])
        print("\nCONTROL IS RED. Every row below would be meaningless. Stopping.")
        return 1
    print(
        f"  control rc={rc} -- "
        f"{[line for line in out.splitlines() if 'checks passed' in line]}\n"
    )

    verdicts = []
    for label, path, anchor, replacement, kind, expected in ROWS:
        original = path.read_bytes()
        text = original.decode("utf-8")
        hits = text.count(anchor)
        if hits != 1:
            print(
                f"  ABORT  {label}\n         anchor matched {hits} times, expected exactly 1"
            )
            verdicts.append((label, kind, "ABORT", f"anchor x{hits}"))
            continue
        try:
            path.write_text(text.replace(anchor, replacement, 1), encoding="utf-8")
            assert path.read_bytes() != original, "write produced no change"
            purge_pycache()
            reset_tables()
            rc, out = run_walk()
        finally:
            path.write_bytes(original)
            purge_pycache()

        fails = failing_checks(out)
        if kind == "BREAKS":
            named = any(expected in f for f in fails)
            ok = rc != 0 and named
            detail = f"rc={rc}, {len(fails)} failed" + (
                "" if named else f" -- but NOT the expected check ({expected!r})"
            )
        else:
            ok = rc == 0
            detail = f"rc={rc}" + ("" if ok else f", unexpectedly failed: {fails}")
        verdicts.append((label, kind, "as predicted" if ok else "MISS", detail))
        print(f"  {'OK ' if ok else 'MISS'}  [{kind}] {label}\n         {detail}")

    reset_tables()
    misses = [v for v in verdicts if v[2] != "as predicted"]
    print(f"\n{len(verdicts) - len(misses)}/{len(verdicts)} rows behaved as predicted")
    return len(misses)


if __name__ == "__main__":
    raise SystemExit(main())
