"""One malformed reason costs all twelve. Measured, not theorised.

Gating PR #81 (merged as 43ae65d) turned up a failure the PR's own live tier
cannot see, because that tier asserts on the runs that came back and says
nothing about the runs that came back empty.

Across 23 real calls with the baseline group profile, 3 returned
`"response was not JSON"` and every place on the screen lost its AI label.
`finishReason` was `STOP` on all three and the text ended with a well-formed
`]`, so this is **not** truncation. The model quoted a trait verbatim inside a
JSON string without escaping it:

    "reason": "Quán cafe này có đặc điểm "yên tĩnh" không phù hợp với nhóm..."

`json.loads` dies at that quote, `parse_reasons` catches `JSONDecodeError` and
returns `{}`, and eleven perfectly well-formed reasons that were sitting in the
same array are thrown away with the broken one.

The route degrades honestly -- `source` drops to `"none"`, nothing is labelled
AI that a model did not write, no money is touched -- so this is loss of the
feature, not a wrong answer. And `cached_gemini_reasons` caches successes only,
so the next request retries. But it is the Khám phá screen on the hero path,
and roughly one first load in ten opens with no AI MATCH on any card.

The prompt itself invites the failure: it tells the model to name the specific
fact that decided the verdict, and traits like `Yên tĩnh` are exactly the kind
of short label a writer reaches for quote marks to set off.

Deterministic on purpose -- no key, no network, runs in the default suite.
Fixture is trimmed from the real captured payload; the shape of the break is
byte-for-byte what Gemini returned.
"""

from __future__ import annotations

import pytest

from app.places.catalog import GROUP, PLACES
from app.places.reasons import ReasonRow, parse_reasons

BY_ID = {place["id"]: place for place in PLACES}

# Item 1 is flawless. Item 2 carries the unescaped quotes around `yên tĩnh`,
# copied from the captured response. Item 1 is the collateral damage.
MALFORMED_BATCH = """[
  {
    "id": "p-tiem-nuong-xom-lao",
    "verdict": "hop",
    "reason": "Có đồ nướng, ngoài trời và view đẹp, giá 200-250k vừa ngân sách nhóm."
  },
  {
    "id": "p-an-cafe-da-lat",
    "verdict": "khong-hop",
    "reason": "Quán cafe này có đặc điểm "yên tĩnh" không phù hợp với nhóm đông."
  }
]"""

ROWS = [
    ReasonRow(place=BY_ID["p-tiem-nuong-xom-lao"]),
    ReasonRow(place=BY_ID["p-an-cafe-da-lat"]),
]


def test_a_single_unescaped_quote_discards_the_whole_batch():
    """Current behaviour, pinned so a fix has something to change.

    This passing is the bug report: two reasons went in, one of them was
    valid, nothing came out.
    """

    assert parse_reasons(MALFORMED_BATCH, ROWS, GROUP) == {}


@pytest.mark.xfail(
    strict=True,
    reason=(
        "known defect from gating #81: parse_reasons is all-or-nothing on the "
        "batch, so one unescaped quote drops every other reason with it. "
        "Owner is the devops lane (app/places/reasons.py); reported via "
        "bug-to. Remove this marker when the parser recovers per-item."
    ),
)
def test_a_well_formed_reason_survives_a_neighbour_that_is_broken():
    """What the screen needs: damage confined to the row that caused it.

    Eleven of twelve cards keeping their AI label beats twelve losing it
    because one sentence had a stray quote in it.
    """

    kept = parse_reasons(MALFORMED_BATCH, ROWS, GROUP)
    assert "p-tiem-nuong-xom-lao" in kept
    assert kept["p-tiem-nuong-xom-lao"].verdict == "hop"


def test_a_clean_batch_still_parses():
    """Guard against 'fixing' the above by loosening the parser into mush.

    A recovering parser still has to keep the normal path exactly as strict:
    every field validated, verdict from the closed set.
    """

    clean = MALFORMED_BATCH.replace('"yên tĩnh"', "yên tĩnh")
    kept = parse_reasons(clean, ROWS, GROUP)
    assert set(kept) == {"p-tiem-nuong-xom-lao", "p-an-cafe-da-lat"}
    assert kept["p-an-cafe-da-lat"].verdict == "khong-hop"
