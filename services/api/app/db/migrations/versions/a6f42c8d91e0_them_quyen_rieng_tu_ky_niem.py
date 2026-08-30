"""Thêm mức hiển thị cho từng kỷ niệm (F42).

Mặc định ở máy chủ là ``group`` để mọi hàng đã tồn tại và mọi writer cũ giữ
đúng phạm vi nhóm hiện tại; migration không được âm thầm mở chúng ra ngoài.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6f42c8d91e0"
down_revision: str | Sequence[str] | None = "c5e14b7a9d02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The non-native enum is a CHECK constraint. Alembic emits that constraint
    # together with the column, matching `Memory.visibility` in the model.
    op.add_column(
        "memories",
        sa.Column(
            "visibility",
            sa.Enum(
                "only_me",
                "friends",
                "group",
                "public",
                name="memory_visibility",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="group",
            nullable=False,
        ),
    )


def downgrade() -> None:
    # Dropping the column also drops its generated CHECK constraint.
    op.drop_column("memories", "visibility")
