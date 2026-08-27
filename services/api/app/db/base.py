"""Shared SQLAlchemy declarative base and naming conventions."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    # The referred table name is dropped on purpose. Including it pushed
    # fk_bank_recipient_snapshots_batch_version_id_collection_batch_versions
    # to 70 characters and PostgreSQL truncates identifiers at 63, so the
    # migration would not compile at all. Table plus column is already unique.
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base for all database models owned by the API infrastructure layer."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

