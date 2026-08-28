"""The live tier: a real call to Gemini, or nothing.

Every other test around `app/places` injects a fake writer, which means none of
them can tell you whether the model actually answers, answers in Vietnamese,
answers about the right places, or -- the one that matters -- is willing to say
a place does not suit the group.

This file is the only thing in the repo that can. It is **skipped by default**,
and a skip here is not a green: it is this claim going unmade. Run it with:

    set -a && . /path/to/.env && set +a
    cd services/api && MOBILE_REQUIRE_GEMINI_TESTS=1 python -m pytest tests/live -q

What it proves
--------------
* a reason exists, in Vietnamese, for most of the catalogue;
* every reason that survived is grounded -- no invented figures;
* **the model does not answer "hợp" to everything.** That is the anti-flattery
  check, and it is the reason the prompt is written as an open question with
  the computed score withheld. A run where all twelve come back `hop` means the
  question is leading the witness again, and the badge stops meaning anything.

What it does not prove
----------------------
That the sentences are *good*, or that a Vietnamese reader finds them natural.
Nobody has read them next to the places yet. It also does not prove stability:
this is one sample at temperature 0.4, not a distribution.
"""

from __future__ import annotations

import os
import re

import pytest

from app.places.catalog import GROUP, PLACES
from app.places.reasons import ReasonRow, gemini_reasons, ungrounded_numbers

pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY", "").strip()
    or os.environ.get("MOBILE_REQUIRE_GEMINI_TESTS") != "1",
    reason="live Gemini tier: needs GEMINI_API_KEY and MOBILE_REQUIRE_GEMINI_TESTS=1",
)

BY_ID = {place["id"]: place for place in PLACES}

# The places the seed data makes objectively awkward for this group of six on a
# 250k budget with a 5km limit. Named here so the assertion below is about
# specific, checkable rows rather than about a vibe.
#
#   p-the-hill-rooftop  320-450k (midpoint 71% over budget) and 5.2km away
#   p-ca-phe-vot-hem    6.1km away, and its stated capacity is 2-5 for a 6
#   p-bowling-sky       7.4km away, nearly half again the group's limit
AWKWARD = ("p-the-hill-rooftop", "p-ca-phe-vot-hem", "p-bowling-sky")


@pytest.fixture(scope="module")
def answers():
    rows = [ReasonRow(place=place) for place in PLACES]
    result = gemini_reasons(rows, GROUP)
    if not result:
        pytest.fail(
            "Gemini returned nothing for all 12 places. Either the key is "
            "rejected, the model is unreachable, or every reason failed the "
            "grounding gate -- check the warnings in the captured log."
        )
    return result


def test_the_model_answered_for_most_of_the_catalogue(answers):
    assert len(answers) >= len(PLACES) - 2, (
        f"only {len(answers)}/{len(PLACES)} places got a reason: {sorted(answers)}"
    )


def test_every_surviving_reason_is_grounded_in_the_row_it_was_given(answers):
    """Belt and braces: `parse_reasons` already drops ungrounded reasons, so
    this asserts the gate did its job rather than that the model behaved."""

    for place_id, reason in answers.items():
        assert ungrounded_numbers(reason.reason, BY_ID[place_id], GROUP) == [], (
            f"{place_id}: {reason.reason}"
        )


def test_reasons_are_vietnamese_prose_not_a_label(answers):
    vietnamese = re.compile(r"[àáảãạăâđèéẻẽẹêìíỉĩịòóỏõọôơùúủũụưỳýỷỹỵ]", re.IGNORECASE)
    for place_id, reason in answers.items():
        assert len(reason.reason) > 25, f"{place_id}: {reason.reason!r}"
        assert vietnamese.search(reason.reason), f"{place_id}: {reason.reason!r}"


def test_the_model_is_willing_to_say_a_place_does_not_suit_the_group(answers):
    """The anti-flattery gate, and the reason the prompt looks the way it does.

    A model asked "why does this suit them" returns twelve yeses and the badge
    becomes a decoration. Asked whether it suits them, with the score withheld,
    it has to actually read the row.
    """

    verdicts = {place_id: reason.verdict for place_id, reason in answers.items()}
    non_hop = {pid: v for pid, v in verdicts.items() if v != "hop"}
    assert non_hop, (
        "every place came back 'hop'. The question is leading the witness "
        f"again: {verdicts}"
    )

    # And specifically: at least one of the rows that fails on budget, distance
    # or capacity has to be among them.
    answered_awkward = [pid for pid in AWKWARD if pid in verdicts]
    assert answered_awkward, "the model skipped every awkward place"
    assert any(verdicts[pid] != "hop" for pid in answered_awkward), (
        "the three places that break budget, distance or capacity all came "
        f"back 'hop': { {pid: verdicts[pid] for pid in answered_awkward} }"
    )


def test_the_best_fitting_place_is_not_rejected(answers):
    """The mirror of the test above. A model that says no to everything is as
    useless as one that says yes to everything, and the same prompt change
    could cause either."""

    best = "p-tiem-nuong-xom-lao"  # scores 96: on budget, 5/5 traits, 1.2km, fits
    if best in answers:
        assert answers[best].verdict in ("hop", "tam"), answers[best]
