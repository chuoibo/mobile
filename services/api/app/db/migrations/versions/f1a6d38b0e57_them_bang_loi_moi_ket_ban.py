"""Thêm bảng lời mời kết bạn (F03, F04).

Đồ thị bạn bè không có bảng `friends`. Có bảng `friend_requests`, và "là bạn"
là `state = 'accepted'` đọc lại từ đó — cùng hình dạng với bất biến 3 về tiền:
quan hệ tính lại được từ sự kiện sinh ra nó, chứ không lưu song song một chỗ
thứ hai rồi để hai chỗ lệch nhau.

Vì sao hướng của cạnh được giữ lại sau khi đã trả lời: `requester_id` và
`addressee_id` là thứ duy nhất khiến luật đồng ý KIỂM ĐƯỢC về sau. Với một
hàng vô hướng, câu "người nhận đã đồng ý" không ai xác minh được nữa.

## Chỉ mục quan trọng nhất trong file này

`uq_friend_edge_live` là UNIQUE trên `least(requester_id, addressee_id)` và
`greatest(...)`, giới hạn ở các trạng thái còn sống. Nó nói: MỖI CẶP người chỉ
có nhiều nhất MỘT cạnh còn sống, bất kể ai hỏi ai trước.

Không có nó, hai người cùng bấm "kết bạn" trong cùng một giây sinh ra hai hàng
pending ngược chiều, rồi cả hai cùng được đồng ý, và sản phẩm có hai tình bạn
giữa đúng hai con người. Màn đếm bạn hiện 2, màn danh sách hiện 1, và không có
cách nào gỡ mà không chọn bừa một hàng để xoá.

`least/greatest` là hạ tầng Postgres thật, không giả lập bằng dict được — đây
chính là lý do `tests/postgres/test_friend_requests_postgres.py` tồn tại và lý
do tầng fake mù với ca này theo đúng thiết kế.

`state IN (...)` cố ý BỎ `declined`: bị từ chối một lần không phải án chung
thân, nên một cạnh đã declined phải nhường chỗ cho lời mời sau. `blocked` thì
CÓ trong danh sách, vì chặn là chặn.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a6d38b0e57"
down_revision: str | Sequence[str] | None = "e3b8c1d5720f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Các trạng thái còn CHIẾM cặp. Viết một lần, dùng ở cả upgrade lẫn downgrade.
LIVE_STATES = "state IN ('pending', 'accepted', 'blocked')"


def upgrade() -> None:
    op.create_table(
        "friend_requests",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("requester_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("addressee_id", sa.UUID(as_uuid=True), nullable=False),
        # `native_enum=False` nghĩa là enum này CHÍNH LÀ một check constraint,
        # và create_table tự phát ra `ck_friend_requests_friend_request_state`.
        # Thêm CheckConstraint trùng bằng tay ở đây từng gây DuplicateObject ở
        # `4d7f2c91a8e3` và kéo sập cả tầng PostgreSQL — đừng thêm lại.
        sa.Column(
            "state",
            sa.Enum(
                "pending",
                "accepted",
                "declined",
                "blocked",
                name="friend_request_state",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("decided_by_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["requester_id"], ["people.id"], name="fk_friend_requests_requester"
        ),
        sa.ForeignKeyConstraint(
            ["addressee_id"], ["people.id"], name="fk_friend_requests_addressee"
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"], ["people.id"], name="fk_friend_requests_decided_by"
        ),
        sa.CheckConstraint("requester_id <> addressee_id", name="no_self_friendship"),
        sa.CheckConstraint(
            "(state = 'pending') = (decided_at IS NULL)",
            name="decided_state_matches_timestamp",
        ),
    )

    # Không dùng `op.create_index` với cột thường được: hai vế là BIỂU THỨC.
    # Alembic dựng được qua `sa.text`, nhưng viết thẳng SQL ở đây đọc ra đúng
    # cái mà `app.domain.friendship.pair_key` làm bằng Python, nên hai cách
    # đánh vần cùng một luật nằm cạnh nhau và sửa một thì thấy ngay cái kia.
    op.execute(
        "CREATE UNIQUE INDEX uq_friend_edge_live ON friend_requests "
        "(least(requester_id, addressee_id), greatest(requester_id, addressee_id)) "
        f"WHERE {LIVE_STATES}"
    )
    op.create_index(
        "ix_friend_requests_addressee", "friend_requests", ["addressee_id", "state"]
    )
    op.create_index(
        "ix_friend_requests_requester", "friend_requests", ["requester_id", "state"]
    )


def downgrade() -> None:
    op.drop_index("ix_friend_requests_requester", table_name="friend_requests")
    op.drop_index("ix_friend_requests_addressee", table_name="friend_requests")
    op.execute("DROP INDEX IF EXISTS uq_friend_edge_live")
    op.drop_table("friend_requests")
