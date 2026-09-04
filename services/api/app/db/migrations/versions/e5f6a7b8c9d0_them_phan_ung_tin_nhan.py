"""Message reactions (M3).

One row per (message, person, kind); `kind` is a closed key the database
checks, so a screen never renders text a stranger chose.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "message_reactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('heart', 'haha', 'like', 'wow', 'sad', 'fire')",
            name=op.f("ck_message_reactions_reaction_kind_known"),
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["messages.id"], name="fk_message_reactions_message"
        ),
        sa.ForeignKeyConstraint(
            ["person_id"], ["people.id"], name="fk_message_reactions_person"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_reactions")),
        sa.UniqueConstraint(
            "message_id", "person_id", "kind", name="uq_message_reactions_one_per_kind"
        ),
    )
    op.create_index("ix_message_reactions_message", "message_reactions", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_message_reactions_message", table_name="message_reactions")
    op.drop_table("message_reactions")
