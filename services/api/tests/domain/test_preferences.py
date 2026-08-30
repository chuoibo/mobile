"""F31 -- the arithmetic and the refusals of the implicit profile.

Pure-function tier. It proves the shape of a profile given rows; it proves
nothing at all about who is allowed to ask for one, because a dict-backed input
cannot tell a member from a stranger. That half lives in
`tests/postgres/test_preference_profile_postgres.py` and is the half that
matters for privacy.
"""

from __future__ import annotations

import pytest

from app.domain.preferences import (
    MAX_TASTES_PER_SECTION,
    PreferenceError,
    build_preference_profile,
)


def _visit(category: str, *kinds: str) -> dict:
    return {"category": category, "kinds": list(kinds)}


def _tastes(profile: dict, section: str) -> dict[str, dict]:
    for row in profile["sections"]:
        if row["section"] == section:
            return {taste["label"]: taste for taste in row["tastes"]}
    return {}


class TestScore:
    def test_top_taste_of_a_section_scores_one(self):
        profile = build_preference_profile(
            [_visit("quan-an-local", "BBQ"), _visit("quan-an-local", "BBQ")], []
        )
        assert _tastes(profile, "food")["BBQ"]["score"] == 1.0

    def test_score_is_the_share_of_the_busiest_taste_in_the_section(self):
        visits = [_visit("quan-an-local", "BBQ")] * 4 + [
            _visit("quan-an-local", "Lẩu")
        ] * 3
        food = _tastes(build_preference_profile(visits, []), "food")
        assert food["BBQ"]["score"] == 1.0
        assert food["Lẩu"]["score"] == 0.75

    def test_sections_are_scored_independently(self):
        """A quiet section is not flattened by a loud one.

        Four dinners beside forty coffees is still a real food preference. A
        single global maximum would round the whole food section to 0.1 and the
        screen would report that this group barely eats.
        """

        visits = [_visit("cafe", "Cà phê")] * 40 + [_visit("quan-an-local", "BBQ")] * 4
        profile = build_preference_profile(visits, [])
        assert _tastes(profile, "food")["BBQ"]["score"] == 1.0
        assert _tastes(profile, "activity")["Cà phê"]["score"] == 1.0

    def test_count_travels_beside_the_score_so_the_ratio_can_be_checked(self):
        visits = [_visit("quan-an-local", "BBQ")] * 3 + [_visit("quan-an-local", "Lẩu")]
        food = _tastes(build_preference_profile(visits, []), "food")
        assert food["BBQ"]["checkin_count"] == 3
        assert food["Lẩu"]["checkin_count"] == 1
        # The reader can divide and get the printed score back.
        assert food["Lẩu"]["score"] == round(1 / 3, 2)

    def test_rounding_is_half_up_not_bankers(self):
        """`round()` would answer 0.12 here; the profile answers 0.13.

        Not an important number by itself. It is tested because the moment two
        clients round differently they print two different profiles for one
        group, and banker's rounding is the surprise that starts that.
        """

        visits = [_visit("quan-an-local", "BBQ")] * 200 + [
            _visit("quan-an-local", "Lẩu")
        ] * 25
        assert _tastes(build_preference_profile(visits, []), "food")["Lẩu"][
            "score"
        ] == 0.13


class TestWhatIsNotCounted:
    def test_unknown_category_is_skipped_never_defaulted(self):
        """A hole in the mapping must not become a bar under a heading.

        Filing an unrecognised category under a default section would invent a
        taste, and an invented taste is wrong in a direction nobody audits --
        unlike a missing one, which somebody notices is missing.
        """

        profile = build_preference_profile(
            [_visit("khong-co-trong-bang", "Gì Đó"), _visit("quan-an-local", "BBQ")], []
        )
        assert profile["checkin_count"] == 1
        assert [row["section"] for row in profile["sections"]] == ["food"]
        assert "Gì Đó" not in _tastes(profile, "food")

    def test_a_visit_with_no_kinds_contributes_nothing(self):
        profile = build_preference_profile([{"category": "cafe", "kinds": []}], [])
        assert profile["checkin_count"] == 0
        assert profile["sections"] == []

    def test_a_group_with_no_checkins_has_no_sections(self):
        profile = build_preference_profile([], [{"split_total_vnd": 0, "headcount": 2}])
        assert profile["sections"] == []
        assert profile["checkin_count"] == 0


class TestDeterminism:
    def test_same_rows_render_the_same_way_twice(self):
        visits = [
            _visit("cafe", "Chill"),
            _visit("vui-choi", "Outdoor"),
            _visit("quan-an-local", "BBQ", "Local"),
        ]
        assert build_preference_profile(visits, []) == build_preference_profile(
            visits, []
        )

    def test_ties_break_on_label_not_on_insertion_order(self):
        forward = build_preference_profile(
            [_visit("quan-an-local", "Zeta"), _visit("quan-an-local", "Alpha")], []
        )
        backward = build_preference_profile(
            [_visit("quan-an-local", "Alpha"), _visit("quan-an-local", "Zeta")], []
        )
        labels = [taste["label"] for taste in forward["sections"][0]["tastes"]]
        assert labels == ["Alpha", "Zeta"]
        assert forward == backward


class TestTruncationIsVisible:
    def test_taste_count_reports_the_full_number_when_the_list_is_capped(self):
        """A capped list with no count reads as a complete one."""

        visits = [
            _visit("quan-an-local", f"Mon{index:02d}")
            for index in range(MAX_TASTES_PER_SECTION + 4)
        ]
        section = build_preference_profile(visits, [])["sections"][0]
        assert len(section["tastes"]) == MAX_TASTES_PER_SECTION
        assert section["taste_count"] == MAX_TASTES_PER_SECTION + 4


class TestMoney:
    def test_average_is_floor_division_over_person_trips(self):
        profile = build_preference_profile(
            [],
            [
                {"split_total_vnd": 1_000_000, "headcount": 3},
                {"split_total_vnd": 500_000, "headcount": 4},
            ],
        )
        assert profile["split_total_vnd"] == 1_500_000
        assert profile["avg_per_person_vnd"] == 1_500_000 // 7
        assert isinstance(profile["avg_per_person_vnd"], int)

    def test_no_trips_means_no_average_rather_than_zero(self):
        """Zero is a claim about spending; null is the absence of one."""

        assert build_preference_profile([], [])["avg_per_person_vnd"] is None

    @pytest.mark.parametrize("bad", [True, False, "200000", 200_000.0, None, -1])
    def test_a_money_value_that_is_not_a_whole_number_of_dong_is_refused(self, bad):
        with pytest.raises(PreferenceError):
            build_preference_profile([], [{"split_total_vnd": bad, "headcount": 2}])

    @pytest.mark.parametrize("bad", [True, "3", 3.0, None])
    def test_a_headcount_that_is_not_an_integer_is_refused(self, bad):
        """`isinstance(True, int)` is true, so a bool sails through unguarded."""

        with pytest.raises(PreferenceError):
            build_preference_profile([], [{"split_total_vnd": 1000, "headcount": bad}])


class TestMalformed:
    def test_a_visit_that_is_not_a_mapping_is_refused(self):
        with pytest.raises(PreferenceError):
            build_preference_profile(["quan-an-local"], [])

    def test_a_trip_that_is_not_a_mapping_is_refused(self):
        with pytest.raises(PreferenceError):
            build_preference_profile([], ["a trip"])
