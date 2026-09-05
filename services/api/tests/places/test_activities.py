"""«Nên làm gì ở đây» is read off tags, never written about a place (M12).

The rule under test is that every phrase traces to a tag. The failure it exists
to prevent is the fluent one: a model handed a name and a category writes
«hải sản tươi ngon, không gian ấm cúng» for a row whose tags say neither, and
nothing on the screen tells the reader which words came from the map.
"""

from __future__ import annotations

from app.places.activities import (
    HOAT_DONG_THEO_MON,
    HOAT_DONG_THEO_TAG,
    TOI_DA,
    doc_hoat_dong,
    hoat_dong_theo_tag,
)


def test_a_tag_this_table_knows_becomes_the_words_a_person_uses():
    assert hoat_dong_theo_tag({"leisure": "park"}) == ["Đi dạo"]
    assert hoat_dong_theo_tag({"tourism": "viewpoint"}) == ["Ngắm cảnh"]
    assert hoat_dong_theo_tag({"amenity": "cinema"}) == ["Xem phim"]


def test_tags_a_place_actually_carries_stack_up():
    out = hoat_dong_theo_tag(
        {"amenity": "cafe", "outdoor_seating": "yes", "internet_access": "wlan"}
    )
    assert out == ["Ngồi cà phê", "Ngồi ngoài trời", "Ngồi làm việc"]


def test_the_cuisine_tag_says_what_somebody_eats():
    assert hoat_dong_theo_tag({"cuisine": "bbq"}) == ["Ăn nướng"]
    assert hoat_dong_theo_tag({"cuisine": "seafood;hotpot"}) == [
        "Ăn hải sản",
        "Ăn lẩu",
    ]


def test_a_place_the_map_says_nothing_about_gets_no_phrases():
    """Empty is the answer. «Ghé chơi» for a place nobody described would be
    filler that reads exactly like a fact."""

    assert hoat_dong_theo_tag({}) == []
    assert hoat_dong_theo_tag({"name": "Quán A", "addr:street": "Yersin"}) == []
    assert hoat_dong_theo_tag({"amenity": "atm"}) == []


def test_one_phrase_twice_is_one_phrase():
    """A cafe whose cuisine is `coffee_shop` says «ngồi cà phê» twice on the
    map and once on the card."""

    assert hoat_dong_theo_tag({"amenity": "cafe", "cuisine": "coffee_shop"}) == [
        "Ngồi cà phê"
    ]


def test_the_list_is_capped_and_the_cap_is_visible():
    tags = {
        "amenity": "restaurant",
        "outdoor_seating": "yes",
        "internet_access": "yes",
        "takeaway": "yes",
        "live_music": "yes",
        "cuisine": "bbq;hotpot;seafood",
    }
    assert len(hoat_dong_theo_tag(tags)) == TOI_DA


def test_the_order_is_the_tables_not_the_dicts():
    """Two rows with the same tags must produce the same line, whatever order
    the importer happened to read them in."""

    xuoi = {"amenity": "cafe", "outdoor_seating": "yes"}
    nguoc = {"outdoor_seating": "yes", "amenity": "cafe"}
    assert hoat_dong_theo_tag(xuoi) == hoat_dong_theo_tag(nguoc)


def test_a_stored_value_this_build_does_not_know_is_dropped():
    """The column may have been written by a newer importer. A phrase this
    build cannot vouch for is not shown -- and never printed as a raw value."""

    assert doc_hoat_dong(["Đi dạo", "Bay dù lượn"]) == ["Đi dạo"]
    assert doc_hoat_dong(None) == []
    assert doc_hoat_dong("Đi dạo") == []
    assert doc_hoat_dong([1, 2, 3]) == []


def test_every_phrase_in_the_table_is_something_a_person_does():
    """No adjectives, no atmosphere, no claim about quality: those are the
    words a model invents, and none of them is in a tag."""

    cam = ("ngon", "tuyệt", "đẹp nhất", "nổi tiếng", "ấm cúng", "sang")
    for _, _, cau in HOAT_DONG_THEO_TAG:
        assert cau.strip() == cau and cau
        assert not any(tu in cau.lower() for tu in cam), cau
    for cau in HOAT_DONG_THEO_MON.values():
        assert not any(tu in cau.lower() for tu in cam), cau
