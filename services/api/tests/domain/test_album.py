"""F36 -- how an album is assembled, and what it refuses to invent.

Pure tier. Which rows reach `build_album` -- and therefore whether an album can
ever contain another group's photograph -- is a WHERE clause, and a dict-backed
input round-trips a missing predicate exactly as cleanly as a present one. That
question is answered in `tests/postgres/test_trip_album_postgres.py`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.domain.album import (
    AlbumError,
    build_album,
    period_label,
)

TRIP = {
    "title": "Đà Lạt",
    "starts_on": date(2026, 8, 1),
    "ends_on": date(2026, 8, 3),
    "headcount": 5,
    "split_total_vnd": 3_000_000,
    "expense_count": 4,
}


def _photo(name: str, *, hearts: int = 0, day: int = 1) -> dict:
    return {
        "id": name,
        "kind": "photo",
        "image_url": f"/contexts/c/photos/{name}",
        "caption": None,
        "place_id": None,
        "place_name": None,
        "created_at": datetime(2026, 8, day, 12, 0, tzinfo=UTC),
        "reaction_count": hearts,
        "comment_count": 0,
    }


def _checkin(place_id: str, name: str = "Tiệm Nướng") -> dict:
    return {
        "id": f"ci-{place_id}",
        "kind": "checkin",
        "image_url": None,
        "caption": None,
        "place_id": place_id,
        "place_name": name,
        "created_at": datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
        "reaction_count": 0,
        "comment_count": 0,
    }


class TestPeriodLabel:
    def test_a_trip_inside_one_year_is_labelled_with_that_year(self):
        assert period_label(date(2026, 8, 1), date(2026, 8, 3)) == "2026"

    def test_a_trip_across_new_year_carries_both_years(self):
        """Filing a new-year trip under its start year is a small lie that
        surfaces once a year -- which is exactly how long it survives."""

        assert period_label(date(2025, 12, 30), date(2026, 1, 2)) == "2025–2026"

    def test_a_missing_date_is_refused_rather_than_formatted(self):
        with pytest.raises(AlbumError):
            period_label(None, date(2026, 1, 2))


class TestNothingIsGenerated:
    def test_the_title_is_the_groups_own_and_the_period_is_a_separate_field(self):
        """The spec's AI-composed album name is not implemented. Keeping the
        two apart means a client never has to guess which half a machine
        wrote, because neither half was."""

        album = build_album(TRIP, [])
        assert album["title"] == "Đà Lạt"
        assert album["period_label"] == "2026"

    def test_a_trip_with_no_title_gets_a_neutral_one_not_an_invented_one(self):
        album = build_album({**TRIP, "title": "  "}, [])
        assert album["title"] == "Chuyến đi"


class TestPhotographsAreReferencedNotRebuilt:
    def test_image_url_is_carried_through_verbatim(self):
        """A second place that formats media paths is a second thing to edit,
        and the album's URLs drift from the wall's the first time only one of
        them is."""

        album = build_album(TRIP, [_photo("aaa")])
        assert album["photos"][0]["image_url"] == "/contexts/c/photos/aaa"

    def test_a_photo_row_with_no_image_url_is_not_listed(self):
        album = build_album(TRIP, [{**_photo("aaa"), "image_url": None}])
        assert album["photos"] == []
        assert album["photo_count"] == 0


class TestHighlights:
    def test_highlights_are_ordered_by_the_hearts_the_group_left(self):
        album = build_album(
            TRIP,
            [_photo("a", hearts=1), _photo("b", hearts=9), _photo("c", hearts=4)],
        )
        assert [row["memory_id"] for row in album["highlights"]] == ["b", "c", "a"]

    def test_a_photograph_nobody_reacted_to_is_never_a_highlight(self):
        """With no threshold an album where nobody reacted would promote its
        newest rows and print the group's silence as a verdict."""

        album = build_album(TRIP, [_photo("a"), _photo("b")])
        assert album["highlights"] == []

    def test_highlights_are_a_subset_of_photos(self):
        album = build_album(TRIP, [_photo("a", hearts=3), _photo("b")])
        listed = {row["memory_id"] for row in album["photos"]}
        assert {row["memory_id"] for row in album["highlights"]} <= listed

    def test_hearts_beat_recency(self):
        album = build_album(
            TRIP, [_photo("new", hearts=1, day=3), _photo("old", hearts=8, day=1)]
        )
        assert album["highlights"][0]["memory_id"] == "old"


class TestPlacesAndCounts:
    def test_a_place_visited_twice_is_named_once(self):
        album = build_album(TRIP, [_checkin("p-a"), _checkin("p-a"), _checkin("p-b")])
        assert [row["place_id"] for row in album["places"]] == ["p-a", "p-b"]
        assert album["place_count"] == 2
        assert album["checkin_count"] == 3

    def test_checkins_are_not_counted_as_photographs(self):
        album = build_album(TRIP, [_checkin("p-a"), _photo("a")])
        assert album["photo_count"] == 1
        assert album["checkin_count"] == 1

    def test_money_and_headcount_come_from_the_trip_row_untouched(self):
        album = build_album(TRIP, [])
        assert album["split_total_vnd"] == 3_000_000
        assert album["expense_count"] == 4
        assert album["headcount"] == 5


class TestMalformed:
    def test_a_memory_that_is_not_a_mapping_is_refused(self):
        with pytest.raises(AlbumError):
            build_album(TRIP, ["a photo"])

    def test_an_outing_that_is_not_a_mapping_is_refused(self):
        with pytest.raises(AlbumError):
            build_album("Đà Lạt", [])
