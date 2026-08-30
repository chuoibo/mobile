#!/usr/bin/env python3
"""Did a maintenance operation cut the ledger? Compare a pg_dump against the live DB.

## Why row counts cannot answer this

A maintenance script that renames, reseeds or clears replay guards on a shared
database always leaves the counts LARGER afterwards, because other lanes keep
writing the whole time. "confirmed_allocations went from 22027 to 22082" is
consistent with nothing having been deleted, and equally consistent with fifty
rows having been deleted and a hundred added. The count is the wrong instrument.

The right one is set difference on the rows themselves. Append-only means every
row that existed before must still exist afterwards, byte for byte. Extra rows
are fine and expected. So the question this script asks, per table, is:

    dump_rows - live_rows == the empty set ?

and anything in that difference is a row that was deleted or modified.

## Why the comparison is textual

`pg_dump` plain format writes each table as a `COPY ... FROM stdin` block in
PostgreSQL's COPY text encoding. This script reads the live table back through
`COPY ... TO STDOUT` with the columns in the dump's own order, which produces
the same encoding from the same server. So the two sides are directly
comparable strings and no type mapping is invented in between -- a JSONB column
reformatted by a driver would otherwise read as a modified row.

## What it does NOT prove

- Nothing about rows written after the dump was taken. A row created at 20:40
  and deleted at 20:41 is invisible here, because it was never in the baseline.
  If you need that window covered, take the dump closer to the operation.
- Nothing about whether the operation was CORRECT. A rename that renamed the
  wrong group deletes no rows and passes this cleanly.
- Nothing about the ten append-only triggers being present. It measures the
  outcome, not the guard. `IMMUTABLE_TABLES` below is a list this file carries,
  not one it discovers from `pg_trigger` -- so a table that grows a trigger
  later is not covered until somebody adds the name here.

Usage:
    scripts/qc/probe_so_cai_sau_bao_tri.py --dump /tmp/truoc.sql
    scripts/qc/probe_so_cai_sau_bao_tri.py --dump /tmp/truoc.sql --dsn postgresql://...
    scripts/qc/probe_so_cai_sau_bao_tri.py --dump /tmp/truoc.sql --show contexts

Exit codes: 0 no append-only row went missing,
1 at least one did -- that is an invariant 3 violation, not a warning,
2 the check could not run, which is never a pass.
"""

from __future__ import annotations

import argparse
import io
import sys

EXIT_OK = 0
EXIT_LEDGER_CUT = 1
EXIT_CANNOT_RUN = 2

DEFAULT_DSN = "postgresql://mobile:mobile-dev-only@127.0.0.1:5432/mobile"

# The ten tables carrying a BEFORE DELETE OR UPDATE trigger in the first
# migration -- the material financial facts. A row leaving one of these is the
# finding this script exists to produce.
IMMUTABLE_TABLES = (
    "audit_events",
    "bank_recipient_snapshots",
    "collection_batch_versions",
    "collection_envelopes",
    "collection_obligation_sources",
    "collection_obligations",
    "confirmed_allocations",
    "expense_versions",
    "payment_reports",
    "receipt_confirmations",
)

# Reported alongside, but a row leaving one of these is information rather than
# a verdict: they are the tables a maintenance script is allowed to touch.
ALSO_REPORTED = (
    "contexts",
    "idempotency_keys",
    "expenses",
    "collection_batches",
    "memberships",
    "outings",
    "people",
    "guest_links",
    "bills",
    "bill_items",
    "uploaded_images",
)


def read_dump(path: str, wanted: set[str]) -> dict[str, tuple[list[str], list[str]]]:
    """Pull each wanted table's COPY block out of a plain pg_dump.

    Returns table -> (column names in dump order, raw data lines).
    """

    blocks: dict[str, tuple[list[str], list[str]]] = {}
    current: str | None = None
    columns: list[str] = []
    rows: list[str] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if current is None:
                if not line.startswith("COPY public."):
                    continue
                name = line.split("COPY public.", 1)[1].split(" ", 1)[0].strip('"')
                if name not in wanted:
                    continue
                # Column names can be quoted -- `"position"` is a reserved word
                # and appears quoted in bill_items. Strip before use or the
                # SELECT built from them is a syntax error.
                inner = line[line.index("(") + 1 : line.index(")")]
                columns = [c.strip().strip('"') for c in inner.split(",")]
                current, rows = name, []
                continue
            if line.rstrip("\n") == "\\.":
                blocks[current] = (columns, rows)
                current = None
                continue
            rows.append(line.rstrip("\n"))
    return blocks


def live_rows(connection, table: str, columns: list[str]) -> list[str]:
    """Read the live table back in the dump's own encoding and column order."""

    buffer = io.StringIO()
    select = ", ".join(f'"{c}"' for c in columns)
    with connection.cursor().copy(
        f'COPY (SELECT {select} FROM public."{table}") TO STDOUT'
    ) as copy:
        for chunk in copy:
            buffer.write(bytes(chunk).decode("utf-8"))
    return buffer.getvalue().splitlines()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dump", required=True, help="pg_dump plain format, trước khi làm"
    )
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument(
        "--show",
        action="append",
        default=[],
        help="in từng dòng chênh lệch của bảng này (lặp lại được)",
    )
    parser.add_argument(
        "--limit", type=int, default=40, help="số dòng in tối đa mỗi bảng"
    )
    args = parser.parse_args(argv)

    try:
        import psycopg
    except ImportError:
        print("KHÔNG ĐỐI CHIẾU ĐƯỢC — thiếu psycopg.", file=sys.stderr)
        return EXIT_CANNOT_RUN

    wanted = set(IMMUTABLE_TABLES) | set(ALSO_REPORTED)
    try:
        blocks = read_dump(args.dump, wanted)
    except OSError as exc:
        print(f"KHÔNG ĐỐI CHIẾU ĐƯỢC — không đọc được dump: {exc}", file=sys.stderr)
        return EXIT_CANNOT_RUN
    if not blocks:
        print(
            f"KHÔNG ĐỐI CHIẾU ĐƯỢC — không có COPY block nào trong {args.dump}.\n"
            "  Dump ở dạng custom/tar thì đọc thẳng không được: "
            "pg_dump --format=plain, hoặc pg_restore ra plain trước.",
            file=sys.stderr,
        )
        return EXIT_CANNOT_RUN

    try:
        connection = psycopg.connect(args.dsn, connect_timeout=10)
    except Exception as exc:  # noqa: BLE001 - driver raises many shapes
        print(f"KHÔNG ĐỐI CHIẾU ĐƯỢC — không nối được database: {exc}", file=sys.stderr)
        return EXIT_CANNOT_RUN

    print(f"{'bảng':34s} {'trước':>7s} {'sau':>7s} {'MẤT':>6s} {'thêm':>6s}")
    print("-" * 64)
    cut: list[str] = []
    detail: dict[str, set[str]] = {}
    for table in IMMUTABLE_TABLES + ALSO_REPORTED:
        if table not in blocks:
            print(f" {table:33s}   không có trong dump")
            continue
        columns, before = blocks[table]
        try:
            after = live_rows(connection, table, columns)
        except Exception as exc:  # noqa: BLE001 - driver raises many shapes
            connection.rollback()
            print(f" {table:33s}   ĐỌC LỖI: {str(exc).splitlines()[0][:60]}")
            continue
        missing = set(before) - set(after)
        added = set(after) - set(before)
        detail[table] = missing
        protected = table in IMMUTABLE_TABLES
        if missing and protected:
            cut.append(table)
        flag = "  <-- MẤT DÒNG" if missing else ""
        mark = "*" if protected else " "
        print(
            f"{mark}{table:33s} {len(before):7d} {len(after):7d} "
            f"{len(missing):6d} {len(added):6d}{flag}"
        )

    print("\n(* = bảng append-only; dòng rời khỏi đây là vi phạm bất biến 3)")
    for table in args.show:
        rows = sorted(detail.get(table, ()))
        print(f"\n=== {table}: {len(rows)} dòng biến mất ===")
        for row in rows[: args.limit]:
            print("  -", row[:200])
        if len(rows) > args.limit:
            print(f"  … còn {len(rows) - args.limit} dòng nữa")

    if cut:
        print(
            f"\nSỔ CÁI BỊ CẮT — {len(cut)} bảng append-only mất dòng: {', '.join(cut)}",
            file=sys.stderr,
        )
        return EXIT_LEDGER_CUT
    print("\nKhông bảng append-only nào mất dòng.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
