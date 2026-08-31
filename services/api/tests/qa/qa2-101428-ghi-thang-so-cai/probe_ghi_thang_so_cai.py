"""Can a non-int money value land in the DB without passing ``allocate()``?

#450 closed ``allocate()`` to float/bool.  ``allocate()`` is the door of the
SPLIT, not the door of the INSERT.  The scenario worth ruling out is worse than
a float passing through: a float sitting ALREADY in the ledger, put there by a
seed, a data migration, a fixture or a direct-write route -- because the four
sources that read straight from a dataclass would then hand it to ``allocate()``,
which now refuses, and the row can never be split again.

This probe measures four things against a real migrated PostgreSQL schema:

  PART 1  what SQL type every money column actually is (not what it is called)
  PART 2  positive control -- can this probe SEE a non-int in the database at
          all?  A probe that reports "everything came back int" while being
          incapable of reporting anything else is a broken instrument.
  PART 3  write 300.5 / 300.4 / True straight down each money column the way a
          seed or fixture would, then read back what landed
  PART 4  hand what landed to ``allocate()`` -- refused (stuck row) or accepted
          (silently different money)?

Run:
  MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile' \
    python3 tests/qa/qa2-101428-ghi-thang-so-cai/probe_ghi_thang_so_cai.py
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

API_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(API_ROOT))

from app.db.models import (  # noqa: E402
    Bill,
    Context,
    Expense,
    ExpenseItem,
    ExpenseVersion,
    Person,
    VerificationScope,
)
from app.domain.allocator import allocate  # noqa: E402
from app.domain.contract import AllocationError  # noqa: E402

SCHEMA = f"qa2_ghithang_{uuid.uuid4().hex[:10]}"

# Fixed, never `datetime.now()`: a probe that reports a different number on a
# rerun cannot be used as evidence by anyone else.
OCCURRED_AT = datetime(2026, 8, 31, 3, 0, tzinfo=UTC)

# The three shapes #450 named. 300.4 is here on purpose: if BIGINT rounds
# rather than refuses, 300.4 and 300.5 land on DIFFERENT integers, which is the
# difference between "harmless" and "the stored number is not the number sent".
CANDIDATES = [
    ("float .5", 300.5),
    ("float .4", 300.4),
    ("float .0", 300.0),
    ("bool True", True),
    ("int (base)", 300),
]


def _url():
    raw = os.environ.get("MOBILE_TEST_DATABASE_URL")
    if raw is None:
        print("SKIP-NOT-GREEN: MOBILE_TEST_DATABASE_URL unset", file=sys.stderr)
        raise SystemExit(2)
    url = make_url(raw)
    if url.get_backend_name() != "postgresql":
        raise SystemExit("this probe refuses a non-PostgreSQL URL")
    return url


def _migrate(url) -> None:
    admin = create_engine(url, future=True)
    with admin.begin() as conn:
        conn.execute(CreateSchema(SCHEMA))
    admin.dispose()
    scoped = url.update_query_dict({"options": f"-csearch_path={SCHEMA}"}, append=False)
    # env.py reads MOBILE_DATABASE_URL. `-x sqlalchemy_url` is ignored by this
    # env.py, and `set_main_option` chokes on the %-escape in the search_path
    # option, so this is the only door that actually points Alembic at the
    # generated schema. Verified below rather than assumed.
    previous = os.environ.get("MOBILE_DATABASE_URL")
    os.environ["MOBILE_DATABASE_URL"] = scoped.render_as_string(hide_password=False)
    try:
        command.upgrade(Config(str(API_ROOT / "alembic.ini")), "head")
    finally:
        if previous is None:
            os.environ.pop("MOBILE_DATABASE_URL", None)
        else:
            os.environ["MOBILE_DATABASE_URL"] = previous

    check = create_engine(scoped, future=True)
    with check.connect() as conn:
        current = conn.scalar(text("select current_schema()"))
        found = conn.scalar(text("select to_regclass('expense_versions')"))
    check.dispose()
    if current != SCHEMA or found is None:
        raise SystemExit(
            f"migrated into the wrong place: current_schema={current!r} "
            f"expected {SCHEMA!r}, to_regclass('expense_versions')={found!r}"
        )


def _drop(url) -> None:
    admin = create_engine(url, future=True)
    with admin.begin() as conn:
        conn.execute(DropSchema(SCHEMA, cascade=True))
    admin.dispose()


def part1(engine) -> list[tuple[str, str, str]]:
    print("=" * 78)
    print("PART 1 -- what SQL type is every money column, really?")
    print("=" * 78)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name, column_name, data_type "
                "FROM information_schema.columns "
                "WHERE table_schema = :s AND column_name LIKE '%%_vnd' "
                "ORDER BY table_name, column_name"
            ),
            {"s": SCHEMA},
        ).all()
        jsonb = conn.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = :s AND data_type = 'jsonb' "
                "ORDER BY table_name, column_name"
            ),
            {"s": SCHEMA},
        ).all()
    for t, c, d in rows:
        print(f"  {t:32s} {c:24s} {d}")
    kinds = sorted({d for _, _, d in rows})
    print(f"\n  money columns   : {len(rows)}")
    print(f"  distinct types  : {kinds}")
    print(f"  jsonb columns   : {len(jsonb)} -> {[f'{t}.{c}' for t, c in jsonb]}")
    print(
        "\n  READ THIS: a jsonb column has NO numeric type at all. If a money\n"
        "  number ever lives inside one, PostgreSQL will not coerce it and a\n"
        "  float stays a float forever. Part 2 uses that as the control.\n"
    )
    return [(t, c, d) for t, c, d in rows]


def part2(engine) -> bool:
    print("=" * 78)
    print("PART 2 -- positive control: can this probe SEE a non-int in the DB?")
    print("=" * 78)
    aid = uuid.uuid4()
    with Session(engine) as s:
        s.execute(
            text(
                "INSERT INTO audit_events "
                "(id, event_type, aggregate_type, aggregate_id, event_data) "
                "VALUES (:i, 'qa2_probe', 'probe', :a, "
                "'{\"amount_vnd\": 300.5}'::jsonb)"
            ),
            {"i": uuid.uuid4(), "a": aid},
        )
        s.commit()
        got = s.execute(
            text("SELECT event_data FROM audit_events WHERE aggregate_id = :a"),
            {"a": aid},
        ).scalar_one()
    value = got["amount_vnd"]
    ok = isinstance(value, float) and value == 300.5
    print("  wrote  jsonb  amount_vnd = 300.5")
    print(f"  read   back   {value!r}  (python type {type(value).__name__})")
    print(
        f"  CONTROL {'PASSES' if ok else 'FAILS'}: the probe "
        f"{'can' if ok else 'CANNOT'} distinguish a float from an int in the DB."
    )
    if not ok:
        print("  -> every 'landed as int' below would be uninterpretable. STOP.")
    print()
    return ok


def _seed_expense(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    person = Person(display_name="QA2 probe")
    session.add(person)
    session.flush()
    ctx = Context(display_name="QA2 probe group", created_by_id=person.id)
    session.add(ctx)
    session.flush()
    expense = Expense(context_id=ctx.id)
    session.add(expense)
    session.flush()
    return expense.id, person.id


def part3(engine) -> list[dict]:
    print("=" * 78)
    print("PART 3 -- write straight down the ledger, the way a seed/fixture does")
    print("=" * 78)
    print("  Door used: SQLAlchemy ORM construct + commit. No HTTP, no pydantic,")
    print("  no allocate(). This is exactly what tests/postgres fixtures, a data")
    print("  migration and a hand-run patch script all use.\n")
    results: list[dict] = []
    for label, candidate in CANDIDATES:
        with Session(engine) as s:
            expense_id, person_id = _seed_expense(s)
            row = {
                "label": label,
                "sent": candidate,
                "sent_type": type(candidate).__name__,
            }
            try:
                version = ExpenseVersion(
                    expense_id=expense_id,
                    version_number=1,
                    description="qa2 probe",
                    recorded_by_id=person_id,
                    paid_by_id=person_id,
                    verification_scope=VerificationScope.TOTALS_ONLY,
                    occurred_at=OCCURRED_AT,
                    subtotal_amount_vnd=candidate,
                    total_amount_vnd=candidate,
                )
                s.add(version)
                s.flush()
                item = ExpenseItem(
                    expense_version_id=version.id,
                    item_key="i1",
                    label="mon",
                    amount_vnd=candidate,
                )
                s.add(item)
                s.commit()
                vid = version.id
            except Exception as exc:  # noqa: BLE001 -- the point is what refuses
                s.rollback()
                row["outcome"] = "REFUSED"
                row["detail"] = (
                    type(exc).__name__ + ": " + str(exc).split("\n")[0][:110]
                )
                results.append(row)
                print(
                    f"  {label:12s} sent {candidate!r:8s} -> REFUSED  {row['detail']}"
                )
                continue
        with Session(engine) as s:
            landed = s.execute(
                text(
                    f"SELECT total_amount_vnd FROM {SCHEMA}.expense_versions "
                    "WHERE id = :i"
                ),
                {"i": vid},
            ).scalar_one()
        row["outcome"] = "STORED"
        row["landed"] = landed
        row["landed_type"] = type(landed).__name__
        row["changed"] = landed != candidate
        results.append(row)
        flag = "  <-- STORED NUMBER != SENT NUMBER" if row["changed"] else ""
        print(
            f"  {label:12s} sent {str(candidate):8s} -> stored {landed!r} "
            f"({type(landed).__name__}){flag}"
        )
    print()
    return results


def part4(results: list[dict]) -> None:
    print("=" * 78)
    print("PART 4 -- consequence: can allocate() still split what landed?")
    print("=" * 78)
    print("  The feared shape is a STUCK ROW: a value the DB accepted but")
    print("  allocate() refuses, so the expense can never be split.\n")
    a, b = uuid.uuid4(), uuid.uuid4()
    for row in results:
        if row.get("outcome") != "STORED":
            continue
        landed = row["landed"]
        # Contract shape copied from tests/domain/golden/02_itemized.json, not
        # invented: a probe that feeds allocate() the wrong keys reports
        # "refused" for every input and proves nothing.
        expense = {
            "participants": [str(a), str(b)],
            "total_vnd": landed,
            "items": [
                {
                    "item_id": "i1",
                    "amount_vnd": landed,
                    "shared_by": [str(a), str(b)],
                }
            ],
            "surcharges": [],
            "discounts": [],
            "advancer_id": None,
        }
        try:
            out = allocate(expense)
            verdict = f"SPLIT OK -> {sorted(out['allocations'].values())}"
        except AllocationError as exc:
            verdict = f"AllocationError({exc.code}) -- ROW IS STUCK"
        except Exception as exc:  # noqa: BLE001
            verdict = (
                f"{type(exc).__name__} -- ROW IS STUCK (and not even a clean code)"
            )
        print(f"  {row['label']:12s} landed {landed!r:6} -> {verdict}")
    print()


def part5(engine) -> None:
    """The 'bản vá dữ liệu' door: a hand-run UPDATE against a money column."""

    print("=" * 78)
    print("PART 5 -- can a hand-run SQL patch rewrite money already in the ledger?")
    print("=" * 78)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT c.relname, t.tgname "
                "FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = :s AND NOT t.tgisinternal "
                "ORDER BY c.relname, t.tgname"
            ),
            {"s": SCHEMA},
        ).all()
    guarded = {r[0] for r in rows}
    money_tables = {
        "bill_discounts",
        "bill_items",
        "bill_surcharges",
        "bills",
        "collection_obligation_sources",
        "collection_obligations",
        "confirmed_allocations",
        "expense_discounts",
        "expense_items",
        "expense_surcharges",
        "expense_versions",
        "outings",
        "payment_reports",
        "receipt_confirmations",
    }
    print(f"  tables carrying an immutability trigger : {len(guarded)}")
    for t_name in sorted(money_tables):
        mark = "TRIGGER" if t_name in guarded else "  none "
        print(f"    {mark}  {t_name}")
    unguarded = sorted(money_tables - guarded)
    print(f"\n  money tables with NO trigger: {len(unguarded)} -> {unguarded}\n")

    # Live fire, both directions, so neither result is a guess about the catalog.
    with Session(engine) as s:
        expense_id, person_id = _seed_expense(s)
        version = ExpenseVersion(
            expense_id=expense_id,
            version_number=1,
            description="qa2 part5",
            recorded_by_id=person_id,
            paid_by_id=person_id,
            verification_scope=VerificationScope.TOTALS_ONLY,
            occurred_at=OCCURRED_AT,
            subtotal_amount_vnd=300,
            total_amount_vnd=300,
        )
        s.add(version)
        s.flush()
        item = ExpenseItem(
            expense_version_id=version.id,
            item_key="i1",
            label="mon",
            amount_vnd=300,
        )
        s.add(item)
        # NEGATIVE CONTROL. If every UPDATE below is rejected, "rejected" says
        # nothing about the trigger -- it could be the connection, the schema,
        # or the probe. `bills` is on the no-trigger list, so it must ACCEPT.
        bill = Bill(
            context_id=s.execute(
                text("SELECT context_id FROM expenses WHERE id = :i"),
                {"i": expense_id},
            ).scalar_one(),
            created_by_id=person_id,
            printed_total_vnd=300,
            items_total_vnd=300,
            confidence=90,
            needs_review=False,
        )
        s.add(bill)
        s.commit()
        vid, iid, bid = version.id, item.id, bill.id

    for table, col, row_id in (
        ("expense_versions", "total_amount_vnd", vid),
        ("expense_items", "amount_vnd", iid),
        ("bills", "items_total_vnd", bid),
    ):
        with Session(engine) as s:
            try:
                s.execute(
                    text(f"UPDATE {table} SET {col} = 999.5 WHERE id = :i"),
                    {"i": row_id},
                )
                s.commit()
                landed = s.execute(
                    text(f"SELECT {col} FROM {table} WHERE id = :i"), {"i": row_id}
                ).scalar_one()
                print(
                    f"  UPDATE {table}.{col} = 999.5  -> ACCEPTED, "
                    f"row now holds {landed!r} ({type(landed).__name__})"
                )
            except Exception as exc:  # noqa: BLE001
                s.rollback()
                detail = str(exc).split("\n")[0][:100]
                print(f"  UPDATE {table}.{col} = 999.5  -> REJECTED  {detail}")
    print()


def main() -> int:
    url = _url()
    _migrate(url)
    scoped = url.update_query_dict({"options": f"-csearch_path={SCHEMA}"}, append=False)
    engine = create_engine(scoped, future=True)
    try:
        print(f"schema: {SCHEMA}\n")
        part1(engine)
        control_ok = part2(engine)
        results = part3(engine)
        part4(results)
        part5(engine)
        print("=" * 78)
        print("VERDICT INPUTS (numbers, not adjectives)")
        print("=" * 78)
        print(f"  positive control passed        : {control_ok}")
        stored = [r for r in results if r.get("outcome") == "STORED"]
        refused = [r for r in results if r.get("outcome") == "REFUSED"]
        changed = [r for r in stored if r.get("changed")]
        print(f"  candidates tried               : {len(results)}")
        print(f"  refused by the database        : {len(refused)}")
        print(f"  stored                         : {len(stored)}")
        print(
            f"  stored with a CHANGED number   : {len(changed)} "
            f"-> {[(r['label'], r['sent'], r['landed']) for r in changed]}"
        )
        non_int = [r for r in stored if r.get("landed_type") != "int"]
        print(f"  stored still NON-INT           : {len(non_int)}")
        return 0 if control_ok else 1
    finally:
        engine.dispose()
        _drop(url)


if __name__ == "__main__":
    raise SystemExit(main())
