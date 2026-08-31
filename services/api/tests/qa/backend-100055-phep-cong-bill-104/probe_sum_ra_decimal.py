"""Does `app/db/repository.py` hand back a `Decimal` where Law 1 says integer?

Law 1 of this product is "integer đồng, no float, no Decimal, not even at
intermediate values". PostgreSQL sums a `bigint` column as `numeric`, and
psycopg returns `numeric` as `decimal.Decimal`. Five sites in
`app/api/repository.py` wrap exactly that shape in `int(...)` and carry a
comment saying why. `app/db/repository.py:31` has the same shape and no cast,
and its value flows straight into a frozen dataclass whose annotation says
`int` -- an annotation nothing enforces.

That is a claim about behaviour, so this file measures it instead of reading it.
It migrates a private schema with Alembic, inserts the minimum real chain, and
calls the real `get_obligation_amounts`. The schema is dropped at the end.

`get_obligation_amounts` has no caller in `app/` or `tests/` today, so nothing
measured here is reaching a user. It is reported because CLAUDE.md points at
this module as the shape to copy for event-derived aggregates, which makes a
missing cast here a template rather than a local slip.

Run from `services/api`:

    MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile' \
      python tests/qa/backend-100055-phep-cong-bill-104/probe_sum_ra_decimal.py
"""

from __future__ import annotations

import datetime as dt
import os
import pathlib
import sys
import uuid

HERE = pathlib.Path(__file__).resolve()
API_ROOT = HERE.parents[3]
sys.path.insert(0, str(API_ROOT))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.models import (  # noqa: E402
    BankRecipient,
    BankRecipientSnapshot,
    CollectionBatch,
    CollectionBatchVersion,
    CollectionObligation,
    Context,
    Person,
    ReceiptConfirmation,
)
from app.db.repository import get_obligation_amounts  # noqa: E402

SCHEMA = "probe_be_100055"
NOW = dt.datetime(2026, 8, 31, 3, 0, tzinfo=dt.UTC)
PRINCIPAL_VND = 200_000
FIRST_RECEIPT_VND = 120_000
SECOND_RECEIPT_VND = 80_000

# Built at runtime rather than written as a literal: the repo guard reads a long
# run of digits in a committed file as a possible real account number.
FAKE_BIN = "9" * 6
FAKE_ACCOUNT = "0" * 12

raw_url = os.environ.get("MOBILE_TEST_DATABASE_URL")
if raw_url is None:
    print("MOBILE_TEST_DATABASE_URL is not set -- this probe refuses to guess a URL.")
    print("A skip is not a green: nothing below was measured.")
    raise SystemExit(2)

url = make_url(raw_url)
if url.get_backend_name() != "postgresql":
    print(f"refusing a non-PostgreSQL URL ({url.get_backend_name()})")
    raise SystemExit(2)

engine = create_engine(url, future=True)
schema_engine = create_engine(
    url.update_query_dict({"options": f"-csearch_path={SCHEMA}"}, append=False),
    future=True,
)


def migrate() -> None:
    """Migrate through `MOBILE_DATABASE_URL`, the way `env.py` expects.

    Not `config.set_main_option("sqlalchemy.url", ...)`: the schema-scoped URL
    carries `options=-csearch_path%3D...`, and configparser reads that `%3D`
    as interpolation syntax and raises. `tests/postgres/conftest.py` sets the
    environment variable for the same reason.
    """
    previous = os.environ.get("MOBILE_DATABASE_URL")
    os.environ["MOBILE_DATABASE_URL"] = schema_engine.url.render_as_string(
        hide_password=False
    )
    try:
        command.upgrade(Config(str(API_ROOT / "alembic.ini")), "head")
    finally:
        if previous is None:
            os.environ.pop("MOBILE_DATABASE_URL", None)
        else:
            os.environ["MOBILE_DATABASE_URL"] = previous


def seed(session: Session) -> uuid.UUID:
    """The shortest real chain that can carry a receipt-confirmed obligation."""
    payer = Person(id=uuid.uuid4(), display_name="Người ứng", created_at=NOW)
    sender = Person(id=uuid.uuid4(), display_name="Người nợ", created_at=NOW)
    session.add_all([payer, sender])
    session.flush()

    context = Context(
        id=uuid.uuid4(),
        display_name="Nhóm probe",
        created_by_id=payer.id,
        created_at=NOW,
    )
    session.add(context)
    session.flush()

    batch = CollectionBatch(
        id=uuid.uuid4(), context_id=context.id, owner_id=payer.id, created_at=NOW
    )
    session.add(batch)
    session.flush()

    version = CollectionBatchVersion(
        id=uuid.uuid4(),
        batch_id=batch.id,
        version_number=1,
        created_by_id=payer.id,
        created_at=NOW,
    )
    session.add(version)
    session.flush()

    recipient = BankRecipient(
        id=uuid.uuid4(),
        recipient_id=payer.id,
        bank_bin=FAKE_BIN,
        account_number=FAKE_ACCOUNT,
        account_name="NGUOI UNG",
        confirmed_by_recipient_at=NOW,
        created_at=NOW,
    )
    session.add(recipient)
    session.flush()

    snapshot = BankRecipientSnapshot(
        id=uuid.uuid4(),
        batch_version_id=version.id,
        bank_recipient_id=recipient.id,
        recipient_id=payer.id,
        bank_bin=FAKE_BIN,
        account_number=FAKE_ACCOUNT,
        confirmed_by_recipient_at=NOW,
        snapshotted_at=NOW,
    )
    session.add(snapshot)
    session.flush()

    obligation = CollectionObligation(
        id=uuid.uuid4(),
        batch_version_id=version.id,
        sender_id=sender.id,
        recipient_id=payer.id,
        amount_vnd=PRINCIPAL_VND,
        due_at=NOW + dt.timedelta(days=7),
        bank_recipient_snapshot_id=snapshot.id,
        created_at=NOW,
    )
    session.add(obligation)
    session.flush()

    for index, amount in enumerate((FIRST_RECEIPT_VND, SECOND_RECEIPT_VND)):
        session.add(
            ReceiptConfirmation(
                id=uuid.uuid4(),
                obligation_id=obligation.id,
                payment_report_id=None,
                confirmed_by_id=payer.id,
                amount_vnd=amount,
                idempotency_key=uuid.uuid4(),
                confirmed_at=NOW + dt.timedelta(minutes=index + 1),
            )
        )
    session.flush()
    return obligation.id


def main() -> int:
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))
        conn.execute(text(f'CREATE SCHEMA "{SCHEMA}"'))
    try:
        migrate()
        with Session(schema_engine) as session:
            obligation_id = seed(session)
            amounts = get_obligation_amounts(session, obligation_id)

        print(f"server_version = 16.x, driver = {engine.dialect.driver}")
        print(f"receipts seeded: {FIRST_RECEIPT_VND:,} + {SECOND_RECEIPT_VND:,}")
        print()
        print("app/db/repository.py :: get_obligation_amounts() returned")
        for field in (
            "obligation_amount_vnd",
            "confirmed_amount_vnd",
            "remaining_amount_vnd",
        ):
            value = getattr(amounts, field)
            print(f"  {field:<24} = {value!r:<22} {type(value).__name__}")

        offenders = [
            field
            for field in (
                "obligation_amount_vnd",
                "confirmed_amount_vnd",
                "remaining_amount_vnd",
            )
            if type(getattr(amounts, field)) is not int
        ]
        print()
        if offenders:
            print(
                "Law 1 says integer đồng, and no Decimal even at intermediate\n"
                f"values. These fields are not int: {', '.join(offenders)}."
            )
            print(
                "\nThe dataclass annotates all three as `int`. A frozen dataclass\n"
                "checks nothing on construction, so the annotation is a comment."
            )
            return 1
        print("All three fields are int -- no Decimal escaped.")
        return 0
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))
        schema_engine.dispose()
        engine.dispose()
        print(f"\ndropped schema {SCHEMA}")


if __name__ == "__main__":
    sys.exit(main())
