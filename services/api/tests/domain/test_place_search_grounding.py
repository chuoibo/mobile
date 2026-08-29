"""The grounding boundary for F12 natural-language place search (rd-be-10).

`GET /places` is safe by construction: its prompt is a pure function of the seed
catalogue, and `tests/api/test_places_prompt_boundary.py` holds that invariant
byte for byte. F12 cannot have that property and still be F12 -- the whole
feature is that a sentence a person typed reaches the model.

So the defence moves from the input to the output. The model is allowed to read
the query; it is not allowed to author the answer. It may copy an `id` out of
the catalogue the server handed it, and nothing else it says becomes a fact on
a screen. That is the same rule `app/domain/companion.py::ground_card` already
holds for the chat companion, and this module is deliberately its twin rather
than a second, subtly different idea about the same danger.

The rule that costs something, and is therefore the one worth testing: an
identifier that is not in the catalogue **sinks the entire answer**. It does not
get quietly filtered out of a list of otherwise-good places. A model that
invented one row was not reading the catalogue when it chose the other four, and
a filtered list hides exactly that -- it serves four plausible places under an
`ai` label with no sign that the fifth was fiction.
"""

from __future__ import annotations

import pytest

from app.domain.place_search import (
    MAX_RESULTS,
    PlaceSearchError,
    ground_search,
)

CATEGORIES = [
    {"id": "quan-an-local", "label": "Quán ăn local"},
    {"id": "cafe", "label": "Cafe"},
]

PLACES = [
    {
        "id": "p-nuong",
        "name": "Tiệm Nướng Xóm Lào",
        "category": "quan-an-local",
        "price_min_vnd": 200_000,
        "price_max_vnd": 250_000,
        "traits": ["Ngoài trời", "Đồ nướng"],
    },
    {
        "id": "p-cafe",
        "name": "Lưng Chừng Cafe",
        "category": "cafe",
        "price_min_vnd": 60_000,
        "price_max_vnd": 90_000,
        "traits": ["Chill", "View đẹp"],
    },
    {
        "id": "p-oc",
        "name": "Quán Ốc Đi Bể",
        "category": "quan-an-local",
        "price_min_vnd": 120_000,
        "price_max_vnd": 180_000,
        "traits": ["Nhóm đông"],
    },
]


def raw(**overrides):
    """A well-formed model answer, so each test changes exactly one thing."""

    body = {
        "understood": {
            "budget_per_person_vnd": 300_000,
            "group_size": 6,
            "max_distance_km": 5,
            "categories": ["quan-an-local"],
            "traits": ["Ngoài trời"],
        },
        "results": [{"id": "p-nuong", "reason": "Đồ nướng, ngồi ngoài trời."}],
    }
    body.update(overrides)
    return body


def ground(**overrides):
    return ground_search(raw(**overrides), PLACES, CATEGORIES)


# ---------------------------------------------------------------------------
# The happy path, stated so the refusals below are not vacuous
# ---------------------------------------------------------------------------


def test_a_well_formed_answer_yields_catalogue_rows_in_the_model_order():
    """Relevance order is the model's answer, so it is preserved, not re-sorted."""

    out = ground(
        results=[
            {"id": "p-oc", "reason": "Đông người vẫn ngồi được."},
            {"id": "p-nuong", "reason": "Đồ nướng ngoài trời."},
        ]
    )

    assert [item["place"]["id"] for item in out["results"]] == ["p-oc", "p-nuong"]
    assert out["results"][0]["reason"] == "Đông người vẫn ngồi được."


def test_the_served_place_is_the_catalogue_row_field_for_field():
    """Facts come from the server. Anything the model says about a place is dropped."""

    out = ground(
        results=[
            {
                "id": "p-nuong",
                "name": "Quán Của Mô Hình",
                "price_min_vnd": 1,
                "rating": 5.0,
                "reason": "Hợp nhóm.",
            }
        ]
    )

    served = out["results"][0]["place"]
    assert served == PLACES[0], (
        "the served row is not the catalogue row: a model-authored field "
        "survived grounding and would reach a screen as a fact"
    )


def test_an_empty_result_list_is_an_answer_not_an_error():
    """"Không có chỗ nào hợp" is a legitimate reply to a search, unlike a chat card."""

    out = ground(results=[])
    assert out["results"] == []
    assert out["understood"]["group_size"] == 6


# ---------------------------------------------------------------------------
# Fail closed: one bad identifier sinks the whole answer
# ---------------------------------------------------------------------------


def test_an_identifier_outside_the_catalogue_rejects_the_whole_answer():
    with pytest.raises(PlaceSearchError) as caught:
        ground(
            results=[
                {"id": "p-nuong", "reason": "Hợp."},
                {"id": "p-khong-co-that", "reason": "Cũng hợp."},
            ]
        )
    assert caught.value.code == "place_search_place_not_in_catalogue"


def test_the_invented_identifier_is_caught_before_the_result_limit_truncates_it():
    """The limit must not become an accidental amnesty for the fabricated row.

    Real ids first, the invented one past position `MAX_RESULTS`: a check
    written after truncation would never see it and would serve a full page of
    good places for an answer that was partly fiction.
    """

    results = [{"id": PLACES[index % 3]["id"]} for index in range(MAX_RESULTS + 2)]
    results[-1] = {"id": "p-nguy-trang"}

    with pytest.raises(PlaceSearchError) as caught:
        ground(results=results)
    assert caught.value.code == "place_search_place_not_in_catalogue"


def test_a_category_outside_the_catalogue_rejects_the_whole_answer():
    with pytest.raises(PlaceSearchError) as caught:
        ground(
            understood={
                "budget_per_person_vnd": None,
                "group_size": None,
                "max_distance_km": None,
                "categories": ["quan-bar-khong-ton-tai"],
                "traits": [],
            }
        )
    assert caught.value.code == "place_search_category_not_in_catalogue"


def test_a_trait_outside_the_catalogue_rejects_the_whole_answer():
    """`understood` is echoed to the screen, so it is a fabrication surface too."""

    with pytest.raises(PlaceSearchError) as caught:
        ground(
            understood={
                "budget_per_person_vnd": None,
                "group_size": None,
                "max_distance_km": None,
                "categories": [],
                "traits": ["Có sao Michelin"],
            }
        )
    assert caught.value.code == "place_search_trait_not_in_catalogue"


# ---------------------------------------------------------------------------
# Money law 1 does not stop at the ledger
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("budget", [300_000.0, "300000", 300_000.5, True, -1])
def test_a_budget_that_is_not_a_non_negative_integer_dong_rejects_the_answer(budget):
    """Integer đồng, including at a value that only ever gets displayed.

    A float budget echoed back to a screen is a float that reached a money value
    inside this service. `True` is in the list because `isinstance(True, int)`
    is true in Python and a bool is not a sum of money.
    """

    with pytest.raises(PlaceSearchError) as caught:
        ground(
            understood={
                "budget_per_person_vnd": budget,
                "group_size": None,
                "max_distance_km": None,
                "categories": [],
                "traits": [],
            }
        )
    assert caught.value.code == "place_search_budget_not_integer"


def test_a_null_budget_is_allowed_because_a_query_need_not_mention_money():
    out = ground(
        understood={
            "budget_per_person_vnd": None,
            "group_size": None,
            "max_distance_km": None,
            "categories": [],
            "traits": [],
        }
    )
    assert out["understood"]["budget_per_person_vnd"] is None


# ---------------------------------------------------------------------------
# Shape refusals
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "not a dict",
        {"results": []},
        {"understood": "not a dict", "results": []},
        {"understood": {}, "results": "not a list"},
    ],
)
def test_a_malformed_answer_is_refused_rather_than_repaired(bad):
    with pytest.raises(PlaceSearchError) as caught:
        ground_search(bad, PLACES, CATEGORIES)
    assert caught.value.code == "place_search_malformed"


def test_a_result_entry_without_a_string_identifier_is_malformed():
    with pytest.raises(PlaceSearchError) as caught:
        ground(results=[{"reason": "Quên mất id."}])
    assert caught.value.code == "place_search_malformed"


def test_repeated_identifiers_collapse_to_the_first_mention():
    out = ground(
        results=[
            {"id": "p-cafe", "reason": "Chill."},
            {"id": "p-cafe", "reason": "Vẫn chill."},
            {"id": "p-oc", "reason": "Đông vui."},
        ]
    )
    assert [item["place"]["id"] for item in out["results"]] == ["p-cafe", "p-oc"]
    assert out["results"][0]["reason"] == "Chill."


def test_more_results_than_the_limit_are_truncated_to_the_limit():
    results = [{"id": PLACES[index % 3]["id"]} for index in range(MAX_RESULTS + 5)]
    out = ground(results=results)
    assert len(out["results"]) <= MAX_RESULTS


def test_a_missing_or_blank_reason_is_absent_rather_than_invented():
    out = ground(results=[{"id": "p-nuong"}, {"id": "p-cafe", "reason": "   "}])
    assert [item["reason"] for item in out["results"]] == [None, None]
