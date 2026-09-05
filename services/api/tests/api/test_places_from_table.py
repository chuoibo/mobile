"""The catalogue route reads the table, and says what it does not know (M9).

Two claims worth a test of their own:

1. `GET /places` and `GET /places/{id}` go through the repository. The proof is
   a repository that answers with rows nothing else in the tree contains: if
   the route were still reading a module constant, these rows could not appear
   and the seed rows would appear instead.
2. A place with no price, no rating and no hours serves nulls -- not zeros, not
   invented numbers -- and still scores, because the badge rescales over what
   is known (ADR-0017 §2.3).
"""

from __future__ import annotations

import anyio
import pytest
from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import PlaceRecord

from .conftest import ASGITestClient, SeedCatalogueReads


def _row(**overrides) -> PlaceRecord:
    base = dict(
        id="osm-node-1",
        destination_id="d-da-lat",
        name="Cà Phê Sương",
        category="cafe",
        kinds=["Cà phê"],
        address="6 Khu Hòa Bình, Đà Lạt",
        lat=11.9418,
        lng=108.4372,
        rating=None,
        rating_count=None,
        price_min_vnd=None,
        price_max_vnd=None,
        open_hours="Mo-Su 07:00-22:00",
        open_now=None,
        travel_minutes=None,
        distance_km=None,
        photo_count=0,
        traits=["Wifi"],
        group_fit=None,
        flag=None,
        description=None,
        reviews=None,
        source="osm",
        source_ref="node/1",
        license="ODbL-1.0",
    )
    base.update(overrides)
    return PlaceRecord(**base)


class OneRowRepository(SeedCatalogueReads):
    """A catalogue of exactly the rows a test hands it."""

    def __init__(self, rows: list[PlaceRecord]):
        self.rows = rows

    def list_places(self, *, destination_id=None, category=None):
        return [
            row
            for row in self.rows
            if (destination_id is None or row.destination_id == destination_id)
            and (category is None or row.category == category)
        ]

    def get_place(self, place_id):
        for row in self.rows:
            if row.id == place_id:
                return row
        return None


def _client(repository, monkeypatch):
    """A client over one hand-made catalogue, wired like the shared `client`."""

    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    app = create_app(auth_mode="dev")
    app.dependency_overrides[get_repository] = lambda: repository
    return ASGITestClient(app)


@pytest.fixture()
def imported_client(monkeypatch):
    return _client(OneRowRepository([_row()]), monkeypatch)


def test_the_list_serves_the_row_the_repository_holds(imported_client):
    response = imported_client.get("/places")
    assert response.status_code == 200
    body = response.json()
    assert [place["id"] for place in body["places"]] == ["osm-node-1"]
    assert body["places"][0]["name"] == "Cà Phê Sương"


def test_unknown_facts_are_null_on_the_wire_never_zero(imported_client):
    place = imported_client.get("/places").json()["places"][0]
    for field in (
        "rating",
        "rating_count",
        "price_min_vnd",
        "price_max_vnd",
        "open_now",
        "travel_minutes",
        "distance_km",
        "group_fit",
    ):
        assert place[field] is None, f"{field} phải là null, nhận {place[field]!r}"
    assert place["open_hours"] == "Mo-Su 07:00-22:00"


def test_the_card_says_where_the_row_came_from(imported_client):
    place = imported_client.get("/places").json()["places"][0]
    assert place["source"] == "osm"
    assert place["license"] == "ODbL-1.0"


def test_a_place_with_no_price_still_scores_on_what_is_known(imported_client):
    """Rescaling, not a penalty: an unpriced place is not a bad place."""
    place = imported_client.get("/places").json()["places"][0]
    assert 0 <= place["match"]["score"] <= 100
    details = {
        factor["label"]: factor["detail"] for factor in place["match"]["factors"]
    }
    assert "chưa có giá" in details["Budget"]
    assert "chưa biết khoảng cách" in details["Khoảng cách"]


def test_an_empty_catalogue_is_an_empty_list_not_a_crash(monkeypatch):
    client = _client(OneRowRepository([]), monkeypatch)
    response = client.get("/places")
    assert response.status_code == 200
    assert response.json()["places"] == []


def test_detail_reads_the_same_table(imported_client):
    response = imported_client.get("/places/osm-node-1")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "osm-node-1"
    # Prose lives on the row now; an imported row has none, and says so with
    # null rather than with somebody else's description.
    assert body["description"] is None
    assert body["reviews"] == []
    assert imported_client.get("/places/khong-co-that").status_code == 404
