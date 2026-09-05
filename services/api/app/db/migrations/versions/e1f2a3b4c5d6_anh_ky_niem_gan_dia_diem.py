"""Ảnh kỷ niệm được gắn địa điểm (M12, ADR-0017 §2.4).

Nguồn ảnh thứ hai của một địa điểm, sau ảnh Wikimedia có giấy phép: ảnh do
chính nhóm chụp ở đó. Trước bản này `payload_matches_kind` cấm điều ấy —
`kind='photo'` bắt buộc `place_id IS NULL` — nên không có gì để hiện.

Ràng buộc mới nới đúng một chuyện và giữ mọi chuyện khác:

- ảnh CÓ THỂ mang địa điểm, và khi mang thì phải mang cả `place_id` lẫn
  `place_name`; nửa địa điểm là một hàng mà tường vẽ ra cái nhãn rỗng;
- ảnh vẫn KHÔNG mang `lat`/`lng`. Toạ độ của một check-in lấy từ bảng
  `places` chứ không từ điện thoại; đọc GPS là F47 và chưa dựng, nên một
  hàng ảnh có toạ độ sẽ làm như thể đã dựng rồi.
- check-in không đổi một chữ.

Thêm `ix_memories_place_kind`: câu hỏi mới đi theo chiều ngược với tường —
một địa điểm, mọi nhóm người đọc thuộc về. Không có index dẫn đầu bằng
`place_id` thì nó quét tường của mọi nhóm để trả lời một màn vừa mở.

Xuống được: hàng ảnh đã gắn địa điểm phải được gỡ nhãn trước khi ràng buộc cũ
quay lại, nếu không `downgrade` sẽ chết giữa chừng trên một database có dữ
liệu. Gỡ nhãn chứ không xoá hàng — tấm ảnh là của người ta.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CU = (
    "(kind = 'photo' AND image_url IS NOT NULL AND image_url <> '' "
    "AND place_id IS NULL AND place_name IS NULL "
    "AND lat IS NULL AND lng IS NULL) OR "
    "(kind = 'checkin' AND image_url IS NULL "
    "AND place_id IS NOT NULL AND place_id <> '' "
    "AND place_name IS NOT NULL AND place_name <> '' "
    "AND lat IS NOT NULL AND lng IS NOT NULL)"
)

MOI = (
    "(kind = 'photo' AND image_url IS NOT NULL AND image_url <> '' "
    "AND ((place_id IS NULL AND place_name IS NULL) "
    "OR (place_id IS NOT NULL AND place_id <> '' "
    "AND place_name IS NOT NULL AND place_name <> '')) "
    "AND lat IS NULL AND lng IS NULL) OR "
    "(kind = 'checkin' AND image_url IS NULL "
    "AND place_id IS NOT NULL AND place_id <> '' "
    "AND place_name IS NOT NULL AND place_name <> '' "
    "AND lat IS NOT NULL AND lng IS NOT NULL)"
)


def upgrade() -> None:
    op.drop_constraint("payload_matches_kind", "memories", type_="check")
    op.create_check_constraint("payload_matches_kind", "memories", MOI)
    op.create_index(
        "ix_memories_place_kind",
        "memories",
        ["place_id", "kind", "created_at"],
        unique=False,
        postgresql_where="place_id IS NOT NULL",
        postgresql_ops={"created_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("ix_memories_place_kind", table_name="memories")
    op.execute(
        "UPDATE memories SET place_id = NULL, place_name = NULL "
        "WHERE kind = 'photo' AND place_id IS NOT NULL"
    )
    op.drop_constraint("payload_matches_kind", "memories", type_="check")
    op.create_check_constraint("payload_matches_kind", "memories", CU)
