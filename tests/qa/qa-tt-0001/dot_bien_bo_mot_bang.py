#!/usr/bin/env python3
"""Systematic mutation of the #486 storage gate: remove ONE table at a time.

## The question

`#486` states its own counting unit as a defence:

    "The enumeration here is complete by construction: every column in the
     migrated schema is classified, and the classification is deny by default."

Complete-by-construction holds only while the *read* is complete. Every rule in
the file is of the form "no row satisfies X", and a read that returned fewer
rows satisfies all of them for free. The file knows this and plants a floor:

    assert len(columns) > 200
    assert len(money_named) >= 20

A floor answers "is the read EMPTY". It does not answer "did the read lose one
table". Those are different questions, and the second is the one that actually
happens: `information_schema.columns` is privilege-filtered, and the query
pins `table_schema = current_schema()`, so a table can leave the read without
anybody dropping it.

## What this driver does

For each table in the migrated schema, it edits the gate's own `_columns()`
query to exclude exactly that table, clears the bytecode cache, runs the real
ten cases against a real migrated PostgreSQL, and records whether ANY of them
went red. Then it restores the file.

One table at a time, every table -- not a sampled one. A single chosen table
would only tell you about that table.

## Canaries, because a mutation table of all-green is indistinguishable from a
## driver that never ran the tests

  baseline   unmutated                     -> must be GREEN
  empty      every table excluded          -> must be RED  (the floor works at the extreme)
  no-money   _looks_like_money -> False    -> must be RED  (the money floor is wired)

If the two RED canaries do not go red, every other row in the table is void and
this script says so instead of printing a result.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
GATE = REPO / "services/api/tests/postgres/test_money_columns_are_integer_postgres.py"
API = REPO / "services/api"

# The line the gate filters its schema read on. The mutation is appended here.
ANCHOR = "where table_schema = :schema"


def read_gate() -> str:
    return GATE.read_text(encoding="utf-8")


def write_gate(source: str) -> None:
    GATE.write_text(source, encoding="utf-8")
    # Same-size edits plus a stale .pyc have produced a green mutation table in
    # this repo before. Remove the cache rather than trust mtime granularity.
    for cache in API.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def mutate_exclude(original: str, tables: list[str]) -> str:
    """Drop the named tables out of the gate's schema read."""

    if ANCHOR not in original:
        raise SystemExit(f"anchor not found in {GATE}; refusing to guess")
    names = ", ".join(f"'{t}'" for t in tables)
    return original.replace(
        ANCHOR, f"{ANCHOR}\n                  and table_name not in ({names})", 1
    )


def mutate_no_money(original: str) -> str:
    """Blind the name-side heuristic entirely."""

    pattern = 'return column_name.endswith("_vnd") or "amount" in column_name'
    if pattern not in original:
        raise SystemExit("money heuristic not found; refusing to guess")
    return original.replace(pattern, "return False", 1)


def run_gate(database_url: str) -> tuple[bool, str]:
    """Run the ten real cases. Returns (green, last summary line)."""

    env = dict(os.environ)
    env["MOBILE_TEST_DATABASE_URL"] = database_url
    env["MOBILE_REQUIRE_POSTGRES_TESTS"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/postgres/test_money_columns_are_integer_postgres.py",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=API,
        env=env,
        capture_output=True,
        text=True,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    summary = lines[-1] if lines else "(no output)"
    # A run that collected nothing is not a pass. Guard against a mutation that
    # makes the module fail to import and exits non-zero for the wrong reason.
    collected = re.search(r"(\d+) passed", summary)
    green = (
        proc.returncode == 0 and collected is not None and int(collected.group(1)) == 10
    )
    return green, summary


def schema_tables(database_url: str) -> list[str]:
    """Table list straight from the models, so the driver reads no hand list."""

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.db.models import Base; import json;"
            " print(json.dumps(sorted(Base.metadata.tables)))",
        ],
        cwd=API,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="postgresql+psycopg://...")
    parser.add_argument("--out", default="", help="write the table as JSON here")
    args = parser.parse_args()

    original = read_gate()
    tables = schema_tables(args.url)
    results: list[dict[str, object]] = []

    try:
        # --- canaries first; the whole table is void without them ---------
        write_gate(original)
        base_green, base_sum = run_gate(args.url)
        print(f"canary baseline      : {'GREEN' if base_green else 'RED'}  {base_sum}")

        write_gate(mutate_exclude(original, tables))
        empty_green, empty_sum = run_gate(args.url)
        print(
            f"canary empty-read    : {'GREEN' if empty_green else 'RED'}  {empty_sum}"
        )

        write_gate(mutate_no_money(original))
        nomoney_green, nomoney_sum = run_gate(args.url)
        print(
            f"canary blind-name    : {'GREEN' if nomoney_green else 'RED'}  {nomoney_sum}"
        )

        if not base_green or empty_green or nomoney_green:
            print(
                "\nCANARY FAIL -- baseline must be GREEN and both blinding "
                "mutations RED. The rows below would prove nothing; not running "
                "them."
            )
            return 2

        # --- one table at a time -------------------------------------------
        print(f"\n--- bỏ MỘT bảng khỏi phép đọc, {len(tables)} bảng ---")
        for table in tables:
            write_gate(mutate_exclude(original, [table]))
            green, summary = run_gate(args.url)
            results.append({"table": table, "gate_green": green, "summary": summary})
            print(
                f"  {'KHÔNG THẤY' if green else 'BẮT ĐƯỢC '}  bỏ {table:35s} {summary}"
            )
    finally:
        write_gate(original)

    missed = [r for r in results if r["gate_green"]]
    print(
        f"\n{len(missed)}/{len(results)} bảng có thể biến mất khỏi phép đọc "
        f"mà không ca nào trong 10 ca đỏ."
    )
    if args.out:
        Path(args.out).write_text(
            json.dumps({"results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
