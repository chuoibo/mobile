"""The hole the confidence gate leaves open: a bill that contradicts itself.

`CONFIDENCE_FLOOR`/`CONFIDENCE_REVIEW` gate on how LEGIBLE the text is, which is
what the vision prompt asks the model for. They say nothing about whether the
numbers are RIGHT. `app/domain/receipt.py`'s own docstring records the two
measured counterexamples: at confidence 98 one line came back 40.000 short
(Gaussian blur r=2), and at 95 one line came back 10.000 short (JPEG q30). Both
sit above `CONFIDENCE_REVIEW`, so no confidence threshold can reach them --
the wrong-money band overlaps the reads-fine band.

There is nonetheless a hard, arithmetic signal in exactly those readings, and
the module already computes it: the total PRINTED on the paper disagrees with
the sum of the lines the model read. `totals_agree` goes False and
`total_difference_vnd` carries the gap. Nothing consults either one.

So `needs_review` is currently backwards about evidence:

    no printed total at all  -> nothing to cross-check -> needs_review True
    printed total DISAGREES  -> cross-check FAILED     -> needs_review False

Missing evidence flags the reading; contradicting evidence does not. The field
`needs_review` is the one the app branches on (its own test says so:
"The app branches on this field, so it may never be absent"), so a bill whose
own arithmetic is 40.000d off arrives at the split screen marked reviewed.

Deterministic like the rest of rd-qa-03: no network, no model, no image, pure
domain call. Expected RED on the branch that carries the receipt reader until
`needs_review` also fires on a failed cross-check -- that redness IS the
finding. Inert on `main`, where `app.domain.receipt` does not exist yet.

Measured against c67e71b (PR #55, backend/doc-bill-bang-gemini).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

_API = pathlib.Path(__file__).resolve().parents[3] / "services" / "api"
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

receipt = pytest.importorskip(
    "app.domain.receipt",
    reason="app.domain.receipt chưa có trên nhánh này (đi kèm reader Gemini)",
)


def _reading(*, confidence: float, total_text: str | None, second_line: str) -> dict:
    """One legible reading; only the misread line and the printed total vary."""
    return {
        "items": [
            {"name": "Phở bò tái", "quantity_text": "1", "line_total_text": "65.000"},
            {
                "name": "Bún chả Hà Nội",
                "quantity_text": "1",
                "line_total_text": second_line,
            },
        ],
        "total_text": total_text,
        "confidence": confidence,
    }


# The two degradations measured live, both landing above CONFIDENCE_REVIEW.
# printed_total is what the paper says; second_line is what the model read.
MISREADS = [
    # blur r=2: one line came back 40.000 short
    pytest.param(0.98, "70.000", "175.000", 40_000, id="blur-r2-conf98-thieu-40k"),
    # JPEG q30: one line came back 10.000 short
    pytest.param(0.95, "100.000", "175.000", 10_000, id="jpeg-q30-conf95-thieu-10k"),
]


@pytest.mark.parametrize(
    "confidence,second_line,printed_total,gap_vnd", MISREADS
)
def test_a_bill_that_contradicts_its_own_total_is_not_marked_reviewed(
    confidence: float, second_line: str, printed_total: str, gap_vnd: int
):
    """The finding: the cross-check fails and `needs_review` stays False.

    The paper prints one total, the lines the model read add up to another, and
    the gap is tens of thousands of dong. That is not a judgement call -- it is
    the bill disagreeing with itself, computed by this very module. A reading
    carrying that contradiction must not reach the split screen flagged clean.
    """
    result = receipt.read_receipt(
        _reading(
            confidence=confidence, total_text=printed_total, second_line=second_line
        )
    )

    # Positive control: the contradiction really is present and really is this
    # big, so the assertion below cannot pass on a reading that simply agrees.
    assert result["totals_agree"] is False
    assert result["total_difference_vnd"] == gap_vnd

    assert result["needs_review"] is True, (
        f"Tổng in trên bill lệch {gap_vnd:,}đ so với tổng các dòng ở mức tin cậy "
        f"{result['confidence']}%, nhưng needs_review={result['needs_review']}: "
        "màn hình chia tiền nhận bản đọc này như một bản đã kiểm."
    )


@pytest.mark.parametrize(
    "confidence,second_line,printed_total,gap_vnd", MISREADS
)
def test_the_contradiction_is_explained_where_the_user_reads_it(
    confidence: float, second_line: str, printed_total: str, gap_vnd: int
):
    """A flag with no sentence is a flag nobody can act on.

    Currently GREEN -- the disagreement warning does fire. Pinned here so a fix
    that flips `needs_review` cannot quietly drop the words that explain it.
    """
    result = receipt.read_receipt(
        _reading(
            confidence=confidence, total_text=printed_total, second_line=second_line
        )
    )

    assert any("chênh" in warning for warning in result["warnings"]), (
        f"Không có câu nào nói cho người dùng biết bill lệch {gap_vnd:,}đ: "
        f"{result['warnings']}"
    )


def test_the_same_reading_with_a_matching_total_is_not_flagged():
    """Negative control: with the totals agreeing, False is the right answer.

    Without this, the test above could pass on a build that flags every single
    reading, which would be a different bug wearing the same green tick.
    """
    result = receipt.read_receipt(
        _reading(confidence=0.98, total_text="135.000", second_line="70.000")
    )

    assert result["totals_agree"] is True
    assert result["needs_review"] is False


def test_missing_evidence_flags_but_failed_evidence_does_not():
    """The asymmetry, stated as one comparison.

    `total_text=None` means nothing cross-checks the lines, and the gate rightly
    flags it. A printed total that DISAGREES is strictly stronger evidence that
    the read is wrong -- it is the cross-check coming back failed rather than
    absent -- yet it flags less. Whatever the rule is, it cannot be softer here
    than in the case where there is no evidence at all.
    """
    no_total = receipt.read_receipt(
        _reading(confidence=0.98, total_text=None, second_line="70.000")
    )
    disagreeing_total = receipt.read_receipt(
        _reading(confidence=0.98, total_text="175.000", second_line="70.000")
    )

    assert no_total["needs_review"] is True  # already the shipped behaviour

    assert disagreeing_total["needs_review"] >= no_total["needs_review"], (
        "Không có tổng để đối chiếu thì cảnh báo, nhưng tổng đối chiếu KHÔNG "
        "khớp thì lại không: thiếu bằng chứng bị gắn cờ nặng hơn bằng chứng "
        "phản bác."
    )
