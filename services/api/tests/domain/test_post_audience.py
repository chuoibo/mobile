"""F42. Who may read a post, decided in one place.

The table at the bottom is the point of this file. Each audience is asserted
against *every* kind of reader, not only the one reader that audience is named
after -- a rule that says "a friend may read a `friends` post" is only half a
rule, and the missing half is the one that leaks.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.domain.post_audience import (  # noqa: E402
    AUDIENCES,
    AudienceError,
    can_read,
    check_writable,
)

AUTHOR = "1aa00000-aaaa-4aaa-8aaa-0000a0000001"
FRIEND = "2bb00000-bbbb-4bbb-8bbb-0000b0000001"
GROUPMATE = "3cc00000-cccc-4ccc-8ccc-0000c0000001"
STRANGER = "4dd00000-dddd-4ddd-8ddd-0000d0000001"
GROUP = "9ee00000-eeee-4eee-8eee-0000e0000009"


def post(audience: str, *, context_id: str | None = None) -> dict:
    return {"author_id": AUTHOR, "audience": audience, "context_id": context_id}


class Vocabulary(unittest.TestCase):
    def test_exactly_the_four_levels_the_spec_names(self):
        self.assertEqual(AUDIENCES, ("only_me", "friends", "group", "public"))

    def test_an_unknown_audience_is_read_by_nobody(self):
        """Fail closed. An unrecognised string is a fact nobody proved."""
        for reader in (AUTHOR, FRIEND, GROUPMATE, STRANGER):
            with self.subTest(reader=reader):
                self.assertFalse(
                    can_read(
                        post("everyone_lol"),
                        reader_id=reader,
                        is_friend=True,
                        is_group_member=True,
                    )
                )


class OnlyMe(unittest.TestCase):
    """The sharpest rule in the feature, so it gets its own class."""

    def test_the_author_reads_their_own(self):
        self.assertTrue(
            can_read(
                post("only_me"),
                reader_id=AUTHOR,
                is_friend=False,
                is_group_member=False,
            )
        )

    def test_no_proven_fact_opens_it(self):
        """Being a friend and a groupmate at once still does not open it.

        This is the shape the bug takes: `only_me` handled by falling through
        to whichever check ran last, so a reader who happens to satisfy some
        *other* audience's predicate reads a post addressed to nobody.
        """
        for reader in (FRIEND, GROUPMATE, STRANGER):
            with self.subTest(reader=reader):
                self.assertFalse(
                    can_read(
                        post("only_me"),
                        reader_id=reader,
                        is_friend=True,
                        is_group_member=True,
                    )
                )


class Friends(unittest.TestCase):
    def test_a_friend_reads_it(self):
        self.assertTrue(
            can_read(
                post("friends"),
                reader_id=FRIEND,
                is_friend=True,
                is_group_member=False,
            )
        )

    def test_a_stranger_does_not(self):
        self.assertFalse(
            can_read(
                post("friends"),
                reader_id=STRANGER,
                is_friend=False,
                is_group_member=False,
            )
        )

    def test_sharing_a_group_is_not_friendship(self):
        """Two people in one group have not agreed to be friends."""
        self.assertFalse(
            can_read(
                post("friends"),
                reader_id=GROUPMATE,
                is_friend=False,
                is_group_member=True,
            )
        )

    def test_the_author_reads_it_without_being_their_own_friend(self):
        self.assertTrue(
            can_read(
                post("friends"),
                reader_id=AUTHOR,
                is_friend=False,
                is_group_member=False,
            )
        )


class Group(unittest.TestCase):
    def test_a_member_reads_it(self):
        self.assertTrue(
            can_read(
                post("group", context_id=GROUP),
                reader_id=GROUPMATE,
                is_friend=False,
                is_group_member=True,
            )
        )

    def test_a_non_member_does_not(self):
        self.assertFalse(
            can_read(
                post("group", context_id=GROUP),
                reader_id=STRANGER,
                is_friend=False,
                is_group_member=False,
            )
        )

    def test_being_a_friend_of_the_author_is_not_membership(self):
        """`friends` and `group` are different audiences, not a hierarchy."""
        self.assertFalse(
            can_read(
                post("group", context_id=GROUP),
                reader_id=FRIEND,
                is_friend=True,
                is_group_member=False,
            )
        )

    def test_a_group_post_naming_no_group_is_read_by_nobody_but_its_author(self):
        """There is no membership of `None`, so the predicate cannot be true.

        The database refuses to store this row. The rule is spelled here too
        because a reader that trusts `is_group_member` alone would accept a
        caller's claim to be a member of nothing.
        """
        self.assertFalse(
            can_read(
                post("group", context_id=None),
                reader_id=GROUPMATE,
                is_friend=False,
                is_group_member=True,
            )
        )
        self.assertTrue(
            can_read(
                post("group", context_id=None),
                reader_id=AUTHOR,
                is_friend=False,
                is_group_member=False,
            )
        )


class Public(unittest.TestCase):
    def test_anybody_reads_it(self):
        for reader in (AUTHOR, FRIEND, GROUPMATE, STRANGER):
            with self.subTest(reader=reader):
                self.assertTrue(
                    can_read(
                        post("public"),
                        reader_id=reader,
                        is_friend=False,
                        is_group_member=False,
                    )
                )


class EveryAudienceAgainstEveryReader(unittest.TestCase):
    """The whole matrix, written out. No cell is inferred from another."""

    #: (audience, reader, is_friend, is_group_member) -> may read
    MATRIX = {
        ("only_me", AUTHOR, False, False): True,
        ("only_me", FRIEND, True, False): False,
        ("only_me", GROUPMATE, False, True): False,
        ("only_me", STRANGER, False, False): False,
        ("friends", AUTHOR, False, False): True,
        ("friends", FRIEND, True, False): True,
        ("friends", GROUPMATE, False, True): False,
        ("friends", STRANGER, False, False): False,
        ("group", AUTHOR, False, False): True,
        ("group", FRIEND, True, False): False,
        ("group", GROUPMATE, False, True): True,
        ("group", STRANGER, False, False): False,
        ("public", AUTHOR, False, False): True,
        ("public", FRIEND, True, False): True,
        ("public", GROUPMATE, False, True): True,
        ("public", STRANGER, False, False): True,
    }

    def test_matrix(self):
        for (audience, reader, friend, member), expected in self.MATRIX.items():
            with self.subTest(audience=audience, reader=reader):
                self.assertIs(
                    can_read(
                        post(
                            audience,
                            context_id=GROUP if audience == "group" else None,
                        ),
                        reader_id=reader,
                        is_friend=friend,
                        is_group_member=member,
                    ),
                    expected,
                )

    def test_the_matrix_covers_every_audience(self):
        """Stops a new audience from being added with no row here."""
        self.assertEqual({row[0] for row in self.MATRIX}, set(AUDIENCES))


class Writable(unittest.TestCase):
    """The write-side shape, mirrored by a CHECK constraint in the schema."""

    def test_a_group_post_must_name_its_group(self):
        with self.assertRaises(AudienceError) as caught:
            check_writable("group", None)
        self.assertEqual(caught.exception.code, "GROUP_AUDIENCE_NEEDS_CONTEXT")

    def test_a_non_group_post_may_not_name_a_group(self):
        """Otherwise `only_me` carries a group id nobody ever checks."""
        for audience in ("only_me", "friends", "public"):
            with self.subTest(audience=audience):
                with self.assertRaises(AudienceError) as caught:
                    check_writable(audience, GROUP)
                self.assertEqual(caught.exception.code, "CONTEXT_NOT_ADDRESSABLE")

    def test_an_unknown_audience_cannot_be_written(self):
        with self.assertRaises(AudienceError) as caught:
            check_writable("everyone_lol", None)
        self.assertEqual(caught.exception.code, "UNKNOWN_AUDIENCE")

    def test_the_four_legal_shapes_pass(self):
        check_writable("group", GROUP)
        for audience in ("only_me", "friends", "public"):
            check_writable(audience, None)


if __name__ == "__main__":
    unittest.main()
