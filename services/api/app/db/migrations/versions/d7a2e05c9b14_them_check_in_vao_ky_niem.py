"""Thêm check-in nhóm vào tường kỷ niệm (F46).

Một check-in là một kỷ niệm có toạ độ và thời điểm, nên nó nằm chung bảng
`memories` chứ không có bảng riêng: tường nhóm là MỘT dòng thời gian, và hai
bảng nghĩa là hai con trỏ phân trang rồi một phép trộn ở phía đọc — chỗ mà một
check-in lặng lẽ biến mất khỏi feed.

Hệ quả lên cột cũ: `image_url` phải cho phép NULL, vì một check-in không có
ảnh. Ràng buộc `image_url <> ''` bị thay bằng một ràng buộc theo `kind`, chặt
hơn cái nó thay thế — nó vẫn cấm chuỗi rỗng cho ảnh, và thêm vào đó cấm một
hàng vừa mang ảnh vừa mang toạ độ.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Renumbered on rebase, and the old id is deliberately not reused.
#
# The first draft of this file hung off `7c3a8f2d1e6b`, which is also the
# parent of `9e4b1c67d305` (the outing tables). That is two alembic heads off
# one parent, and `upgrade head` on a shared database took this fork: the
# database ended up stamped `8f1c6a4b2e70` with no `outings` table and no
# revision in any branch that explained why.
#
# Rebasing onto the real head fixes the fork. Reusing the id would not fix the
# databases already stamped with it -- they would read as "up to date" while
# missing every table between `7c3a8f2d1e6b` and here. A fresh id makes those
# databases fail with "Can't locate revision", which is the true answer.
revision: str = "d7a2e05c9b14"
down_revision: str | Sequence[str] | None = "c5f141903a2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Repeated in `downgrade`, so it is named once.
PAYLOAD_MATCHES_KIND = (
    "(kind = 'photo' AND image_url IS NOT NULL AND image_url <> '' "
    "AND place_id IS NULL AND place_name IS NULL "
    "AND lat IS NULL AND lng IS NULL) OR "
    "(kind = 'checkin' AND image_url IS NULL "
    "AND place_id IS NOT NULL AND place_id <> '' "
    "AND place_name IS NOT NULL AND place_name <> '' "
    "AND lat IS NOT NULL AND lng IS NOT NULL)"
)


def upgrade() -> None:
    # `native_enum=False` means this enum IS a check constraint, and
    # `add_column` emits it as `ck_memories_memory_kind` on its own. Adding a
    # matching CheckConstraint by hand here raised DuplicateObject in
    # `4d7f2c91a8e3` and took every PostgreSQL test down with it.
    op.add_column(
        "memories",
        sa.Column(
            "kind",
            sa.Enum(
                "photo",
                "checkin",
                name="memory_kind",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="photo",
            nullable=False,
        ),
    )
    op.add_column("memories", sa.Column("place_id", sa.Text(), nullable=True))
    op.add_column("memories", sa.Column("place_name", sa.Text(), nullable=True))
    op.add_column("memories", sa.Column("lat", sa.Float(), nullable=True))
    op.add_column("memories", sa.Column("lng", sa.Float(), nullable=True))

    # Dropped before `image_url` becomes nullable, not after. The old
    # constraint is satisfied by NULL in PostgreSQL, so the order does not
    # matter for correctness -- it matters for the reader, because leaving a
    # constraint named `image_url_not_blank` on a nullable column is a name
    # that describes something the column no longer promises.
    op.drop_constraint(
        op.f("ck_memories_image_url_not_blank"), "memories", type_="check"
    )
    op.alter_column("memories", "image_url", existing_type=sa.Text(), nullable=True)

    op.create_check_constraint(
        op.f("ck_memories_payload_matches_kind"), "memories", PAYLOAD_MATCHES_KIND
    )
    op.create_check_constraint(
        op.f("ck_memories_lat_range"), "memories", "lat IS NULL OR lat BETWEEN -90 AND 90"
    )
    op.create_check_constraint(
        op.f("ck_memories_lng_range"),
        "memories",
        "lng IS NULL OR lng BETWEEN -180 AND 180",
    )

    op.create_index(
        "ix_memories_context_place",
        "memories",
        [sa.text("context_id"), sa.text("place_id"), sa.text("created_at DESC")],
        postgresql_where=sa.text("place_id IS NOT NULL"),
    )


def downgrade() -> None:
    # This DELETE is destructive and is written out rather than hidden.
    #
    # A check-in has no `image_url`, and the column this reverts to is NOT
    # NULL. There is no value to put there: an empty string is refused by the
    # constraint being restored, and inventing a URL would store a photograph
    # that does not exist. So the choice is between a downgrade that always
    # fails on a database that has ever been checked into, and one that drops
    # the rows the older schema cannot represent. Failing every time would make
    # the down path untestable, which is worse -- but nobody should run this
    # against production data without reading this paragraph first.
    op.execute(sa.text("DELETE FROM memories WHERE kind = 'checkin'"))

    op.drop_index("ix_memories_context_place", table_name="memories")
    op.drop_constraint(op.f("ck_memories_lng_range"), "memories", type_="check")
    op.drop_constraint(op.f("ck_memories_lat_range"), "memories", type_="check")
    op.drop_constraint(
        op.f("ck_memories_payload_matches_kind"), "memories", type_="check"
    )

    op.alter_column("memories", "image_url", existing_type=sa.Text(), nullable=False)
    op.create_check_constraint(
        op.f("ck_memories_image_url_not_blank"), "memories", "image_url <> ''"
    )

    op.drop_column("memories", "lng")
    op.drop_column("memories", "lat")
    op.drop_column("memories", "place_name")
    op.drop_column("memories", "place_id")
    # Takes `ck_memories_memory_kind` with it, the same way `add_column`
    # brought it in.
    op.drop_column("memories", "kind")
