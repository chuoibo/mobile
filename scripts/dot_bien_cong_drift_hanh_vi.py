#!/usr/bin/env python3
"""Mutation table for the workflow-drift gate, after it stopped reading text.

`bug-095404` proved the `#271` gate green on five ways of writing one
violation. The repair stopped pattern-matching the workflow and started running
it: `tests/_workflow_step_exec.py` executes each `run:` body in a stub tree and
reports which FILE ran and what argv the shell built.

This table is the QA table (`tests/qa/qa-tt-0017/mutants.py`, PR #274) plus the
rows that repair needs in order to be believed. Run QA's table first -- it is
the unblock criterion and it is not this file's job to restate it.

What this file adds, and why each row exists:

  KEEP rows K3..K7 -- the repair could have been a byte-pin wearing a gate's
  clothes, and QA's two KEEP rows would not have noticed. The gate must stay
  green when the runner is reached through `bash`, through `./`, from inside a
  block with a comment, and THROUGH A SHELL VARIABLE. That last one is the
  proof it is not text matching: `"$RUNNER" -q` contains no runner name at all
  and must still pass. K7 checks the `if:` refusal is aimed and not a blanket
  ban on conditions.

  EVADE rows E6..E9 -- the half that carries the weight ("was the runner
  executed?") is blind by construction to a step that runs the runner AND
  something else, and to a step that never runs because of `if:`. Those are the
  holes the repair claims to have closed too, so they are measured, not
  asserted. E8 and E9 keep the runner call intact on purpose: they can only be
  caught by the second half.

A row that is GREEN when it should be RED is a hole. A KEEP row that is RED is
worse -- it means the gate is pinned to an incidental spelling, and a gate that
fails on a tidy-up is a gate somebody deletes.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "postgres-repository.yml"
GATE = "tests/test_postgres_tier_runner.py"

ORIGINAL_STEP = """      - name: Migrate an isolated schema and exercise the real repository
        run: scripts/postgres_tier.sh -q"""

NAME = "      - name: Migrate an isolated schema and exercise the real repository"

# Every EVADE row inherited from QA keeps a mention of the runner in a shell
# comment, which is what satisfied the old gate's first half.
MENTION = "          # was: scripts/postgres_tier.sh -q"

ROWS = [
    (
        "C1",
        "CONTROL",
        "inline pytest, runner named only in a comment",
        "RED",
        NAME + "\n        run: |\n" + MENTION + "\n"
        "          cd services/api && python3 -m pytest tests/postgres -q",
    ),
    (
        "K1",
        "KEEP",
        "runner still called, one extra flag",
        "GREEN",
        NAME + "\n        run: scripts/postgres_tier.sh -q --maxfail=1",
    ),
    (
        "K2",
        "KEEP",
        "runner still called, step renamed",
        "GREEN",
        "      - name: Chay tang live tren PostgreSQL that\n"
        "        run: scripts/postgres_tier.sh -q",
    ),
    (
        "K3",
        "KEEP",
        "runner reached through `bash` instead of by path",
        "GREEN",
        NAME + "\n        run: bash scripts/postgres_tier.sh -q",
    ),
    (
        "K4",
        "KEEP",
        "runner reached with a ./ prefix",
        "GREEN",
        NAME + "\n        run: ./scripts/postgres_tier.sh -q",
    ),
    (
        "K5",
        "KEEP",
        "runner call moved into a block, comment above it",
        "GREEN",
        NAME + "\n        run: |\n"
        "          # One definition of the live tier, not two.\n"
        "          scripts/postgres_tier.sh -q",
    ),
    (
        "K6",
        "KEEP",
        "runner path held in a shell variable (no name in the text)",
        "GREEN",
        NAME + "\n        run: |\n"
        "          RUNNER=scripts/postgres_tier.sh\n"
        '          "$RUNNER" -q',
    ),
    (
        "K7",
        "KEEP",
        "`if:` on a step that runs no shell (upload on failure)",
        "GREEN",
        NAME + "\n        run: scripts/postgres_tier.sh -q\n"
        "\n"
        "      - name: Keep the log when the tier fails\n"
        "        if: always()\n"
        "        uses: actions/upload-artifact@v4\n"
        "        with:\n"
        "          name: pytest-log\n"
        "          path: services/api/pytest.log",
    ),
    (
        "E1",
        "EVADE",
        "same inline pytest, split by a shell line-continuation",
        "RED",
        NAME + "\n        run: |\n" + MENTION + "\n"
        "          cd services/api && python3 -m pytest \\\n"
        "            tests/postgres -q",
    ),
    (
        "E2",
        "EVADE",
        "same tier, reached by cd-ing one level deeper first",
        "RED",
        NAME + "\n        run: |\n" + MENTION + "\n"
        "          cd services/api/tests && python3 -m pytest postgres -q",
    ),
    (
        "E3",
        "EVADE",
        "same path, written with a ./ prefix",
        "RED",
        NAME + "\n        run: |\n" + MENTION + "\n"
        "          cd services/api && python3 -m pytest ./tests/postgres -q",
    ),
    (
        "E4",
        "EVADE",
        "same path, held in a shell variable",
        "RED",
        NAME + "\n        run: |\n" + MENTION + "\n"
        "          TIER=tests/postgres\n"
        '          cd services/api && python3 -m pytest "$TIER" -q',
    ),
    (
        "E5",
        "EVADE",
        "runs NOTHING; runner named only in a comment",
        "RED",
        NAME + "\n        run: |\n" + MENTION + "\n"
        '          echo "tam thoi bo qua tang live"',
    ),
    (
        "E6",
        "EVADE",
        "runner called, but the step is behind `if:` and never runs",
        "RED",
        NAME + "\n        if: ${{ false }}\n        run: scripts/postgres_tier.sh -q",
    ),
    (
        "E7",
        "EVADE",
        "runner called AND a second, wider pytest run beside it",
        "RED",
        NAME + "\n        run: |\n"
        "          scripts/postgres_tier.sh -q\n"
        "          cd services/api && python3 -m pytest -q",
    ),
    (
        "E8",
        "EVADE",
        "runner called; an ADDED step re-runs the narrow tier",
        "RED",
        NAME + "\n        run: scripts/postgres_tier.sh -q\n"
        "\n"
        "      - name: Re-check the repository tier\n"
        "        run: cd services/api && python3 -m pytest tests/postgres -q",
    ),
    (
        "E9",
        "EVADE",
        "runner called; same step also runs tests/qa on its own",
        "RED",
        NAME + "\n        run: |\n"
        "          scripts/postgres_tier.sh -q\n"
        "          cd services/api && python3 -m pytest ../../tests/qa -q",
    ),
]


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", GATE, "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=900,
    )
    tail = (proc.stdout or "").strip().splitlines()
    # Only the final summary line. Grepping the whole output has read a count
    # out of a docstring before now.
    summary = tail[-1] if tail else "(no output)"
    return proc.returncode, summary


def main() -> int:
    original = WORKFLOW.read_text(encoding="utf-8")
    if ORIGINAL_STEP not in original:
        print(
            "ANCHOR MISSING -- the step this table mutates is not in the "
            "workflow verbatim. Refusing to run: a no-op mutation prints GREEN "
            "and reads exactly like a gate that is holding."
        )
        return 2

    rc, summary = run_gate()
    print(
        f"{'BASE':<5} {'-':<8} {'unmutated tree':<52} "
        f"expect GREEN  got {'GREEN' if rc == 0 else 'RED':<5}  {summary}"
    )
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
            print(
                f"{tag:<5} {kind:<8} {desc:<52} "
                f"expect {expect:<5}  got {got:<5}  "
                f"{'ok' if ok else '<<< MISMATCH'}  {summary}"
            )
    finally:
        WORKFLOW.write_text(original, encoding="utf-8")

    holes = [v for v in verdicts if not v[2] and v[1] == "EVADE"]
    pinned = [v for v in verdicts if not v[2] and v[1] == "KEEP"]
    broken = [v for v in verdicts if not v[2] and v[1] == "CONTROL"]
    print()
    if broken:
        print("CONTROL ROW OFF EXPECTATION -- the harness is measuring nothing.")
        return 2
    if pinned:
        print(
            f"BYTE-PIN: {len(pinned)} keep row(s) went RED with the property "
            f"intact: {', '.join(p[0] for p in pinned)}. The gate is pinned to a "
            "spelling, which is a different defect, not a fix."
        )
        return 1
    if holes:
        print(
            f"HOLES: {len(holes)} of "
            f"{len([v for v in verdicts if v[1] == 'EVADE'])} evasion shapes "
            f"pass the gate: {', '.join(h[0] for h in holes)}"
        )
        return 1
    print("ALL ROWS AS EXPECTED -- no evasion shape tried here got through.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
