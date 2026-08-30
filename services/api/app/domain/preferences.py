"""F31 -- the implicit profile: what this group keeps choosing, in its own rows.

## The one design decision worth arguing about

There is no `group_preferences` table, and adding one would have been easier.

A stored profile is a cache, and invariant 3 says a cache is never the source
of truth. The failure it invites is specific and quiet: the group checks in
somewhere new, nothing recomputes the row, and the screen goes on saying "BBQ
0.91" for a group that has not eaten BBQ in two months. Nobody sees a stale
score, because a score has no receipt attached -- unlike a wrong total, which
somebody eventually adds up by hand. So the profile is derived on the request
that asks, from check-ins and the ledger, exactly like `summarise_history`
beside it.

The cost is honest and paid per read: two queries the memory wall already runs.

## Why each taste carries its own count

`score` is a ratio, and a ratio printed alone cannot be checked by the person
reading it. Every taste therefore ships `checkin_count` next to its score, so
the arithmetic is auditable from the response itself: a reader who suspects the
number can divide. This is the same rule `SuggestionBasis` follows -- the
server computes every figure the screen shows as evidence, and the model is
never asked to restate one.

## What this module deliberately refuses to guess

A place whose catalogue category is not one this module knows is **skipped**,
not filed under a default section. Guessing would put a bar under "Food"
because the mapping had a hole, and a profile that quietly invents a taste is
worse than one that admits it saw nothing: the first is wrong in a direction
nobody audits.

Photographs are not evidence of a taste either. A caption is text somebody
typed; only a check-in names a catalogue place, and only a catalogue place has
a category. `list_memories(kind="checkin")` is the whole input.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

#: Catalogue category -> the section of the profile it belongs under.
#:
#: Written out rather than inferred from the category string, because the
#: mockup files `cafe` under *Activity* and not under *Food*: going for coffee
#: is what the group does, not what it eats. A rule that reads "categories
#: starting with `quan-an` are food" would have quietly disagreed.
SECTION_OF_CATEGORY: dict[str, str] = {
    "quan-an-local": "food",
    "cafe": "activity",
    "vui-choi": "activity",
    "di-choi-dem": "activity",
}

#: Section order on the wire. Fixed, so two renders of one profile do not
#: swap two headings under somebody's thumb.
SECTION_ORDER: tuple[str, ...] = ("food", "activity")

#: How many tastes a section shows. The cap is visible on the wire --
#: `taste_count` reports how many distinct tastes were actually found -- because
#: a silently truncated list reads as a complete one.
MAX_TASTES_PER_SECTION = 6

#: Longest taste label echoed back. Catalogue-owned text, but bounded anyway:
#: nothing downstream should be able to grow a response by editing a data file.
MAX_LABEL = 40


class PreferenceError(Exception):
    """Malformed input reached the profile builder."""


def _integer_count(value: Any) -> int:
    """A count, and specifically not a bool.

    `isinstance(True, int)` is true in Python, so a bool sails through an
    `int` check and then formats as `True` three layers away. The suggestion
    module spells this out for money; a headcount deserves the same refusal.
    """

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PreferenceError("preference_count_not_integer")
    return value


def _labels(visit: Any) -> tuple[str, list[str]] | None:
    """The section and taste labels of one check-in, or None to skip it."""

    if not isinstance(visit, dict):
        raise PreferenceError("preference_visit_malformed")
    category = visit.get("category")
    if not isinstance(category, str):
        return None
    section = SECTION_OF_CATEGORY.get(category)
    if section is None:
        # An unknown category is dropped, never defaulted. See module docstring.
        return None
    kinds = visit.get("kinds")
    if not isinstance(kinds, list | tuple):
        return None
    labels = [
        kind.strip()[:MAX_LABEL]
        for kind in kinds
        if isinstance(kind, str) and kind.strip()
    ]
    return (section, labels) if labels else None


def build_preference_profile(visits: list[dict], trips: list[dict]) -> dict:
    """This group's tastes and its spending shape, recomputed from its own rows.

    `visits` are check-ins already resolved through the place catalogue by the
    caller -- ``{"category": str, "kinds": [str, ...]}`` -- and `trips` are
    started outings whose `split_total_vnd` was summed from confirmed
    allocations, never read off a stored total.

    Both arrive scoped to one context. This function has no way to reach a
    second group's rows and is **not** the place that enforces that; the service
    proves ACTIVE membership before it collects either list.

    `score` is the taste's share of the busiest taste *within its own section*,
    so the top row of each section is 1.0. Sections are scored independently on
    purpose: a group with forty cafe check-ins and four dinners has a real food
    preference, and dividing by a global maximum would round it to nothing.

    Money stays integer đồng -- floor division over person-trips, the same
    arithmetic `summarise_history` uses, for the same reason.
    """

    per_section: dict[str, Counter] = {section: Counter() for section in SECTION_ORDER}
    counted = 0
    for visit in visits:
        resolved = _labels(visit)
        if resolved is None:
            continue
        section, labels = resolved
        counted += 1
        for label in labels:
            per_section[section][label] += 1

    sections = []
    for section in SECTION_ORDER:
        counts = per_section[section]
        if not counts:
            continue
        top = max(counts.values())
        # Count descending, then label ascending. Ties are broken by name and
        # never by dict insertion order, so the same rows render the same way.
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        sections.append(
            {
                "section": section,
                "taste_count": len(ordered),
                "tastes": [
                    {
                        "label": label,
                        "checkin_count": count,
                        # Round-half-up in integers. `round()` is banker's
                        # rounding and float division reintroduces the binary
                        # error this repository spends its money rules avoiding;
                        # neither belongs in a number two clients must agree on.
                        "score": ((count * 200 + top) // (2 * top)) / 100,
                    }
                    for label, count in ordered[:MAX_TASTES_PER_SECTION]
                ],
            }
        )

    total = 0
    people = 0
    for trip in trips:
        if not isinstance(trip, dict):
            raise PreferenceError("preference_trip_malformed")
        total += _integer_count(trip.get("split_total_vnd"))
        people += _integer_count(trip.get("headcount"))

    return {
        "sections": sections,
        "checkin_count": counted,
        "outing_count": len(trips),
        "split_total_vnd": total,
        "avg_per_person_vnd": total // people if people else None,
    }
