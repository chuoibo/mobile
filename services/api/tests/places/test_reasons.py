"""The prompt, the parser, and the fabrication gate. No network in this file.

These prove the shape of the question and what happens to a bad answer. They
prove **nothing** about what Gemini actually says -- that needs the live tier,
and a skip there is not a green.
"""

from __future__ import annotations

import json

import pytest

from app.places.catalog import GROUP, PLACES
from app.places.reasons import (
    ReasonRow,
    build_prompt,
    gemini_reasons,
    parse_reasons,
    ungrounded_numbers,
)

BY_ID = {place["id"]: place for place in PLACES}
ROWS = [ReasonRow(place=place) for place in PLACES]


def one_row(place_id: str) -> list[ReasonRow]:
    return [ReasonRow(place=BY_ID[place_id])]


# ---------------------------------------------------------------------------
# Anti-anchoring: the question must not contain the answer
# ---------------------------------------------------------------------------


def test_the_row_put_to_the_model_has_no_score_field():
    """Structural, not a promise in a comment.

    `ReasonRow` carries the place and nothing else, so a later edit cannot
    quietly start feeding the computed verdict into the question that is meant
    to produce an independent one.
    """

    assert not hasattr(ROWS[0], "score")
    assert set(ReasonRow.__slots__) == {"place"}


def test_the_prompt_never_states_the_computed_score():
    """A model told the answer is 96 writes a justification for 96."""

    prompt = build_prompt(ROWS, GROUP)
    for place in PLACES:
        payload = json.loads(
            [line for line in prompt.splitlines() if f'"{place["id"]}"' in line][0]
        )
        assert "diem" not in payload, f"{place['id']} row leaks the score"
        assert "score" not in payload, f"{place['id']} row leaks the score"
    # And the model is told it does not have the number, so it cannot treat a
    # figure it invented as one it was given.
    assert "bạn không được cho con số đó" in prompt


def test_the_prompt_offers_not_suitable_as_a_real_answer():
    """"Explain why this suits them" always gets an answer. Ask a question the
    model is allowed to answer no to, and no becomes informative."""

    prompt = build_prompt(ROWS, GROUP)
    assert "khong-hop" in prompt
    assert "CÓ HỢP" in prompt
    # And the anti-flattery line, which is the part that makes `khong-hop`
    # something other than decoration.
    assert "chiều người hỏi" in prompt


def test_the_prompt_forbids_facts_that_were_not_supplied():
    prompt = build_prompt(ROWS, GROUP)
    assert "Không thêm món ăn" in prompt
    assert "giải thưởng" in prompt


def test_the_prompt_carries_every_place_and_the_group_profile():
    prompt = build_prompt(ROWS, GROUP)
    for place in PLACES:
        assert place["id"] in prompt
        assert place["name"] in prompt
    assert str(GROUP["size"]) in prompt
    assert "250k" in prompt


# ---------------------------------------------------------------------------
# Grounding gate
# ---------------------------------------------------------------------------

NUONG = BY_ID["p-tiem-nuong-xom-lao"]  # 200-250k, 1.2km, 25 phút, 4-10 người


@pytest.mark.parametrize(
    "reason",
    [
        "Khoảng 200-250k mỗi người, vừa đúng ngân sách 250k của nhóm.",
        "Cách 1.2km, đi khoảng 25 phút.",
        "Quán nhận 4-10 người nên nhóm 6 người ngồi vừa.",
        "Giá 250.000đ một người là trong tầm.",
        "Mở 10:00 – 22:30 nên tối nay vẫn kịp.",
        "Đồ nướng ngoài trời, đúng kiểu nhóm thích.",
    ],
)
def test_reasons_quoting_only_supplied_figures_pass(reason):
    assert ungrounded_numbers(reason, NUONG, GROUP) == []


@pytest.mark.parametrize(
    ("reason", "invented"),
    [
        ("Quán từng được bình chọn top 10 Đà Lạt năm 2023.", "2023"),
        ("Có hơn 500 loại rượu vang trong hầm.", "500"),
        ("Bàn đặt trước 48 tiếng mới có chỗ.", "48"),
    ],
)
def test_reasons_asserting_figures_nobody_supplied_are_caught(reason, invented):
    """The expensive failure: fluent, specific, and false.

    A reason like this reads better than a true one, which is exactly why it
    cannot be allowed to reach a screen wearing an AI badge.
    """

    stray = ungrounded_numbers(reason, NUONG, GROUP)
    assert invented in stray


def test_the_gate_does_not_reject_the_places_own_street_number():
    """Over-rejection is a real cost: it silently drops good reasons and the
    catalogue goes quiet for no visible cause."""

    assert ungrounded_numbers("Ngay 27/1 Yersin, dễ tìm.", NUONG, GROUP) == []


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def model_says(items) -> str:
    return json.dumps(items, ensure_ascii=False)


def test_a_well_formed_answer_parses():
    out = parse_reasons(
        model_says(
            [{"id": NUONG["id"], "verdict": "hop", "reason": "Đúng 200-250k, 1.2km."}]
        ),
        one_row(NUONG["id"]),
        GROUP,
    )
    assert out[NUONG["id"]].verdict == "hop"


def test_a_not_suitable_verdict_survives_parsing():
    """`khong-hop` has to travel all the way to the caller. A parser that
    quietly upgraded it would undo the entire prompt design."""

    hill = BY_ID["p-the-hill-rooftop"]
    out = parse_reasons(
        model_says(
            [
                {
                    "id": hill["id"],
                    "verdict": "khong-hop",
                    "reason": "320-450k vượt ngân sách 250k, lại 5.2km.",
                }
            ]
        ),
        [ReasonRow(place=hill)],
        GROUP,
    )
    assert out[hill["id"]].verdict == "khong-hop"


def test_a_fabricated_figure_drops_that_place_only():
    """One bad sentence must not cost the other eleven their reasons."""

    hill = BY_ID["p-the-hill-rooftop"]
    rows = one_row(NUONG["id"]) + [ReasonRow(place=hill)]
    out = parse_reasons(
        model_says(
            [
                {
                    "id": NUONG["id"],
                    "verdict": "hop",
                    "reason": "Quán đạt 3 sao Michelin năm 2019.",
                },
                {
                    "id": hill["id"],
                    "verdict": "khong-hop",
                    "reason": "320-450k quá tay so với 250k.",
                },
            ]
        ),
        rows,
        GROUP,
    )
    assert NUONG["id"] not in out
    assert hill["id"] in out


def test_a_place_the_model_invented_is_discarded():
    """There is no row to check it against, so there is no way to serve it."""

    out = parse_reasons(
        model_says(
            [{"id": "p-khong-ton-tai", "verdict": "hop", "reason": "Chỗ này tuyệt."}]
        ),
        one_row(NUONG["id"]),
        GROUP,
    )
    assert out == {}


@pytest.mark.parametrize(
    "item",
    [
        {"id": "p-tiem-nuong-xom-lao", "verdict": "tuyet-voi", "reason": "Hay lắm."},
        {"id": "p-tiem-nuong-xom-lao", "verdict": "hop", "reason": "   "},
        {"id": "p-tiem-nuong-xom-lao", "verdict": "hop"},
        {"id": "p-tiem-nuong-xom-lao", "reason": "Hợp đấy."},
    ],
)
def test_malformed_items_are_dropped_not_coerced(item):
    assert parse_reasons(model_says([item]), one_row(NUONG["id"]), GROUP) == {}


@pytest.mark.parametrize("text", ["not json at all", '{"not": "a list"}', ""])
def test_garbage_from_the_model_yields_no_reasons_and_no_exception(text):
    assert parse_reasons(text, one_row(NUONG["id"]), GROUP) == {}


# ---------------------------------------------------------------------------
# The call itself
# ---------------------------------------------------------------------------


def test_no_key_means_no_call_and_no_reasons(monkeypatch):
    """Missing credentials is a quiet, honest degradation, not a 500 and not a
    fabricated sentence."""

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert gemini_reasons(ROWS, GROUP) == {}


def test_a_blank_key_is_treated_as_absent(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    assert gemini_reasons(ROWS, GROUP) == {}


def test_the_key_never_reaches_a_log_or_an_error(monkeypatch, caplog):
    """The one leak that would matter. The key goes in a header; nothing that
    could carry it -- URL, request body, response body -- is ever logged."""

    import urllib.error

    monkeypatch.setenv("GEMINI_API_KEY", "AIza-SECRET-DO-NOT-LEAK")

    def explode(*args, **kwargs):
        del args, kwargs
        raise urllib.error.HTTPError(
            "https://example.invalid", 401, "Unauthorized", {}, None
        )

    monkeypatch.setattr("urllib.request.urlopen", explode)
    with caplog.at_level("DEBUG"):
        assert gemini_reasons(one_row(NUONG["id"]), GROUP) == {}
    assert "SECRET" not in caplog.text
    assert "AIza" not in caplog.text


def test_a_network_failure_is_swallowed_into_an_empty_result(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-whatever")

    def explode(*args, **kwargs):
        del args, kwargs
        raise TimeoutError("too slow")

    monkeypatch.setattr("urllib.request.urlopen", explode)
    assert gemini_reasons(one_row(NUONG["id"]), GROUP) == {}
