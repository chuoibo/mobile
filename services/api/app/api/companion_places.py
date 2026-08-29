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


def load_place_catalogue() -> list[dict]:
    """Return only place facts the client contract is prepared to display.

    Keeping this as an adapter avoids a second catalogue while the soft import
    lets the companion fail closed on deployments that do not ship places yet.
    """

    try:
        from app.places.catalog import PLACES
    except ImportError:
        return []

    return [
        {field: place.get(field) for field in CLIENT_PLACE_FIELDS}
        for place in PLACES
    ]
