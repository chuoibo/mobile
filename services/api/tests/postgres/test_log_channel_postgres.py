"""The log channel every privacy assertion in this tier reads must be alive.

Alembic's `env.py` calls `logging.config.fileConfig`, whose
`disable_existing_loggers` defaults to True, so migrating used to switch off
every `app.*` logger that import order had already created. `#182` fixed that
at the root by naming `app` in `services/api/alembic.ini`, and
`tests/test_migration_keeps_app_loggers.py` guards it there.

This file is deliberately not that gate again. That one runs alembic offline
and proves migrating no longer kills the channel; it says in its own words that
it does not prove any particular `not in caplog.text` assertion is reading a
live channel. This one closes exactly that gap, from inside the tier where
those assertions actually run: after the real session fixture has migrated a
real schema, the loggers are still enabled and a record still reaches `caplog`.

Why the gap is worth its own file: an assertion shaped
`assert SECRET not in caplog.text` is satisfied perfectly by a dead channel.
It fails open, and it fails silently. The two guards differ in what could
break them -- `alembic.ini` losing `app` breaks the first, while anything at
all that empties `caplog` in this tier breaks this one.
"""

from __future__ import annotations

import logging

import pytest
from sqlalchemy.orm import Session

# Imported at module scope on purpose: this is what makes the logger exist
# before the session fixture migrates, which is the exact condition that used
# to switch it off. Importing it inside the test would create the logger after
# `fileConfig` had already run, and the bug would hide.
import app.api.service  # noqa: F401

pytestmark = pytest.mark.postgres

CANARY = "CANARY-log-channel-con-song"


def _disabled_application_loggers() -> list[str]:
    return sorted(
        name
        for name, logger in logging.getLogger().manager.loggerDict.items()
        if name.startswith("app.")
        and isinstance(logger, logging.Logger)
        and logger.disabled
    )


def test_migrating_the_schema_leaves_every_application_logger_enabled(
    postgres_session: Session,
) -> None:
    """Alembic may configure its own loggers; it may not switch off ours."""

    assert _disabled_application_loggers() == []


def test_a_module_level_logger_still_reaches_caplog_after_migration(
    postgres_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """The channel the privacy cases read is open, not merely empty."""

    with caplog.at_level(logging.DEBUG):
        logging.getLogger("app.api.service").warning(CANARY)

    assert [record for record in caplog.records if record.name == "app.api.service"], (
        "no record from app.api.service reached caplog: the channel every "
        "'secret not in caplog.text' assertion in this tier reads is dead"
    )
    assert CANARY in caplog.text
