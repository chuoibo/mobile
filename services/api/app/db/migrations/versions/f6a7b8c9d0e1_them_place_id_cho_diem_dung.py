"""Catalogue place id on outing stops (M4).

A stop with `place_id` opens the real place detail from the timeline; one
without stays a free-text label. Text rather than a foreign key while the
catalogue is code; the service checks the key.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("outing_stops", sa.Column("place_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("outing_stops", "place_id")
