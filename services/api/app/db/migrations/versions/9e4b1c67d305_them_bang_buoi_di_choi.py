"""Add outing, timeline stop, and invite tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9e4b1c67d305"
down_revision: str | Sequence[str] | None = "7c3a8f2d1e6b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("headcount", sa.Integer(), nullable=False),
        sa.Column("budget_per_person_vnd", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ends_on >= starts_on",
            name=op.f("ck_outings_dates_in_order"),
        ),
        sa.CheckConstraint(
            "headcount > 0",
            name=op.f("ck_outings_headcount_positive"),
        ),
        sa.CheckConstraint(
            "budget_per_person_vnd >= 0",
            name=op.f("ck_outings_budget_not_negative"),
        ),
        sa.CheckConstraint(
            "title <> ''",
            name=op.f("ck_outings_title_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["context_id"],
            ["contexts.id"],
            name="fk_outings_context",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["people.id"],
            name="fk_outings_created_by",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outings")),
    )
    op.create_index(
        "ix_outings_context_schedule",
        "outings",
        ["context_id", "starts_on", "id"],
    )

    op.create_table(
        "outing_stops",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("minute_of_day", sa.Integer(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("place_name", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "minute_of_day BETWEEN 0 AND 1439",
            name=op.f("ck_outing_stops_minute_in_day"),
        ),
        sa.CheckConstraint(
            "position >= 0",
            name=op.f("ck_outing_stops_position_not_negative"),
        ),
        sa.CheckConstraint(
            "label <> ''",
            name=op.f("ck_outing_stops_label_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["outing_id"],
            ["outings.id"],
            name="fk_outing_stops_outing",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outing_stops")),
        sa.UniqueConstraint(
            "outing_id",
            "position",
            name=op.f("uq_outing_stops_position"),
        ),
    )

    op.create_table(
        "outing_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "group",
                "friend",
                "link",
                name="outing_invite_source",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "invited_person_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("invited_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_digest", sa.LargeBinary(length=32), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "accepted_by_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(source = 'link') = (token_digest IS NOT NULL)",
            name=op.f("ck_outing_invites_link_carries_digest"),
        ),
        sa.CheckConstraint(
            "(source = 'link') = (invited_person_id IS NULL)",
            name=op.f("ck_outing_invites_link_names_nobody"),
        ),
        sa.CheckConstraint(
            "(accepted_at IS NULL) = (accepted_by_id IS NULL)",
            name=op.f("ck_outing_invites_acceptance_is_whole"),
        ),
        sa.ForeignKeyConstraint(
            ["accepted_by_id"],
            ["people.id"],
            name="fk_outing_invites_accepter",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_id"],
            ["people.id"],
            name="fk_outing_invites_inviter",
        ),
        sa.ForeignKeyConstraint(
            ["invited_person_id"],
            ["people.id"],
            name="fk_outing_invites_person",
        ),
        sa.ForeignKeyConstraint(
            ["outing_id"],
            ["outings.id"],
            name="fk_outing_invites_outing",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outing_invites")),
        sa.UniqueConstraint(
            "token_digest",
            name=op.f("uq_outing_invites_token_digest"),
        ),
    )
    op.create_index(
        "uq_outing_invites_person",
        "outing_invites",
        ["outing_id", "invited_person_id"],
        unique=True,
        postgresql_where=sa.text("invited_person_id IS NOT NULL"),
    )
    op.create_index(
        "ix_outing_invites_outing",
        "outing_invites",
        ["outing_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_outing_invites_outing", table_name="outing_invites")
    op.drop_index(
        "uq_outing_invites_person",
        "outing_invites",
        postgresql_where=sa.text("invited_person_id IS NOT NULL"),
    )
    op.drop_index("ix_outings_context_schedule", table_name="outings")
    op.drop_table("outing_invites")
    op.drop_table("outing_stops")
    op.drop_table("outings")
