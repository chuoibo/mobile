"""The one-shot backfill in c5f141903a2b, pinned to a scenario it can fail.

bug-141903 shut the self-promotion path by giving `memberships` an `origin`
column: rows born from a forwardable bearer link may not clear their own join
request. New rows get the right label from application code, which
`test_membership_origin_postgres.py` already proves.

Rows that already existed when the migration ran get theirs from a single
`UPDATE ... FROM` inside `upgrade()`. That statement runs exactly once, on real
data, and no test covered it. If its join were wrong the old rows would keep the
trusted `named` default and keep the escalation path the fix just closed --
silently, because nothing reads a backfill after it has run.

So this file runs the migration itself. It builds a throwaway schema at
`9e4b1c67d305` (the revision immediately before), seeds rows the way the
pre-`origin` product would have left them, upgrades to `c5f141903a2b`, and reads
the labels back.

Each seeded membership pins one clause of that UPDATE; the comments say which.
Break a clause and exactly one row flips.

Unlike the rest of this directory the test owns its schema and commits: it must
observe what a migration in its own transaction wrote. The shared
`postgres_engine` fixture is deliberately untouched -- it migrates to head, and
head is what this test needs to arrive at, not start from.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateSchema, DropSchema

from .conftest import _configured_url, _schema_url

pytestmark = pytest.mark.postgres

API_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PREFIX = "backfill_it_"

# The revision that introduced `outing_invites`, and the one under test.
BEFORE = "9e4b1c67d305"
UNDER_TEST = "c5f141903a2b"

NOW = datetime(2026, 8, 20, 3, 15, tzinfo=UTC)


@pytest.fixture
def scratch_schema() -> Generator[tuple[Engine, Callable[[str], None]]]:
    """A private schema at `BEFORE`, plus a way to migrate it forward.

    Private because the test commits. A shared schema would leak these rows into
    the row-counting tests next door, and stamping the shared `alembic_version`
    back to an older revision would strand every other file in the directory.
    """
    database_url = _configured_url()
    schema_name = SCHEMA_PREFIX + uuid.uuid4().hex
    admin_engine = create_engine(database_url, pool_pre_ping=True, hide_parameters=True)
    scoped_url = _schema_url(database_url, schema_name)
    engine: Engine | None = None

    def upgrade(revision: str) -> None:
        previous = os.environ.get("MOBILE_DATABASE_URL")
        os.environ["MOBILE_DATABASE_URL"] = scoped_url.render_as_string(
            hide_password=False
        )
        try:
            command.upgrade(Config(str(API_ROOT / "alembic.ini")), revision)
        finally:
            if previous is None:
                os.environ.pop("MOBILE_DATABASE_URL", None)
            else:
                os.environ["MOBILE_DATABASE_URL"] = previous

    try:
        with admin_engine.begin() as connection:
            connection.execute(CreateSchema(schema_name))
        upgrade(BEFORE)

        engine = create_engine(scoped_url, pool_pre_ping=True, hide_parameters=True)
        with engine.connect() as connection:
            assert connection.scalar(text("select current_schema()")) == schema_name
            # The column under test must be absent, or the test would be reading
            # a value the migration never had to compute.
            assert (
                connection.scalar(
                    text(
                        "select count(*) from information_schema.columns "
                        "where table_schema = :s and table_name = 'memberships' "
                        "and column_name = 'origin'"
                    ),
                    {"s": schema_name},
                )
                == 0
            )

        yield engine, upgrade
    finally:
        if engine is not None:
            engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema_name, cascade=True, if_exists=True))
        admin_engine.dispose()


def _person(connection, name: str) -> uuid.UUID:
    person_id = uuid.uuid4()
    connection.execute(
        text(
            "insert into people (id, display_name, created_at) "
            "values (:id, :name, :now)"
        ),
        {"id": person_id, "name": name, "now": NOW},
    )
    return person_id


def _context(connection, name: str, created_by: uuid.UUID) -> uuid.UUID:
    context_id = uuid.uuid4()
    connection.execute(
        text(
            "insert into contexts (id, display_name, created_by_id, created_at) "
            "values (:id, :name, :by, :now)"
        ),
        {"id": context_id, "name": name, "by": created_by, "now": NOW},
    )
    return context_id


def _membership(
    connection,
    *,
    context_id: uuid.UUID,
    person_id: uuid.UUID,
    state: str = "active",
) -> uuid.UUID:
    membership_id = uuid.uuid4()
    left_at = NOW if state == "left" else None
    connection.execute(
        text(
            "insert into memberships "
            "(id, context_id, person_id, state, role, joined_at, left_at, created_at) "
            "values (:id, :ctx, :person, :state, 'member', :now, :left_at, :now)"
        ),
        {
            "id": membership_id,
            "ctx": context_id,
            "person": person_id,
            "state": state,
            "now": NOW,
            "left_at": left_at,
        },
    )
    return membership_id


def _invite(
    connection,
    *,
    outing_id: uuid.UUID,
    source: str,
    invited_by: uuid.UUID,
    accepted_by: uuid.UUID,
    invited_person: uuid.UUID | None = None,
) -> None:
    # Two CHECK constraints refuse a half-built invite and they are right to:
    # `ck_outing_invites_link_carries_digest` wants a digest on links only, and
    # `ck_outing_invites_acceptance_is_whole` wants the two acceptance columns
    # set together. Seeding around them is what makes this fixture real data.
    digest = uuid.uuid4().bytes + uuid.uuid4().bytes if source == "link" else None
    connection.execute(
        text(
            "insert into outing_invites "
            "(id, outing_id, source, invited_person_id, invited_by_id, "
            " token_digest, accepted_at, accepted_by_id, created_at) "
            "values (:id, :outing, :source, :invited_person, :by, "
            " :digest, :now, :accepted_by, :now)"
        ),
        {
            "id": uuid.uuid4(),
            "outing": outing_id,
            "source": source,
            "invited_person": invited_person,
            "by": invited_by,
            "digest": digest,
            "now": NOW,
            "accepted_by": accepted_by,
        },
    )


def _outing(connection, *, context_id: uuid.UUID, created_by: uuid.UUID) -> uuid.UUID:
    outing_id = uuid.uuid4()
    connection.execute(
        text(
            "insert into outings "
            "(id, context_id, created_by_id, title, starts_on, ends_on, "
            " headcount, budget_per_person_vnd, created_at) "
            "values (:id, :ctx, :by, 'Đà Lạt 2 ngày', '2030-09-05', '2030-09-06', "
            " 4, 2500000, :now)"
        ),
        {"id": outing_id, "ctx": context_id, "by": created_by, "now": NOW},
    )
    return outing_id


def test_the_backfill_labels_link_born_rows_and_leaves_every_other_row_alone(
    scratch_schema: tuple[Engine, Callable[[str], None]],
) -> None:
    engine, upgrade = scratch_schema

    with engine.begin() as connection:
        host = _person(connection, "Minh Anh")
        link_holder = _person(connection, "Người cầm link")
        named_friend = _person(connection, "Bạn được mời đích danh")
        leaver = _person(connection, "Người đã rời nhóm")

        group = _context(connection, "Team Đà Lạt", host)
        # A second group the link holder also belongs to, so the UPDATE has
        # somewhere to spill if it forgets which outing it is talking about.
        other_group = _context(connection, "Team Nha Trang", host)

        outing = _outing(connection, context_id=group, created_by=host)

        _invite(
            connection,
            outing_id=outing,
            source="link",
            invited_by=host,
            accepted_by=link_holder,
        )
        _invite(
            connection,
            outing_id=outing,
            source="friend",
            invited_by=host,
            invited_person=named_friend,
            accepted_by=named_friend,
        )
        _invite(
            connection,
            outing_id=outing,
            source="link",
            invited_by=host,
            accepted_by=leaver,
        )

        memberships = {
            # `oi.source = 'link' AND oi.accepted_by_id = m.person_id`
            "link_holder": _membership(
                connection, context_id=group, person_id=link_holder
            ),
            # `oi.source = 'link'` -- a named invitee is not a bearer token.
            "named_friend": _membership(
                connection, context_id=group, person_id=named_friend
            ),
            # `o.context_id = m.context_id` -- same person, different group.
            "link_holder_elsewhere": _membership(
                connection, context_id=other_group, person_id=link_holder
            ),
            # `m.state <> 'left'` -- a closed membership is not re-labelled.
            "leaver": _membership(
                connection, context_id=group, person_id=leaver, state="left"
            ),
            # No invite row at all: the founder relies on the server default.
            "host": _membership(connection, context_id=group, person_id=host),
        }

    upgrade(UNDER_TEST)

    with engine.connect() as connection:
        got = {
            name: connection.scalar(
                text("select origin from memberships where id = :id"),
                {"id": membership_id},
            )
            for name, membership_id in memberships.items()
        }

    assert got == {
        "link_holder": "link",
        "named_friend": "named",
        "link_holder_elsewhere": "named",
        "leaver": "named",
        "host": "named",
    }
