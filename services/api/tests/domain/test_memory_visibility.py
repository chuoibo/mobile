"""F42's per-memory visibility decision, independent of HTTP and SQL."""

from __future__ import annotations

import pytest

from app.domain.memory_visibility import can_view_memory

# Letter-bearing hex, not all-digit UUIDs: the repo guard strips separators and
# reads 32 consecutive digits as an account number, so an all-digit UUID makes
# the commit unstageable.
AUTHOR = "1aa00000-aaaa-4aaa-8aaa-0000a0000042"
VIEWER = "2bb00000-bbbb-4bbb-8bbb-0000b0000042"
STRANGER = "3cc00000-cccc-4ccc-8ccc-0000c0000042"


def _viewer(relation: str) -> dict:
    person_id = AUTHOR if relation.startswith("author") else VIEWER
    is_context_member = relation != "non_member" and relation != "author_non_member"
    friend_edge = None
    if relation in {"accepted_friend", "pending_friend"}:
        friend_edge = {
            "requester_id": AUTHOR,
            "addressee_id": VIEWER,
            "state": "accepted" if relation == "accepted_friend" else "pending",
        }
    return {
        "person_id": person_id,
        "is_context_member": is_context_member,
        "friend_edge": friend_edge,
    }


@pytest.mark.parametrize(
    ("visibility", "relation", "expected"),
    [
        ("only_me", "author", True),
        ("only_me", "accepted_friend", False),
        ("only_me", "pending_friend", False),
        ("only_me", "context_member", False),
        ("only_me", "non_member", False),
        ("friends", "author", True),
        ("friends", "accepted_friend", True),
        ("friends", "pending_friend", False),
        ("friends", "context_member", False),
        ("friends", "non_member", False),
        ("group", "author", True),
        ("group", "accepted_friend", True),
        ("group", "pending_friend", True),
        ("group", "context_member", True),
        ("group", "non_member", False),
        ("public", "author", True),
        ("public", "accepted_friend", True),
        ("public", "pending_friend", True),
        ("public", "context_member", True),
        ("public", "non_member", False),
    ],
)
def test_visibility_matrix(visibility, relation, expected):
    memory = {"author_id": AUTHOR, "visibility": visibility}

    assert can_view_memory(memory=memory, viewer=_viewer(relation)) is expected


@pytest.mark.parametrize("visibility", ["only_me", "friends", "group", "public"])
def test_membership_gate_remains_the_floor_for_an_author_who_left(visibility):
    memory = {"author_id": AUTHOR, "visibility": visibility}

    assert can_view_memory(memory=memory, viewer=_viewer("author_non_member")) is False


def test_an_accepted_edge_for_other_people_does_not_grant_friend_visibility():
    memory = {"author_id": AUTHOR, "visibility": "friends"}
    viewer = _viewer("accepted_friend")
    viewer["friend_edge"] = {
        "requester_id": VIEWER,
        "addressee_id": STRANGER,
        "state": "accepted",
    }

    assert can_view_memory(memory=memory, viewer=viewer) is False


@pytest.mark.parametrize("state", ["pending", "declined", "blocked"])
def test_only_an_accepted_edge_grants_friend_visibility(state):
    memory = {"author_id": AUTHOR, "visibility": "friends"}
    viewer = _viewer("accepted_friend")
    viewer["friend_edge"]["state"] = state

    assert can_view_memory(memory=memory, viewer=viewer) is False


def test_unknown_visibility_fails_closed():
    memory = {"author_id": AUTHOR, "visibility": "typo"}

    assert can_view_memory(memory=memory, viewer=_viewer("context_member")) is False
