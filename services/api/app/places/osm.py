"""Turn OpenStreetMap elements into catalogue rows (M9, ADR-0017).

Pure: tags in, row dict out. No network, no session, no clock. The importer
script does the talking to Overpass and the writing to the table; everything
that decides *what a place is* lives here, where a test can ask it directly.

The mapping is deliberately narrow. OSM has thousands of tags and this product
has four categories; anything that does not map cleanly is dropped rather than
filed under a category it half fits. A catalogue with fewer, right rows beats
one with a laundromat under «Vui chơi».

What is NOT derived here, and why: price, rating and «open now». OSM carries
none of the three. `opening_hours` is carried through verbatim as text because
its syntax («Mo-Fr 08:00-22:00; Sa off») is a spec of its own, and a half-right
parser would produce a confident, wrong «Đang mở».
"""

from __future__ import annotations

from typing import Any

from app.places.prompt_safety import place_is_safe_for_prompt

CATEGORY_BY_TAG: dict[tuple[str, str], str] = {
    ("amenity", "restaurant"): "quan-an-local",
    ("amenity", "fast_food"): "quan-an-local",
    ("amenity", "food_court"): "quan-an-local",
    ("amenity", "cafe"): "cafe",
    ("amenity", "ice_cream"): "cafe",
    ("amenity", "bar"): "di-choi-dem",
    ("amenity", "pub"): "di-choi-dem",
    ("amenity", "nightclub"): "di-choi-dem",
    ("amenity", "cinema"): "vui-choi",
    ("tourism", "attraction"): "vui-choi",
    ("tourism", "viewpoint"): "vui-choi",
    ("tourism", "museum"): "vui-choi",
    ("tourism", "theme_park"): "vui-choi",
    ("tourism", "artwork"): "vui-choi",
    ("leisure", "park"): "vui-choi",
    ("leisure", "garden"): "vui-choi",
    ("leisure", "water_park"): "vui-choi",
    ("leisure", "bowling_alley"): "vui-choi",
}

# Vietnamese labels for the handful of `cuisine` values that actually turn up
# around here. An unmapped cuisine keeps its own word rather than disappearing:
# «ramen» on a card is still information, and inventing a translation is worse.
CUISINE_LABELS: dict[str, str] = {
    "coffee_shop": "Cà phê",
    "vietnamese": "Việt",
    "noodle": "Mì · bún",
    "pho": "Phở",
    "bbq": "Nướng",
    "barbecue": "Nướng",
    "hotpot": "Lẩu",
    "seafood": "Hải sản",
    "vegetarian": "Chay",
    "japanese": "Nhật",
    "korean": "Hàn",
    "chinese": "Hoa",
    "thai": "Thái",
    "italian": "Ý",
    "pizza": "Pizza",
    "burger": "Burger",
    "ice_cream": "Kem",
    "bubble_tea": "Trà sữa",
    "tea": "Trà",
    "juice": "Nước ép",
    "breakfast": "Ăn sáng",
    "street_food": "Ăn vặt",
}

TRAIT_BY_TAG: list[tuple[str, tuple[str, ...], str]] = [
    ("outdoor_seating", ("yes",), "Ngoài trời"),
    ("internet_access", ("wlan", "yes", "terminal"), "Wifi"),
    ("air_conditioning", ("yes",), "Máy lạnh"),
    ("wheelchair", ("yes",), "Lối cho xe lăn"),
    ("takeaway", ("yes", "only"), "Mang về"),
    ("smoking", ("no",), "Không khói thuốc"),
    ("live_music", ("yes",), "Nhạc sống"),
]


def category_for(tags: dict[str, str]) -> str | None:
    """The one category this element belongs in, or None to skip it."""
    for key, value in tags.items():
        found = CATEGORY_BY_TAG.get((key, value))
        if found is not None:
            return found
    return None


def kinds_for(tags: dict[str, str]) -> list[str]:
    """Short words under the name: cuisine first, then what it is."""
    out: list[str] = []
    cuisine = tags.get("cuisine", "")
    for raw in cuisine.split(";"):
        word = raw.strip().lower()
        if not word:
            continue
        label = CUISINE_LABELS.get(word)
        if label is None:
            label = word.replace("_", " ").capitalize()
        if label not in out:
            out.append(label)
    if not out:
        for key in ("amenity", "tourism", "leisure"):
            value = tags.get(key)
            if value:
                out.append(value.replace("_", " ").capitalize())
                break
    return out[:4]


def traits_for(tags: dict[str, str]) -> list[str]:
    """Facts a tag states outright. Nothing inferred, nothing atmospheric."""
    return [
        label
        for key, values, label in TRAIT_BY_TAG
        if tags.get(key, "").strip().lower() in values
    ]


def address_for(tags: dict[str, str], fallback_city: str | None = None) -> str | None:
    """A street address from `addr:*`, or None. Partial is fine; empty is not.

    A house number with no street is dropped: «27» is not an address, and a
    card that prints it looks like the app lost the rest.
    """
    street = tags.get("addr:street", "").strip()
    number = tags.get("addr:housenumber", "").strip()
    ward = tags.get("addr:subdistrict", "").strip() or tags.get("addr:ward", "").strip()
    district = (
        tags.get("addr:district", "").strip() or tags.get("addr:suburb", "").strip()
    )
    city = tags.get("addr:city", "").strip() or (fallback_city or "").strip()

    if not street:
        parts = [p for p in (ward, district, city) if p]
        return ", ".join(parts) if parts else None

    head = f"{number} {street}".strip() if number else street
    parts = [head, *[p for p in (ward, district, city) if p]]
    return ", ".join(parts)


# Names that are the category word and nothing else. OpenStreetMap has plenty
# of these -- a mapper who knew there was a cafe there but not what it is
# called. «Café» on a card is not a place a person can choose between, so the
# row is skipped rather than shown as one of twenty-five identical entries.
GENERIC_NAMES = {
    "cafe",
    "café",
    "coffee",
    "restaurant",
    "nha hang",
    "nhà hàng",
    "quan an",
    "quán ăn",
    "quan cafe",
    "quán cafe",
    "quan ca phe",
    "quán cà phê",
    "ca phe",
    "cà phê",
    "bar",
    "pub",
    "hotel",
    "khach san",
    "khách sạn",
    "cafe restaurant",
    "café restaurant",
    "restaurant cafe",
}


def name_for(tags: dict[str, str]) -> str | None:
    """The Vietnamese name if the element carries one, else its plain name.

    `None` when the only name is the category word: «Café» tells a reader
    nothing they did not already know from the filter they just tapped.
    """
    for key in ("name:vi", "name"):
        value = tags.get(key, "").strip()
        if value and value.casefold() not in GENERIC_NAMES:
            return value
    return None


def row_from_element(
    element: dict[str, Any], *, destination_id: str, fallback_city: str | None = None
) -> dict[str, Any] | None:
    """One Overpass element to one `places` row, or None if it does not qualify.

    Skipped: anything unnamed, anything without coordinates, anything whose
    tags do not map to one of the four categories. Every skip is a row this
    product would not have been able to describe honestly.
    """
    tags = {
        str(k): str(v) for k, v in (element.get("tags") or {}).items() if v is not None
    }
    name = name_for(tags)
    category = category_for(tags)
    if name is None or category is None:
        return None

    lat = element.get("lat", (element.get("center") or {}).get("lat"))
    lng = element.get("lon", (element.get("center") or {}).get("lon"))
    if not isinstance(lat, int | float) or not isinstance(lng, int | float):
        return None

    kind = str(element.get("type", "node"))
    ident = element.get("id")
    if ident is None:
        return None
    source_ref = f"{kind}/{ident}"

    return {
        "id": f"osm-{kind}-{ident}",
        "destination_id": destination_id,
        "name": name,
        "category": category,
        "kinds": kinds_for(tags),
        "address": address_for(tags, fallback_city),
        "lat": float(lat),
        "lng": float(lng),
        "rating": None,
        "rating_count": None,
        "price_min_vnd": None,
        "price_max_vnd": None,
        "open_hours": tags.get("opening_hours") or None,
        "open_now": None,
        "travel_minutes": None,
        "distance_km": None,
        "photo_count": 0,
        "traits": traits_for(tags),
        "group_fit": None,
        "flag": None,
        "description": None,
        "reviews": None,
        "source": "osm",
        "source_ref": source_ref,
        "license": "ODbL-1.0",
    }


def rows_from_payload(
    payload: dict[str, Any],
    *,
    destination_id: str,
    fallback_city: str | None = None,
    limit_per_category: int | None = None,
) -> list[dict[str, Any]]:
    """Every qualifying element, deduped by id, optionally capped per category.

    The cap keeps a catalogue curated rather than exhaustive: a city with 400
    cafes does not make a better screen than one with 40, and the reader is
    choosing a place to go, not auditing a map.
    """
    seen: set[str] = set()
    per_category: dict[str, int] = {}
    out: list[dict[str, Any]] = []
    for element in payload.get("elements", []):
        row = row_from_element(
            element, destination_id=destination_id, fallback_city=fallback_city
        )
        if row is None or row["id"] in seen:
            continue
        # A venue name on OpenStreetMap is text anybody in the world can write,
        # and this catalogue is quoted to a model. Rows that talk to the model
        # are refused at the door as well as at the prompt (ADR-0017): the
        # prompt filter is the guarantee, this is the hygiene.
        if not place_is_safe_for_prompt(row):
            continue
        category = row["category"]
        if (
            limit_per_category is not None
            and per_category.get(category, 0) >= limit_per_category
        ):
            continue
        seen.add(row["id"])
        per_category[category] = per_category.get(category, 0) + 1
        out.append(row)
    return out


OVERPASS_TAG_FILTERS: tuple[tuple[str, str], ...] = (
    (
        "amenity",
        "restaurant|fast_food|food_court|cafe|ice_cream|bar|pub|nightclub|cinema",
    ),
    ("tourism", "attraction|viewpoint|museum|theme_park|artwork"),
    ("leisure", "park|garden|water_park|bowling_alley"),
)


def overpass_query(
    *, south: float, west: float, north: float, east: float, timeout_s: int = 60
) -> str:
    """The Overpass QL for one destination box.

    Only named elements: a row without a name is a row no screen can draw.
    `nwr` rather than `node` because a restaurant in a building is tagged on the
    way; `out center` gives those a point without shipping their geometry.
    """
    box = f"{south},{west},{north},{east}"
    parts = "".join(
        f'nwr["{key}"~"^({values})$"]["name"]({box});'
        for key, values in OVERPASS_TAG_FILTERS
    )
    return f"[out:json][timeout:{timeout_s}];({parts});out center tags;"
