"""Thêm vai trò thành viên và tin nhắn nhóm."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "4d7f2c91a8e3"
down_revision: str | Sequence[str] | None = "6ba1d0cef47a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "memberships",
        sa.Column(
            "role",
            sa.Enum(
                "member",
                "admin",
                name="membership_role",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="member",
            nullable=False,
        ),
    )
    # No explicit CHECK here on purpose. `native_enum=False` means the enum IS
    # a check constraint, and `add_column` already emitted it as
    # `ck_memberships_membership_role`. Creating it again by hand raised
    # DuplicateObject and took the whole migration -- and therefore every
    # PostgreSQL test -- down with it.

    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("context_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "text",
                "image",
                "ai_card",
                name="message_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("card", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(kind = 'text' AND body IS NOT NULL AND image_url IS NULL "
            "AND card IS NULL) OR "
            "(kind = 'image' AND image_url IS NOT NULL AND card IS NULL) OR "
            "(kind = 'ai_card' AND card IS NOT NULL AND image_url IS NULL "
            "AND body IS NULL)",
            name=op.f("ck_messages_payload_matches_kind"),
        ),
        sa.CheckConstraint(
            "kind = 'ai_card' OR author_id IS NOT NULL",
            name=op.f("ck_messages_human_kinds_have_author"),
        ),
        sa.ForeignKeyConstraint(
            ["author_id"], ["people.id"], name="fk_messages_author_id"
        ),
        sa.ForeignKeyConstraint(
            ["context_id"], ["contexts.id"], name="fk_messages_context_id"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index(
        "ix_messages_context_feed",
        "messages",
        [
            sa.text("context_id"),
            sa.text("created_at DESC"),
            sa.text("id DESC"),
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_context_feed", table_name="messages")
    op.drop_table("messages")
    # PostgreSQL drops a CHECK constraint together with the only column it
    # references, so the enum constraint needs no separate statement.
    op.drop_column("memberships", "role")
