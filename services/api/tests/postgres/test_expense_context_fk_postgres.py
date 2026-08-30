"""`context_id` on the three money tables must point at a group that exists.

`bills`, `expenses` and `collection_batches` were created by the initial
schema, before `contexts` had a table at all. When `contexts` arrived it
retrofitted no foreign key onto them, so their `context_id` stayed what the
`Context` docstring already calls out: a plain UUID pointing at nothing. Every
table added afterwards -- `memberships`, `outings`, `messages`, `posts`,
`votes`, `memories`, `uploaded_images` -- got the key. These three were left
behind, and nothing since has noticed.

What that costs is not theoretical. On the demo database on 2026-08-30,
`public.expenses` carried 10932 rows whose `context_id` matched no row in
`contexts`, 7308 of them with confirmed allocations behind them. Their money
still reaches `GET /people/{id}/finance`, because the spend query walks
`confirmed_allocations -> expense_versions` and never joins `contexts` at all.
So the personal screen adds up đồng from a group that cannot name itself.

The trap to know about when auditing this: an inner JOIN from `expenses` to
`contexts` drops those rows *silently*, and drops them in the flattering
direction -- the reconciliation total comes out smaller, so a checker reports
"clean" while the screen keeps counting. The first measurement of this bug was
off by 329.667đ for exactly that reason. Any query written to audit `expenses`
has to LEFT JOIN or it will agree with itself instead of with the product.

The fix asserted here is the key itself, in both directions:

* nothing may be written into these tables for a group that does not exist;
* and a group that still holds money may not be deleted out from under it,
  which is the other way rows in a live database turn into orphans.

Deliberately not asserted: that any *existing* orphan has been cleaned up.
Removing rows from the ledger is not a schema decision, and the money laws
forbid both silently deleting them and inventing the groups they point at.
The migration therefore enforces every future write and leaves history alone;
see its docstring for what that means for a database that is already dirty.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.repository import SqlAlchemyApiRepository
from app.db.models import Bill, CollectionBatch, Context, Expense, Person

NOW = datetime(2030, 8, 30, 9, 0, tzinfo=UTC)

# The id the demo database carried 10881 orphan expenses under. Hand-written
# rather than generated, which is how it survived: no group was ever created
# to match it, and nothing asked.
DEMO_ORPHAN_CONTEXT_ID = uuid.UUID("1aa00000-aaaa-4aaa-8aaa-0000a0000001")

MONEY_TABLES = ("bills", "expenses", "collection_batches")


def _person(session: Session, name: str = "Minh") -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _context(session: Session, created_by_id: uuid.UUID) -> Context:
    context = Context(
        id=uuid.uuid4(), display_name="Nhóm ăn tối", created_by_id=created_by_id
    )
    session.add(context)
    session.flush()
    return context


def _context_foreign_key(session: Session, table: str) -> dict[str, object] | None:
    """The FK on `<table>.context_id`, as PostgreSQL actually holds it.

    Read from `pg_constraint` rather than from SQLAlchemy's reflection so the
    answer comes from the migrated database and not from the models file that
    is supposed to describe it. `convalidated` is carried out because a
    constraint added `NOT VALID` enforces new writes but has never checked the
    rows already there -- a real and useful state, and one worth being unable
    to confuse with a fully checked key.

    `::regclass` resolves against `search_path`, which the session fixture has
    pinned to this test's own schema.
    """

    row = session.execute(
        text(
            """
            SELECT c.conname,
                   c.convalidated,
                   confrel.relname AS referenced_table,
                   att.attname     AS column_name
              FROM pg_constraint c
              JOIN pg_class confrel ON confrel.oid = c.confrelid
              JOIN unnest(c.conkey) AS k(attnum) ON TRUE
              JOIN pg_attribute att
                ON att.attrelid = c.conrelid AND att.attnum = k.attnum
             WHERE c.conrelid = CAST(:table AS regclass)
               AND c.contype = 'f'
               AND att.attname = 'context_id'
            """
        ),
        {"table": table},
    ).mappings().one_or_none()
    return dict(row) if row else None


@pytest.mark.parametrize("table", MONEY_TABLES)
def test_money_table_context_id_points_at_contexts(
    postgres_session: Session, table: str
) -> None:
    """The column claims to name a group; the database has to agree."""

    foreign_key = _context_foreign_key(postgres_session, table)

    assert foreign_key is not None, (
        f"{table}.context_id has no foreign key: any UUID is a valid group"
    )
    assert foreign_key["referenced_table"] == "contexts"
    # A freshly migrated schema has no history to forgive, so the key must come
    # out fully checked here. If this ever reads False on a clean migrate, the
    # migration has quietly downgraded itself and the guarantee is weaker than
    # this file claims.
    assert foreign_key["convalidated"] is True, (
        f"{table}.context_id foreign key exists but was never validated"
    )


def test_ledger_refuses_an_expense_for_a_group_that_does_not_exist(
    postgres_session: Session,
) -> None:
    """The exact row the demo database is full of, through the real write path.

    `SqlAlchemyApiRepository.create_expense` takes `context_id` straight from
    the request body and writes it. This asserts against that method rather
    than against a hand-built model so the guarantee covers the code the API
    actually runs.
    """

    repository = SqlAlchemyApiRepository(postgres_session)

    with pytest.raises(IntegrityError):
        repository.create_expense(DEMO_ORPHAN_CONTEXT_ID)
        postgres_session.flush()


def test_ledger_refuses_a_bill_for_a_group_that_does_not_exist(
    postgres_session: Session,
) -> None:
    postgres_session.add(
        Bill(
            id=uuid.uuid4(),
            context_id=uuid.uuid4(),
            created_by_id=_person(postgres_session).id,
            printed_total_vnd=None,
            items_total_vnd=0,
            confidence=100,
            needs_review=False,
        )
    )
    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_ledger_refuses_a_collection_batch_for_a_group_that_does_not_exist(
    postgres_session: Session,
) -> None:
    postgres_session.add(
        CollectionBatch(
            id=uuid.uuid4(),
            context_id=uuid.uuid4(),
            owner_id=_person(postgres_session).id,
        )
    )
    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_deleting_a_group_that_still_holds_money_is_refused(
    postgres_session: Session,
) -> None:
    """The other road to an orphan, and the one a live database takes.

    Blocking the write only stops rows being *born* pointing nowhere. A group
    deleted while its expenses remain turns every one of them into an orphan
    at once, retroactively, and the personal screen goes on adding up their
    đồng under a name that no longer resolves. RESTRICT is what makes the
    ledger outrank the group row.
    """

    person = _person(postgres_session)
    context = _context(postgres_session, person.id)
    postgres_session.add(Expense(id=uuid.uuid4(), context_id=context.id))
    postgres_session.flush()

    with pytest.raises(IntegrityError):
        postgres_session.execute(
            text("DELETE FROM contexts WHERE id = :id"), {"id": context.id}
        )
        postgres_session.flush()


def test_an_expense_for_a_real_group_is_still_written(
    postgres_session: Session,
) -> None:
    """The positive control.

    Without this, every assertion above would still pass if the foreign key
    were pointed at the wrong column and refused *everything*. A test file
    that only proves things get rejected cannot tell a working key from a
    broken table.
    """

    person = _person(postgres_session)
    context = _context(postgres_session, person.id)

    identity = SqlAlchemyApiRepository(postgres_session).create_expense(context.id)
    postgres_session.flush()

    assert identity.context_id == context.id
    assert (
        postgres_session.scalar(
            text("SELECT count(*) FROM expenses WHERE id = :id"), {"id": identity.id}
        )
        == 1
    )
