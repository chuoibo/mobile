"""The consent rule, tested where it is cheapest to test.

Every case here is about one sentence: a friendship exists only when the person
who was asked said yes. The API-level test proves the route refuses; this
proves the rule itself refuses, so that a future route that forgets to check
still cannot produce an accepted edge.
"""

from __future__ import annotations

import pytest

from app.domain.friendship import (
    BLOCKED_IS_SILENT,
    Decision,
    FriendshipError,
    FriendState,
    are_friends,
    decide,
    is_live_edge,
    open_request,
)

ANH = "a1a00000-aaaa-4aaa-8aaa-0000a0000001"
BINH = "b2b00000-bbbb-4bbb-8bbb-0000b0000001"
CUONG = "c3c00000-cccc-4ccc-8ccc-0000c0000001"


def _pending(requester=ANH, addressee=BINH):
    return open_request(requester_id=requester, addressee_id=addressee)


# --- the gate ---------------------------------------------------------------


def test_requester_cannot_accept_their_own_request():
    """The whole feature in one case.

    If this passes while the implementation lets a requester accept, the
    product has "add friend", not "friend request", and the second person's
    agreement is decorative.
    """
    edge = _pending()
    with pytest.raises(FriendshipError) as refused:
        decide(edge=edge, actor_id=ANH, decision=Decision.ACCEPT)
    assert refused.value.code == "ONLY_ADDRESSEE_MAY_ANSWER"


def test_requester_cannot_decline_on_the_addressees_behalf():
    edge = _pending()
    with pytest.raises(FriendshipError) as refused:
        decide(edge=edge, actor_id=ANH, decision=Decision.DECLINE)
    assert refused.value.code == "ONLY_ADDRESSEE_MAY_ANSWER"


def test_a_stranger_cannot_answer_somebody_elses_request():
    edge = _pending()
    with pytest.raises(FriendshipError) as refused:
        decide(edge=edge, actor_id=CUONG, decision=Decision.ACCEPT)
    assert refused.value.code == "NOT_A_PARTY"


def test_addressee_accepting_is_what_creates_the_friendship():
    """The control case. A gate that only ever refuses proves nothing."""
    edge = _pending()
    assert are_friends(edge) is False

    answered = decide(edge=edge, actor_id=BINH, decision=Decision.ACCEPT)

    assert answered["state"] == FriendState.ACCEPTED
    assert are_friends(answered) is True


def test_a_pending_request_is_not_a_friendship():
    assert are_friends(_pending()) is False


def test_declined_is_not_a_friendship():
    declined = decide(edge=_pending(), actor_id=BINH, decision=Decision.DECLINE)
    assert declined["state"] == FriendState.DECLINED
    assert are_friends(declined) is False


# --- the pair is unordered --------------------------------------------------


def test_the_same_two_people_are_one_edge_whichever_way_round():
    forward = open_request(requester_id=ANH, addressee_id=BINH)
    backward = open_request(requester_id=BINH, addressee_id=ANH)
    assert forward["pair"] == backward["pair"]


def test_nobody_friends_themselves():
    with pytest.raises(FriendshipError) as refused:
        open_request(requester_id=ANH, addressee_id=ANH)
    assert refused.value.code == "SELF_EDGE"


# --- reopening --------------------------------------------------------------


def test_a_second_request_cannot_stack_on_a_pending_one():
    with pytest.raises(FriendshipError) as refused:
        open_request(requester_id=ANH, addressee_id=BINH, existing=_pending())
    assert refused.value.code == BLOCKED_IS_SILENT


def test_being_declined_once_does_not_bar_asking_again():
    declined = decide(edge=_pending(), actor_id=BINH, decision=Decision.DECLINE)
    again = open_request(requester_id=ANH, addressee_id=BINH, existing=declined)
    assert again["state"] == FriendState.PENDING


def test_a_blocked_edge_refuses_with_the_same_code_as_a_busy_one():
    """Blocking must not announce itself.

    The blocked person asks again and gets the answer a duplicate request gets.
    If these two codes ever diverge, the refusal tells somebody they were
    blocked and by whom -- which is the one thing a block is meant to withhold.
    """
    blocked = decide(edge=_pending(), actor_id=BINH, decision=Decision.BLOCK)

    with pytest.raises(FriendshipError) as after_block:
        open_request(requester_id=ANH, addressee_id=BINH, existing=blocked)
    with pytest.raises(FriendshipError) as after_pending:
        open_request(requester_id=ANH, addressee_id=BINH, existing=_pending())

    assert after_block.value.code == after_pending.value.code


# --- blocking ---------------------------------------------------------------


def test_either_party_may_block_an_accepted_friendship():
    accepted = decide(edge=_pending(), actor_id=BINH, decision=Decision.ACCEPT)

    by_requester = decide(edge=accepted, actor_id=ANH, decision=Decision.BLOCK)
    by_addressee = decide(edge=accepted, actor_id=BINH, decision=Decision.BLOCK)

    assert by_requester["state"] == FriendState.BLOCKED
    assert by_addressee["state"] == FriendState.BLOCKED


def test_blocking_ends_the_friendship():
    accepted = decide(edge=_pending(), actor_id=BINH, decision=Decision.ACCEPT)
    blocked = decide(edge=accepted, actor_id=ANH, decision=Decision.BLOCK)
    assert are_friends(blocked) is False


def test_accepting_is_not_possible_after_a_block():
    blocked = decide(edge=_pending(), actor_id=BINH, decision=Decision.BLOCK)
    with pytest.raises(FriendshipError) as refused:
        decide(edge=blocked, actor_id=BINH, decision=Decision.ACCEPT)
    assert refused.value.code == "NOT_PENDING"


def test_accepting_twice_is_refused():
    accepted = decide(edge=_pending(), actor_id=BINH, decision=Decision.ACCEPT)
    with pytest.raises(FriendshipError) as refused:
        decide(edge=accepted, actor_id=BINH, decision=Decision.ACCEPT)
    assert refused.value.code == "NOT_PENDING"


# --- which states hold the pair --------------------------------------------


@pytest.mark.parametrize(
    ("state", "live"),
    [
        (FriendState.PENDING, True),
        (FriendState.ACCEPTED, True),
        (FriendState.BLOCKED, True),
        (FriendState.DECLINED, False),
    ],
)
def test_only_declined_frees_the_pair_for_a_new_request(state, live):
    assert is_live_edge(state) is live
