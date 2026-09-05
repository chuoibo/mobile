"""The taste vocabulary: what it accepts, what it refuses, what order it keeps.

These are the rules a screen cannot enforce for itself. The chips are drawn by
one client today; the words they stand for have to mean the same thing to a
second client, to the aggregate that counts them across a group, and to any
prompt that is allowed to name one.
"""

from __future__ import annotations

import pytest

from app.domain.interests import (
    BUDGET_BANDS,
    INTEREST_IDS,
    INTEREST_TAGS,
    InterestError,
    budget_band,
    normalise_budget_band,
    normalise_interests,
)


def test_vocabulary_ids_are_unique_and_slug_shaped() -> None:
    assert len(set(INTEREST_IDS)) == len(INTEREST_IDS)
    for tag_id in INTEREST_IDS:
        assert tag_id == tag_id.strip().lower()
        assert " " not in tag_id
    assert all(tag.label.strip() for tag in INTEREST_TAGS)


def test_order_is_the_vocabularys_and_not_the_callers() -> None:
    """Two people who picked the same set produce the same list.

    The tap order is the thumb's, not the answer's: a reader diffing two
    profiles must not see a change that is only somebody's finger.
    """

    first = normalise_interests(["cafe", "an-uong"])
    second = normalise_interests(["an-uong", "cafe"])
    assert first == second == ["an-uong", "cafe"]


def test_repeats_collapse() -> None:
    assert normalise_interests(["cafe", "cafe", "cafe"]) == ["cafe"]


def test_empty_is_a_real_answer() -> None:
    """Finishing the step having chosen nothing is supported, and is not the
    same as never having answered -- the caller can tell those apart because
    this returns a list either way and the profile route returns what it read."""

    assert normalise_interests([]) == []


def test_an_unknown_word_is_refused_rather_than_dropped() -> None:
    """Dropping it would let a client ship a chip that silently does nothing."""

    with pytest.raises(InterestError) as caught:
        normalise_interests(["cafe", "du-thuyen"])
    assert str(caught.value) == "interest_unknown"


def test_a_non_string_is_refused() -> None:
    with pytest.raises(InterestError) as caught:
        normalise_interests(["cafe", 7])
    assert str(caught.value) == "interest_not_a_string"


def test_a_bare_string_is_not_a_list_of_tags() -> None:
    """`"cafe"` iterates as four characters; the answer must be a list."""

    with pytest.raises(InterestError) as caught:
        normalise_interests("cafe")
    assert str(caught.value) == "interests_not_a_list"


def test_choosing_everything_is_allowed() -> None:
    assert normalise_interests(list(INTEREST_IDS)) == list(INTEREST_IDS)


def test_budget_bands_tile_without_overlapping() -> None:
    """`min` inclusive, `max` exclusive, so no amount belongs to two bands."""

    for lower, upper in zip(BUDGET_BANDS, BUDGET_BANDS[1:], strict=False):
        assert lower.max_vnd == upper.min_vnd
    assert BUDGET_BANDS[0].min_vnd == 0


def test_budget_bounds_are_integers() -> None:
    """Law 1 reaches the personalization screen too: a band is two integers,
    and nothing in this module averages them."""

    for band in BUDGET_BANDS:
        assert isinstance(band.min_vnd, int) and not isinstance(band.min_vnd, bool)
        assert band.max_vnd is None or isinstance(band.max_vnd, int)


def test_a_skipped_budget_is_none_and_not_the_cheapest_band() -> None:
    assert normalise_budget_band(None) is None
    assert budget_band(None) is None


def test_a_band_this_build_dropped_reads_as_no_answer() -> None:
    """A stale id from a phone that has not updated resolves to «no answer»
    rather than to an error: the person did answer, the answer is gone, and
    assuming nothing is the honest state."""

    assert budget_band("sang-chanh") is None


def test_an_unknown_band_is_refused_on_the_way_in() -> None:
    """Lenient on read, strict on write -- the write is where a client bug is
    still fixable."""

    with pytest.raises(InterestError) as caught:
        normalise_budget_band("sang-chanh")
    assert str(caught.value) == "budget_band_unknown"


def test_band_ids_resolve_to_themselves() -> None:
    for band in BUDGET_BANDS:
        assert normalise_budget_band(band.id) == band.id
        resolved = budget_band(band.id)
        assert resolved is not None and resolved.label == band.label
