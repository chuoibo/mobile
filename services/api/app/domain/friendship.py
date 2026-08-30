"""The friend graph, as a state machine. F03 and F04.

One edge between two people, and the rule that makes it an edge rather than a
claim: **the addressee decides**. A friendship exists when the person who was
asked said yes. Nothing else creates one.

That sentence is the whole reason this module is pure and separate. Written the
ordinary way -- a `friends` table an endpoint inserts into -- "add friend" is a
write the requester performs on somebody else's social graph, and every later
reader (who may see the trip, who may be invited, whose name autocompletes)
inherits a relationship the other person never agreed to. Section 9's confused
deputy, wearing a friendly word.

So there is no `add_friend`. There is `open_request`, which creates a PENDING
edge and grants nothing, and `decide`, which only the addressee may call.
`are_friends` is derived from the resulting state, never stored as its own
truth -- the same shape as invariant 3 for money: the relationship is
recomputable from the events that produced it.

## The four states are the spec's, exactly

`feature_list.md` F04 lists pending, accepted, declined, blocked. They are not
four flags on a row; they are the four places an edge can rest, and the legal
moves between them are the table below.

    PENDING --accept--> ACCEPTED      addressee only
    PENDING --decline-> DECLINED      addressee only
    PENDING --block---> BLOCKED       addressee only
    ACCEPTED -block---> BLOCKED       either party -- friendship can end badly
    DECLINED -----> (reopen)          a new request, not a transition

DECLINED is deliberately not terminal: being turned down once is not a life
sentence, and the alternative is a product where a mistyped tap permanently
removes somebody from your reachable set. BLOCKED *is* terminal, because that
is what the word is for. `open_request` refuses to reopen a blocked edge, and
refuses it without saying who blocked whom -- see `BLOCKED_IS_SILENT`.

## Pair keys

`(A asks B)` and `(B asks A)` are the same edge, so state has to be keyed by an
unordered pair. `pair_key` sorts the two ids, which is what lets the database
enforce "at most one live edge per pair" with one unique index instead of two
rows racing each other into a friendship nobody can undo. The SQL index says
the same thing in `least()/greatest()`; keep the two spellings agreeing.

Pure: `dict` in, `dict` out. Raises `FriendshipError`. Imports nothing from
`app.db`, `app.api`, sqlalchemy or fastapi -- `tests/test_import_boundary.py`
parses this file to check that, so the check is not a promise.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "BLOCKED_IS_SILENT",
    "Decision",
    "FriendState",
    "FriendshipError",
    "are_friends",
    "decide",
    "is_live_edge",
    "open_request",
    "pair_key",
]


class FriendState(StrEnum):
    """The four rest states of one edge. F04's list, unchanged."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    BLOCKED = "blocked"


class Decision(StrEnum):
    """What an addressee may answer. Accepting is one of three, not the default."""

    ACCEPT = "accept"
    DECLINE = "decline"
    BLOCK = "block"


#: A blocked person must not be able to tell blocking apart from "no account",
#: "never answered", or "already asked". If the refusal named the block, the
#: block would announce itself to exactly the person it protects somebody from,
#: and the product would be teaching users that blocking is unsafe. So
#: `open_request` raises the same code for a blocked edge as for a duplicate
#: one, and the caller must map both to the same HTTP answer.
BLOCKED_IS_SILENT = "REQUEST_NOT_OPEN"


class FriendshipError(Exception):
    """A refusal with a stable code. The code is the contract; the text is not."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


#: States in which an edge still occupies the pair -- a new request may not be
#: opened alongside one of these. DECLINED is absent on purpose: that is the
#: state a person may ask again from.
_LIVE = (FriendState.PENDING, FriendState.ACCEPTED, FriendState.BLOCKED)


def pair_key(a: str, b: str) -> tuple[str, str]:
    """The unordered pair, canonically ordered.

    Sorted as strings, matching what `least()/greatest()` do to the same two
    values in the partial unique index. Two spellings of one rule is a risk;
    they are kept adjacent in the migration's comment for that reason.
    """
    if not a or not b:
        raise FriendshipError("PERSON_REQUIRED")
    if a == b:
        # Nobody friends themselves. Allowed, this becomes a self-edge that
        # every "who are my friends" query has to special-case forever.
        raise FriendshipError("SELF_EDGE")
    return (a, b) if a < b else (b, a)


def is_live_edge(state: str) -> bool:
    """True when this state still occupies the pair against a new request."""
    return FriendState(state) in _LIVE


def open_request(
    *, requester_id: str, addressee_id: str, existing: dict | None = None
) -> dict:
    """Open a PENDING edge from requester to addressee.

    `existing` is the current edge for this pair, if any, as previously
    returned by this module. Passing it is how the caller proves it looked --
    the parameter is not optional in spirit, only in signature, and the
    repository always reads before writing.

    Grants nothing. A PENDING edge is a question, and `are_friends` is False
    for it.
    """
    pair_key(requester_id, addressee_id)  # raises on self-edge / empty

    if existing is not None and is_live_edge(existing["state"]):
        # One code for pending, accepted and blocked alike. See
        # BLOCKED_IS_SILENT: distinguishing them here is what would leak the
        # block. "You already have a live edge with this person" is true in
        # all three cases and reveals nothing new to a legitimate caller,
        # because a legitimate caller can already see their own pending and
        # accepted edges by listing them.
        raise FriendshipError(BLOCKED_IS_SILENT)

    return {
        "requester_id": requester_id,
        "addressee_id": addressee_id,
        "state": str(FriendState.PENDING),
        "pair": list(pair_key(requester_id, addressee_id)),
    }


def decide(*, edge: dict, actor_id: str, decision: str) -> dict:
    """Answer a request. **Only the addressee may accept.**

    This function is the consent gate for the whole feature. The permission
    table refuses an actor who is not the addressee before the request reaches
    here, and this refuses it again on facts read from the row itself. Two
    layers because they fail differently: the table is data somebody could edit
    without reading this file, and this is logic somebody could call without
    going through a route.

    Blocking is the one answer either party may give, and the only one legal
    from ACCEPTED -- a friendship that has to end does not need the other
    side's permission to end.
    """
    answer = Decision(decision)
    state = FriendState(edge["state"])
    requester_id = edge["requester_id"]
    addressee_id = edge["addressee_id"]

    if actor_id not in (requester_id, addressee_id):
        raise FriendshipError("NOT_A_PARTY")

    if answer is Decision.BLOCK:
        if state is FriendState.BLOCKED:
            raise FriendshipError("ALREADY_BLOCKED")
        # Either party, from PENDING or ACCEPTED. A requester who realises they
        # asked the wrong person is also using this door.
        return {**edge, "state": str(FriendState.BLOCKED)}

    # Accept and decline are answers to a question, so they need a question.
    if state is not FriendState.PENDING:
        raise FriendshipError("NOT_PENDING")

    if actor_id != addressee_id:
        # The line the acceptance criteria mutate. A requester accepting their
        # own request is the entire failure mode this feature exists to
        # prevent: it is "add friend" with extra steps.
        raise FriendshipError("ONLY_ADDRESSEE_MAY_ANSWER")

    return {
        **edge,
        "state": str(
            FriendState.ACCEPTED if answer is Decision.ACCEPT else FriendState.DECLINED
        ),
    }


def are_friends(edge: dict | None) -> bool:
    """Derived, never stored. Only ACCEPTED is a friendship."""
    if edge is None:
        return False
    return FriendState(edge["state"]) is FriendState.ACCEPTED
