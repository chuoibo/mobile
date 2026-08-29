"""Add sanitized uploads for private group photos and personal avatars."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8c4a1d92e67"
down_revision: str | Sequence[str] | None = "e3b8c1d5720f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "uploaded_images",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("context_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("owner_person_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("uploaded_by_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "num_nonnulls(context_id, owner_person_id) = 1",
            name=op.f("ck_uploaded_images_image_has_one_owner"),
        ),
        sa.CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png')",
            name=op.f("ck_uploaded_images_content_type_allowed"),
        ),
        sa.CheckConstraint(
            "byte_size > 0 AND width > 0 AND height > 0",
            name=op.f("ck_uploaded_images_image_dimensions_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["context_id"],
            ["contexts.id"],
            name="fk_uploaded_images_context",
        ),
        sa.ForeignKeyConstraint(
            ["owner_person_id"],
            ["people.id"],
            name="fk_uploaded_images_owner",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["people.id"],
            name="fk_uploaded_images_uploaded_by",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uploaded_images")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_uploaded_images_storage_key")),
    )
    op.create_index(
        "ix_uploaded_images_context",
        "uploaded_images",
        [sa.text("context_id"), sa.text("created_at DESC")],
        postgresql_where=sa.text("context_id IS NOT NULL"),
    )
    op.create_index(
        "ix_uploaded_images_avatar",
        "uploaded_images",
        [sa.text("owner_person_id"), sa.text("created_at DESC")],
        postgresql_where=sa.text("owner_person_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_uploaded_images_avatar", table_name="uploaded_images")
    op.drop_index("ix_uploaded_images_context", table_name="uploaded_images")
    op.drop_table("uploaded_images")
