"""Bỏ đường thanh toán: hai bảng tài khoản ngân hàng và cột trỏ tới chúng.

Sản phẩm nói mỗi người phải bỏ ra bao nhiêu và vì những khoản nào, rồi dừng.
Chuyển tiền thế nào là việc giữa hai người, không phải việc của hệ thống — nên
không còn tài khoản để lưu, không còn bản chụp tài khoản để đóng băng vào một
đợt thu, và không còn cột nào trên nghĩa vụ trỏ tới chúng.

Nghĩa vụ không mất nghĩa: `sender_id`, `recipient_id`, `amount_vnd`, `due_at`
vẫn đủ để nói ai nợ ai bao nhiêu, tới khi nào.

`collection_obligations` là bảng chỉ-ghi-thêm, có trigger từ chối UPDATE và
DELETE **theo dòng**. Bỏ một cột là DDL chứ không phải sửa dòng, nên trigger
không kích hoạt và tính chỉ-ghi-thêm không bị nới. View
`collection_obligation_progress` chỉ đọc `id` và `amount_vnd` của bảng này nên
không chặn việc bỏ cột.

Đường lùi dựng lại đủ schema cũ, nhưng **từ chối chạy** khi bảng nghĩa vụ còn
dòng: cột cũ là NOT NULL và không có giá trị nào để điền vào cho một nghĩa vụ
đã tồn tại. Bịa một bản chụp tài khoản để thoả ràng buộc là cách tệ nhất để
downgrade một bảng tiền.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7a1c4d90b52"
down_revision: str | Sequence[str] | None = "c9f28a4d1b73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_obligations_snapshot_same_batch_version",
        "collection_obligations",
        type_="foreignkey",
    )
    op.drop_column("collection_obligations", "bank_recipient_snapshot_id")

    op.drop_index(
        "ix_bank_recipient_snapshots_batch_version_id",
        table_name="bank_recipient_snapshots",
    )
    # The trigger that made this table append-only goes with the table.
    op.drop_table("bank_recipient_snapshots")

    op.drop_index("uq_bank_recipients_active_recipient", table_name="bank_recipients")
    op.drop_index("ix_bank_recipients_recipient_id", table_name="bank_recipients")
    op.drop_table("bank_recipients")


def downgrade() -> None:
    obligations = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM collection_obligations"))
        .scalar_one()
    )
    if obligations:
        raise RuntimeError(
            f"{obligations} collection_obligations exist and the old schema "
            "requires a bank_recipient_snapshot_id for each; there is no value "
            "to restore. Refusing rather than inventing a bank destination."
        )

    op.create_table(
        "bank_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_bin", sa.String(length=6), nullable=False),
        sa.Column("account_number", sa.String(length=32), nullable=False),
        sa.Column("account_name", sa.Text(), nullable=False),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "account_number ~ '^[0-9A-Za-z]{6,32}$'",
            name="ck_bank_recipients_account_number_format",
        ),
        sa.CheckConstraint(
            "bank_bin ~ '^[0-9]{6}$'", name="ck_bank_recipients_bank_bin_format"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bank_recipients"),
    )
    op.create_index(
        "ix_bank_recipients_recipient_id", "bank_recipients", ["recipient_id"]
    )
    op.create_index(
        "uq_bank_recipients_active_recipient",
        "bank_recipients",
        ["recipient_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "bank_recipient_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_bin", sa.String(length=6), nullable=False),
        sa.Column("account_number", sa.String(length=32), nullable=False),
        sa.Column("account_name", sa.Text(), nullable=False),
        sa.Column(
            "snapshotted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "account_number ~ '^[0-9A-Za-z]{6,32}$'",
            name="ck_bank_recipient_snapshots_account_number_format",
        ),
        sa.CheckConstraint(
            "bank_bin ~ '^[0-9]{6}$'",
            name="ck_bank_recipient_snapshots_bank_bin_format",
        ),
        sa.ForeignKeyConstraint(
            ["bank_recipient_id"],
            ["bank_recipients.id"],
            name="fk_bank_recipient_snapshots_bank_recipient_id_bank_recipients",
        ),
        sa.ForeignKeyConstraint(
            ["batch_version_id"],
            ["collection_batch_versions.id"],
            name="fk_bank_recipient_snapshots_batch_version_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bank_recipient_snapshots"),
        sa.UniqueConstraint(
            "id", "batch_version_id", name="uq_bank_recipient_snapshots_id_batch"
        ),
    )
    op.create_index(
        "ix_bank_recipient_snapshots_batch_version_id",
        "bank_recipient_snapshots",
        ["batch_version_id"],
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER reject_bank_recipient_snapshots_mutation
            BEFORE UPDATE OR DELETE ON bank_recipient_snapshots
            FOR EACH ROW
            EXECUTE FUNCTION reject_immutable_financial_row_change()
            """
        )
    )

    op.add_column(
        "collection_obligations",
        sa.Column(
            "bank_recipient_snapshot_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_obligations_snapshot_same_batch_version",
        "collection_obligations",
        "bank_recipient_snapshots",
        ["bank_recipient_snapshot_id", "batch_version_id"],
        ["id", "batch_version_id"],
    )
