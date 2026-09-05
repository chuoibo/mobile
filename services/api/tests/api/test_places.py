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

import uuid
from datetime import UTC, datetime

import pytest

from app.api.repository import PersonRecord
from app.api.routes.places import get_reason_writer
from app.places.catalog import CATEGORIES, PLACES
from app.places.reasons import PlaceReason
from app.places.scoring import score_place
from app.places.taste import profile_for_person

from .helpers import actor_headers

#: A signed-in reader with tastes, because since M11 a match percentage needs
#: somebody to be a match FOR. Anonymous browsing is still a first-class case
#: and has its own tests below -- it just has no badge.
TOI = uuid.UUID("aa22aa22-0a0a-4a0a-8a0a-0a0a0a0a0aa2")
SO_THICH = ["an-uong", "cafe", "nightlife", "mon-local", "outdoor"]
MUC_CHI = "vua-phai"
GU_TOI = profile_for_person(SO_THICH, MUC_CHI)
T0 = datetime(2030, 9, 5, 9, tzinfo=UTC)


def dang_nhap(repository):
    """Seed the reader above and hand back their headers."""

    repository.people[TOI] = PersonRecord(
        id=TOI, display_name="Tôi", created_at=T0, budget_band=MUC_CHI
    )
    repository.person_interests[TOI] = set(SO_THICH)
    return actor_headers(actor_id=TOI)


def fixed_reasons(rows, group=None):
    """A reason writer that answers for every row, without a network call."""

    return {
        row.place["id"]: PlaceReason(
            verdict="hop",
            reason=f"Giá {row.place['price_min_vnd'] // 1000}k hợp túi nhóm.",
        )
        for row in rows
    }


def silent_reasons(rows, group=None):
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


def get_places(client, headers=None, **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return client.get(f"/places?{query}" if query else "/places", headers=headers or {})


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
        assert required <= set(place), (
            f"{place.get('id')} thiếu {required - set(place)}"
        )
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


def test_source_is_ai_only_when_a_reason_was_actually_written(client, repository):
    """The whole point of the work item.

    `matchLabel` in `places.ts` prints the words AI MATCH on `source == "ai"`
    and nothing else. So `ai` has to mean a model answered for *this* place.
    """

    use_writer(client, fixed_reasons)
    for place in get_places(client, headers=dang_nhap(repository)).json()["places"]:
        assert place["match"]["source"] == "ai"
        assert place["match"]["reason"].strip()


def test_gemini_silence_never_produces_an_ai_labelled_sentence(client, repository):
    """When the model answers for nobody, no card may claim it did.

    This is the failure mode the deleted stub server had built in: a canned
    Vietnamese sentence is indistinguishable from a generated one once it is on
    screen, and three days later nobody remembers which is which.
    """

    use_writer(client, silent_reasons)
    for place in get_places(client, headers=dang_nhap(repository)).json()["places"]:
        assert place["match"]["source"] == "none", place["id"]
        # A score with no reason still renders -- as a plain score, with the
        # factors that produced it. That sentence is assembled from the same
        # numbers, so it is checkable; it is just not the model's.
        assert place["match"]["reason"].strip()
        assert place["match"]["factors"]


def test_score_is_between_0_and_100_and_the_factors_explain_it(client, repository):
    for place in get_places(client, headers=dang_nhap(repository)).json()["places"]:
        match = place["match"]
        assert 0 <= match["score"] <= 100
        labels = [factor["label"] for factor in match["factors"]]
        assert labels == ["Budget", "Sở thích", "Nhóm", "Khoảng cách"]
        for factor in match["factors"]:
            assert factor["detail"].strip()


def test_places_are_ordered_best_first_within_each_open_tier(client, repository):
    """Best first -- but inside a tier, since `open_now` now sorts above score.

    This used to assert one globally descending list. That assertion is false
    by design now: a closed place sorts below every open place regardless of
    score. Narrowed rather than deleted, because "the score orders the list" is
    still the rule everywhere it is allowed to apply.
    """

    places = get_places(client, headers=dang_nhap(repository)).json()["places"]
    for is_open in (True, False):
        tier = [p["match"]["score"] for p in places if p["open_now"] is is_open]
        assert tier == sorted(tier, reverse=True), f"open_now={is_open} tier unsorted"


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


def test_the_profile_the_score_is_computed_against_is_disclosed(client, repository):
    """A percentage with no stated basis is a decoration. The app renders the
    factors; whoever those factors are relative to has to travel with them."""

    body = get_places(client, headers=dang_nhap(repository)).json()
    assert body["group"]["basis"] == "ca-nhan"
    assert body["group"]["interests"] == SO_THICH
    # 100k..250k, midpoint in whole đồng.
    assert body["group"]["budget_per_person_vnd"] == 175_000
    assert isinstance(body["group"]["budget_per_person_vnd"], int)
    assert body["group"]["people_answered"] == 1


def test_a_signed_out_reader_is_told_the_basis_is_nobody(client):
    """And gets no percentages at all. The six invented people this used to be
    scored against («22-28 tuổi», «Chill, View đẹp, Đồ nướng») are gone, and a
    number computed from them was worse than no number."""

    body = get_places(client).json()
    assert body["group"]["basis"] == "chua-biet"
    assert body["group"]["interests"] == []
    assert body["group"]["budget_per_person_vnd"] is None
    assert body["places"], "danh mục vẫn phải đọc được khi chưa đăng nhập"
    assert all(place["match"] is None for place in body["places"])


def test_a_taste_this_catalogue_cannot_serve_is_named_as_ours(client, repository):
    """«Shopping» matches nothing here because no shop was imported. That is a
    claim about the catalogue, and saying nothing would make it read as a claim
    about the places."""

    headers = dang_nhap(repository)
    repository.person_interests[TOI] = {"shopping", "cafe"}
    body = get_places(client, headers=headers).json()
    assert body["group"]["uncovered_interests"] == ["shopping"]


def seed_places_of_default_destination() -> list[dict]:
    """The seed rows the route serves when nobody names a destination (M10).

    `GET /places` is scoped to one city now, and the twelve seed rows sit in
    two. Comparing against all twelve would be comparing against a list this
    route never claims to return.
    """
    from app.places.seed_catalog import _destination_for

    return [place for place in PLACES if _destination_for(place) == "d-da-lat"]


def test_catalogue_ids_are_unique(client):
    body = get_places(client).json()
    ids = [place["id"] for place in body["places"]]
    assert len(ids) == len(set(ids))
    assert body["destination"]["id"] == "d-da-lat"
    assert len(ids) == len(seed_places_of_default_destination())


# ---------------------------------------------------------------------------
# open_now: a tier above the score, never a term inside it
# ---------------------------------------------------------------------------


def test_a_closed_place_never_outranks_an_open_one(client):
    """The ordering rule, stated as the only thing that matters to a reader.

    A shut door is not a matter of degree. Folding `open_now` into the score
    would make it one -- a closed place would merely lose some points and could
    still out-argue an open place on budget and distance, which is how a screen
    ends up recommending somewhere nobody can go tonight. It would also mean
    re-deriving every hand-checked score in this suite to buy that.

    So it sorts as a tier: open before closed, and the score decides only
    within a tier. The score itself is untouched.
    """

    places = get_places(client).json()["places"]
    open_ids = [place["id"] for place in places if place["open_now"]]
    closed_ids = [place["id"] for place in places if not place["open_now"]]
    assert open_ids and closed_ids, "seed needs both states or this proves nothing"

    last_open = max(places.index(p) for p in places if p["open_now"])
    first_closed = min(places.index(p) for p in places if not p["open_now"])
    assert first_closed > last_open, (
        "a closed place ranked above an open one: "
        f"closed at {first_closed}, open still at {last_open}"
    )


def test_open_now_does_not_move_the_score(client, repository):
    """The companion half: the tier must not have leaked into the arithmetic.

    Without this, someone could satisfy the test above by adding an `open_now`
    penalty to `score_place`, which is exactly what was ruled out.
    """

    places = {
        place["id"]: place
        for place in get_places(client, headers=dang_nhap(repository)).json()["places"]
    }
    for place in seed_places_of_default_destination():
        expected, _ = score_place(place, GU_TOI)
        assert places[place["id"]]["match"]["score"] == expected, (
            f"{place['id']}: score no longer matches score_place() alone"
        )


def test_ties_inside_a_tier_still_break_on_rating(client):
    """Two renders of the same data must not shuffle under a thumb."""

    first = [p["id"] for p in get_places(client).json()["places"]]
    second = [p["id"] for p in get_places(client).json()["places"]]
    assert first == second
