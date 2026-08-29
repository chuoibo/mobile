"""Opaque keyset cursors for group message pagination."""

from __future__ import annotations

import base64
import binascii
import uuid
from datetime import UTC, datetime


class CursorError(ValueError):
    """Raised when a message cursor cannot be decoded safely."""


def encode_cursor(created_at: datetime, message_id: uuid.UUID) -> str:
    """Encode one stable message position for use in a query string."""

    payload = f"{created_at.isoformat()}|{message_id}".encode()
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(raw: str) -> tuple[datetime, uuid.UUID]:
    """Decode a message position, rejecting malformed input explicitly."""

    if not raw:
        raise CursorError("Invalid cursor")

    try:
        encoded = raw.encode("ascii")
        padding = b"=" * (-len(encoded) % 4)
        decoded = base64.b64decode(
            encoded + padding,
            altchars=b"-_",
            validate=True,
        ).decode("utf-8")
        timestamp_raw, separator, message_id_raw = decoded.partition("|")
        if not separator:
            raise ValueError("cursor separator is missing")
        created_at = datetime.fromisoformat(timestamp_raw)
        message_id = uuid.UUID(message_id_raw)
    except (UnicodeEncodeError, UnicodeDecodeError, binascii.Error, ValueError) as exc:
        raise CursorError("Invalid cursor") from exc

    if created_at.tzinfo is None or created_at.utcoffset() is None:
        created_at = created_at.replace(tzinfo=UTC)
    return created_at, message_id
