"""Registering a bank destination, against a real PostgreSQL server.

Three of the guarantees this route depends on cannot exist in a dict-backed
fake, and each one is money:

* `uq_bank_recipients_active_recipient` -- a partial unique index over
  `revoked_at IS NULL`. Changing an account has to revoke the old row and
  insert the new one in an order the index accepts. A fake dictionary simply
  overwrites a key and calls it a day.
* the two regex check constraints on `bank_bin` and `account_number`, which are
  the backstop under `app.domain.bank_account`.
* `BankRecipientSnapshot` -- an envelope already in somebody's hands must keep
  pointing at the account frozen into it. If changing a live account rewrote
  published payment instructions, a compromised account could redirect money
  that was already asked for.

The first test drives real HTTP into this database, because the API test layer
proves the wiring against a fake and the repository tests prove the SQL, and
neither one proves that the route and the schema agree.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import anyio
import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_repository
from app.api.errors import ApiProblem
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.api.schemas import BankRecipientRequest
from app.api.service import ApiService
from app.db.models import AuditEvent, BankRecipient

from .test_repository_postgres import NOW, ORIGINAL_ACCOUNT, _persist_lifecycle

pytestmark = pytest.mark.postgres

# Synthetic throughout: a real Napas BIN with account numbers that are not real
# accounts. Nothing in this repository may carry a real one.
BANK_BIN = "970418"
ACCOUNT = "0000000000TEST"
CHANGED = "1111111111TEST"


def _actor(person_id: uuid.UUID) -> Actor:
    return Actor(id=person_id, roles=frozenset({"member"}), context_ids=frozenset())


def _request(recipient_id: uuid.UUID, **overrides) -> BankRecipientRequest:
    fields = {
        "recipient_id": recipient_id,
        "bank_bin": BANK_BIN,
        "account_number": ACCOUNT,
        "account_name": "NGUOI UNG TIEN",
    }
    fields.update(overrides)
    return BankRecipientRequest(**fields)


def _active_rows(session: Session, recipient_id: uuid.UUID) -> list[BankRecipient]:
    return list(
        session.scalars(
            select(BankRecipient).where(
                BankRecipient.recipient_id == recipient_id,
                BankRecipient.revoked_at.is_(None),
            )
        )
    )


def test_registered_over_http_and_read_back_over_http(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The acceptance criterion end to end: a real request writes a real row,
    and a second real request reads it back out of PostgreSQL."""
    recipient_id = uuid.uuid4()
    repository = SqlAlchemyApiRepository(postgres_session)

    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repository
    headers = {"X-Actor-ID": str(recipient_id), "X-Actor-Roles": "member"}

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            written = await client.post(
                "/bank-recipients",
                headers=headers,
                json={
                    "recipient_id": str(recipient_id),
                    "bank_bin": BANK_BIN,
                    "account_number": ACCOUNT,
                    "account_name": "NGUOI UNG TIEN",
                },
            )
            read = await client.get(
                f"/bank-recipients/{recipient_id}", headers=headers
            )
            return written, read

    written, read = anyio.run(exchange)

    assert written.status_code == 201, written.text
    assert read.status_code == 200, read.text
    assert read.json()["account_number"] == ACCOUNT
    assert read.json()["bank_name"] == "BIDV"

    # And the row is really in the table, not only in the response body.
    rows = _active_rows(postgres_session, recipient_id)
    assert [row.account_number for row in rows] == [ACCOUNT]


def test_changing_an_account_leaves_exactly_one_active_row(postgres_session: Session):
    """`uq_bank_recipients_active_recipient` is a partial unique index. Insert
    before revoke and PostgreSQL rejects the whole request; the fake would have
    accepted either order."""
    recipient_id = uuid.uuid4()
    service = ApiService(SqlAlchemyApiRepository(postgres_session))
    actor = _actor(recipient_id)

    first, created = service.set_bank_recipient(_request(recipient_id), actor)
    assert created is True
    second, changed = service.set_bank_recipient(
        _request(recipient_id, account_number=CHANGED), actor
    )
    assert changed is True

    active = _active_rows(postgres_session, recipient_id)
    assert [row.account_number for row in active] == [CHANGED]
    assert second.id != first.id

    # The replaced row is revoked, not deleted: it is what a published envelope
    # was frozen from, and the audit has to be able to explain that envelope.
    superseded = postgres_session.get(BankRecipient, first.id)
    assert superseded is not None
    assert superseded.revoked_at is not None


def test_re_registering_the_same_account_writes_no_second_row(
    postgres_session: Session,
):
    """Section 8.5 makes adding or changing a destination a notifiable event.
    A retry that sends the same digits changed nothing and must not notify."""
    recipient_id = uuid.uuid4()
    service = ApiService(SqlAlchemyApiRepository(postgres_session))
    actor = _actor(recipient_id)

    first, _ = service.set_bank_recipient(_request(recipient_id), actor)
    again, created = service.set_bank_recipient(_request(recipient_id), actor)

    assert created is False
    assert again.id == first.id
    assert len(_active_rows(postgres_session, recipient_id)) == 1
    events = list(
        postgres_session.scalars(
            select(AuditEvent).where(AuditEvent.aggregate_type == "bank_recipient")
        )
    )
    assert len(events) == 1


def test_the_audit_records_the_registration_without_the_account_number(
    postgres_session: Session,
):
    """An audit row is read far more widely than the table it describes. The
    account number is already in `bank_recipients`; copying it into a JSONB
    blob that every audit query scans spreads it for nothing."""
    recipient_id = uuid.uuid4()
    service = ApiService(SqlAlchemyApiRepository(postgres_session))

    record, _ = service.set_bank_recipient(_request(recipient_id), _actor(recipient_id))

    event = postgres_session.scalar(
        select(AuditEvent).where(AuditEvent.aggregate_id == record.id)
    )
    assert event is not None
    assert event.actor_id == recipient_id
    assert event.aggregate_type == "bank_recipient"
    assert event.event_type == "bank_recipient_confirmed_by_recipient"
    assert ACCOUNT not in str(event.event_data)


def test_changing_an_account_does_not_move_money_already_asked_for(
    postgres_session: Session,
):
    """The whole reason `BankRecipientSnapshot` exists.

    A guest is holding a link with payment instructions on it. If changing the
    live account rewrote that link, taking over one account would redirect
    money that was already requested -- and the sender would have no way to
    tell, because the page would look exactly as it did before.
    """
    state = _persist_lifecycle(postgres_session)
    repository = SqlAlchemyApiRepository(postgres_session)
    before = repository.get_guest_envelope(state.token_digest, NOW + timedelta(minutes=1))
    assert before is not None
    assert before.envelope["obligations"][0]["account_number"] == ORIGINAL_ACCOUNT

    ApiService(repository).set_bank_recipient(
        _request(state.recipient_id, account_number=CHANGED),
        _actor(state.recipient_id),
    )

    after = repository.get_guest_envelope(state.token_digest, NOW + timedelta(minutes=2))
    assert after is not None
    assert after.envelope["obligations"][0]["account_number"] == ORIGINAL_ACCOUNT
    assert CHANGED not in str(after.envelope)


def test_registering_for_somebody_else_writes_nothing(postgres_session: Session):
    """Section 9.2 with no admin exception. Asserted against the table, not
    against the exception: a check that raises after the INSERT would pass a
    test that only looked at the status code."""
    recipient_id = uuid.uuid4()
    service = ApiService(SqlAlchemyApiRepository(postgres_session))

    with pytest.raises(ApiProblem) as caught:
        service.set_bank_recipient(_request(recipient_id), _actor(uuid.uuid4()))

    assert caught.value.status_code == 403
    assert _active_rows(postgres_session, recipient_id) == []


def test_reading_is_scoped_to_the_owner(postgres_session: Session):
    recipient_id = uuid.uuid4()
    service = ApiService(SqlAlchemyApiRepository(postgres_session))
    service.set_bank_recipient(_request(recipient_id), _actor(recipient_id))

    with pytest.raises(ApiProblem) as caught:
        service.get_bank_recipient(recipient_id, _actor(uuid.uuid4()))

    assert caught.value.status_code == 403
    assert ACCOUNT not in caught.value.detail


def test_reading_before_registering_is_not_found(postgres_session: Session):
    service = ApiService(SqlAlchemyApiRepository(postgres_session))
    stranger = uuid.uuid4()

    with pytest.raises(ApiProblem) as caught:
        service.get_bank_recipient(stranger, _actor(stranger))

    assert caught.value.status_code == 404


def test_a_revoked_account_stops_being_readable(postgres_session: Session):
    """`revoked_at` is not a soft delete that leaves the data reachable. Once
    a destination is withdrawn, the route stops handing it out."""
    recipient_id = uuid.uuid4()
    repository = SqlAlchemyApiRepository(postgres_session)
    service = ApiService(repository)
    record, _ = service.set_bank_recipient(_request(recipient_id), _actor(recipient_id))

    row = postgres_session.get(BankRecipient, record.id)
    row.revoked_at = NOW
    postgres_session.flush()

    with pytest.raises(ApiProblem) as caught:
        service.get_bank_recipient(recipient_id, _actor(recipient_id))
    assert caught.value.status_code == 404


def test_the_database_still_refuses_a_malformed_destination(postgres_session: Session):
    """Domain validation is the first line, and these constraints are the line
    behind it. A test that only exercised the service would not notice if the
    migration ever dropped them."""
    for column, value in (("bank_bin", "97041"), ("account_number", "0123-4567")):
        with pytest.raises(IntegrityError):
            with postgres_session.begin_nested():
                fields = {
                    "recipient_id": uuid.uuid4(),
                    "bank_bin": BANK_BIN,
                    "account_number": ACCOUNT,
                    "confirmed_by_recipient_at": NOW,
                    "created_at": NOW,
                }
                fields[column] = value
                postgres_session.add(BankRecipient(**fields))
                postgres_session.flush()


# --- What enforces the invariant, as opposed to what happens to satisfy it ----
#
# The cases above drive the adapter, which revokes the old row before inserting
# the new one. They would all still pass on a schema whose unique index had been
# dropped, because the adapter would keep getting the order right on its own.
# These go around the adapter and ask the database directly.


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


def test_the_partial_index_and_not_the_adapter_refuses_a_second_live_row(
    postgres_session: Session,
):
    """Insert a conflicting live row behind the adapter's back.

    If this raises, the guarantee "one live destination per person" is held by
    the schema. If it does not, the guarantee is held only by the current
    ordering of two statements in `save_bank_recipient`, and the next person to
    reorder them removes it without a single test going red.
    """
    recipient_id = uuid.uuid4()
    service = ApiService(SqlAlchemyApiRepository(postgres_session))
    service.set_bank_recipient(_request(recipient_id), _actor(recipient_id))

    with pytest.raises(IntegrityError) as caught:
        with postgres_session.begin_nested():
            postgres_session.add(
                BankRecipient(
                    recipient_id=recipient_id,
                    bank_bin=BANK_BIN,
                    account_number=CHANGED,
                    confirmed_by_recipient_at=NOW,
                    created_at=NOW,
                )
            )
            postgres_session.flush()

    assert _constraint_name(caught.value) == "uq_bank_recipients_active_recipient"


def test_the_partial_index_really_is_partial_in_this_schema(postgres_session: Session):
    """Read the definition the server holds, not the one `models.py` declares.

    `Index(..., postgresql_where=...)` is a statement of intent; the migration
    is what ran. A unique index that lost its WHERE clause would still look
    correct in the model and would reject every replacement outright -- nobody
    could ever change their account a second time.
    """
    definition = postgres_session.scalar(
        text(
            "select indexdef from pg_indexes "
            "where indexname = 'uq_bank_recipients_active_recipient' "
            "and schemaname = current_schema()"
        )
    )

    assert definition is not None, "the index is missing from this schema"
    assert "UNIQUE" in definition
    assert "revoked_at IS NULL" in definition


def test_a_history_of_revoked_rows_does_not_lock_the_person_out(
    postgres_session: Session,
):
    """Which is why the index is partial. Somebody who changes bank three times
    must not find the fourth attempt rejected by their own history."""
    recipient_id = uuid.uuid4()
    service = ApiService(SqlAlchemyApiRepository(postgres_session))

    for index in range(3):
        service.set_bank_recipient(
            _request(recipient_id, account_number=f"ACCOUNT{index:03d}"),
            _actor(recipient_id),
        )

    all_rows = list(
        postgres_session.scalars(
            select(BankRecipient).where(BankRecipient.recipient_id == recipient_id)
        )
    )
    assert len(all_rows) == 3, "every destination stays as history"
    assert [row.account_number for row in _active_rows(postgres_session, recipient_id)] == [
        "ACCOUNT002"
    ]


def test_two_people_each_keep_their_own_live_destination(postgres_session: Session):
    """The index is per recipient, not global. If it were global, the second
    person to register would be refused because somebody else already had."""
    first_person = uuid.uuid4()
    second_person = uuid.uuid4()
    service = ApiService(SqlAlchemyApiRepository(postgres_session))

    service.set_bank_recipient(_request(first_person), _actor(first_person))
    service.set_bank_recipient(
        _request(second_person, account_number=CHANGED), _actor(second_person)
    )

    loaded = SqlAlchemyApiRepository(postgres_session).load_bank_recipients(
        frozenset({first_person, second_person})
    )
    assert loaded[first_person].account_number == ACCOUNT
    assert loaded[second_person].account_number == CHANGED


# The doubled prefix is real, not a typo: the model names the constraint
# `ck_bank_recipients_..._format` and the metadata naming convention prepends
# `ck_%(table_name)s_` on top of it. Pinned as the server actually reports it,
# because catching drift is the entire point of these two cases.
BIN_CONSTRAINT = "ck_bank_recipients_ck_bank_recipients_bank_bin_format"
ACCOUNT_CONSTRAINT = "ck_bank_recipients_ck_bank_recipients_account_number_format"


@pytest.mark.parametrize(
    ("bank_bin", "account_number", "constraint"),
    [
        ("97041", ACCOUNT, BIN_CONSTRAINT),
        ("97041a", ACCOUNT, BIN_CONSTRAINT),
        ("", ACCOUNT, BIN_CONSTRAINT),
        (BANK_BIN, "", ACCOUNT_CONSTRAINT),
        (BANK_BIN, "0123-4567", ACCOUNT_CONSTRAINT),
        (BANK_BIN, "0123 4567", ACCOUNT_CONSTRAINT),
    ],
)
def test_the_database_names_the_constraint_the_api_already_refused(
    postgres_session: Session, bank_bin: str, account_number: str, constraint: str
):
    """The other half of `test_every_shape_the_database_check_would_reject_is_
    refused_here_first` in tests/api.

    Those values come back 422 naming the bad field. These are the same values
    arriving unvalidated, and each one has to be stopped -- by the constraint
    this test names. If the API and the schema ever drift apart, the caller
    stops getting a 422 and starts getting a 500 out of an IntegrityError.

    Note "0123 4567": the API accepts it and stores "01234567", because that is
    how a banking app displays a number. It is in this list because the raw form
    with the space must not be storable -- normalising is the API's job, and the
    column is the proof it happened.
    """
    with pytest.raises(IntegrityError) as caught:
        with postgres_session.begin_nested():
            postgres_session.add(
                BankRecipient(
                    recipient_id=uuid.uuid4(),
                    bank_bin=bank_bin,
                    account_number=account_number,
                    confirmed_by_recipient_at=NOW,
                    created_at=NOW,
                )
            )
            postgres_session.flush()

    assert _constraint_name(caught.value) == constraint


@pytest.mark.parametrize(
    ("bank_bin", "account_number"),
    [
        ("9704155", ACCOUNT),
        (BANK_BIN, "1" * 20),
    ],
)
def test_an_over_long_value_is_stopped_by_the_column_not_the_check(
    postgres_session: Session, bank_bin: str, account_number: str
):
    """Also refused, but by width rather than by CHECK, and that is a different
    exception class.

    Kept separate instead of folded into the cases above: a test that accepted
    either error would keep passing if a CHECK constraint were dropped and only
    the column width were left standing. The API rejects both of these at 422
    long before they get here.
    """
    with pytest.raises(DataError):
        with postgres_session.begin_nested():
            postgres_session.add(
                BankRecipient(
                    recipient_id=uuid.uuid4(),
                    bank_bin=bank_bin,
                    account_number=account_number,
                    confirmed_by_recipient_at=NOW,
                    created_at=NOW,
                )
            )
            postgres_session.flush()


def test_the_person_scoped_route_writes_a_real_row(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """`PUT /people/{id}/bank-recipient` against the real schema.

    The API-layer test proves it reaches the same service. This proves it
    reaches the same table -- an alias that quietly wrote somewhere else would
    look identical against a fake.
    """
    recipient_id = uuid.uuid4()
    repository = SqlAlchemyApiRepository(postgres_session)

    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repository
    headers = {"X-Actor-ID": str(recipient_id), "X-Actor-Roles": "member"}

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            written = await client.put(
                f"/people/{recipient_id}/bank-recipient",
                headers=headers,
                json={
                    "bank_bin": BANK_BIN,
                    "account_number": ACCOUNT,
                    "account_name": "NGUOI UNG TIEN",
                },
            )
            # Read back through the *other* shape: one destination, two doors.
            read = await client.get(
                f"/bank-recipients/{recipient_id}", headers=headers
            )
            return written, read

    written, read = anyio.run(exchange)

    assert written.status_code == 201, written.text
    assert read.status_code == 200, read.text
    assert read.json()["id"] == written.json()["id"]

    rows = _active_rows(postgres_session, recipient_id)
    assert [row.account_number for row in rows] == [ACCOUNT]
