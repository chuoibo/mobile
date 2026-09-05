"""Licensed photographs of catalogue places (M12, ADR-0017).

`DESIGN.md` forbade photographs on catalogue places, and the reason was sound:
the catalogue was twelve invented rows, so any picture on one was a picture of
somewhere else. The places are real now, and the rule the ADR replaced it with
is narrower rather than looser -- a photograph is allowed exactly when it can
say where it came from.

So the provenance columns are NOT NULL with non-blank CHECKs. A row that cannot
name its author, its licence and its source does not exist; it is not filtered
out on the way to the screen, because the filter is what gets forgotten.

Unique on `(place_id, source_url)`: running the importer twice is a no-op
rather than a second copy of the same photograph.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9d0e1f2a3b4"
down_revision: str | Sequence[str] | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "place_photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("place_id", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("license", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png')",
            name="place_photo_content_type_allowed",
        ),
        sa.CheckConstraint(
            "byte_size > 0 AND width > 0 AND height > 0",
            name="place_photo_dimensions_positive",
        ),
        sa.CheckConstraint(
            "length(btrim(author)) > 0 AND length(btrim(license)) > 0 "
            "AND length(btrim(source_url)) > 0",
            name="place_photo_cites_its_source",
        ),
        sa.ForeignKeyConstraint(
            ["place_id"], ["places.id"], name="fk_place_photos_place"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_place_photos"),
        sa.UniqueConstraint("storage_key", name="uq_place_photos_storage_key"),
        sa.UniqueConstraint(
            "place_id", "source_url", name="uq_place_photos_place_source"
        ),
    )
    op.create_index("ix_place_photos_place", "place_photos", ["place_id", "sort_order"])


def downgrade() -> None:
    op.drop_index("ix_place_photos_place", table_name="place_photos")
    op.drop_table("place_photos")
