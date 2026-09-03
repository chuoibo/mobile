"""`parse_intent` / `parse_vote`: the grammar the chat composer relies on.

Pure functions, so every edge is a one-liner here: a command must be the first
token, `/planning` is a word, a mention may sit anywhere, and a vote without
two distinct options is not a vote.
"""

from __future__ import annotations

import unicodedata

import pytest

from app.domain.chat_intent import parse_intent, parse_vote


@pytest.mark.parametrize(
    ("body", "intent", "args"),
    [
        ("/plan đi Đà Lạt cuối tuần", "plan", "đi Đà Lạt cuối tuần"),
        ("/PLAN", "plan", ""),
        ("  /Plan\nsáng mai", "plan", "sáng mai"),
        ("/chia-bill", "chia_bill", ""),
        ("/chiabill tối qua", "chia_bill", "tối qua"),
        ("/vote Ăn gì? Bún bò | Phở", "vote", "Ăn gì? Bún bò | Phở"),
        ("/binh-chon Đi đâu? A | B", "vote", "Đi đâu? A | B"),
        ("@Rủ Đi gợi ý cafe đi", "mention", "@Rủ Đi gợi ý cafe đi"),
        ("tối nay @rudi chọn quán giúp", "mention", "tối nay @rudi chọn quán giúp"),
        ("@RU DI ơi", "mention", "@RU DI ơi"),
    ],
)
def test_commands_and_mentions_are_recognised(body, intent, args):
    assert parse_intent(body) == {"intent": intent, "args": args}


@pytest.mark.parametrize(
    "body",
    [
        "/planning cuối tuần",  # a word, not a command
        "hôm nay /plan nhé",  # a sentence that mentions a command
        "/vote2 A | B",
        "plan đi chơi",
        "chia bill đi",
        "",
        "   ",
        None,
    ],
)
def test_ordinary_text_has_no_intent(body):
    assert parse_intent(body) is None


def test_decomposed_unicode_is_normalised_before_matching():
    nfd = unicodedata.normalize("NFD", "@Rủ Đi gợi ý")
    assert nfd != "@Rủ Đi gợi ý"
    parsed = parse_intent(nfd)
    assert parsed is not None and parsed["intent"] == "mention"
    # And what the companion reads back is NFC, not the decomposed bytes.
    assert parsed["args"] == "@Rủ Đi gợi ý"


def test_args_keep_the_persons_own_casing():
    assert parse_intent("/Plan Đà Lạt")["args"] == "Đà Lạt"


@pytest.mark.parametrize(
    ("args", "question", "options"),
    [
        (
            "Ăn gì tối nay? Bún bò | Phở | Cơm tấm",
            "Ăn gì tối nay?",
            ["Bún bò", "Phở", "Cơm tấm"],
        ),
        ("Đi đâu | Đà Lạt | Vũng Tàu", "Đi đâu", ["Đà Lạt", "Vũng Tàu"]),
        (
            "Mấy giờ? 7h |  8h  || 7H",
            "Mấy giờ?",
            ["7h", "8h"],
        ),  # blanks dropped, duplicates folded
    ],
)
def test_vote_grammar(args, question, options):
    assert parse_vote(args) == {"question": question, "options": options}


@pytest.mark.parametrize(
    "args",
    [
        "Ăn gì?",  # no separator at all
        "Ăn gì? Bún bò",  # one option
        "Ăn gì? Bún bò | bún bò",  # one option after folding
        "? A | B",  # no question
        "Q? " + " | ".join(f"o{i}" for i in range(21)),  # 21 options
        "Q? " + ("x" * 201) + " | y",  # an option too long for the vote table
        "A | B",  # question with a single option
    ],
)
def test_malformed_votes_are_none_not_guesses(args):
    assert parse_vote(args) is None
