"""Khoá ngoại context_id cho ba bảng tiền: bills, expenses, collection_batches

`bills`, `expenses` và `collection_batches` ra đời ở schema đầu tiên, lúc
`contexts` còn chưa có bảng. Khi `contexts` được thêm (03b9e198c99f) nó không
gắn khoá ngoại ngược lại cho ba bảng này, nên `context_id` của chúng vẫn đúng
như docstring của `Context` đã tự mô tả: một UUID trỏ vào hư không. Mọi bảng
sinh sau đó -- memberships, outings, messages, posts, votes, memories,
uploaded_images -- đều có khoá. Ba bảng này bị bỏ lại.

Hậu quả đo được trên máy demo ngày 2026-08-30: `public.expenses` có 10932 hàng
mà `context_id` không khớp hàng nào trong `contexts`, 7308 hàng trong số đó đã
có confirmed_allocations. Tiền của chúng vẫn chảy vào `GET /people/{id}/finance`
-- truy vấn spend đi từ confirmed_allocations sang expense_versions và không hề
join `contexts` -- nên màn Cá nhân cộng tiền của một nhóm không tự gọi tên được.

## Vì sao NOT VALID chứ không kiểm luôn hàng cũ

Khoá được thêm ở dạng `NOT VALID`. PostgreSQL vẫn cưỡng chế nó cho **mọi lệnh
ghi từ đây trở đi**; thứ nó bỏ qua chỉ là việc quét lại các hàng đã nằm sẵn.
Đó đúng là ranh giới nên dừng:

* Xoá 10932 hàng mồ côi là xoá sổ cái. Bất biến 3 nói số dư phải tính lại được
  từ sổ; migration không được phép tự quyết định huỷ chứng cứ tiền.
* Chế ra `contexts` giả để "nhận nuôi" chúng còn tệ hơn: nó hợp thức hoá dữ
  liệu hỏng, và màn Cá nhân sẽ in tiền đó dưới một cái tên chưa ai từng đặt.
* Cả hai đều là quyết định về DỮ LIỆU, có chủ sở hữu riêng (máy demo là của
  devops) và cần người quyết, không phải việc của một file migration.

Nên: chặn đường sinh ra hàng mồ côi mới, để nguyên lịch sử, và nói to số hàng
bẩn còn lại thay vì im lặng.

Trên database sạch (mọi schema test, cài mới, CI) migration tự chạy tiếp
`VALIDATE CONSTRAINT`, nên khoá ra ở trạng thái đã kiểm đầy đủ -- và
`tests/postgres/test_expense_context_fk_postgres.py` bắt buộc `convalidated`
phải là true sau một lần migrate sạch, để migration không thể lặng lẽ tự hạ cấp.

## Chiều xoá

Không khai `ON DELETE`, tức là `NO ACTION`: xoá một `contexts` còn giữ tiền sẽ
bị từ chối. Đây là chiều thứ hai sinh ra hàng mồ côi, và là chiều mà một
database đang sống thực sự đi qua -- chặn đường ghi chỉ ngăn hàng mồ côi được
SINH RA, không ngăn cả loạt hàng cũ hoá mồ côi cùng lúc vì nhóm bị xoá.

Revision ID: b3c7e0d24f19
Revises: d1e2f3a4b5c6
Create Date: 2026-08-30

Phần giờ-phút-giây của dòng `Create Date` mà alembic tự sinh bị bỏ đi, giống
các migration trước: chuỗi số liền của nó chạm luật `long-number` của repo
guard, vốn tồn tại để chặn số tài khoản lọt vào Git.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c7e0d24f19"
down_revision: str | Sequence[str] | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")

# Bảng tiền, theo thứ tự bảng chữ cái để log đọc được ổn định giữa các lần chạy.
MONEY_TABLES: tuple[str, ...] = ("bills", "collection_batches", "expenses")


def _constraint_name(table: str) -> str:
    # Khớp NAMING_CONVENTION trong app/db/base.py: fk_<table>_<column>.
    # Dài nhất là fk_collection_batches_context_id (32 ký tự), còn xa mốc 63.
    return f"fk_{table}_context_id"


def upgrade() -> None:
    # `--sql` (offline) mode has no database to ask, so `bind.execute` returns
    # nothing to read a count from. The orphan check below is therefore skipped
    # and both statements are emitted: a rendered script is read by a person
    # before it runs, and VALIDATE failing loudly in front of them is the right
    # outcome -- far better than a script that silently leaves the key unchecked.
    offline = op.get_context().as_sql
    bind = op.get_bind()

    for table in MONEY_TABLES:
        name = _constraint_name(table)
        op.execute(
            sa.text(
                f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" '
                f'FOREIGN KEY (context_id) REFERENCES "contexts" (id) NOT VALID'
            )
        )

        if offline:
            op.execute(sa.text(f'ALTER TABLE "{table}" VALIDATE CONSTRAINT "{name}"'))
            continue

        # Đếm trước khi VALIDATE để phân biệt được hai kết cục. Chạy thẳng
        # VALIDATE rồi bắt lỗi cũng ra đúng kết quả, nhưng lúc đó không còn
        # con số nào để in ra, mà con số mới là thứ người đọc log cần.
        #
        # NOT EXISTS chứ không phải JOIN: một inner join ở đây đếm nhầm theo
        # đúng chiều dễ chịu -- nó ĐÁNH RƠI chính những hàng đang cần đếm và
        # trả về "sạch". Lần đo đầu tiên của bug này lệch 329.667đ vì vậy.
        orphans = bind.execute(
            sa.text(
                f'SELECT count(*) FROM "{table}" t '
                f'WHERE NOT EXISTS (SELECT 1 FROM "contexts" c WHERE c.id = t.context_id)'
            )
        ).scalar_one()

        if orphans == 0:
            op.execute(sa.text(f'ALTER TABLE "{table}" VALIDATE CONSTRAINT "{name}"'))
            continue

        logger.warning(
            "%s: %d hàng có context_id không trỏ vào contexts nào. Khoá %s được "
            "thêm ở dạng NOT VALID -- mọi lệnh ghi mới đã bị chặn, nhưng số hàng "
            "cũ này KHÔNG được kiểm và vẫn còn nguyên trong sổ. Tiền của chúng "
            "vẫn cộng vào GET /people/{id}/finance. Dọn là một quyết định về dữ "
            "liệu, không phải về schema: chạy VALIDATE CONSTRAINT sau khi đã có "
            "người quyết xử lý số hàng đó thế nào.",
            table,
            orphans,
            name,
        )


def downgrade() -> None:
    for table in MONEY_TABLES:
        op.execute(
            sa.text(
                f'ALTER TABLE "{table}" DROP CONSTRAINT "{_constraint_name(table)}"'
            )
        )
