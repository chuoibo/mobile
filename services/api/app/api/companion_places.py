"""Server catalogue adapter for companion-safe place cards."""

from __future__ import annotations

from app.places.prompt_safety import safe_places

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
        # No caller: the seed rows, so the live probes and the offline scripts
        # that ask for «the catalogue» with no session still get one. Every
        # request path passes its own read; this branch is not one of them.
        from app.places.catalog import PLACES

        rows = PLACES

    # Only rows safe to put in front of a model (M9, ADR-0017): the catalogue
    # is a table now, and its rows can come from data the world can edit.
    return [
        {field: place.get(field) for field in CLIENT_PLACE_FIELDS}
        for place in safe_places(rows)
    ]
