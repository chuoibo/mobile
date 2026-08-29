"""Add the scanned bill draft tables.

Revision ID: a13f7c9e24b6
Revises: 6ba1d0cef47a

The share-source enum creates its own check constraint because it is a
non-native SQLAlchemy enum. A second explicit check for the same enum would
duplicate the generated constraint and make the migration fail.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a13f7c9e24b6"
down_revision: str | Sequence[str] | None = "4d7f2c91a8e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bills",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("printed_total_vnd", sa.BigInteger(), nullable=True),
        sa.Column("items_total_vnd", sa.BigInteger(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 100",
            name=op.f("ck_bills_confidence_range"),
        ),
        sa.CheckConstraint(
            "printed_total_vnd IS NULL OR printed_total_vnd >= 0",
            name=op.f("ck_bills_printed_total_nonnegative"),
        ),
        sa.CheckConstraint(
            "items_total_vnd >= 0",
            name=op.f("ck_bills_items_total_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bills")),
    )
    op.create_index(op.f("ix_bills_context_id"), "bills", ["context_id"], unique=False)

    op.create_table(
        "bill_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_vnd", sa.BigInteger(), nullable=True),
        sa.Column("line_total_vnd", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "line_total_vnd > 0",
            name=op.f("ck_bill_items_line_total_positive"),
        ),
        sa.CheckConstraint(
            "quantity > 0", name=op.f("ck_bill_items_quantity_positive")
        ),
        sa.ForeignKeyConstraint(["bill_id"], ["bills.id"], name="fk_bill_items_bill"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bill_items")),
        sa.UniqueConstraint("bill_id", "item_key", name="uq_bill_items_bill_item_key"),
    )
    op.create_index(
        op.f("ix_bill_items_bill_id"),
        "bill_items",
        ["bill_id"],
        unique=False,
    )

    op.create_table(
        "bill_item_shares",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "ai_suggested",
                "confirmed",
                name="bill_share_source",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("decided_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(source = 'confirmed' AND decided_by_id IS NOT NULL AND "
            "decided_at IS NOT NULL) OR "
            "(source = 'ai_suggested' AND decided_by_id IS NULL AND "
            "decided_at IS NULL)",
            name=op.f("ck_bill_item_shares_decision_matches_source"),
        ),
        sa.ForeignKeyConstraint(
            ["bill_item_id"],
            ["bill_items.id"],
            name="fk_bill_item_shares_item",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bill_item_shares")),
        sa.UniqueConstraint(
            "bill_item_id",
            "participant_id",
            name="uq_bill_item_shares_item_participant",
        ),
    )
    op.create_index(
        op.f("ix_bill_item_shares_bill_item_id"),
        "bill_item_shares",
        ["bill_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_bill_item_shares_bill_item_id"),
        table_name="bill_item_shares",
    )
    op.drop_table("bill_item_shares")
    op.drop_index(op.f("ix_bill_items_bill_id"), table_name="bill_items")
    op.drop_table("bill_items")
    op.drop_index(op.f("ix_bills_context_id"), table_name="bills")
    op.drop_table("bills")
