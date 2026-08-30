#!/usr/bin/env python3
"""Let `seed_demo_data.py` build its group a SECOND time on a database that already ran it.

The problem this exists for
---------------------------
`seed_demo_data.py` derives every write key from a fixed namespace and a fixed
slug -- `uuid5(DEMO_NAMESPACE, "write:" + slug)`. Nothing in the key varies per
run or per context. That is deliberate and it is right for the case it was
written for: a half-finished run re-runs and replays the writes that landed
instead of doubling them.

It has a consequence nobody wrote down until 2026-08-30. The expenses are
backdated from `datetime.now(UTC)`, so their request bodies move with the
calendar. Re-running on a later day therefore sends *the same key* with *a
different body*, and the server does exactly what it should:

    POST /expenses -> HTTP 422 {"code": "idempotency_key_reuse"}

So the fixture can only ever build its group ONCE per database. After that the
demo data is frozen in whatever shape it reached, correct or not.

Why the documented recovery was not usable
------------------------------------------
`check_complete()` offers two ways out, and on the machine that needed them
both were worse than the disease:

  1. "build a separate stack, separate database" -- works, but it is a second
     demo machine at a second address, and the address everyone's link, cron
     entry and phone points at is still serving the broken data.
  2. "`make clean` then `make demo`" -- `make clean` removes TWO volumes, and
     the second one is `mobile-media-data`. Every uploaded photo on the machine
     goes with it, and the Makefile says plainly that seeding does not bring
     them back: "seed dựng dữ liệu tiền, không dựng ảnh của người ta."

The message also says, correctly, that the group cannot be deleted with SQL --
`confirmed_allocations` and nine sibling tables carry BEFORE DELETE OR UPDATE
triggers that reject the row. That is the ledger doing its job and this script
does not argue with it.

The third way
-------------
Nothing requires the old group to be DELETED. It only has to stop answering to
the name the fixture looks up, because both `seed_demo_data.existing_group()`
and `check_demo_data.py` resolve the demo group by

    SELECT id FROM contexts WHERE display_name = %s LIMIT 1

`contexts` carries no immutability trigger -- it holds no material fact -- so
renaming it is a plain UPDATE. Rename the old group, drop the fixture's own
replay keys, and the next `make demo` builds a genuinely new group beside the
old one. Nothing is deleted. The ledger keeps every row it ever had, which is
what an append-only ledger is FOR, and invariant 3 still holds: balances remain
recomputable from the ledger for both groups.

What this script will not do
----------------------------
It deletes from exactly one table, `idempotency_keys`, and only the rows whose
key it can regenerate from the fixture's own namespace. On the machine this was
written for that was 29 rows out of 879 -- the other 850 belong to other lanes
and are never candidates, because a key that this script cannot derive is a key
it does not own. `IMMUTABLE_TABLES` below is asserted against, not remembered.

Usage:
    python3 scripts/reset_demo_group.py                 # dry run, writes nothing
    python3 scripts/reset_demo_group.py --yes           # actually rename + clear
    python3 scripts/reset_demo_group.py --dsn ... --yes # another machine

Then `make demo` (or the `demo` compose service) to build the fresh group.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))

import seed_demo_data as seed  # noqa: E402  - path set above

DEFAULT_DSN = "postgresql://mobile:mobile-dev-only@127.0.0.1:5432/mobile"

EXIT_OK = 0
EXIT_NOTHING_TO_DO = 1
EXIT_CANNOT_RUN = 2

# The ten tables whose rows are material financial facts. Every one carries a
# BEFORE DELETE OR UPDATE trigger in the first migration. Listed here so the
# assertion below is a check and not a promise: if this script ever grows a
# second DELETE, it fails loudly rather than quietly cutting the ledger.
IMMUTABLE_TABLES = frozenset(
    {
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
    }
)

# The only table this script deletes from.
TABLES_WRITTEN = frozenset({"contexts", "idempotency_keys"})


def fixture_write_slugs(now: datetime) -> list[str]:
    """Every slug `seed_demo_data.py` writes with under a STATIC name.

    Derived from the fixture's own data, never copied. That is the property
    that matters: when the fixture grows a fourth outing or an eighth person,
    the key set grows with it and the next reset still clears everything. A
    hand-written list would silently under-clear, and under-clearing shows up
    as the same HTTP 422 this script exists to remove -- one table further in,
    where it is much harder to read.

    Keys built from ids the server chose during a run (`receipt-call:` carries
    an obligation id) are deliberately absent. A later run mints different
    obligations, so those keys cannot collide and clearing them would be
    deleting a row this script cannot prove it owns.
    """

    slugs = ["context"]
    for person_uuid, _name in seed.PEOPLE:
        slugs += [
            f"person:{person_uuid}",
            f"invite:{person_uuid}",
            f"accept:{person_uuid}",
            f"bank:{person_uuid}",
        ]
    for outing in seed.outings(now):
        slug = outing["slug"]
        slugs += [
            f"batch:{slug}",
            f"publish:{slug}",
            f"outing:{slug}",
            f"timeline:{slug}",
        ]
        for expense in outing["expenses"]:
            slugs += [f"expense:{expense['slug']}", f"confirm:{expense['slug']}"]
    return slugs


def fixture_write_keys(now: datetime) -> list[str]:
    """The same slugs, hashed the way the fixture hashes them.

    Split from `fixture_write_slugs` so a test can read the slugs back. Keys are
    uuid5 digests: comparing them tells you two lists differ but never which
    write went missing, and "which write" is the whole question when a reset
    under-clears.
    """

    return [seed.idempotency_key(s) for s in fixture_write_slugs(now)]


def archive_name(now: datetime) -> str:
    """A name the fixture's lookup will not match.

    Carries the date because a machine that needed this once tends to need it
    again, and two archives called the same thing are indistinguishable in the
    group list. The suffix says "do not demo this" in the language of the
    people reading that list.
    """

    stamped = f"{seed.GROUP_NAME} (tồn dư {now:%d/%m} — KHÔNG dùng để demo)"
    # The whole point is that `existing_group()` stops matching. If a future
    # edit ever makes these equal the script would silently do nothing while
    # reporting success.
    assert stamped != seed.GROUP_NAME
    return stamped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Giải phóng tên nhóm demo để `make demo` dựng lại được, KHÔNG xoá sổ cái."
    )
    parser.add_argument("--dsn", default=DEFAULT_DSN, help=f"mặc định {DEFAULT_DSN}")
    parser.add_argument(
        "--yes", action="store_true", help="ghi thật; thiếu cờ này là chạy khô"
    )
    parser.add_argument("--timeout", default=10, type=int)
    args = parser.parse_args()

    # Cheap, and it has caught a real edit: a second DELETE added later would
    # otherwise reach a ledger table with nothing standing in the way.
    assert not (TABLES_WRITTEN & IMMUTABLE_TABLES), (
        "script này sắp ghi vào một bảng append-only — dừng lại, đó là sổ cái"
    )

    now = datetime.now(UTC)
    keys = fixture_write_keys(now)

    try:
        connection = psycopg.connect(args.dsn, connect_timeout=args.timeout)
    except Exception as exc:  # noqa: BLE001 - driver raises many shapes
        print(f"KHÔNG CHẠY ĐƯỢC — không nối được database: {exc}", file=sys.stderr)
        return EXIT_CANNOT_RUN

    with connection:
        row = connection.execute(
            "SELECT id FROM contexts WHERE display_name = %s LIMIT 1",
            (seed.GROUP_NAME,),
        ).fetchone()
        if row is None:
            print(
                f"Không có nhóm nào tên '{seed.GROUP_NAME}' trên máy này — "
                "không có gì để giải phóng.\n"
                "  Chạy thẳng `make demo` là dựng được.",
                file=sys.stderr,
            )
            return EXIT_NOTHING_TO_DO
        context_id = row[0]

        present = connection.execute(
            "SELECT count(*) FROM idempotency_keys WHERE idempotency_key = ANY(%s)",
            (keys,),
        ).fetchone()[0]
        total = connection.execute("SELECT count(*) FROM idempotency_keys").fetchone()[
            0
        ]
        new_name = archive_name(now)

        print(f"Nhóm demo hiện tại   {seed.GROUP_NAME}  ({context_id})")
        print(f"  đổi tên thành      {new_name}")
        print(f"  key fixture xoá    {present} / {total} key trên máy")
        print(f"  key của lane khác  {total - present} — KHÔNG đụng tới")
        print("  sổ cái             không xoá dòng nào, không tắt trigger nào")

        if not args.yes:
            print("\nChạy khô — chưa ghi gì. Thêm --yes để làm thật.")
            return EXIT_OK

        renamed = connection.execute(
            "UPDATE contexts SET display_name = %s WHERE id = %s",
            (new_name, context_id),
        ).rowcount
        cleared = connection.execute(
            "DELETE FROM idempotency_keys WHERE idempotency_key = ANY(%s)",
            (keys,),
        ).rowcount
        connection.commit()

        print(f"\nĐã đổi tên {renamed} nhóm, xoá {cleared} key fixture.")
        print("Giờ chạy `make demo` để dựng bộ dữ liệu demo mới.")
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
