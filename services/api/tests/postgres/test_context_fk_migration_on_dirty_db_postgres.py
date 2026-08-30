"""Running b3c7e0d24f19 on a database that is already full of orphans.

The demo database has 10932 expenses naming groups that do not exist. The
obvious way to add this foreign key -- `ADD CONSTRAINT` and let PostgreSQL
check -- would abort on the first of them, and `alembic upgrade head` would
stop being runnable there at all. That was the reason the person who found the
bug did not fix it: adding the key needs a decision about the existing rows
first.

The migration takes the third option: `NOT VALID`, which enforces every future
write while leaving rows already present unchecked. So the answer to "what
happens to the 10932" is "nothing, on purpose, and loudly" -- deleting them
would destroy ledger rows and inventing groups for them would launder the bad
data, and neither is a migration's decision to make.

That is a claim about behaviour on dirty data, and the rest of the suite runs
on schemas that are clean by construction, so none of it can check this. This
file builds the dirty case on purpose: migrate to the revision *before* the
key, write orphans, then migrate forward and look at what survived.

What it pins:

* the upgrade completes rather than aborting;
* the orphan rows are all still there afterwards, to the row -- a migration
  that "fixed" the problem by deleting money would pass every other test in
  this repository;
* the constraint arrives unvalidated, which is the honest state for a table
  whose history was never checked;
* and it still refuses the next orphan, because enforcing new writes is the
  whole point of adding it in this shape rather than not at all.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema

from tests.postgres.conftest import API_ROOT, _configured_url, _schema_url

# The revision immediately before the one under test.
REVISION_BEFORE = "d1e2f3a4b5c6"
REVISION_UNDER_TEST = "b3c7e0d24f19"

ORPHAN_COUNT = 7


def _upgrade(schema_url: str, revision: str) -> None:
    """Run alembic against one schema, restoring the env var afterwards."""

    previous = os.environ.get("MOBILE_DATABASE_URL")
    os.environ["MOBILE_DATABASE_URL"] = schema_url
    try:
        command.upgrade(Config(str(API_ROOT / "alembic.ini")), revision)
    finally:
        if previous is None:
            os.environ.pop("MOBILE_DATABASE_URL", None)
        else:
            os.environ["MOBILE_DATABASE_URL"] = previous


@pytest.fixture
def dirty_engine() -> Generator[Engine]:
    """A schema stopped one revision short of the key, then filled with orphans.

    Its own schema rather than the session-wide one: this has to migrate in
    two steps with writes in between, which the shared fixture -- already at
    head before any test runs -- cannot express.
    """

    database_url = _configured_url()
    schema_name = "dirty_fk_it_" + uuid.uuid4().hex
    admin_engine = create_engine(database_url, pool_pre_ping=True, hide_parameters=True)
    engine: Engine | None = None
    created = False

    try:
        with admin_engine.begin() as connection:
            connection.execute(CreateSchema(schema_name))
        created = True

        scoped_url = _schema_url(database_url, schema_name)
        _upgrade(scoped_url.render_as_string(hide_password=False), REVISION_BEFORE)

        engine = create_engine(scoped_url, pool_pre_ping=True, hide_parameters=True)
        with engine.begin() as connection:
            # One group that really exists, so the assertions below can tell a
            # working key apart from a table that rejects everything.
            person_id = uuid.uuid4()
            real_context_id = uuid.uuid4()
            connection.execute(
                text("INSERT INTO people (id, display_name) VALUES (:id, 'Minh')"),
                {"id": person_id},
            )
            connection.execute(
                text(
                    "INSERT INTO contexts (id, display_name, created_by_id) "
                    "VALUES (:id, 'Nhóm có thật', :by)"
                ),
                {"id": real_context_id, "by": person_id},
            )
            connection.execute(
                text("INSERT INTO expenses (id, context_id) VALUES (:id, :ctx)"),
                {"id": uuid.uuid4(), "ctx": real_context_id},
            )
            # And the rows the demo database is full of: written here only
            # because this revision still allows them.
            connection.execute(
                text("INSERT INTO expenses (id, context_id) VALUES (:id, :ctx)"),
                [
                    {"id": uuid.uuid4(), "ctx": uuid.uuid4()}
                    for _ in range(ORPHAN_COUNT)
                ],
            )

        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin_engine.begin() as connection:
                connection.execute(
                    DropSchema(schema_name, cascade=True, if_exists=True)
                )
        admin_engine.dispose()


def test_the_key_lands_on_a_dirty_database_without_destroying_anything(
    dirty_engine: Engine,
) -> None:
    scoped_url = str(dirty_engine.url.render_as_string(hide_password=False))

    # 1. It runs at all. A validating ADD CONSTRAINT would abort right here.
    _upgrade(scoped_url, REVISION_UNDER_TEST)

    with dirty_engine.connect() as connection:
        orphans = connection.scalar(
            text(
                "SELECT count(*) FROM expenses e WHERE NOT EXISTS "
                "(SELECT 1 FROM contexts c WHERE c.id = e.context_id)"
            )
        )
        total = connection.scalar(text("SELECT count(*) FROM expenses"))
        validated = connection.scalar(
            text(
                "SELECT convalidated FROM pg_constraint "
                "WHERE conname = 'fk_expenses_context_id' "
                "AND conrelid = CAST('expenses' AS regclass)"
            )
        )

    # 2. Every orphan is still there. Nothing was quietly cleaned up.
    assert orphans == ORPHAN_COUNT
    assert total == ORPHAN_COUNT + 1

    # 3. The constraint exists but admits it never checked the history.
    assert validated is False, (
        "the key came out validated on a table with orphans in it, "
        "which PostgreSQL cannot do -- the migration is not doing what it says"
    )


def test_a_dirty_database_still_refuses_the_next_orphan(
    dirty_engine: Engine,
) -> None:
    """NOT VALID forgives the past; it does not forgive the next write.

    This is the assertion that makes the whole approach worth anything. If it
    failed, the migration would be a comment: the demo database would keep
    growing new orphans exactly as before, and the 10932 would just be the
    number as of the day somebody looked.
    """

    _upgrade(
        str(dirty_engine.url.render_as_string(hide_password=False)), REVISION_UNDER_TEST
    )

    with pytest.raises(IntegrityError):
        with dirty_engine.begin() as connection:
            connection.execute(
                text("INSERT INTO expenses (id, context_id) VALUES (:id, :ctx)"),
                {"id": uuid.uuid4(), "ctx": uuid.uuid4()},
            )
