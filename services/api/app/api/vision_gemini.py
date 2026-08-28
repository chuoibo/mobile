"""Gemini receipt reader with a credential-safe failure boundary."""

from __future__ import annotations

import json
import os

from google import genai
from google.genai import types

from app.domain.receipt import ReceiptError

__all__ = ["GeminiReceiptReader"]


DEFAULT_MODEL = "gemini-2.5-flash"

_PROMPT = """
Read this receipt and return only the fields in the response schema.

Transcribe every monetary string exactly as printed on the paper. Do not
normalize separators, expand abbreviations, convert units, round, or calculate
money. Copy quantity_text only from a quantity or SL column; omit it when no
quantity is printed. Set unit_price_text only when the receipt prints a separate
unit-price column, otherwise set it to null. Set total_text only from the printed
Tổng cộng or Tổng tiền line, otherwise set it to null.

Never alter any item, line total, or printed total to make the item lines add up
to the printed total. If the numbers disagree, preserve every transcription as
printed. Confidence must be an honest estimate from 0.0 to 1.0 of how legible
the receipt text is; do not raise it because the output looks plausible.
""".strip()

_STRING = types.Schema(type=types.Type.STRING)
_NULLABLE_STRING = types.Schema(type=types.Type.STRING, nullable=True)
_ITEM_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "name": _STRING,
        "quantity_text": _STRING,
        "unit_price_text": _NULLABLE_STRING,
        "line_total_text": _STRING,
    },
    required=["name", "unit_price_text", "line_total_text"],
)
# The generateContent endpoint rejects `additional_properties` on a response
# schema even though the SDK type accepts it, so unknown keys are dropped by
# read_receipt instead of being refused upstream.
_RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "items": types.Schema(type=types.Type.ARRAY, items=_ITEM_SCHEMA),
        "total_text": _NULLABLE_STRING,
        "confidence": types.Schema(
            type=types.Type.NUMBER,
            minimum=0.0,
            maximum=1.0,
        ),
    },
    required=["items", "total_text", "confidence"],
)


class GeminiReceiptReader:
    """Read one receipt without retaining its image or API credential."""

    __slots__ = ("_model",)

    def __init__(self) -> None:
        self._model = os.environ.get("MOBILE_GEMINI_MODEL") or DEFAULT_MODEL

    def read(self, image: bytes, mime_type: str) -> dict:
        """Return one raw reading and redact every backend failure."""

        try:
            api_key = os.environ["GEMINI_API_KEY"]
        except KeyError:
            raise ReceiptError("RECEIPT_READER_NOT_CONFIGURED") from None
        if not api_key:
            raise ReceiptError("RECEIPT_READER_NOT_CONFIGURED")

        try:
            with genai.Client(api_key=api_key) as client:
                response = client.models.generate_content(
                    model=self._model,
                    contents=[
                        _PROMPT,
                        types.Part.from_bytes(data=image, mime_type=mime_type),
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                        response_schema=_RESPONSE_SCHEMA,
                    ),
                )
                parsed = response.parsed
                if not isinstance(parsed, dict):
                    parsed = json.loads(response.text)
                if not isinstance(parsed, dict):
                    raise TypeError("receipt response must be an object")
                return dict(parsed)
        except Exception as exc:
            raise RuntimeError(type(exc).__name__) from None
