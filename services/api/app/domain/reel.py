"""Grounding for F37 AI-picked trip keepsakes.

This is the same boundary ``suggestion.py`` applies to places, repeated for a
different wire shape rather than weakened by reuse through flags:

* The model copies identifiers; the server owns facts.  It may write only the
  reel title and one note per pick.  Image paths, captions, place names,
  timestamps, and social counts are attached from the offered server rows.
* One identifier outside the offered set sinks the whole answer.  The check is
  made over the model's complete list, before duplicate detection and before
  the display cap, so neither operation can pardon a fabricated final pick.
* A title, a note, and the memory they describe are one claim.  A partial claim
  is refused rather than rendered as an endorsement the model did not make.
* The returned payload is rebuilt from a whitelist.  A model-authored field
  cannot become a client feature until a person adds it here deliberately.

Only metadata reaches the model.  No image bytes and no image URLs are needed
to choose from what the group said and did around a memory; those URLs remain
server-owned facts and are attached only after grounding succeeds.
"""

from __future__ import annotations

from typing import Any

__all__ = ["MAX_NOTE", "MAX_PICKS", "MAX_TITLE", "ReelError", "ground_reel"]

MAX_PICKS = 6
MAX_TITLE = 120
MAX_NOTE = 240


class ReelError(Exception):
    """A refused reel, carried as a closed code instead of private text."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _incomplete() -> ReelError:
    return ReelError("incomplete_pick")


def _bounded_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        raise _incomplete()
    trimmed = value.strip()
    if not trimmed:
        raise _incomplete()
    return trimmed[:limit]


def ground_reel(raw: Any, memories: list[dict]) -> dict:
    """Attach server-owned memory facts to one complete, grounded AI reel.

    The caller already scoped ``memories`` to one authorised trip.  This pure
    function has no repository and cannot widen that scope; it only decides
    whether the model copied identifiers from the rows it was offered.
    """

    if not isinstance(raw, dict):
        raise _incomplete()
    raw_picks = raw.get("picks")
    if not isinstance(raw_picks, list):
        raise _incomplete()

    memory_by_id = {
        str(memory["id"]): memory
        for memory in memories
        if isinstance(memory, dict) and memory.get("id") is not None
    }

    entries: list[tuple[str, dict]] = []
    for raw_pick in raw_picks:
        if not isinstance(raw_pick, dict):
            raise _incomplete()
        memory_id = raw_pick.get("memory_id")
        if not isinstance(memory_id, str) or not memory_id:
            raise _incomplete()
        entries.append((memory_id, raw_pick))

    # Inspect the complete answer first.  Deduplication and the display cap
    # both shorten it, and neither may hide an identifier the server did not
    # offer.
    if any(memory_id not in memory_by_id for memory_id, _ in entries):
        raise ReelError("unknown_memory")

    seen: set[str] = set()
    for memory_id, _ in entries:
        if memory_id in seen:
            raise ReelError("duplicate_memory")
        seen.add(memory_id)

    if len(entries) > MAX_PICKS:
        raise ReelError("too_many_picks")
    if not entries:
        raise ReelError("empty_reel")

    title = _bounded_text(raw.get("title"), MAX_TITLE)
    picks: list[dict] = []
    for memory_id, raw_pick in entries:
        note = _bounded_text(raw_pick.get("note"), MAX_NOTE)
        memory = memory_by_id[memory_id]
        # Whitelist, never a copy of either untrusted input.  The identifier is
        # taken from the server row too, so the wire never treats model text as
        # the authoritative spelling of a fact it already owns.
        picks.append(
            {
                "memory_id": memory["id"],
                "image_url": memory.get("image_url"),
                "caption": memory.get("caption"),
                "place_name": memory.get("place_name"),
                "created_at": memory.get("created_at"),
                "reaction_count": memory.get("reaction_count", 0),
                "comment_count": memory.get("comment_count", 0),
                "note": note,
            }
        )

    return {"title": title, "picks": picks}
