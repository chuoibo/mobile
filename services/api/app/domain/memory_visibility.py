"""Decide who may see one row on a context's memory wall.

Context membership is always the floor: visibility can narrow access inside a
group, but it cannot widen access past ``view_group_memories``. There is no
cross-group read surface in the product yet, so ``public`` currently grants
nothing beyond ``group``. The value is stored so a future public feed has a
visibility level to read; it must not be described as wider today.

Pure functions over plain dictionaries. No I/O, ORM, or web framework.
"""

from __future__ import annotations

__all__ = ["can_view_memory"]

_LEVELS = frozenset({"only_me", "friends", "group", "public"})


def _is_accepted_edge(edge: object, author_id: object, viewer_id: object) -> bool:
    if not isinstance(edge, dict) or edge.get("state") != "accepted":
        return False

    requester_id = edge.get("requester_id")
    addressee_id = edge.get("addressee_id")
    return (requester_id == author_id and addressee_id == viewer_id) or (
        requester_id == viewer_id and addressee_id == author_id
    )


def can_view_memory(*, memory: dict, viewer: dict) -> bool:
    """Return whether ``viewer`` may see ``memory`` within its context.

    ``viewer`` carries authoritative facts resolved by the caller:
    ``person_id``, ``is_context_member``, and an optional ``friend_edge``.
    Unknown or incomplete facts fail closed.
    """
    visibility = memory.get("visibility")
    author_id = memory.get("author_id")
    viewer_id = viewer.get("person_id")

    if visibility not in _LEVELS or viewer.get("is_context_member") is not True:
        return False
    if author_id is None or viewer_id is None:
        return False
    if viewer_id == author_id:
        return True
    if visibility == "friends":
        return _is_accepted_edge(viewer.get("friend_edge"), author_id, viewer_id)
    return visibility in {"group", "public"}
