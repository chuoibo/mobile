"""Keep bearer-token join requests from inheriting named-invite trust."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5f141903a2b"
down_revision: str | Sequence[str] | None = "9e4b1c67d305"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "memberships",
        sa.Column(
            "origin",
            sa.Enum(
                "named",
                "link",
                name="membership_origin",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="named",
            nullable=False,
        ),
    )

    # Redeemed bearer links must not inherit the trusted default, or existing
    # data would retain the same self-promotion path after this fix deploys.
    op.execute(
        sa.text(
            """
            UPDATE memberships AS m
            SET origin = 'link'
            FROM outing_invites AS oi
            JOIN outings AS o ON o.id = oi.outing_id
            WHERE oi.source = 'link'
              AND oi.accepted_by_id = m.person_id
              AND o.context_id = m.context_id
              AND m.state <> 'left'
            """
        )
    )


def downgrade() -> None:
    op.drop_column("memberships", "origin")
