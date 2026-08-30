"""Pure normalization for receipt readings produced by a vision backend.

The backend copies text from the receipt. This module deterministically turns
that text into integer dong while preserving independently observed amounts.
It performs no I/O and never asks a model to reconcile receipt arithmetic.
"""

from __future__ import annotations

import math
import re

from .contract import MAX_AMOUNT_VND

__all__ = [
    "CONFIDENCE_FLOOR",
    "CONFIDENCE_REVIEW",
    "DOCUMENT_TYPE_OTHER",
    "DOCUMENT_TYPE_PRICE_LIST",
    "DOCUMENT_TYPE_RECEIPT",
    "ReceiptError",
    "normalize_vnd",
    "read_receipt",
    "read_scanned_document",
]


CONFIDENCE_FLOOR = 50
CONFIDENCE_REVIEW = 90

# What the reader is asked to decide before it transcribes anything. Only the
# first value is admissible; the other two exist so the reader has somewhere to
# put a photograph that is not a bill, instead of being forced to describe one.
DOCUMENT_TYPE_RECEIPT = "receipt"
DOCUMENT_TYPE_PRICE_LIST = "price_list"
DOCUMENT_TYPE_OTHER = "other"


# The unit is a word before it is a sign, and both reach this function
# unchanged: the readers are told to preserve the money form exactly as
# written, so "480.000đ" and "480000 đồng" both arrive as typed. Listing only
# the signs made the product refuse a reading it had got right and blame the
# person who wrote the message (qa-tt-0034).
#
# "đ" and "d" already stood alone here, so "đồng phục" is not newly at risk: a
# marker is only stripped when it is the entire head or tail of the field, and
# what survives ("phục") is still refused.
#
# Longest form first is convention, not load-bearing: measured both ways, the
# engine backtracks past "đ" and reaches "đồng" regardless. Written this way so
# a reader need not reason about backtracking to see which form is meant.
_CURRENCY_MARKER = r"(?:VND|VNĐ|đồng|dong|đ|₫|d)"
# The compound precedes "nghìn" for the same reason and with the same caveat:
# alternation is retried in full at each expansion of the lazy number, so "2
# trăm nghìn" reads the same with the compound listed last.
_SUFFIX_PATTERN = re.compile(
    r"^(?P<number>.+?)\s*"
    r"(?P<suffix>trăm\s*nghìn|trăm\s*ngàn|nghìn|ngàn|triệu|tr|k)$",
    re.IGNORECASE,
)
# Bare "trăm" is deliberately absent. "2 trăm" is 200 dong on a price list and
# 200000 in conversation; a function that cannot tell them apart must refuse
# rather than pick one.
_SUFFIX_MULTIPLIERS = {
    "trămnghìn": 100_000,
    "trămngàn": 100_000,
    "nghìn": 1_000,
    "ngàn": 1_000,
    "k": 1_000,
    "triệu": 1_000_000,
    "tr": 1_000_000,
}
_GROUPED_PATTERN = re.compile(
    r"\d{1,3}(?P<separator>[., ])\d{3}(?:(?P=separator)\d{3})*"
)
_PLAIN_PATTERN = re.compile(r"\d+")
_FRACTIONAL_PATTERN = re.compile(r"(?P<whole>\d+)[.,](?P<fraction>\d+)")
# A Vietnamese bill prints the count beside the dish -- "Trà đá X4" -- rather
# than in a column of its own, and the reader transcribes that marker into
# quantity_text. Both orders occur on paper, and the ASCII "x" and the
# multiplication sign are the same mark set by different tools.
#
# The strictness is the point. This admits a marker wrapped around digits and
# nothing else, so "vài", "4 phần" and "x4x" still raise INVALID_QUANTITY. A
# quantity that cannot be read exactly must not be guessed: it divides a real
# line total into the unit price shown beside a real dish.
_QUANTITY_MARKER_PATTERN = re.compile(
    r"(?:[x×]\s*(?P<leading>\d+)|(?P<trailing>\d+)\s*[x×])",
    re.IGNORECASE,
)


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
    # How many digits the fractional part is worth, read off the multiplier
    # itself rather than listed by hand. Hard-coding 3 for everything that is
    # not a million read "1,5 trăm nghìn" as 100500 -- a wrong amount that
    # still looks like money.
    scale_digits = len(str(multiplier)) - 1
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
        suffix_text = re.sub(r"\s+", "", suffix.group("suffix").casefold())
        multiplier = _SUFFIX_MULTIPLIERS[suffix_text]
        return _parse_suffixed(suffix.group("number").strip(), multiplier)

    if _PLAIN_PATTERN.fullmatch(value):
        return _checked_amount(_parse_amount_digits(value))

    grouped = _GROUPED_PATTERN.fullmatch(value)
    if grouped is not None:
        separator = grouped.group("separator")
        return _checked_amount(_parse_amount_digits(value.replace(separator, "")))

    raise _unreadable()


def _read_quantity(item: dict) -> int:
    """Read a printed count, treating "none was printed" as one of the item.

    The model has three ways of saying a line prints no quantity column --
    omitting the key, sending ``null``, sending an empty or blank string -- and
    only the first used to be accepted. The other two raised INVALID_QUANTITY,
    which ``read_receipt`` applies to the WHOLE document, so one blank on one
    line threw away every correctly-read line beside it. rd-qa-38 measured that
    on the hero path: 153 of 153 observed failures were this one code, and none
    of them were a picture the model had misread.

    Reading a blank as 1 cannot move money. ``line_total_text`` is transcribed
    independently and the bill total is the sum of those line totals, so no
    count chosen here enters an amount. A count is used only to cross-check a
    printed unit price and to derive one when the bill printed none, where 1
    makes the derivation ``line_total // 1`` -- the identity, inventing no
    number. That is why this widening is safe while "x4" had to be read exactly
    (#213): 4 genuinely divides a real total.

    Widening "not printed" must not widen "printed and unreadable" -- "vài",
    "0" and "2.5" are still refusals, and a non-string that is not ``None``
    (4, [], True) is a broken contract rather than a blank.
    """

    if "quantity_text" not in item:
        return 1
    quantity_text = item["quantity_text"]
    if quantity_text is None:
        return 1
    if not isinstance(quantity_text, str):
        raise ReceiptError("INVALID_QUANTITY")
    stripped = quantity_text.strip()
    if not stripped:
        return 1
    if _PLAIN_PATTERN.fullmatch(stripped) is None:
        marker = _QUANTITY_MARKER_PATTERN.fullmatch(stripped)
        if marker is None:
            raise ReceiptError("INVALID_QUANTITY")
        stripped = marker.group("leading") or marker.group("trailing")
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


def read_scanned_document(raw: dict) -> dict:
    """Admit only a legible receipt, then normalize it.

    Kept separate from ``read_receipt`` because the two answer different
    questions. This one asks whether the photograph may be turned into money at
    all; ``read_receipt`` asks what the transcribed strings mean. Splitting them
    also leaves the normalizer callable on its own, which the rd-qa-03
    regression file does.

    The order of the two refusals is the whole design. Legibility first: under
    ``CONFIDENCE_FLOOR`` the document type is exactly as untrustworthy as the
    amounts, and a real bill photographed too badly to read comes back labelled
    "other" because the model could not see it either. "Chụp lại" is the true
    instruction there; "this is not a receipt" would send that person looking
    for a different piece of paper.

    Then the type, fail-closed: only the exact string ``receipt`` opens the
    gate. A reading with no ``document_type``, or one this module does not
    recognise, is refused -- a backend that did not answer the question has
    established nothing, and the default it would fall back to is the very
    assumption that produced 340.000 dong from a menu.
    """

    if not isinstance(raw, dict):
        raise ReceiptError("INVALID_RECEIPT")

    if _read_confidence(raw) < CONFIDENCE_FLOOR:
        raise ReceiptError("RECEIPT_TOO_BLURRY")

    document_type = raw.get("document_type")
    if document_type == DOCUMENT_TYPE_RECEIPT:
        return read_receipt(raw)
    if document_type == DOCUMENT_TYPE_PRICE_LIST:
        raise ReceiptError("NOT_A_RECEIPT_PRICE_LIST")
    raise ReceiptError("NOT_A_RECEIPT")


def read_receipt(raw: dict) -> dict:
    """Normalize one raw reading without reconciling independent amounts."""

    if not isinstance(raw, dict):
        raise ReceiptError("INVALID_RECEIPT")
    if "items" not in raw or not isinstance(raw["items"], list):
        raise ReceiptError("INVALID_RECEIPT")

    confidence = _read_confidence(raw)
    if confidence < CONFIDENCE_FLOOR:
        raise ReceiptError("RECEIPT_TOO_BLURRY")
    if not raw["items"]:
        raise ReceiptError("NO_ITEMS_READ")
    if "total_text" not in raw:
        raise ReceiptError("INVALID_RECEIPT")

    items: list[dict] = []
    warnings: list[str] = []
    if confidence < CONFIDENCE_REVIEW:
        warnings.append(
            "Ảnh bill chưa đủ rõ; hãy kiểm tra từng món và số tiền trước khi xác nhận."
        )

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
        warnings.append(
            "Không đọc thấy tổng in trên bill để đối chiếu với tổng các dòng."
        )
    else:
        total_vnd = normalize_vnd(total_text)
        total_difference_vnd = total_vnd - items_total_vnd
        totals_agree = total_difference_vnd == 0
        if not totals_agree:
            # Two different failures used to arrive as one identical sentence.
            # A bill that does not add up and a reading that misread four lines
            # both produce a difference, but they need opposite actions: query
            # the restaurant, or re-check every line against the paper. The
            # amount is stated identically either way; only the attribution
            # changes, because confidence can say whether the reading was clear
            # enough for the difference to be worth believing.
            if confidence < CONFIDENCE_REVIEW:
                warnings.append(
                    "Tổng in trên bill chênh "
                    f"{total_difference_vnd:+d} đồng so với tổng các dòng, "
                    "nhưng ảnh chưa đủ rõ nên chênh lệch này có thể do đọc sai "
                    "dòng chứ không phải do bill; đối chiếu từng dòng với tờ "
                    "giấy trước khi xác nhận."
                )
            else:
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
        # Derived from the warnings rather than listed alongside them. This is
        # the only field the app branches on to demand per-item confirmation,
        # so a warning that ships without it is a warning nothing surfaces --
        # which is the rd-qa-03 complaint one layer up. Found live: the mockup
        # bill read at confidence 0.98 with 151.000 dong unaccounted for
        # between the lines and the printed total, warned about it, and asked
        # nobody to look.
        "needs_review": bool(warnings),
        "warnings": warnings,
    }
