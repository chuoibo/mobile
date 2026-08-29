"""Grounding for F32 proactive outing suggestions (rd-be-14).

The third model-facing surface in this service, and the first one nobody asked
for. `ground_card` answers a conversation somebody was already having and
`ground_search` answers a sentence somebody just typed; this card simply
appears. That removes the one reviewer the other two surfaces get for free --
a person mid-thought, who would notice that the restaurant being suggested is
not a restaurant they have ever heard of.

So the rules are the ones the earlier two surfaces already paid for, repeated
rather than reinvented. Three grounding modules is one more than anybody wants,
and the honest reason there are three is that the shapes differ; the *rules*
must not, because the moment they differ one of them is the weaker one and
nobody finds out which until it is on a screen:

* **The model copies identifiers; the server owns facts.** A `place_id` outside
  the catalogue sinks the whole card rather than being filtered out of it. A
  model that invented the fourth stop was not reading the catalogue when it
  picked the first three, and a filtered card hides exactly that.
* **That check runs before deduplication and before `MAX_STOPS`.** Both of
  those shorten the list, and a check that ran after either would let the
  display limit act as an amnesty for a fabricated stop that happened to land
  last (#139).
* **`reason` and `verdict` are one claim, tied at one point.** Half a pair is a
  card that either shows a model endorsement nobody gave or a conclusion with
  nothing behind it (#146).
* **The payload is rebuilt from a whitelist.** A field the model invents cannot
  become a client feature until a person deliberately adds it here (#140).

The history the suggestion is built on is *not* model output either.
`summarise_history` computes it from the group's own trips and check-ins, in
integer đồng, and the route serves it beside the card so the screen can say
what the suggestion is based on. Letting the model restate those figures would
be the fabrication surface this module exists to close, one field to the left.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

#: The card kind this module -- and only this module -- serves. Deliberately
#: not a fourth kind inside `ground_card`: a proactive suggestion is not a chat
#: message, and widening the companion's whitelist to carry it would put an
#: unasked-for card into the message stream.
SUGGESTION_KIND = "outing_suggestion"

#: A proposal, not an itinerary dump. Four stops is an evening a group can read
#: at a glance and still argue with.
MAX_STOPS = 4

#: One or two sentences, same ceiling the sibling surfaces use.
MAX_TEXT = 240

#: Titles of past trips shown back as the basis for the suggestion.
MAX_RECENT_TITLES = 3

#: The model's own conclusion about one stop for one group, from a closed set.
#: Held as a literal because the domain may not reach into `app.places`, and
#: kept identical to `app.domain.place_search.VERDICTS` on purpose: browse,
#: search and this card put the same badge on the same place.
VERDICTS: tuple[str, ...] = ("hop", "tam", "khong-hop")


class SuggestionError(Exception):
    """A refused card, carried as a code rather than a message.

    The text that provoked the refusal is model output, and model output is
    exactly what must not be echoed into a log line or a response body.
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _malformed() -> SuggestionError:
    return SuggestionError("suggestion_card_malformed")


def _bounded_text(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise _malformed()
    return value[:MAX_TEXT]


def _reason(value: Any) -> str | None:
    """Absent, blank and unusable all mean the same thing: no reason.

    Never substituted. A stop the model said nothing about is served with no
    sentence at all; inventing prose here would put words on a card that
    nothing wrote.
    """

    if value is None:
        return None
    if not isinstance(value, str):
        raise _malformed()
    trimmed = value.strip()
    return trimmed[:MAX_TEXT] if trimmed else None


def _verdict(value: Any) -> str | None:
    """Narrower blast radius than a fabricated identifier, on purpose.

    An identifier outside the catalogue is evidence the model stopped reading
    what it was handed. An unusable verdict token is a malformed label on one
    stop, and costing the group its whole suggestion over it would trade a
    feature for a badge.
    """

    if isinstance(value, str) and value in VERDICTS:
        return value
    return None


def _paired(reason: str | None, verdict: str | None) -> tuple[str | None, str | None]:
    """A sentence and the conclusion behind it, or neither.

    One point, not one per call site. A rule that has to be remembered at every
    call site is a rule that gets forgotten at the next one.
    """

    if reason is None or verdict is None:
        return None, None
    return reason, verdict


def _integer_dong(value: Any) -> int:
    """Money law 1, at figures that only ever get displayed.

    `bool` is rejected explicitly because `isinstance(True, int)` is true in
    Python and `True` is not a sum of money.
    """

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SuggestionError("suggestion_history_not_integer_dong")
    return value


def _headcount(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SuggestionError("suggestion_history_not_integer_dong")
    return value


def summarise_history(trips: list[dict], visits: list[dict]) -> dict:
    """What this group has actually done, computed by the server.

    `trips` are finished outings with their totals recomputed from the ledger
    (invariant 3 -- nothing here reads a stored total), and `visits` are the
    catalogue categories of places the group checked in at. Both arrive already
    scoped to one context; this function has no way to reach a second group's
    rows and is not the place that enforces that.

    The average is floor division over person-trips, so it stays an integer
    number of đồng. A displayed average that arrived as `222222.22` is a float
    inside a money value, and the fact that nothing downstream divides by it is
    not a reason to allow it -- the next reader will not know that.
    """

    total = 0
    people = 0
    titles: list[str] = []
    for trip in trips:
        if not isinstance(trip, dict):
            raise _malformed()
        total += _integer_dong(trip.get("split_total_vnd"))
        people += _headcount(trip.get("headcount"))
        title = trip.get("title")
        if isinstance(title, str) and title.strip():
            titles.append(title.strip()[:MAX_TEXT])

    counts = Counter(
        visit["category"]
        for visit in visits
        if isinstance(visit, dict) and isinstance(visit.get("category"), str)
    )
    # Count descending, then the category id, so two renders of one history do
    # not shuffle the basis line under somebody's thumb.
    top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))

    return {
        "outing_count": len(trips),
        "split_total_vnd": total,
        "avg_per_person_vnd": total // people if people else None,
        "top_categories": [category for category, _ in top],
        "recent_titles": titles[:MAX_RECENT_TITLES],
    }


def ground_suggestion(raw: Any, allowed_places: list[dict]) -> dict:
    """Rebuild one proactive card from identifiers plus server-owned facts.

    Raises `SuggestionError` rather than returning a partial card. Unlike a
    search, an empty answer is not a legitimate outcome here: a proactive card
    with nothing in it is not a quieter suggestion, it is a blank rectangle.
    """

    if not isinstance(raw, dict) or "kind" not in raw:
        raise _malformed()
    if raw["kind"] != SUGGESTION_KIND:
        raise SuggestionError("suggestion_card_kind_unknown")

    payload = raw.get("payload")
    if not isinstance(payload, dict):
        raise _malformed()

    title = _bounded_text(payload, "title")
    when_text = _bounded_text(payload, "when_text")

    raw_stops = payload.get("stops")
    if not isinstance(raw_stops, list):
        raise _malformed()

    entries: list[tuple[str, str, str, str | None, str | None]] = []
    for raw_stop in raw_stops:
        if not isinstance(raw_stop, dict):
            raise _malformed()
        place_id = raw_stop.get("place_id")
        if not isinstance(place_id, str):
            raise _malformed()
        reason, verdict = _paired(
            _reason(raw_stop.get("reason")), _verdict(raw_stop.get("verdict"))
        )
        entries.append(
            (
                place_id,
                _bounded_text(raw_stop, "time_text"),
                _bounded_text(raw_stop, "note"),
                reason,
                verdict,
            )
        )

    catalogue = {
        place["id"]: place
        for place in allowed_places
        if isinstance(place, dict) and isinstance(place.get("id"), str)
    }
    # Over the complete list the model sent, before deduplication and before
    # MAX_STOPS. See the module docstring: a check that ran after either would
    # let a shortened list stand in for a clean one.
    if any(place_id not in catalogue for place_id, _, _, _, _ in entries):
        raise SuggestionError("suggestion_place_not_in_catalogue")

    stops: list[dict] = []
    seen: set[str] = set()
    for place_id, time_text, note, reason, verdict in entries:
        if place_id in seen:
            continue
        seen.add(place_id)
        stops.append(
            {
                "time_text": time_text,
                "note": note,
                "reason": reason,
                "verdict": verdict,
                "place": dict(catalogue[place_id]),
            }
        )

    if not stops:
        raise SuggestionError("suggestion_card_empty")

    # Whitelist, not a copy. Adding a field here is a deliberate act by a
    # person; a field the model invented cannot become a client feature.
    return {
        "kind": SUGGESTION_KIND,
        "payload": {
            "title": title,
            "when_text": when_text,
            "stops": stops[:MAX_STOPS],
        },
    }
