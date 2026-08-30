"""F45: fair means minimax, and the server never learns who is where.

The ranking tests use synthetic points on the equator rather than the seed
catalogue, for one reason worth stating: on a straight line between two
origins, *total* travel is the same constant for every point in between. That
makes total useless as a discriminator there and leaves minimax as the only key
that can order those candidates -- which is exactly the disagreement this
feature turns on, isolated so a mutation cannot hide in it.
"""

from __future__ import annotations

import json
import unittest

from app.places.areas import find_area
from app.places.catalog import PLACES
from app.places.meeting import MAX_ORIGIN_AREAS, MIN_ORIGIN_AREAS, rank_meeting_points

WEST = {"id": "west", "label": "Tây", "lat": 0.0, "lng": 0.0}
EAST = {"id": "east", "label": "Đông", "lat": 0.0, "lng": 1.0}


def point(place_id: str, lng: float) -> dict:
    return {
        "id": place_id,
        "name": place_id,
        "category": "cafe",
        "address": "somewhere",
        "lat": 0.0,
        "lng": lng,
    }


#: Three candidates on the line between WEST and EAST. Every one of them has
#: the same total travel (the separation of the two origins), so only the worst
#: journey can tell them apart. Ids are chosen so that alphabetical order --
#: what a tie-break falls back on -- puts the *wrong* answer first.
NEAR_WEST = point("p-a-near-west", 0.05)
OFF_CENTRE = point("p-b-off-centre", 0.35)
MIDPOINT = point("p-c-midpoint", 0.5)
LINE = [NEAR_WEST, OFF_CENTRE, MIDPOINT]


class FairnessTest(unittest.TestCase):
    def test_the_midpoint_wins_between_two_origins(self):
        ranked = rank_meeting_points([WEST, EAST], LINE)
        self.assertEqual(ranked[0]["place_id"], MIDPOINT["id"])

    def test_ranking_by_total_travel_would_pick_a_different_place(self):
        """The mutation this design exists to refuse, made explicit.

        All three candidates tie on total, so a `sum`-keyed sort falls through
        to the id tie-break and returns `p-a-near-west` -- a "meeting point"
        five kilometres from one person and a hundred from the other. This test
        asserts the two orderings genuinely differ, so the assertion above is
        not quietly true under both keys.
        """

        ranked = rank_meeting_points([WEST, EAST], LINE)
        totals = {row["fairness"]["total_km"] for row in ranked}
        self.assertEqual(len(totals), 1, "candidates must tie on total travel")

        by_total = sorted(LINE, key=lambda place: place["id"])
        self.assertNotEqual(by_total[0]["id"], ranked[0]["place_id"])

    def test_the_worst_journey_is_what_orders_the_list(self):
        ranked = rank_meeting_points([WEST, EAST], LINE)
        worsts = [row["fairness"]["worst_km"] for row in ranked]
        self.assertEqual(worsts, sorted(worsts))

    def test_spread_is_zero_at_the_midpoint(self):
        ranked = rank_meeting_points([WEST, EAST], [MIDPOINT])
        self.assertAlmostEqual(ranked[0]["fairness"]["spread_km"], 0.0, places=2)

    def test_spread_is_large_at_one_end(self):
        ranked = rank_meeting_points([WEST, EAST], [NEAR_WEST])
        self.assertGreater(ranked[0]["fairness"]["spread_km"], 90.0)

    def test_multiplicity_does_not_move_the_worst_journey(self):
        """Three friends in the west still meet in the middle.

        Minimax is invariant to how many people share an origin, because
        duplicating a value does not change a maximum. This is the intended
        reading of "balanced" -- weighting by headcount would send everybody to
        wherever the majority already is -- and it is asserted rather than left
        as a surprise, because it is the property most likely to be "fixed"
        into a headcount weighting by someone who assumed it was a bug.
        """

        balanced = rank_meeting_points([WEST, EAST], LINE)[0]["place_id"]
        lopsided = rank_meeting_points([WEST, WEST, WEST, EAST], LINE)[0]["place_id"]
        self.assertEqual(balanced, MIDPOINT["id"])
        self.assertEqual(lopsided, balanced)

    def test_multiplicity_breaks_a_tie_on_the_worst_journey(self):
        """Where duplicates *do* bite: two candidates level on minimax.

        `p-z-west` and `p-a-east` sit symmetrically about the midpoint, so
        their worst journeys are identical and the total decides. With one
        friend at each end the totals are identical too and the id tie-break
        picks `p-a-east`; with three in the west the total pulls the answer
        west, to the candidate id-order would not have chosen. Removing
        `total_km` from the sort key turns this red.
        """

        west_candidate = point("p-z-west", 0.4)
        east_candidate = point("p-a-east", 0.6)
        pair = [west_candidate, east_candidate]

        even = rank_meeting_points([WEST, EAST], pair)
        self.assertAlmostEqual(
            even[0]["fairness"]["worst_km"], even[1]["fairness"]["worst_km"], places=2
        )
        self.assertEqual(even[0]["place_id"], "p-a-east")

        weighted = rank_meeting_points([WEST, WEST, WEST, EAST], pair)
        self.assertEqual(weighted[0]["place_id"], "p-z-west")

    def test_every_origin_gets_a_leg(self):
        ranked = rank_meeting_points([WEST, WEST, EAST], [MIDPOINT])
        self.assertEqual(len(ranked[0]["travel"]), 3)

    def test_limit_is_honoured(self):
        ranked = rank_meeting_points([WEST, EAST], LINE, limit=2)
        self.assertEqual(len(ranked), 2)

    def test_no_places_is_an_empty_answer_not_a_crash(self):
        self.assertEqual(rank_meeting_points([WEST, EAST], []), [])


class PrivacyShapeTest(unittest.TestCase):
    def test_the_answer_names_areas_and_never_a_person(self):
        """The structural guarantee: there is no person in the input, so there
        is none in the output. Nothing here is being carefully omitted."""

        ranked = rank_meeting_points([WEST, EAST], LINE)
        blob = json.dumps(ranked, default=str)
        for forbidden in ("person", "member", "author", "actor", "user"):
            with self.subTest(field=forbidden):
                self.assertNotIn(forbidden, blob.lower())

    def test_legs_are_attributed_to_the_areas_the_caller_supplied(self):
        ranked = rank_meeting_points([WEST, EAST], [MIDPOINT])
        self.assertEqual(
            [leg["id"] for leg in ranked[0]["travel"]], [WEST["id"], EAST["id"]]
        )

    def test_the_internal_sort_key_does_not_reach_the_wire(self):
        ranked = rank_meeting_points([WEST, EAST], LINE)
        for row in ranked:
            self.assertNotIn("_sort", row)


class RealCatalogueTest(unittest.TestCase):
    def test_saigon_friends_are_not_sent_to_da_lat(self):
        """The sanity check the synthetic points cannot make.

        Four origins across Saigon, and the catalogue contains eight Đà Lạt
        places 200 km away. A meeting point that is not in Saigon means the
        distance term is not being applied at all.
        """

        origins = [
            find_area("hcm-quan-1"),
            find_area("hcm-quan-3"),
            find_area("hcm-quan-7"),
            find_area("hcm-thu-duc"),
        ]
        ranked = rank_meeting_points(origins, PLACES)
        self.assertTrue(ranked)
        winner = next(
            place for place in PLACES if place["id"] == ranked[0]["place_id"]
        )
        self.assertIn("TP.HCM", winner["address"])

    def test_bounds_are_stated_constants(self):
        """Pinned so the route and this module cannot disagree about them."""

        self.assertEqual(MIN_ORIGIN_AREAS, 2)
        self.assertGreaterEqual(MAX_ORIGIN_AREAS, 4)


if __name__ == "__main__":
    unittest.main()
