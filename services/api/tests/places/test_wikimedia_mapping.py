"""What Commons has to say before a photograph may be shown (M12, ADR-0017).

Pure mapping, no network. The rule under test is refusal-by-default: a file
that cannot name its licence, its author and its source page is skipped, and
nothing is ever filled in with «Unknown» -- a placeholder in an attribution
field looks like attribution and satisfies nobody's licence terms.
"""

from __future__ import annotations

from app.places.wikimedia import (
    GIAY_PHEP_CHO_PHEP,
    anh_tu_imageinfo,
    giay_phep,
    truy_van_gan_diem,
)


def _file(**overrides):
    meta = {
        "LicenseShortName": {"value": "CC BY-SA 4.0"},
        "Artist": {"value": "Nguyễn A"},
        "ObjectName": {"value": "Hồ Xuân Hương"},
    }
    meta.update(overrides.pop("meta", {}))
    info = {
        "thumburl": "https://upload.wikimedia.org/x.jpg",
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:X",
        "thumbwidth": 1024,
        "thumbheight": 768,
        "extmetadata": meta,
    }
    info.update(overrides)
    return {"query": {"pages": {"1": {"title": "File:X.jpg", "imageinfo": [info]}}}}


def test_a_file_with_all_four_facts_is_usable():
    rows = anh_tu_imageinfo(_file())
    assert len(rows) == 1
    row = rows[0]
    assert row["license"] == "CC BY-SA 4.0"
    assert row["author"] == "Nguyễn A"
    assert row["source_url"].startswith("https://commons.wikimedia.org/")
    assert row["width"] == 1024


def test_no_licence_means_no_photograph():
    assert anh_tu_imageinfo(_file(meta={"LicenseShortName": None})) == []


def test_a_licence_outside_the_allowlist_is_refused():
    """Deny by default. A licence nobody has read is not a licence this
    product may publish under, however plausible its name looks."""

    for ten in ("Fair use", "All rights reserved", "CC BY-NC 4.0"):
        assert giay_phep(ten) is None, ten
        assert anh_tu_imageinfo(_file(meta={"LicenseShortName": {"value": ten}})) == []


def test_no_author_means_no_photograph():
    """«Unknown» would be worse than the missing picture: it is a claim about
    attribution that attributes nothing."""

    assert anh_tu_imageinfo(_file(meta={"Artist": {"value": "   "}})) == []


def test_no_source_page_means_no_photograph():
    assert anh_tu_imageinfo(_file(descriptionurl=None)) == []


def test_the_author_reaches_the_screen_as_text_not_as_markup():
    """Commons authors are HTML fragments. This string ends up under a picture
    in a mobile app, and the one thing it must not carry is somebody's markup."""

    rows = anh_tu_imageinfo(
        _file(meta={"Artist": {"value": '<a href="/wiki/User:B">Trần&nbsp;B</a>'}})
    )
    assert rows[0]["author"] == "Trần B"
    assert "<" not in rows[0]["author"]


def test_the_author_is_bounded():
    rows = anh_tu_imageinfo(_file(meta={"Artist": {"value": "Tên " * 200}}))
    assert len(rows[0]["author"]) <= 120


def test_licence_spelling_variants_resolve_to_one_string():
    """Commons writes one licence several ways. The card prints one."""

    assert giay_phep("cc by-sa 4.0") == "CC BY-SA 4.0"
    assert giay_phep("CC_BY_SA_4.0") == "CC BY-SA 4.0"
    assert giay_phep("CC0") == "CC0"


def test_every_allowlisted_licence_names_a_version_or_is_public_domain():
    """«CC BY» without a version is not a licence: the version is part of the
    terms, and this string is what gets printed under the picture."""

    for key, nhan in GIAY_PHEP_CHO_PHEP.items():
        assert key.strip() == key.strip().lower()
        assert nhan.strip()
        if nhan.startswith("CC BY"):
            assert any(char.isdigit() for char in nhan), nhan


def test_an_empty_answer_is_an_empty_list_not_a_crash():
    assert anh_tu_imageinfo(None) == []
    assert anh_tu_imageinfo({}) == []
    assert anh_tu_imageinfo({"query": {"pages": []}}) == []


def test_the_query_sends_a_place_and_nothing_else():
    """Coordinates of a PLACE, already published in OpenStreetMap. No user
    data leaves in this string -- there is nowhere in it for any."""

    q = truy_van_gan_diem(11.94, 108.44, 250, 6)
    assert "ggscoord=11.94%7C108.44" in q
    assert "action=query" in q and "generator=geosearch" in q
    assert "iiprop=url%7Cextmetadata" in q


def test_the_radius_and_the_count_are_bounded():
    q = truy_van_gan_diem(11.9, 108.4, 999_999, 999)
    assert "ggsradius=10000" in q
    assert "ggslimit=50" in q
