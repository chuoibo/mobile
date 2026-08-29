"""`POST /places/search` -- F12, a sentence a person typed (rd-be-10).

What this tier proves and what it does not
------------------------------------------
The searcher is injected, so nothing here calls Gemini and nothing here proves
the model is any good at reading Vietnamese. What it proves is the half that
does not depend on the model being right: whatever comes back, only catalogue
rows reach the caller, an invented identifier costs the whole answer, and a
sentence with a figure nobody supplied never ships under an ``ai`` label.

That split is the point. The model's competence is measured in
``tests/live/``, where a skip is not a green. The model's *containment* is
measured here, deterministically, and it has to hold even on the day the model
is wrong -- or is doing what an attacker asked it to.
"""

from __future__ import annotations

import pytest

from app.api.routes.places import get_place_searcher
from app.places.catalog import GROUP, PLACES
from app.places.scoring import score_place

BY_ID = {place["id"]: place for place in PLACES}
REAL_IDS = [place["id"] for place in PLACES]


def searcher_returning(raw):
    """A searcher that answers with a fixed model payload, without a network call."""

    def search(query: str):
        del query
        return raw

    return search


def use(client, raw):
    client.app.dependency_overrides[get_place_searcher] = lambda: searcher_returning(raw)


def understood(**overrides):
    body = {
        "budget_per_person_vnd": 300_000,
        "group_size": 6,
        "max_distance_km": 5,
        "categories": ["quan-an-local"],
        "traits": ["Ngoài trời"],
    }
    body.update(overrides)
    return body


def post(client, query="quán nướng ngoài trời cho 6 người dưới 300k"):
    return client.post("/places/search", json={"query": query})


# ---------------------------------------------------------------------------
# The feature
# ---------------------------------------------------------------------------


def test_a_natural_sentence_comes_back_as_real_places_from_the_catalogue(client):
    use(
        client,
        {
            "understood": understood(),
            "results": [
                {"id": "p-tiem-nuong-xom-lao", "reason": "Đồ nướng, ngồi ngoài trời."},
                {"id": "p-nuong-ngoi-troi-thong", "reason": "Cũng nướng ngoài trời."},
            ],
        },
    )

    response = post(client)
    assert response.status_code == 200, response.text
    body = response.json()

    assert [place["id"] for place in body["places"]] == [
        "p-tiem-nuong-xom-lao",
        "p-nuong-ngoi-troi-thong",
    ]
    assert body["source"] == "ai"
    assert body["understood"]["budget_per_person_vnd"] == 300_000
    assert body["query"] == "quán nướng ngoài trời cho 6 người dưới 300k"


def test_every_field_on_a_returned_card_is_the_catalogue_row_not_the_model(client):
    """The model may choose a row. It may never describe one."""

    use(
        client,
        {
            "understood": understood(),
            "results": [
                {
                    "id": "p-tiem-nuong-xom-lao",
                    "name": "Quán Của Mô Hình",
                    "address": "1 Đường Bịa Ra",
                    "price_min_vnd": 1,
                    "rating": 5.0,
                    "reason": "Hợp nhóm.",
                }
            ],
        },
    )

    body = post(client).json()
    served = body["places"][0]
    real = BY_ID["p-tiem-nuong-xom-lao"]
    for field in ("name", "address", "price_min_vnd", "price_max_vnd", "rating"):
        assert served[field] == real[field], f"{field} came from the model"
    assert "Quán Của Mô Hình" not in response_text(body)


def test_the_score_is_the_same_arithmetic_the_browse_screen_shows(client):
    """One score per place per group, or two screens disagree about one place."""

    use(
        client,
        {
            "understood": understood(),
            "results": [{"id": "p-lung-chung-cafe", "reason": "Chill."}],
        },
    )

    served = post(client).json()["places"][0]
    expected, factors = score_place(BY_ID["p-lung-chung-cafe"], GROUP)
    assert served["match"]["score"] == expected
    assert len(served["match"]["factors"]) == len(factors)


def test_a_grounded_model_sentence_is_served_under_the_ai_label(client):
    use(
        client,
        {
            "understood": understood(),
            "results": [{"id": "p-lung-chung-cafe", "reason": "Chỗ này yên, hợp ngồi lâu."}],
        },
    )

    match = post(client).json()["places"][0]["match"]
    assert match["source"] == "ai"
    assert match["reason"] == "Chỗ này yên, hợp ngồi lâu."


# ---------------------------------------------------------------------------
# Fail closed
# ---------------------------------------------------------------------------


def test_an_invented_identifier_costs_the_whole_answer_not_just_its_own_row(client):
    """Four good rows chosen by a model that invented the fifth are not four good rows."""

    use(
        client,
        {
            "understood": understood(),
            "results": [
                {"id": "p-tiem-nuong-xom-lao", "reason": "Hợp."},
                {"id": "p-lung-chung-cafe", "reason": "Hợp."},
                {"id": "p-quan-nuong-bia-dat", "reason": "Quán nướng ngon nhất Đà Lạt."},
            ],
        },
    )

    response = post(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["places"] == [], (
        "an answer containing one fabricated identifier was served with the "
        "fabrication filtered out -- the caller cannot tell it happened"
    )
    assert body["source"] == "none"
    assert body["understood"] is None
    assert "p-quan-nuong-bia-dat" not in response_text(body)


def test_a_sentence_quoting_a_figure_nobody_supplied_loses_its_ai_label(client):
    """Reused gate, not a second one: `reasons.ungrounded_numbers` decides.

    Blast radius differs from an invented id on purpose. A place that does not
    exist means the answer *set* is fiction; a stray figure means one sentence
    is. The row survives with the template reason and no `ai` label.
    """

    use(
        client,
        {
            "understood": understood(),
            "results": [
                {
                    "id": "p-lung-chung-cafe",
                    "reason": "Quán từng lọt top 47 quán cafe đẹp nhất năm 2019.",
                }
            ],
        },
    )

    body = post(client).json()
    assert [place["id"] for place in body["places"]] == ["p-lung-chung-cafe"]
    match = body["places"][0]["match"]
    assert match["source"] == "none"
    assert "top 47" not in match["reason"]


def test_a_model_that_cannot_be_reached_is_an_honest_empty_answer_not_a_500(client):
    client.app.dependency_overrides[get_place_searcher] = lambda: lambda query: None

    response = post(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["places"] == []
    assert body["source"] == "none"


def test_a_searcher_that_raises_is_contained(client):
    def boom(query):
        raise RuntimeError("socket died")

    client.app.dependency_overrides[get_place_searcher] = lambda: boom

    response = post(client)
    assert response.status_code == 200, response.text
    assert response.json()["source"] == "none"


def test_no_silent_fallback_to_keyword_search_when_the_model_is_down(client):
    """A broken AI must not be dressed up as a working one.

    Returning keyword hits under `source: "none"` would put a plausible list on
    the screen and leave nobody able to tell that the feature is not running.
    """

    client.app.dependency_overrides[get_place_searcher] = lambda: lambda query: None

    body = post(client, query="cafe").json()
    assert body["places"] == []


@pytest.mark.parametrize("query", ["", "   ", "\n\t "])
def test_an_empty_query_is_refused_before_any_model_is_asked(client, query):
    asked = []

    def record(text):
        asked.append(text)
        return None

    client.app.dependency_overrides[get_place_searcher] = lambda: record

    response = client.post("/places/search", json={"query": query})
    assert response.status_code == 422, response.text
    assert asked == []


def test_an_oversized_query_is_refused_rather_than_pasted_into_a_prompt(client):
    asked = []

    def record(text):
        asked.append(text)
        return None

    client.app.dependency_overrides[get_place_searcher] = lambda: record

    response = client.post("/places/search", json={"query": "a" * 5000})
    assert response.status_code == 422, response.text
    assert asked == [], "a 5000-character payload reached the prompt builder"


def response_text(body) -> str:
    import json

    return json.dumps(body, ensure_ascii=False)
