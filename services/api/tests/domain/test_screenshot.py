"""Pure F26 contract tests for reading one transaction screenshot."""

from __future__ import annotations

from importlib import import_module

import pytest

from app.domain.contract import MAX_AMOUNT_VND


def _contract():
    return import_module("app.domain.screenshot")


def _raw(**overrides) -> dict:
    reading = {
        "source": "grab",
        "merchant": "Quán Cơm Nhà",
        "total_text": "180k",
        "occurred_on": "2030-08-30",
        "confidence": 0.99,
    }
    reading.update(overrides)
    return reading


@pytest.mark.parametrize("source", ["grab", "shopeefood", "banking", "receipt"])
def test_screenshot_normalizes_each_transaction_source(source: str) -> None:
    module = _contract()

    result = module.read_screenshot(
        _raw(source=source, merchant="  Quán Cơm Nhà  ")
    )

    assert result == {
        "source": source,
        "merchant": "Quán Cơm Nhà",
        "total_vnd": 180_000,
        "occurred_on": "2030-08-30",
        "needs_review": True,
    }
    assert set(result) == {
        "source",
        "merchant",
        "total_vnd",
        "occurred_on",
        "needs_review",
    }
    assert "confidence" not in result


@pytest.mark.parametrize(
    ("total_text", "total_vnd"),
    [("1 triệu", 1_000_000), ("180.000đ", 180_000)],
)
def test_screenshot_reuses_vietnamese_amount_normalization(
    total_text: str, total_vnd: int
) -> None:
    module = _contract()

    result = module.read_screenshot(_raw(total_text=total_text))

    assert result["total_vnd"] == total_vnd


@pytest.mark.parametrize("reading", [None, [], "grab", 7])
def test_screenshot_requires_an_object(reading) -> None:
    module = _contract()

    with pytest.raises(module.ScreenshotError) as caught:
        module.read_screenshot(reading)

    assert caught.value.code == "UNREADABLE"


@pytest.mark.parametrize("source", [None, "", "other-app", "Grab", 7, True])
def test_screenshot_rejects_an_unknown_source(source) -> None:
    module = _contract()

    with pytest.raises(module.ScreenshotError) as caught:
        module.read_screenshot(_raw(source=source))

    assert caught.value.code == "UNREADABLE"


def test_screenshot_other_is_an_explicit_non_transaction() -> None:
    module = _contract()

    with pytest.raises(module.ScreenshotError) as caught:
        module.read_screenshot(_raw(source="other"))

    assert caught.value.code == "NOT_A_TRANSACTION"


@pytest.mark.parametrize("merchant", [None, 7, True, "", "   "])
def test_screenshot_rejects_an_unusable_merchant(merchant) -> None:
    module = _contract()

    with pytest.raises(module.ScreenshotError) as caught:
        module.read_screenshot(_raw(merchant=merchant))

    assert caught.value.code == "UNREADABLE"


@pytest.mark.parametrize("total", [180_000, 180_000.0, True, None])
def test_screenshot_rejects_model_money_that_is_not_text(total) -> None:
    module = _contract()

    with pytest.raises(module.ScreenshotError) as caught:
        module.read_screenshot(_raw(total_text=total))

    assert caught.value.code == "UNREADABLE"


# The over-ceiling case is derived because a 13-digit literal is both brittle
# and indistinguishable from leaked financial data to the repository guard.
@pytest.mark.parametrize("total_text", ["0", "-1", "", str(MAX_AMOUNT_VND + 1)])
def test_screenshot_rejects_non_positive_or_oversized_money(
    total_text: str,
) -> None:
    module = _contract()

    with pytest.raises(module.ScreenshotError) as caught:
        module.read_screenshot(_raw(total_text=total_text))

    assert caught.value.code == "UNREADABLE"


@pytest.mark.parametrize(
    "occurred_on",
    ["", "30-08-2030", "2030-02-30", "2030-W35-5", 20300830, True, []],
)
def test_screenshot_rejects_an_invalid_transaction_date(occurred_on) -> None:
    module = _contract()

    with pytest.raises(module.ScreenshotError) as caught:
        module.read_screenshot(_raw(occurred_on=occurred_on))

    assert caught.value.code == "UNREADABLE"


@pytest.mark.parametrize("occurred_on", [None, pytest.param("missing", id="missing")])
def test_screenshot_allows_an_absent_transaction_date(occurred_on) -> None:
    module = _contract()
    reading = _raw(occurred_on=occurred_on)
    if occurred_on == "missing":
        reading.pop("occurred_on")

    result = module.read_screenshot(reading)

    assert result["occurred_on"] is None


@pytest.mark.parametrize(
    "identity_key",
    [
        "paid_by",
        "payer",
        "person_id",
        "people",
        "shared_by",
        "participants",
        "who-paid",
        "recipientName",
    ],
)
def test_screenshot_refuses_model_authored_identity(identity_key: str) -> None:
    module = _contract()

    with pytest.raises(module.ScreenshotError) as caught:
        module.read_screenshot({**_raw(), identity_key: "Người trong ảnh"})

    assert caught.value.code == "MODEL_NAMED_A_PERSON"


def test_screenshot_rejects_non_string_keys() -> None:
    module = _contract()

    with pytest.raises(module.ScreenshotError) as caught:
        module.read_screenshot({**_raw(), 7: "unexpected"})

    assert caught.value.code == "UNREADABLE"
