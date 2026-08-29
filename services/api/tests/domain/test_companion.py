"""The two rules that keep the group companion honest, as pure functions.

Both rules are the kind that a green test suite is very good at pretending to
enforce, so each one is tested against the failure it exists to prevent rather
than against its happy path:

* `plan_turn` decides whether the AI may speak at all. It is handed message
  METADATA and never a message body -- the privacy rule is enforced by the
  shape of its argument, not by remembering not to log. A test below asserts
  the decision is unchanged when bodies are absent entirely.

* `ground_card` decides what the AI is allowed to have said. The model returns
  place IDs and nothing else; every human-readable fact about a place is copied
  from the server catalogue. So the interesting tests are not "a good card
  survives" but "a card naming a place nobody has heard of is refused" and
  "a name the model wrote is thrown away even when the ID is real".
"""

from __future__ import annotations

import pytest

from app.domain.companion import (
    DEFAULT_LIMITS,
    CompanionError,
    ground_card,
    plan_turn,
)

NOW = "2026-08-29T20:00:00+07:00"


def _messages(*kinds_and_times: tuple[str, str]) -> list[dict]:
    return [
        {"id": f"m{index}", "author_kind": kind, "created_at": created_at}
        for index, (kind, created_at) in enumerate(kinds_and_times)
    ]


def _catalogue() -> list[dict]:
    return [
        {
            "id": "p-tiem-nuong",
            "name": "Tiệm Nướng Xóm Lào",
            "address": "27/1 Yersin, TP. Đà Lạt",
            "price_min_vnd": 200_000,
            "price_max_vnd": 250_000,
        },
        {
            "id": "p-cafe-suong",
            "name": "Cafe Sương Mai",
            "address": "12 Trần Phú, TP. Đà Lạt",
            "price_min_vnd": 40_000,
            "price_max_vnd": 90_000,
        },
    ]


# --- the speaking cap ---------------------------------------------------


def test_the_companion_may_speak_after_people_have_been_talking():
    conversation = {
        "messages": _messages(
            ("human", "2026-08-29T19:40:00+07:00"),
            ("human", "2026-08-29T19:50:00+07:00"),
        ),
        "now": NOW,
    }

    assert plan_turn(conversation) == {"may_speak": True, "reason": "ok"}


def test_the_companion_does_not_answer_itself():
    """Two AI cards in a row is the failure people call "the bot is spamming"."""

    conversation = {
        "messages": _messages(
            ("human", "2026-08-29T19:00:00+07:00"),
            ("ai", "2026-08-29T19:01:00+07:00"),
        ),
        "now": NOW,
    }

    decision = plan_turn(conversation)

    assert decision["may_speak"] is False
    assert decision["reason"] == "already_spoke_last"


def test_the_companion_stops_once_it_has_spoken_its_share_of_the_window():
    older = "2026-08-29T10:00:00+07:00"
    conversation = {
        "messages": _messages(
            ("ai", older),
            ("human", older),
            ("ai", older),
            ("human", older),
            ("ai", older),
            ("human", older),
        ),
        "now": NOW,
    }

    decision = plan_turn(conversation)

    assert decision["may_speak"] is False
    assert decision["reason"] == "rate_limited"


def test_a_cap_that_only_counts_recent_messages_lets_an_old_burst_expire():
    """The window slides. Three AI cards last week must not silence it forever."""

    older = "2026-08-29T10:00:00+07:00"
    conversation = {
        "messages": _messages(("ai", older), ("ai", older), ("ai", older))
        + _messages(*[("human", older)] * DEFAULT_LIMITS["window_messages"]),
        "now": NOW,
    }

    assert plan_turn(conversation)["may_speak"] is True


def test_the_companion_waits_out_its_cooldown_even_when_people_reply_fast():
    conversation = {
        "messages": _messages(
            ("human", "2026-08-29T19:59:00+07:00"),
            ("ai", "2026-08-29T19:59:30+07:00"),
            ("human", "2026-08-29T19:59:50+07:00"),
        ),
        "now": NOW,
    }

    decision = plan_turn(conversation)

    assert decision["may_speak"] is False
    assert decision["reason"] == "cooldown"


def test_the_companion_does_not_open_an_empty_room():
    assert plan_turn({"messages": [], "now": NOW}) == {
        "may_speak": False,
        "reason": "no_conversation",
    }


def test_the_cap_is_decided_without_ever_seeing_what_anyone_wrote():
    """The privacy rule, enforced by shape.

    `plan_turn` cannot leak message text because it is never given any. This
    test would still pass if the function ignored bodies it was handed, so it
    is paired with `test_no_message_body_reaches_the_logs` at the API layer;
    together they cover "never received" and "never emitted".
    """

    metadata_only = {
        "messages": _messages(
            ("human", "2026-08-29T19:40:00+07:00"),
            ("human", "2026-08-29T19:50:00+07:00"),
        ),
        "now": NOW,
    }
    for message in metadata_only["messages"]:
        assert set(message) == {"id", "author_kind", "created_at"}

    assert plan_turn(metadata_only)["may_speak"] is True


def test_a_timestamp_without_a_timezone_is_refused_rather_than_guessed():
    conversation = {
        "messages": _messages(("human", "2026-08-29T19:40:00")),
        "now": NOW,
    }

    with pytest.raises(CompanionError) as raised:
        plan_turn(conversation)

    assert raised.value.code == "companion_timestamp_naive"


# --- grounding: the model may choose, only the server may describe ------


def test_a_place_the_catalogue_has_never_heard_of_sinks_the_whole_card():
    """The one failure this feature exists to prevent."""

    raw = {
        "kind": "places",
        "payload": {
            "intro": "Tối nay nhóm mình ăn nướng nhé",
            "place_ids": ["p-tiem-nuong", "p-quan-nay-khong-ton-tai"],
        },
    }

    with pytest.raises(CompanionError) as raised:
        ground_card(raw, _catalogue())

    assert raised.value.code == "companion_place_not_in_catalogue"


def test_an_itinerary_stop_at_an_invented_place_sinks_the_whole_card():
    raw = {
        "kind": "itinerary",
        "payload": {
            "title": "Tối thứ bảy",
            "stops": [
                {"place_id": "p-tiem-nuong", "time_text": "19:00", "note": "Ăn tối"},
                {"place_id": "p-bar-tren-may", "time_text": "21:00", "note": "Đi tiếp"},
            ],
        },
    }

    with pytest.raises(CompanionError) as raised:
        ground_card(raw, _catalogue())

    assert raised.value.code == "companion_place_not_in_catalogue"


def test_a_name_the_model_wrote_is_discarded_even_when_the_id_is_real():
    """Grounding is structural: the model picks, the server describes.

    Without this, a model that returns a real ID beside an invented name still
    puts the invented name on screen -- and an ID check alone would pass it.
    """

    raw = {
        "kind": "places",
        "payload": {
            "intro": "Gợi ý nè",
            "place_ids": ["p-tiem-nuong"],
            # Everything below is the model talking about the world. None of it
            # may survive into the card.
            "name": "Quán Nướng Bịa Đặt",
            "address": "404 Không Có Thật",
            "rating": 5.0,
        },
    }

    card = ground_card(raw, _catalogue())

    place = card["payload"]["places"][0]
    assert place["name"] == "Tiệm Nướng Xóm Lào"
    assert place["address"] == "27/1 Yersin, TP. Đà Lạt"
    assert "Bịa" not in str(card)


def test_the_card_carries_no_field_the_contract_did_not_name():
    """The money rule, enforced by whitelist rather than by banned words.

    A ban-list is a game of catch-up: forget one key and it ships. Rebuilding
    the payload from named fields means a new field has to be added on purpose.
    """

    raw = {
        "kind": "places",
        "payload": {
            "intro": "Chốt nhé",
            "place_ids": ["p-cafe-suong"],
            "expense": {"total_vnd": 900_000, "payer_id": "someone"},
            "amount_vnd": 900_000,
            "obligation": {"owes": 150_000},
            "split": "equal",
        },
    }

    card = ground_card(raw, _catalogue())

    assert set(card["payload"]) == {"intro", "places"}
    for banned in ("expense", "amount_vnd", "obligation", "split"):
        assert banned not in card["payload"]
    assert "900000" not in str(card).replace("_", "")


def test_a_places_card_with_nothing_in_it_is_refused_rather_than_shown():
    raw = {"kind": "places", "payload": {"intro": "Đây nè", "place_ids": []}}

    with pytest.raises(CompanionError) as raised:
        ground_card(raw, _catalogue())

    assert raised.value.code == "companion_card_empty"


def test_a_place_card_is_refused_when_the_catalogue_is_not_loaded():
    """Today's main has no catalogue module. Empty must mean silent, not free."""

    raw = {"kind": "places", "payload": {"intro": "x", "place_ids": ["p-tiem-nuong"]}}

    with pytest.raises(CompanionError) as raised:
        ground_card(raw, [])

    assert raised.value.code == "companion_place_not_in_catalogue"


def test_a_text_card_still_works_without_any_catalogue():
    raw = {"kind": "text", "payload": {"text": "Mình thấy 7 giờ hợp lý hơn đó"}}

    card = ground_card(raw, [])

    assert card == {
        "kind": "text",
        "payload": {"text": "Mình thấy 7 giờ hợp lý hơn đó"},
    }


def test_an_empty_text_card_is_refused():
    with pytest.raises(CompanionError) as raised:
        ground_card({"kind": "text", "payload": {"text": "   "}}, _catalogue())

    assert raised.value.code == "companion_card_empty"


def test_a_kind_nobody_can_render_is_refused():
    raw = {"kind": "poll", "payload": {"question": "Đi đâu?"}}

    with pytest.raises(CompanionError) as raised:
        ground_card(raw, _catalogue())

    assert raised.value.code == "companion_card_kind_unknown"


def test_a_card_that_is_not_even_shaped_like_a_card_is_refused():
    for raw in ({}, {"payload": {}}, {"kind": "text"}, {"kind": "text", "payload": []}):
        with pytest.raises(CompanionError) as raised:
            ground_card(raw, _catalogue())
        assert raised.value.code == "companion_card_malformed"


def test_the_same_place_named_twice_appears_once():
    raw = {
        "kind": "places",
        "payload": {
            "intro": "x",
            "place_ids": ["p-tiem-nuong", "p-cafe-suong", "p-tiem-nuong"],
        },
    }

    card = ground_card(raw, _catalogue())

    assert [place["id"] for place in card["payload"]["places"]] == [
        "p-tiem-nuong",
        "p-cafe-suong",
    ]


def test_an_itinerary_keeps_its_stops_in_the_order_the_model_planned_them():
    raw = {
        "kind": "itinerary",
        "payload": {
            "title": "Tối nay",
            "stops": [
                {"place_id": "p-tiem-nuong", "time_text": "19:00", "note": "Ăn"},
                {"place_id": "p-cafe-suong", "time_text": "21:00", "note": "Cafe"},
            ],
        },
    }

    card = ground_card(raw, _catalogue())

    stops = card["payload"]["stops"]
    assert [stop["place"]["id"] for stop in stops] == ["p-tiem-nuong", "p-cafe-suong"]
    assert [stop["time_text"] for stop in stops] == ["19:00", "21:00"]
    assert stops[0]["place"]["name"] == "Tiệm Nướng Xóm Lào"


def test_an_itinerary_carries_no_field_the_contract_did_not_name():
    """The whitelist is per card kind, and `itinerary` is a card kind.

    A places card has been guarded against a smuggled `amount_vnd` since it was
    written. The itinerary branch builds its own payload dict and was never
    held to the same rule, so the one card kind that plans a whole evening was
    also the one kind where an invented total could reach the client. Same
    model, same boundary.
    """
    raw = {
        "kind": "itinerary",
        "payload": {
            "title": "Tối nay",
            "stops": [
                {"place_id": "p-tiem-nuong", "time_text": "19:00", "note": "Ăn"},
            ],
            "expense": {"total_vnd": 900_000, "payer_id": "someone"},
            "amount_vnd": 900_000,
            "budget_per_person_vnd": 300_000,
        },
    }

    card = ground_card(raw, _catalogue())

    assert set(card["payload"]) == {"title", "stops"}
    for banned in ("expense", "amount_vnd", "budget_per_person_vnd"):
        assert banned not in card["payload"]
    assert "900000" not in str(card).replace("_", "")


def test_an_itinerary_stop_is_described_by_the_catalogue_not_by_the_model():
    """A real ID beside invented facts is the harder half of grounding.

    The ID check passes here -- the place genuinely exists -- so nothing
    refuses the card. If a stop copied the model's own `place` object, a real
    restaurant would appear on screen with an address nobody can drive to and a
    price nobody agreed to. The existing itinerary tests check which places are
    named and in what order; neither notices the facts being swapped.
    """
    raw = {
        "kind": "itinerary",
        "payload": {
            "title": "Tối nay",
            "stops": [
                {
                    "place_id": "p-tiem-nuong",
                    "time_text": "19:00",
                    "note": "Ăn",
                    "place": {
                        "id": "p-tiem-nuong",
                        "name": "Quán Không Có Thật",
                        "address": "1 Đường Bịa, Sao Hoả",
                        "price_min_vnd": 5_000,
                        "price_max_vnd": 9_000,
                    },
                },
            ],
        },
    }

    card = ground_card(raw, _catalogue())

    stop = card["payload"]["stops"][0]
    assert set(stop) == {"time_text", "note", "place"}
    assert stop["place"] == {
        "id": "p-tiem-nuong",
        "name": "Tiệm Nướng Xóm Lào",
        "address": "27/1 Yersin, TP. Đà Lạt",
        "price_min_vnd": 200_000,
        "price_max_vnd": 250_000,
    }
    assert "Quán Không Có Thật" not in str(card)
    assert "Sao Hoả" not in str(card)


def _two_day_stops(count: int) -> list[dict]:
    """A plan long enough that a display limit has to decide something."""
    places = ["p-tiem-nuong", "p-cafe-suong"]
    return [
        {
            "place_id": places[index % 2],
            "time_text": f"Ngày {index // 4 + 1} · {8 + index}:00",
            "note": f"Chặng {index + 1}",
        }
        for index in range(count)
    ]


def test_an_itinerary_longer_than_the_display_limit_never_drops_a_stop_in_silence():
    """"Ghi rõ từng khung giờ của cả hai ngày" is the ordinary request here.

    Two days is routinely more than six stops, and the payload named only
    `title` and `stops`, so `stops[:MAX_STOPS]` dropped the tail with nothing on
    the card admitting it. The group read one day and believed that was the
    whole plan. A card may show fewer stops than the model planned, but it may
    never let a stop vanish without accounting for it.
    """
    raw = {
        "kind": "itinerary",
        "payload": {"title": "Hai ngày ở Đà Lạt", "stops": _two_day_stops(8)},
    }

    card = ground_card(raw, _catalogue())

    payload = card["payload"]
    shown = payload["stops"]
    omitted = payload.get("omitted_stop_count", 0)
    assert omitted == 8 - len(shown), "a cut stop must be counted on the card"
    assert [stop["note"] for stop in shown] == [
        f"Chặng {index + 1}" for index in range(len(shown))
    ]


def test_an_itinerary_short_enough_to_show_whole_carries_no_cut_flag():
    """The control half: without it, "flags when it cuts" and "flags always"
    are the same green.
    """
    raw = {
        "kind": "itinerary",
        "payload": {"title": "Tối nay", "stops": _two_day_stops(3)},
    }

    card = ground_card(raw, _catalogue())

    payload = card["payload"]
    assert len(payload["stops"]) == 3
    assert set(payload) == {"title", "stops"}


def _wide_catalogue(count: int) -> list[dict]:
    return [
        {
            "id": f"p-quan-{index}",
            "name": f"Quán Số {index}",
            "address": f"{index} Trần Phú, TP. Đà Lạt",
            "price_min_vnd": 40_000,
            "price_max_vnd": 90_000,
        }
        for index in range(count)
    ]


def test_a_places_card_longer_than_the_display_limit_also_counts_what_it_cut():
    """The same defect with a different noun, fixed in the same breath.

    `unique_ids[:MAX_PLACES]` drops the tail exactly the way the stops slice
    did. Left alone this is simply the next bug report.
    """
    catalogue = _wide_catalogue(8)
    raw = {
        "kind": "places",
        "payload": {
            "intro": "Tám chỗ đáng thử",
            "place_ids": [place["id"] for place in catalogue],
        },
    }

    card = ground_card(raw, catalogue)

    payload = card["payload"]
    shown = payload["places"]
    assert payload.get("omitted_place_count", 0) == 8 - len(shown)


def test_a_repeated_place_id_is_not_reported_as_something_the_card_cut():
    """Dedup is normalisation, not omission.

    Counting duplicates as cut places would put "còn 3 chỗ nữa" on a card that
    is in fact showing everything the model chose -- a false alarm is the same
    kind of lie as a silent cut, and it teaches the group to ignore the notice.
    """
    catalogue = _wide_catalogue(3)
    raw = {
        "kind": "places",
        "payload": {
            "intro": "Ba chỗ",
            "place_ids": ["p-quan-0", "p-quan-0", "p-quan-1", "p-quan-2", "p-quan-1"],
        },
    }

    card = ground_card(raw, catalogue)

    payload = card["payload"]
    assert len(payload["places"]) == 3
    assert set(payload) == {"intro", "places"}
