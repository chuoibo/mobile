#!/usr/bin/env python3
"""Which `int(...)` casts on money in the repository actually have a gate?

Background. `#223` added the first case in `test_group_recap_postgres.py` that
can go red when the `int(...)` around a PostgreSQL `SUM` is deleted, and its
description left an open question: the other money casts in
`app/api/repository.py` were said to rest on the author being careful rather
than on a gate. This script answers that question by measurement instead of by
reading, and it is committed so the answer can be re-checked whenever
`repository.py` changes.

Method. For each cast site, delete that one cast -- and only that one -- then
run the whole PostgreSQL layer and record what turns red. One site at a time
matters: deleting two casts at once lets the first assertion fail and hides
whether the second assertion was load-bearing at all. That is not theoretical.
The `expense_count` assertion added by `#223` looks like a Law 1 gate and can
never fail, and a joint mutation of both casts on that line reports a green
gate for it.

A red run is not by itself proof that the site is gated, which is the trap this
script exists to avoid falling into. Deleting the recap cast turns nine cases
red in `test_suggestion_postgres.py` -- a *different* feature, whose failures
name coordinates, logs and place cards and never mention recap money. Somebody
reading that output would go and debug suggestions. So each site declares the
test file that is supposed to own it, and a site only counts as gated when that
file is among the reds. A site whose only reds come from elsewhere is reported
as `chi tinh nang khac do`, and it is a hole: the bug is detectable but not
diagnosable, and the trail points at the wrong feature.

Two outcomes are possible when a mutation survives outright, and they are not
the same finding:

  * a SUM site surviving is a real hole -- `SUM` over a `bigint` comes back
    from psycopg as `Decimal`, so deleting the cast changes observable
    behaviour and nothing noticed;
  * a COUNT site surviving is an equivalent mutant -- PostgreSQL `count()`
    returns `bigint`, which psycopg already hands back as a Python `int`, so
    the cast is a no-op and no gate can exist for it. Writing a test for one
    of these is wasted work, and the test would pass on a broken build for the
    same reason it passes on a good one.

Exit code is 0 when every SUM site is caught by its own owning test file, 1
otherwise. A surviving COUNT site is reported but is not a failure; the script
proves the equivalence against the driver rather than asserting it.

Run from the repository root, with PostgreSQL up:

    MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/<db>' \
        python3 tests/qa/rd-qa-39/ma-tran-cast-tien.py

Use a database of your own. The PostgreSQL layer migrates a fresh schema per
session, but a shared database still collects them.
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "services" / "api"
TARGET = API_ROOT / "app" / "api" / "repository.py"

SUM = "SUM"
COUNT = "COUNT"


@dataclass(frozen=True)
class Site:
    """One `int(...)` cast, and the test file that claims to guard it.

    `old` -> `new` keeps parentheses balanced by turning `int(` into `(`, so
    the mutation is exactly "the cast is gone" rather than "the expression was
    rewritten". `owner` is empty for COUNT sites, where no gate can exist.
    """

    label: str
    kind: str
    old: str
    new: str
    owner: str = ""


SITES = [
    Site(
        "recap.split_total_vnd",
        SUM,
        "int(row.split_total_vnd or 0)",
        "(row.split_total_vnd or 0)",
        "test_group_recap_postgres.py",
    ),
    Site(
        "recap.expense_count",
        COUNT,
        "int(row.expense_count or 0)",
        "(row.expense_count or 0)",
    ),
    Site(
        "recap.memory_count",
        COUNT,
        "int(row.memory_count or 0)",
        "(row.memory_count or 0)",
    ),
    Site(
        "receipts.confirmed",
        SUM,
        "int(confirmed_amount_vnd)",
        "(confirmed_amount_vnd)",
        "test_repository_postgres.py",
    ),
    Site(
        "finance.spend_vnd",
        SUM,
        "spend_vnd = int(",
        "spend_vnd = (",
        "test_person_finance_postgres.py",
    ),
    Site(
        "finance.expense_count",
        COUNT,
        "expense_count = int(",
        "expense_count = (",
    ),
    Site(
        "finance.group_count",
        COUNT,
        "group_count = int(",
        "group_count = (",
    ),
    Site(
        "finance.owed_vnd",
        SUM,
        "owed_vnd = int(",
        "owed_vnd = (",
        "test_person_finance_postgres.py",
    ),
    Site(
        "finance.paid_vnd",
        SUM,
        "paid_vnd = int(",
        "paid_vnd = (",
        "test_person_finance_postgres.py",
    ),
]


def _fail(message: str) -> None:
    print(f"DUNG: {message}", file=sys.stderr)
    raise SystemExit(2)


def _drop_pycache() -> None:
    """Stale bytecode outlives a source restore and reads as a live mutation."""
    for cached in (API_ROOT / "app").rglob("__pycache__"):
        shutil.rmtree(cached, ignore_errors=True)


def _guard_clean_tree() -> None:
    """Refuse to mutate a file that already has uncommitted work in it.

    The restore step writes the original text back. If somebody's unsaved edit
    were the original text, this script would be the thing that deleted it.
    """
    dirty = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--", str(TARGET)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if dirty:
        _fail(
            f"{TARGET.relative_to(REPO_ROOT)} co thay doi chua commit "
            "-- commit hoac stash truoc"
        )


def _check_no_unknown_sum_site(source: str) -> list[str]:
    """Report money `SUM`s that this matrix does not know about.

    A new `func.sum` over an amount column added after this script was written
    would otherwise be silently outside the measurement, and the table would
    still print a clean bill of health.
    """
    known = sum(source.count(site.old) for site in SITES if site.kind is SUM)
    found = len(re.findall(r"func\.sum\(", source))
    if found <= known:
        return []
    return [f"repository.py co {found} cho `func.sum(`, ma tran chi phu {known}"]


def _run_layer(env: dict[str, str]) -> list[str]:
    """Run the PostgreSQL layer, return the test files that went red."""
    run = subprocess.run(
        ["python3", "-m", "pytest", "tests/postgres", "-q", "--tb=no"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    failed = [line for line in run.stdout.splitlines() if line.startswith("FAILED")]
    return [line.split("::")[0].split("/")[-1] for line in failed]


def main() -> int:
    if not os.environ.get("MOBILE_TEST_DATABASE_URL"):
        _fail(
            "can MOBILE_TEST_DATABASE_URL -- tang postgres se skip va bang nay se noi doi"
        )
    _guard_clean_tree()

    original = TARGET.read_text()
    env = dict(os.environ, MOBILE_REQUIRE_POSTGRES_TESTS="1")

    holes = _check_no_unknown_sum_site(original)
    survivors: list[Site] = []

    print(f"{'site':<24} {'loai':<6} {'ket qua':<24} file do")
    print("-" * 96)

    try:
        for site in SITES:
            occurrences = original.count(site.old)
            if occurrences != 1:
                holes.append(
                    f"{site.label}: moc dot bien khong con duy nhat ({occurrences} lan)"
                )
                print(f"{site.label:<24} {site.kind:<6} {'!! moc da troi':<24} -")
                continue

            TARGET.write_text(original.replace(site.old, site.new))
            _drop_pycache()
            red_files = _run_layer(env)
            TARGET.write_text(original)

            shown = ", ".join(sorted(set(red_files))) if red_files else "-"

            if not red_files:
                verdict = "song sot"
                survivors.append(site)
                if site.kind is SUM:
                    holes.append(
                        f"{site.label}: SUM khong ai gac -- Decimal thoat ra, khong test nao do"
                    )
            elif site.owner and site.owner not in red_files:
                # Detectable but not diagnosable: the reds name another feature.
                verdict = "chi tinh nang khac do"
                holes.append(
                    f"{site.label}: khong ca nao trong {site.owner} do "
                    f"-- nguoi sua se di theo {shown}"
                )
            else:
                verdict = f"bat dung cho ({len(red_files)} do)"

            print(f"{site.label:<24} {site.kind:<6} {verdict:<24} {shown}")
    finally:
        TARGET.write_text(original)
        _drop_pycache()

    print()
    if survivors:
        print("Song sot, va vi sao chung khong phai lo hong:")
        for site in survivors:
            print(f"  {site.label:<24} {site.kind} -- xem kieu driver tra ve duoi day")
        print()
        _print_driver_types()

    if holes:
        print("KHONG DAT:")
        for hole in holes:
            print(f"  - {hole}")
        return 1

    print("DAT: moi cho SUM tien deu co mot ca do duoc, trong dung file so huu no.")
    return 0


def _print_driver_types() -> None:
    """Show the driver's own answer, so 'equivalent' is measured, not claimed."""
    try:
        import psycopg
    except ImportError:  # pragma: no cover - psycopg ships with the API deps
        print("  (khong import duoc psycopg de kiem kieu tra ve)")
        return

    url = os.environ["MOBILE_TEST_DATABASE_URL"].replace(
        "postgresql+psycopg://", "postgresql://"
    )
    probes = [
        (
            "coalesce(sum(bigint), 0)",
            "select coalesce(sum(x), 0) from (select 1::bigint as x) t",
        ),
        ("count(col)", "select count(x) from (select 1::bigint as x) t"),
        (
            "count(distinct col)",
            "select count(distinct x) from (select 1::bigint as x) t",
        ),
    ]
    print("  Kieu psycopg thuc su tra ve:")
    with psycopg.connect(url) as connection:
        for label, sql in probes:
            value = connection.execute(sql).fetchone()[0]
            name = type(value).__name__
            note = "can int()" if name == "Decimal" else "da la int -- cast la no-op"
            print(f"    {label:<26} -> {name:<8} {note}")


if __name__ == "__main__":
    raise SystemExit(main())
