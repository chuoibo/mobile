"""Add the private group memory table."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7c3a8f2d1e6b"
down_revision: str | Sequence[str] | None = "b2d9f4c781a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "image_url <> ''",
            name=op.f("ck_memories_image_url_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["people.id"],
            name="fk_memories_author",
        ),
        sa.ForeignKeyConstraint(
            ["context_id"],
            ["contexts.id"],
            name="fk_memories_context",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memories")),
    )
    op.create_index(
        "ix_memories_context_feed",
        "memories",
        [
            sa.text("context_id"),
            sa.text("created_at DESC"),
            sa.text("id DESC"),
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_memories_context_feed", table_name="memories")
    op.drop_table("memories")
