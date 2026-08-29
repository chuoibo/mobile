"""Retain bill surcharges and discounts for allocator projection.

Revision ID: b2d9f4c781a0
Revises: a13f7c9e24b6

Bill drafts already retain item lines, but dropping VAT, service charges, and
discounts makes the stored draft disagree with the printed total. These tables
preserve every allocator-relevant line until the bill is projected.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2d9f4c781a0"
down_revision: str | Sequence[str] | None = "a13f7c9e24b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SURCHARGE_MODE_ENUM_NAME = "surcharge_mode"
DISCOUNT_SCOPE_ENUM_NAME = "discount_scope"


def upgrade() -> None:
    op.create_table(
        "bill_surcharges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("surcharge_key", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
        sa.Column(
            "mode",
            sa.Enum(
                "proportional",
                "even",
                name=SURCHARGE_MODE_ENUM_NAME,
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount_vnd > 0",
            name=op.f("ck_bill_surcharges_amount_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["bill_id"],
            ["bills.id"],
            name="fk_bill_surcharges_bill",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bill_surcharges")),
        sa.UniqueConstraint(
            "bill_id",
            "surcharge_key",
            name="uq_bill_surcharges_bill_surcharge_key",
        ),
    )
    op.create_index(
        op.f("ix_bill_surcharges_bill_id"),
        "bill_surcharges",
        ["bill_id"],
        unique=False,
    )

    op.create_table(
        "bill_discounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discount_key", sa.String(length=64), nullable=False),
        sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
        sa.Column(
            "scope",
            sa.Enum(
                "global_proportional",
                "item",
                name=DISCOUNT_SCOPE_ENUM_NAME,
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("target_item_key", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "amount_vnd > 0",
            name=op.f("ck_bill_discounts_amount_positive"),
        ),
        sa.CheckConstraint(
            "(scope = 'item' AND target_item_key IS NOT NULL) OR "
            "(scope = 'global_proportional' AND target_item_key IS NULL)",
            name=op.f("ck_bill_discounts_scope_target_match"),
        ),
        sa.ForeignKeyConstraint(
            ["bill_id"],
            ["bills.id"],
            name="fk_bill_discounts_bill",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bill_discounts")),
        sa.UniqueConstraint(
            "bill_id",
            "discount_key",
            name="uq_bill_discounts_bill_discount_key",
        ),
    )
    op.create_index(
        op.f("ix_bill_discounts_bill_id"),
        "bill_discounts",
        ["bill_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_bill_discounts_bill_id"),
        table_name="bill_discounts",
    )
    op.drop_table("bill_discounts")
    op.drop_index(
        op.f("ix_bill_surcharges_bill_id"),
        table_name="bill_surcharges",
    )
    op.drop_table("bill_surcharges")
