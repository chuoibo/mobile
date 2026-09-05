"""How a match percentage is produced, and why it is arithmetic and not a model.

rd-be-05's brief is blunt about this: "Con số 95% không có giá trị tự thân...
nếu là số giả thì đừng hiện phần trăm." A number a person cannot reproduce is
worse than no number, because it looks like evidence.

So the score is four weighted components over the seed row and the group
profile, and every one of them is handed back to the caller as a factor line.
The screen renders those lines under the badge, which means the percentage
always arrives with its own working shown. A reader who disagrees with 82% can
see it was 40 for budget, 21 for taste, 12 for distance, 10 for group size, and
argue with the weights instead of with a black box.

`Fraction`, not `float`, for the same reason `allocator.py` uses it: budget
arithmetic on money must not acquire a rounding error on the way to a
comparison. The only rounding is the single `round()` at the end that turns the
exact rational into the integer the badge shows.

Since M11 the group is a real one (`app/places/taste.py`) and every one of its
fields may be unknown. A term with no answer leaves the total instead of
scoring zero -- the rule M9 introduced for the catalogue's own null columns,
now applied to the other side of the comparison. When nothing at all is known,
`score_place` returns `None` and the card carries no percentage: the wire has
always allowed `match: null`, and a number computed from nobody was the thing
worth removing.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from app.domain.interests import INTEREST_TAGS
from app.places.taste import TasteProfile, matches

# 100 points, split by how much each component should be able to move the
# badge on its own. Budget dominates because a place nobody can afford is not
# a suggestion, it is a joke at the group's expense.
WEIGHT_BUDGET = 40
WEIGHT_TASTE = 35
WEIGHT_DISTANCE = 15
WEIGHT_GROUP_SIZE = 10

#: The distance at which a place stops counting as nearby, in km. A property of
#: this scale, not a claim about anybody: see `distance_fit`.
FAR_KM = 5.0


#: Tag id -> the word a person actually chose, for the factor line. The screen
#: shows «Cafe», not «cafe»: the id is a key, and a key on screen is a leak of
#: how the thing is stored.
_LABELS: dict[str, str] = {tag.id: tag.label for tag in INTEREST_TAGS}


def _exact(value: float | int) -> Fraction:
    """Decimal-exact rational from a seed value.

    Via `str` on purpose: `Fraction(1.2)` takes the binary expansion of the
    float and lands on a ratio of two sixteen-digit integers, while
    `Fraction("1.2")` is 6/5. The seed file is written in decimal and should be
    read as decimal. `tests/places/test_scoring.py` pins the difference.

    (The exact ratio is not quoted here: sixteen consecutive digits trip the
    repo guard's card-number rule, and that rule is worth more than the
    illustration.)
    """

    return Fraction(str(value))


def budget_fit(place: dict[str, Any], group: TasteProfile) -> Fraction | None:
    """1 at or under budget, decaying to 0 at twice budget. `None` if unpriced.

    The midpoint of the band rather than either end: quoting the cheap end
    flatters every place with a wide band, and quoting the expensive end buries
    places that have a cheap option.

    Since M9 a place may have no price at all -- OpenStreetMap does not carry
    one. That is `None`, not zero: a place nobody has priced has not failed the
    budget test, it has not taken it, and `score_place` leaves its weight out
    of the total rather than scoring it as unaffordable.
    """

    low = place.get("price_min_vnd")
    high = place.get("price_max_vnd")
    budget = group.budget_per_person_vnd
    # Two ways not to have an answer, and they are different facts: the place
    # has no price, or nobody said what they meant to spend. Neither is a
    # failed budget test, so both leave the term out rather than scoring 0.
    if low is None or high is None or budget is None:
        return None
    midpoint = (low + high) // 2
    if midpoint <= budget:
        return Fraction(1)
    over = Fraction(midpoint - budget, budget)
    return max(Fraction(0), Fraction(1) - over)


def taste_fit(
    place: dict[str, Any], group: TasteProfile
) -> tuple[Fraction | None, list[str]]:
    """Share of the tastes these people claimed that this place answers.

    Deliberately not the other direction. Scoring "what share of this place's
    traits the group likes" would reward a place that lists one trait, and the
    question being asked is whether the group gets what it came for.

    Nobody having claimed anything is `None`, not zero. Zero would rank every
    place equally badly and still print a percentage, which is a statement
    about the places; `None` says the sentence has no subject yet.

    What counts as a hit is `app/places/taste.py`, not this file: a taste is a
    word, and what a word means about a row belongs beside the importer that
    writes the row.
    """

    if not group.interests:
        return None, []
    hits = [tag for tag in group.interests if matches(tag, place)]
    return Fraction(len(hits), len(group.interests)), hits


def distance_fit(place: dict[str, Any]) -> Fraction | None:
    """1 next door, 0 at `FAR_KM` and beyond. `None` when the row has no distance.

    `None` when the row carries no distance: until somebody says where they are
    standing, «how far» has no answer, and an imported place is not far away
    merely because nobody measured.

    The limit is a property of this scale and no longer a field of the profile.
    It used to be `group["max_distance_km"]`, which read as «the group said 5km»
    -- and no group ever said it; the number was part of the invented profile
    deleted in M11. A screen that lets somebody state a limit can pass one in
    then, and it will be a fact rather than a constant wearing a fact's clothes.
    """

    here = place.get("distance_km")
    if here is None:
        return None
    return max(Fraction(0), Fraction(1) - _exact(here) / _exact(FAR_KM))


def group_size_fit(place: dict[str, Any], group: TasteProfile) -> Fraction | None:
    """All or nothing: the party either fits through the door or it does not.

    No partial credit, because a table for 8 does not half-seat 12.

    A place with no stated capacity used to score 0 here, on the argument that
    absence of a constraint is not evidence the constraint is met. That was
    right when every row in the catalogue carried a capacity and a missing one
    meant something. Since M9 no imported row carries one at all, and scoring
    them all 0 would rank «the map does not say» below «too small» -- so an
    unstated capacity is now `None` and its weight leaves the total. What did
    not change: a capacity that IS stated and does not fit still scores 0.
    """

    fit = place.get("group_fit")
    if not fit or group.size is None:
        return None
    return (
        Fraction(1)
        if fit["min_people"] <= group.size <= fit["max_people"]
        else Fraction(0)
    )


def score_place(
    place: dict[str, Any], group: TasteProfile
) -> tuple[int | None, list[dict[str, str]]]:
    """The badge number, and the four lines that account for it.

    `None` for the number when not one term had an answer -- an anonymous
    reader, or somebody who has not said anything about themself yet. The four
    lines still come back, and they say which side of each comparison is
    missing, so the screen can ask for the half it needs.
    """

    budget = budget_fit(place, group)
    taste, hits = taste_fit(place, group)
    near = distance_fit(place)
    size = group_size_fit(place, group)

    # Only the terms this place has an answer for count, and they are scaled
    # back up to 100. Without the rescaling a place the map simply does not
    # describe would score 35 out of 100 while a described place scores 80, and
    # the badge would be measuring how well-mapped a venue is rather than how
    # well it suits the group. A place with nothing known at all scores 0 and
    # `factors` says why.
    terms: list[tuple[int, Fraction | None]] = [
        (WEIGHT_BUDGET, budget),
        (WEIGHT_TASTE, taste),
        (WEIGHT_DISTANCE, near),
        (WEIGHT_GROUP_SIZE, size),
    ]
    known = [(weight, value) for weight, value in terms if value is not None]
    total_weight = sum(weight for weight, _ in known)
    # A match is a match WITH somebody. Capacity and distance can refine a
    # badge but must not carry one on their own: «6 người vừa bàn» rescaled to
    # a lone term prints 100%, which reads as «hợp hoàn hảo» when all it says
    # is that the party fits through the door -- and the card already shows the
    # capacity and the distance as facts. So the badge needs at least one thing
    # the person said about themself, which is what `TasteProfile.known` is.
    if not group.known or total_weight == 0:
        # Nothing known on either side. Not a zero: a badge reading 0% is a
        # claim about the place, and the only thing missing is us knowing who
        # is asking.
        score = None
    else:
        exact = (
            Fraction(sum(weight * value for weight, value in known))
            * Fraction(
                WEIGHT_BUDGET + WEIGHT_TASTE + WEIGHT_DISTANCE + WEIGHT_GROUP_SIZE
            )
            / Fraction(total_weight)
        )
        # One rounding, at the end, on an exact rational. `round` on a Fraction
        # is banker's rounding, which is fine here: this is a display
        # percentage, not money, and no sum of these has to reconcile.
        score = int(round(exact))

    budget_k = (
        None
        if group.budget_per_person_vnd is None
        else group.budget_per_person_vnd // 1000
    )
    if budget_k is None and budget is None:
        budget_detail = "chưa có giá, và chưa ai nói mức chi"
    elif budget_k is None:
        midpoint_k = (place["price_min_vnd"] + place["price_max_vnd"]) // 2 // 1000
        budget_detail = f"~{midpoint_k}k/người; chưa ai nói mức chi"
    elif budget is None:
        budget_detail = f"chưa có giá; mức chi đã nói ~{budget_k}k/người"
    else:
        midpoint_k = (place["price_min_vnd"] + place["price_max_vnd"]) // 2 // 1000
        budget_detail = f"~{midpoint_k}k/người so với ~{budget_k}k đã nói"

    fit = place.get("group_fit") or {}
    capacity = (
        f"{fit['min_people']}-{fit['max_people']} người"
        if fit
        else "quán không ghi sức chứa"
    )

    if near is None:
        distance_detail = "chưa biết khoảng cách"
    else:
        phut = place.get("travel_minutes")
        distance_detail = f"{place['distance_km']}km"
        if phut is not None:
            distance_detail += f", đi khoảng {phut} phút"

    if taste is None:
        taste_detail = "chưa chọn sở thích nào, nên chưa so được"
    elif hits:
        taste_detail = ", ".join(_LABELS[tag] for tag in hits)
    else:
        taste_detail = "không trùng sở thích nào đã chọn"

    if group.size is None:
        size_detail = f"chưa biết đi mấy người; quán hợp {capacity}"
    else:
        size_detail = f"nhóm {group.size} người, quán hợp {capacity}"

    factors = [
        {"label": "Budget", "detail": budget_detail},
        {"label": "Sở thích", "detail": taste_detail},
        {"label": "Nhóm", "detail": size_detail},
        {"label": "Khoảng cách", "detail": distance_detail},
    ]
    return score, factors
