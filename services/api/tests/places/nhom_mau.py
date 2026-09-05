"""One taste profile the tests score against, and why it looks like this.

Until M11 the suite scored everything against `catalog.GROUP` -- six invented
people who liked «Chill, View đẹp, Đồ nướng». Deleting that constant left every
hand-computed vector without a subject, so this is its replacement: an explicit
profile a test file names, rather than a default the app carries.

It deliberately keeps the two numbers the old vectors used (250.000đ a head, six
people) so the budget and group-size arithmetic in `test_scoring.py` is
comparable line by line with what it replaced. What changed is the taste term,
and it had to: tastes are vocabulary words now, matched against a row's
category, traits and cuisine words, not free strings compared to `traits`.
"""

from __future__ import annotations

from app.places.taste import TasteProfile

#: Five of the eight words, chosen so the seed rows land on 3, 2, 1 and 0 hits
#: -- a profile every place matches, or none does, cannot show that the taste
#: term moves the badge.
NHOM_MAU = TasteProfile(
    basis="nhom",
    interests=("an-uong", "cafe", "nightlife", "mon-local", "outdoor"),
    budget_per_person_vnd=250_000,
    size=6,
    people=6,
    people_answered=6,
)

#: The same taste, said by one person browsing alone: no headcount, so the
#: group-size term drops out and the badge rests on budget and taste.
TOI_MAU = TasteProfile(
    basis="ca-nhan",
    interests=("an-uong", "cafe"),
    budget_per_person_vnd=175_000,
    size=None,
    people=1,
    people_answered=1,
)
