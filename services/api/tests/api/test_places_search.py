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
from app.places.catalog import CATEGORIES, GROUP, PLACES
from app.places.scoring import score_place

from .helpers import actor_headers

BY_ID = {place["id"]: place for place in PLACES}
REAL_IDS = [place["id"] for place in PLACES]
REAL_CATEGORY_IDS = [category["id"] for category in CATEGORIES]


def searcher_returning(raw):
    """A searcher that answers with a fixed model payload, without a network call.

    Takes the catalogue the route hands it (M9: the rows come from the table,
    so the route reads them and passes them in) and ignores it: what this stub
    is for is the answer, not the prompt.
    """

    def search(query: str, places=None):
        del query, places
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
    return client.post("/places/search", json={"query": query}, headers=actor_headers())


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
            "results": [
                {
                    "id": "p-lung-chung-cafe",
                    "verdict": "hop",
                    "reason": "Chỗ này yên, hợp ngồi lâu.",
                }
            ],
        },
    )

    match = post(client).json()["places"][0]["match"]
    assert match["source"] == "ai"
    assert match["reason"] == "Chỗ này yên, hợp ngồi lâu."


# ---------------------------------------------------------------------------
# The label and the conclusion are one claim (bug-174904)
# ---------------------------------------------------------------------------
#
# `match.source == "ai"` says a model wrote the sentence; `match.verdict` says
# what the model concluded. The app treats the pair as a single fact and
# refuses a whole response that breaks it, because the two halves are what the
# badge is assembled from: `source: "ai"` with no verdict renders as "AI MATCH
# 95%", a percentage attributed to a model that never gave an opinion.
#
# So search asks for the verdict rather than passing `None` and hoping the
# label carries itself. Every case below states the same rule from one side:
# a card carries both halves or neither.


def pairs_intact(body) -> list[dict]:
    """Cards whose `source`/`verdict` pair is the one the app refuses."""

    return [
        place["match"]
        for place in body["places"]
        if (place["match"]["source"] == "ai") != (place["match"]["verdict"] is not None)
    ]


def test_the_verdict_the_model_gave_reaches_the_card_it_belongs_to(client):
    """Three rows, three different conclusions, none of them swapped."""

    use(
        client,
        {
            "understood": understood(),
            "results": [
                {"id": "p-tiem-nuong-xom-lao", "verdict": "hop", "reason": "Hợp nhóm."},
                {"id": "p-lung-chung-cafe", "verdict": "tam", "reason": "Tạm được."},
                {
                    "id": "p-nuong-ngoi-troi-thong",
                    "verdict": "khong-hop",
                    "reason": "Hơi xa nhóm.",
                },
            ],
        },
    )

    body = post(client).json()
    assert [
        (place["id"], place["match"]["source"], place["match"]["verdict"])
        for place in body["places"]
    ] == [
        ("p-tiem-nuong-xom-lao", "ai", "hop"),
        ("p-lung-chung-cafe", "ai", "tam"),
        ("p-nuong-ngoi-troi-thong", "ai", "khong-hop"),
    ]


def test_a_sentence_written_without_a_verdict_is_never_labelled_ai(client):
    """The exact shape the app rejected on the first live query of F12.

    The model wrote prose for this row and gave no conclusion. Serving that as
    `source: "ai"` with `verdict: null` puts the words AI MATCH and a
    percentage on a card the model never judged.
    """

    use(
        client,
        {
            "understood": understood(),
            "results": [{"id": "p-lung-chung-cafe", "reason": "Chỗ này yên, hợp ngồi lâu."}],
        },
    )

    body = post(client).json()
    assert [place["id"] for place in body["places"]] == ["p-lung-chung-cafe"]
    match = body["places"][0]["match"]
    assert match["verdict"] is None
    assert match["source"] == "none", (
        "a sentence with no verdict shipped under the ai label -- the badge "
        "would say AI MATCH for a place no model gave an opinion on"
    )
    assert "Chỗ này yên" not in match["reason"], (
        "the model's sentence is still on the card while the card claims no "
        "model wrote it"
    )


def test_a_verdict_outside_the_closed_set_costs_the_row_its_label_not_the_answer(
    client,
):
    """Blast radius, deliberately narrower than a fabricated identifier.

    An unknown verdict token is a malformed field on one row, not evidence the
    model stopped reading the catalogue, so the row survives without its label.
    """

    use(
        client,
        {
            "understood": understood(),
            "results": [
                {"id": "p-lung-chung-cafe", "verdict": "rất hợp", "reason": "Hợp nhóm."},
                {"id": "p-tiem-nuong-xom-lao", "verdict": "hop", "reason": "Nướng ngon."},
            ],
        },
    )

    body = post(client).json()
    assert body["source"] == "ai"
    assert [place["id"] for place in body["places"]] == [
        "p-lung-chung-cafe",
        "p-tiem-nuong-xom-lao",
    ]
    assert [place["match"]["source"] for place in body["places"]] == ["none", "ai"]
    assert body["places"][0]["match"]["verdict"] is None
    assert "rất hợp" not in response_text(body)


def test_a_row_that_loses_its_sentence_loses_its_verdict_with_it(client):
    """The gates drop the prose; the conclusion cannot outlive it.

    A verdict left behind on a card labelled `none` breaks the same pair from
    the other side, and the app refuses that response too.
    """

    use(
        client,
        {
            "understood": understood(),
            "results": [
                {
                    "id": "p-lung-chung-cafe",
                    "verdict": "hop",
                    "reason": "Quán từng lọt top 47 quán cafe đẹp nhất năm 2019.",
                }
            ],
        },
    )

    match = post(client).json()["places"][0]["match"]
    assert match["source"] == "none"
    assert match["verdict"] is None, (
        "the ungrounded-number gate dropped the sentence but kept the verdict"
    )


def test_an_echoed_sentence_loses_its_verdict_with_it(client):
    query = "quán nướng ngoài trời cho 6 người dưới 300k, gần trung tâm"
    use(
        client,
        {
            "understood": understood(),
            "results": [{"id": "p-lung-chung-cafe", "verdict": "hop", "reason": query}],
        },
    )

    match = post(client, query=query).json()["places"][0]["match"]
    assert match["source"] == "none"
    assert match["verdict"] is None


def test_no_card_search_serves_ever_breaks_the_pair_the_app_enforces(client):
    """One payload with every shape at once, checked by the client's own rule.

    The cases above each pin one path. This pins the invariant itself, so a
    later path that produces a card some other way is covered before anyone
    remembers to write a case for it.
    """

    use(
        client,
        {
            "understood": understood(),
            "results": [
                {"id": "p-tiem-nuong-xom-lao", "verdict": "hop", "reason": "Hợp nhóm."},
                {"id": "p-lung-chung-cafe", "reason": "Không có kết luận."},
                {"id": "p-nuong-ngoi-troi-thong", "verdict": "khong-hop"},
                {"id": "p-quan-oc-di-be", "verdict": "sai-tu-vung", "reason": "Ổn."},
                {
                    "id": "p-the-hill-rooftop",
                    "verdict": "tam",
                    "reason": "Quán từng lọt top 47 quán ngon nhất năm 2019.",
                },
            ],
        },
    )

    body = post(client).json()
    assert len(body["places"]) == 5
    assert pairs_intact(body) == [], (
        "these cards claim an AI label with no verdict, or a verdict with no "
        "AI label -- the app refuses the whole response on either"
    )


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
    client.app.dependency_overrides[get_place_searcher] = lambda: lambda query, places=None: None

    response = post(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["places"] == []
    assert body["source"] == "none"


def test_a_searcher_that_raises_is_contained(client):
    def boom(query, places=None):
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

    client.app.dependency_overrides[get_place_searcher] = lambda: lambda query, places=None: None

    body = post(client, query="cafe").json()
    assert body["places"] == []


@pytest.mark.parametrize("query", ["", "   ", "\n\t "])
def test_an_empty_query_is_refused_before_any_model_is_asked(client, query):
    asked = []

    def record(text, places=None):
        asked.append(text)
        return None

    client.app.dependency_overrides[get_place_searcher] = lambda: record

    response = client.post(
        "/places/search", json={"query": query}, headers=actor_headers()
    )
    assert response.status_code == 422, response.text
    assert asked == []


def test_an_oversized_query_is_refused_rather_than_pasted_into_a_prompt(client):
    asked = []

    def record(text, places=None):
        asked.append(text)
        return None

    client.app.dependency_overrides[get_place_searcher] = lambda: record

    response = client.post(
        "/places/search", json={"query": "a" * 5000}, headers=actor_headers()
    )
    assert response.status_code == 422, response.text
    assert asked == [], "a 5000-character payload reached the prompt builder"


# ---------------------------------------------------------------------------
# The handle, not the gate (rd-be-12)
# ---------------------------------------------------------------------------
#
# Every other grounding case above and in `tests/domain/` calls the gate with a
# catalogue the test itself built. So they all check that `ground_search`
# decides correctly about the list it was handed, and none of them checks
# *which list the route hands it*. Those are different claims: the gate can be
# perfect while the route feeds it an empty list, a subset, or someone else's
# categories, and every one of those cases stays green.
#
# The pair below pins the handle from both sides, which is what makes it a
# bound rather than a smoke test. The first half says nothing real is missing
# from what the route passes; the second says nothing unreal was added. Neither
# half alone is enough -- an empty list passes the second on its own, and a
# catalogue with an extra invented row passes the first.


@pytest.mark.parametrize("category_id", REAL_CATEGORY_IDS)
def test_the_route_hands_the_gate_every_category_the_catalogue_publishes(
    client, category_id
):
    """A category the app itself ships must survive its own grounding gate.

    Parametrised over the real catalogue rather than one hand-picked id on
    purpose. A route that passed `[CATEGORIES[0]]` -- or any other plausible
    subset -- answers correctly for the id the rest of this file happens to
    use, and refuses the other three while every existing case stays green.
    """

    use(
        client,
        {
            "understood": understood(categories=[category_id]),
            "results": [{"id": "p-lung-chung-cafe", "reason": "Hợp."}],
        },
    )

    body = post(client).json()
    assert body["source"] == "ai", (
        f"category {category_id!r} ships in the catalogue but the route refused "
        "the answer that used it -- the route is not passing the real categories"
    )
    assert body["understood"]["categories"] == [category_id]


def test_a_category_the_catalogue_does_not_publish_still_costs_the_whole_answer(
    client,
):
    """The other side of the bound: the route may not widen the gate either.

    `quan-nhau-san-thuong` is exactly the kind of id a model invents -- it reads
    like the four real ones. Serving it would mean the screen offers a filter
    the catalogue cannot fill.
    """

    assert "quan-nhau-san-thuong" not in REAL_CATEGORY_IDS

    use(
        client,
        {
            "understood": understood(categories=["quan-nhau-san-thuong"]),
            "results": [{"id": "p-lung-chung-cafe", "reason": "Hợp."}],
        },
    )

    body = post(client).json()
    assert body["source"] == "none"
    assert body["places"] == []
    assert body["understood"] is None
    assert "quan-nhau-san-thuong" not in response_text(body)


@pytest.mark.parametrize("place_id", REAL_IDS)
def test_the_route_hands_the_gate_every_place_the_catalogue_publishes(
    client, place_id
):
    """Same bound on the other argument, for the same reason.

    `allowed_places=[]` is caught by the happy-path case at the top of this
    file, but a *subset* is not: the cases above only ever name three of the
    twelve rows, so a route passing those three would stay green while nine
    real places became unreachable through search.
    """

    use(
        client,
        {
            "understood": understood(),
            "results": [{"id": place_id, "reason": "Hợp."}],
        },
    )

    body = post(client).json()
    assert body["source"] == "ai", (
        f"place {place_id!r} ships in the catalogue but the route refused the "
        "answer that named it -- the route is not passing the real catalogue"
    )
    assert [place["id"] for place in body["places"]] == [place_id]


def response_text(body) -> str:
    import json

    return json.dumps(body, ensure_ascii=False)
