"""Whose taste a card is scored against, and what a taste word means about a row.

Two things live here because neither works without the other, and both are
about the catalogue rather than about a person:

* **`TasteProfile`** -- the answer to «hợp với ai?». Until M11 that answer was
  a constant in `catalog.py`: six people, aged 22-28, 250k each, who like
  «Chill, View đẹp, Đồ nướng». Every match percentage the product has ever
  shown was scored against those six invented people, on both real and seeded
  rows. It has to be somebody real or it has to be nobody.
* **`EVIDENCE`** -- what makes a row count as «Cafe» or «Outdoor». The taste
  vocabulary is the domain's (`app/domain/interests.py`); what it means about a
  place is the catalogue's, and it changes when the importer's tag tables
  change. Keeping the two apart is why adding a chip does not touch this file
  and adding an OSM tag does not touch that one.

## Nobody is a real answer

`UNKNOWN` is a profile with nothing in it, and it is what an anonymous reader
gets. Every scoring term then has no answer, `score_place` returns `None`, and
the card carries no percentage at all -- the wire has always allowed
`match: null` and the app has always drawn it as «no badge». That is the honest
shape of «we do not know you yet», and it is strictly better than the previous
behaviour, which was to print a number computed from six people who do not
exist.

## Why an interest matches by category, trait or word -- and sometimes by none

The importer writes three things a taste can be read off (`app/places/osm.py`):
the four catalogue categories, the trait labels it derives from tags that state
a fact outright (`outdoor_seating=yes` -> «Ngoài trời»), and the cuisine or
amenity words under the name. `EVIDENCE` cites which of those each taste reads.

Two tastes cite nothing: this catalogue imports no shops and no karaoke bars,
so «Shopping» and «Karaoke» have nothing to match against. That is recorded
here as an empty tuple and reported on the wire as `uncovered_interests`,
rather than being quietly scored as «no match». The difference matters to the
person reading the screen: «không có chỗ nào hợp gu bạn» is a claim about the
places, and «Rủ Đi chưa nhập nhóm địa điểm này» is a claim about us.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.domain.interests import INTEREST_IDS, budget_band

Basis = Literal["nhom", "ca-nhan", "chua-biet"]


@dataclass(frozen=True, slots=True)
class TasteEvidence:
    """Which parts of a catalogue row count as one taste."""

    categories: tuple[str, ...] = ()
    traits: tuple[str, ...] = ()
    kinds: tuple[str, ...] = ()


#: What each word of the vocabulary reads on a row. Every value here is written
#: by `app/places/osm.py` or by the seed file -- nothing is invented for the
#: sake of a match.
EVIDENCE: dict[str, TasteEvidence] = {
    "an-uong": TasteEvidence(categories=("quan-an-local",)),
    "cafe": TasteEvidence(categories=("cafe",), kinds=("Cà phê", "Trà sữa", "Trà")),
    "nightlife": TasteEvidence(categories=("di-choi-dem",)),
    # Cuisine tags, which OSM carries for a good share of Vietnamese rows, plus
    # the seed file's own «Local» word.
    "mon-local": TasteEvidence(
        kinds=("Việt", "Phở", "Mì · bún", "Lẩu", "Ăn vặt", "Ăn sáng", "Local")
    ),
    "outdoor": TasteEvidence(
        traits=("Ngoài trời",), kinds=("Park", "Garden", "Viewpoint")
    ),
    # Nothing to read: this catalogue imports neither shops nor karaoke.
    "shopping": TasteEvidence(),
    "karaoke": TasteEvidence(),
    "game": TasteEvidence(
        kinds=("Bowling alley", "Theme park", "Cinema", "Water park")
    ),
}

assert set(EVIDENCE) == set(INTEREST_IDS), (
    "EVIDENCE và từ vựng sở thích lệch nhau: mỗi từ phải nói rõ nó đọc gì "
    "trên một dòng danh mục, kể cả khi câu trả lời là «chưa có gì»."
)


def covers(tag: str) -> bool:
    """Does this catalogue have anything at all that could match this taste?"""

    evidence = EVIDENCE.get(tag)
    return bool(evidence and (evidence.categories or evidence.traits or evidence.kinds))


def uncovered(tags: tuple[str, ...] | list[str]) -> list[str]:
    """The chosen tastes this catalogue cannot speak to, in vocabulary order."""

    return [tag for tag in INTEREST_IDS if tag in tags and not covers(tag)]


def _tokens(values: Any) -> set[str]:
    return {
        value.strip().casefold()
        for value in values or ()
        if isinstance(value, str) and value.strip()
    }


def matches(tag: str, place: dict[str, Any]) -> bool:
    """Is this row evidence of this taste?

    Case-insensitive on the words because the importer capitalises what OSM
    gives it and the seed file does not; exact on the whole token rather than a
    substring, so «Trà» does not match «Trà trộn» by accident.
    """

    evidence = EVIDENCE.get(tag)
    if evidence is None:
        return False
    if place.get("category") in evidence.categories:
        return True
    traits = _tokens(place.get("traits"))
    if traits & {value.casefold() for value in evidence.traits}:
        return True
    kinds = _tokens(place.get("kinds"))
    return bool(kinds & {value.casefold() for value in evidence.kinds})


@dataclass(frozen=True, slots=True)
class TasteProfile:
    """Whose budget and taste a score is relative to, and how much is known.

    Every field except `basis` may be unknown, and «unknown» is not a default
    value: a term with no answer leaves the score rather than scoring zero, the
    same rule the catalogue's own null fields follow since M9.

    `people` and `people_answered` exist so the screen can say what the number
    rests on -- «gu của 3/6 người đã chọn» is checkable, «gu nhóm» is not.
    """

    basis: Basis
    interests: tuple[str, ...] = ()
    budget_per_person_vnd: int | None = None
    size: int | None = None
    people: int = 0
    people_answered: int = 0

    @property
    def cache_key(self) -> str:
        """A string that is equal exactly when two profiles would earn the same
        sentence from the model. Used to key the reason cache; it holds taste
        words and a rounded budget, never an identity."""

        return f"{self.basis}|{','.join(self.interests)}|{self.budget_per_person_vnd}|{self.size}"

    @property
    def known(self) -> bool:
        """Is there anything here to score against at all?"""

        return bool(self.interests) or self.budget_per_person_vnd is not None


#: Nobody: an anonymous reader browsing the catalogue.
UNKNOWN = TasteProfile(basis="chua-biet")


def _midpoint_vnd(band_id: str | None) -> int | None:
    """The middle of a band, in whole đồng, or None.

    Floor division, never a float: Law 1 covers intermediate values, and the
    midpoint of a band is exactly the intermediate value that would otherwise
    arrive as `225000.5`. An open top end (no `max_vnd`) is read as its floor --
    the only bound anybody stated.
    """

    band = budget_band(band_id)
    if band is None:
        return None
    if band.max_vnd is None:
        return band.min_vnd
    return (band.min_vnd + band.max_vnd) // 2


def profile_for_person(interests: list[str], band_id: str | None) -> TasteProfile:
    """One person's own answers, for a reader with no group on screen."""

    return TasteProfile(
        basis="ca-nhan",
        interests=tuple(tag for tag in INTEREST_IDS if tag in interests),
        budget_per_person_vnd=_midpoint_vnd(band_id),
        size=None,
        people=1,
        people_answered=1 if (interests or band_id) else 0,
    )


def profile_for_group(members: list[tuple[list[str], str | None]]) -> TasteProfile:
    """The group's taste, summed from the members who answered.

    A taste counts for the group if **at least one** member claimed it. The
    alternative -- a majority rule -- silently drops the taste of anybody in a
    minority, which in a group of five friends means dropping four of them.
    What keeps that from turning into «this group likes everything» is that the
    score is a share: the more the group claims, the harder each place has to
    work to satisfy it.

    The budget is the floor-average of the midpoints of the bands people
    actually chose. Averaging is a choice with a cost, and it is stated rather
    than hidden: one person on «dưới 100K» pulls the group figure down, and a
    place at the top of the range loses points for them. The rejected
    alternative was the minimum, which lets one frugal answer decide for
    everybody; both are defensible, and the response carries
    `people_answered` so the number can be argued with.

    Members who answered nothing contribute nothing -- they are not counted as
    zero đồng and their silence is not read as a taste.
    """

    tastes: set[str] = set()
    midpoints: list[int] = []
    answered = 0
    for interests, band_id in members:
        midpoint = _midpoint_vnd(band_id)
        if interests or midpoint is not None:
            answered += 1
        tastes.update(interests)
        if midpoint is not None:
            midpoints.append(midpoint)
    return TasteProfile(
        basis="nhom",
        interests=tuple(tag for tag in INTEREST_IDS if tag in tastes),
        budget_per_person_vnd=(sum(midpoints) // len(midpoints)) if midpoints else None,
        size=len(members) or None,
        people=len(members),
        people_answered=answered,
    )
