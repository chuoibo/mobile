"""Independent mutation table for the response-side money gate merged in #277.

Run from the repo root, in a clean tree:

    python3 tests/qa/qa-tt-0019/dot-bien-cong-tien-ra.py

Why this file exists rather than a paragraph in a verdict: the gate it measures
is itself a gate, and the only way to tell "guards the property" apart from
"reacts to any edit" is to run rows of all three kinds and read their colours
together. A table where every row is red proves nothing, and a summary of one
is not re-runnable.

Three kinds of row, and the table is only readable because all three are here:

  break-property  the rule stops holding      -> the gate must go RED
  keep-property   the rule still holds, but   -> the gate must stay GREEN
                  the text around it changed
  out-of-scope    a real violation written in -> records what the gate cannot
                  a shape the walk cannot see    see, so nobody inherits a
                                                 conclusion it never reached

The out-of-scope row is the finding. `money_fields()` selects by field NAME
(`MONEY_SUFFIX = "_vnd"`, plus two dicts pinned by name), so a money field named
anything else is invisible to the walk no matter how lax it is. That is not a
live wrong number today -- measured separately, 0 of the 56 fields still lax on
a response model carries a money name -- but the gate's own headline claims more
than its walk delivers, and the next author to add `refund_amount: int` gets a
green tick.

Safety: each row restores `schemas.py` with `git checkout --` before and after
itself, and refuses to run a row whose anchor is not unique, so a mutation
cannot silently land on the wrong copy of a repeated line.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / "services/api/app/api/schemas.py"
SCHEMAS_REL = "services/api/app/api/schemas.py"
GATE = "services/api/tests/api/test_money_response_type_gate.py"

ROWS = (
    (
        "A. MoneyVnd alias mat strict (15 truong cung phu thuoc mot dong nay)",
        "break-property",
        "RED",
        "MoneyVnd = Annotated[int, Field(strict=True)]",
        "MoneyVnd = Annotated[int, Field()]",
    ),
    (
        "B. Truong tien THU N+1, ten dung quy uoc (_vnd), khai int lax",
        "break-property",
        "RED",
        "    spend_vnd: MoneyVnd\n",
        "    spend_vnd: MoneyVnd\n    refund_vnd: int = 0\n",
    ),
    (
        "C. Truong tien THU N+1, ten KHONG mang hau to _vnd, khai int lax",
        "out-of-scope",
        "GREEN (cho mu -- day la phat hien)",
        "    spend_vnd: MoneyVnd\n",
        "    spend_vnd: MoneyVnd\n    refund_amount: int = 0\n",
    ),
    (
        "D. Viet strict inline thay vi dung alias -- tinh chat khong doi",
        "keep-property",
        "GREEN",
        "    spend_vnd: MoneyVnd\n",
        "    spend_vnd: Annotated[int, Field(strict=True)]\n",
    ),
    (
        "E. Doi HANG SO cua NonNegativeMoneyVnd (ge=0 -> ge=-1), strict giu nguyen",
        "keep-property",
        "GREEN",
        "NonNegativeMoneyVnd = Annotated[int, Field(strict=True, ge=0)]",
        "NonNegativeMoneyVnd = Annotated[int, Field(strict=True, ge=-1)]",
    ),
)


def run_gate() -> str:
    """Last summary line of the gate, never a grep over the whole output.

    Reading only the final line because a docstring or a captured log inside the
    run can contain the word "passed" and be mistaken for the tally.
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            GATE,
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    for line in reversed(proc.stdout.strip().splitlines()):
        if "passed" in line or "failed" in line or "error" in line:
            return line.strip()
    return f"(could not read a tally, rc={proc.returncode})"


def restore() -> None:
    subprocess.run(["git", "checkout", "--", SCHEMAS_REL], cwd=ROOT, check=True)


def main() -> int:
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", SCHEMAS_REL],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        print(
            f"REFUSING: {SCHEMAS_REL} has uncommitted changes -- restore would eat them."
        )
        return 2

    print(f"BASELINE (no mutation): {run_gate()}\n")

    for label, kind, expected, old, new in ROWS:
        restore()
        text = SCHEMAS.read_text()
        hits = text.count(old)
        if hits != 1:
            print(f"{label}\n   SKIPPED: anchor appears {hits} times, not unique\n")
            continue
        SCHEMAS.write_text(text.replace(old, new, 1))
        # A mutation that changed nothing would report GREEN and read as proof.
        assert SCHEMAS.read_text() != text, "mutation was a no-op"
        print(
            f"{label}\n   kind={kind}  expected={expected}\n   actual  = {run_gate()}\n"
        )
        restore()

    left = subprocess.run(
        ["git", "status", "--porcelain", "--", SCHEMAS_REL],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    print(f"tree restored: {left or 'clean'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
