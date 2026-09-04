"""What a chat message asks the companion to do (M3, ADR-0016 scope).

Pure: text in, a small dict out, no I/O. The service stores the human message
first and only then reads the intent, so a refused or rate-limited companion
never loses what the person typed.

## Grammar

- A command is the FIRST token of the message: `/plan`, `/chia-bill`
  (`/chiabill`), `/vote` (`/binh-chon`). Case-insensitive, NFC-normalised, and
  it must be followed by whitespace or the end -- `/planning` is a word, not a
  command, and `hôm nay /plan` is a sentence that mentions one.
- A mention is `@Rủ Đi` / `@rudi` / `@ru di` anywhere in the text.
- `/vote` carries `Câu hỏi? A | B | C`: the question up to the first `?`
  (inclusive) and 2..20 distinct options split on `|`. Without a `?` the first
  segment is the question. Anything else is `None`, and the caller says so
  instead of guessing a poll nobody asked for.

The returned `args` is the original text (NFC) after the command, so the
companion reads what the person wrote, not a lower-cased copy.
"""

from __future__ import annotations

import unicodedata
from typing import Literal, TypedDict

Intent = Literal["plan", "chia_bill", "vote", "mention"]

COMMANDS: dict[str, Intent] = {
    "/plan": "plan",
    "/chia-bill": "chia_bill",
    "/chiabill": "chia_bill",
    "/vote": "vote",
    "/binh-chon": "vote",
}
MENTIONS: tuple[str, ...] = ("@rủ đi", "@rudi", "@ru di")

MAX_QUESTION = 300
MAX_OPTION = 200
MIN_OPTIONS = 2
MAX_OPTIONS = 20


class ParsedIntent(TypedDict):
    intent: Intent
    args: str


class VoteSpec(TypedDict):
    question: str
    options: list[str]


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def parse_intent(body: str | None) -> ParsedIntent | None:
    """The command or mention in `body`, or `None` for an ordinary message."""
    if not isinstance(body, str):
        return None
    text = _nfc(body).strip()
    if not text:
        return None
    folded = text.casefold()
    for command, intent in COMMANDS.items():
        if folded == command or (
            folded.startswith(command) and folded[len(command)].isspace()
        ):
            return {"intent": intent, "args": text[len(command) :].strip()}
    if any(mention in folded for mention in MENTIONS):
        return {"intent": "mention", "args": text}
    return None


def parse_vote(args: str) -> VoteSpec | None:
    """`Câu hỏi? A | B | C` -> a question and 2..20 distinct options, else None."""
    text = _nfc(args).strip()
    if "|" not in text:
        return None
    if "?" in text:
        head, _, tail = text.partition("?")
        question = (head + "?").strip()
        raw_options = tail
    else:
        question, _, raw_options = text.partition("|")
        question = question.strip()
    options: list[str] = []
    seen: set[str] = set()
    for part in raw_options.split("|"):
        label = " ".join(part.split())
        if not label:
            continue
        if len(label) > MAX_OPTION:
            return None
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        options.append(label)
    # A bare `?` is punctuation, not a question.
    if not question.rstrip("?").strip() or len(question) > MAX_QUESTION:
        return None
    if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        return None
    return {"question": question, "options": options}
