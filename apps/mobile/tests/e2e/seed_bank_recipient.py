"""Seed a confirmed bank destination for one recipient.

Stands in for an endpoint that does not exist yet: nothing in the HTTP surface
writes `bank_recipients`, so a batch can never freeze and no envelope can ever
be produced. Until that route lands, the end-to-end test seeds the row the
route would have written -- data, not a faked API response. Every call the test
makes still goes over real HTTP against the real service.
"""
import os, sys, uuid, datetime, sqlalchemy as sa

recipient_id = uuid.UUID(sys.argv[1])
# Same variable the API and Alembic read, so the seeder lands in whichever
# database the server under test is actually using. Hardcoded, it wrote into the
# shared dev database no matter where the server was pointed, which seeds a row
# the test then cannot see.
url = os.environ.get(
    "MOBILE_DATABASE_URL", "postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile"
)
engine = sa.create_engine(url)
now = datetime.datetime.now(datetime.timezone.utc)
with engine.begin() as conn:
    conn.execute(
        sa.text(
            "INSERT INTO bank_recipients "
            "(id, recipient_id, bank_bin, account_number, account_name,"
            " confirmed_by_recipient_at) "
            "VALUES (:id, :rid, :bin, :acct, :name, :at) "
            "ON CONFLICT DO NOTHING"
        ),
        {
            "id": uuid.uuid4(),
            "rid": recipient_id,
            # Synthetic. Not a real bank, not a real account.
            "bin": "970418",
            "acct": "0000000000TEST",
            "name": "NGUOI UNG TIEN",
            "at": now,
        },
    )
print("seeded", recipient_id)
