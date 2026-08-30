"""Add vote, option, and ballot tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "a7d3f2b81c56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "question <> ''",
            name=op.f("ck_votes_question_not_blank"),
        ),
        sa.CheckConstraint(
            "(closed_at IS NULL) = (closed_by_id IS NULL)",
            name=op.f("ck_votes_closing_is_whole"),
        ),
        sa.ForeignKeyConstraint(
            ["context_id"],
            ["contexts.id"],
            name="fk_votes_context",
        ),
        sa.ForeignKeyConstraint(
            ["outing_id"],
            ["outings.id"],
            name="fk_votes_outing",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["people.id"],
            name="fk_votes_created_by",
        ),
        sa.ForeignKeyConstraint(
            ["closed_by_id"],
            ["people.id"],
            name="fk_votes_closed_by",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_votes")),
    )
    op.create_index(
        "ix_votes_context_created",
        "votes",
        ["context_id", "created_at", "id"],
    )

    op.create_table(
        "vote_options",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vote_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("place_name", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "position >= 0",
            name=op.f("ck_vote_options_position_not_negative"),
        ),
        sa.CheckConstraint(
            "label <> ''",
            name=op.f("ck_vote_options_label_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["vote_id"],
            ["votes.id"],
            name="fk_vote_options_vote",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vote_options")),
        sa.UniqueConstraint(
            "vote_id",
            "position",
            name=op.f("uq_vote_options_position"),
        ),
    )

    op.create_table(
        "vote_ballots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vote_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("option_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("voter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["vote_id"],
            ["votes.id"],
            name="fk_vote_ballots_vote",
        ),
        sa.ForeignKeyConstraint(
            ["option_id"],
            ["vote_options.id"],
            name="fk_vote_ballots_option",
        ),
        sa.ForeignKeyConstraint(
            ["voter_id"],
            ["people.id"],
            name="fk_vote_ballots_voter",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vote_ballots")),
        sa.UniqueConstraint(
            "vote_id",
            "voter_id",
            name=op.f("uq_vote_ballots_one_per_person"),
        ),
    )
    op.create_index(
        "ix_vote_ballots_vote",
        "vote_ballots",
        ["vote_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_vote_ballots_vote", table_name="vote_ballots")
    op.drop_index("ix_votes_context_created", table_name="votes")
    op.drop_table("vote_ballots")
    op.drop_table("vote_options")
    op.drop_table("votes")
