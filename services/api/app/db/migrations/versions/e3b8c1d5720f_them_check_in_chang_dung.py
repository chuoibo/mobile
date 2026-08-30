"""Thêm check-in theo chặng dừng của buổi đi chơi (F46).

Bảng này KHÔNG lưu vị trí. Check-in ở đây là một cái nút, không phải cảm biến:
hàng ghi *ai* bấm, ở *chặng nào*, *lúc nào*. Toạ độ đọc từ GPS của điện thoại là
F47 và chưa dựng — không có cột nào để nó chảy vào.

Khác với check-in trên tường kỷ niệm (`memories`, revision d7a2e05c9b14): ở đó
toạ độ là của *quán* lấy từ danh mục máy chủ, tức một sự thật về một hàng ăn.
Một toạ độ gắn với một con người và một mốc thời gian là sự thật về đường đi của
người đó, hạng dữ liệu khác hẳn và không thu hồi được sau khi đã vào lịch sử
nhóm. Nên cột không tồn tại, chứ không phải để trống.

`uq_outing_stop_checkins_person` là chỗ luật "một người một lần cho mỗi chặng"
thật sự được cưỡng chế. Một câu `if chưa check-in` trong Python không chặn được
hai điện thoại bấm cùng lúc; unique index thì có.

`ondelete=CASCADE` vì check-in chỉ có nghĩa khi chặng nó trỏ tới còn tồn tại.

Lúc viết revision này, `replace_outing_stops` xoá rồi chèn lại TOÀN BỘ chặng mỗi
lần lưu dòng thời gian, nên mọi lần sửa kế hoạch đều quét sạch check-in. Đó là
bug-223357 và đã sửa ở tầng repository (giữ nguyên hàng của chặng không đổi);
schema ở đây không đổi theo. Ghi lại để không ai đọc câu trên thành "vẫn thế".
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3b8c1d5720f"
down_revision: str | Sequence[str] | None = "d7a2e05c9b14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outing_stop_checkins",
        sa.Column(
            "id", sa.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("stop_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["stop_id"],
            ["outing_stops.id"],
            name="fk_outing_stop_checkins_stop",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["people.id"],
            name="fk_outing_stop_checkins_person",
        ),
        sa.UniqueConstraint(
            "stop_id", "person_id", name="uq_outing_stop_checkins_person"
        ),
    )
    op.create_index(
        "ix_outing_stop_checkins_stop",
        "outing_stop_checkins",
        ["stop_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outing_stop_checkins_stop", table_name="outing_stop_checkins")
    op.drop_table("outing_stop_checkins")
