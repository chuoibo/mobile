"""Grounding for F12 natural-language place search (rd-be-10).

`GET /places` is safe because nothing a caller types reaches its prompt, and
`tests/api/test_places_prompt_boundary.py` holds that byte for byte. F12 cannot
make that promise and still be F12: putting the person's sentence in front of
the model *is* the feature. So the defence moves from the input to the output.

The model reads the query. It does not author the answer. It may copy an `id`
out of the catalogue the server handed it, and nothing else it says becomes a
fact on a screen. That is the same rule `app/domain/companion.py::ground_card`
already holds for the chat companion, and this module is deliberately its twin
rather than a second, subtly different idea about the same danger -- two
grounding rules in one service means one of them is the weaker one, and nobody
finds out which until it is on a screen.

**One bad identifier sinks the whole answer.** It is not quietly filtered out
of a list of otherwise-good places. A model that invented one row was not
reading the catalogue when it chose the other four, and a filtered list hides
exactly that: four plausible places served under an `ai` label with no sign
that the fifth was fiction. The check therefore runs over the complete list
before deduplication and before `MAX_RESULTS` truncation, so the display limit
cannot become an accidental amnesty for a fabricated row that happened to land
in ninth place.

`understood` is echoed to the screen, so it is a fabrication surface too and
gets the same treatment: categories and traits are closed vocabularies drawn
from the catalogue, and a token from outside either one sinks the answer rather
than being dropped from a list the caller then reads as complete.

Strict about types, lenient about absence. A model that omits an empty array
has not asserted anything false, and rejecting its answer would cost a good
result for a punctuation-level difference; a model that sends a *string* where
a list belongs is not answering the question that was asked.
"""

from __future__ import annotations

from typing import Any

#: Cards a search screen can show before the list stops being an answer and
#: starts being a catalogue dump.
MAX_RESULTS = 8

#: One or two sentences. Bounds what a model can spend a screen on, and bounds
#: what an injected instruction can get printed if it survives everything else.
MAX_REASON = 240


class PlaceSearchError(Exception):
    """A model answer that will not be served, with the reason it was refused.

    Carries a code rather than a message because the caller logs it and never
    shows it: the text that provoked the refusal is model output, and model
    output is exactly what must not be echoed back on this path.
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _malformed() -> PlaceSearchError:
    return PlaceSearchError("place_search_malformed")


def _integer_dong(value: Any) -> int | None:
    """Money law 1, at a value that only ever gets displayed.

    A budget echoed back to a screen as `2.5e5` is a float that reached a money
    value inside this service, and the fact that nothing downstream divides by
    it is not a reason to let it in -- the next thing to read this field will
    not know that. `bool` is rejected explicitly because `isinstance(True, int)`
    is true in Python and `True` is not a sum of money.
    """

    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PlaceSearchError("place_search_budget_not_integer")
    return value


def _headcount(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _malformed()
    return value


def _distance_km(value: Any) -> float | None:
    """Not money, so a fraction is a real distance rather than a lost đồng."""

    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise _malformed()
    return value


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        raise _malformed()
    return value


def _reason(value: Any) -> str | None:
    """Absent, blank and unusable all mean the same thing: no reason.

    Never substituted. A row the model said nothing about is served with the
    server's own template sentence under `source: "none"`, which is the honest
    label; inventing prose here would put words on a card that nothing wrote.
    """

    if value is None:
        return None
    if not isinstance(value, str):
        raise _malformed()
    trimmed = value.strip()
    return trimmed[:MAX_REASON] if trimmed else None


def _ground_understood(
    raw: Any, allowed_places: list[dict], allowed_categories: list[dict]
) -> dict:
    if not isinstance(raw, dict):
        raise _malformed()

    categories = _string_list(raw.get("categories"))
    known_categories = {
        category["id"]
        for category in allowed_categories
        if isinstance(category, dict) and isinstance(category.get("id"), str)
    }
    if any(category not in known_categories for category in categories):
        raise PlaceSearchError("place_search_category_not_in_catalogue")

    traits = _string_list(raw.get("traits"))
    known_traits = {
        trait
        for place in allowed_places
        for trait in place.get("traits", [])
        if isinstance(trait, str)
    }
    if any(trait not in known_traits for trait in traits):
        raise PlaceSearchError("place_search_trait_not_in_catalogue")

    # Whitelist, not a copy. A field the model invents cannot become a client
    # feature until a person deliberately adds it here.
    return {
        "budget_per_person_vnd": _integer_dong(raw.get("budget_per_person_vnd")),
        "group_size": _headcount(raw.get("group_size")),
        "max_distance_km": _distance_km(raw.get("max_distance_km")),
        "categories": list(categories),
        "traits": list(traits),
    }


def ground_search(
    raw: Any, allowed_places: list[dict], allowed_categories: list[dict]
) -> dict:
    """Rebuild one model answer from identifiers plus server-owned facts.

    Raises `PlaceSearchError` rather than returning a partial answer. An empty
    result list is *not* an error: "không có chỗ nào hợp" is a legitimate reply
    to a search, unlike a chat card, which has to say something to exist.
    """

    if not isinstance(raw, dict):
        raise _malformed()

    understood = _ground_understood(
        raw.get("understood"), allowed_places, allowed_categories
    )

    raw_results = raw.get("results")
    if not isinstance(raw_results, list):
        raise _malformed()

    entries: list[tuple[str, str | None]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            raise _malformed()
        place_id = item.get("id")
        if not isinstance(place_id, str):
            raise _malformed()
        entries.append((place_id, _reason(item.get("reason"))))

    catalogue = {
        place["id"]: place
        for place in allowed_places
        if isinstance(place, dict) and isinstance(place.get("id"), str)
    }
    # Before deduplication and before the display limit, on purpose. See the
    # module docstring: a check that ran after truncation would serve a full
    # page of real places for an answer that was partly fiction.
    if any(place_id not in catalogue for place_id, _ in entries):
        raise PlaceSearchError("place_search_place_not_in_catalogue")

    results: list[dict] = []
    seen: set[str] = set()
    for place_id, reason in entries:
        if place_id in seen:
            continue
        seen.add(place_id)
        results.append({"place": dict(catalogue[place_id]), "reason": reason})

    return {"understood": understood, "results": results[:MAX_RESULTS]}
