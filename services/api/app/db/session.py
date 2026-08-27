"""Lazy SQLAlchemy engine and session construction."""

from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile"
)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Build the process-wide engine only when database access is requested."""

    database_url = os.environ.get("MOBILE_DATABASE_URL", DEFAULT_DATABASE_URL)
    return create_engine(database_url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Return the process-wide SQLAlchemy session factory."""

    return sessionmaker(bind=get_engine(), expire_on_commit=False)
