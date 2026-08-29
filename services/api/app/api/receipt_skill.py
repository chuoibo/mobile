"""Application boundary for pluggable receipt-reading backends."""

from __future__ import annotations

from typing import Protocol

from app.domain.receipt import ReceiptError, read_scanned_document

__all__ = [
    "ALLOWED_MIME_TYPES",
    "MAX_IMAGE_BYTES",
    "ReceiptReader",
    "run_receipt_skill",
]


ALLOWED_MIME_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/heic"})
MAX_IMAGE_BYTES = 8 * 1024 * 1024


class ReceiptReader(Protocol):
    """Copy raw receipt fields from one in-memory image."""

    def read(self, image: bytes, mime_type: str) -> dict:
        """Return the raw receipt-reading contract."""
        ...


def run_receipt_skill(image: bytes, mime_type: str, *, reader: ReceiptReader) -> dict:
    """Validate an upload before reading and normalize the raw result."""

    if not image:
        raise ReceiptError("EMPTY_IMAGE")
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ReceiptError("UNSUPPORTED_IMAGE_TYPE")
    if len(image) > MAX_IMAGE_BYTES:
        raise ReceiptError("IMAGE_TOO_LARGE")

    raw = reader.read(image, mime_type)
    result = read_scanned_document(raw)
    # ADR-0009 decision 4: this skill publishes no confidence score. The number
    # is what decides the outcome above, so it is computed and kept, but a
    # percentage on a screen invites a rule ("accept anything over 90"), and
    # rd-qa-03 measured why that rule would be wrong -- confidence tracked how
    # legible the text was, not whether the money was right, and drifted
    # 1.00/1.00/0.95/0.95/0.95 across repeat calls on one image at temperature 0.
    # What survives is the decision it drove: needs_review, and words.
    result.pop("confidence", None)
    return result
