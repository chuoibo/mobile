"""Isolated PostgreSQL schema migrated by Alembic for repository tests.

The ordinary suite deliberately uses a fake repository and must stay fast. This
layer is different: it refuses SQLite, migrates a unique schema in PostgreSQL,
and drops only that generated schema after the session.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.models import Context, Person
from app.places.seed_catalog import seed_place_catalog

API_ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL_ENV = "MOBILE_TEST_DATABASE_URL"
REQUIRE_POSTGRES_ENV = "MOBILE_REQUIRE_POSTGRES_TESTS"
SCHEMA_PREFIX = "repository_it_"


def _configured_url() -> URL:
    raw_url = os.environ.get(DATABASE_URL_ENV)
    if raw_url is None:
        if os.environ.get(REQUIRE_POSTGRES_ENV) == "1":
            pytest.fail(
                f"{DATABASE_URL_ENV} is required when {REQUIRE_POSTGRES_ENV}=1",
                pytrace=False,
            )
        pytest.skip(f"set {DATABASE_URL_ENV} to run PostgreSQL repository tests")

    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        pytest.fail(
            "PostgreSQL repository tests refuse non-PostgreSQL URLs", pytrace=False
        )
    return url


def _schema_url(database_url: URL, schema_name: str) -> URL:
    return database_url.update_query_dict(
        {"options": f"-csearch_path={schema_name}"}, append=False
    )


def seed_context(
    session: Session,
    context_id: uuid.UUID | None = None,
    *,
    created_by_id: uuid.UUID | None = None,
    display_name: str = "Nhóm test",
) -> uuid.UUID:
    """Persist a real context and, when needed, its synthetic creator."""

    if created_by_id is None:
        creator = Person(display_name="Người tạo test")
        session.add(creator)
        session.flush()
        created_by_id = creator.id

    context_id = context_id or uuid.uuid4()
    session.add(
        Context(
            id=context_id,
            display_name=display_name,
            created_by_id=created_by_id,
        )
    )
    session.flush()
    return context_id


@pytest.fixture(scope="session")
def postgres_engine() -> Generator[Engine]:
    database_url = _configured_url()
    schema_name = SCHEMA_PREFIX + uuid.uuid4().hex
    admin_engine = create_engine(database_url, pool_pre_ping=True, hide_parameters=True)
    test_engine: Engine | None = None
    schema_created = False

    try:
        with admin_engine.begin() as connection:
            connection.execute(CreateSchema(schema_name))
        schema_created = True

        scoped_url = _schema_url(database_url, schema_name)
        previous_application_url = os.environ.get("MOBILE_DATABASE_URL")
        os.environ["MOBILE_DATABASE_URL"] = scoped_url.render_as_string(
            hide_password=False
        )
        try:
            config = Config(str(API_ROOT / "alembic.ini"))
            command.upgrade(config, "head")
        finally:
            if previous_application_url is None:
                os.environ.pop("MOBILE_DATABASE_URL", None)
            else:
                os.environ["MOBILE_DATABASE_URL"] = previous_application_url

        test_engine = create_engine(
            scoped_url,
            pool_pre_ping=True,
            hide_parameters=True,
        )
        with test_engine.connect() as connection:
            assert connection.scalar(text("select current_schema()")) == schema_name
            assert (
                connection.scalar(text("select to_regclass('expenses')")) == "expenses"
            )

        # M9: the catalogue is a table now, so a fresh schema has no places in
        # it. Seed the same twelve invented rows the api tier fakes, or every
        # test that saves a bookmark or attaches a stop to a place would fail
        # on a catalogue that is merely empty rather than on its own subject.
        with Session(test_engine) as session:
            seed_place_catalog(session)
            session.commit()

        yield test_engine
    finally:
        if test_engine is not None:
            test_engine.dispose()
        if schema_created:
            with admin_engine.begin() as connection:
                connection.execute(
                    DropSchema(schema_name, cascade=True, if_exists=True)
                )
        admin_engine.dispose()


@pytest.fixture
def postgres_session(postgres_engine: Engine) -> Generator[Session]:
    with Session(postgres_engine, expire_on_commit=False) as session:
        try:
            yield session
        finally:
            session.rollback()
