"""Destinations and places as tables (M9, ADR-0017).

`app/places/catalog.py` said it out loud: twelve invented rows, in code,
because a read-only catalogue for a proof of concept did not need a table --
and «when places become user-editable this file is the thing that gets
replaced». Real venue data may not enter Git (charter), so a catalogue of real
places has to live here, filled by an import script.

Nearly every column is nullable on purpose. OpenStreetMap gives a name, a
point and a kind; it does not give opening hours, prices or ratings. Null is
what «chưa có» is made of.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "destinations",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("province", sa.Text(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("bbox_south", sa.Float(), nullable=False),
        sa.Column("bbox_west", sa.Float(), nullable=False),
        sa.Column("bbox_north", sa.Float(), nullable=False),
        sa.Column("bbox_east", sa.Float(), nullable=False),
        sa.Column("blurb", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="destination_name_not_blank"),
        sa.CheckConstraint("lat >= -90 AND lat <= 90", name="destination_lat_range"),
        sa.CheckConstraint("lng >= -180 AND lng <= 180", name="destination_lng_range"),
        sa.CheckConstraint(
            "bbox_south < bbox_north AND bbox_west < bbox_east",
            name="destination_bbox_ordered",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_destinations"),
    )
    op.create_index("ix_destinations_order", "destinations", ["sort_order", "id"])

    op.create_table(
        "places",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("destination_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column(
            "kinds",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("rating_count", sa.Integer(), nullable=True),
        sa.Column("price_min_vnd", sa.BigInteger(), nullable=True),
        sa.Column("price_max_vnd", sa.BigInteger(), nullable=True),
        sa.Column("open_hours", sa.Text(), nullable=True),
        sa.Column("open_now", sa.Boolean(), nullable=True),
        sa.Column("travel_minutes", sa.Integer(), nullable=True),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("photo_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "traits",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("group_fit", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("flag", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reviews", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="place_name_not_blank"),
        sa.CheckConstraint("lat >= -90 AND lat <= 90", name="place_lat_range"),
        sa.CheckConstraint("lng >= -180 AND lng <= 180", name="place_lng_range"),
        sa.CheckConstraint(
            "source IN ('seed', 'osm', 'curated')", name="place_source_known"
        ),
        sa.CheckConstraint(
            "(source <> 'osm') OR (source_ref IS NOT NULL AND license IS NOT NULL)",
            name="place_osm_row_cites_its_source",
        ),
        sa.CheckConstraint(
            "price_min_vnd IS NULL OR price_min_vnd >= 0", name="place_price_min_sane"
        ),
        sa.CheckConstraint(
            "price_max_vnd IS NULL OR price_min_vnd IS NULL "
            "OR price_max_vnd >= price_min_vnd",
            name="place_price_band_ordered",
        ),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)", name="place_rating_range"
        ),
        sa.ForeignKeyConstraint(
            ["destination_id"], ["destinations.id"], name="fk_places_destination"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_places"),
        sa.UniqueConstraint("source", "source_ref", name="uq_places_source_ref"),
    )
    op.create_index(
        "ix_places_destination", "places", ["destination_id", "category", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_places_destination", table_name="places")
    op.drop_table("places")
    op.drop_index("ix_destinations_order", table_name="destinations")
    op.drop_table("destinations")
