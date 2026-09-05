"""«Nên làm gì ở đây», derived from tags at import time (M12, ADR-0017 §2.3).

## Why this is a lookup table and not a model call

The screen wants a line under the name that says what a person actually does at
this place. There are two ways to get one: read the tags the place already
carries, or ask a model to write a sentence about a venue it has never been to.

The second is how a catalogue starts describing places it does not know. A
model handed «Quán Ốc Dì Bé, quan-an-local» will produce «hải sản tươi ngon,
không gian ấm cúng» for a row whose tags say neither -- fluent, plausible, and
about nowhere. Every word below traces to a tag somebody wrote on the map.

## And why it happens at IMPORT, not when a screen opens

A phrase computed per request is a phrase that can change between two renders
of the same place, and a cost paid on every read for an answer that only
changes when the map does. Import writes it once; the row carries it.

## The vocabulary is closed and the mapping is one-way

`HOAT_DONG_THEO_TAG` is read left to right: a tag this table does not name
contributes nothing. There is deliberately no fallback phrase -- «Ghé chơi» for
a place nobody described would be filler that reads exactly like a fact, and a
place with no activities shows none rather than a sentence about nothing.
"""

from __future__ import annotations

from typing import Any

#: `(tag, giá trị) -> việc người ta làm ở đó`. Every phrase is what the tag
#: says, in the words a person would use, and nothing more.
HOAT_DONG_THEO_TAG: list[tuple[str, tuple[str, ...], str]] = [
    ("amenity", ("cafe",), "Ngồi cà phê"),
    ("amenity", ("restaurant", "food_court"), "Ăn một bữa"),
    ("amenity", ("fast_food",), "Ăn nhanh"),
    ("amenity", ("bar", "pub"), "Uống một ly"),
    ("amenity", ("nightclub",), "Đi bar khuya"),
    ("amenity", ("ice_cream",), "Ăn kem"),
    ("amenity", ("cinema",), "Xem phim"),
    ("leisure", ("park", "garden"), "Đi dạo"),
    ("leisure", ("water_park",), "Chơi nước"),
    ("leisure", ("bowling_alley",), "Chơi bowling"),
    ("tourism", ("viewpoint",), "Ngắm cảnh"),
    ("tourism", ("museum",), "Xem trưng bày"),
    ("tourism", ("artwork",), "Xem tác phẩm"),
    ("tourism", ("attraction", "theme_park"), "Chơi cả buổi"),
    ("outdoor_seating", ("yes",), "Ngồi ngoài trời"),
    ("live_music", ("yes",), "Nghe nhạc sống"),
    ("internet_access", ("wlan", "yes", "terminal"), "Ngồi làm việc"),
    ("takeaway", ("yes", "only"), "Mua mang về"),
]

#: Cuisine values that say what somebody eats there. Same table shape, read
#: from the semicolon-separated `cuisine` tag.
HOAT_DONG_THEO_MON: dict[str, str] = {
    "bbq": "Ăn nướng",
    "barbecue": "Ăn nướng",
    "hotpot": "Ăn lẩu",
    "seafood": "Ăn hải sản",
    "coffee_shop": "Ngồi cà phê",
    "bubble_tea": "Uống trà sữa",
    "ice_cream": "Ăn kem",
    "vegetarian": "Ăn chay",
    "breakfast": "Ăn sáng",
    "street_food": "Ăn vặt",
}

#: How many phrases a card may carry. The list is a hint, not an inventory.
TOI_DA = 4


def hoat_dong_theo_tag(tags: dict[str, str]) -> list[str]:
    """What a person does at a place with these tags, in table order.

    Deduplicated, capped, and empty when the tags say nothing this table knows.
    Empty is a real answer: the screen shows no line rather than a sentence
    that could be about any place at all.
    """

    out: list[str] = []

    def them(cau: str) -> None:
        if cau not in out:
            out.append(cau)

    for key, values, cau in HOAT_DONG_THEO_TAG:
        if tags.get(key, "").strip().lower() in values:
            them(cau)

    for raw in (tags.get("cuisine") or "").split(";"):
        cau = HOAT_DONG_THEO_MON.get(raw.strip().lower())
        if cau:
            them(cau)

    return out[:TOI_DA]


#: The seed rows carry no OpenStreetMap tags -- they were written by hand
#: before the catalogue was a table. What they do carry is a category, a few
#: `kinds` and a few `traits`, which are the same facts under other names.
HOAT_DONG_THEO_DANH_MUC: dict[str, str] = {
    "quan-an-local": "Ăn một bữa",
    "cafe": "Ngồi cà phê",
    "di-choi-dem": "Uống một ly",
    "vui-choi": "Chơi cả buổi",
}

#: Words the seed file uses for the same things the tags say.
HOAT_DONG_THEO_TU: dict[str, str] = {
    "bbq": "Ăn nướng",
    "nướng": "Ăn nướng",
    "đồ nướng": "Ăn nướng",
    "lẩu": "Ăn lẩu",
    "hải sản": "Ăn hải sản",
    "ngoài trời": "Ngồi ngoài trời",
    "nhạc sống": "Nghe nhạc sống",
    "view đẹp": "Ngắm cảnh",
    "bowling": "Chơi bowling",
}


def hoat_dong_theo_dong(row: dict[str, Any]) -> list[str]:
    """The same phrases for a row that has no tags -- the seed catalogue.

    Reads the row's own category, kinds and traits and nothing else. Same rule
    as `hoat_dong_theo_tag`, applied to the vocabulary the seed file happens to
    be written in: no phrase appears that the row does not already say in some
    other column.
    """

    out: list[str] = []

    def them(cau: str) -> None:
        if cau not in out:
            out.append(cau)

    tu_danh_muc = HOAT_DONG_THEO_DANH_MUC.get(str(row.get("category") or ""))
    if tu_danh_muc:
        them(tu_danh_muc)
    for tu in [*(row.get("kinds") or []), *(row.get("traits") or [])]:
        cau = HOAT_DONG_THEO_TU.get(str(tu).strip().lower())
        if cau:
            them(cau)
    return out[:TOI_DA]


def doc_hoat_dong(value: Any) -> list[str]:
    """The stored column, read defensively.

    A row written before this column existed carries NULL, and a row written by
    a future importer may carry a word this build does not know. Both are «no
    activities» rather than a crash or an id printed on a card.
    """

    if not isinstance(value, list):
        return []
    biet = (
        {cau for _, _, cau in HOAT_DONG_THEO_TAG}
        | set(HOAT_DONG_THEO_MON.values())
        | set(HOAT_DONG_THEO_DANH_MUC.values())
        | set(HOAT_DONG_THEO_TU.values())
    )
    return [item for item in value if isinstance(item, str) and item in biet][:TOI_DA]
