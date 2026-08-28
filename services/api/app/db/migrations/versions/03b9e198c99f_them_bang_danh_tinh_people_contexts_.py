"""Add people, groups, contexts, and membership history.

Revision ID: 03b9e198c99f
Revises: 20260827_0001

The previous API used `context_id` as if it named a group. The product contract
does not: a group is stable while a context is one trip, occasion, or cycle.
Legacy context identifiers are therefore backfilled one-to-one into both tables
without inferring membership. Existing financial subject identifiers are also
backfilled as distinct people with a neutral label; silently merging them would
rewrite ledger identity.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "03b9e198c99f"
down_revision: str | Sequence[str] | None = "20260827_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PERSON_FOREIGN_KEYS = (
    ("fk_expense_versions_recorded_by", "expense_versions", "recorded_by_id"),
    ("fk_expense_versions_paid_by", "expense_versions", "paid_by_id"),
    (
        "fk_expense_item_shares_participant",
        "expense_item_shares",
        "participant_id",
    ),
    (
        "fk_confirmed_allocations_participant",
        "confirmed_allocations",
        "participant_id",
    ),
    (
        "fk_confirmed_allocations_confirmed_by",
        "confirmed_allocations",
        "confirmed_by_id",
    ),
    ("fk_collection_batches_owner", "collection_batches", "owner_id"),
    (
        "fk_collection_batch_versions_created_by",
        "collection_batch_versions",
        "created_by_id",
    ),
    ("fk_bank_recipients_recipient", "bank_recipients", "recipient_id"),
    (
        "fk_bank_recipient_snapshots_recipient",
        "bank_recipient_snapshots",
        "recipient_id",
    ),
    (
        "fk_collection_obligations_sender",
        "collection_obligations",
        "sender_id",
    ),
    (
        "fk_collection_obligations_recipient",
        "collection_obligations",
        "recipient_id",
    ),
    ("fk_collection_envelopes_sender", "collection_envelopes", "sender_id"),
    ("fk_payment_reports_reported_by", "payment_reports", "reported_by_id"),
    (
        "fk_receipt_confirmations_confirmed_by",
        "receipt_confirmations",
        "confirmed_by_id",
    ),
    ("fk_audit_events_actor", "audit_events", "actor_id"),
)


def _backfill_legacy_people() -> None:
    op.execute(
        """
        INSERT INTO people (id, display_name)
        SELECT subject_id, 'Legacy participant'
        FROM (
            SELECT recorded_by_id AS subject_id FROM expense_versions
            UNION SELECT paid_by_id FROM expense_versions
            UNION SELECT participant_id FROM expense_item_shares
            UNION SELECT participant_id FROM confirmed_allocations
            UNION SELECT confirmed_by_id FROM confirmed_allocations
            UNION SELECT owner_id FROM collection_batches
            UNION SELECT created_by_id FROM collection_batch_versions
            UNION SELECT recipient_id FROM bank_recipients
            UNION SELECT recipient_id FROM bank_recipient_snapshots
            UNION SELECT sender_id FROM collection_obligations
            UNION SELECT recipient_id FROM collection_obligations
            UNION SELECT sender_id FROM collection_envelopes
            UNION SELECT reported_by_id FROM payment_reports
            UNION SELECT confirmed_by_id FROM receipt_confirmations
            UNION SELECT actor_id FROM audit_events
        ) AS legacy_subjects
        WHERE subject_id IS NOT NULL
        ON CONFLICT (id) DO NOTHING
        """
    )


def _backfill_legacy_contexts() -> None:
    legacy_contexts = """
        SELECT context_id FROM expenses
        UNION SELECT context_id FROM collection_batches
    """
    op.execute(
        f"""
        INSERT INTO groups (id, display_name, created_by_id)
        SELECT context_id, 'Legacy group', NULL
        FROM ({legacy_contexts}) AS legacy_contexts
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute(
        f"""
        INSERT INTO contexts (id, group_id, display_name, created_by_id)
        SELECT context_id, context_id, 'Legacy context', NULL
        FROM ({legacy_contexts}) AS legacy_contexts
        ON CONFLICT (id) DO NOTHING
        """
    )


def upgrade() -> None:
    op.create_table(
        "people",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(btrim(display_name)) BETWEEN 1 AND 120",
            name=op.f("ck_people_display_name_length"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_people")),
    )
    _backfill_legacy_people()

    op.create_table(
        "groups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(btrim(display_name)) BETWEEN 1 AND 120",
            name=op.f("ck_groups_display_name_length"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["people.id"],
            name="fk_groups_created_by",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_groups")),
    )
    op.create_table(
        "contexts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(btrim(display_name)) BETWEEN 1 AND 120",
            name=op.f("ck_contexts_display_name_length"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["people.id"],
            name="fk_contexts_created_by",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.id"],
            name="fk_contexts_group",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contexts")),
    )
    op.create_index("ix_contexts_group_id", "contexts", ["group_id"])
    _backfill_legacy_contexts()

    op.create_table(
        "memberships",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "invited",
                "active",
                "left",
                "removed",
                name="membership_state",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="invited",
            nullable=False,
        ),
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
        sa.Column("invited_by_id", sa.UUID(), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(state = 'invited' AND joined_at IS NULL AND left_at IS NULL) OR "
            "(state = 'active' AND joined_at IS NOT NULL AND left_at IS NULL) OR "
            "(state IN ('left', 'removed') AND joined_at IS NOT NULL "
            "AND left_at IS NOT NULL AND left_at >= joined_at)",
            name=op.f("ck_memberships_lifecycle_timestamps"),
        ),
        sa.CheckConstraint(
            "state <> 'invited' OR invited_by_id IS NOT NULL",
            name=op.f("ck_memberships_invitation_has_inviter"),
        ),
        sa.ForeignKeyConstraint(
            ["group_id"], ["groups.id"], name="fk_memberships_group"
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_id"],
            ["people.id"],
            name="fk_memberships_invited_by",
        ),
        sa.ForeignKeyConstraint(
            ["person_id"], ["people.id"], name="fk_memberships_person"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
    )
    op.create_index("ix_memberships_group_id", "memberships", ["group_id"])
    op.create_index(
        "ix_memberships_person_open",
        "memberships",
        ["person_id"],
        postgresql_where=sa.text("state IN ('invited', 'active')"),
    )
    op.create_index(
        "uq_memberships_open_per_person",
        "memberships",
        ["group_id", "person_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('invited', 'active')"),
    )
    op.execute(
        """
        CREATE FUNCTION reject_overlapping_membership_intervals()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF NEW.joined_at IS NULL THEN
                RETURN NEW;
            END IF;

            PERFORM pg_advisory_xact_lock(
                hashtextextended(
                    NEW.group_id::text || ':' || NEW.person_id::text,
                    0
                )
            );
            IF EXISTS (
                SELECT 1
                FROM memberships AS existing
                WHERE existing.group_id = NEW.group_id
                  AND existing.person_id = NEW.person_id
                  AND existing.id <> NEW.id
                  AND existing.joined_at IS NOT NULL
                  AND tstzrange(existing.joined_at, existing.left_at, '[)')
                      && tstzrange(NEW.joined_at, NEW.left_at, '[)')
            ) THEN
                RAISE EXCEPTION 'membership intervals overlap'
                    USING ERRCODE = '23P01',
                          CONSTRAINT = 'ex_memberships_no_overlap';
            END IF;
            RETURN NEW;
        END;
        $function$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_memberships_no_overlapping_intervals
        BEFORE INSERT OR UPDATE OF group_id, person_id, state, joined_at, left_at
        ON memberships
        FOR EACH ROW
        EXECUTE FUNCTION reject_overlapping_membership_intervals()
        """
    )

    op.create_foreign_key(
        "fk_expenses_context", "expenses", "contexts", ["context_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_collection_batches_context",
        "collection_batches",
        "contexts",
        ["context_id"],
        ["id"],
    )
    for name, source_table, source_column in PERSON_FOREIGN_KEYS:
        op.create_foreign_key(
            name,
            source_table,
            "people",
            [source_column],
            ["id"],
        )


def downgrade() -> None:
    for name, source_table, _source_column in reversed(PERSON_FOREIGN_KEYS):
        op.drop_constraint(name, source_table, type_="foreignkey")
    op.drop_constraint(
        "fk_collection_batches_context",
        "collection_batches",
        type_="foreignkey",
    )
    op.drop_constraint("fk_expenses_context", "expenses", type_="foreignkey")

    op.execute("DROP TRIGGER trg_memberships_no_overlapping_intervals ON memberships")
    op.execute("DROP FUNCTION reject_overlapping_membership_intervals()")
    op.drop_index(
        "uq_memberships_open_per_person",
        table_name="memberships",
        postgresql_where=sa.text("state IN ('invited', 'active')"),
    )
    op.drop_index(
        "ix_memberships_person_open",
        table_name="memberships",
        postgresql_where=sa.text("state IN ('invited', 'active')"),
    )
    op.drop_index("ix_memberships_group_id", table_name="memberships")
    op.drop_table("memberships")
    op.drop_index("ix_contexts_group_id", table_name="contexts")
    op.drop_table("contexts")
    op.drop_table("groups")
    op.drop_table("people")
