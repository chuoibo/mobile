"""Render a VietQR payload to an image the guest can save.

Spec section 8.6 is blunt about why this matters: people open the link on the
same phone they will pay from, so there is no second device to point at a
screen. The QR is the fallback for "save the image, then pick it from the
gallery inside the banking app". Copy-to-clipboard is the primary path.

PNG rather than SVG on purpose: long-press-to-save works reliably on iOS and
Android for a raster image, and inconsistently for inline SVG.
"""

from __future__ import annotations

import base64
import io

import segno

__all__ = ["QRError", "payload_to_png_data_uri"]

# Small enough to stay well inside a data URI, large enough that a banking app
# reading it off a saved screenshot still resolves the modules.
_SCALE = 6
_BORDER = 4  # QR standard quiet zone; 2 makes some scanners fail silently
_MAX_BYTES = 60_000


class QRError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def payload_to_png_data_uri(payload: str) -> str:
    """Encode an EMVCo payload as a PNG data URI.

    Error correction stays at 'M'. Higher levels survive a scuffed printed
    receipt, which is not the situation here: this code is read off a clean
    screen or a saved screenshot, and a denser code is harder for an older
    phone camera to resolve.
    """
    if not payload or not payload.strip():
        raise QRError("EMPTY_PAYLOAD")

    code = segno.make(payload, error="m")
    buffer = io.BytesIO()
    code.save(buffer, kind="png", scale=_SCALE, border=_BORDER)
    raw = buffer.getvalue()

    if len(raw) > _MAX_BYTES:
        # A data URI this large would bloat the HTML past what a slow mobile
        # connection should carry. Fail loudly rather than ship a page that
        # takes ten seconds to paint.
        raise QRError("QR_TOO_LARGE")

    # repo-guard: allow=data-uri-base64 reason=synthetic-fixture-never-real-participant-data
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
