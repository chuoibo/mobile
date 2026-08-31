#!/usr/bin/env python3
"""Probe: what does PostgreSQL actually do with a non-int bound to a money column?

Measured, not assumed. The claim under test is the one
`test_money_columns_are_integer_postgres.py` makes in its own docstring: a
`bigint` money column is NOT a barrier, because a float is rounded and stored
with nothing raised.

This is deliberately standalone -- no pytest, no fixtures, no repository -- so
the numbers quoted in PR #495 can be reproduced by one pasted command against
any PostgreSQL. It creates its own throwaway table and drops it again.

    MOBILE_TEST_DATABASE_URL='postgresql+psycopg://...' \
      python3 tests/qa/backend-tt-0004-ghi-tien/probe_ghi_tien_khong_nguyen.py

Exit codes: 0 = probe ran, 2 = could not measure (never a silent pass).
"""

from __future__ import annotations

import os
import sys
import uuid
from decimal import Decimal

try:
    from sqlalchemy import BigInteger, Column, MetaData, Table, create_engine, select
except ImportError as exc:  # pragma: no cover - environment problem, not a result
    print(f"KHONG KIEM DUOC: thieu sqlalchemy ({exc})")
    raise SystemExit(2) from exc

CANDIDATES: list[tuple[str, object]] = [
    ("int   300", 300),
    ("float 300.5", 300.5),
    ("float 300.4", 300.4),
    ("float 300.0", 300.0),
    ("Decimal 300.5", Decimal("300.5")),
    ("Decimal 300", Decimal("300")),
    ("bool  True", True),
    ("str   '300'", "300"),
]


def main() -> int:
    url = os.environ.get("MOBILE_TEST_DATABASE_URL")
    if not url:
        print("KHONG KIEM DUOC: chua dat MOBILE_TEST_DATABASE_URL")
        return 2

    engine = create_engine(url)
    metadata = MetaData()
    table = Table(
        "probe_money_" + uuid.uuid4().hex[:8],
        metadata,
        Column("amount_vnd", BigInteger, nullable=False),
    )

    try:
        metadata.create_all(engine)
    except Exception as exc:  # noqa: BLE001 - a probe reports, it never repairs
        print(f"KHONG KIEM DUOC: khong tao duoc bang thu ({exc})")
        return 2

    with engine.connect() as connection:
        version = connection.exec_driver_sql("show server_version").scalar()
    print(f"PostgreSQL {version} -- cot bigint amount_vnd\n")

    refused = stored_ok = distorted = 0
    try:
        for label, value in CANDIDATES:
            try:
                with engine.begin() as connection:
                    connection.execute(table.insert().values(amount_vnd=value))
            except Exception as exc:  # noqa: BLE001 - the refusal is the result
                refused += 1
                print(f"{label:16} -> REFUSED  {type(exc).__name__}")
                continue
            with engine.begin() as connection:
                stored = connection.execute(select(table.c.amount_vnd)).all()[-1][0]
            if stored == value:
                stored_ok += 1
                print(f"{label:16} -> STORED {stored!r} ({type(stored).__name__})")
            else:
                distorted += 1
                print(
                    f"{label:16} -> STORED {stored!r} ({type(stored).__name__})"
                    "   <-- DOI SO, khong mot tin hieu nao"
                )
    finally:
        metadata.drop_all(engine)

    print(
        f"\ntong ket: {len(CANDIDATES)} ung vien | {refused} bi tu choi | "
        f"{stored_ok} luu dung | {distorted} BI DOI SO"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
