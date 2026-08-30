"""Add posts (F39) with their four privacy levels (F42).

One table. `audience` is a constrained string rather than a native enum, the
same as every other enum in this schema, so a fifth level later is a CHECK
change instead of an `ALTER TYPE` that cannot run inside a transaction.

`audience_matches_target` is the invariant that keeps the other three levels
free of a group id. Without it a `only_me` row could carry a `context_id`, and
the first query that joins posts to contexts -- a perfectly reasonable query to
write -- would hand somebody's private note to a group they mentioned once.

The three indexes are the three reads. `ix_posts_group_feed` and
`ix_posts_public_feed` are partial: an `only_me` row appears in neither, and is
reachable only through `ix_posts_author_feed`, which is exactly the one read
that is allowed to return it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7d3f2b81c56"
down_revision: str | Sequence[str] | None = "c5e14b7a9d02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "audience",
            sa.Enum(
                "only_me",
                "friends",
                "group",
                "public",
                name="post_audience",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("body <> ''", name=op.f("ck_posts_body_not_blank")),
        # Held by the database, not only by `app.domain.post_audience`. A row
        # written by anything that skips that layer still cannot disagree.
        sa.CheckConstraint(
            "(audience = 'group') = (context_id IS NOT NULL)",
            name=op.f("ck_posts_audience_matches_target"),
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["people.id"],
            name="fk_posts_author",
        ),
        sa.ForeignKeyConstraint(
            ["context_id"],
            ["contexts.id"],
            name="fk_posts_context",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_posts")),
    )
    op.create_index(
        "ix_posts_author_feed",
        "posts",
        ["author_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_posts_group_feed",
        "posts",
        ["context_id", sa.text("created_at DESC")],
        postgresql_where=sa.text("audience = 'group'"),
    )
    op.create_index(
        "ix_posts_public_feed",
        "posts",
        [sa.text("created_at DESC")],
        postgresql_where=sa.text("audience = 'public'"),
    )


def downgrade() -> None:
    op.drop_index("ix_posts_public_feed", table_name="posts")
    op.drop_index("ix_posts_group_feed", table_name="posts")
    op.drop_index("ix_posts_author_feed", table_name="posts")
    # Takes `ck_posts_audience_matches_target` and the audience CHECK with it.
    op.drop_table("posts")
