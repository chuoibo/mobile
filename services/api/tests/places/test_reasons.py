"""The prompt, the parser, and the fabrication gate. No network in this file.

These prove the shape of the question and what happens to a bad answer. They
prove **nothing** about what Gemini actually says -- that needs the live tier,
and a skip there is not a green.
"""

from __future__ import annotations

import json

import pytest

from app.places.catalog import PLACES
from app.places.reasons import (
    ReasonRow,
    build_prompt,
    gemini_reasons,
    parse_reasons,
    ungrounded_numbers,
)

from .nhom_mau import NHOM_MAU

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

    prompt = build_prompt(ROWS, NHOM_MAU)
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
    """ "Explain why this suits them" always gets an answer. Ask a question the
    model is allowed to answer no to, and no becomes informative."""

    prompt = build_prompt(ROWS, NHOM_MAU)
    assert "khong-hop" in prompt
    assert "CÓ HỢP" in prompt
    # And the anti-flattery line, which is the part that makes `khong-hop`
    # something other than decoration.
    assert "chiều người hỏi" in prompt


def test_the_prompt_forbids_facts_that_were_not_supplied():
    prompt = build_prompt(ROWS, NHOM_MAU)
    assert "Không thêm món ăn" in prompt
    assert "giải thưởng" in prompt


def test_the_prompt_carries_every_place_and_the_group_profile():
    prompt = build_prompt(ROWS, NHOM_MAU)
    for place in PLACES:
        assert place["id"] in prompt
        assert place["name"] in prompt
    assert str(NHOM_MAU.size) in prompt
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
    assert ungrounded_numbers(reason, NUONG, NHOM_MAU) == []


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

    stray = ungrounded_numbers(reason, NUONG, NHOM_MAU)
    assert invented in stray


def test_the_gate_does_not_reject_the_places_own_street_number():
    """Over-rejection is a real cost: it silently drops good reasons and the
    catalogue goes quiet for no visible cause."""

    assert ungrounded_numbers("Ngay 27/1 Yersin, dễ tìm.", NUONG, NHOM_MAU) == []


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
        NHOM_MAU,
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
        NHOM_MAU,
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
        NHOM_MAU,
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
        NHOM_MAU,
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
    assert parse_reasons(model_says([item]), one_row(NUONG["id"]), NHOM_MAU) == {}


@pytest.mark.parametrize("text", ["not json at all", '{"not": "a list"}', ""])
def test_garbage_from_the_model_yields_no_reasons_and_no_exception(text):
    assert parse_reasons(text, one_row(NUONG["id"]), NHOM_MAU) == {}


# ---------------------------------------------------------------------------
# Recovering a batch the document parser cannot read
#
# `tests/places/test_reasons_batch_robustness.py` holds the captured payload
# and the story. These are the ways a *fix* for it goes wrong: a salvage path
# that quietly stops applying the checks the clean path applies is worse than
# the bug, because now the screen carries an `ai` label on something nobody
# validated. Each case below is a gate that a lenient parser would fail.
# ---------------------------------------------------------------------------

HILL = "p-the-hill-rooftop"
CAFE = "p-an-cafe-da-lat"


def broken_item(place_id: str) -> str:
    """An item whose reason quotes a trait without escaping the quote marks.

    The failure Gemini actually produces, minimised.
    """

    return (
        f'{{"id": "{place_id}", "verdict": "khong-hop", '
        f'"reason": "Đặc điểm "yên tĩnh" không hợp nhóm đông."}}'
    )


def good_item(place_id: str, reason: str, verdict: str = "khong-hop") -> str:
    return json.dumps(
        {"id": place_id, "verdict": verdict, "reason": reason}, ensure_ascii=False
    )


def three_rows() -> list[ReasonRow]:
    return [ReasonRow(place=BY_ID[pid]) for pid in (NUONG["id"], CAFE, HILL)]


def test_good_items_after_a_broken_one_are_recovered_too():
    """Not just the prefix before the break.

    A fix that decodes until the first error and stops would pass the captured
    fixture -- its one good item happens to come first -- and still lose most
    of a real batch, where the broken reason lands in the middle.
    """

    text = "\n".join(
        [
            "[",
            good_item(NUONG["id"], "Đồ nướng ngoài trời, 200-250k vừa túi.", "hop")
            + ",",
            broken_item(CAFE) + ",",
            good_item(HILL, "320-450k vượt ngân sách 250k, lại 5.2km."),
            "]",
        ]
    )
    kept = parse_reasons(text, three_rows(), NHOM_MAU)
    assert set(kept) == {NUONG["id"], HILL}
    assert kept[HILL].verdict == "khong-hop"


def test_a_recovered_item_still_faces_the_fabrication_gate():
    """The invented-number gate is not skipped on the recovery path.

    This is the one that matters for money-adjacent copy: a salvaged reason
    claiming a figure nobody supplied must be dropped exactly as it would be in
    a clean batch, or the fix has traded a blank card for a false one.
    """

    text = "\n".join(
        [
            "[",
            broken_item(CAFE) + ",",
            good_item(HILL, "Quán đạt 3 sao Michelin năm 2019.", "hop"),
            "]",
        ]
    )
    assert parse_reasons(text, three_rows(), NHOM_MAU) == {}


@pytest.mark.parametrize(
    "item",
    [
        '{"id": "p-khong-ton-tai", "verdict": "hop", "reason": "Chỗ này tuyệt."}',
        '{"id": "p-the-hill-rooftop", "verdict": "tuyet-voi", "reason": "Hay lắm."}',
        '{"id": "p-the-hill-rooftop", "verdict": "hop", "reason": "   "}',
        '{"id": "p-the-hill-rooftop", "reason": "Hợp đấy."}',
    ],
)
def test_recovery_does_not_relax_field_validation(item):
    """Unknown place, verdict outside the closed set, empty or missing reason.

    All four are dropped in a clean batch. Arriving via the recovery path
    changes nothing about them.
    """

    text = f"[\n{broken_item(CAFE)},\n{item}\n]"
    assert parse_reasons(text, three_rows(), NHOM_MAU) == {}


def test_prose_that_merely_contains_a_brace_recovers_nothing():
    """The resync must not turn arbitrary text into reasons.

    Stepping to the next `{` after a failure is how items are recovered; a
    document that is not a batch at all has to come back empty rather than
    yield whatever the scan happens to trip over.
    """

    text = 'Xin lỗi, tôi không thể trả lời. {"id": nope} { { {'
    assert parse_reasons(text, three_rows(), NHOM_MAU) == {}


def test_a_response_cut_off_mid_array_keeps_what_arrived():
    """Truncation was total loss for the same reason the stray quote was.

    Not the failure that was measured -- `finishReason` was `STOP` on all three
    real cases -- but the same all-or-nothing parse caused it, so the fix
    covers it and this records that it does.
    """

    text = (
        "[\n"
        + good_item(NUONG["id"], "Đồ nướng ngoài trời, 1.2km thôi.", "hop")
        + ',\n{"id": "p-the-hill-rooftop", "verdict": "khong-'
    )
    kept = parse_reasons(text, three_rows(), NHOM_MAU)
    assert set(kept) == {NUONG["id"]}


def test_the_clean_path_never_reaches_the_salvage(monkeypatch):
    """Structural: a well-formed batch is decoded by `json.loads`, full stop.

    Recovery is a fallback, and a fallback that starts running on the happy
    path is just a lenient parser wearing a different name. Booby-trap it and
    the normal case must still come out whole.
    """

    def explode(_text):
        raise AssertionError("salvage ran on a document that parsed cleanly")

    monkeypatch.setattr("app.places.reasons._salvage_objects", explode)
    text = model_says(
        [{"id": NUONG["id"], "verdict": "hop", "reason": "Đúng 200-250k, 1.2km."}]
    )
    assert (
        parse_reasons(text, one_row(NUONG["id"]), NHOM_MAU)[NUONG["id"]].verdict
        == "hop"
    )


def test_the_rescan_gives_up_instead_of_walking_every_brace(monkeypatch):
    """`_MAX_SALVAGE_MISSES` is enforced, counted rather than assumed.

    Resynchronising at the next `{` is O(braces) attempts, and each attempt can
    scan to the end of the document before it fails, so an unbounded rescan is
    quadratic in a body that is not a batch at all. The first version of this
    test just asserted the result was empty and took 0.01s either way -- it
    passed with the bound deleted, which made it decorative. Counting the
    decode attempts is what actually holds the bound in place.
    """

    attempts = []
    real_raw_decode = json.JSONDecoder.raw_decode

    def counting(self, s, idx=0):
        attempts.append(idx)
        return real_raw_decode(self, s, idx)

    monkeypatch.setattr(json.JSONDecoder, "raw_decode", counting)
    assert parse_reasons("{" * 5000, three_rows(), NHOM_MAU) == {}
    assert len(attempts) < 100, f"rescan tried {len(attempts)} times on 5000 braces"


# ---------------------------------------------------------------------------
# The call itself
# ---------------------------------------------------------------------------


def test_no_key_means_no_call_and_no_reasons(monkeypatch):
    """Missing credentials is a quiet, honest degradation, not a 500 and not a
    fabricated sentence."""

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert gemini_reasons(ROWS, NHOM_MAU) == {}


def test_a_blank_key_is_treated_as_absent(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    assert gemini_reasons(ROWS, NHOM_MAU) == {}


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
        assert gemini_reasons(one_row(NUONG["id"]), NHOM_MAU) == {}
    assert "SECRET" not in caplog.text
    assert "AIza" not in caplog.text


def test_a_network_failure_is_swallowed_into_an_empty_result(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-whatever")

    def explode(*args, **kwargs):
        del args, kwargs
        raise TimeoutError("too slow")

    monkeypatch.setattr("urllib.request.urlopen", explode)
    assert gemini_reasons(one_row(NUONG["id"]), NHOM_MAU) == {}
