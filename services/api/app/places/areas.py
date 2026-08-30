"""Areas: the coarsest place-shaped thing this product is willing to name.

F44 asks the group where it hangs out and expects an answer like "District 1,
District 3, Thu Duc". That answer is a *bucket*, and the bucket size is the
whole privacy design: a coordinate says where somebody stood, a district says
which part of town a group tends towards. Only the second one is safe to
aggregate and hand back.

## Why areas resolve from coordinates, not from the catalogue

A check-in on the memory wall snapshots `place_id`, `place_name`, `lat` and
`lng` at the moment the button was pressed -- `Memory` says why, at length: the
catalogue is seed data with a stated expiry, and a venue that later moves would
otherwise rewrite where the group was last March. Resolving an area by looking
`place_id` back up in `catalog.py` would re-introduce exactly the drift that
snapshot exists to prevent. So `nearest_area` reads the snapshot.

## Why an unmatched coordinate is None and not "the closest one"

`nearest_area` without a radius is a function that always answers, which sounds
convenient until a check-in in Hanoi is reported as District 1 because that was
the least-wrong option on offer. A heatmap row is a claim about where a group
goes; an unbounded nearest-neighbour makes that claim unfalsifiable. Anything
further than `MAX_AREA_RADIUS_KM` from every known centroid is `None`, and the
routes above disclose the count of rows that landed there rather than dropping
them silently.

Synthetic data, like `catalog.py`: these centroids are approximate points for a
demo, not survey coordinates, and no real person's location is described here.
"""

from __future__ import annotations

import math
import re
from typing import Any, TypedDict

__all__ = [
    "AREAS",
    "MAX_AREA_RADIUS_KM",
    "Area",
    "area_of_address",
    "find_area",
    "haversine_km",
    "nearest_area",
]


class Area(TypedDict):
    id: str
    label: str
    lat: float
    lng: float


#: District-level buckets. Deliberately coarse: this is the resolution at which
#: "where does the group hang out" can be answered without the answer also
#: being "and here is where a member was standing".
#:
#: ## Why Đà Lạt is one area and Saigon is four
#:
#: Not a judgement about the cities. The seed catalogue's ward numbers and its
#: coordinates were invented independently and do not agree with each other:
#: two places whose addresses both say `P.8` sit 3.7 km apart, and the three
#: `P.10` rows are scattered across the same spread. Ward-level buckets built
#: on those coordinates would file a place under a district its own address
#: contradicts -- the screen would show "Phường 8" beside an address reading
#: "P.10", and the heatmap would be quietly wrong in a way that looks like a
#: rendering bug rather than a data one.
#:
#: The Saigon rows do agree: each sits within a kilometre of its stated
#: district's real centroid, so those buckets are honest at district level.
#: `test_areas.py` cross-checks both claims against the catalogue, so if the
#: seed data is ever made internally consistent this comment fails with it.
AREAS: list[Area] = [
    # Centroid of the eight Đà Lạt rows; every one of them is within ~2 km.
    {"id": "da-lat", "label": "Đà Lạt", "lat": 11.9429, "lng": 108.4428},
    {"id": "hcm-quan-1", "label": "Quận 1, TP.HCM", "lat": 10.7769, "lng": 106.7009},
    {"id": "hcm-quan-3", "label": "Quận 3, TP.HCM", "lat": 10.7840, "lng": 106.6870},
    {"id": "hcm-quan-4", "label": "Quận 4, TP.HCM", "lat": 10.7590, "lng": 106.7050},
    {
        "id": "hcm-phu-nhuan",
        "label": "Phú Nhuận, TP.HCM",
        "lat": 10.7990,
        "lng": 106.6800,
    },
    # No seed place sits in these three. They exist as *origins* for F45, which
    # asks where people are starting from, not where the catalogue is.
    {"id": "hcm-quan-7", "label": "Quận 7, TP.HCM", "lat": 10.7340, "lng": 106.7220},
    {
        "id": "hcm-binh-thanh",
        "label": "Bình Thạnh, TP.HCM",
        "lat": 10.8040,
        "lng": 106.7100,
    },
    {"id": "hcm-thu-duc", "label": "Thủ Đức, TP.HCM", "lat": 10.8500, "lng": 106.7550},
]

#: Beyond this, a coordinate belongs to no area this product knows. Districts
#: here sit 1--15 km apart and the two cities are ~300 km apart, so the radius
#: is wide enough never to orphan a real seed row and narrow enough that one
#: city's check-in can never be filed under the other's.
MAX_AREA_RADIUS_KM = 25.0

_EARTH_RADIUS_KM = 6371.0088

#: `Quận 1` must not match inside `Quận 10`. The trailing boundary is what
#: stops that, and it is why this is a regex and not a substring search.
_HCM_DISTRICT = re.compile(r"Qu[âậ]n\s+(\d+)\b", re.IGNORECASE)
_NAMED_HCM = (
    ("phú nhuận", "hcm-phu-nhuan"),
    ("bình thạnh", "hcm-binh-thanh"),
    ("thủ đức", "hcm-thu-duc"),
)

_BY_ID = {area["id"]: area for area in AREAS}


def find_area(area_id: str) -> Area | None:
    """The one area with this id, or None.

    The seam every caller uses instead of indexing `AREAS`, so an id that came
    from a request body is resolved in exactly one place.
    """

    return _BY_ID.get(area_id)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres.

    Floats, and allowed to be: money law 1 governs money, and a distance is not
    money. Nothing in this module may touch a `_vnd` field, which is what keeps
    the two apart -- see the test that asserts it.
    """

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def nearest_area(lat: float, lng: float) -> Area | None:
    """The area this coordinate falls in, or None when it falls in none.

    Ties break on `id` so two runs over the same history produce the same
    heatmap. A heatmap that reshuffles under a thumb reads as new information
    about the group when nothing changed.
    """

    best: Area | None = None
    best_km = MAX_AREA_RADIUS_KM
    for area in sorted(AREAS, key=lambda row: row["id"]):
        km = haversine_km(lat, lng, area["lat"], area["lng"])
        if km < best_km:
            best, best_km = area, km
    return best


def area_of_address(address: str) -> Area | None:
    """The area a catalogue address names, or None.

    Used for catalogue rows, which have an address and no visit behind them.
    Check-ins do not come through here: they carry a snapshot coordinate, and
    `nearest_area` reads that instead for the reason in the module docstring.
    """

    if not address:
        return None
    lowered = address.lower()
    # City first, and Đà Lạt returns before the district patterns run. Saigon
    # addresses carry ward numbers too (`P.9, Quận 4`), so a parser that looked
    # for wards before deciding the city would read half of Saigon as Đà Lạt.
    if "đà lạt" in lowered:
        return find_area("da-lat")
    if "hcm" in lowered or "hồ chí minh" in lowered:
        district = _HCM_DISTRICT.search(address)
        if district:
            return find_area(f"hcm-quan-{district.group(1)}")
        for needle, area_id in _NAMED_HCM:
            if needle in lowered:
                return find_area(area_id)
    return None


def area_summary(area: Area) -> dict[str, Any]:
    """The wire shape of an area: id, label, and the centroid it was measured from.

    The centroid ships because every distance in a meeting-point answer is
    computed from it. A fairness number whose basis is not disclosed cannot be
    argued with, which is the same rule `GroupSummary` follows for match scores.
    """

    return {
        "id": area["id"],
        "label": area["label"],
        "lat": area["lat"],
        "lng": area["lng"],
    }
