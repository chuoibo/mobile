"""Pure vote counting that keeps a deadlock visible to its callers.

The persisted rows guarantee one ballot per person, but the tally validates
that invariant again so corrupt input becomes an explicit error instead of a
plausible-looking result.  Only aggregate counts leave this boundary; voter
identities are used solely to reject duplicates.
"""

from __future__ import annotations


class VoteError(Exception):
    """A stable refusal code for vote input that cannot be counted truthfully."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def tally(options: list[dict], ballots: list[dict]) -> dict:
    """Count ballots without choosing a winner when the group is tied."""

    if not options:
        raise VoteError("NO_OPTIONS")

    ordered_options = sorted(options, key=lambda option: option["position"])
    positions = [option["position"] for option in ordered_options]
    if len(positions) != len(set(positions)):
        raise VoteError("DUPLICATE_POSITION")

    option_ids = [option["id"] for option in ordered_options]
    counts = {option_id: 0 for option_id in option_ids}
    seen_voters = set()

    for ballot in ballots:
        voter_id = ballot["voter_id"]
        if voter_id in seen_voters:
            raise VoteError("DUPLICATE_BALLOT")
        seen_voters.add(voter_id)

        option_id = ballot["option_id"]
        if option_id not in counts:
            raise VoteError("UNKNOWN_OPTION")
        counts[option_id] += 1

    total_ballots = len(ballots)
    if total_ballots == 0:
        leading_option_ids = []
    else:
        highest_count = max(counts.values())
        leading_option_ids = [
            option_id for option_id in option_ids if counts[option_id] == highest_count
        ]

    is_tie = len(leading_option_ids) > 1
    decided_option_id = leading_option_ids[0] if len(leading_option_ids) == 1 else None
    return {
        "total_ballots": total_ballots,
        "counts": counts,
        "leading_option_ids": leading_option_ids,
        "is_tie": is_tie,
        "decided_option_id": decided_option_id,
    }


__all__ = ["VoteError", "tally"]
