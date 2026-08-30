"""Application boundary for pluggable transaction-screenshot readers."""

from __future__ import annotations

from typing import Protocol

from app.api.receipt_skill import (
    _REJECTION_TO_RECEIPT_CODE,
    ALLOWED_MIME_TYPES,
    MAX_IMAGE_BYTES,
)
from app.domain.screenshot import ScreenshotError, read_screenshot
from app.media.images import ImageRejected, sanitize_image

__all__ = [
    "ALLOWED_MIME_TYPES",
    "MAX_IMAGE_BYTES",
    "ScreenshotReader",
    "run_screenshot_skill",
]

# Both vision routes admit the same upload formats and run the same sanitizer.
# Reusing this exact mapping prevents one route from turning a pixel bomb into
# 413 while its neighbour drifts to 415 for the identical buffer.
_REJECTION_TO_SCREENSHOT_CODE = _REJECTION_TO_RECEIPT_CODE


class ScreenshotReader(Protocol):
    """Copy transaction-shaped fields from one rebuilt in-memory image."""

    def read(self, image: bytes, mime_type: str) -> dict:
        """Return the raw screenshot-reading contract."""
        ...


def run_screenshot_skill(
    image: bytes,
    mime_type: str,
    *,
    reader: ScreenshotReader,
) -> dict:
    """Validate and rebuild an upload before any model can inspect it."""

    if not image:
        raise ScreenshotError("EMPTY_IMAGE")
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ScreenshotError("UNSUPPORTED_IMAGE_TYPE")
    if len(image) > MAX_IMAGE_BYTES:
        # This must stay ahead of decoding. Re-encoding changes byte length,
        # and measuring afterwards would spend the expensive operation first.
        raise ScreenshotError("IMAGE_TOO_LARGE")

    try:
        sanitized = sanitize_image(image)
    except ImageRejected as exc:
        raise ScreenshotError(
            _REJECTION_TO_SCREENSHOT_CODE.get(
                exc.code,
                "UNSUPPORTED_IMAGE_TYPE",
            )
        ) from None

    # The declared upload type describes the discarded container. The reader
    # receives rebuilt pixels and therefore the sanitizer's actual output type.
    return read_screenshot(reader.read(sanitized.data, sanitized.content_type))
