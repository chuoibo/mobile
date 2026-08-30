"""Re-encode uploaded images so embedded phone metadata never reaches storage."""

from __future__ import annotations

import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 50_000_000


class ImageRejected(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class SanitizedImage:
    data: bytes
    content_type: str
    width: int
    height: int


def sanitize_image(raw: bytes) -> SanitizedImage:
    """Rebuild pixels so no decoder metadata can cross the storage boundary."""

    if len(raw) > MAX_UPLOAD_BYTES:
        raise ImageRejected(
            "image_too_large",
            f"Image exceeds the {MAX_UPLOAD_BYTES}-byte upload limit.",
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                width, height = source.size
                if width * height > MAX_PIXELS:
                    raise ImageRejected(
                        "image_dimensions_too_large",
                        f"Image exceeds the {MAX_PIXELS}-pixel limit.",
                    )

                source.load()
                transposed = ImageOps.exif_transpose(source)
                transposed.load()

                has_alpha = "A" in transposed.getbands() or (
                    transposed.mode == "P" and "transparency" in transposed.info
                )
                mode = "RGBA" if has_alpha else "RGB"
                pixels = transposed.convert(mode)
                clean = Image.frombytes(mode, transposed.size, pixels.tobytes())
    except ImageRejected:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageRejected(
            "image_dimensions_too_large",
            f"Image exceeds the {MAX_PIXELS}-pixel limit.",
        ) from exc
    except Exception as exc:
        raise ImageRejected(
            "not_an_image",
            "The uploaded bytes could not be decoded as a complete image.",
        ) from exc

    output = io.BytesIO()
    if clean.mode == "RGBA":
        clean.save(output, format="PNG")
        content_type = "image/png"
    else:
        clean.save(output, format="JPEG", quality=88, optimize=True)
        content_type = "image/jpeg"

    return SanitizedImage(
        data=output.getvalue(),
        content_type=content_type,
        width=clean.width,
        height=clean.height,
    )
