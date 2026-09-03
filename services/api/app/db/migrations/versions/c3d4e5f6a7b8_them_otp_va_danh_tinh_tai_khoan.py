"""OTP challenges and account identities (ADR-0016, M1).

`otp_challenges` holds one row per code sent: a keyed digest of the phone, a
digest of the code salted by the row id, an expiry, an attempt counter and a
consumed timestamp. No number and no code is ever stored.

`account_identities` binds an external proof -- a phone digest, or later a
Google `sub` -- to one person, unique per (provider, subject). It is how the
OTP door finds the person a friend already named by phone, and how the Google
door will recognise a returning account without ever merging by email.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b7e2c9a41d05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "otp_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("code_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at > created_at",
            name=op.f("ck_otp_challenges_expiry_after_creation"),
        ),
        sa.CheckConstraint(
            "attempts >= 0", name=op.f("ck_otp_challenges_attempts_not_negative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_otp_challenges")),
    )
    op.create_index(
        "ix_otp_challenges_phone_recent",
        "otp_challenges",
        ["phone_digest", sa.text("created_at DESC")],
        unique=False,
    )

    op.create_table(
        "account_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "provider IN ('phone', 'google')",
            name=op.f("ck_account_identities_provider_known"),
        ),
        sa.ForeignKeyConstraint(
            ["person_id"], ["people.id"], name="fk_account_identities_person"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_identities")),
        sa.UniqueConstraint(
            "provider", "subject", name="uq_account_identities_provider_subject"
        ),
    )
    op.create_index(
        op.f("ix_account_identities_person"),
        "account_identities",
        ["person_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_account_identities_person"), table_name="account_identities")
    op.drop_table("account_identities")
    op.drop_index("ix_otp_challenges_phone_recent", table_name="otp_challenges")
    op.drop_table("otp_challenges")
