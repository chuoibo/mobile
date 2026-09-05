"""Put the invented seed catalogue into the `places` table (M9, ADR-0017).

`app/places/catalog.py` and `app/places/details.py` stop being the catalogue
and become **seed material**: twelve invented rows and their invented prose,
loaded into the table for demos and tests so every flow, fixture and Maestro
assertion that names `p-tiem-nuong-xom-lao` keeps working. A production
database runs the OpenStreetMap import instead, or as well.

Idempotent: running twice changes nothing. Written as a function on a Session
rather than a script so `make demo`, the e2e stack and the Postgres tests can
all call the same code path.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Destination, Place
from app.places.catalog import PLACES
from app.places.details import find_detail

# Two destinations, because the twelve seed rows sit in two cities. Coordinates
# are the city centres; the boxes are wide enough to hold the seed rows and are
# what the OSM importer would query with.
SEED_DESTINATIONS: list[dict[str, Any]] = [
    {
        "id": "d-da-lat",
        "name": "Đà Lạt",
        "province": "Lâm Đồng",
        "lat": 11.9404,
        "lng": 108.4583,
        "bbox_south": 11.88,
        "bbox_west": 108.38,
        "bbox_north": 12.00,
        "bbox_east": 108.52,
        "blurb": "Thành phố sương mù, quán cà phê và đồi thông.",
        "sort_order": 10,
    },
    {
        "id": "d-tphcm",
        "name": "TP. Hồ Chí Minh",
        "province": "TP. Hồ Chí Minh",
        "lat": 10.7769,
        "lng": 106.7009,
        "bbox_south": 10.68,
        "bbox_west": 106.60,
        "bbox_north": 10.88,
        "bbox_east": 106.82,
        "blurb": "Ăn khuya, rooftop và cà phê vợt trong hẻm.",
        "sort_order": 20,
    },
]


def _destination_for(place: dict[str, Any]) -> str:
    """Which seeded city a seed row belongs to, from its own address string.

    A lookup by address rather than a hand-written map: the addresses are in
    the same file as the rows, so a thirteenth seed row lands in the right city
    without anybody remembering to edit a second list.
    """
    address = str(place.get("address", ""))
    if "Đà Lạt" in address:
        return "d-da-lat"
    return "d-tphcm"


def seed_place_catalog(session: Session) -> tuple[int, int]:
    """Insert any missing seed destinations and places. Returns (dests, places).

    Existing rows are left exactly as they are: this function is for filling an
    empty catalogue, not for republishing over one somebody has since imported.
    """
    da_co_dd = set(session.scalars(select(Destination.id)).all())
    them_dd = 0
    for row in SEED_DESTINATIONS:
        if row["id"] in da_co_dd:
            continue
        session.add(Destination(**row))
        them_dd += 1
    session.flush()

    da_co = set(session.scalars(select(Place.id)).all())
    them = 0
    for place in PLACES:
        if place["id"] in da_co:
            continue
        prose = find_detail(place["id"])
        session.add(
            Place(
                id=place["id"],
                destination_id=_destination_for(place),
                name=place["name"],
                category=place["category"],
                kinds=list(place["kinds"]),
                address=place["address"],
                lat=place["lat"],
                lng=place["lng"],
                rating=place["rating"],
                rating_count=place["rating_count"],
                price_min_vnd=place["price_min_vnd"],
                price_max_vnd=place["price_max_vnd"],
                open_hours=place["open_hours"],
                open_now=place["open_now"],
                travel_minutes=place["travel_minutes"],
                distance_km=place["distance_km"],
                photo_count=place["photo_count"],
                traits=list(place["traits"]),
                group_fit=dict(place["group_fit"]),
                flag=place["flag"],
                description=None if prose is None else prose["description"],
                reviews=None if prose is None else list(prose["reviews"]),
                source="seed",
                source_ref=None,
                license=None,
            )
        )
        them += 1
    session.flush()
    return them_dd, them


def main() -> int:
    """`python3 -m app.places.seed_catalog` -- fill an empty catalogue.

    Used by the e2e stack and the demo box, which both have a fresh database
    and no import of their own. Reads `MOBILE_DATABASE_URL`, like every other
    script that talks to the database directly.
    """
    import os

    from sqlalchemy import create_engine

    url = os.environ.get("MOBILE_DATABASE_URL", "").strip()
    if not url:
        print("MOBILE_DATABASE_URL chưa đặt", flush=True)
        return 2
    engine = create_engine(url)
    with Session(engine) as session:
        dests, places = seed_place_catalog(session)
        session.commit()
    print(f"danh mục seed: thêm {dests} điểm đến, {places} địa điểm", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
