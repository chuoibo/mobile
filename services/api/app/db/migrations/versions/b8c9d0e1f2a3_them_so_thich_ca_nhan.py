"""Personal tastes, stored (M11, ADR-0019).

The personalization step has collected eight taste chips and a budget band
since the first build and then said so on the screen: «Chưa gửi lên máy chủ.»
It was true -- there was no table and no route -- and it is what made the
screen honest rather than a shell. This migration is the other half.

Two shapes, because the two answers are different in kind: a taste is a set
(a person may claim several, and each is countable across a group), a budget
is one answer out of three (or none). So tastes get a table with a uniqueness
rule that protects every count computed from it, and the band gets a column.

No CHECK lists the vocabulary. The words are a product decision that will grow
and the domain owns them; a constraint here would make adding one chip a
migration. The uniqueness rule is the part that has to be in the database,
because it is the part that would corrupt arithmetic.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("people", sa.Column("budget_band", sa.Text(), nullable=True))
    op.create_table(
        "person_interests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(tag)) > 0", name="person_interest_tag_not_blank"
        ),
        sa.ForeignKeyConstraint(
            ["person_id"], ["people.id"], name="fk_person_interests_person"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_person_interests"),
        sa.UniqueConstraint("person_id", "tag", name="uq_person_interests_person_tag"),
    )
    op.create_index(
        "ix_person_interests_person", "person_interests", ["person_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_person_interests_person", table_name="person_interests")
    op.drop_table("person_interests")
    op.drop_column("people", "budget_band")
