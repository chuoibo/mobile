"""Session table, and a named invite that may carry a secret.

Two changes, one subject (ADR-0014). `account_sessions` gives the server
somewhere to say which person a bearer token stands for, so `get_actor` stops
reading that from a header the client writes. And the check constraint on
`outing_invites` stops forbidding a digest on named rows: exchanging a named
invite is how a person gets their first session, and a credential with nowhere
to store its digest cannot exist.

The relaxed rule keeps the half that still matters -- a `link` row without a
digest can never be redeemed by anyone -- and drops the half that was only ever
an artefact of links being the single kind of secret this table held.

Downgrade is only safe while no named row carries a digest, which is why it
refuses instead of dropping the column's contents on the floor.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9f28a4d1b73"
down_revision: str | Sequence[str] | None = "b3c7e0d24f19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column(
            "issued_from_invite_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at > created_at",
            name=op.f("ck_account_sessions_expiry_after_creation"),
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["people.id"],
            name="fk_account_sessions_person",
        ),
        sa.ForeignKeyConstraint(
            ["issued_from_invite_id"],
            ["outing_invites.id"],
            name="fk_account_sessions_invite",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_sessions")),
        sa.UniqueConstraint(
            "token_digest", name=op.f("uq_account_sessions_token_digest")
        ),
    )
    op.create_index(
        op.f("ix_account_sessions_person"),
        "account_sessions",
        ["person_id"],
        unique=False,
    )

    op.drop_constraint(
        op.f("ck_outing_invites_link_carries_digest"),
        "outing_invites",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_outing_invites_link_carries_digest"),
        "outing_invites",
        "source <> 'link' OR token_digest IS NOT NULL",
    )


def downgrade() -> None:
    # The old rule forbids what this migration allowed. Rather than delete a
    # live credential to satisfy a constraint, refuse and say which rows are in
    # the way -- a downgrade that silently unauthenticates people is worse than
    # one that stops.
    named_with_digest = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT count(*) FROM outing_invites "
                "WHERE source <> 'link' AND token_digest IS NOT NULL"
            )
        )
        .scalar_one()
    )
    if named_with_digest:
        raise RuntimeError(
            f"{named_with_digest} named outing_invites still carry a digest; "
            "revoke or rotate them before downgrading"
        )

    op.drop_constraint(
        op.f("ck_outing_invites_link_carries_digest"),
        "outing_invites",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_outing_invites_link_carries_digest"),
        "outing_invites",
        "(source = 'link') = (token_digest IS NOT NULL)",
    )

    op.drop_index(op.f("ix_account_sessions_person"), table_name="account_sessions")
    op.drop_table("account_sessions")
