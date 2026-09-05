"""Which catalogue rows are safe to put in a model prompt (M9, ADR-0017).

`tests/api/test_places_prompt_boundary.py` was written as an alarm: it asserted
that every row reaching the Gemini prompt was one of the hard-coded literals in
`catalog.py`, and it said in its own docstring that the day place data stops
being a literal, the prompt-injection reproduced at
`tests/live/test_places_reason_quality_live.py` becomes reachable and must be
fixed *before the new source ships*. That day is M9: rows now come from a table
an importer fills from OpenStreetMap, which anybody in the world can edit.

So this module is the fix the alarm asked for. It is deliberately a **filter,
not an escape**: a row whose text tries to talk to the model is dropped from
the prompt entirely rather than quoted more carefully. The place still appears
on the screen -- it just gets no AI sentence, which is the honest outcome for a
row we are not willing to show a model.

What it does not claim: this is not a proof that no prompt injection exists.
It removes the reachable path this repo has actually reproduced, and it keeps
the row-level blast radius at one card.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

#: Fields a caller-facing prompt quotes. `id` is ours; coordinates are numbers.
FIELDS_IN_PROMPT = ("name", "address", "open_hours")
LIST_FIELDS_IN_PROMPT = ("kinds", "traits")

MAX_NAME_CHARS = 120
MAX_ADDRESS_CHARS = 200
MAX_ITEM_CHARS = 60

# Phrases that only appear in text written *at* a model. Matched on the folded
# form so «BỎ  QUA   MỌI HƯỚNG DẪN» and «bỏ qua mọi hướng dẫn» are the same
# string. Vietnamese and English, because both reach a Vietnamese map.
INSTRUCTION_PATTERNS = (
    r"bo qua .{0,20}huong dan",
    r"quen .{0,20}huong dan",
    r"lam theo .{0,20}sau day",
    r"tra loi .{0,20}hop",
    r"ignore .{0,30}(instruction|prompt|above|previous)",
    r"disregard .{0,30}(instruction|prompt|above|previous)",
    r"system prompt",
    r"you are (now|a) ",
    r"</?(system|assistant|user)>",
    r"```",
)

_INSTRUCTION = re.compile("|".join(INSTRUCTION_PATTERNS))


def _fold(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace. Comparison form only."""
    khong_dau = "".join(
        ch
        for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )
    return re.sub(r"\s+", " ", khong_dau.replace("đ", "d").replace("Đ", "D")).lower()


def field_is_safe(value: Any, *, max_chars: int) -> bool:
    """One string field. Non-strings pass: they are not text put to a model."""
    if value is None:
        return True
    if not isinstance(value, str):
        return True
    if len(value) > max_chars:
        return False
    # A control character or a newline is how injected text pretends to start a
    # new section of the prompt. Real venue names contain neither.
    if any(unicodedata.category(ch) == "Cc" for ch in value):
        return False
    return _INSTRUCTION.search(_fold(value)) is None


def place_is_safe_for_prompt(place: dict[str, Any]) -> bool:
    """Whether this row may be shown to a model at all."""
    limits = {
        "name": MAX_NAME_CHARS,
        "address": MAX_ADDRESS_CHARS,
        "open_hours": MAX_ITEM_CHARS,
    }
    for field in FIELDS_IN_PROMPT:
        if not field_is_safe(place.get(field), max_chars=limits[field]):
            return False
    for field in LIST_FIELDS_IN_PROMPT:
        items = place.get(field) or []
        if not isinstance(items, list) or len(items) > 20:
            return False
        for item in items:
            if not field_is_safe(item, max_chars=MAX_ITEM_CHARS):
                return False
    return True


def safe_places(places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The rows a prompt may quote, in the order they arrived."""
    return [place for place in places if place_is_safe_for_prompt(place)]
