"""Add hearts (F40) and comments (F41) to the group memory wall.

Two tables and not one column on `memories`. A counter column on the memory
row would be a cache of a fact the rows themselves hold, and a cache is the
one thing invariant 3 says may never be the source of truth -- two devices
pressing the heart in the same instant would both read 17 and both write 18.

Both tables cascade from `memories`: a heart or a sentence about a photograph
that no longer exists is a row no screen can draw.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5e14b7a9d02"
down_revision: str | Sequence[str] | None = "f1a6d38b0e57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_reactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["memory_id"],
            ["memories.id"],
            name="fk_memory_reactions_memory",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["people.id"],
            name="fk_memory_reactions_person",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_reactions")),
        # One person, one heart. Held by the database and not by an
        # `if not exists` in Python, which two concurrent requests both pass.
        sa.UniqueConstraint(
            "memory_id", "person_id", name="uq_memory_reactions_person"
        ),
    )
    op.create_index("ix_memory_reactions_memory", "memory_reactions", ["memory_id"])

    op.create_table(
        "memory_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "body <> ''", name=op.f("ck_memory_comments_body_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["people.id"],
            name="fk_memory_comments_author",
        ),
        sa.ForeignKeyConstraint(
            ["memory_id"],
            ["memories.id"],
            name="fk_memory_comments_memory",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_comments")),
    )
    op.create_index(
        "ix_memory_comments_memory",
        "memory_comments",
        ["memory_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_memory_comments_memory", table_name="memory_comments")
    op.drop_table("memory_comments")
    op.drop_index("ix_memory_reactions_memory", table_name="memory_reactions")
    op.drop_table("memory_reactions")
