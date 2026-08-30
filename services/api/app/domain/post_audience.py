"""F42. The four audiences a post can be addressed to, and who they reach.

Spec section F42 names four levels and stops there. What the spec does not say,
and what this module exists to pin down, is that they are a *vocabulary* and
not a ladder: `friends` and `group` reach disjoint sets of people, and neither
contains the other. Written as a ladder -- the obvious implementation, a rank
comparison like the one in `visibility.py` -- a person who shares a group with
the author reads posts addressed to the author's friends, which is a different
promise from the one the word on the button made.

## Why this module takes facts and not identities

`can_read` is handed `is_friend` and `is_group_member` as booleans that someone
else already proved. It cannot look them up and must not: the whole reason F42
is a privacy feature is that "who are your friends" and "who is in this group"
are answers only the server holds, read from `friend_requests` and
`memberships` at the moment of the read. A version of this function that
accepted a list of friend ids would work identically against a list supplied by
the caller, and the caller is the one person whose claim about their own
membership is worth nothing.

That is also why `friends` is not frozen at write time. Unfriending someone has
to take away what they can see; a recipient list computed when the post was
written would keep them in it forever.

Pure functions over plain dicts. No I/O, no ORM, no framework.
"""

from __future__ import annotations

__all__ = [
    "AUDIENCES",
    "DEFAULT_AUDIENCE",
    "AudienceError",
    "can_read",
    "check_writable",
    "needs_context",
]

#: Narrowest first, purely so the tuple reads in a sensible order. Nothing in
#: this module compares two audiences by position, and nothing should: see the
#: module docstring on why these are not a ladder.
AUDIENCES = ("only_me", "friends", "group", "public")

#: What a client that says nothing gets. The narrowest level that is still a
#: post rather than a note to oneself would be `friends`; this picks
#: `only_me` instead, because the cost of guessing too narrow is that somebody
#: re-posts, and the cost of guessing too wide cannot be taken back.
DEFAULT_AUDIENCE = "only_me"


class AudienceError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def needs_context(audience: str) -> bool:
    """Only `group` names a group. Everything else addresses people."""
    return audience == "group"


def check_writable(audience: str, context_id: object | None) -> None:
    """Refuse a post whose audience and target do not agree.

    Mirrored by the `audience_matches_target` CHECK constraint on the table.
    Two spellings of one rule, deliberately: change either and change both.
    The constraint is what makes the rule true of rows written by anything
    that skips this layer; this is what makes the refusal a 422 instead of an
    IntegrityError surfacing as a 500.
    """
    if audience not in AUDIENCES:
        raise AudienceError("UNKNOWN_AUDIENCE")
    if needs_context(audience) and context_id is None:
        raise AudienceError("GROUP_AUDIENCE_NEEDS_CONTEXT")
    if not needs_context(audience) and context_id is not None:
        # A `only_me` post carrying a group id is a row that looks group-scoped
        # to every future query written by someone who did not read this file.
        raise AudienceError("CONTEXT_NOT_ADDRESSABLE")


def can_read(
    post: dict,
    *,
    reader_id: str,
    is_friend: bool,
    is_group_member: bool,
) -> bool:
    """Whether one reader may see one post. The only place this is decided.

    `is_friend` means "reader and author are friends *now*", and
    `is_group_member` means "reader is in the group this post names *now*".
    Both are the caller's to prove, and both are ignored for audiences they do
    not apply to -- that asymmetry is the rule the `only_me` tests are about.
    """
    audience = post.get("audience")
    if audience not in AUDIENCES:
        # Fail closed, the same way `can_view_history` does. An audience string
        # this module does not recognise is a fact nobody proved, and reading a
        # missing fact as permissive is how a schema change becomes a leak.
        return False

    # The author is the one reader every audience includes, `only_me` included.
    # Checked first so no audience branch has to remember to allow it.
    if reader_id == post.get("author_id"):
        return True

    if audience == "public":
        return True
    if audience == "friends":
        return is_friend
    if audience == "group":
        # `is_group_member` is a claim about the group this post names. With no
        # group named there is nothing for it to be a claim about, so it is not
        # evidence of anything and the post stays with its author.
        return post.get("context_id") is not None and is_group_member
    # `only_me`, and it reached here, so the reader is not the author.
    return False
