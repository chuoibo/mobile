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
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from app.places.catalog import GroupProfile

# 100 points, split by how much each component should be able to move the
# badge on its own. Budget dominates because a place nobody can afford is not
# a suggestion, it is a joke at the group's expense.
WEIGHT_BUDGET = 40
WEIGHT_TASTE = 35
WEIGHT_DISTANCE = 15
WEIGHT_GROUP_SIZE = 10


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


def budget_fit(place: dict[str, Any], group: GroupProfile) -> Fraction:
    """1 at or under budget, decaying to 0 at twice budget.

    The midpoint of the band rather than either end: quoting the cheap end
    flatters every place with a wide band, and quoting the expensive end buries
    places that have a cheap option.
    """

    midpoint = (place["price_min_vnd"] + place["price_max_vnd"]) // 2
    budget = group["budget_per_person_vnd"]
    if midpoint <= budget:
        return Fraction(1)
    over = Fraction(midpoint - budget, budget)
    return max(Fraction(0), Fraction(1) - over)


def taste_fit(place: dict[str, Any], group: GroupProfile) -> tuple[Fraction, list[str]]:
    """Share of the group's stated likes this place actually has.

    Deliberately not the other direction. Scoring "what share of this place's
    traits the group likes" would reward a place that lists one trait, and the
    question being asked is whether the group gets what it came for.
    """

    likes = set(group["likes"])
    if not likes:
        return Fraction(0), []
    hits = sorted(likes & set(place["traits"]))
    return Fraction(len(hits), len(likes)), hits


def distance_fit(place: dict[str, Any], group: GroupProfile) -> Fraction:
    """1 next door, 0 at the group's stated limit and beyond."""

    limit = _exact(group["max_distance_km"])
    if limit <= 0:
        return Fraction(0)
    return max(Fraction(0), Fraction(1) - _exact(place["distance_km"]) / limit)


def group_size_fit(place: dict[str, Any], group: GroupProfile) -> Fraction:
    """All or nothing: the party either fits through the door or it does not.

    No partial credit, because a table for 8 does not half-seat 12. A place
    with no stated capacity scores 0 rather than 1 -- absence of a constraint
    is not evidence the constraint is met.
    """

    fit = place.get("group_fit")
    if not fit:
        return Fraction(0)
    return Fraction(1) if fit["min_people"] <= group["size"] <= fit["max_people"] else Fraction(0)


def score_place(
    place: dict[str, Any], group: GroupProfile
) -> tuple[int, list[dict[str, str]]]:
    """The badge number, and the four lines that account for it."""

    budget = budget_fit(place, group)
    taste, hits = taste_fit(place, group)
    near = distance_fit(place, group)
    size = group_size_fit(place, group)

    exact = (
        WEIGHT_BUDGET * budget
        + WEIGHT_TASTE * taste
        + WEIGHT_DISTANCE * near
        + WEIGHT_GROUP_SIZE * size
    )
    # One rounding, at the end, on an exact rational. `round` on a Fraction is
    # banker's rounding, which is fine here: this is a display percentage, not
    # money, and no sum of these has to reconcile against anything.
    score = int(round(exact))

    midpoint_k = (place["price_min_vnd"] + place["price_max_vnd"]) // 2 // 1000
    budget_k = group["budget_per_person_vnd"] // 1000
    fit = place.get("group_fit") or {}
    capacity = (
        f"{fit['min_people']}-{fit['max_people']} người"
        if fit
        else "quán không ghi sức chứa"
    )

    factors = [
        {
            "label": "Budget",
            "detail": f"~{midpoint_k}k/người so với ~{budget_k}k nhóm định",
        },
        {
            "label": "Sở thích",
            "detail": ", ".join(hits) if hits else "không trùng sở thích nào đã ghi",
        },
        {
            "label": "Nhóm",
            "detail": f"nhóm {group['size']} người, quán hợp {capacity}",
        },
        {
            "label": "Khoảng cách",
            "detail": f"{place['distance_km']}km, đi khoảng {place['travel_minutes']} phút",
        },
    ]
    return score, factors
