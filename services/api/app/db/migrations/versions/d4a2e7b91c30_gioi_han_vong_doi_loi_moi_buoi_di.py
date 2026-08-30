"""Giới hạn vòng đời và cho phép thu hồi lời mời buổi đi.

Các dòng đã tồn tại được đặt ``expires_at = created_at`` để hết hạn ngay.
Nếu cấp cho chúng một TTL mới, mọi liên kết đã rò rỉ sẽ nhận thêm một vòng đời,
chính là lỗi migration này phải khắc phục. Cách backfill này tương ứng với việc
backfill ``origin`` của #128: dữ liệu cũ phải nhận semantics an toàn mới, không
được giữ lại mức tin cậy trước đây.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4a2e7b91c30"
down_revision: str | Sequence[str] | None = "c5f141903a2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outing_invites",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outing_invites",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Legacy links must die at migration time instead of receiving a fresh TTL.
    op.execute(
        sa.text(
            "UPDATE outing_invites SET expires_at = created_at"
        )
    )
    op.alter_column(
        "outing_invites",
        "expires_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_outing_invites_expiry_after_creation"),
        "outing_invites",
        "expires_at >= created_at",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_outing_invites_expiry_after_creation"),
        "outing_invites",
        type_="check",
    )
    op.drop_column("outing_invites", "expires_at")
    op.drop_column("outing_invites", "revoked_at")
