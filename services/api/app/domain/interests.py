"""M11 -- the words a person is allowed to use about their own taste.

## Why the vocabulary is closed, and why it lives in `domain/`

The personalization step used to collect eight taste chips and a budget band
and then say so on screen: «Rủ Đi chỉ dùng lựa chọn này để cá nhân hóa gợi ý
trên máy. Chưa gửi lên máy chủ.» That sentence was true, which is the only
thing that made it acceptable. This module is what makes it false in the
direction the product wanted (ADR-0019 §2.1): the answers now leave the phone.

The vocabulary is a fixed list rather than free text for two reasons that pull
the same way:

* **It is the ground the model stands on.** A suggestion card may say the group
  leans toward cafés only if «cafe» is a word the server knows; free text would
  put whatever somebody typed into a prompt, and there would be no list to
  check the answer against afterwards.
* **It is what makes two people comparable.** «Đồ nướng», «BBQ» and «nướng» are
  one taste written three ways, and a profile that treats them as three has
  quietly stopped being able to count.

It lives in `domain/` because it is a rule about words, not about storage: the
HTTP layer refuses a tag outside the list, the aggregate reads the same list,
and neither may hold its own copy. `tests/test_import_boundary.py` keeps this
file free of the database and the framework.

## What this module deliberately does not decide

It does not say what a tag *means about a place*. That mapping -- which
catalogue rows count as evidence of «Outdoor» -- is about the catalogue and
belongs beside it, not here. This module owns the words and their order.

## Budget is a band, never a number the person typed

Law 1 is integer đồng including intermediate values, and a budget typed as one
number invites the average of a range, which is how `225000.5` gets into a
product with no halves of a đồng. A band is two integers and no arithmetic is
done on them here. The three bands tile without overlapping -- `min_vnd` is
inclusive, `max_vnd` exclusive -- so no amount belongs to two of them.

Skipping the question is a supported answer and is not the cheapest band: the
mockup's own rule is that a skipped budget leaves recommendation on default
rather than guessing hard.
"""

from __future__ import annotations

from dataclasses import dataclass


class InterestError(Exception):
    """A word outside the vocabulary reached the writer."""


@dataclass(frozen=True, slots=True)
class InterestTag:
    """One taste, as the server spells it."""

    id: str
    label: str


#: The vocabulary, in the reading order the personalization screen draws.
#:
#: The order is part of the data rather than something each caller sorts for
#: itself: two people who chose the same set must produce the same list, or a
#: reader diffing two profiles sees a change that is only a thumb's order.
INTEREST_TAGS: tuple[InterestTag, ...] = (
    InterestTag("an-uong", "Ăn uống"),
    InterestTag("cafe", "Cafe"),
    InterestTag("nightlife", "Nightlife"),
    InterestTag("mon-local", "Món local"),
    InterestTag("outdoor", "Outdoor"),
    InterestTag("shopping", "Shopping"),
    InterestTag("karaoke", "Karaoke"),
    InterestTag("game", "Game"),
)

#: Ids in vocabulary order. Built from the tuple above so the two can never
#: disagree; a second hand-written list is the kind of thing that drifts.
INTEREST_IDS: tuple[str, ...] = tuple(tag.id for tag in INTEREST_TAGS)

#: Longest interest list a request may carry. Choosing everything is a real
#: answer, so the cap is the size of the vocabulary itself -- it exists to
#: bound the body, not to tell somebody they like too many things.
MAX_INTERESTS = len(INTEREST_TAGS)


@dataclass(frozen=True, slots=True)
class BudgetBand:
    """A per-person, per-outing spending band, in đồng.

    `min_vnd` inclusive, `max_vnd` exclusive; `max_vnd` is None for an open top
    end. Both are integers, and nothing here averages them.
    """

    id: str
    label: str
    min_vnd: int
    max_vnd: int | None


#: The three bands the personalization screen offers, same ids as the client's
#: `so-thich.ts`. `tests/test_interest_vocabulary_matches_client.py` (repo root)
#: fails when the two lists drift apart.
BUDGET_BANDS: tuple[BudgetBand, ...] = (
    BudgetBand("tiet-kiem", "Dưới 100K", 0, 100_000),
    BudgetBand("vua-phai", "100K–250K", 100_000, 250_000),
    BudgetBand("thoai-mai", "250K–500K", 250_000, 500_000),
)

BUDGET_BAND_IDS: tuple[str, ...] = tuple(band.id for band in BUDGET_BANDS)


def budget_band(band_id: str | None) -> BudgetBand | None:
    """The band with this id, or None -- for `None` and for an id we dropped.

    A stale id from a phone that has not been updated resolves to «no answer»
    rather than to an error: the person did answer once, the answer no longer
    exists, and the honest state is the one where nothing is assumed about
    their budget.
    """

    if band_id is None:
        return None
    for band in BUDGET_BANDS:
        if band.id == band_id:
            return band
    return None


def normalise_interests(tags: object) -> list[str]:
    """The caller's tags as the server stores them, or `InterestError`.

    Deduplicated and put back into vocabulary order, so «cafe then ăn uống» and
    «ăn uống then cafe» are one answer stored one way. An unknown word is
    refused rather than dropped: silently ignoring it would let a client ship a
    chip that does nothing and never find out.
    """

    if not isinstance(tags, list | tuple):
        raise InterestError("interests_not_a_list")
    seen: set[str] = set()
    for tag in tags:
        if not isinstance(tag, str):
            raise InterestError("interest_not_a_string")
        if tag not in INTEREST_IDS:
            raise InterestError("interest_unknown")
        seen.add(tag)
    if len(seen) > MAX_INTERESTS:  # pragma: no cover - unreachable, kept honest
        raise InterestError("interests_too_many")
    return [tag_id for tag_id in INTEREST_IDS if tag_id in seen]


def normalise_budget_band(band_id: object) -> str | None:
    """The band id as stored, or `InterestError`. `None` means «skipped»."""

    if band_id is None:
        return None
    if not isinstance(band_id, str):
        raise InterestError("budget_band_not_a_string")
    if band_id not in BUDGET_BAND_IDS:
        raise InterestError("budget_band_unknown")
    return band_id
