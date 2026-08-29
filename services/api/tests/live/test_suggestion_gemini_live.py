"""The live tier for F32: a real call to Gemini, or nothing.

Every other F32 test injects `FakeSuggester`, so none of them can answer the
question the feature is judged on: does a REAL model, handed a real group's
history and the server's catalogue, propose an evening out of places that
actually exist?

Skipped by default, and a skip here is not a green -- it is this claim going
unmade. Run it with:

    set -a && . /path/to/.env && set +a
    cd services/api && MOBILE_REQUIRE_GEMINI_TESTS=1 python -m pytest tests/live -q

What it proves
--------------
* The model answers with the one kind this surface serves, in Vietnamese.
* **Every `place_id` it returns exists in the catalogue it was handed.** That is
  the "không bịa địa điểm" criterion measured against the *model*, rather than
  against the server that would have refused the card anyway.
* It obeys the pair rule the prompt states: a stop carries both a `verdict` from
  the closed set and a sentence, or the server drops both.
* It does not restate the history figures as if it had computed them -- the
  basis on screen is the server's arithmetic, and a model echoing a number is a
  second, unchecked source for it.

What it does not prove
----------------------
That the suggestion is *good*, or that a Vietnamese reader would act on it --
nobody has read one of these next to a map yet. Nor is it a distribution: a
handful of samples at temperature 0.4 cannot bound a fabrication rate. A green
run means "no fabrication observed in these samples", never "the model cannot
fabricate".

The division of labour is the same one the companion tier states. If the model
does invent a place, the product is still safe -- `ground_suggestion` refuses
the whole card, and `tests/domain/test_suggestion_grounding.py` proves that
refusal without a network. This file exists to say whether the prompt is
holding, because a server that keeps refusing a confused model is a feature
nobody can use.
"""

from __future__ import annotations

import os

import pytest

from app.api.companion_places import load_place_catalogue
from app.api.suggestion_gemini import gemini_suggestion
from app.domain.suggestion import (
    SUGGESTION_KIND,
    VERDICTS,
    ground_suggestion,
    summarise_history,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY", "").strip()
    or os.environ.get("MOBILE_REQUIRE_GEMINI_TESTS") != "1",
    reason="live Gemini tier: needs GEMINI_API_KEY and MOBILE_REQUIRE_GEMINI_TESTS=1",
)

HISTORY = summarise_history(
    [
        {"title": "Đà Lạt 2030", "split_total_vnd": 1_240_000, "headcount": 4},
        {"title": "Nướng cuối tuần", "split_total_vnd": 520_000, "headcount": 5},
    ],
    [
        {"category": "quan-an-local"},
        {"category": "quan-an-local"},
        {"category": "cafe"},
    ],
)


@pytest.fixture(scope="module")
def live_card():
    places = load_place_catalogue()
    raw = gemini_suggestion(HISTORY, places)
    if raw is None:
        pytest.fail("live Gemini suggestion returned nothing", pytrace=False)
    return raw, places


def test_the_model_answers_with_the_kind_this_surface_serves(live_card):
    raw, _places = live_card

    assert raw.get("kind") == SUGGESTION_KIND


def test_every_identifier_the_model_chose_exists_in_the_catalogue(live_card):
    """The acceptance criterion, measured against the model rather than the gate."""

    raw, places = live_card
    known = {place["id"] for place in places}
    chosen = [stop.get("place_id") for stop in raw["payload"]["stops"]]

    assert chosen, "the model proposed an evening with no stops"
    assert [place_id for place_id in chosen if place_id not in known] == []


def test_the_card_survives_grounding_untouched_by_the_server(live_card):
    raw, places = live_card

    grounded = ground_suggestion(raw, places)
    stops = grounded["payload"]["stops"]

    assert grounded["payload"]["title"].strip()
    assert grounded["payload"]["when_text"].strip()
    for stop in stops:
        # Both halves, or the server would have dropped both -- so a stop that
        # still has a verdict here is a stop the model paired properly.
        assert stop["verdict"] in VERDICTS, stop
        assert stop["reason"], stop


def test_the_model_does_not_restate_the_history_figures_as_its_own(live_card):
    """The basis is the server's arithmetic. A second source for it is a lie.

    Checks the raw đồng figures specifically. "195k" is the server's own
    rounding and appears in the prompt as a phrase the model may repeat; a full
    `1760000` coming back means it copied a number it did not compute.
    """

    raw, _places = live_card
    text = repr(raw)

    for figure in (str(HISTORY["split_total_vnd"]), str(HISTORY["avg_per_person_vnd"])):
        assert figure not in text
