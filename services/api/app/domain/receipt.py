"""Pure normalization for receipt readings produced by a vision backend.

The backend copies text from the receipt. This module deterministically turns
that text into integer dong while preserving independently observed amounts.
It performs no I/O and never asks a model to reconcile receipt arithmetic.
"""

from __future__ import annotations

import math
import re

from .contract import MAX_AMOUNT_VND

__all__ = ["ReceiptError", "normalize_vnd", "read_receipt"]


_CURRENCY_MARKER = r"(?:VND|VNĐ|đ|₫|d)"
_SUFFIX_PATTERN = re.compile(
    r"^(?P<number>.+?)\s*(?P<suffix>nghìn|ngàn|triệu|tr|k)$",
    re.IGNORECASE,
)
_GROUPED_PATTERN = re.compile(
    r"\d{1,3}(?P<separator>[., ])\d{3}(?:(?P=separator)\d{3})*"
)
_PLAIN_PATTERN = re.compile(r"\d+")
_FRACTIONAL_PATTERN = re.compile(r"(?P<whole>\d+)[.,](?P<fraction>\d+)")


class ReceiptError(Exception):
    """Report one stable receipt-reading failure."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _unreadable() -> ReceiptError:
    return ReceiptError("UNREADABLE_AMOUNT")


def _strip_currency_marker(value: str) -> str:
    leading = re.fullmatch(
        rf"\s*{_CURRENCY_MARKER}\s*(?P<amount>.*?)\s*", value, re.IGNORECASE
    )
    if leading is not None:
        value = leading.group("amount")

    trailing = re.fullmatch(
        rf"\s*(?P<amount>.*?)\s*{_CURRENCY_MARKER}\s*", value, re.IGNORECASE
    )
    if trailing is not None:
        value = trailing.group("amount")
    return value.strip()


def _checked_amount(value: int) -> int:
    if value < 0 or value > MAX_AMOUNT_VND:
        raise _unreadable()
    return value


def _parse_amount_digits(value: str) -> int:
    significant = value.lstrip("0") or "0"
    if len(significant) > len(str(MAX_AMOUNT_VND)):
        raise _unreadable()
    return int(significant)


def _parse_suffixed(number: str, multiplier: int) -> int:
    if _GROUPED_PATTERN.fullmatch(number):
        raise _unreadable()

    if _PLAIN_PATTERN.fullmatch(number):
        return _checked_amount(_parse_amount_digits(number) * multiplier)

    match = _FRACTIONAL_PATTERN.fullmatch(number)
    if match is None:
        raise _unreadable()

    whole = match.group("whole")
    fraction = match.group("fraction")
    scale_digits = 6 if multiplier == 1_000_000 else 3
    if len(fraction) > scale_digits and any(
        digit != "0" for digit in fraction[scale_digits:]
    ):
        raise _unreadable()
    fraction_head = fraction[:scale_digits]
    fractional_amount = int(fraction_head) * 10 ** (scale_digits - len(fraction_head))
    amount = _parse_amount_digits(whole) * multiplier + fractional_amount
    return _checked_amount(amount)


def normalize_vnd(text: str) -> int:
    """Read one unambiguous Vietnamese amount as an exact integer dong."""

    if not isinstance(text, str):
        raise _unreadable()

    value = re.sub(r"\s+", " ", text.replace("\u00a0", " ").replace("\u202f", " "))
    value = _strip_currency_marker(value.strip())
    if not value:
        raise _unreadable()

    suffix = _SUFFIX_PATTERN.fullmatch(value)
    if suffix is not None:
        suffix_text = suffix.group("suffix").casefold()
        multiplier = 1_000_000 if suffix_text in {"tr", "triệu"} else 1_000
        return _parse_suffixed(suffix.group("number").strip(), multiplier)

    if _PLAIN_PATTERN.fullmatch(value):
        return _checked_amount(_parse_amount_digits(value))

    grouped = _GROUPED_PATTERN.fullmatch(value)
    if grouped is not None:
        separator = grouped.group("separator")
        return _checked_amount(_parse_amount_digits(value.replace(separator, "")))

    raise _unreadable()


def _read_quantity(item: dict) -> int:
    if "quantity_text" not in item:
        return 1
    quantity_text = item["quantity_text"]
    if not isinstance(quantity_text, str):
        raise ReceiptError("INVALID_QUANTITY")
    stripped = quantity_text.strip()
    if _PLAIN_PATTERN.fullmatch(stripped) is None:
        raise ReceiptError("INVALID_QUANTITY")
    try:
        quantity = int(stripped)
    except ValueError:
        raise ReceiptError("INVALID_QUANTITY") from None
    if quantity <= 0:
        raise ReceiptError("INVALID_QUANTITY")
    return quantity


def _read_confidence(raw: dict) -> int:
    if "confidence" not in raw:
        raise ReceiptError("INVALID_CONFIDENCE")
    confidence = raw["confidence"]
    if type(confidence) not in {int, float}:
        raise ReceiptError("INVALID_CONFIDENCE")
    if not 0 <= confidence <= 1:
        raise ReceiptError("INVALID_CONFIDENCE")
    if type(confidence) is float and not math.isfinite(confidence):
        raise ReceiptError("INVALID_CONFIDENCE")
    return int(confidence * 100)


def read_receipt(raw: dict) -> dict:
    """Normalize one raw reading without reconciling independent amounts."""

    if not isinstance(raw, dict):
        raise ReceiptError("INVALID_RECEIPT")
    if "items" not in raw or not isinstance(raw["items"], list):
        raise ReceiptError("INVALID_RECEIPT")
    if not raw["items"]:
        raise ReceiptError("NO_ITEMS_READ")
    if "total_text" not in raw:
        raise ReceiptError("INVALID_RECEIPT")

    confidence = _read_confidence(raw)
    items: list[dict] = []
    warnings: list[str] = []

    for raw_item in raw["items"]:
        if not isinstance(raw_item, dict):
            raise ReceiptError("INVALID_RECEIPT_ITEM")
        name = raw_item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ReceiptError("INVALID_RECEIPT_ITEM")
        if "line_total_text" not in raw_item:
            raise ReceiptError("INVALID_RECEIPT_ITEM")

        quantity = _read_quantity(raw_item)
        line_total_vnd = normalize_vnd(raw_item["line_total_text"])
        unit_price_text = raw_item.get("unit_price_text")
        if unit_price_text is not None:
            unit_price_vnd = normalize_vnd(unit_price_text)
            if unit_price_vnd * quantity != line_total_vnd:
                warnings.append(
                    f'Đơn giá in trên bill của "{name}" nhân số lượng '
                    "không khớp thành tiền; giữ nguyên cả hai số."
                )
        elif line_total_vnd % quantity == 0:
            unit_price_vnd = line_total_vnd // quantity
        else:
            unit_price_vnd = None

        items.append(
            {
                "name": name,
                "quantity": quantity,
                "unit_price_vnd": unit_price_vnd,
                "line_total_vnd": line_total_vnd,
            }
        )

    items_total_vnd = sum(item["line_total_vnd"] for item in items)
    total_text = raw["total_text"]
    if total_text is None:
        total_vnd = None
        totals_agree = None
        total_difference_vnd = None
    else:
        total_vnd = normalize_vnd(total_text)
        total_difference_vnd = total_vnd - items_total_vnd
        totals_agree = total_difference_vnd == 0
        if not totals_agree:
            warnings.append(
                "Tổng in trên bill chênh "
                f"{total_difference_vnd:+d} đồng so với tổng các dòng; "
                "giữ nguyên cả hai số."
            )

    return {
        "items": items,
        "items_total_vnd": items_total_vnd,
        "total_vnd": total_vnd,
        "totals_agree": totals_agree,
        "total_difference_vnd": total_difference_vnd,
        "confidence": confidence,
        "warnings": warnings,
    }
