"""The catalogue tables, on a real PostgreSQL (M9, ADR-0017).

The fake repository in the api tier can be wrong about SQL in exactly the ways
that matter here: the CHECK constraints are the enforcement for «an imported
row cites its licence» and «a price band is ordered», and a fake cannot refuse
anything. So the refusals are proved here, against the schema Alembic built.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.repository import SqlAlchemyApiRepository
from app.db.models import Destination, Place
from app.places.seed_catalog import seed_place_catalog


def _place(**overrides) -> Place:
    base = dict(
        id="osm-node-777",
        destination_id="d-da-lat",
        name="Quán Thử",
        category="cafe",
        kinds=["Cà phê"],
        address=None,
        lat=11.94,
        lng=108.44,
        traits=[],
        source="osm",
        source_ref="node/777",
        license="ODbL-1.0",
    )
    base.update(overrides)
    return Place(**base)


def test_the_seeder_is_idempotent(postgres_session: Session):
    """The conftest already seeded; a second run must add nothing."""
    truoc = postgres_session.scalar(select(Place).where(Place.id.isnot(None)))
    assert truoc is not None, "conftest phải seed danh mục"
    dests, places = seed_place_catalog(postgres_session)
    assert (dests, places) == (0, 0)


def test_the_twelve_seed_rows_keep_their_ids(postgres_session: Session):
    """Everything else in the product points at these strings."""
    ids = set(
        postgres_session.scalars(select(Place.id).where(Place.source == "seed")).all()
    )
    assert "p-tiem-nuong-xom-lao" in ids
    assert "p-quan-oc-di-be" in ids
    assert len(ids) == 12


def test_seed_rows_carry_their_prose(postgres_session: Session):
    row = postgres_session.get(Place, "p-tiem-nuong-xom-lao")
    assert row is not None
    assert row.description
    assert row.reviews


def test_an_imported_row_without_a_licence_is_refused(postgres_session: Session):
    """ODbL attribution is a condition, so the database is where it is kept."""
    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(_place(license=None))
            postgres_session.flush()


def test_an_imported_row_without_a_source_ref_is_refused(postgres_session: Session):
    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(_place(source_ref=None))
            postgres_session.flush()


def test_an_unknown_source_is_refused(postgres_session: Session):
    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(
                _place(source="scraped", source_ref=None, license=None)
            )
            postgres_session.flush()


def test_a_backwards_price_band_is_refused(postgres_session: Session):
    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(_place(price_min_vnd=300_000, price_max_vnd=200_000))
            postgres_session.flush()


def test_a_rating_outside_the_scale_is_refused(postgres_session: Session):
    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(_place(rating=9.0))
            postgres_session.flush()


def test_the_same_osm_element_cannot_land_twice(postgres_session: Session):
    postgres_session.add(_place())
    postgres_session.flush()
    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(_place(id="osm-node-777-bis"))
            postgres_session.flush()


def test_a_place_needs_a_destination_that_exists(postgres_session: Session):
    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(_place(destination_id="d-khong-co"))
            postgres_session.flush()


def test_the_repository_reads_back_what_the_seeder_wrote(postgres_session: Session):
    repository = SqlAlchemyApiRepository(postgres_session)
    rows = repository.list_places()
    assert len(rows) >= 12
    one = repository.get_place("p-tiem-nuong-xom-lao")
    assert one is not None
    assert one.name == "Tiệm Nướng Xóm Lào"
    assert one.source == "seed"
    # `to_row()` is what every scorer reads; it must carry the shape they know.
    row = one.to_row()
    for key in ("id", "name", "category", "kinds", "traits", "price_min_vnd", "lat"):
        assert key in row


def test_filters_narrow_at_the_database(postgres_session: Session):
    repository = SqlAlchemyApiRepository(postgres_session)
    cafes = repository.list_places(category="cafe")
    assert cafes and all(row.category == "cafe" for row in cafes)
    da_lat = repository.list_places(destination_id="d-da-lat")
    assert da_lat and all(row.destination_id == "d-da-lat" for row in da_lat)
    assert repository.list_places(category="khong-co-that") == []


def test_destinations_come_back_in_a_stable_order(postgres_session: Session):
    repository = SqlAlchemyApiRepository(postgres_session)
    rows = repository.list_destinations()
    assert [row.id for row in rows] == sorted(
        (row.id for row in rows),
        key=lambda ident: (
            {r.id: r.sort_order for r in rows}[ident],
            ident,
        ),
    )
    assert repository.get_destination("d-da-lat") is not None
    assert repository.get_destination("d-khong-co") is None


def test_a_destination_box_must_be_the_right_way_round(postgres_session: Session):
    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(
                Destination(
                    id="d-sai",
                    name="Sai",
                    lat=10.0,
                    lng=100.0,
                    bbox_south=12.0,
                    bbox_west=100.0,
                    bbox_north=11.0,
                    bbox_east=101.0,
                )
            )
            postgres_session.flush()
