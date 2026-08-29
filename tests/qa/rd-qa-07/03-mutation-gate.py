#!/usr/bin/env python3
"""rd-qa-07 · Which money guarantees on the personal screen are actually defended?

`person_finance_summary` states four money rules in its own comments. Comments
do not fail a build. This gate plants each rule's exact inverse, runs the whole
repo gate, and asks the only question that matters: did anything go red?

Read the two verdicts the opposite way round from usual:

  KILLED   -- good. A test caught the defect. The rule is defended.
  SURVIVED -- bad. Every test in the repo passed with the money rule inverted.

Three of the six mutants below are CONTROLS: they are known to be caught, and
they are here to prove this harness and the suite underneath it are alive. If a
control ever stops being KILLED, the SURVIVED verdicts in the same run mean
nothing -- the environment is broken, not the code. That ordering is the whole
point: rd-qa-06 spent a run chasing a finding that was purely the harness's
fault, and imp-detect on this repo has returned `[] + exit 0` for want of a
browser. A detector is not trusted until it has been seen to react.

Restores from a /tmp copy, never `git checkout` -- checkout restores to HEAD
and would silently destroy uncommitted work in the same file.

Run from the repo root, with PostgreSQL up:

    docker compose up -d postgres
    python3 tests/qa/rd-qa-07/03-mutation-gate.py

Exits non-zero while any non-control mutant survives. Today that is 3.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "services" / "api"
TARGET = API / "app" / "api" / "repository.py"
BACKUP = Path("/tmp/rd-qa-07-repository.py.bak")

DB_URL = os.environ.get(
    "MOBILE_TEST_DATABASE_URL",
    "postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile",
)

# (name, is_control, old, new). Anchors are matched inside the SqlAlchemy
# implementation only -- the Protocol above it repeats some expressions.
MUTANTS = [
    (
        "M1-oldest-version-wins",
        True,
        'func.max(ExpenseVersion.version_number).label("version_number"),',
        'func.min(ExpenseVersion.version_number).label("version_number"),',
    ),
    (
        "M2-payer-owes-their-own-share",
        True,
        "current_allocations.c.paid_by_id != person_id",
        "current_allocations.c.paid_by_id != None  # noqa: E711",
    ),
    (
        "M6-settled-stops-adding-back-up",
        True,
        "settled_vnd=spend_vnd - outstanding_vnd,",
        "settled_vnd=paid_vnd,",
    ),
    (
        # The realistic bad fix. rd-qa-06 reported that a guest who presses
        # "Tôi đã chuyển" still shows as "chưa gửi" on the collection board.
        # The tempting repair is to let the report count -- which would let
        # anybody clear their own debt by pressing a button.
        "M3-a-self-report-settles-the-debt",
        False,
        """                .where(CollectionObligation.sender_id == person_id)
            )
            or 0
        )
        # Clamped:""",
        """                .where(CollectionObligation.sender_id == person_id)
            )
            or 0
        ) + int(
            self.session.scalar(
                select(func.coalesce(func.sum(PaymentReport.amount_vnd), 0))
                .select_from(PaymentReport)
                .join(
                    CollectionObligation,
                    CollectionObligation.id == PaymentReport.obligation_id,
                )
                .where(CollectionObligation.sender_id == person_id)
            )
            or 0
        )
        # Clamped:""",
    ),
    (
        "M4-over-confirmation-becomes-negative-debt",
        False,
        "outstanding_vnd = max(0, owed_vnd - paid_vnd)",
        "outstanding_vnd = owed_vnd - paid_vnd",
    ),
    (
        "M5-decimal-escapes-as-money",
        False,
        """        spend_vnd = int(
            self.session.scalar(
                select(func.coalesce(func.sum(current_allocations.c.amount_vnd), 0))
            )
            or 0
        )""",
        """        spend_vnd = (
            self.session.scalar(
                select(func.coalesce(func.sum(current_allocations.c.amount_vnd), 0))
            )
            or 0
        )""",
    ),
]

ENV = {
    **os.environ,
    "MOBILE_TEST_DATABASE_URL": DB_URL,
    "MOBILE_REQUIRE_POSTGRES_TESTS": "1",
}


def gate() -> tuple[int, list[str], str]:
    """The whole repo gate, with the live PostgreSQL layer required."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", str(ROOT / "tests"),
         "-q", "--no-header", "-p", "no:cacheprovider"],
        capture_output=True, text=True, env=ENV, cwd=API,
    )
    out = proc.stdout + proc.stderr
    red = sorted({
        ln.split("::")[-1].split()[0]
        for ln in out.splitlines() if ln.startswith("FAILED")
    })
    tail = [ln for ln in out.splitlines() if " passed" in ln or " failed" in ln]
    return proc.returncode, red, (tail[-1].strip() if tail else "?")


def main() -> int:
    original = TARGET.read_text()
    shutil.copy(TARGET, BACKUP)
    anchor = original.rindex("    def person_finance_summary(")
    head, body = original[:anchor], original[anchor:]

    code, _, tail = gate()
    print(f"BASELINE  exit={code}  {tail}\n")
    if code != 0:
        print("baseline is RED -- every verdict below would be noise. Aborting.")
        shutil.copy(BACKUP, TARGET)
        return 2

    survived, controls_ok = [], True
    try:
        for name, is_control, old, new in MUTANTS:
            tag = "control" if is_control else "       "
            if body.count(old) != 1:
                print(f"{tag} {name:44s} ANCHOR-DRIFT ({body.count(old)}x) -- code moved, fix this gate")
                controls_ok = False
                continue
            TARGET.write_text(head + body.replace(old, new, 1))
            code, red, tail = gate()
            shutil.copy(BACKUP, TARGET)
            verdict = "KILLED  " if code != 0 else "SURVIVED"
            print(f"{tag} {name:44s} {verdict}  {tail}")
            if red:
                print(f"{'':53s}red: {', '.join(red[:4])}")
            if is_control and code == 0:
                controls_ok = False
            if not is_control and code == 0:
                survived.append(name)
    finally:
        shutil.copy(BACKUP, TARGET)
        assert TARGET.read_text() == original, "RESTORE FAILED -- working tree is dirty"

    print("\n" + "=" * 70)
    if not controls_ok:
        print("CONTROLS DID NOT ALL DIE -- this run proves nothing. Fix the harness first.")
        return 2
    print("controls all KILLED -- the suite and this harness are both alive.")
    if survived:
        print(f"\n{len(survived)} money rule(s) defended by NOTHING:")
        for s in survived:
            print(f"  - {s}")
        return 1
    print("no survivors: every money rule on this screen is defended by a test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
