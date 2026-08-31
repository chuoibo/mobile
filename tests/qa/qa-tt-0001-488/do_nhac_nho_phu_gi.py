#!/usr/bin/env python3
"""Measure what PR #488's coverage *reminder* can and cannot see.

## What this asks

`test_every_aggregating_method_is_driven` in
`services/api/tests/postgres/test_money_expressions_are_integer_postgres.py`
is the answer PR #488 gives to "a hand-written list cannot know what it is
missing": it walks the AST of two repository modules and requires that every
method building a widening SQL aggregate is named on `MONEY_QUERY_SURFACE`.

The type rule next to it is blind to spelling on purpose -- it reads the type
PostgreSQL reports for each result column, so `text("SUM(...)")` and
`func.sum()` reach it by the same path. The reminder is not: it is built on
names. This harness measures the size of that difference by adding one new
undriven money query at a time, each spelled differently, and recording
whether the file goes red.

A mutant that stays GREEN means: a new money query returning an inexact type
can be added to the repository layer and nothing in this gate says so.

## Why a positive control is the first row

A harness that patches the wrong place, or whose pytest invocation is broken,
prints GREEN for every mutant and reads exactly like "nothing is blind". Row
Y0 adds the spelling the reminder *does* know (`func.sum`) at the same
insertion point as the others. Y0 must be RED. If it is not, every other row
here is void and the harness says so instead of printing a table.

## How to run it

Needs a real PostgreSQL, because the gate under test does:

    scripts/postgres_tier.sh --keep -k money_expressions      # prints the URL

then, from anywhere inside the repository:

    MOBILE_TEST_DATABASE_URL='<the URL it printed>' \
      python3 tests/qa/qa-tt-0001-488/do_nhac_nho_phu_gi.py

Exit 0: the positive control fired and the table below is meaningful.
Exit 2: the harness could not measure and refuses to print a clean table.

## What it does NOT prove

It says nothing about the type rule, which is a different assert and is not
name-based. It does not claim any of these queries exists today -- measured on
this tree, `func.sum`/`avg`/`round` appear only in the two modules the
reminder already scans. What it measures is which future drift arrives
silently.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys


REPO_ROOT = pathlib.Path(
    subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
)
API_ROOT = REPO_ROOT / "services" / "api"
SCANNED_MODULE = pathlib.Path("app/api/repository.py")
UNSCANNED_MODULE = pathlib.Path("app/api/money_reports_qa_probe.py")
GATE = "tests/postgres/test_money_expressions_are_integer_postgres.py"

# Appended to a module the reminder scans. Each entry is one new money query
# that nobody drives; only the spelling differs. The reminder is the thing
# under test, so every body must import cleanly -- a mutant that breaks the
# module goes red as a collection error, which reads like "caught" and is not.
BODIES = {
    "Y0": (
        "func.sum -- cach viet nhac nho CO biet",
        "    return select(func.sum(ReceiptConfirmation.amount_vnd))\n",
    ),
    "Y1": (
        "chia doi bill bang toan tu / 2.0 (khong co Call nao)",
        "    return select(ReceiptConfirmation.amount_vnd / 2.0)\n",
    ),
    "Y2": (
        "SQL viet tay qua text()",
        "    from sqlalchemy import text\n\n"
        '    return text("SELECT sum(amount_vnd)::numeric AS s '
        'FROM receipt_confirmations")\n',
    ),
}

# The one assert the reminder is supposed to fail on. A mutant red for any
# other reason -- an import error, a collection error -- is not evidence the
# reminder saw anything, so the harness reads the reason and not just the code.
REMINDER_TEST = "test_every_aggregating_method_is_driven"


def run_gate() -> tuple[int, str, bool]:
    """Return (exit code, last line, did the reminder assert itself fail)."""

    env = dict(os.environ, MOBILE_REQUIRE_POSTGRES_TESTS="1")
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", GATE, "-q", "-rf"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    stdout = completed.stdout
    tail = [line for line in stdout.splitlines() if line.strip()]
    reminder_failed = f"FAILED {GATE}::{REMINDER_TEST}" in stdout or any(
        line.startswith("FAILED") and REMINDER_TEST in line for line in tail
    )
    return (
        completed.returncode,
        tail[-1][:60] if tail else "(khong co output)",
        (reminder_failed),
    )


def restore() -> None:
    subprocess.run(
        ["git", "checkout", "--", str(SCANNED_MODULE)], cwd=API_ROOT, check=True
    )
    (API_ROOT / UNSCANNED_MODULE).unlink(missing_ok=True)


def dirty_paths() -> list[str]:
    out = subprocess.run(
        ["git", "status", "--porcelain", str(SCANNED_MODULE), str(UNSCANNED_MODULE)],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line.strip()]


def append_method(label: str, body: str) -> None:
    target = API_ROOT / SCANNED_MODULE
    method = (
        f"\n\ndef _qa_probe_{label.lower()}():\n"
        '    """QA mutation probe -- undriven money query, restored by the harness."""\n\n'
        f"{body}"
    )
    with target.open("a", encoding="utf-8") as handle:
        handle.write(method)


def write_unscanned_module() -> None:
    (API_ROOT / UNSCANNED_MODULE).write_text(
        "from sqlalchemy import func, select\n\n"
        "from app.db.models import ReceiptConfirmation\n\n\n"
        "def money_report_statement():\n"
        '    "QA mutation probe -- lives outside REPOSITORY_MODULES."\n'
        "    return select(func.sum(ReceiptConfirmation.amount_vnd))\n",
        encoding="utf-8",
    )


def main() -> int:
    if not os.environ.get("MOBILE_TEST_DATABASE_URL"):
        print("KHONG KIEM DUOC: thieu MOBILE_TEST_DATABASE_URL.")
        return 2
    if dirty_paths():
        print("KHONG KIEM DUOC: file se bi dot bien dang co thay doi chua commit:")
        print("\n".join(dirty_paths()))
        return 2

    base_rc, base_tail, _ = run_gate()
    print(f"M0 khong dot bien (phai XANH){'':>26} rc={base_rc}  {base_tail}")
    if base_rc != 0:
        print("KHONG KIEM DUOC: nen da do truoc khi dot bien.")
        return 2

    rows: list[tuple[str, str, int, str, bool]] = []
    try:
        for label, (what, body) in BODIES.items():
            append_method(label, body)
            rc, tail, by_reminder = run_gate()
            restore()
            rows.append((label, what, rc, tail, by_reminder))

        write_unscanned_module()
        rc, tail, by_reminder = run_gate()
        restore()
        rows.append(
            (
                "Y3",
                "func.sum o module NGOAI hai module duoc quet",
                rc,
                tail,
                by_reminder,
            )
        )
    finally:
        restore()

    print("\n=== them MOT query tien moi, khong ai lai, moi hang mot cach viet ===")
    blind: list[str] = []
    wrong_reason: list[str] = []
    for label, what, rc, tail, by_reminder in rows:
        if rc == 0:
            verdict = "LOT"
            blind.append(f"{label} {what}")
        elif by_reminder:
            verdict = "BAT DUOC (dung nhac nho)"
        else:
            verdict = "DO NHUNG SAI LY DO"
            wrong_reason.append(f"{label} {what}")
        print(f"{label} {what:<52} rc={rc}  {tail:<34} -> {verdict}")

    control = next(row for row in rows if row[0] == "Y0")
    print("\n=== TONG KET ===")
    if wrong_reason:
        print(
            "KHONG KIEM DUOC: cac hang duoi do vi mot ly do KHAC "
            f"{REMINDER_TEST} (thuong la loi cu phap/import cua chinh dot bien), "
            "nen khong hang nao chung minh nhac nho da nhin thay gi:"
        )
        for item in wrong_reason:
            print(f"  - {item}")
        return 2
    if control[2] == 0:
        print(
            "KHONG KIEM DUOC: doi chung duong Y0 (func.sum) LOT. Diem chen sai "
            "hoac lenh pytest hong, nen moi hang khac o bang tren la vo nghia."
        )
        return 2
    print(f"doi chung duong Y0 DO dung o {REMINDER_TEST} -- phep do phan biet duoc.")
    if not blind:
        print("khong cach viet nao lot qua nhac nho.")
    else:
        print(f"{len(blind)} cach viet them duoc mot query tien moi ma cong van XANH:")
        for item in blind:
            print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
