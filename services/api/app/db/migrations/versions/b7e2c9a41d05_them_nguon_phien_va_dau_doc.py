"""Sessions say which door minted them, and a group remembers how far you read.

Two changes for M1 of the production-ready roadmap (ADR-0016).

`account_sessions.issued_via` names the proof behind a session -- `invite`,
`otp`, `google`, `genesis`. Until now the only doors were a named invitation and
the genesis script, told apart by whether `issued_from_invite_id` was NULL. Two
more doors arrive with OTP and Google, and "NULL means genesis" stops being
true the day the first OTP session is minted, so the provenance gets its own
column and two check constraints: the value is one of four, and only `invite`
rows carry an invite id. Existing rows are backfilled from the one fact that
already distinguished them.

`context_read_marks` is one row per (group, person): the last message they
read, with its own `created_at` copied beside it so "unread" is the feed's
keyset comparison and never a join. Unread counts are derived, not stored.

Downgrade drops both, which loses read positions -- acceptable, they are a
convenience -- and refuses if any session was minted through a door the old
schema cannot represent.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7e2c9a41d05"
down_revision: str | Sequence[str] | None = "e7a1c4d90b52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "account_sessions",
        sa.Column(
            "issued_via",
            sa.String(length=16),
            server_default="invite",
            nullable=False,
        ),
    )
    # The one fact that told the two old doors apart becomes the explicit value.
    op.execute(
        "UPDATE account_sessions SET issued_via = 'genesis' "
        "WHERE issued_from_invite_id IS NULL"
    )
    op.create_check_constraint(
        op.f("ck_account_sessions_issued_via_known"),
        "account_sessions",
        "issued_via IN ('invite', 'otp', 'google', 'genesis')",
    )
    op.create_check_constraint(
        op.f("ck_account_sessions_invite_matches_via"),
        "account_sessions",
        "(issued_via = 'invite') = (issued_from_invite_id IS NOT NULL)",
    )

    op.create_table(
        "context_read_marks",
        sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "last_read_message_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["context_id"], ["contexts.id"], name="fk_context_read_marks_context"
        ),
        sa.ForeignKeyConstraint(
            ["person_id"], ["people.id"], name="fk_context_read_marks_person"
        ),
        sa.ForeignKeyConstraint(
            ["last_read_message_id"],
            ["messages.id"],
            name="fk_context_read_marks_message",
        ),
        sa.PrimaryKeyConstraint(
            "context_id", "person_id", name=op.f("pk_context_read_marks")
        ),
    )


def downgrade() -> None:
    op.drop_table("context_read_marks")
    connection = op.get_bind()
    foreign = connection.execute(
        sa.text(
            "SELECT count(*) FROM account_sessions "
            "WHERE issued_via NOT IN ('invite', 'genesis')"
        )
    ).scalar_one()
    if foreign:
        raise RuntimeError(
            f"{foreign} phiên được mint qua cửa OTP/Google; schema cũ không biểu "
            "diễn được chúng. Thu hồi các phiên đó trước khi downgrade."
        )
    op.drop_constraint(
        op.f("ck_account_sessions_invite_matches_via"),
        "account_sessions",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_account_sessions_issued_via_known"),
        "account_sessions",
        type_="check",
    )
    op.drop_column("account_sessions", "issued_via")
