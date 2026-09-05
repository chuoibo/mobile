"""«Nên làm gì ở đây», one column on `places` (M12, ADR-0017 §2.3).

Derived from the row's own OpenStreetMap tags when the importer writes it: a
`leisure=park` is a place you walk in, an `outdoor_seating=yes` is a place you
sit outside. Every phrase traces to a tag somebody put on the map.

Not a model's sentence, and not computed per request. A model handed a name and
a category writes fluent prose about a venue it has never seen; a phrase
computed on read changes between two renders of the same place and costs a
model call on a screen open. This column is written once, by the import.

NULL rather than `'[]'`: a row written before this column existed has not been
looked at yet, which is a different fact from a row the importer examined and
found nothing to say about. Both draw as no line on screen.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d0e1f2a3b4c5"
down_revision: str | Sequence[str] | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "places",
        sa.Column("activities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("places", "activities")
