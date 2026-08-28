"""The bank-destination write path, on the schema that actually enforces it.

`tests/api` proves the HTTP route calls the service and the service calls the
repository. It cannot prove any of the three things that make this write safe,
because the fake is a dict keyed by recipient:

  * that "replace" revokes the old row instead of overwriting it, so the record
    of which account was live when survives;
  * that `uq_bank_recipients_active_recipient` -- a partial unique index over
    `revoked_at IS NULL` -- is what enforces one live destination per person,
    rather than the adapter method having got the order right by luck;
  * that the API's regex validation and the database CHECK constraints agree,
    so a value the API accepts is never a value the database rejects at 500.

A dict cannot disagree with itself about any of those. PostgreSQL can.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.api.repository import SqlAlchemyApiRepository
from app.db.models import BankRecipient

NOW = datetime(2030, 8, 28, 9, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=1)

# Synthetic. Not a real bank, not a real account.
FIRST_ACCOUNT = ("970415", "0000000000TEST", "NGUYEN VAN NAM")
SECOND_ACCOUNT = ("970418", "9999999999TEST", "NGUYEN VAN NAM")


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


def _live_rows(session: Session, recipient_id: uuid.UUID) -> list[BankRecipient]:
    return list(
        session.scalars(
            select(BankRecipient)
            .where(
                BankRecipient.recipient_id == recipient_id,
                BankRecipient.revoked_at.is_(None),
            )
            .order_by(BankRecipient.created_at)
        )
    )


def _all_rows(session: Session, recipient_id: uuid.UUID) -> list[BankRecipient]:
    return list(
        session.scalars(
            select(BankRecipient)
            .where(BankRecipient.recipient_id == recipient_id)
            .order_by(BankRecipient.confirmed_by_recipient_at)
        )
    )


def test_save_writes_a_row_the_batch_gate_can_read(postgres_session: Session):
    repository = SqlAlchemyApiRepository(postgres_session)
    recipient_id = uuid.uuid4()

    saved = repository.save_bank_recipient(
        recipient_id=recipient_id,
        bank_bin=FIRST_ACCOUNT[0],
        account_number=FIRST_ACCOUNT[1],
        account_name=FIRST_ACCOUNT[2],
        now=NOW,
    )

    # `load_bank_recipients` is the reader the batch freeze gate uses. If the
    # write lands somewhere that reader cannot see it, the dead end is still
    # there in a different disguise.
    loaded = repository.load_bank_recipients(frozenset({recipient_id}))
    assert set(loaded) == {recipient_id}
    assert loaded[recipient_id].id == saved.id
    assert loaded[recipient_id].bank_bin == FIRST_ACCOUNT[0]
    assert loaded[recipient_id].account_number == FIRST_ACCOUNT[1]
    assert loaded[recipient_id].account_name == FIRST_ACCOUNT[2]
    assert loaded[recipient_id].confirmed_at == NOW


def test_replacing_revokes_the_old_row_instead_of_overwriting_it(
    postgres_session: Session,
):
    repository = SqlAlchemyApiRepository(postgres_session)
    recipient_id = uuid.uuid4()

    first = repository.save_bank_recipient(
        recipient_id=recipient_id,
        bank_bin=FIRST_ACCOUNT[0],
        account_number=FIRST_ACCOUNT[1],
        account_name=FIRST_ACCOUNT[2],
        now=NOW,
    )
    second = repository.save_bank_recipient(
        recipient_id=recipient_id,
        bank_bin=SECOND_ACCOUNT[0],
        account_number=SECOND_ACCOUNT[1],
        account_name=SECOND_ACCOUNT[2],
        now=LATER,
    )

    assert second.id != first.id

    stored = _all_rows(postgres_session, recipient_id)
    assert len(stored) == 2, "the old destination must survive as history"

    old, new = stored
    assert old.id == first.id
    assert old.account_number == FIRST_ACCOUNT[1]
    assert old.revoked_at == LATER
    assert new.id == second.id
    assert new.account_number == SECOND_ACCOUNT[1]
    assert new.revoked_at is None

    live = _live_rows(postgres_session, recipient_id)
    assert [row.id for row in live] == [second.id]

    loaded = repository.load_bank_recipients(frozenset({recipient_id}))
    assert loaded[recipient_id].account_number == SECOND_ACCOUNT[1]


def test_the_partial_index_refuses_a_second_live_destination(
    postgres_session: Session,
):
    """Prove the database is the enforcer, not the adapter's statement order.

    The adapter revokes before inserting. If that ordering silently stopped
    working, the previous test would still pass on a schema with no unique
    index -- so this one bypasses the adapter and inserts the conflicting row
    directly.
    """
    repository = SqlAlchemyApiRepository(postgres_session)
    recipient_id = uuid.uuid4()
    repository.save_bank_recipient(
        recipient_id=recipient_id,
        bank_bin=FIRST_ACCOUNT[0],
        account_number=FIRST_ACCOUNT[1],
        account_name=FIRST_ACCOUNT[2],
        now=NOW,
    )

    with pytest.raises(IntegrityError) as caught:
        with postgres_session.begin_nested():
            postgres_session.add(
                BankRecipient(
                    recipient_id=recipient_id,
                    bank_bin=SECOND_ACCOUNT[0],
                    account_number=SECOND_ACCOUNT[1],
                    account_name=SECOND_ACCOUNT[2],
                    confirmed_by_recipient_at=LATER,
                )
            )
            postgres_session.flush()

    assert _constraint_name(caught.value) == "uq_bank_recipients_active_recipient"


def test_a_revoked_row_does_not_block_a_new_one(postgres_session: Session):
    """The index is partial for a reason: history must not lock the person out."""
    repository = SqlAlchemyApiRepository(postgres_session)
    recipient_id = uuid.uuid4()

    for index, now in enumerate((NOW, LATER, LATER + timedelta(days=1))):
        repository.save_bank_recipient(
            recipient_id=recipient_id,
            bank_bin="970415",
            account_number=f"ACCOUNT{index:03d}",
            account_name=None,
            now=now,
        )

    assert len(_all_rows(postgres_session, recipient_id)) == 3
    assert len(_live_rows(postgres_session, recipient_id)) == 1


def test_two_people_each_keep_their_own_live_destination(postgres_session: Session):
    repository = SqlAlchemyApiRepository(postgres_session)
    first_person = uuid.uuid4()
    second_person = uuid.uuid4()

    repository.save_bank_recipient(
        recipient_id=first_person,
        bank_bin=FIRST_ACCOUNT[0],
        account_number=FIRST_ACCOUNT[1],
        account_name=None,
        now=NOW,
    )
    repository.save_bank_recipient(
        recipient_id=second_person,
        bank_bin=SECOND_ACCOUNT[0],
        account_number=SECOND_ACCOUNT[1],
        account_name=None,
        now=NOW,
    )

    loaded = repository.load_bank_recipients(frozenset({first_person, second_person}))
    assert loaded[first_person].account_number == FIRST_ACCOUNT[1]
    assert loaded[second_person].account_number == SECOND_ACCOUNT[1]


def test_get_active_returns_none_when_the_person_never_said(postgres_session: Session):
    repository = SqlAlchemyApiRepository(postgres_session)
    assert repository.get_active_bank_recipient(uuid.uuid4()) is None


def test_get_active_stops_seeing_a_destination_once_it_is_replaced(
    postgres_session: Session,
):
    repository = SqlAlchemyApiRepository(postgres_session)
    recipient_id = uuid.uuid4()
    repository.save_bank_recipient(
        recipient_id=recipient_id,
        bank_bin=FIRST_ACCOUNT[0],
        account_number=FIRST_ACCOUNT[1],
        account_name=None,
        now=NOW,
    )
    repository.save_bank_recipient(
        recipient_id=recipient_id,
        bank_bin=SECOND_ACCOUNT[0],
        account_number=SECOND_ACCOUNT[1],
        account_name=None,
        now=LATER,
    )

    active = repository.get_active_bank_recipient(recipient_id)
    assert active is not None
    assert active.account_number == SECOND_ACCOUNT[1]


# The doubled prefix is real, not a typo: the model names the constraint
# `ck_bank_recipients_..._format` and the metadata naming convention prepends
# `ck_%(table_name)s_` on top of it. Pinned as the server actually reports it,
# because the point of these cases is to catch drift between API and database.
BIN_CONSTRAINT = "ck_bank_recipients_ck_bank_recipients_bank_bin_format"
ACCOUNT_CONSTRAINT = "ck_bank_recipients_ck_bank_recipients_account_number_format"


@pytest.mark.parametrize(
    ("bank_bin", "account_number", "constraint"),
    [
        ("97041", "0000000000TEST", BIN_CONSTRAINT),
        ("97041a", "0000000000TEST", BIN_CONSTRAINT),
        ("970415", "", ACCOUNT_CONSTRAINT),
        ("970415", "0123 4567", ACCOUNT_CONSTRAINT),
        ("970415", "0123-4567", ACCOUNT_CONSTRAINT),
    ],
)
def test_the_database_rejects_exactly_what_the_api_rejects(
    postgres_session: Session, bank_bin: str, account_number: str, constraint: str
):
    """Same values the API returns 422 for in `tests/api/test_bank_recipients`.

    If these two lists ever drift, a caller gets a 500 out of an IntegrityError
    instead of a 422 naming the bad field. Pinning the constraint name is what
    makes that drift a red test rather than a production surprise.
    """
    repository = SqlAlchemyApiRepository(postgres_session)

    with pytest.raises(IntegrityError) as caught:
        with postgres_session.begin_nested():
            repository.save_bank_recipient(
                recipient_id=uuid.uuid4(),
                bank_bin=bank_bin,
                account_number=account_number,
                account_name=None,
                now=NOW,
            )

    assert _constraint_name(caught.value) == constraint


@pytest.mark.parametrize(
    ("bank_bin", "account_number"),
    [
        ("9704155", "0000000000TEST"),
        ("970415", "A" * 20),
    ],
)
def test_an_over_long_value_is_stopped_by_the_column_not_the_check(
    postgres_session: Session, bank_bin: str, account_number: str
):
    """Also rejected, but by width rather than by CHECK -- a different error.

    Worth separating instead of folding into the CHECK cases above: `DataError`
    and `IntegrityError` are different classes, and a test that accepted either
    would keep passing if a CHECK were dropped and only the column width were
    left. The API rejects both of these at 422 before they get here.
    """
    repository = SqlAlchemyApiRepository(postgres_session)

    with pytest.raises(DataError):
        with postgres_session.begin_nested():
            repository.save_bank_recipient(
                recipient_id=uuid.uuid4(),
                bank_bin=bank_bin,
                account_number=account_number,
                account_name=None,
                now=NOW,
            )


def test_the_partial_index_really_is_partial_in_this_schema(
    postgres_session: Session,
):
    """Read the index definition rather than trusting the model declaration.

    `Index(..., postgresql_where=...)` in `models.py` is a statement of intent.
    This asserts the migration actually produced a WHERE clause, because a
    unique index without one would reject every replacement outright.
    """
    definition = postgres_session.scalar(
        text(
            "select indexdef from pg_indexes "
            "where indexname = 'uq_bank_recipients_active_recipient' "
            "and schemaname = current_schema()"
        )
    )
    assert definition is not None
    assert "UNIQUE" in definition
    assert "revoked_at IS NULL" in definition


def test_saving_leaves_no_stray_rows_for_other_people(postgres_session: Session):
    repository = SqlAlchemyApiRepository(postgres_session)
    before = postgres_session.scalar(select(func.count()).select_from(BankRecipient))

    repository.save_bank_recipient(
        recipient_id=uuid.uuid4(),
        bank_bin=FIRST_ACCOUNT[0],
        account_number=FIRST_ACCOUNT[1],
        account_name=None,
        now=NOW,
    )

    after = postgres_session.scalar(select(func.count()).select_from(BankRecipient))
    assert after == before + 1
