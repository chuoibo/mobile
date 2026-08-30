"""Areas: the bucket that makes F44 safe to answer at all.

Pure functions, so this tier proves the arithmetic and the parsing completely.
What it does not prove is that any *route* uses them -- that is
`tests/postgres/test_social_map_postgres.py`, which is where a caller and a
membership row exist.
"""

from __future__ import annotations

import unittest

from app.places.areas import (
    AREAS,
    MAX_AREA_RADIUS_KM,
    area_of_address,
    find_area,
    haversine_km,
    nearest_area,
)
from app.places.catalog import PLACES


class AreaCatalogueTest(unittest.TestCase):
    def test_ids_are_unique(self):
        ids = [area["id"] for area in AREAS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_centroid_is_a_point_on_earth(self):
        for area in AREAS:
            with self.subTest(area=area["id"]):
                self.assertTrue(-90 <= area["lat"] <= 90)
                self.assertTrue(-180 <= area["lng"] <= 180)

    def test_find_area_refuses_an_unknown_id(self):
        self.assertIsNone(find_area("khong-co-khu-nay"))


class HaversineTest(unittest.TestCase):
    def test_a_point_is_zero_from_itself(self):
        self.assertAlmostEqual(haversine_km(10.77, 106.70, 10.77, 106.70), 0.0)

    def test_one_degree_of_longitude_at_the_equator(self):
        """111.195 km on a mean-radius sphere.

        Not 111.32: that figure uses the *equatorial* radius 6378.137, and this
        module uses the mean radius 6371.0088. Both are defensible choices for a
        distance between two districts; only one of them is the one implemented,
        and pinning the wrong constant here would have been a test asserting a
        number the code never claimed. A degree/radian slip moves this by tens
        of kilometres, so it still catches the mistake it was written for.
        """

        self.assertAlmostEqual(haversine_km(0.0, 0.0, 0.0, 1.0), 111.195, delta=0.01)

    def test_it_is_symmetric(self):
        there = haversine_km(11.94, 108.43, 10.77, 106.70)
        back = haversine_km(10.77, 106.70, 11.94, 108.43)
        self.assertAlmostEqual(there, back)

    def test_da_lat_to_saigon_is_about_two_hundred_kilometres(self):
        """The two cities in the seed catalogue, far enough apart that no
        radius could ever file one city's check-in under the other's."""

        km = haversine_km(11.9433, 108.4370, 10.7769, 106.7009)
        self.assertGreater(km, 200.0)


class AddressParsingTest(unittest.TestCase):
    def test_every_da_lat_ward_lands_in_the_one_da_lat_bucket(self):
        """Ward numbers are deliberately not read -- see `AREAS`.

        The seed catalogue's Đà Lạt wards disagree with its own coordinates, so
        a ward-level bucket would contradict the address printed beside it.
        """

        for address in (
            "27/1 Yersin, P.10, TP. Đà Lạt, Lâm Đồng",
            "5 Nguyễn Chí Thanh, P.1, TP. Đà Lạt, Lâm Đồng",
            "Đường Mai Anh Đào, P.8, TP. Đà Lạt, Lâm Đồng",
        ):
            with self.subTest(address=address):
                area = area_of_address(address)
                self.assertIsNotNone(area)
                self.assertEqual(area["id"], "da-lat")

    def test_numbered_saigon_district(self):
        area = area_of_address("220 Vĩnh Khánh, P.9, Quận 4, TP.HCM")
        self.assertIsNotNone(area)
        self.assertEqual(area["id"], "hcm-quan-4")

    def test_a_saigon_address_with_a_ward_number_is_not_read_as_da_lat(self):
        """`P.9` appears in Saigon addresses too. The city is decided first,
        so the ward pattern never runs on them."""

        area = area_of_address("180 Nam Kỳ Khởi Nghĩa, P.6, Quận 3, TP.HCM")
        self.assertIsNotNone(area)
        self.assertEqual(area["id"], "hcm-quan-3")

    def test_named_saigon_district(self):
        area = area_of_address("330 Phan Đình Phùng, P.1, Q. Phú Nhuận, TP.HCM")
        self.assertIsNotNone(area)
        self.assertEqual(area["id"], "hcm-phu-nhuan")

    def test_an_address_in_neither_city_is_none(self):
        self.assertIsNone(area_of_address("1 Tràng Tiền, Hoàn Kiếm, Hà Nội"))

    def test_blank_is_none_rather_than_a_guess(self):
        self.assertIsNone(area_of_address(""))


class NearestAreaTest(unittest.TestCase):
    def test_a_centroid_resolves_to_its_own_area(self):
        for area in AREAS:
            with self.subTest(area=area["id"]):
                found = nearest_area(area["lat"], area["lng"])
                self.assertIsNotNone(found)
                self.assertEqual(found["id"], area["id"])

    def test_a_coordinate_far_from_every_district_is_none(self):
        """Hanoi. Without the radius this returns whichever Saigon district is
        least wrong, and a heatmap then reports the group hangs out there."""

        self.assertIsNone(nearest_area(21.0278, 105.8342))

    def test_the_null_island_coordinate_is_none(self):
        """0,0 is what a broken client sends. It must not become a district."""

        self.assertIsNone(nearest_area(0.0, 0.0))

    def test_every_seed_place_resolves_to_some_area(self):
        """If this fails the heatmap silently under-counts real visits, and
        `unknown_area_count` is the only thing that would show it."""

        for place in PLACES:
            with self.subTest(place=place["id"]):
                self.assertIsNotNone(nearest_area(place["lat"], place["lng"]))

    def test_resolution_agrees_with_the_address_for_every_seed_place(self):
        """Two independent routes to the same answer, cross-checked.

        `nearest_area` reads the snapshot coordinate and `area_of_address`
        reads the text. They are computed from different fields of the same
        row, so a centroid that drifted into the wrong district shows up here
        rather than as a quietly wrong heatmap.
        """

        for place in PLACES:
            with self.subTest(place=place["id"]):
                by_point = nearest_area(place["lat"], place["lng"])
                by_text = area_of_address(place["address"])
                self.assertIsNotNone(by_point)
                self.assertIsNotNone(by_text)
                self.assertEqual(by_point["id"], by_text["id"])

    def test_a_point_just_past_the_radius_is_refused(self):
        """Due north of a centroid by slightly more than the radius.

        Pins the bound itself: widening `MAX_AREA_RADIUS_KM` turns this red,
        which is the point -- the radius is a privacy-relevant claim about how
        far a coordinate may be dragged before it stops being an area.
        """

        area = find_area("hcm-thu-duc")
        # ~111.32 km per degree of latitude, so this is the radius plus 2 km.
        offset = (MAX_AREA_RADIUS_KM + 2.0) / 111.32
        self.assertIsNone(nearest_area(area["lat"] + offset, area["lng"]))


if __name__ == "__main__":
    unittest.main()
