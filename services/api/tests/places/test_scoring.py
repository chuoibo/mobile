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

from app.places.catalog import PLACES
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
from app.places.taste import UNKNOWN

from .nhom_mau import NHOM_MAU, TOI_MAU

BY_ID = {place["id"]: place for place in PLACES}


# id, expected score, the arithmetic it came from.
#
# Recomputed for M11 against `NHOM_MAU`: five tastes (Ăn uống, Cafe, Nightlife,
# Món local, Outdoor), 250k a head, six people. Budget, distance and size are
# the same arithmetic as before -- only the taste term changed, because a taste
# is now a vocabulary word read off a row's category, traits or cuisine words
# rather than a free string compared against `traits`.
GOLDEN = [
    # 40 (225k under 250k budget) + 21 (3/5: quán ăn, «Local», «Ngoài trời»)
    # + 11.4 (15 x (1 - 1.2/5)) + 10 (6 fits 4-10) = 82.4
    ("p-tiem-nuong-xom-lao", 82),
    # 40 (250k = budget exactly) + 7 (1/5: đi chơi đêm) + 9.6 (15 x (1 - 1.8/5))
    # + 10 (6 fits 4-12) = 66.6
    ("p-chill-dem-da-lat", 67),
    # 18.4 (385k midpoint is 54% over budget) + 7 (1/5) + 0 (5.2km past the
    # 5km limit) + 10 (6 fits 4-16) = 35.4
    ("p-the-hill-rooftop", 35),
    # 40 (75k, well under) + 14 (2/5: cafe, «Local») + 0 (6.1km past the limit)
    # + 0 (a group of 6 does not fit a 2-5 room) = 54
    ("p-ca-phe-vot-hem", 54),
    # 40 (220k under) + 0 (a bowling alley answers none of the five)
    # + 0 (7.4km past the limit) + 10 (fits 4-12) = 50
    ("p-bowling-sky", 50),
]


@pytest.mark.parametrize(("place_id", "expected"), GOLDEN)
def test_score_matches_the_hand_computed_value(place_id, expected):
    score, _ = score_place(BY_ID[place_id], NHOM_MAU)
    assert score == expected


def test_nobody_gets_no_number_at_all():
    """The M11 rule, and the reason the badge disappears when signed out.

    Every term needs the other side of a comparison. With no profile there is
    no budget to be under, no taste to answer and no headcount to seat, so the
    score is `None` -- not 0, which would read as «these places are a bad fit»
    when the missing half is us knowing who is asking.
    """

    for place in PLACES:
        score, factors = score_place(place, UNKNOWN)
        assert score is None, place["id"]
        assert len(factors) == 4


def test_one_person_is_scored_on_what_they_did_say():
    """A profile with no headcount still scores: the size term drops out and
    budget and taste carry the badge. 40 (75k under 175k) + 17.5 (1/2: cafe)
    + 0 (6.1km) = 57.5 out of the 90 points those three terms carry, rescaled
    to 100 -> 64."""

    score, _ = score_place(BY_ID["p-ca-phe-vot-hem"], TOI_MAU)
    assert score == 64


def test_weights_add_up_to_one_hundred():
    """A "percentage" whose components cannot reach 100 is not a percentage."""

    assert WEIGHT_BUDGET + WEIGHT_TASTE + WEIGHT_DISTANCE + WEIGHT_GROUP_SIZE == 100


def test_every_seed_place_scores_inside_the_range():
    for place in PLACES:
        score, _ = score_place(place, NHOM_MAU)
        assert score is not None and 0 <= score <= 100, place["id"]


def test_budget_component_is_exact_rational_not_float():
    """Money law 1 reaches the comparison, not just the ledger.

    `Fraction`, so a band midpoint one đồng over budget scores strictly below
    one exactly on it -- a float would let those collapse into each other.
    """

    place = dict(BY_ID["p-chill-dem-da-lat"])
    assert isinstance(budget_fit(place, NHOM_MAU), Fraction)
    assert budget_fit(place, NHOM_MAU) == 1  # 250k midpoint, 250k budget

    one_dong_over = {**place, "price_min_vnd": 250_001, "price_max_vnd": 250_001}
    assert budget_fit(one_dong_over, NHOM_MAU) < 1


def test_budget_hits_zero_at_double_and_does_not_go_negative():
    place = {
        **BY_ID["p-chill-dem-da-lat"],
        "price_min_vnd": 500_000,
        "price_max_vnd": 500_000,
    }
    assert budget_fit(place, NHOM_MAU) == 0
    ruinous = {**place, "price_min_vnd": 5_000_000, "price_max_vnd": 5_000_000}
    assert budget_fit(ruinous, NHOM_MAU) == 0


def test_distance_is_zero_at_the_limit_not_negative():
    at_limit = {**BY_ID["p-tiem-nuong-xom-lao"], "distance_km": 5.0}
    beyond = {**BY_ID["p-tiem-nuong-xom-lao"], "distance_km": 40.0}
    assert distance_fit(at_limit) == 0
    assert distance_fit(beyond) == 0


def test_distance_reads_the_seed_as_decimal_not_as_binary_float():
    """`Fraction(1.2)` is not 6/5. If it were used, this equality would fail."""

    place = {**BY_ID["p-tiem-nuong-xom-lao"], "distance_km": 1.2}
    assert distance_fit(place) == Fraction(1) - Fraction(12, 10) / Fraction(5)


def test_group_size_is_all_or_nothing_and_absence_is_unknown_not_zero():
    """M9 changed one half of this rule and left the other half alone.

    A capacity that is stated and does not fit still scores 0. A capacity that
    is not stated is now `None` -- the term drops out of the total instead of
    being counted as a failure -- because no imported row carries one, and
    «the map does not say» must not rank below «too small».
    """

    place = BY_ID["p-tiem-nuong-xom-lao"]
    assert group_size_fit(place, NHOM_MAU) == 1
    assert group_size_fit({**place, "group_fit": None}, NHOM_MAU) is None
    too_small = {
        **place,
        "group_fit": {"min_people": 2, "max_people": 4, "relation": "x"},
    }
    assert group_size_fit(too_small, NHOM_MAU) == 0


def test_taste_counts_the_tastes_claimed_not_the_places_words():
    """A place answering one of the five must not outscore a place answering
    three of them, however many words it lists of its own."""

    place = BY_ID["p-tiem-nuong-xom-lao"]
    share, hits = taste_fit(place, NHOM_MAU)
    assert share == Fraction(3, 5)
    assert hits == ["an-uong", "mon-local", "outdoor"]

    narrow = {**place, "traits": [], "kinds": []}
    partial, hits = taste_fit(narrow, NHOM_MAU)
    assert partial == Fraction(1, 5) and hits == ["an-uong"]


def test_no_taste_claimed_is_unknown_rather_than_zero():
    """Zero would rank every place equally badly and still print a badge --
    a statement about the places, when the missing half is the person."""

    silent = UNKNOWN
    share, hits = taste_fit(BY_ID["p-tiem-nuong-xom-lao"], silent)
    assert share is None and hits == []


def test_factors_name_the_four_components_in_a_fixed_order():
    """The screen renders these as rows. Reordering them between two requests
    would shuffle the sheet under someone reading it."""

    for place in PLACES:
        _, factors = score_place(place, NHOM_MAU)
        assert [factor["label"] for factor in factors] == [
            "Budget",
            "Sở thích",
            "Nhóm",
            "Khoảng cách",
        ]
        for factor in factors:
            assert factor["detail"].strip()


def test_a_place_that_answers_no_taste_says_so_rather_than_showing_blank():
    _, factors = score_place(BY_ID["p-bowling-sky"], NHOM_MAU)
    taste_line = next(f for f in factors if f["label"] == "Sở thích")
    assert taste_line["detail"] == "không trùng sở thích nào đã chọn"


def test_the_factor_lines_name_which_half_is_missing():
    """The four lines are what the screen shows instead of a badge when there
    is no badge, so each has to say whose half of the comparison is absent."""

    _, factors = score_place(BY_ID["p-tiem-nuong-xom-lao"], UNKNOWN)
    detail = {factor["label"]: factor["detail"] for factor in factors}
    assert "chưa ai nói mức chi" in detail["Budget"]
    assert detail["Sở thích"] == "chưa chọn sở thích nào, nên chưa so được"
    assert detail["Nhóm"].startswith("chưa biết đi mấy người")
