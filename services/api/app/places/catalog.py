"""Seed data for the Khám phá screen.

Synthetic but plausible. Names, addresses, ratings and coordinates are invented
for a demo: no real business is being described, rated or geolocated here, and
nothing in this file came from a person. That matters beyond politeness --
putting a real venue's real rating in a repo is the kind of data the charter
keeps out of Git, and inventing one avoids the question entirely.

These twelve rows are no longer the catalogue. Since M9 (ADR-0017) the
catalogue is the `places` table, and this file is the **seed material** that
`app/places/seed_catalog.py` loads into it for demos and tests -- which is why
every id here still matters: flows, fixtures and saved bookmarks name them.

The old note said «when places become user-editable this file is the thing that
gets replaced, and the route's shape does not have to». That is what happened:
the route's shape did not change, and real venues arrive through
`scripts/import_osm_places.py` instead of through this file, because real venue
data may not live in Git.
"""

from __future__ import annotations

from typing import Any, TypedDict


class GroupProfile(TypedDict):
    size: int
    age_range: str
    budget_per_person_vnd: int
    likes: list[str]
    max_distance_km: float
    when: str


CATEGORIES: list[dict[str, str]] = [
    {"id": "quan-an-local", "label": "Quán ăn local"},
    {"id": "cafe", "label": "Cafe"},
    {"id": "vui-choi", "label": "Vui chơi"},
    {"id": "di-choi-dem", "label": "Đi chơi đêm"},
]

# The group every score in `scoring.py` is relative to, and the one the route
# discloses in its response. A percentage whose basis is not stated is a
# decoration; stating it here in one place is what makes the arithmetic
# checkable by hand.
#
# Hard-coded for the vertical slice: the app has one synthetic group, and the
# route takes `context_id` so the seam for reading a real one already exists.
GROUP: GroupProfile = {
    "size": 6,
    "age_range": "22-28",
    "budget_per_person_vnd": 250_000,
    "likes": ["Chill", "View đẹp", "Đồ nướng", "Ngoài trời", "Nhóm đông"],
    "max_distance_km": 5.0,
    "when": "Tối nay",
}

PLACES: list[dict[str, Any]] = [
    {
        "id": "p-tiem-nuong-xom-lao",
        "name": "Tiệm Nướng Xóm Lào",
        "category": "quan-an-local",
        "kinds": ["BBQ", "Lào", "Local"],
        "rating": 4.7,
        "rating_count": 128,
        "distance_km": 1.2,
        "price_min_vnd": 200_000,
        "price_max_vnd": 250_000,
        "address": "27/1 Yersin, P.10, TP. Đà Lạt, Lâm Đồng",
        "open_now": True,
        "open_hours": "10:00 – 22:30",
        "travel_minutes": 25,
        "photo_count": 18,
        "traits": ["Chill", "View đẹp", "Nhóm đông", "Đồ nướng", "Ngoài trời"],
        "group_fit": {
            "min_people": 4,
            "max_people": 10,
            "relation": "Bạn bè, đồng nghiệp",
        },
        "flag": None,
        "lat": 11.9404,
        "lng": 108.4383,
    },
    {
        "id": "p-lung-chung-cafe",
        "name": "Lưng Chừng Cafe",
        "category": "cafe",
        "kinds": ["Cafe", "View đồi"],
        "rating": 4.6,
        "rating_count": 156,
        "distance_km": 1.6,
        "price_min_vnd": 180_000,
        "price_max_vnd": 230_000,
        "address": "12 Khe Sanh, P.10, TP. Đà Lạt, Lâm Đồng",
        "open_now": True,
        "open_hours": "07:00 – 22:00",
        "travel_minutes": 20,
        "photo_count": 24,
        "traits": ["Chill", "Sống ảo", "Nhẹ nhàng", "View đẹp", "Ngoài trời"],
        "group_fit": {"min_people": 2, "max_people": 8, "relation": "Bạn bè, cặp đôi"},
        "flag": None,
        "lat": 11.9512,
        "lng": 108.4451,
    },
    {
        "id": "p-chill-dem-da-lat",
        "name": "Chill Đêm Đà Lạt",
        "category": "di-choi-dem",
        "kinds": ["Bar", "Rooftop"],
        "rating": 4.5,
        "rating_count": 112,
        "distance_km": 1.8,
        "price_min_vnd": 250_000,
        "price_max_vnd": 250_000,
        "address": "5 Nguyễn Chí Thanh, P.1, TP. Đà Lạt, Lâm Đồng",
        "open_now": True,
        "open_hours": "18:00 – 01:00",
        "travel_minutes": 22,
        "photo_count": 11,
        "traits": ["Rooftop", "Nhạc chill", "Cocktail", "View đẹp"],
        "group_fit": {"min_people": 4, "max_people": 12, "relation": "Bạn bè"},
        "flag": "hot",
        "lat": 11.9435,
        "lng": 108.4372,
    },
    {
        "id": "p-an-cafe-da-lat",
        "name": "An Cafe Đà Lạt",
        "category": "cafe",
        "kinds": ["Cafe", "Vintage"],
        "rating": 4.4,
        "rating_count": 98,
        "distance_km": 2.1,
        "price_min_vnd": 150_000,
        "price_max_vnd": 200_000,
        "address": "63 Phan Đình Phùng, P.2, TP. Đà Lạt, Lâm Đồng",
        "open_now": True,
        "open_hours": "07:30 – 22:00",
        "travel_minutes": 18,
        "photo_count": 9,
        "traits": ["Vintage", "Yên tĩnh", "Đồ uống ngon"],
        "group_fit": {"min_people": 2, "max_people": 6, "relation": "Bạn thân"},
        "flag": None,
        "lat": 11.9376,
        "lng": 108.4429,
    },
    {
        "id": "p-dreampark",
        "name": "Khu vui chơi DREAMpark",
        "category": "vui-choi",
        "kinds": ["Giải trí", "Nhiều hoạt động"],
        "rating": 4.6,
        "rating_count": 118,
        "distance_km": 2.3,
        "price_min_vnd": 220_000,
        "price_max_vnd": 320_000,
        "address": "Đường Mai Anh Đào, P.8, TP. Đà Lạt, Lâm Đồng",
        "open_now": True,
        "open_hours": "08:00 – 21:00",
        "travel_minutes": 28,
        "photo_count": 32,
        "traits": ["Nhóm đông", "Ngoài trời", "Nhiều trò"],
        "group_fit": {
            "min_people": 4,
            "max_people": 20,
            "relation": "Bạn bè, gia đình",
        },
        "flag": "new",
        "lat": 11.9601,
        "lng": 108.4498,
    },
    {
        "id": "p-lau-ga-la-e",
        "name": "Lẩu Gà Lá É Tao Ngộ",
        "category": "quan-an-local",
        "kinds": ["Lẩu", "Đặc sản", "Local"],
        "rating": 4.5,
        "rating_count": 204,
        "distance_km": 2.8,
        "price_min_vnd": 170_000,
        "price_max_vnd": 220_000,
        "address": "5B Nguyễn Công Trứ, P.8, TP. Đà Lạt, Lâm Đồng",
        "open_now": True,
        "open_hours": "10:00 – 22:00",
        "travel_minutes": 24,
        "photo_count": 14,
        "traits": ["Nhóm đông", "Ấm cúng", "Đặc sản"],
        "group_fit": {
            "min_people": 4,
            "max_people": 12,
            "relation": "Bạn bè, đồng nghiệp",
        },
        "flag": None,
        "lat": 11.9339,
        "lng": 108.4287,
    },
    {
        "id": "p-nuong-ngoi-troi-thong",
        "name": "Nướng Ngói Trời Thông",
        "category": "quan-an-local",
        "kinds": ["BBQ", "Ngoài trời"],
        "rating": 4.3,
        "rating_count": 76,
        "distance_km": 3.4,
        "price_min_vnd": 230_000,
        "price_max_vnd": 290_000,
        "address": "18 Trần Hưng Đạo, P.3, TP. Đà Lạt, Lâm Đồng",
        "open_now": False,
        "open_hours": "16:00 – 23:00",
        "travel_minutes": 30,
        "photo_count": 7,
        "traits": ["Đồ nướng", "Ngoài trời", "Nhóm đông", "Chill"],
        "group_fit": {"min_people": 4, "max_people": 14, "relation": "Bạn bè"},
        "flag": None,
        "lat": 11.9285,
        "lng": 108.4451,
    },
    {
        "id": "p-song-mau-workshop",
        "name": "Sống Màu Workshop",
        "category": "vui-choi",
        "kinds": ["Workshop", "Gốm"],
        "rating": 4.8,
        "rating_count": 64,
        "distance_km": 3.9,
        "price_min_vnd": 250_000,
        "price_max_vnd": 350_000,
        "address": "31 Hùng Vương, P.10, TP. Đà Lạt, Lâm Đồng",
        "open_now": True,
        "open_hours": "09:00 – 18:00",
        "travel_minutes": 26,
        "photo_count": 21,
        "traits": ["Sáng tạo", "Nhẹ nhàng", "Sống ảo"],
        "group_fit": {
            "min_people": 2,
            "max_people": 8,
            "relation": "Bạn thân, cặp đôi",
        },
        "flag": "new",
        "lat": 11.9478,
        "lng": 108.4557,
    },
    {
        "id": "p-quan-oc-di-be",
        "name": "Quán Ốc Dì Bé",
        "category": "quan-an-local",
        "kinds": ["Hải sản", "Bình dân", "Local"],
        "rating": 4.4,
        "rating_count": 311,
        "distance_km": 4.6,
        "price_min_vnd": 120_000,
        "price_max_vnd": 180_000,
        "address": "220 Vĩnh Khánh, P.9, Quận 4, TP.HCM",
        "open_now": True,
        "open_hours": "16:00 – 00:00",
        "travel_minutes": 32,
        "photo_count": 12,
        "traits": ["Nhóm đông", "Bình dân", "Ngoài trời"],
        "group_fit": {"min_people": 3, "max_people": 12, "relation": "Bạn bè"},
        "flag": None,
        "lat": 10.7561,
        "lng": 106.7024,
    },
    {
        "id": "p-the-hill-rooftop",
        "name": "The Hill Rooftop",
        "category": "di-choi-dem",
        "kinds": ["Rooftop", "Nhạc sống"],
        "rating": 4.2,
        "rating_count": 89,
        "distance_km": 5.2,
        "price_min_vnd": 320_000,
        "price_max_vnd": 450_000,
        "address": "76 Lê Lai, P. Bến Thành, Quận 1, TP.HCM",
        "open_now": True,
        "open_hours": "17:00 – 02:00",
        "travel_minutes": 38,
        "photo_count": 26,
        "traits": ["Rooftop", "Nhạc sống", "View đẹp"],
        "group_fit": {
            "min_people": 4,
            "max_people": 16,
            "relation": "Bạn bè, đồng nghiệp",
        },
        "flag": "hot",
        "lat": 10.7702,
        "lng": 106.6944,
    },
    {
        "id": "p-ca-phe-vot-hem",
        "name": "Cà Phê Vợt Hẻm 330",
        "category": "cafe",
        "kinds": ["Cafe", "Cổ", "Local"],
        "rating": 4.5,
        "rating_count": 142,
        "distance_km": 6.1,
        "price_min_vnd": 60_000,
        "price_max_vnd": 90_000,
        "address": "330 Phan Đình Phùng, P.1, Q. Phú Nhuận, TP.HCM",
        "open_now": True,
        "open_hours": "05:00 – 23:00",
        "travel_minutes": 35,
        "photo_count": 8,
        "traits": ["Yên tĩnh", "Local", "Bình dân"],
        "group_fit": {"min_people": 2, "max_people": 5, "relation": "Bạn thân"},
        "flag": None,
        "lat": 10.7935,
        "lng": 106.6801,
    },
    {
        "id": "p-bowling-sky",
        "name": "Bowling Sky Center",
        "category": "vui-choi",
        "kinds": ["Bowling", "Trong nhà"],
        "rating": 4.1,
        "rating_count": 57,
        "distance_km": 7.4,
        "price_min_vnd": 180_000,
        "price_max_vnd": 260_000,
        "address": "180 Nam Kỳ Khởi Nghĩa, P.6, Quận 3, TP.HCM",
        "open_now": True,
        "open_hours": "10:00 – 23:00",
        "travel_minutes": 41,
        "photo_count": 15,
        "traits": ["Nhóm đông", "Trong nhà", "Vận động"],
        "group_fit": {
            "min_people": 4,
            "max_people": 12,
            "relation": "Bạn bè, đồng nghiệp",
        },
        "flag": None,
        "lat": 10.7864,
        "lng": 106.6893,
    },
]


def find_place(place_id: str) -> dict[str, Any] | None:
    """The one row with this id, or None.

    Exists so `POST /contexts/{id}/checkins` never takes a venue's name or its
    coordinates from the request body. A client that could send those could
    write "the group was at 0,0" into a group's permanent history, and no
    later reader would have anything to check it against.

    A linear scan over twelve rows. When this file becomes a table -- which
    the module docstring says it will -- this function is the seam that gets a
    WHERE clause, and its callers do not change.
    """

    return next((place for place in PLACES if place["id"] == place_id), None)
