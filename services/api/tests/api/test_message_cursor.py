"""The message cursor codec, tested where it is cheap to test.

A cursor is a promise to a client: hand this back and you continue exactly
where you stopped. Offset breaks that promise the moment somebody sends a
message mid-scroll, which is why the contract is a cursor from the first day
rather than after a client already depends on offsets.

The codec is pure -- two values in, one opaque string out -- so it does not
need PostgreSQL to be checked. What it DOES need is to refuse garbage loudly.
A cursor that silently decodes to "the beginning of time" reads as a working
page while quietly re-serving the whole history.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime, timedelta

from app.api.cursors import CursorError, decode_cursor, encode_cursor


class MessageCursorTests(unittest.TestCase):
    def test_a_cursor_round_trips_to_the_same_position(self):
        moment = datetime(2026, 8, 29, 12, 30, 45, 123456, tzinfo=UTC)
        message_id = uuid.uuid4()

        self.assertEqual(
            decode_cursor(encode_cursor(moment, message_id)), (moment, message_id)
        )

    def test_a_cursor_carries_no_padding_or_url_hostile_characters(self):
        """It travels in a query string. `+`, `/` and `=` do not survive that
        trip intact through every client we do not control."""
        cursor = encode_cursor(datetime.now(UTC), uuid.uuid4())

        self.assertNotIn("+", cursor)
        self.assertNotIn("/", cursor)
        self.assertNotIn("=", cursor)

    def test_two_positions_one_microsecond_apart_are_different_cursors(self):
        moment = datetime(2026, 8, 29, 12, 30, 45, 123456, tzinfo=UTC)
        message_id = uuid.uuid4()

        self.assertNotEqual(
            encode_cursor(moment, message_id),
            encode_cursor(moment + timedelta(microseconds=1), message_id),
        )

    def test_two_messages_at_the_same_instant_are_different_cursors(self):
        """`now()` inside one PostgreSQL transaction is the same value for
        every row it writes, so a timestamp alone is not a position."""
        moment = datetime(2026, 8, 29, 12, 30, 45, tzinfo=UTC)

        self.assertNotEqual(
            encode_cursor(moment, uuid.uuid4()), encode_cursor(moment, uuid.uuid4())
        )

    def test_garbage_is_refused_rather_than_decoded_to_the_beginning(self):
        for bad in ("", "not-a-cursor", "!!!!", "YWJj", "eyJhIjoxfQ"):
            with self.subTest(cursor=bad):
                with self.assertRaises(CursorError):
                    decode_cursor(bad)

    def test_a_cursor_with_a_valid_shape_but_an_unparseable_id_is_refused(self):
        import base64

        forged = base64.urlsafe_b64encode(
            b"2026-08-29T12:30:45+00:00|not-a-uuid"
        ).decode("ascii").rstrip("=")

        with self.assertRaises(CursorError):
            decode_cursor(forged)

    def test_a_decoded_moment_is_timezone_aware(self):
        """A naive datetime compared against a `timestamptz` column is how a
        page silently shifts by seven hours in this timezone."""
        moment = datetime(2026, 8, 29, 12, 30, 45, tzinfo=UTC)
        decoded, _ = decode_cursor(encode_cursor(moment, uuid.uuid4()))

        self.assertIsNotNone(decoded.tzinfo)


if __name__ == "__main__":
    unittest.main()
