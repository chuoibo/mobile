"""F43/F44 aggregation, and the privacy property that is the whole point.

The interesting tests here are not "does it count correctly". They are the ones
that feed a private field in and prove it does not come out -- because the
functions under test take the *full* check-in record on purpose, so that the
stripping happens somewhere it can be tested rather than in a caller that could
quietly stop doing it.

What this tier does not prove: that any route is gated. A pure function has no
actor. `tests/postgres/test_social_map_postgres.py` proves the gate, with a real
membership row and a real outsider.
"""

from __future__ import annotations

import json
import unittest
import uuid
from datetime import UTC, datetime

from app.places.areas import find_area
from app.places.catalog import PLACES
from app.places.social_map import (
    PRIVATE_CHECKIN_FIELDS,
    heatmap_rows,
    trending_layer,
    unknown_area_count,
    visited_layer,
)

DA_LAT = PLACES[0]
CAFE = PLACES[1]
SAIGON = next(place for place in PLACES if "Quận 4" in place["address"])

AUTHOR = uuid.UUID("a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5")
OTHER_AUTHOR = uuid.UUID("f5e4d3c2-b1a0-4f9e-8d7c-b6a5f4e3d2c1")
WHEN = datetime(2026, 3, 14, 20, 30, tzinfo=UTC)


def checkin(place, *, author=AUTHOR, when=WHEN):
    """A check-in row shaped exactly as the repository hands it over.

    Carries `author_id` and `created_at` deliberately. A fixture that omitted
    them would make every privacy assertion below vacuous.
    """

    return {
        "id": uuid.uuid4(),
        "place_id": place["id"],
        "place_name": place["name"],
        "lat": place["lat"],
        "lng": place["lng"],
        "author_id": author,
        "created_at": when,
        "caption": "Tới rồi nha",
    }


class VisitedLayerTest(unittest.TestCase):
    def test_repeat_visits_roll_into_one_row_with_a_count(self):
        rows = visited_layer([checkin(DA_LAT), checkin(DA_LAT), checkin(CAFE)])
        self.assertEqual([row["place_id"] for row in rows], [DA_LAT["id"], CAFE["id"]])
        self.assertEqual([row["visit_count"] for row in rows], [2, 1])

    def test_it_orders_by_count_then_id(self):
        """Deterministic, and deliberately not by recency: the order of a list
        is enough to recover roughly when each visit happened."""

        rows = visited_layer([checkin(CAFE), checkin(DA_LAT), checkin(SAIGON)])
        self.assertEqual(
            [row["place_id"] for row in rows],
            sorted([CAFE["id"], DA_LAT["id"], SAIGON["id"]]),
        )

    def test_a_photo_memory_is_not_a_visit(self):
        """Photos have no place and no coordinates. Counting them as visits
        would inflate every number on the map."""

        photo = {
            "id": uuid.uuid4(),
            "place_id": None,
            "place_name": None,
            "lat": None,
            "lng": None,
            "author_id": AUTHOR,
            "created_at": WHEN,
        }
        self.assertEqual(visited_layer([photo]), [])

    def test_no_author_and_no_timestamp_survive(self):
        """The property F43 exists under. Two distinct authors, one place: the
        answer is "2 visits" and never "these two people"."""

        rows = visited_layer([checkin(DA_LAT), checkin(DA_LAT, author=OTHER_AUTHOR)])

        # The exact shape, not "does not contain". A new key added to this
        # function has to be added here too, which is the moment somebody has
        # to justify it.
        self.assertEqual(
            set(rows[0]),
            {"place_id", "place_name", "lat", "lng", "visit_count"},
        )
        blob = json.dumps(rows, default=str)
        for field in PRIVATE_CHECKIN_FIELDS:
            with self.subTest(field=field):
                self.assertNotIn(field, blob)
        self.assertNotIn(str(AUTHOR), blob)
        self.assertNotIn(str(OTHER_AUTHOR), blob)
        self.assertNotIn("2026", blob)


class TrendingLayerTest(unittest.TestCase):
    def test_it_is_the_hot_flag_and_nothing_else(self):
        rows = trending_layer(PLACES)
        self.assertEqual(
            {row["place_id"] for row in rows},
            {place["id"] for place in PLACES if place["flag"] == "hot"},
        )

    def test_it_does_not_depend_on_the_group(self):
        """Same list for everybody. A "trending" layer that mixed in the
        group's own history would be a second channel for private data
        wearing a public-looking name."""

        self.assertEqual(trending_layer(PLACES), trending_layer(PLACES))


class HeatmapTest(unittest.TestCase):
    def test_it_buckets_by_district_and_counts(self):
        rows = heatmap_rows(
            [checkin(DA_LAT), checkin(CAFE), checkin(SAIGON)],
        )
        by_id = {row["id"]: row for row in rows}
        # Both Đà Lạt places land in the one Đà Lạt bucket.
        self.assertEqual(by_id["da-lat"]["visit_count"], 2)
        self.assertEqual(by_id["hcm-quan-4"]["visit_count"], 1)

    def test_shares_are_a_percentage_of_what_resolved(self):
        rows = heatmap_rows([checkin(DA_LAT), checkin(CAFE), checkin(SAIGON)])
        by_id = {row["id"]: row for row in rows}
        self.assertEqual(by_id["da-lat"]["share_percent"], 66)
        self.assertEqual(by_id["hcm-quan-4"]["share_percent"], 33)

    def test_an_empty_history_is_an_empty_heatmap_not_a_crash(self):
        self.assertEqual(heatmap_rows([]), [])

    def test_a_visit_outside_every_district_is_counted_not_dropped(self):
        """Disclosure, not silence. A heatmap built from 1 of 2 visits and
        presented as the group's habits is a confident wrong answer."""

        hanoi = {
            "id": uuid.uuid4(),
            "place_id": "p-somewhere-else",
            "place_name": "Chỗ nào đó",
            "lat": 21.0278,
            "lng": 105.8342,
            "author_id": AUTHOR,
            "created_at": WHEN,
        }
        rows = heatmap_rows([checkin(DA_LAT), hanoi])
        self.assertEqual([row["id"] for row in rows], ["da-lat"])
        self.assertEqual(rows[0]["visit_count"], 1)
        self.assertEqual(unknown_area_count([checkin(DA_LAT), hanoi]), 1)

    def test_ordering_is_stable_for_equal_counts(self):
        first = heatmap_rows([checkin(DA_LAT), checkin(SAIGON)])
        second = heatmap_rows([checkin(SAIGON), checkin(DA_LAT)])
        self.assertEqual([row["id"] for row in first], [row["id"] for row in second])

    def test_no_author_and_no_timestamp_survive(self):
        """F44's stated requirement: the heatmap must not let a reader work
        out who was where at what time."""

        rows = heatmap_rows(
            [checkin(DA_LAT), checkin(CAFE, author=OTHER_AUTHOR), checkin(SAIGON)]
        )

        self.assertEqual(
            set(rows[0]),
            {"id", "label", "lat", "lng", "visit_count", "share_percent"},
        )
        blob = json.dumps(rows, default=str)
        for field in PRIVATE_CHECKIN_FIELDS:
            with self.subTest(field=field):
                self.assertNotIn(field, blob)
        self.assertNotIn(str(AUTHOR), blob)
        self.assertNotIn(str(OTHER_AUTHOR), blob)
        self.assertNotIn("2026", blob)

    def test_a_single_visit_does_not_expose_a_coordinate(self):
        """The worst case for inference: one check-in, one bucket.

        Even then the answer is a district centroid, not the venue's own
        coordinate -- so the heatmap cannot be used to locate the visit more
        precisely than the bucket it is being reported in.
        """

        rows = heatmap_rows([checkin(SAIGON)])
        area = find_area("hcm-quan-4")
        self.assertEqual(rows[0]["lat"], area["lat"])
        self.assertEqual(rows[0]["lng"], area["lng"])
        self.assertNotEqual(rows[0]["lat"], SAIGON["lat"])
        self.assertNotEqual(rows[0]["lng"], SAIGON["lng"])


if __name__ == "__main__":
    unittest.main()
