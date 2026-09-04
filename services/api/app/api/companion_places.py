"""Server catalogue adapter for companion-safe place cards."""

from __future__ import annotations

CLIENT_PLACE_FIELDS = (
    "id",
    "name",
    "address",
    "price_min_vnd",
    "price_max_vnd",
    "rating",
    "distance_km",
    "open_hours",
    "category",
)


def load_place_catalogue(rows: list[dict] | None = None) -> list[dict]:
    """Return only place facts the client contract is prepared to display.

    Keeping this as an adapter avoids a second catalogue. `rows` is the caller's
    catalogue read (M9: the service reads it from the table); the argument is
    optional so a caller without a repository still fails closed on an empty
    list rather than on an ImportError.
    """

    if rows is None:
        return []

    return [
        {field: place.get(field) for field in CLIENT_PLACE_FIELDS}
        for place in rows
    ]
