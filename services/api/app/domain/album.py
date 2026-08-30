"""F36 -- the trip album: one way of reading rows that already exist.

## The album copies nothing

No table, no blob, no second URL. An album entry carries the *same*
`/contexts/{id}/photos/{id}` path the memory wall serves, so the bytes still
travel the one route that gates them. Had the album minted its own media path
it would have become a second door to the same photographs, and the second door
is always the one nobody remembers to lock.

That also fixes what "read an album" is allowed to mean: exactly what "read the
wall" means, because it is the same rows. The service proves ACTIVE membership
of the context in the path *before* it looks the outing up, and the repository
joins memories on the outing's own `context_id`, so an album can only ever be
assembled out of its own group's rows -- there is no id a caller could pass
that makes a foreign photograph appear inside one.

## What is derived, and what is a shell

Derived, from rows, on the request that asks: the photographs, the places, the
money, every count. `split_total_vnd` is the recap's figure, summed from
confirmed allocations -- invariant 3, never a stored total, so an album and the
recap screen cannot print two different numbers for one trip.

**A shell, and stated as one:** the spec's "AI tạo `Đà Lạt 2026`" is not here.
The title is the outing's own title with the trip's year appended, computed by
this function. Nothing generates it. A model-written album name is a plausible
sentence sitting on top of a set of real photographs, and there is no way for a
reader to tell which parts of the screen were derived and which were composed;
`period_label` is separate from `title` so a client can render the two without
the server having pretended one was the other.

`highlights` is likewise not a model's opinion. It is the rows this group
reacted to most -- their judgement, counted, not a machine's guess at it.
"""

from __future__ import annotations

from datetime import date
from typing import Any

#: Photographs listed in one album. An album is a screen, not an export.
MAX_PHOTOS = 60

#: Distinct places named. Reported alongside `place_count` so a trip that
#: visited more than this many does not read as though it visited this many.
MAX_PLACES = 20

#: Rows offered as highlights.
MAX_HIGHLIGHTS = 6

#: A memory needs at least this many hearts to be a highlight. Zero-heart rows
#: are never highlights: with no threshold, an album where nobody reacted would
#: promote its six newest photographs and call the group's silence a verdict.
MIN_HIGHLIGHT_REACTIONS = 1


class AlbumError(Exception):
    """Malformed rows reached the album builder."""


def _text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:limit]


def period_label(starts_on: date, ends_on: date) -> str:
    """`2026`, or `2025–2026` for a trip that crossed midnight on 31 December.

    Two years get both. A new-year trip filed under its start year is a small
    lie that only appears once a year, which is exactly how long it survives
    without anybody noticing.
    """

    if not isinstance(starts_on, date) or not isinstance(ends_on, date):
        raise AlbumError("album_dates_malformed")
    if ends_on.year != starts_on.year:
        return f"{starts_on.year}–{ends_on.year}"
    return str(starts_on.year)


def build_album(outing: dict, memories: list[dict]) -> dict:
    """One trip's album, assembled from the trip row and its own memories.

    `outing` is a recap row -- title, dates, headcount and the ledger-summed
    `split_total_vnd`. `memories` are the memories that fall inside the trip's
    days, newest first, already scoped to the trip's context by the caller.

    The photograph list keeps `image_url` verbatim. Rewriting it here, even
    into an identical-looking string, would make this function a second author
    of media paths and the album's URLs would drift from the wall's the first
    time one of the two was edited.
    """

    if not isinstance(outing, dict):
        raise AlbumError("album_outing_malformed")

    starts_on = outing.get("starts_on")
    ends_on = outing.get("ends_on")
    title = _text(outing.get("title"), 240) or "Chuyến đi"

    photos: list[dict] = []
    places: list[dict] = []
    seen_places: set[str] = set()
    checkin_count = 0
    reacted: list[tuple[int, dict]] = []

    for memory in memories:
        if not isinstance(memory, dict):
            raise AlbumError("album_memory_malformed")
        kind = memory.get("kind")
        if kind == "photo":
            image_url = memory.get("image_url")
            if isinstance(image_url, str) and image_url:
                entry = {
                    "memory_id": memory.get("id"),
                    "image_url": image_url,
                    "caption": _text(memory.get("caption"), 240),
                    "created_at": memory.get("created_at"),
                    "reaction_count": memory.get("reaction_count", 0),
                    "comment_count": memory.get("comment_count", 0),
                }
                photos.append(entry)
                hearts = entry["reaction_count"]
                if isinstance(hearts, int) and hearts >= MIN_HIGHLIGHT_REACTIONS:
                    reacted.append((hearts, entry))
        elif kind == "checkin":
            checkin_count += 1
            place_id = memory.get("place_id")
            if isinstance(place_id, str) and place_id not in seen_places:
                seen_places.add(place_id)
                places.append(
                    {
                        "place_id": place_id,
                        "place_name": _text(memory.get("place_name"), 240),
                    }
                )

    # Hearts descending, then newest first. `created_at` is only a tiebreak, so
    # a row nobody reacted to can never overtake one they did.
    reacted.sort(key=lambda row: (-row[0], _sort_key(row[1].get("created_at"))))

    return {
        "title": title,
        "period_label": period_label(starts_on, ends_on),
        "starts_on": starts_on,
        "ends_on": ends_on,
        "photos": photos[:MAX_PHOTOS],
        "photo_count": len(photos),
        "places": places[:MAX_PLACES],
        "place_count": len(places),
        "checkin_count": checkin_count,
        "highlights": [entry for _, entry in reacted[:MAX_HIGHLIGHTS]],
        "split_total_vnd": outing.get("split_total_vnd", 0),
        "expense_count": outing.get("expense_count", 0),
        "headcount": outing.get("headcount", 0),
    }


def _sort_key(created_at: Any) -> float:
    """Newest first, without letting a missing timestamp raise mid-sort."""

    try:
        return -created_at.timestamp()
    except AttributeError:
        return 0.0
