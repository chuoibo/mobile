"""Profile fields and saved places (M2).

`people.bio` / `people.city`: free text a person writes about themself,
both optional, nothing derived from either.

`saved_places`: one row per (person, catalogue place) bookmark. The place id
is the catalogue key -- text rather than a foreign key while the catalogue is
code -- and the service refuses a key the catalogue does not know.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("people", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("people", sa.Column("city", sa.Text(), nullable=True))
    op.create_table(
        "saved_places",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("place_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["person_id"], ["people.id"], name="fk_saved_places_person"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saved_places")),
        sa.UniqueConstraint(
            "person_id", "place_id", name="uq_saved_places_person_place"
        ),
    )
    op.create_index("ix_saved_places_person", "saved_places", ["person_id"])


def downgrade() -> None:
    op.drop_index("ix_saved_places_person", table_name="saved_places")
    op.drop_table("saved_places")
    op.drop_column("people", "city")
    op.drop_column("people", "bio")
