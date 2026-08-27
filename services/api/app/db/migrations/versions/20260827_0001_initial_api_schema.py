"""Create the first expense and collection schema.

Revision ID: 20260827_0001
Revises: None
Create Date: 2026-08-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260827_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_expenses"),
    )
    op.create_index("ix_expenses_context_id", "expenses", ["context_id"])

    op.create_table(
        "collection_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "accruing",
                "frozen",
                "published",
                "collecting",
                "completed",
                "closed_with_exceptions",
                "cancelled",
                name="collection_batch_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="accruing",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collecting_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_collection_batches"),
    )
    op.create_index(
        "ix_collection_batches_context_id", "collection_batches", ["context_id"]
    )

    op.create_table(
        "bank_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_bin", sa.String(length=6), nullable=False),
        sa.Column("account_number", sa.String(length=19), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=True),
        sa.Column(
            "confirmed_by_recipient_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "account_number ~ '^[A-Za-z0-9]{1,19}$'",
            name="ck_bank_recipients_account_number_format",
        ),
        sa.CheckConstraint(
            "bank_bin ~ '^[0-9]{6}$'", name="ck_bank_recipients_bank_bin_format"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bank_recipients"),
    )
    op.create_index(
        "ix_bank_recipients_recipient_id", "bank_recipients", ["recipient_id"]
    )
    op.create_index(
        "uq_bank_recipients_active_recipient",
        "bank_recipients",
        ["recipient_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "expense_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expense_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("previous_version_number", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("recorded_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("paid_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "payer_acknowledgement",
            sa.Enum(
                "pending",
                "acknowledged",
                "disputed",
                name="payer_acknowledgement",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "verification_scope",
            sa.Enum(
                "totals_only",
                "items_reviewed",
                name="verification_scope",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("subtotal_amount_vnd", sa.BigInteger(), nullable=False),
        sa.Column(
            "fee_amount_vnd", sa.BigInteger(), server_default="0", nullable=False
        ),
        sa.Column(
            "vat_amount_vnd", sa.BigInteger(), server_default="0", nullable=False
        ),
        sa.Column(
            "shipping_amount_vnd", sa.BigInteger(), server_default="0", nullable=False
        ),
        sa.Column(
            "discount_amount_vnd", sa.BigInteger(), server_default="0", nullable=False
        ),
        sa.Column("total_amount_vnd", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "discount_amount_vnd >= 0",
            name="ck_expense_versions_discount_nonnegative",
        ),
        sa.CheckConstraint(
            "fee_amount_vnd >= 0", name="ck_expense_versions_fee_nonnegative"
        ),
        sa.CheckConstraint(
            "shipping_amount_vnd >= 0",
            name="ck_expense_versions_shipping_nonnegative",
        ),
        sa.CheckConstraint(
            "subtotal_amount_vnd >= 0",
            name="ck_expense_versions_subtotal_nonnegative",
        ),
        sa.CheckConstraint(
            "total_amount_vnd >= 0", name="ck_expense_versions_total_nonnegative"
        ),
        sa.CheckConstraint(
            "total_amount_vnd = subtotal_amount_vnd + fee_amount_vnd + "
            "vat_amount_vnd + shipping_amount_vnd - discount_amount_vnd",
            name="ck_expense_versions_total_components_match",
        ),
        sa.CheckConstraint(
            "vat_amount_vnd >= 0", name="ck_expense_versions_vat_nonnegative"
        ),
        sa.CheckConstraint(
            "(version_number = 1 AND previous_version_number IS NULL) OR "
            "(version_number > 1 AND previous_version_number = version_number - 1)",
            name="ck_expense_versions_version_chain",
        ),
        sa.ForeignKeyConstraint(
            ["expense_id"], ["expenses.id"], name="fk_expense_versions_expense_id_expenses"
        ),
        sa.ForeignKeyConstraint(
            ["expense_id", "previous_version_number"],
            ["expense_versions.expense_id", "expense_versions.version_number"],
            name="fk_expense_versions_previous_version",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_expense_versions"),
        sa.UniqueConstraint(
            "expense_id",
            "version_number",
            name="uq_expense_versions_expense_version",
        ),
    )
    op.create_index(
        "ix_expense_versions_expense_id", "expense_versions", ["expense_id"]
    )

    op.create_table(
        "collection_batch_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("previous_version_number", sa.Integer(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(version_number = 1 AND previous_version_number IS NULL) OR "
            "(version_number > 1 AND previous_version_number = version_number - 1)",
            name="ck_collection_batch_versions_version_chain",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["collection_batches.id"],
            name="fk_collection_batch_versions_batch_id_collection_batches",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id", "previous_version_number"],
            [
                "collection_batch_versions.batch_id",
                "collection_batch_versions.version_number",
            ],
            name="fk_batch_versions_previous_version",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collection_batch_versions"),
        sa.UniqueConstraint(
            "batch_id", "version_number", name="uq_batch_versions_batch_version"
        ),
    )
    op.create_index(
        "ix_collection_batch_versions_batch_id",
        "collection_batch_versions",
        ["batch_id"],
    )

    op.create_table(
        "confirmed_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "expense_version_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
        sa.Column("confirmed_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount_vnd >= 0", name="ck_confirmed_allocations_amount_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["expense_version_id"],
            ["expense_versions.id"],
            name="fk_confirmed_allocations_expense_version_id_expense_versions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_confirmed_allocations"),
        sa.UniqueConstraint(
            "expense_version_id",
            "participant_id",
            name="uq_confirmed_allocations_version_participant",
        ),
    )
    op.create_index(
        "ix_confirmed_allocations_expense_version_id",
        "confirmed_allocations",
        ["expense_version_id"],
    )

    op.create_table(
        "bank_recipient_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_bin", sa.String(length=6), nullable=False),
        sa.Column("account_number", sa.String(length=19), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=True),
        sa.Column(
            "confirmed_by_recipient_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "snapshotted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "account_number ~ '^[A-Za-z0-9]{1,19}$'",
            name="ck_bank_recipient_snapshots_account_number_format",
        ),
        sa.CheckConstraint(
            "bank_bin ~ '^[0-9]{6}$'",
            name="ck_bank_recipient_snapshots_bank_bin_format",
        ),
        sa.ForeignKeyConstraint(
            ["bank_recipient_id"],
            ["bank_recipients.id"],
            name="fk_bank_recipient_snapshots_bank_recipient_id_bank_recipients",
        ),
        sa.ForeignKeyConstraint(
            ["batch_version_id"],
            ["collection_batch_versions.id"],
            name=(
                "fk_bank_recipient_snapshots_batch_version_id_"
                "collection_batch_versions"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bank_recipient_snapshots"),
        sa.UniqueConstraint(
            "batch_version_id",
            "recipient_id",
            name="uq_bank_snapshots_batch_recipient",
        ),
        sa.UniqueConstraint(
            "id", "batch_version_id", name="uq_bank_snapshots_id_batch_version"
        ),
    )
    op.create_index(
        "ix_bank_recipient_snapshots_batch_version_id",
        "bank_recipient_snapshots",
        ["batch_version_id"],
    )

    op.create_table(
        "collection_obligations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "bank_recipient_snapshot_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount_vnd > 0", name="ck_collection_obligations_amount_positive"
        ),
        sa.CheckConstraint(
            "sender_id <> recipient_id",
            name="ck_collection_obligations_different_parties",
        ),
        sa.ForeignKeyConstraint(
            ["bank_recipient_snapshot_id", "batch_version_id"],
            [
                "bank_recipient_snapshots.id",
                "bank_recipient_snapshots.batch_version_id",
            ],
            name="fk_obligations_snapshot_same_batch_version",
        ),
        sa.ForeignKeyConstraint(
            ["batch_version_id"],
            ["collection_batch_versions.id"],
            name=(
                "fk_collection_obligations_batch_version_id_"
                "collection_batch_versions"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collection_obligations"),
        sa.UniqueConstraint(
            "batch_version_id",
            "sender_id",
            "recipient_id",
            name="uq_obligations_batch_sender_recipient",
        ),
    )
    op.create_index(
        "ix_collection_obligations_batch_version_id",
        "collection_obligations",
        ["batch_version_id"],
    )

    op.create_table(
        "collection_obligation_sources",
        sa.Column("obligation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "confirmed_allocation_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount_vnd > 0", name="ck_collection_obligation_sources_amount_positive"
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_allocation_id"],
            ["confirmed_allocations.id"],
            name=(
                "fk_collection_obligation_sources_confirmed_allocation_id_"
                "confirmed_allocations"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["obligation_id"],
            ["collection_obligations.id"],
            name=(
                "fk_collection_obligation_sources_obligation_id_"
                "collection_obligations"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "obligation_id",
            "confirmed_allocation_id",
            name="pk_collection_obligation_sources",
        ),
    )
    op.create_index(
        "ix_collection_obligation_sources_confirmed_allocation_id",
        "collection_obligation_sources",
        ["confirmed_allocation_id"],
    )

    op.create_table(
        "collection_envelopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["batch_version_id"],
            ["collection_batch_versions.id"],
            name=(
                "fk_collection_envelopes_batch_version_id_"
                "collection_batch_versions"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collection_envelopes"),
        sa.UniqueConstraint(
            "batch_version_id",
            "sender_id",
            name="uq_collection_envelopes_batch_sender",
        ),
    )
    op.create_index(
        "ix_collection_envelopes_batch_version_id",
        "collection_envelopes",
        ["batch_version_id"],
    )

    op.create_table(
        "guest_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("envelope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "revoked",
                "expired",
                "rotated",
                name="guest_link_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "capability_exposed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("first_opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_from_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "expires_at > created_at", name="ck_guest_links_expiry_after_creation"
        ),
        sa.ForeignKeyConstraint(
            ["envelope_id"],
            ["collection_envelopes.id"],
            name="fk_guest_links_envelope_id_collection_envelopes",
        ),
        sa.ForeignKeyConstraint(
            ["rotated_from_id"],
            ["guest_links.id"],
            name="fk_guest_links_rotated_from_id_guest_links",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_guest_links"),
        sa.UniqueConstraint("rotated_from_id", name="uq_guest_links_rotated_from"),
        sa.UniqueConstraint("token_digest", name="uq_guest_links_token_digest"),
    )
    op.create_index("ix_guest_links_envelope_id", "guest_links", ["envelope_id"])

    op.create_table(
        "payment_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("obligation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("guest_link_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reported_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "reported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount_vnd > 0", name="ck_payment_reports_amount_positive"
        ),
        sa.ForeignKeyConstraint(
            ["guest_link_id"],
            ["guest_links.id"],
            name="fk_payment_reports_guest_link_id_guest_links",
        ),
        sa.ForeignKeyConstraint(
            ["obligation_id"],
            ["collection_obligations.id"],
            name="fk_payment_reports_obligation_id_collection_obligations",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_payment_reports"),
        sa.UniqueConstraint("idempotency_key", name="uq_payment_reports_idempotency_key"),
        sa.UniqueConstraint(
            "id", "obligation_id", name="uq_payment_reports_id_obligation"
        ),
    )
    op.create_index(
        "ix_payment_reports_obligation_id", "payment_reports", ["obligation_id"]
    )

    op.create_table(
        "receipt_confirmations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("obligation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confirmed_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount_vnd > 0", name="ck_receipt_confirmations_amount_positive"
        ),
        sa.ForeignKeyConstraint(
            ["obligation_id"],
            ["collection_obligations.id"],
            name=(
                "fk_receipt_confirmations_obligation_id_collection_obligations"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["payment_report_id", "obligation_id"],
            ["payment_reports.id", "payment_reports.obligation_id"],
            name="fk_receipt_confirmations_report_same_obligation",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_receipt_confirmations"),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_receipt_confirmations_idempotency_key"
        ),
    )
    op.create_index(
        "ix_receipt_confirmations_obligation_id",
        "receipt_confirmations",
        ["obligation_id"],
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "event_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index(
        "ix_audit_events_aggregate_id", "audit_events", ["aggregate_id"]
    )
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])

    op.execute(
        sa.text(
            """
            CREATE VIEW collection_obligation_progress AS
            SELECT
                obligation.id AS obligation_id,
                obligation.amount_vnd,
                COALESCE(SUM(confirmation.amount_vnd), 0)::bigint
                    AS confirmed_amount_vnd,
                GREATEST(
                    obligation.amount_vnd
                        - COALESCE(SUM(confirmation.amount_vnd), 0),
                    0
                )::bigint AS remaining_amount_vnd,
                CASE
                    WHEN COALESCE(SUM(confirmation.amount_vnd), 0) = 0
                        THEN 'unconfirmed'
                    WHEN COALESCE(SUM(confirmation.amount_vnd), 0)
                        < obligation.amount_vnd
                        THEN 'partially_confirmed'
                    WHEN COALESCE(SUM(confirmation.amount_vnd), 0)
                        = obligation.amount_vnd
                        THEN 'confirmed'
                    ELSE 'over_confirmed'
                END AS confirmation_state
            FROM collection_obligations AS obligation
            LEFT JOIN receipt_confirmations AS confirmation
                ON confirmation.obligation_id = obligation.id
            GROUP BY obligation.id, obligation.amount_vnd
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION reject_immutable_financial_row_change()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION '% is append-only', TG_TABLE_NAME
                    USING ERRCODE = '55000';
            END;
            $$
            """
        )
    )
    immutable_tables = (
        "expense_versions",
        "confirmed_allocations",
        "collection_batch_versions",
        "bank_recipient_snapshots",
        "collection_obligations",
        "collection_obligation_sources",
        "collection_envelopes",
        "payment_reports",
        "receipt_confirmations",
        "audit_events",
    )
    for table_name in immutable_tables:
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER reject_{table_name}_mutation
                BEFORE UPDATE OR DELETE ON {table_name}
                FOR EACH ROW
                EXECUTE FUNCTION reject_immutable_financial_row_change()
                """
            )
        )


    # --- Added under review blockers D-02 and D-03 -------------------------
    # The migration has not been deployed anywhere, so it is amended in place
    # rather than chained behind a second revision.
    op.create_table(
        "expense_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("expense_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.Text()),
        sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["expense_version_id"], ["expense_versions.id"]),
        sa.CheckConstraint("amount_vnd > 0", name="ck_expense_items_amount_positive"),
        sa.UniqueConstraint("expense_version_id", "item_key", name="uq_expense_items_version_key"),
    )
    op.create_index("ix_expense_items_expense_version_id", "expense_items", ["expense_version_id"])

    op.create_table(
        "expense_item_shares",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("expense_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["expense_item_id"], ["expense_items.id"]),
        sa.UniqueConstraint("expense_item_id", "participant_id", name="uq_item_share_unique"),
    )
    op.create_index("ix_expense_item_shares_expense_item_id", "expense_item_shares", ["expense_item_id"])

    op.create_table(
        "expense_surcharges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("expense_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("surcharge_key", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
        sa.Column(
            "mode",
            sa.Enum("proportional", "even", name="surcharge_mode", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["expense_version_id"], ["expense_versions.id"]),
        sa.CheckConstraint("amount_vnd > 0", name="ck_expense_surcharges_amount_positive"),
        sa.UniqueConstraint("expense_version_id", "surcharge_key", name="uq_surcharges_version_key"),
    )
    op.create_index("ix_expense_surcharges_expense_version_id", "expense_surcharges", ["expense_version_id"])

    op.create_table(
        "expense_discounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("expense_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discount_key", sa.String(length=64), nullable=False),
        sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
        sa.Column(
            "scope",
            sa.Enum("global_proportional", "item", name="discount_scope", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("target_item_id", postgresql.UUID(as_uuid=True)),
        sa.ForeignKeyConstraint(["expense_version_id"], ["expense_versions.id"]),
        sa.ForeignKeyConstraint(["target_item_id"], ["expense_items.id"]),
        sa.CheckConstraint("amount_vnd > 0", name="ck_expense_discounts_amount_positive"),
        sa.CheckConstraint(
            "(scope = 'item' AND target_item_id IS NOT NULL) OR "
            "(scope = 'global_proportional' AND target_item_id IS NULL)",
            name="ck_expense_discounts_scope_target_match",
        ),
        sa.UniqueConstraint("expense_version_id", "discount_key", name="uq_discounts_version_key"),
    )
    op.create_index("ix_expense_discounts_expense_version_id", "expense_discounts", ["expense_version_id"])


def downgrade() -> None:
    op.execute(sa.text("DROP VIEW IF EXISTS collection_obligation_progress"))
    op.drop_table("expense_discounts")
    op.drop_table("expense_surcharges")
    op.drop_table("expense_item_shares")
    op.drop_table("expense_items")
    op.drop_table("audit_events")
    op.drop_table("receipt_confirmations")
    op.drop_table("payment_reports")
    op.drop_table("guest_links")
    op.drop_table("collection_envelopes")
    op.drop_table("collection_obligation_sources")
    op.drop_table("collection_obligations")
    op.drop_table("bank_recipient_snapshots")
    op.drop_table("confirmed_allocations")
    op.drop_table("collection_batch_versions")
    op.drop_table("expense_versions")
    op.drop_table("bank_recipients")
    op.drop_table("collection_batches")
    op.drop_table("expenses")
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS reject_immutable_financial_row_change()")
    )
