"""F33 -- what the companion is allowed to read, and what it must not carry.

Pure tier. It pins the three refusals the digest encodes and the fact that no
identity survives into it. Whether a stranger can reach the route at all is a
question about membership rows, and it is answered in
`tests/postgres/test_contextual_suggestion_postgres.py`.
"""

from __future__ import annotations

import pytest

from app.domain.conversation import (
    MAX_LINE,
    MAX_LINES,
    ConversationError,
    has_conversation,
    summarise_conversation,
)


def _text(body: str, author: str = "nam") -> dict:
    return {"kind": "text", "body": body, "author_id": author}


class TestWhatCountsAsConversation:
    def test_an_ai_card_is_not_something_the_group_said(self):
        """The companion must not read its own output back as evidence.

        Left in, suggestion two is built from suggestion one and every round
        drifts further from anything a human typed -- while looking better
        evidenced each time, because the transcript keeps growing.
        """

        digest = summarise_conversation(
            [
                {"kind": "ai_card", "body": "Đi ăn nướng nhé?", "author_id": None},
                _text("Chán quá"),
            ],
            member_count=4,
        )
        assert digest["recent_lines"] == ["Chán quá"]
        assert digest["message_count"] == 1

    def test_a_shared_photograph_is_not_a_turn(self):
        digest = summarise_conversation(
            [
                {"kind": "image", "body": None, "author_id": "nam"},
                _text("Đi đâu không?"),
            ],
            member_count=3,
        )
        assert digest["message_count"] == 1

    def test_an_empty_or_whitespace_body_is_dropped(self):
        digest = summarise_conversation(
            [_text("   "), {"kind": "text", "body": None, "author_id": "x"}],
            member_count=2,
        )
        assert digest["recent_lines"] == []


class TestOrder:
    def test_newest_first_in_oldest_first_out(self):
        """A model handed a conversation backwards decides the last thing said
        was the first, and answers the wrong sentence."""

        digest = summarise_conversation(
            [_text("Đi đâu không?"), _text("Chán quá")], member_count=2
        )
        assert digest["recent_lines"] == ["Chán quá", "Đi đâu không?"]


class TestNobodyIsNamed:
    def test_the_digest_carries_a_speaker_count_and_no_identities(self):
        digest = summarise_conversation(
            [_text("a", "nam"), _text("b", "kiet"), _text("c", "nam")], member_count=5
        )
        assert digest["speaker_count"] == 2
        assert set(digest) == {
            "recent_lines",
            "message_count",
            "speaker_count",
            "member_count",
        }
        assert "nam" not in repr(digest["recent_lines"])

    def test_member_count_is_reported_as_membership_not_as_presence(self):
        """The mockup says "4 người đang online". Nothing in this product
        observes presence, so the field counts what it can actually count."""

        assert summarise_conversation([], member_count=4)["member_count"] == 4


class TestBounds:
    def test_only_the_most_recent_turns_are_kept(self):
        digest = summarise_conversation(
            [_text(f"line {index}") for index in range(MAX_LINES + 10)], member_count=2
        )
        assert digest["message_count"] == MAX_LINES

    def test_a_long_line_is_trimmed_rather_than_passed_through(self):
        digest = summarise_conversation([_text("x" * 5000)], member_count=2)
        assert len(digest["recent_lines"][0]) == MAX_LINE


class TestThreshold:
    def test_one_turn_is_not_a_conversation(self):
        assert not has_conversation(summarise_conversation([_text("hi")], member_count=3))

    def test_two_turns_from_one_person_is_still_a_conversation(self):
        """The spec's own example is one person saying they are bored, so the
        threshold counts turns and not distinct speakers."""

        digest = summarise_conversation(
            [_text("Chán quá", "nam"), _text("Đi đâu không", "nam")], member_count=3
        )
        assert has_conversation(digest)

    def test_an_empty_group_chat_is_not_a_conversation(self):
        assert not has_conversation(summarise_conversation([], member_count=4))


class TestMalformed:
    def test_a_message_that_is_not_a_mapping_is_refused(self):
        with pytest.raises(ConversationError):
            summarise_conversation(["chán quá"], member_count=2)

    @pytest.mark.parametrize("bad", [True, "4", 4.0, None])
    def test_a_member_count_that_is_not_an_integer_is_refused(self, bad):
        with pytest.raises(ConversationError):
            summarise_conversation([], member_count=bad)
