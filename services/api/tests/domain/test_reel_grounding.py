"""F37 -- an AI reel may choose rows, but it may not author their facts.

The reel repeats the grounding boundary from ``suggestion.py`` with a shape
suited to memories: the model copies identifiers and writes two bounded text
fields; the server attaches everything else.  Refusals are deliberately whole
reel refusals.  Filtering or truncating a bad answer would make a partially
fabricated answer look clean.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.reel import MAX_NOTE, MAX_PICKS, MAX_TITLE, ReelError, ground_reel

CONTEXT_ID = uuid.UUID("37c00000-fee1-4fee-8fee-0000fee00037")
FIRST_ID = uuid.UUID("37a00000-fee1-4fee-8fee-0000fee00001")
SECOND_ID = uuid.UUID("37a00000-fee1-4fee-8fee-0000fee00002")
NOW = datetime(2030, 8, 30, 12, 0, tzinfo=UTC)


def _memory(
    memory_id: uuid.UUID,
    *,
    kind: str = "photo",
    image_url: str | None = None,
    caption: str | None = "Cả nhóm trên đỉnh đồi",
    place_name: str | None = "Đồi thông",
    created_at: datetime = NOW,
    reaction_count: int = 4,
    comment_count: int = 2,
) -> dict:
    return {
        "id": memory_id,
        "kind": kind,
        "image_url": image_url
        if image_url is not None
        else f"/contexts/{CONTEXT_ID}/photos/{memory_id}",
        "caption": caption,
        "place_name": place_name,
        "created_at": created_at,
        "reaction_count": reaction_count,
        "comment_count": comment_count,
        "author_id": uuid.uuid4(),
        "server_only": "must not cross the whitelist",
    }


MEMORIES = [
    _memory(FIRST_ID),
    _memory(
        SECOND_ID,
        kind="checkin",
        image_url="",
        caption="Dừng chân ăn trưa",
        place_name="Quán bên hồ",
        created_at=NOW - timedelta(hours=1),
        reaction_count=1,
        comment_count=3,
    )
    | {"image_url": None},
]


def _pick(memory_id: uuid.UUID | str, note: object = "Khoảnh khắc cả nhóm nhớ mãi"):
    return {
        "memory_id": str(memory_id),
        "note": note,
        "image_url": "https://model.invalid/invented.jpg",
        "caption": "Chú thích do model bịa",
        "place_name": "Nơi không tồn tại",
        "reaction_count": 999,
        "comment_count": 999,
        "created_at": "1900-01-01T00:00:00Z",
        "cta": "Mua ngay",
    }


def _raw(*picks: dict, title: object = "Những điều còn ở lại") -> dict:
    return {
        "title": title,
        "picks": list(picks),
        "summary": "A field outside the contract",
    }


def _code(raw: object, memories: list[dict] = MEMORIES) -> str:
    with pytest.raises(ReelError) as raised:
        ground_reel(raw, memories)
    return raised.value.code


def test_grounding_keeps_model_order_and_rebuilds_every_fact_from_server_rows():
    grounded = ground_reel(_raw(_pick(SECOND_ID), _pick(FIRST_ID)), MEMORIES)

    assert set(grounded) == {"title", "picks"}
    assert grounded["title"] == "Những điều còn ở lại"
    assert [pick["memory_id"] for pick in grounded["picks"]] == [
        SECOND_ID,
        FIRST_ID,
    ]
    assert grounded["picks"][0] == {
        "memory_id": SECOND_ID,
        "image_url": None,
        "caption": "Dừng chân ăn trưa",
        "place_name": "Quán bên hồ",
        "created_at": NOW - timedelta(hours=1),
        "reaction_count": 1,
        "comment_count": 3,
        "note": "Khoảnh khắc cả nhóm nhớ mãi",
    }


def test_a_field_the_model_invents_cannot_cross_either_whitelist():
    grounded = ground_reel(_raw(_pick(FIRST_ID)), MEMORIES)

    assert set(grounded["picks"][0]) == {
        "memory_id",
        "image_url",
        "caption",
        "place_name",
        "created_at",
        "reaction_count",
        "comment_count",
        "note",
    }
    assert "author_id" not in grounded["picks"][0]
    assert "server_only" not in grounded["picks"][0]


def test_an_identifier_outside_the_offered_set_sinks_the_whole_reel():
    invented = uuid.uuid4()

    assert _code(_raw(_pick(FIRST_ID), _pick(invented))) == "unknown_memory"


def test_unknown_is_checked_before_deduplication():
    invented = uuid.uuid4()

    assert (
        _code(_raw(_pick(FIRST_ID), _pick(FIRST_ID), _pick(invented)))
        == "unknown_memory"
    )


def test_unknown_is_checked_before_the_display_cap():
    offered = [_memory(uuid.uuid4()) for _ in range(MAX_PICKS)]
    raw = _raw(*[_pick(memory["id"]) for memory in offered], _pick(uuid.uuid4()))

    assert _code(raw, offered) == "unknown_memory"


def test_a_repeated_identifier_sinks_instead_of_collapsing():
    assert _code(_raw(_pick(FIRST_ID), _pick(FIRST_ID))) == "duplicate_memory"


def test_more_than_six_picks_sink_instead_of_being_truncated():
    offered = [_memory(uuid.uuid4()) for _ in range(MAX_PICKS + 1)]

    assert (
        _code(_raw(*[_pick(memory["id"]) for memory in offered]), offered)
        == "too_many_picks"
    )


def test_zero_picks_is_not_a_reel():
    assert _code(_raw()) == "empty_reel"


@pytest.mark.parametrize("title", [None, "", "   ", 37, True])
def test_each_pick_needs_a_usable_title(title):
    assert _code(_raw(_pick(FIRST_ID), title=title)) == "incomplete_pick"


@pytest.mark.parametrize("note", [None, "", "   ", 37, True])
def test_each_pick_needs_its_own_usable_note(note):
    assert _code(_raw(_pick(FIRST_ID, note=note))) == "incomplete_pick"


def test_title_and_note_are_trimmed_then_bounded():
    title = "  " + "T" * (MAX_TITLE + 7) + "  "
    note = "  " + "N" * (MAX_NOTE + 11) + "  "

    grounded = ground_reel(_raw(_pick(FIRST_ID, note=note), title=title), MEMORIES)

    assert grounded["title"] == "T" * MAX_TITLE
    assert grounded["picks"][0]["note"] == "N" * MAX_NOTE


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "not a reel",
        [],
        {},
        {"title": "x", "picks": {}},
        {"title": "x", "picks": ["not a pick"]},
        {"title": "x", "picks": [{"note": "missing id"}]},
        {"title": "x", "picks": [{"memory_id": 37, "note": "bad id"}]},
    ],
)
def test_malformed_shapes_are_refused_without_repair(raw):
    assert _code(raw) == "incomplete_pick"


def test_empty_is_decided_before_the_missing_title():
    assert _code({"picks": []}) == "empty_reel"
