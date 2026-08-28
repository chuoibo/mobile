"""`GET /places` -- the catalogue the Khám phá screen reads (rd-be-05).

What this tier proves and what it does not
------------------------------------------
These run against the fake repository, so they prove the wire shape, the
deterministic score, and the refusal rules. They do **not** prove anything
about Gemini: the reason writer is injected, and the tests here supply one that
never touches the network. The live model call has its own tier in
``tests/live/test_places_gemini_live.py``, which is skipped without a key --
and a skip there is not a green.

The rule these tests exist to hold is the one rd-be-05 was written for: a score
is only ever shown next to a reason somebody can check, and a sentence nobody
generated is never served wearing an ``ai`` label.
"""

from __future__ import annotations

import pytest

from app.api.routes.places import get_reason_writer
from app.places.catalog import CATEGORIES, GROUP, PLACES
from app.places.reasons import PlaceReason


def fixed_reasons(rows):
    """A reason writer that answers for every row, without a network call."""

    return {
        row.place["id"]: PlaceReason(
            verdict="hop",
            reason=f"Giá {row.place['price_min_vnd'] // 1000}k hợp túi nhóm.",
        )
        for row in rows
    }


def silent_reasons(rows):
    """A writer that answers for nobody -- the Gemini-is-down case."""

    del rows
    return {}


@pytest.fixture(autouse=True)
def no_network(client):
    """No test in this module is allowed to reach Gemini.

    Default to the silent writer rather than the fixed one: a test that forgets
    to say which writer it wants gets the honest-failure path, so an accidental
    omission surfaces as a missing AI label rather than as a fabricated one.
    """

    client.app.dependency_overrides[get_reason_writer] = lambda: silent_reasons
    return client


def use_writer(client, writer):
    client.app.dependency_overrides[get_reason_writer] = lambda: writer


def get_places(client, **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return client.get(f"/places?{query}" if query else "/places")


def test_places_route_exists_and_returns_the_catalogue(client):
    """The reproduction. Before rd-be-05 this answered 404 for every caller.

    The app's `fetchPlaces` turns that 404 into a `chua-co-endpoint` screen, so
    Khám phá had a route to nowhere and no amount of front-end work could have
    fixed it.
    """

    response = get_places(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body["places"], list)
    assert body["places"], "catalogue served zero places"
    assert body["categories"] == [
        {"id": category["id"], "label": category["label"]} for category in CATEGORIES
    ]


def test_every_place_carries_the_fields_the_app_parses(client):
    """`parsePlace` in `places.ts` throws on a missing field; that throw is a
    blank tab in front of a person. Pin the field list on this side too."""

    body = get_places(client).json()
    required = {
        "id",
        "name",
        "category",
        "kinds",
        "rating",
        "rating_count",
        "distance_km",
        "price_min_vnd",
        "price_max_vnd",
        "address",
        "open_now",
        "open_hours",
        "travel_minutes",
        "photo_count",
        "traits",
        "group_fit",
        "flag",
        "lat",
        "lng",
        "match",
    }
    for place in body["places"]:
        assert required <= set(place), f"{place.get('id')} thiếu {required - set(place)}"
        assert place["flag"] in (None, "new", "hot")


def test_prices_are_whole_dong_at_the_boundary(client):
    """Money law 1 does not stop at the ledger. A price band that leaves the
    server fractional is a float that got into a money value somewhere."""

    for place in get_places(client).json()["places"]:
        for field in ("price_min_vnd", "price_max_vnd"):
            value = place[field]
            assert isinstance(value, int) and not isinstance(value, bool), (
                f"{place['id']}.{field} = {value!r} is not an int"
            )
        assert place["price_min_vnd"] <= place["price_max_vnd"]


def test_source_is_ai_only_when_a_reason_was_actually_written(client):
    """The whole point of the work item.

    `matchLabel` in `places.ts` prints the words AI MATCH on `source == "ai"`
    and nothing else. So `ai` has to mean a model answered for *this* place.
    """

    use_writer(client, fixed_reasons)
    for place in get_places(client).json()["places"]:
        assert place["match"]["source"] == "ai"
        assert place["match"]["reason"].strip()


def test_gemini_silence_never_produces_an_ai_labelled_sentence(client):
    """When the model answers for nobody, no card may claim it did.

    This is the failure mode the deleted stub server had built in: a canned
    Vietnamese sentence is indistinguishable from a generated one once it is on
    screen, and three days later nobody remembers which is which.
    """

    use_writer(client, silent_reasons)
    for place in get_places(client).json()["places"]:
        assert place["match"]["source"] == "none", place["id"]
        # A score with no reason still renders -- as a plain score, with the
        # factors that produced it. That sentence is assembled from the same
        # numbers, so it is checkable; it is just not the model's.
        assert place["match"]["reason"].strip()
        assert place["match"]["factors"]


def test_score_is_between_0_and_100_and_the_factors_explain_it(client):
    for place in get_places(client).json()["places"]:
        match = place["match"]
        assert 0 <= match["score"] <= 100
        labels = [factor["label"] for factor in match["factors"]]
        assert labels == ["Budget", "Sở thích", "Nhóm", "Khoảng cách"]
        for factor in match["factors"]:
            assert factor["detail"].strip()


def test_places_are_ordered_best_first(client):
    scores = [place["match"]["score"] for place in get_places(client).json()["places"]]
    assert scores == sorted(scores, reverse=True)


def test_category_filter_narrows_the_list(client):
    everything = get_places(client).json()["places"]
    cafes = get_places(client, category="cafe").json()["places"]
    assert cafes, "no place in the seed catalogue is a cafe"
    assert len(cafes) < len(everything)
    assert {place["category"] for place in cafes} == {"cafe"}


def test_unknown_category_is_an_empty_list_not_an_error(client):
    """An empty answer is a real answer. 404 here would send the app to the
    `chua-co-endpoint` screen, which says the route is unbuilt -- a lie."""

    response = get_places(client, category="khong-co-loai-nay")
    assert response.status_code == 200
    assert response.json()["places"] == []


def test_free_text_query_matches_name_and_traits(client):
    hits = get_places(client, q="nướng").json()["places"]
    assert hits
    for place in hits:
        haystack = " ".join([place["name"], *place["kinds"], *place["traits"]]).lower()
        assert "nướng" in haystack


def test_the_group_profile_the_score_is_computed_against_is_disclosed(client):
    """A percentage with no stated basis is a decoration. The app renders the
    factors; the group those factors are relative to has to travel with them."""

    body = get_places(client).json()
    assert body["group"]["size"] == GROUP["size"]
    assert body["group"]["budget_per_person_vnd"] == GROUP["budget_per_person_vnd"]
    assert isinstance(body["group"]["budget_per_person_vnd"], int)


def test_catalogue_ids_are_unique(client):
    ids = [place["id"] for place in get_places(client).json()["places"]]
    assert len(ids) == len(set(ids))
    assert len(ids) == len(PLACES)
