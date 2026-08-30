"""Pure integer-dong arithmetic for F34 group budget awareness.

The repository supplies outing totals recomputed from the ledger. This module
turns those facts into per-person figures and a candidate comparison without
knowing how anything was stored or who asked for it.
"""

from __future__ import annotations

from typing import Any

from app.domain.money import vnd_violation

__all__ = [
    "COMPARISON_TOLERANCE_PERCENT",
    "BudgetError",
    "build_group_budget",
]

# A group does not need a warning for normal day-to-day noise. Ten percent is
# wide enough to keep a nearby option neutral while still making a materially
# dearer one visible. The comparison below uses scaled integers, not a ratio.
COMPARISON_TOLERANCE_PERCENT = 10
_PERCENT_SCALE = 100


class BudgetError(Exception):
    """Report a malformed repository fact or candidate without coercion."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _invalid() -> BudgetError:
    return BudgetError("INVALID_BUDGET_INPUT")


def _non_negative_integer(value: Any) -> int:
    # ``bool`` subclasses ``int``; accepting it would turn True into one đồng.
    if vnd_violation(value):
        raise _invalid()
    return value


def _read_outing(raw: Any) -> dict:
    if not isinstance(raw, dict):
        raise _invalid()

    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        raise _invalid()
    in_progress = raw.get("in_progress")
    if type(in_progress) is not bool:
        raise _invalid()

    return {
        "outing_id": raw.get("outing_id"),
        "title": title.strip(),
        "headcount": _non_negative_integer(raw.get("headcount")),
        "budget_per_person_vnd": _non_negative_integer(
            raw.get("budget_per_person_vnd")
        ),
        "split_total_vnd": _non_negative_integer(raw.get("split_total_vnd")),
        "in_progress": in_progress,
    }


def _comparison(candidate: int, average: int) -> dict:
    delta = candidate - average
    tolerance = average * COMPARISON_TOLERANCE_PERCENT
    if abs(delta) * _PERCENT_SCALE <= tolerance:
        verdict = "nhu-thuong"
    elif delta < 0:
        verdict = "re-hon"
    else:
        verdict = "cao-hon"
    return {
        "candidate_per_person_vnd": candidate,
        "delta_vnd": delta,
        "verdict": verdict,
    }


def build_group_budget(
    outings: list[dict],
    *,
    active_member_count: int,
    candidate_per_person_vnd: int | None,
) -> dict:
    """Build current spend and a historical comparison using only integers."""

    if not isinstance(outings, list):
        raise _invalid()
    active_count = _non_negative_integer(active_member_count)
    candidate = (
        None
        if candidate_per_person_vnd is None
        else _non_negative_integer(candidate_per_person_vnd)
    )

    finished_total = 0
    finished_headcount = 0
    outing_count = 0
    current: list[dict] = []

    for raw in outings:
        outing = _read_outing(raw)
        headcount = outing["headcount"]
        split_total = outing["split_total_vnd"]
        if not outing["in_progress"]:
            outing_count += 1
            finished_total += split_total
            finished_headcount += headcount
            continue

        # A zero-headcount row cannot be created through the API or database
        # constraints, but a read boundary still must not turn corruption into
        # ZeroDivisionError. The response schema has no unknown value for this
        # field, so an empty population contributes zero per person explicitly.
        spent = split_total // headcount if headcount else 0
        remaining = outing["budget_per_person_vnd"] - spent
        current.append(
            {
                "outing_id": outing["outing_id"],
                "title": outing["title"],
                "headcount": headcount,
                "budget_per_person_vnd": outing["budget_per_person_vnd"],
                "spent_per_person_vnd": spent,
                "remaining_per_person_vnd": remaining,
                "over_budget": remaining < 0,
            }
        )

    average = finished_total // finished_headcount if finished_headcount else None
    comparison = (
        _comparison(candidate, average)
        if candidate is not None and average is not None
        else None
    )
    return {
        "outing_count": outing_count,
        "active_member_count": active_count,
        "avg_per_person_vnd": average,
        "in_progress": current,
        "comparison": comparison,
    }
