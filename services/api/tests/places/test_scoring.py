"""Hand-computed score vectors.

The point of rd-be-05 is that the badge number is reproducible by a person.
These are that claim made executable: each expected value below was worked out
on paper from the weights and the seed row, not read off a run. A test that
records whatever the code happened to print proves only that the code is
deterministic, which was never in doubt.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from app.places.catalog import GROUP, PLACES
from app.places.scoring import (
    WEIGHT_BUDGET,
    WEIGHT_DISTANCE,
    WEIGHT_GROUP_SIZE,
    WEIGHT_TASTE,
    budget_fit,
    distance_fit,
    group_size_fit,
    score_place,
    taste_fit,
)

BY_ID = {place["id"]: place for place in PLACES}


# id, expected score, the arithmetic it came from
GOLDEN = [
    # 40 (225k under 250k budget) + 35 (5/5 likes) + 11.4 (15 x (1 - 1.2/5))
    # + 10 (6 fits 4-10) = 96.4
    ("p-tiem-nuong-xom-lao", 96),
    # 40 (250k = budget exactly) + 7 (1/5 likes) + 9.6 (15 x (1 - 1.8/5))
    # + 10 (6 fits 4-12) = 66.6
    ("p-chill-dem-da-lat", 67),
    # 18.4 (385k midpoint is 54% over budget) + 7 (1/5) + 0 (5.2km past the
    # 5km limit) + 10 (6 fits 4-16) = 35.4
    ("p-the-hill-rooftop", 35),
    # 40 (75k, well under) + 0 (no shared like) + 0 (6.1km past the limit)
    # + 0 (a group of 6 does not fit a 2-5 room) = 40
    ("p-ca-phe-vot-hem", 40),
    # 40 (220k under) + 7 (1/5) + 0 (7.4km past the limit) + 10 (fits 4-12) = 57
    ("p-bowling-sky", 57),
]


@pytest.mark.parametrize(("place_id", "expected"), GOLDEN)
def test_score_matches_the_hand_computed_value(place_id, expected):
    score, _ = score_place(BY_ID[place_id], GROUP)
    assert score == expected


def test_weights_add_up_to_one_hundred():
    """A "percentage" whose components cannot reach 100 is not a percentage."""

    assert (
        WEIGHT_BUDGET + WEIGHT_TASTE + WEIGHT_DISTANCE + WEIGHT_GROUP_SIZE == 100
    )


def test_every_seed_place_scores_inside_the_range():
    for place in PLACES:
        score, _ = score_place(place, GROUP)
        assert 0 <= score <= 100, place["id"]


def test_budget_component_is_exact_rational_not_float():
    """Money law 1 reaches the comparison, not just the ledger.

    `Fraction`, so a band midpoint one đồng over budget scores strictly below
    one exactly on it -- a float would let those collapse into each other.
    """

    place = dict(BY_ID["p-chill-dem-da-lat"])
    assert isinstance(budget_fit(place, GROUP), Fraction)
    assert budget_fit(place, GROUP) == 1  # 250k midpoint, 250k budget

    one_dong_over = {**place, "price_min_vnd": 250_001, "price_max_vnd": 250_001}
    assert budget_fit(one_dong_over, GROUP) < 1


def test_budget_hits_zero_at_double_and_does_not_go_negative():
    place = {**BY_ID["p-chill-dem-da-lat"], "price_min_vnd": 500_000, "price_max_vnd": 500_000}
    assert budget_fit(place, GROUP) == 0
    ruinous = {**place, "price_min_vnd": 5_000_000, "price_max_vnd": 5_000_000}
    assert budget_fit(ruinous, GROUP) == 0


def test_distance_is_zero_at_the_limit_not_negative():
    at_limit = {**BY_ID["p-tiem-nuong-xom-lao"], "distance_km": 5.0}
    beyond = {**BY_ID["p-tiem-nuong-xom-lao"], "distance_km": 40.0}
    assert distance_fit(at_limit, GROUP) == 0
    assert distance_fit(beyond, GROUP) == 0


def test_distance_reads_the_seed_as_decimal_not_as_binary_float():
    """`Fraction(1.2)` is not 6/5. If it were used, this equality would fail."""

    place = {**BY_ID["p-tiem-nuong-xom-lao"], "distance_km": 1.2}
    assert distance_fit(place, GROUP) == Fraction(1) - Fraction(12, 10) / Fraction(5)


def test_group_size_is_all_or_nothing_and_absence_scores_zero():
    place = BY_ID["p-tiem-nuong-xom-lao"]
    assert group_size_fit(place, GROUP) == 1
    assert group_size_fit({**place, "group_fit": None}, GROUP) == 0
    too_small = {**place, "group_fit": {"min_people": 2, "max_people": 4, "relation": "x"}}
    assert group_size_fit(too_small, GROUP) == 0


def test_taste_counts_the_groups_likes_not_the_places_traits():
    """A place listing one trait the group wants must not outscore a place
    listing that trait plus four others the group also wants."""

    place = BY_ID["p-tiem-nuong-xom-lao"]
    full, hits = taste_fit(place, GROUP)
    assert full == 1 and len(hits) == 5

    narrow = {**place, "traits": ["Chill"]}
    partial, hits = taste_fit(narrow, GROUP)
    assert partial == Fraction(1, 5) and hits == ["Chill"]


def test_factors_name_the_four_components_in_a_fixed_order():
    """The screen renders these as rows. Reordering them between two requests
    would shuffle the sheet under someone reading it."""

    for place in PLACES:
        _, factors = score_place(place, GROUP)
        assert [factor["label"] for factor in factors] == [
            "Budget",
            "Sở thích",
            "Nhóm",
            "Khoảng cách",
        ]
        for factor in factors:
            assert factor["detail"].strip()


def test_a_place_with_no_matching_traits_says_so_rather_than_showing_blank():
    _, factors = score_place(BY_ID["p-ca-phe-vot-hem"], GROUP)
    taste_line = next(f for f in factors if f["label"] == "Sở thích")
    assert taste_line["detail"] == "không trùng sở thích nào đã ghi"
