"""Điểm đến: the list, the default, and the position that is not kept (M10).

Two promises are tested here rather than reviewed: `GET /places` always names
the destination it served, and `GET /destinations?lat&lng` answers «which city
am I in» without keeping, echoing or logging where the caller was (ADR-0018).
"""

from __future__ import annotations

import anyio
import pytest

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import DestinationRecord

from .conftest import ASGITestClient, SeedCatalogueReads, _seed_place_records

DA_LAT = DestinationRecord(
    id="d-da-lat",
    name="Đà Lạt",
    province="Lâm Đồng",
    lat=11.9404,
    lng=108.4583,
    bbox_south=11.88,
    bbox_west=108.38,
    bbox_north=12.00,
    bbox_east=108.52,
    blurb="Thành phố sương mù",
    sort_order=10,
)
HA_NOI = DestinationRecord(
    id="d-ha-noi",
    name="Hà Nội",
    province="Hà Nội",
    lat=21.0285,
    lng=105.8542,
    bbox_south=20.98,
    bbox_west=105.81,
    bbox_north=21.07,
    bbox_east=105.90,
    blurb="Phố cổ",
    sort_order=30,
)


class TwoCityRepository(SeedCatalogueReads):
    """Two destinations; every seed place belongs to the first."""

    def list_destinations(self):
        return [DA_LAT, HA_NOI]

    def get_destination(self, destination_id):
        for row in (DA_LAT, HA_NOI):
            if row.id == destination_id:
                return row
        return None

    def list_places(self, *, destination_id=None, category=None):
        rows = [
            row
            for row in _seed_place_records()
            if destination_id in (None, "d-da-lat")
            and (category is None or row.category == category)
        ]
        return sorted(rows, key=lambda row: row.id)


@pytest.fixture()
def client(monkeypatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    app = create_app(auth_mode="dev")
    app.dependency_overrides[get_repository] = lambda: TwoCityRepository()
    return ASGITestClient(app)


def test_the_list_names_the_destination_it_served(client):
    body = client.get("/places").json()
    assert body["destination"]["id"] == "d-da-lat"
    assert body["destination"]["name"] == "Đà Lạt"


def test_the_default_is_the_first_by_sort_order_not_an_accident(client):
    """A caller who has not chosen gets a real city, and is told which."""
    body = client.get("/places").json()
    assert body["destination"]["id"] == "d-da-lat"
    assert body["places"], "điểm đến mặc định phải có địa điểm thật trong đó"


def test_asking_for_the_other_city_narrows_the_list(client):
    body = client.get("/places?destination=d-ha-noi").json()
    assert body["destination"]["id"] == "d-ha-noi"
    assert body["places"] == [], "Hà Nội chưa nhập chỗ nào, và đó là một câu trả lời"


def test_an_unknown_destination_is_404_not_a_silent_default(client):
    """Serving Đà Lạt to somebody who asked for a city we do not have would
    look like an answer and be a lie about where those places are."""
    response = client.get("/places?destination=d-khong-co")
    assert response.status_code == 404
    assert response.json()["code"] == "destination_not_found"


def test_destinations_come_back_in_order(client):
    body = client.get("/destinations").json()
    assert [row["id"] for row in body["destinations"]] == ["d-da-lat", "d-ha-noi"]
    assert body["nearest"] is None
    assert all(row["distance_km"] is None for row in body["destinations"])


def test_coordinates_name_the_city_and_are_not_echoed_back(client):
    """The answer is a city and a rounded distance -- never the position."""
    response = client.get("/destinations?lat=11.95&lng=108.44")
    body = response.json()
    assert body["nearest"]["id"] == "d-da-lat"
    assert body["nearest"]["distance_km"] < 5
    raw = response.text
    assert "11.95" not in raw and "108.44" not in raw, "toạ độ của người gọi bị dội lại"


def test_a_position_far_from_everything_gets_no_city(client):
    """Middle of the East Sea: nearest row is hundreds of km away, and the
    honest answer is null rather than the least-wrong city."""
    body = client.get("/destinations?lat=15.0&lng=113.0").json()
    assert body["nearest"] is None
    assert [row["id"] for row in body["destinations"]] == ["d-da-lat", "d-ha-noi"]


def test_the_nearest_is_the_nearest_not_the_first(client):
    body = client.get("/destinations?lat=21.0&lng=105.85").json()
    assert body["nearest"]["id"] == "d-ha-noi"
    assert body["destinations"][0]["id"] == "d-ha-noi", "sắp theo khoảng cách"


def test_half_a_position_is_a_refusal_not_half_an_answer(client):
    for query in ("?lat=11.9", "?lng=108.4"):
        response = client.get(f"/destinations{query}")
        assert response.status_code == 422
        assert response.json()["code"] == "coordinates_incomplete"


def test_an_out_of_range_coordinate_is_refused_by_the_route(client):
    assert client.get("/destinations?lat=99&lng=108").status_code == 422
