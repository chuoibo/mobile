"""Two guards the receipt reader does not have yet (rd-qa-03).

These are deterministic: no network, no model, no image. They call the pure
domain normalizer with readings shaped exactly like the ones the real Gemini
backend returned during the rd-qa-03 adversarial run, and assert the guard that
was missing in both cases.

Why this file skips on `main`: `app.domain.receipt` arrives with the Gemini
receipt reader, which is not merged yet. On `main` there is nothing to guard, so
the file skips. On the branch that carries the reader it is expected to be RED
until the guards land -- that redness IS the finding, not a broken test.

Evidence behind each case is in docs/claude/2026-08-29/rd-qa-03-ai-co-bia-khong.md.
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


def _reading(*, confidence: float, total_text: str | None) -> dict:
    """A well-formed reading, varying only the two fields under test."""
    return {
        "items": [
            {"name": "Pho bo tai", "line_total_text": "65.000"},
            {"name": "Bun cha Ha Noi", "line_total_text": "70.000"},
        ],
        "total_text": total_text,
        "confidence": confidence,
    }


def test_low_confidence_reading_is_not_returned_as_plain_fact():
    """A 30%-confidence read must not look like a 98%-confidence read.

    Observed live at Gaussian blur r=12: confidence 0.30-0.40, eight item
    amounts returned, every one of them wrong, HTTP 200, and the only warning
    was the generic totals-disagree line that a correct read also produces.
    """
    result = receipt.read_receipt(_reading(confidence=0.30, total_text=None))

    assert result["confidence"] == 30
    assert result["warnings"], (
        "Đọc ở mức tin cậy 30% mà không kèm cảnh báo nào: màn hình không thể "
        "phân biệt số đọc chắc với số đoán mò."
    )


def test_receipt_without_a_printed_total_is_flagged():
    """No printed total means nothing independently checks the item lines.

    Observed live with a restaurant MENU photo: eight items, confidence 95-100,
    total_text null, warnings [] -- so items_total_vnd (340.000) is presented
    with exactly the same confidence as a bill whose printed total confirms it.
    """
    result = receipt.read_receipt(_reading(confidence=0.95, total_text=None))

    assert result["total_vnd"] is None
    assert result["items_total_vnd"] == 135_000
    assert result["warnings"], (
        "Bill không in tổng thì không có gì đối chứng các dòng, nhưng kết quả "
        "trả về không cảnh báo gì -- tổng cộng dồn trông y như tổng đã kiểm."
    )
