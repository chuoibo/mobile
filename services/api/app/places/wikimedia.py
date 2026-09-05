"""What a Wikimedia Commons answer has to say before a photograph may be used.

Pure mapping, like `osm.py` beside it: a payload in, rows out, no network and
no database. The script that does talk to Commons is
`scripts/import_place_photos.py`, and `tests/test_only_the_importer_talks_out.py`
keeps every request-serving module out of that conversation.

## The rule this file exists to enforce

ADR-0017 allows a photograph of a real place exactly when it can say where it
came from. Commons is a good source because it answers that question in the
payload -- `extmetadata` carries the licence, the author and the file's own
description page. It is also a source that *sometimes does not*: a file can be
uploaded with no licence template, a broken one, or one of the several
non-free tags Commons tolerates for fair-use material.

So the default here is refusal. A file whose licence is not in
`GIAY_PHEP_CHO_PHEP`, or whose author or source page cannot be read, is
skipped and counted -- never imported with a placeholder like «Unknown». An
«Unknown» in an attribution field is worse than no photograph: it looks like
attribution and satisfies nobody's licence terms.

## Why the licence list is a closed allowlist and not a blocklist

The failure a blocklist has is silent: a licence nobody thought of arrives, is
not on the list of bad ones, and a picture ships under terms nobody read. The
failure an allowlist has is loud and cheap -- a photograph is missing, somebody
adds the licence after reading it, and the next import picks the file up.
"""

from __future__ import annotations

import html
import re
from typing import Any

#: Licences that let this product show the photograph with attribution.
#: Written out in full because «CC BY» is not a licence -- a version is part of
#: the terms, and the string is what gets printed under the picture.
GIAY_PHEP_CHO_PHEP: dict[str, str] = {
    "cc0": "CC0",
    "cc-zero": "CC0",
    "public domain": "Phạm vi công cộng",
    "pd": "Phạm vi công cộng",
    "cc-by-2.0": "CC BY 2.0",
    "cc-by-2.5": "CC BY 2.5",
    "cc-by-3.0": "CC BY 3.0",
    "cc-by-4.0": "CC BY 4.0",
    "cc-by-sa-2.0": "CC BY-SA 2.0",
    "cc-by-sa-2.5": "CC BY-SA 2.5",
    "cc-by-sa-3.0": "CC BY-SA 3.0",
    "cc-by-sa-4.0": "CC BY-SA 4.0",
}

#: Longest author string kept. Commons authors are sometimes a paragraph of
#: HTML; the card shows a name, and nothing downstream should be able to grow a
#: response by editing a wiki page.
MAX_AUTHOR = 120

_THE_TAG = re.compile(r"<[^>]+>")


def _plain(value: Any) -> str:
    """Commons returns small HTML fragments. The screen prints text.

    Tags are stripped rather than rendered: this string ends up under a
    photograph in a mobile app, and the one thing it must not carry is markup
    somebody put on a wiki page.
    """

    if not isinstance(value, str):
        return ""
    text = html.unescape(_THE_TAG.sub(" ", value))
    return " ".join(text.split()).strip()


def giay_phep(raw: Any) -> str | None:
    """The licence as this product prints it, or None to refuse the file."""

    key = _plain(raw).lower()
    if not key:
        return None
    if key in GIAY_PHEP_CHO_PHEP:
        return GIAY_PHEP_CHO_PHEP[key]
    # Commons writes the same licence several ways («CC BY-SA 4.0», «cc by sa
    # 4.0»). Normalising the separators catches those without loosening the
    # list: an unknown licence is still an unknown licence.
    gon = key.replace(" ", "-").replace("_", "-")
    return GIAY_PHEP_CHO_PHEP.get(gon)


def _meta(meta: dict[str, Any], name: str) -> Any:
    """One `extmetadata` field's value, or None. Module-level rather than a
    closure so it does not capture the loop variable it reads."""

    row = meta.get(name)
    return row.get("value") if isinstance(row, dict) else None


def anh_tu_imageinfo(payload: Any) -> list[dict[str, Any]]:
    """Every usable photograph in an `imageinfo` answer, in the order given.

    A file contributes a row only when all four of these are readable: the
    image URL, a licence on the allowlist, an author, and the description page
    that stands as the source. Anything else is skipped -- the caller counts
    the skips, because «Commons had nothing for this place» and «Commons had
    six pictures and none of them said who took them» are different facts.
    """

    pages = ((payload or {}).get("query") or {}).get("pages") or {}
    if isinstance(pages, dict):
        danh_sach = list(pages.values())
    elif isinstance(pages, list):
        danh_sach = pages
    else:
        return []

    out: list[dict[str, Any]] = []
    for page in danh_sach:
        if not isinstance(page, dict):
            continue
        infos = page.get("imageinfo") or []
        if not infos or not isinstance(infos[0], dict):
            continue
        info = infos[0]
        meta = info.get("extmetadata") or {}
        if not isinstance(meta, dict):
            continue

        phep = giay_phep(_meta(meta, "LicenseShortName")) or giay_phep(
            _meta(meta, "License")
        )
        tac_gia = _plain(_meta(meta, "Artist"))[:MAX_AUTHOR]
        nguon = info.get("descriptionurl")
        url = info.get("thumburl") or info.get("url")
        if not (phep and tac_gia and isinstance(nguon, str) and isinstance(url, str)):
            continue
        out.append(
            {
                "url": url,
                "license": phep,
                "author": tac_gia,
                "source_url": nguon,
                "title": _plain(_meta(meta, "ObjectName"))
                or _plain(page.get("title"))
                or None,
                "width": info.get("thumbwidth") or info.get("width"),
                "height": info.get("thumbheight") or info.get("height"),
            }
        )
    return out


def truy_van_gan_diem(lat: float, lng: float, ban_kinh_m: int, so_luong: int) -> str:
    """The Commons query string for «pictures taken near this point».

    Coordinates of a PLACE, never of a person: this runs in an import script
    over catalogue rows, and the only positions it sends are the ones already
    published in OpenStreetMap.
    """

    from urllib.parse import urlencode

    return urlencode(
        {
            "action": "query",
            "format": "json",
            "generator": "geosearch",
            "ggscoord": f"{lat}|{lng}",
            "ggsradius": str(max(10, min(ban_kinh_m, 10_000))),
            "ggslimit": str(max(1, min(so_luong, 50))),
            "ggsnamespace": "6",
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "iiurlwidth": "1024",
        }
    )
