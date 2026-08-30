"""F33 -- reading the room: what the group is talking about, right now.

F32 and F33 look like the same card and are not. F32 answers "it has been three
weeks, want to go out?" from *history*; F33 answers "you two just said you were
bored" from *the last few messages*. Same grounding, different evidence, so the
digest below is a separate function rather than a flag on `summarise_history`.

## Three refusals encoded here

**The companion does not read its own cards back.** `ai_card` messages are
dropped. A card that treats its own previous output as something the group said
is a feedback loop: suggestion two is built from suggestion one, drifts a little
further from anything a human typed, and every round makes the drift look
better evidenced than it is.

**Images are not conversation.** An `image` message has no body. Counting it as
a turn would let a group that shared four photos and said nothing trip a
suggestion whose whole premise is that they were talking.

**Nobody is named.** The digest carries `speaker_count`, never author ids or
display names. The count is what the card needs -- "a few of you are talking"
-- and a name in a model prompt is a real person's name leaving the group for
no gain the feature can point at.

## What the caller must still not do

`recent_lines` is private group text. It is what the model reads, and that is
the feature; it is **not** something to log, and it is deliberately absent from
the response basis. The counts are what the screen gets to print.
"""

from __future__ import annotations

from typing import Any

#: Messages the digest reads. Anything else is not somebody talking.
CONVERSATION_KIND = "text"

#: Turns handed to the model. Enough for "what are they on about" and short
#: enough that one long paste cannot become the entire prompt.
MAX_LINES = 12

#: Longest single line kept. A trimmed line is still evidence of a topic; an
#: untrimmed one is an unbounded string in somebody else's prompt.
MAX_LINE = 200

#: Below this the card stays quiet. One "hi" is not a conversation, and a
#: suggestion fired at it is the product interrupting rather than joining.
MIN_LINES = 2


class ConversationError(Exception):
    """Malformed message rows reached the digest."""


def summarise_conversation(messages: list[dict], *, member_count: int) -> dict:
    """The last few human turns of one group, bounded and unattributed.

    `messages` arrive newest-first -- the order `list_messages` returns -- and
    already scoped to one context. `member_count` is the number of ACTIVE
    members, counted by the caller from membership rows.

    Returns the digest in **oldest-first** order, because that is the order a
    conversation happened in and a model handed it backwards will reliably
    decide the last thing said was the first.

    `member_count` is reported as exactly that. The mockup's line reads "4
    người đang online", and this product has no presence signal: there is no
    session table, no heartbeat, nothing that knows who has the app open. A
    card that said "online" would be asserting a fact the server cannot
    observe, so the field is named for what it actually counts.
    """

    if isinstance(member_count, bool) or not isinstance(member_count, int):
        raise ConversationError("conversation_member_count_not_integer")

    lines: list[str] = []
    speakers: set[str] = set()
    for message in messages:
        if not isinstance(message, dict):
            raise ConversationError("conversation_message_malformed")
        if message.get("kind") != CONVERSATION_KIND:
            continue
        body = message.get("body")
        if not isinstance(body, str) or not body.strip():
            continue
        if len(lines) < MAX_LINES:
            lines.append(body.strip()[:MAX_LINE])
            author = message.get("author_id")
            if author is not None:
                speakers.add(str(author))

    lines.reverse()
    return {
        "recent_lines": lines,
        "message_count": len(lines),
        "speaker_count": len(speakers),
        "member_count": member_count,
    }


def has_conversation(digest: dict) -> bool:
    """Whether there is enough being said to answer at all.

    Two turns from one person is a person thinking out loud; the threshold is
    on turns and not on speakers so that a group where one member says "chán
    quá" twice still gets an answer, which is the case the spec draws.
    """

    return digest["message_count"] >= MIN_LINES
