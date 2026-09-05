"""F10 -- `GET /places/{id}`, the screen behind a card.

What this tier proves: the wire shape, the 404, and the one property that
matters most on a detail screen -- that the score and the AI label here are the
*same* ones the grid showed, computed by the same code rather than recomputed
alongside it.

What it does not prove: anything about Gemini. The reason writer is injected and
never opens a socket, exactly as in `test_places.py`.
"""

from __future__ import annotations

import pytest

from app.api.routes.places import get_reason_writer
from app.places.catalog import PLACES
from app.places.details import PLACE_DETAILS
from app.places.scoring import score_place

from .test_places import GU_TOI, dang_nhap, fixed_reasons, silent_reasons, use_writer

PLACE = PLACES[0]


@pytest.fixture(autouse=True)
def no_network(client):
    client.app.dependency_overrides[get_reason_writer] = lambda: silent_reasons
    return client


def test_a_known_place_comes_back_whole(client):
    response = client.get(f"/places/{PLACE['id']}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == PLACE["id"]
    assert body["name"] == PLACE["name"]
    assert body["address"] == PLACE["address"]
    assert body["open_hours"] == PLACE["open_hours"]
    assert body["lat"] == PLACE["lat"]
    assert body["lng"] == PLACE["lng"]
    assert body["group_fit"] == PLACE["group_fit"]


def test_it_carries_every_field_f10_names(client):
    """The spec lists photos, rating, address, price, distance, opening hours,
    description, tags, reviews, map and group suitability. Each one is a field
    here or is declared absent -- `photos_available` is the declaration."""

    body = client.get(f"/places/{PLACE['id']}").json()
    for field in (
        "photo_count",
        "photos_available",
        "rating",
        "rating_count",
        "address",
        "price_min_vnd",
        "price_max_vnd",
        "distance_km",
        "travel_minutes",
        "open_hours",
        "open_now",
        "description",
        "kinds",
        "traits",
        "reviews",
        "lat",
        "lng",
        "group_fit",
        "match",
    ):
        assert field in body, f"detail response is missing {field}"


def test_prices_stay_integer_dong(client):
    """Money law 1 does not stop at the ledger. A price that arrives here as a
    float means one reached a money value upstream."""

    body = client.get(f"/places/{PLACE['id']}").json()
    assert isinstance(body["price_min_vnd"], int)
    assert isinstance(body["price_max_vnd"], int)
    assert not isinstance(body["price_min_vnd"], bool)


def test_the_score_matches_the_grid_exactly(client, repository):
    """One place, one number. Two call sites computing a score separately is
    how the same restaurant shows 94% on one screen and 87% on the next."""

    headers = dang_nhap(repository)
    listed = client.get("/places", headers=headers).json()
    card = next(row for row in listed["places"] if row["id"] == PLACE["id"])
    detail = client.get(f"/places/{PLACE['id']}", headers=headers).json()
    assert detail["match"]["score"] == card["match"]["score"]
    assert detail["match"]["factors"] == card["match"]["factors"]
    # And that both agree with the arithmetic, not merely with each other:
    # two screens showing the same wrong number is still wrong.
    assert detail["match"]["score"] == score_place(PLACE, GU_TOI)[0]


def test_a_signed_out_reader_gets_the_row_without_a_badge(client):
    """The detail page is public and stays public. What a session buys is the
    percentage, because a match is a match with somebody."""

    body = client.get(f"/places/{PLACE['id']}").json()
    assert body["match"] is None
    assert body["name"] == PLACE["name"] and body["address"] == PLACE["address"]


def test_no_model_answer_means_no_ai_label(client, repository):
    """The silent writer is active. `source` must be `none` and `verdict` must
    be absent -- a percentage credited to a model that never answered is the
    exact lie `Match` exists to prevent."""

    body = client.get(f"/places/{PLACE['id']}", headers=dang_nhap(repository)).json()
    assert body["match"]["source"] == "none"
    assert body["match"]["verdict"] is None
    assert body["match"]["reason"]


def test_a_model_answer_is_labelled_ai(client, repository):
    use_writer(client, fixed_reasons)
    body = client.get(f"/places/{PLACE['id']}", headers=dang_nhap(repository)).json()
    assert body["match"]["source"] == "ai"
    assert body["match"]["verdict"] == "hop"


def test_a_writer_that_raises_does_not_become_a_500(client, repository):
    """A read-only catalogue row must survive a model outage."""

    def exploding(rows, group=None):
        del rows
        raise RuntimeError("gemini is down")

    use_writer(client, exploding)
    response = client.get(f"/places/{PLACE['id']}", headers=dang_nhap(repository))
    assert response.status_code == 200, response.text
    assert response.json()["match"]["source"] == "none"


def test_an_unknown_id_is_404_and_says_so_in_vietnamese(client):
    """404 rather than an empty 200: a caller has to be able to tell "no such
    place" from "this place has no details"."""

    response = client.get("/places/p-khong-ton-tai")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "place_not_found"
    assert "địa điểm" in body["detail"].lower()


def test_the_error_message_carries_no_machine_code(client):
    """Câu chữ tiếng Việt, no server-side error code on the screen."""

    detail = client.get("/places/p-khong-ton-tai").json()["detail"]
    assert "place_not_found" not in detail
    assert "404" not in detail


def test_the_search_route_is_not_shadowed(client):
    """`/places/{place_id}` is declared first and must not swallow the POST.

    Starlette treats a path match with the wrong method as a partial match and
    keeps scanning, so the later full match still wins. Pinned because the
    failure mode is a 404 on search that looks like the feature was deleted.
    """

    response = client.post("/places/search", json={"query": "quán nướng"})
    assert response.status_code != 404


def test_a_get_on_the_search_path_is_a_place_lookup(client):
    """The other half: `GET /places/search` has no full match and lands here
    as an id that does not exist."""

    response = client.get("/places/search")
    assert response.status_code == 404
    assert response.json()["code"] == "place_not_found"


def test_description_and_reviews_come_from_the_seed(client):
    seed = PLACE_DETAILS[PLACE["id"]]
    body = client.get(f"/places/{PLACE['id']}").json()
    assert body["description"] == seed["description"]
    assert [review["author"] for review in body["reviews"]] == [
        review["author"] for review in seed["reviews"]
    ]


def test_every_catalogue_place_has_a_detail_page(client):
    """A card the grid draws must open. A place with no prose still answers
    200 with `description: null` rather than 404."""

    for place in PLACES:
        response = client.get(f"/places/{place['id']}")
        assert response.status_code == 200, f"{place['id']}: {response.text}"


def test_photos_are_declared_absent_rather_than_faked(client):
    """There is no image store for venues. An array of invented urls would
    render as broken frames; saying so is the honest alternative."""

    body = client.get(f"/places/{PLACE['id']}").json()
    assert body["photos_available"] is False
    assert "photos" not in body
