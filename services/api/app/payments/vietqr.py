"""Build a VietQR payload string (EMVCo merchant-presented QR).

The product never holds or moves money (spec section 14.1). All it does is
render a string that a Vietnamese banking app knows how to read, so the sender
transfers directly to the recipient. That is the whole scope of this module.

Structure is EMVCo tag-length-value: two digits of tag, two digits of length,
then the value, nested the same way. The final tag 63 is a CRC computed over
everything before it *including* its own "6304" header.
"""

from __future__ import annotations

__all__ = ["crc16_ccitt_false", "build_payload", "parse_tlv", "VietQRError"]

_GUID_VIETQR = "A000000727"
_SERVICE_TO_ACCOUNT = "QRIBFTTA"
_SERVICE_TO_CARD = "QRIBFTTC"
_CURRENCY_VND = "704"
_COUNTRY_VN = "VN"


class VietQRError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def crc16_ccitt_false(data: str) -> str:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, no final xor.

    The standard check value for this variant is CRC("123456789") == 0x29B1,
    which the tests assert. Getting the variant wrong is the classic way to
    produce a QR that every banking app silently refuses.
    """
    crc = 0xFFFF
    for byte in data.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def _tlv(tag: str, value: str) -> str:
    if len(tag) != 2 or not tag.isdigit():
        raise VietQRError("INVALID_TAG")
    if len(value) > 99:
        raise VietQRError("VALUE_TOO_LONG")
    return f"{tag}{len(value):02d}{value}"


def build_payload(
    *,
    bank_bin: str,
    account_number: str,
    amount_vnd: int | None = None,
    note: str | None = None,
    to_card: bool = False,
) -> str:
    """Render the payload. `amount_vnd` of None means the sender types it in.

    An amount makes the code dynamic (point-of-initiation 12), which Vietnamese
    banking apps treat as single-use. That is what we want: a request to pay one
    specific obligation, not a reusable donation code.
    """
    if not bank_bin.isdigit() or len(bank_bin) != 6:
        raise VietQRError("INVALID_BANK_BIN")
    if not account_number or not account_number.isalnum():
        raise VietQRError("INVALID_ACCOUNT_NUMBER")
    if amount_vnd is not None:
        if isinstance(amount_vnd, bool) or not isinstance(amount_vnd, int):
            raise VietQRError("AMOUNT_NOT_INTEGER")
        if amount_vnd <= 0:
            raise VietQRError("NON_POSITIVE_AMOUNT")

    beneficiary = _tlv("00", bank_bin) + _tlv("01", account_number)
    merchant_account = (
        _tlv("00", _GUID_VIETQR)
        + _tlv("01", beneficiary)
        + _tlv("02", _SERVICE_TO_CARD if to_card else _SERVICE_TO_ACCOUNT)
    )

    payload = _tlv("00", "01")
    payload += _tlv("01", "12" if amount_vnd is not None else "11")
    payload += _tlv("38", merchant_account)
    payload += _tlv("53", _CURRENCY_VND)
    if amount_vnd is not None:
        # Integer dong, rendered without decimals. A float here would be a
        # money bug of exactly the kind spec section 4 forbids.
        payload += _tlv("54", str(amount_vnd))
    payload += _tlv("58", _COUNTRY_VN)
    if note:
        payload += _tlv("62", _tlv("08", note))

    payload += "6304"
    return payload + crc16_ccitt_false(payload)


def parse_tlv(payload: str) -> dict[str, str]:
    """Parse one TLV level back into {tag: value}. Used by the tests to prove
    the builder produces something readable rather than merely well-formed."""
    result: dict[str, str] = {}
    index = 0
    while index < len(payload):
        if index + 4 > len(payload):
            raise VietQRError("TRUNCATED")
        tag = payload[index : index + 2]
        length = int(payload[index + 2 : index + 4])
        value = payload[index + 4 : index + 4 + length]
        if len(value) != length:
            raise VietQRError("TRUNCATED")
        result[tag] = value
        index += 4 + length
    return result
