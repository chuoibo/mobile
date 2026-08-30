"""The itinerary display limit, on both sides of the model boundary (rd-be-17).

`MAX_STOPS` used to exist in exactly one place: a `stops[:MAX_STOPS]` slice in
`ground_card`. Nothing told the model a limit existed, and nothing told the
group when one had been applied. So the ordinary request -- "ghi rõ từng khung
giờ của cả hai ngày" -- produced a plan longer than six stops, the server threw
the tail away, and the card that arrived looked exactly like a complete plan.
The group read one day and believed that was the whole thing.

The same shape as the `categories` bug in #139: a prompt that expects something
of the model without ever stating the constraint, and then blames the model for
the answer. So the limit is now declared in two places that must agree:

* **In the schema sent to the model**, so it condenses deliberately and chooses
  which stops matter. It knows the content; the server does not.
* **On the card, when the server still has to cut**, because a schema limit is
  a request and not a guarantee. A model that ignores it must not be able to
  make stops disappear in silence.

The domain half of this lives in `tests/domain/test_companion.py`. This file
holds the half the domain cannot see: what the model was actually asked for.
"""

from __future__ import annotations

from app.api.companion_gemini import _PROMPT, _RESPONSE_SCHEMA
from app.domain.companion import MAX_STOPS


def _stops_schema():
    return _RESPONSE_SCHEMA.properties["payload"].properties["stops"]


def test_the_model_is_told_how_many_stops_a_card_can_hold():
    """Without this the model has no way to know a limit exists at all."""

    stops = _stops_schema()
    assert stops.max_items is not None, (
        "the stops array declares no upper bound, so the model plans as many "
        "stops as it likes and the server silently discards the tail"
    )
    assert int(stops.max_items) == MAX_STOPS, (
        "the limit the model is given and the limit the server enforces have "
        "drifted apart -- the model condenses to one number and is cut at another"
    )


def test_the_prompt_asks_the_model_to_choose_rather_than_to_be_truncated():
    """A bare `max_items` says "stop at six", not "pick the six that matter".

    The point of moving the decision to the model is that it knows what the six
    stops are about. If the prompt never asks it to prioritise, a schema cap
    just relocates the same arbitrary cut.
    """

    assert "itinerary" in _PROMPT.lower()
    assert str(MAX_STOPS) in _PROMPT, (
        "the prompt never states the stop budget, so the model cannot plan "
        "around it -- it can only be trimmed after the fact"
    )


def test_the_model_is_told_which_prose_each_structured_card_must_include():
    """Shared payload fields still need kind-specific requirements.

    Requiring every prose field on the shared payload object would make a text
    card invent an irrelevant title and intro. The prompt and field descriptions
    must instead tell the model which field belongs to each structured card.
    """
    payload = _RESPONSE_SCHEMA.properties["payload"]
    title = payload.properties["title"]
    intro = payload.properties["intro"]

    assert "An itinerary card MUST include payload.title" in _PROMPT
    assert "A places card MUST include payload.intro" in _PROMPT
    assert title.description == "Required title for an itinerary card."
    assert intro.description == "Required introduction for a places card."


def test_the_places_limit_is_declared_the_same_way_for_the_same_reason():
    """`place_ids` had the identical defect and is fixed in the same breath.

    Left alone it would be the next bug report with a different noun: the model
    returns seven places, five are shown, nothing on the card says so.
    """

    from app.domain.companion import MAX_PLACES

    place_ids = _RESPONSE_SCHEMA.properties["payload"].properties["place_ids"]
    assert place_ids.max_items is not None
    assert int(place_ids.max_items) == MAX_PLACES
