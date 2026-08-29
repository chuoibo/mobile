"""The grounding boundary for F32 proactive outing suggestions (rd-be-14).

This is the third model-facing surface in the service, and it is the first one
nobody asked for: the companion answers a conversation and search answers a
sentence, but a proactive card arrives on a screen with no question behind it.
That makes the fabrication risk worse rather than better. There is no person
mid-thought to notice that the place being suggested does not exist, because
there is no thought -- the card is simply there when the tab opens.

So the rules the first two surfaces paid for are repeated here verbatim rather
than approximated:

1. **The model cannot author facts.** It copies `place_id` out of a catalogue
   the server handed it, and the server attaches every name, price and address
   afterwards. One identifier from outside the catalogue sinks the whole card;
   it is not filtered out of an otherwise-good itinerary. A model that invented
   the fourth stop was not reading the catalogue when it picked the first three.
2. **The check runs before deduplication and before the display limit.**
   `MAX_STOPS` is a display decision. Letting it run first would turn it into an
   amnesty: a fabricated stop in seventh place would be truncated away and the
   remaining six served as if the answer had been clean. This is the bug #139
   found in a sibling module, and it is cheap to have again.
3. **`reason` and `verdict` travel as one claim.** Half a pair renders as a
   model endorsement nobody gave, or a conclusion with nothing behind it. Tied
   at the single point every stop passes through, because a rule that has to be
   remembered at each call site is a rule that gets forgotten at the next one.
4. **The payload is rebuilt from a whitelist, never copied.** #140 showed the
   companion whitelisting `places` and not `itinerary` for weeks, so the case
   that matters is the one for *this* kind, written the day the kind exists.

Money is not exempt because it is only being displayed: the history digest is
integer đồng end to end, and an average is floor division, never a float.
"""

from __future__ import annotations

import pytest

from app.domain.place_search import VERDICTS as SEARCH_VERDICTS
from app.domain.suggestion import (
    MAX_STOPS,
    SUGGESTION_KIND,
    VERDICTS,
    SuggestionError,
    ground_suggestion,
    summarise_history,
)

PLACES = [
    {
        "id": "p-nuong",
        "name": "Tiệm Nướng Xóm Lào",
        "category": "quan-an-local",
        "address": "27/1 Yersin, TP. Đà Lạt",
        "price_min_vnd": 200_000,
        "price_max_vnd": 250_000,
    },
    {
        "id": "p-cafe",
        "name": "Lưng Chừng Cafe",
        "category": "cafe",
        "address": "12 Trần Phú, TP. Đà Lạt",
        "price_min_vnd": 60_000,
        "price_max_vnd": 90_000,
    },
    {
        "id": "p-oc",
        "name": "Quán Ốc Đi Bể",
        "category": "quan-an-local",
        "address": "5 Nguyễn Chí Thanh, TP. Đà Lạt",
        "price_min_vnd": 120_000,
        "price_max_vnd": 180_000,
    },
    {
        "id": "p-ho",
        "name": "Hồ Tuyền Lâm",
        "category": "ngoai-troi",
        "address": "Đường Hoa Hồng, TP. Đà Lạt",
        "price_min_vnd": 0,
        "price_max_vnd": 0,
    },
    {
        "id": "p-cho-dem",
        "name": "Chợ Đêm Đà Lạt",
        "category": "ngoai-troi",
        "address": "Nguyễn Thị Minh Khai, TP. Đà Lạt",
        "price_min_vnd": 50_000,
        "price_max_vnd": 120_000,
    },
    {
        "id": "p-bun",
        "name": "Bún Bò Ấp Ánh Sáng",
        "category": "quan-an-local",
        "address": "2 Ánh Sáng, TP. Đà Lạt",
        "price_min_vnd": 40_000,
        "price_max_vnd": 60_000,
    },
]


def _stop(place_id: str, **overrides) -> dict:
    stop = {
        "place_id": place_id,
        "time_text": "18:00",
        "note": "Đi sớm cho kịp chỗ ngồi ngoài trời",
        "reason": "Nhóm hay ăn quán local và mức giá vừa ngân sách",
        "verdict": "hop",
    }
    stop.update(overrides)
    return stop


def _card(*stops: dict, **overrides) -> dict:
    payload = {
        "title": "Tối thứ Bảy: nướng rồi cà phê",
        "when_text": "Tối thứ Bảy tuần này",
        "stops": list(stops),
    }
    payload.update(overrides)
    return {"kind": SUGGESTION_KIND, "payload": payload}


# ---------------------------------------------------------------------------
# The happy path, and what a served stop is actually made of
# ---------------------------------------------------------------------------


def test_a_well_formed_card_keeps_the_model_order():
    grounded = ground_suggestion(_card(_stop("p-cafe"), _stop("p-nuong")), PLACES)

    assert grounded["kind"] == SUGGESTION_KIND
    assert [stop["place"]["id"] for stop in grounded["payload"]["stops"]] == [
        "p-cafe",
        "p-nuong",
    ]


def test_the_served_place_is_the_catalogue_row_field_for_field():
    """Every displayed fact comes from the server, not from the model."""

    grounded = ground_suggestion(_card(_stop("p-nuong")), PLACES)
    place = grounded["payload"]["stops"][0]["place"]

    assert place == PLACES[0]
    # A copy, so a caller mutating the response cannot edit the catalogue.
    assert place is not PLACES[0]


def test_a_card_with_no_stops_is_refused_rather_than_served_empty():
    """Unlike a search, a proactive card has to say something to exist."""

    with pytest.raises(SuggestionError) as raised:
        ground_suggestion(_card(), PLACES)
    assert raised.value.code == "suggestion_card_empty"


# ---------------------------------------------------------------------------
# Acceptance 1: refuse, never filter
# ---------------------------------------------------------------------------


def test_an_identifier_outside_the_catalogue_rejects_the_whole_card():
    """Filtering the bad stop out instead of raising must fail this test.

    Two stops, one real and one invented, and the invented one sits inside
    every limit this module applies -- so a module that merely truncated late
    would still be caught here. What this case is about is the choice between
    refusing and filtering.
    """

    with pytest.raises(SuggestionError) as raised:
        ground_suggestion(
            _card(_stop("p-nuong"), _stop("p-quan-khong-ton-tai")), PLACES
        )
    assert raised.value.code == "suggestion_place_not_in_catalogue"


# ---------------------------------------------------------------------------
# Acceptance 2: check before the cut, not after
# ---------------------------------------------------------------------------


def test_the_invented_identifier_is_caught_before_the_display_limit_truncates_it():
    """The fabricated stop is past `MAX_STOPS`, where a late check cannot see it.

    A module that validated `stops[:MAX_STOPS]` would serve `MAX_STOPS` real
    places and never mention that the model also invented one. That is worse
    than a refusal, because the card looks complete.
    """

    real = [_stop(place["id"]) for place in PLACES[:MAX_STOPS]]
    assert len(real) == MAX_STOPS

    with pytest.raises(SuggestionError) as raised:
        ground_suggestion(_card(*real, _stop("p-bia-ra")), PLACES)
    assert raised.value.code == "suggestion_place_not_in_catalogue"


def test_the_limit_counts_distinct_places_not_repeated_mentions():
    """Deduplication runs before the cut, so a repeat cannot cost a real stop.

    Written this way on purpose. Deduplication cannot hide a fabricated
    identifier -- collapsing duplicates never removes a *unique* id -- so a
    case claiming it does would be a test that cannot fail for the reason it
    states. What the order genuinely decides is this: truncating first would
    spend limit slots on repeats and serve a short card built from a long
    answer.
    """

    stops = [
        _stop("p-nuong"),
        _stop("p-nuong"),
        *[_stop(place["id"]) for place in PLACES[1:]],
    ]

    grounded = ground_suggestion(_card(*stops), PLACES)
    served = [stop["place"]["id"] for stop in grounded["payload"]["stops"]]

    assert len(served) == MAX_STOPS
    assert len(set(served)) == MAX_STOPS


def test_repeated_identifiers_collapse_to_the_first_mention():
    grounded = ground_suggestion(
        _card(_stop("p-nuong"), _stop("p-nuong"), _stop("p-cafe")), PLACES
    )

    assert [stop["place"]["id"] for stop in grounded["payload"]["stops"]] == [
        "p-nuong",
        "p-cafe",
    ]


def test_more_stops_than_the_limit_are_truncated_to_the_limit():
    stops = [_stop(place["id"]) for place in PLACES]
    assert len(stops) > MAX_STOPS

    grounded = ground_suggestion(_card(*stops), PLACES)

    assert len(grounded["payload"]["stops"]) == MAX_STOPS


# ---------------------------------------------------------------------------
# Acceptance 3: reason and verdict are one claim
# ---------------------------------------------------------------------------


def test_a_full_pair_survives_grounding():
    grounded = ground_suggestion(
        _card(_stop("p-nuong", reason="Hợp ngân sách nhóm", verdict="tam")), PLACES
    )
    stop = grounded["payload"]["stops"][0]

    assert stop["reason"] == "Hợp ngân sách nhóm"
    assert stop["verdict"] == "tam"


def test_a_sentence_with_no_verdict_behind_it_loses_the_sentence():
    """`source: "ai"` beside a null verdict is a badge nobody gave."""

    grounded = ground_suggestion(
        _card(_stop("p-nuong", reason="Nghe hợp lắm", verdict=None)), PLACES
    )
    stop = grounded["payload"]["stops"][0]

    assert stop["reason"] is None
    assert stop["verdict"] is None
    # The stop itself stays: a bad sentence about a real place is not a bad card.
    assert stop["place"]["id"] == "p-nuong"


def test_a_verdict_with_no_sentence_behind_it_is_dropped_too():
    grounded = ground_suggestion(
        _card(_stop("p-nuong", reason="   ", verdict="hop")), PLACES
    )
    stop = grounded["payload"]["stops"][0]

    assert stop["reason"] is None
    assert stop["verdict"] is None


def test_a_verdict_outside_the_closed_set_costs_the_pair_not_the_card():
    grounded = ground_suggestion(
        _card(
            _stop("p-nuong", verdict="tuyet-voi"),
            _stop("p-cafe"),
        ),
        PLACES,
    )
    first, second = grounded["payload"]["stops"]

    assert (first["reason"], first["verdict"]) == (None, None)
    assert second["verdict"] == "hop"


def test_the_verdict_vocabulary_is_the_one_the_rest_of_the_product_shows():
    """One badge, one vocabulary. Two would mean one of them is the weaker."""

    assert VERDICTS == SEARCH_VERDICTS


# ---------------------------------------------------------------------------
# Acceptance 4: the payload is a whitelist for THIS kind
# ---------------------------------------------------------------------------


def test_a_key_the_contract_never_named_cannot_reach_the_payload():
    """#140: `places` was whitelisted and `itinerary` was not, for weeks."""

    raw = _card(
        _stop(
            "p-nuong",
            name="Quán do model tự đặt tên",
            price_min_vnd=1,
            lat=11.94,
            lng=108.44,
            booking_url="https://khong-phai-cua-san-pham",
        ),
        budget_per_person_vnd=999_999,
        cta="Đặt bàn ngay",
    )

    grounded = ground_suggestion(raw, PLACES)

    assert set(grounded) == {"kind", "payload"}
    assert set(grounded["payload"]) == {"title", "when_text", "stops"}
    assert set(grounded["payload"]["stops"][0]) == {
        "time_text",
        "note",
        "reason",
        "verdict",
        "place",
    }
    # And the place is still the catalogue row, not the model's edit of it.
    assert grounded["payload"]["stops"][0]["place"] == PLACES[0]


def test_a_kind_this_module_does_not_serve_is_refused():
    with pytest.raises(SuggestionError) as raised:
        ground_suggestion({**_card(_stop("p-nuong")), "kind": "places"}, PLACES)
    assert raised.value.code == "suggestion_card_kind_unknown"


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "một chuỗi",
        {"kind": SUGGESTION_KIND},
        {"kind": SUGGESTION_KIND, "payload": []},
        {"kind": SUGGESTION_KIND, "payload": {"title": 7, "when_text": "x", "stops": []}},
        {"kind": SUGGESTION_KIND, "payload": {"title": "x", "when_text": "y", "stops": {}}},
    ],
)
def test_a_malformed_card_is_refused_rather_than_repaired(bad):
    with pytest.raises(SuggestionError):
        ground_suggestion(bad, PLACES)


def test_a_stop_without_a_string_place_id_is_malformed():
    with pytest.raises(SuggestionError) as raised:
        ground_suggestion(_card({**_stop("p-nuong"), "place_id": 42}), PLACES)
    assert raised.value.code == "suggestion_card_malformed"


# ---------------------------------------------------------------------------
# The history digest: server-owned, integer đồng, and never the model's
# ---------------------------------------------------------------------------

TRIPS = [
    {"title": "Đà Lạt tháng 7", "split_total_vnd": 1_200_000, "headcount": 4},
    {"title": "Nướng cuối tuần", "split_total_vnd": 800_000, "headcount": 5},
]
VISITS = [
    {"category": "quan-an-local"},
    {"category": "quan-an-local"},
    {"category": "cafe"},
]


def test_the_digest_counts_trips_and_totals_the_ledger_figures():
    digest = summarise_history(TRIPS, VISITS)

    assert digest["outing_count"] == 2
    assert digest["split_total_vnd"] == 2_000_000
    assert digest["recent_titles"] == ["Đà Lạt tháng 7", "Nướng cuối tuần"]


def test_the_average_per_person_is_floor_division_in_integer_dong():
    """Money law 1 at a value that only ever gets displayed.

    2.000.000 đồng over 9 person-trips is 222.222,22 -- and a product that
    lets that become a float has a float in a money value regardless of what
    the next reader does with it.
    """

    digest = summarise_history(TRIPS, VISITS)

    assert digest["avg_per_person_vnd"] == 222_222
    assert isinstance(digest["avg_per_person_vnd"], int)
    assert not isinstance(digest["avg_per_person_vnd"], bool)


def test_the_most_visited_categories_come_first():
    digest = summarise_history(TRIPS, VISITS)

    assert digest["top_categories"] == ["quan-an-local", "cafe"]


def test_a_group_with_no_history_has_nothing_to_average():
    digest = summarise_history([], [])

    assert digest["outing_count"] == 0
    assert digest["split_total_vnd"] == 0
    assert digest["avg_per_person_vnd"] is None
    assert digest["top_categories"] == []


@pytest.mark.parametrize("bad", [250_000.0, "250000", True, -1])
def test_a_trip_total_that_is_not_integer_dong_is_refused(bad):
    with pytest.raises(SuggestionError) as raised:
        summarise_history([{"title": "x", "split_total_vnd": bad, "headcount": 4}], [])
    assert raised.value.code == "suggestion_history_not_integer_dong"
