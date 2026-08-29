"""F17 tally: the machine counts, and it refuses to break a tie.

This file exists because of one sentence in the task: a tie must be shown as a
tie. A product that quietly picks the first option when two places draw 4-4 has
taken away the exact decision the feature was built to support -- and it takes
it away silently, because a single winner looks identical to a real one.

So `decided_option_id` is `None` in three different situations that a caller
must be able to tell apart, and the tally reports each one distinctly:

  - nobody has voted yet          -> no leader at all
  - two or more options are level -> leaders, and `is_tie` true
  - exactly one option leads      -> a decision, and `is_tie` false

Pure functions over plain dicts. The tally never sees a Session, a request, or
a person's name -- only ids -- so nothing here can leak who voted for what into
a place the caller did not already have the right to read.
"""

from __future__ import annotations

import pytest

from app.domain.vote import VoteError, tally


def _options(*ids: str) -> list[dict]:
    return [{"id": name, "position": index} for index, name in enumerate(ids)]


def _ballots(**by_voter: str) -> list[dict]:
    return [
        {"voter_id": voter, "option_id": option} for voter, option in by_voter.items()
    ]


def test_the_spec_example_reports_a_clear_winner():
    """F17's own example: 4 / 2 / 1 has one winner and is not a tie."""

    result = tally(
        options=_options("pizza", "bep-me-in", "som-tum"),
        ballots=_ballots(
            an="pizza",
            binh="pizza",
            chi="pizza",
            dung="pizza",
            em="bep-me-in",
            phuc="bep-me-in",
            giang="som-tum",
        ),
    )

    assert result["total_ballots"] == 7
    assert result["counts"] == {"pizza": 4, "bep-me-in": 2, "som-tum": 1}
    assert result["leading_option_ids"] == ["pizza"]
    assert result["is_tie"] is False
    assert result["decided_option_id"] == "pizza"


def test_an_option_nobody_chose_still_appears_with_zero():
    """A missing row and a zero are different facts to the person reading it."""

    result = tally(
        options=_options("pizza", "bun-cha", "som-tum"),
        ballots=_ballots(an="pizza"),
    )

    assert result["counts"] == {"pizza": 1, "bun-cha": 0, "som-tum": 0}


def test_a_level_result_is_reported_as_a_tie_and_decides_nothing():
    """The rule this file exists for: 2-2 must not become a winner."""

    result = tally(
        options=_options("pizza", "bun-cha"),
        ballots=_ballots(an="pizza", binh="bun-cha", chi="pizza", dung="bun-cha"),
    )

    assert result["is_tie"] is True
    assert result["decided_option_id"] is None
    assert result["leading_option_ids"] == ["pizza", "bun-cha"]


def test_a_three_way_tie_lists_every_leader_in_the_order_the_group_wrote_them():
    """Order comes from `position`, not from ballot arrival or id sort.

    If leaders came back in arrival order, the option listed first on screen
    would change every time somebody voted, which reads as movement in a result
    that has not moved.
    """

    result = tally(
        options=_options("pizza", "bun-cha", "som-tum"),
        ballots=_ballots(an="som-tum", binh="bun-cha", chi="pizza"),
    )

    assert result["is_tie"] is True
    assert result["leading_option_ids"] == ["pizza", "bun-cha", "som-tum"]
    assert result["decided_option_id"] is None


def test_a_vote_nobody_answered_has_no_leader_and_is_not_a_tie():
    """Zero-all is not a draw between the options; it is an unanswered question.

    Calling it a tie would put "hoà" on screen for a vote that has simply not
    started, and the group would read a deadlock that does not exist.
    """

    result = tally(options=_options("pizza", "bun-cha"), ballots=[])

    assert result["total_ballots"] == 0
    assert result["counts"] == {"pizza": 0, "bun-cha": 0}
    assert result["leading_option_ids"] == []
    assert result["is_tie"] is False
    assert result["decided_option_id"] is None


def test_a_single_option_that_nobody_chose_does_not_win_by_walkover():
    result = tally(options=_options("pizza"), ballots=[])

    assert result["decided_option_id"] is None
    assert result["leading_option_ids"] == []


def test_one_voter_appearing_twice_is_refused_rather_than_counted_twice():
    """One person one ballot is a DB unique index; the tally refuses to assume it.

    The index is the guarantee, but a tally that silently sums duplicates would
    turn any future bug -- a bad backfill, a repository that appends instead of
    replacing -- into a wrong number on a screen instead of an error.
    """

    with pytest.raises(VoteError) as excinfo:
        tally(
            options=_options("pizza", "bun-cha"),
            ballots=[
                {"voter_id": "an", "option_id": "pizza"},
                {"voter_id": "an", "option_id": "bun-cha"},
            ],
        )

    assert excinfo.value.code == "DUPLICATE_BALLOT"


def test_a_ballot_for_an_option_that_is_not_on_the_list_is_refused():
    with pytest.raises(VoteError) as excinfo:
        tally(
            options=_options("pizza"),
            ballots=[{"voter_id": "an", "option_id": "somewhere-else"}],
        )

    assert excinfo.value.code == "UNKNOWN_OPTION"


def test_a_vote_with_no_options_is_refused():
    """A question with nothing to choose cannot be tallied into anything true."""

    with pytest.raises(VoteError) as excinfo:
        tally(options=[], ballots=[])

    assert excinfo.value.code == "NO_OPTIONS"


def test_two_options_may_not_share_a_position():
    """Duplicate positions make leader order ambiguous, so they are an error."""

    with pytest.raises(VoteError) as excinfo:
        tally(
            options=[
                {"id": "pizza", "position": 0},
                {"id": "bun-cha", "position": 0},
            ],
            ballots=[],
        )

    assert excinfo.value.code == "DUPLICATE_POSITION"


def test_the_tally_does_not_mutate_what_it_was_given():
    """The caller's rows come from a repository; the tally is a reader."""

    options = _options("pizza", "bun-cha")
    ballots = _ballots(an="pizza")
    options_before = [dict(option) for option in options]
    ballots_before = [dict(ballot) for ballot in ballots]

    tally(options=options, ballots=ballots)

    assert options == options_before
    assert ballots == ballots_before


def test_the_tally_never_reports_who_voted_for_what():
    """A count is public to the group; a named ballot is not part of F17.

    Nothing in the result may carry a voter id. If a future caller wants "who
    voted", that is a separate decision with its own privacy argument, not a
    field that arrived by accident inside the results payload.
    """

    result = tally(
        options=_options("pizza", "bun-cha"),
        ballots=_ballots(an="pizza", binh="bun-cha"),
    )

    assert "an" not in repr(result)
    assert "binh" not in repr(result)
    assert set(result) == {
        "total_ballots",
        "counts",
        "leading_option_ids",
        "is_tie",
        "decided_option_id",
    }
