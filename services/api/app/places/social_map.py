"""F43 and F44: what a group's own check-ins add up to, and nothing more.

Both features read one source -- the check-in rows of the group's memory wall
-- and both are strictly *narrower* than the wall the caller could already
read. That is the whole safety argument, so it is worth stating precisely.

## The audience never widens, and the detail only shrinks

A check-in row carries `author_id` and `created_at`. `GET /contexts/{id}/memories`
already shows both to anybody who passes `view_group_memories`, so a member can
already see who checked in where and when. These two features are gated on the
same ACTIVE membership and answer with *less*: a place with a count, or a
district with a count. No author. No timestamp.

That is what makes "the heatmap must not let you infer who was where at what
time" true by construction rather than by care. The functions below build their
output dicts key by key from a fixed list; an author id cannot reach a caller
through here because there is no line that would put it there. `test_social_map`
feeds rows carrying both private fields and asserts neither appears anywhere in
the serialised answer -- which is a test of this module, not of the caller's
manners.

## Counts, not a stored total

Every number here is recomputed from the rows on the request that asks. There is
no `visit_count` column, for the same reason invariant 3 keeps balances out of
cache: a count that is stored is a count that starts disagreeing with the rows
it claims to summarise, and nobody notices until two screens disagree.
"""

from __future__ import annotations

from typing import Any

from app.places.areas import Area, area_summary, nearest_area

__all__ = [
    "heatmap_rows",
    "trending_layer",
    "unknown_area_count",
    "visited_layer",
]

#: The fields a check-in row carries that must never reach a map or heatmap
#: answer. Named here so the gate that proves it can import the list rather
#: than restate it -- a second copy of this tuple is a second thing to forget.
#:
#: The memory row's own `id` is not listed, and not by oversight: an opaque
#: uuid discloses nothing on its own, and putting the bare string "id" in a
#: substring check would match `place_id` and `area["id"]` and make the whole
#: assertion fire on the answer's own legitimate fields. The tests pin the exact
#: key set of every returned row as well, which is the stronger statement.
PRIVATE_CHECKIN_FIELDS = ("author_id", "created_at", "caption")


def visited_layer(checkins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """"Places friends visited": one row per place, with how often.

    Takes the full check-in record deliberately, private fields and all, rather
    than a pre-narrowed shape. If the caller narrowed first, this function's
    tests would prove nothing about what actually ships -- the stripping has to
    happen where it can be tested, and this is that place.

    Ordered by visit count, then place id. Not by recency: recency is a
    timestamp wearing a sort order, and the ordering of a list is enough to
    recover roughly when something happened.
    """

    rolled: dict[str, dict[str, Any]] = {}
    for row in checkins:
        place_id = row.get("place_id")
        if not place_id or row.get("lat") is None or row.get("lng") is None:
            # A photo memory, or a check-in written before the shape
            # constraint. Neither is a visit with a location.
            continue
        entry = rolled.get(place_id)
        if entry is None:
            rolled[place_id] = {
                "place_id": place_id,
                "place_name": row.get("place_name") or place_id,
                "lat": float(row["lat"]),
                "lng": float(row["lng"]),
                "visit_count": 1,
            }
        else:
            entry["visit_count"] += 1
    return sorted(
        rolled.values(),
        key=lambda entry: (-entry["visit_count"], entry["place_id"]),
    )


def trending_layer(places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Catalogue rows the catalogue itself flags as busy.

    Derived from `flag == "hot"` and from nothing about the group, so this layer
    is identical for every caller. Said out loud because a "trending" list that
    silently mixed in the group's own history would be a second channel for the
    same private data, wearing a public-looking name.
    """

    return [
        {
            "place_id": place["id"],
            "place_name": place["name"],
            "lat": float(place["lat"]),
            "lng": float(place["lng"]),
            "rating": place["rating"],
            "rating_count": place["rating_count"],
        }
        for place in sorted(places, key=lambda place: place["id"])
        if place.get("flag") == "hot"
    ]


def _resolve(checkins: list[dict[str, Any]]) -> list[tuple[Area | None, dict]]:
    out: list[tuple[Area | None, dict]] = []
    for row in checkins:
        if row.get("lat") is None or row.get("lng") is None:
            continue
        out.append((nearest_area(float(row["lat"]), float(row["lng"])), row))
    return out


def heatmap_rows(checkins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """F44: "nhóm bạn hay tụ ở đâu", as districts and counts.

    The coarsening from coordinate to district is the feature, not a rendering
    convenience: a district plus a count cannot be walked back to a person or an
    evening, and a coordinate plus a timestamp can.

    `share_percent` is an integer percentage of the rows that *did* resolve to
    an area. It ships beside `visit_count` and the caller also gets the resolved
    total, so the arithmetic can be checked by hand rather than trusted.
    """

    rolled: dict[str, dict[str, Any]] = {}
    resolved_total = 0
    for area, _row in _resolve(checkins):
        if area is None:
            continue
        resolved_total += 1
        entry = rolled.get(area["id"])
        if entry is None:
            rolled[area["id"]] = {**area_summary(area), "visit_count": 1}
        else:
            entry["visit_count"] += 1

    rows = sorted(
        rolled.values(), key=lambda entry: (-entry["visit_count"], entry["id"])
    )
    for row in rows:
        # Integer division, not rounding: the shares are a rough shape of where
        # a group goes, and a rounded set that sums to 101% invites an argument
        # about the wrong thing.
        row["share_percent"] = (
            row["visit_count"] * 100 // resolved_total if resolved_total else 0
        )
    return rows


def unknown_area_count(checkins: list[dict[str, Any]]) -> int:
    """Check-ins that matched no known district.

    Disclosed rather than dropped. A heatmap built from 9 of 40 visits and
    presented as the group's habits is a wrong answer that looks like a right
    one; the count is what lets a reader notice.
    """

    return sum(1 for area, _row in _resolve(checkins) if area is None)
