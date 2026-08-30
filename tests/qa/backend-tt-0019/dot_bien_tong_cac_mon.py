"""Mutation matrix for the tt-0019 bill-total gate.

Each row edits `ApiService.create_bill`, runs the two files that guard the
rule, and reports which cases died. Rows 1-4 break the property and must go
red; row 5 preserves it and must stay green, so an all-red table cannot be
mistaken for a working gate -- a table where every row is red says the suite
notices *edits*, not that it notices *this rule*.

The row that earns its keep is M2. It leaves the answer correct -- same 422,
same code -- and only moves the check below the write. Every `tests/api` case
stays green, because HTTP cannot see the row that survived; only the postgres
case goes red. That measurement is why
`tests/postgres/test_bill_items_total_matches_lines_postgres.py` exists.

Run it from anywhere:

    MOBILE_TEST_DATABASE_URL='postgresql+psycopg://...' \\
    MOBILE_REQUIRE_POSTGRES_TESTS=1 python3 tests/qa/backend-tt-0019/dot_bien_tong_cac_mon.py

Without those two variables the postgres rows skip rather than run, and M2 --
the only row they cover -- silently reports GREEN. The script refuses to start
in that state rather than print a table that reads like a pass.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

# Anchored on this file rather than on the caller's cwd: the pytest invocation
# below needs `services/api` as its working directory to pick up the
# `pythonpath` in that package's pyproject.toml.
API_ROOT = pathlib.Path(__file__).resolve().parents[3] / "services" / "api"
SERVICE = API_ROOT / "app" / "api" / "service.py"
ORIGINAL = SERVICE.read_text(encoding="utf-8")

if not os.environ.get("MOBILE_TEST_DATABASE_URL"):
    raise SystemExit(
        "MOBILE_TEST_DATABASE_URL is unset, so the postgres rows would skip and "
        "M2 -- the row those rows exist for -- would report GREEN. Refusing to "
        "print a table that cannot tell a passing gate from an absent one."
    )

GUARD = """        lines_total_vnd = sum(item.line_total_vnd for item in request.items)
        if request.items_total_vnd != lines_total_vnd:
            raise ApiProblem(
                422,
                "bill_items_total_mismatch",
                f"Declared items total {request.items_total_vnd} does not match "
                f"the sum of the lines {lines_total_vnd}",
            )
"""

assert ORIGINAL.count(GUARD) == 1, "guard block is not a unique anchor"

WRITE_TAIL = """        except RepositoryConflict as exc:
            raise ApiProblem(409, exc.code, "Bill creation conflicted") from exc
"""
assert ORIGINAL.count(WRITE_TAIL) == 1, "write tail is not a unique anchor"


def removed() -> str:
    """M1 -- no rule at all. The state of `main` before this commit."""
    return ORIGINAL.replace(GUARD, "")


def after_the_write() -> str:
    """M2 -- right answer, wrong moment.

    Still a 422, still the same code, but the bill is already written. This is
    the mutation the postgres file exists for: every `tests/api` case stays
    green because HTTP cannot see the row that survived.
    """
    return ORIGINAL.replace(GUARD, "").replace(WRITE_TAIL, WRITE_TAIL + GUARD)


def one_sided() -> str:
    """M3 -- only refuses a total that is too high."""
    return ORIGINAL.replace(
        "if request.items_total_vnd != lines_total_vnd:",
        "if request.items_total_vnd > lines_total_vnd:",
    )


def wrong_sum() -> str:
    """M4 -- folds surcharges in, so the sum is no longer the lines."""
    return ORIGINAL.replace(
        "lines_total_vnd = sum(item.line_total_vnd for item in request.items)",
        "lines_total_vnd = sum(item.line_total_vnd for item in request.items) + sum(\n"
        "            surcharge.amount_vnd for surcharge in request.surcharges\n"
        "        )",
    )


def reworded() -> str:
    """M5 -- CONTROL. Message reworded, property untouched. Must stay green."""
    return ORIGINAL.replace(
        'f"Declared items total {request.items_total_vnd} does not match "\n'
        '                f"the sum of the lines {lines_total_vnd}",',
        'f"The lines add to {lines_total_vnd}, not to "\n'
        '                f"{request.items_total_vnd}",',
    )


MUTANTS = [
    ("M1 rule removed (= main today)", removed, "RED"),
    ("M2 rule moved below the write", after_the_write, "RED"),
    ("M3 only refuses too-high totals", one_sided, "RED"),
    ("M4 sum includes surcharges", wrong_sum, "RED"),
    ("M5 CONTROL message reworded", reworded, "GREEN"),
]

FILES = [
    "tests/api/test_bill_items_total_matches_lines.py",
    "tests/postgres/test_bill_items_total_matches_lines_postgres.py",
]


def run() -> tuple[int, int, list[str]]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *FILES,
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        cwd=API_ROOT,
    )
    out = proc.stdout
    if "skipped" in out and "MOBILE_TEST_DATABASE_URL" in out:
        raise SystemExit("postgres rows skipped -- see the guard at import time")
    passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", out)) else 0
    failed = int(m.group(1)) if (m := re.search(r"(\d+) failed", out)) else 0
    names = re.findall(r"^FAILED (\S+)", out, re.MULTILINE)
    return passed, failed, names


def main() -> int:
    base_pass, base_fail, _ = run()
    print(f"{'clean':<34} {base_pass:>3} passed  {base_fail:>3} failed")
    print("-" * 78)
    verdicts = []
    try:
        for label, build, expected in MUTANTS:
            mutated = build()
            assert mutated != ORIGINAL, f"{label}: mutation changed nothing"
            SERVICE.write_text(mutated, encoding="utf-8")
            passed, failed, names = run()
            actual = "RED" if failed else "GREEN"
            ok = "ok" if actual == expected else "MISMATCH"
            verdicts.append(actual == expected)
            print(
                f"{label:<34} {passed:>3} passed  {failed:>3} failed   {actual:<5} {ok}"
            )
            for name in names:
                print(f"{'':<34}   - {name.split('::')[-1]}")
    finally:
        SERVICE.write_text(ORIGINAL, encoding="utf-8")
    print("-" * 78)
    print("restored:", SERVICE.read_text(encoding="utf-8") == ORIGINAL)
    return 0 if all(verdicts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
