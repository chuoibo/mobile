#!/usr/bin/env python3
"""Count copies of the đồng integer-shape check under any `app/` root.

Why this exists: `docs/architecture/01-cuong-che-luat-1-so-nguyen-dong.md`
claims "13 before -> 1 after". A zero (or a one) with no baseline is
indistinguishable from a broken scanner, so the baseline has to be measurable
with the SAME instrument that produces today's number -- not with whatever
scanner happened to exist back then.

It reuses the matcher inside `tests/test_one_money_check.py` rather than
re-implementing it. Re-implementing would let this script and the gate drift
apart, and then a disagreement between them would prove nothing about the
tree -- only that two copies of a matcher disagree. That is the same
copy-paste failure the gate itself was written to stop.

Two units are printed on purpose, because the difference between them is the
whole lesson of section 3 of that document:

  * `scope`    -- one count per enclosing function
  * `subject`  -- one count per (enclosing function, checked expression)

`money_skill.validate_context` checks two different subjects, so `scope`
reports 12 where `subject` reports 13. #437's "13" is the subject unit. Quote
the number without the unit and the next person re-measures 12 and reads a
regression that is not there.

Usage:

    # today's tree
    cd services/api && python3 tests/qa/backend-111300-trang-kien-truc-luat-1/\
dem_ban_sao_bo_kiem.py app

    # the baseline before #437, for the "13 before" half of the claim
    mkdir -p /tmp/nen437
    git archive f6c4518 services/api/app | tar -x -C /tmp/nen437
    cd services/api && python3 tests/qa/backend-111300-trang-kien-truc-luat-1/\
dem_ban_sao_bo_kiem.py /tmp/nen437/services/api/app

Exits 1 when the measurement is untrustworthy rather than printing a number:
an empty scope, or a matcher that cannot find the shape in its own positive
control. An empty list must be RED, never a silent "0 copies".
"""

from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys

GATE = pathlib.Path(__file__).resolve().parents[2] / "test_one_money_check.py"

POSITIVE_CONTROL = (
    "def f(value):\n"
    "    if isinstance(value, bool) or not isinstance(value, int):\n"
    "        raise E('x')\n"
)


def load_gate():
    spec = importlib.util.spec_from_file_location("one_money_check", GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def subjects_in(gate, source: str) -> dict[str, set[str]]:
    """Map enclosing function -> set of subject expressions it checks."""
    buckets: dict[str, dict[str, set[str]]] = {}
    gate._collect(ast.parse(source), "<module>", buckets)
    found: dict[str, set[str]] = {}
    for scope, seen in buckets.items():
        hits = (seen["bool"] & seen["int"]) | seen["type_int"]
        if hits:
            found[scope] = hits
    return found


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2

    gate = load_gate()
    root = pathlib.Path(argv[1]).resolve()

    if not root.is_dir():
        print(f"FAIL: {root} is not a directory")
        return 1

    # Positive control: a matcher that cannot see the shape it was built for
    # would print 0 for every tree, and 0 would read as "clean".
    if not subjects_in(gate, POSITIVE_CONTROL):
        print("FAIL: the matcher cannot find the shape in its own control")
        return 1

    files = [p for layer in gate.SCOPE for p in sorted((root / layer).rglob("*.py"))]
    if len(files) <= 10:
        print(f"FAIL: only {len(files)} files under {root}; SCOPE looks wrong")
        return 1

    by_scope = 0
    by_subject = 0
    for path in files:
        found = subjects_in(gate, path.read_text(encoding="utf-8"))
        for scope, hits in sorted(found.items()):
            by_scope += 1
            for subject in sorted(hits):
                by_subject += 1
                print(f"  {path.relative_to(root)}::{scope}({subject})")

    home = root / "domain" / "money.py"
    print()
    print(f"root            : {root}")
    print(f"files scanned   : {len(files)}   (SCOPE = {', '.join(gate.SCOPE)})")
    print(f"unit = scope    : {by_scope}")
    print(f"unit = subject  : {by_subject}   <-- the unit #437 reported")
    print(f"money.py present: {home.exists()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
