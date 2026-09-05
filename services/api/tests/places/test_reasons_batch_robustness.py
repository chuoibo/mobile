"""One malformed reason used to cost all twelve. Measured, not theorised.

Written by the backend lane while gating #81 (PR #91) to pin the defect;
kept by the devops lane as the regression test for the fix, with the
`xfail(strict=True)` on the desired-behaviour case removed now that it holds.
The history below is why the recovery path in `app.places.reasons` exists, and
is left in full so nobody has to re-measure it to know what it cost.

Gating PR #81 (merged as 43ae65d) turned up a failure the PR's own live tier
cannot see, because that tier asserts on the runs that came back and says
nothing about the runs that came back empty.

Across 23 real calls with the baseline group profile, 3 returned
`"response was not JSON"` and every place on the screen lost its AI label.
`finishReason` was `STOP` on all three and the text ended with a well-formed
`]`, so this is **not** truncation. The model quoted a trait verbatim inside a
JSON string without escaping it:

    "reason": "Quán cafe này có đặc điểm "yên tĩnh" không phù hợp với nhóm..."

`json.loads` dies at that quote, `parse_reasons` caught `JSONDecodeError` and
returned `{}`, and eleven perfectly well-formed reasons that were sitting in
the same array were thrown away with the broken one. `parse_reasons` now falls
back to decoding the array item by item, so the loss is one card, not twelve.

The route degraded honestly -- `source` dropped to `"none"`, nothing was
labelled AI that a model did not write, no money was touched -- so this was
loss of the feature, not a wrong answer. And `cached_gemini_reasons` caches
successes only, so the next request retried. But it is the Khám phá screen on
the hero path, and roughly one first load in ten opened with no AI MATCH on
any card.

The prompt itself invites the failure: it tells the model to name the specific
fact that decided the verdict, and traits like `Yên tĩnh` are exactly the kind
of short label a writer reaches for quote marks to set off. The prompt was
deliberately *not* touched by the fix -- wording changes move verdicts, and the
live measurements #91 took would all have to be re-run to know they had not.
Asking the model more nicely would also only lower the rate; the parser is what
decided that one bad sentence costs twelve cards instead of one.

Deterministic on purpose -- no key, no network, runs in the default suite.
Fixture is trimmed from the real captured payload; the shape of the break is
byte-for-byte what Gemini returned.
"""

from __future__ import annotations

from app.places.catalog import PLACES
from app.places.reasons import ReasonRow, parse_reasons

from .nhom_mau import NHOM_MAU

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


def test_the_item_carrying_the_unescaped_quote_is_the_only_one_lost():
    """The other half of the fix, and the half that is easy to lose.

    Before: two reasons in, one of them valid, nothing out. After: the broken
    item is still dropped -- it is not repaired, not guessed at, not served
    with the quotes stripped -- and it is the *only* thing dropped.

    This was the case that pinned the defect (asserting `== {}`); it now pins
    the boundary of the recovery instead. If a later edit makes the salvage
    clever enough to reconstruct `p-an-cafe-da-lat`, that is a parser inventing
    a sentence the model did not write, and this test is what says no.
    """

    kept = parse_reasons(MALFORMED_BATCH, ROWS, NHOM_MAU)
    assert set(kept) == {"p-tiem-nuong-xom-lao"}


def test_a_well_formed_reason_survives_a_neighbour_that_is_broken():
    """What the screen needs: damage confined to the row that caused it.

    Eleven of twelve cards keeping their AI label beats twelve losing it
    because one sentence had a stray quote in it.
    """

    kept = parse_reasons(MALFORMED_BATCH, ROWS, NHOM_MAU)
    assert "p-tiem-nuong-xom-lao" in kept
    assert kept["p-tiem-nuong-xom-lao"].verdict == "hop"


def test_a_clean_batch_still_parses():
    """Guard against 'fixing' the above by loosening the parser into mush.

    A recovering parser still has to keep the normal path exactly as strict:
    every field validated, verdict from the closed set.
    """

    clean = MALFORMED_BATCH.replace('"yên tĩnh"', "yên tĩnh")
    kept = parse_reasons(clean, ROWS, NHOM_MAU)
    assert set(kept) == {"p-tiem-nuong-xom-lao", "p-an-cafe-da-lat"}
    assert kept["p-an-cafe-da-lat"].verdict == "khong-hop"
