"""Application boundary for pluggable receipt-reading backends."""

from __future__ import annotations

from typing import Protocol

from app.domain.receipt import ReceiptError, read_scanned_document
from app.media.images import ImageRejected, sanitize_image

__all__ = [
    "ALLOWED_MIME_TYPES",
    "MAX_IMAGE_BYTES",
    "ReceiptReader",
    "run_receipt_skill",
]


# ``image/heic`` was on this list and is deliberately off it now. Nothing in
# this process can decode HEIC -- Pillow ships AVIF, not HEIC, and pillow-heif
# is not a dependency -- so every HEIC upload would reach the sanitiser below
# and be refused as undecodable anyway. Advertising a format that always ends
# in 415 is worse than not advertising it: the two candidate behaviours were
# "refuse it" and "forward it unstripped", and forwarding is unavailable,
# because an iPhone's default format is exactly the one that always carries
# GPS. The client re-encodes to JPEG before upload and labels it image/jpeg,
# so this removes nothing the app actually sends.
ALLOWED_MIME_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})
MAX_IMAGE_BYTES = 8 * 1024 * 1024

# ``sanitize_image`` speaks the vocabulary of the photo-upload route. Here the
# same three refusals have to arrive as receipt-shaped codes, because the route
# above translates only those and would otherwise answer 500 for a bad
# photograph. A pixel bomb maps onto IMAGE_TOO_LARGE rather than earning a code
# of its own: it is a size refusal, 413 is the honest status, and the wire
# contract stays the one the client already knows.
_REJECTION_TO_RECEIPT_CODE = {
    "not_an_image": "UNSUPPORTED_IMAGE_TYPE",
    "image_too_large": "IMAGE_TOO_LARGE",
    "image_dimensions_too_large": "IMAGE_TOO_LARGE",
}


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

    # The byte ceiling is checked above, on the bytes as uploaded, and must
    # stay there. Sanitising re-encodes, so a limit read off the *output* would
    # let a 20 MB upload be fully decoded before anything measured it -- the
    # decode is the expensive part, so a limit applied after it does not limit
    # anything.
    #
    # rd-qa-33 measured what this call is for: a bill photographed at the table
    # reached the vision backend with its GPS intact, so splitting a dinner also
    # disclosed the restaurant, the hour and the handset. The reader is handed
    # the rebuilt pixels and the type those pixels actually are -- forwarding
    # the upload's declared type would describe a buffer that no longer exists.
    try:
        sanitized = sanitize_image(image)
    except ImageRejected as exc:
        raise ReceiptError(
            _REJECTION_TO_RECEIPT_CODE.get(exc.code, "UNSUPPORTED_IMAGE_TYPE")
        ) from None

    raw = reader.read(sanitized.data, sanitized.content_type)
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
