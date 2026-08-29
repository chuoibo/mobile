"""Pure speaking and grounding rules for the group companion.

The model is allowed to choose catalogue identifiers, but it is never trusted
to describe a place. Rebuilding every card here makes that boundary structural:
only server-owned catalogue facts can reach a client, regardless of extra keys
or persuasive prose returned by the model.
"""

from __future__ import annotations

from datetime import datetime

DEFAULT_LIMITS = {
    "window_messages": 20,
    "max_ai_messages_per_window": 3,
    "cooldown_seconds": 90,
}

MAX_PLACES = 5
MAX_STOPS = 6
MAX_TEXT = 600


class CompanionError(Exception):
    """A stable refusal code that exposes no conversation or model output."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _aware_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        raise TypeError("companion timestamp must be an ISO-8601 string")

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CompanionError("companion_timestamp_naive")
    return parsed


def plan_turn(conversation: dict, limits: dict | None = None) -> dict:
    """Decide whether the companion may speak using metadata only.

    Every timestamp is validated before any early return. Otherwise a malformed
    older row could stay hidden whenever a higher-priority speaking rule fires,
    making the cap depend on which path happened to inspect the history.
    """

    messages = conversation["messages"]
    now = _aware_datetime(conversation["now"])
    message_times = [_aware_datetime(message["created_at"]) for message in messages]

    resolved_limits = dict(DEFAULT_LIMITS)
    if limits is not None:
        resolved_limits.update(limits)

    if not any(message.get("author_kind") == "human" for message in messages):
        return {"may_speak": False, "reason": "no_conversation"}

    if messages[-1].get("author_kind") == "ai":
        return {"may_speak": False, "reason": "already_spoke_last"}

    window_size = resolved_limits["window_messages"]
    recent_messages = messages[-window_size:] if window_size else []
    ai_messages = sum(
        message.get("author_kind") == "ai" for message in recent_messages
    )
    if ai_messages >= resolved_limits["max_ai_messages_per_window"]:
        return {"may_speak": False, "reason": "rate_limited"}

    latest_ai_at = next(
        (
            created_at
            for message, created_at in reversed(
                list(zip(messages, message_times, strict=True))
            )
            if message.get("author_kind") == "ai"
        ),
        None,
    )
    if latest_ai_at is not None:
        elapsed_seconds = (now - latest_ai_at).total_seconds()
        if elapsed_seconds < resolved_limits["cooldown_seconds"]:
            return {"may_speak": False, "reason": "cooldown"}

    return {"may_speak": True, "reason": "ok"}


def _malformed() -> CompanionError:
    return CompanionError("companion_card_malformed")


def _bounded_text(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise _malformed()
    return value[:MAX_TEXT]


def _catalogue_by_id(allowed_places: list[dict]) -> dict[str, dict]:
    return {
        place["id"]: place
        for place in allowed_places
        if isinstance(place, dict) and isinstance(place.get("id"), str)
    }


def _ground_places(payload: dict, catalogue: dict[str, dict]) -> dict:
    intro = _bounded_text(payload, "intro")
    place_ids = payload.get("place_ids")
    if not isinstance(place_ids, list) or not all(
        isinstance(place_id, str) for place_id in place_ids
    ):
        raise _malformed()

    # Validate the complete model response before truncating it. An invented
    # sixth identifier must sink the card, not disappear behind MAX_PLACES.
    if any(place_id not in catalogue for place_id in place_ids):
        raise CompanionError("companion_place_not_in_catalogue")

    unique_ids: list[str] = []
    seen: set[str] = set()
    for place_id in place_ids:
        if place_id not in seen:
            seen.add(place_id)
            unique_ids.append(place_id)

    selected = unique_ids[:MAX_PLACES]
    if not selected:
        raise CompanionError("companion_card_empty")
    return {
        "kind": "places",
        "payload": {
            "intro": intro,
            "places": [dict(catalogue[place_id]) for place_id in selected],
        },
    }


def _ground_itinerary(payload: dict, catalogue: dict[str, dict]) -> dict:
    title = _bounded_text(payload, "title")
    raw_stops = payload.get("stops")
    if not isinstance(raw_stops, list):
        raise _malformed()

    stops: list[tuple[str, str, str]] = []
    for raw_stop in raw_stops:
        if not isinstance(raw_stop, dict):
            raise _malformed()
        place_id = raw_stop.get("place_id")
        if not isinstance(place_id, str):
            raise _malformed()
        time_text = _bounded_text(raw_stop, "time_text")
        note = _bounded_text(raw_stop, "note")
        stops.append((place_id, time_text, note))

    # Check all mentioned IDs before applying the display limit for the same
    # fail-closed reason as a places card.
    if any(place_id not in catalogue for place_id, _, _ in stops):
        raise CompanionError("companion_place_not_in_catalogue")
    if not stops:
        raise CompanionError("companion_card_empty")

    return {
        "kind": "itinerary",
        "payload": {
            "title": title,
            "stops": [
                {
                    "time_text": time_text,
                    "note": note,
                    "place": dict(catalogue[place_id]),
                }
                for place_id, time_text, note in stops[:MAX_STOPS]
            ],
        },
    }


def ground_card(raw: dict, allowed_places: list[dict]) -> dict:
    """Rebuild one model card from contract fields and server-owned facts.

    Unknown keys are never copied. This whitelist is the money and
    anti-fabrication boundary: a new model field cannot become a client feature
    until a human deliberately adds it here.
    """

    if not isinstance(raw, dict) or "kind" not in raw:
        raise _malformed()
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        raise _malformed()

    kind = raw["kind"]
    if kind not in {"text", "places", "itinerary"}:
        raise CompanionError("companion_card_kind_unknown")

    if kind == "text":
        text = _bounded_text(payload, "text")
        if not text.strip():
            raise CompanionError("companion_card_empty")
        return {"kind": "text", "payload": {"text": text}}

    catalogue = _catalogue_by_id(allowed_places)
    if kind == "places":
        return _ground_places(payload, catalogue)
    return _ground_itinerary(payload, catalogue)
