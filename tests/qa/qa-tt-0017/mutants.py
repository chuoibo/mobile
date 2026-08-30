#!/usr/bin/env python3
"""Mutation table for the #271 workflow-drift gate.

#271 replaced `assertIn("scripts/postgres_tier.sh", <whole file>)` with a check
that reads `run:` step bodies, because a substring over a whole file cannot tell
a COMMAND from a MENTION of one. That is the right diagnosis. This table asks
whether the new check finished the job, by writing the SAME violation -- CI runs
the narrow `tests/postgres` tier again, so the sixteen live cases under
`tests/qa/` stop running -- in shapes the PR's own table (M7/M8/M9) did not try.

Rows are of three kinds and all three are needed to read the result:

  CONTROL  the shape #271 already blocks. Must be RED, else the harness is
           measuring nothing and every other row is meaningless.
  KEEP     the property is PRESERVED, only an incidental constant moves. Must
           be GREEN, else the gate is a byte-pin wearing a gate's clothes.
  EVADE    the property is BROKEN, written another way. GREEN here is a hole.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "postgres-repository.yml"
GATE = "tests/test_postgres_tier_runner.py"

ORIGINAL_STEP = """      - name: Migrate an isolated schema and exercise the real repository
        run: scripts/postgres_tier.sh -q"""

# Every EVADE row keeps a mention of the runner so that the first half of the
# gate ("some step invokes the runner") is satisfied by a shell COMMENT inside
# the run body -- the same confusion #271 removed at file scope, one level down.
MENTION = "          # was: scripts/postgres_tier.sh -q"

ROWS = [
    (
        "C1",
        "CONTROL",
        "inline pytest, runner name left in a shell comment (= PR's M7)",
        "RED",
        f"""      - name: Migrate an isolated schema and exercise the real repository
        run: |
{MENTION}
          cd services/api && python3 -m pytest tests/postgres -q""",
    ),
    (
        "K1",
        "KEEP",
        "runner still called, one extra flag (= PR's M8)",
        "GREEN",
        """      - name: Migrate an isolated schema and exercise the real repository
        run: scripts/postgres_tier.sh -q --maxfail=1""",
    ),
    (
        "K2",
        "KEEP",
        "runner still called, step renamed (= PR's M9)",
        "GREEN",
        """      - name: Chay tang live tren PostgreSQL that
        run: scripts/postgres_tier.sh -q""",
    ),
    (
        "E1",
        "EVADE",
        "same inline pytest, split by a shell line-continuation",
        "RED",
        f"""      - name: Migrate an isolated schema and exercise the real repository
        run: |
{MENTION}
          cd services/api && python3 -m pytest \\
            tests/postgres -q""",
    ),
    (
        "E2",
        "EVADE",
        "same tier, reached by cd-ing one level deeper first",
        "RED",
        f"""      - name: Migrate an isolated schema and exercise the real repository
        run: |
{MENTION}
          cd services/api/tests && python3 -m pytest postgres -q""",
    ),
    (
        "E3",
        "EVADE",
        "same path, written with a ./ prefix",
        "RED",
        f"""      - name: Migrate an isolated schema and exercise the real repository
        run: |
{MENTION}
          cd services/api && python3 -m pytest ./tests/postgres -q""",
    ),
    (
        "E4",
        "EVADE",
        "same path, held in a shell variable",
        "RED",
        f"""      - name: Migrate an isolated schema and exercise the real repository
        run: |
{MENTION}
          TIER=tests/postgres
          cd services/api && python3 -m pytest "$TIER" -q""",
    ),
    (
        "E5",
        "EVADE",
        "runs NOTHING; runner named only in a comment",
        "RED",
        f"""      - name: Migrate an isolated schema and exercise the real repository
        run: |
{MENTION}
          echo "tam thoi bo qua tang live" """,
    ),
]


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", GATE, "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    tail = (proc.stdout or "").strip().splitlines()
    summary = tail[-1] if tail else "(no output)"
    return proc.returncode, summary


def main() -> int:
    original = WORKFLOW.read_text(encoding="utf-8")
    if ORIGINAL_STEP not in original:
        print("ANCHOR MISSING -- the step this table mutates is not in the "
              "workflow verbatim. Refusing to run: a no-op mutation prints "
              "GREEN and reads exactly like a gate that is holding.")
        return 2

    rc, summary = run_gate()
    print(f"{'BASE':<5} {'-':<8} {'unmutated tree':<52} "
          f"expect GREEN  got {'GREEN' if rc == 0 else 'RED':<5}  {summary}")
    if rc != 0:
        print("BASELINE IS RED -- every row below is uninterpretable.")
        return 2

    verdicts = []
    try:
        for tag, kind, desc, expect, replacement in ROWS:
            WORKFLOW.write_text(
                original.replace(ORIGINAL_STEP, replacement), encoding="utf-8"
            )
            # A mutation that did not change the file would print the baseline's
            # GREEN and be read as "the gate caught nothing to catch".
            assert WORKFLOW.read_text(encoding="utf-8") != original, tag
            rc, summary = run_gate()
            got = "GREEN" if rc == 0 else "RED"
            ok = got == expect
            verdicts.append((tag, kind, ok, got, expect, desc))
            print(f"{tag:<5} {kind:<8} {desc:<52} "
                  f"expect {expect:<5}  got {got:<5}  "
                  f"{'ok' if ok else '<<< MISMATCH'}  {summary}")
    finally:
        WORKFLOW.write_text(original, encoding="utf-8")

    holes = [v for v in verdicts if not v[2] and v[1] == "EVADE"]
    broken = [v for v in verdicts if not v[2] and v[1] != "EVADE"]
    print()
    if broken:
        print(f"HARNESS SUSPECT: {len(broken)} control/keep row(s) off expectation.")
        return 2
    if holes:
        print(f"HOLES: {len(holes)} of "
              f"{len([v for v in verdicts if v[1] == 'EVADE'])} evasion shapes "
              f"pass the gate: {', '.join(h[0] for h in holes)}")
        return 1
    print("ALL ROWS AS EXPECTED -- no evasion shape tried here got through.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
