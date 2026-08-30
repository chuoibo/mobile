"""Did stripping EXIF cost us any reading quality? Ask the real model, twice.

rd-be-20 put ``sanitize_image`` between the upload and the vision backend. That
re-encodes to JPEG at quality 88 and applies EXIF ``Orientation`` before the
call, so the backend no longer sees the bytes the phone produced. Both of those
could plausibly change what the model reads, and neither can be settled by a
fake reader: the fake returns a canned reading whatever you hand it.

So this asks Gemini. One source bill, four live calls:

    A  raw upright     the bytes as the phone wrote them, EXIF and all
    B  stripped upright   what the route now sends
    C  raw sideways     Orientation=6, tag set, pixels NOT rotated -- the old path
    D  stripped sideways  Orientation=6 applied, so the bill arrives upright

A vs B is the regression question: same picture, does re-encoding lose lines?
C vs D is the side effect the task predicted would help: a backend reads pixels,
not the orientation tag, so C is a bill lying on its side.

Not a pytest case on purpose. It costs money, it calls the network, and its
verdict is a comparison a person should read rather than a boolean a suite
should enforce -- a model revision may legitimately shift a line and that must
not turn CI red. Run it when the sanitiser or the prompt changes:

    cd services/api
    set -a; . /home/lakiet/mobile/.env; set +a
    python3 tests/live/probe_exif_ocr_ab.py
"""

from __future__ import annotations

import io
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from PIL import Image  # noqa: E402

from app.api.vision_gemini import GeminiReceiptReader  # noqa: E402
from app.domain.receipt import read_receipt  # noqa: E402
from app.media.images import sanitize_image  # noqa: E402

MOCKUP = pathlib.Path(
    os.environ.get(
        "MOBILE_RECEIPT_MOCKUP",
        "/home/lakiet/mobile/product/features/04-chia-bill-thong-minh.png",
    )
)
CROP_BOX = (52, 445, 268, 750)
UPSCALE = 6
GPS_IFD = 0x8825
ORIENTATION = 0x0112


def phone_photo(*, sideways: bool) -> bytes:
    """The mockup receipt, saved the way a phone would save it."""

    with Image.open(MOCKUP) as sheet:
        crop = sheet.convert("RGB").crop(CROP_BOX)
        crop = crop.resize((crop.width * UPSCALE, crop.height * UPSCALE), Image.LANCZOS)
        if sideways:
            # Rotate the pixels and set the tag that says "rotate them back".
            # That is what a phone held sideways actually writes.
            crop = crop.transpose(Image.ROTATE_90)

    exif = Image.Exif()
    exif[0x010F] = "Apple"
    exif[0x0110] = "iPhone 15 Pro"
    exif[0x9003] = "2026:08:30 20:15:00"
    if sideways:
        exif[ORIENTATION] = 6
    gps = exif.get_ifd(GPS_IFD)
    gps[1] = "N"
    gps[2] = (21.0, 1.0, 44.0)
    gps[3] = "E"
    gps[4] = (105.0, 51.0, 8.0)

    buffer = io.BytesIO()
    crop.save(buffer, format="JPEG", quality=95, exif=exif.tobytes())
    return buffer.getvalue()


def gps_of(data: bytes) -> dict:
    with Image.open(io.BytesIO(data)) as image:
        return dict(image.getexif().get_ifd(GPS_IFD))


def run(label: str, image: bytes, mime: str) -> None:
    reading = read_receipt(GeminiReceiptReader().read(image, mime))
    items = reading["items"]
    print(
        f"{label:22} {len(image):>8,}B  gps={'CÓ' if gps_of(image) else 'không':5}"
        f"  items={len(items):<3} total={reading['total_vnd']:<10,}"
        f" items_total={reading['items_total_vnd']:,}"
    )
    for item in items:
        print(f"{'':24}   {item['name'][:34]:<34} {item['line_total_vnd']:>10,}")


def main() -> int:
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY chưa đặt. set -a; . /home/lakiet/mobile/.env; set +a")
        return 2
    if not MOCKUP.is_file():
        print(f"không thấy mockup: {MOCKUP}")
        return 2

    for sideways in (False, True):
        which = "nghiêng" if sideways else "thẳng"
        raw = phone_photo(sideways=sideways)
        clean = sanitize_image(raw)
        print(f"\n--- bill {which} ---")
        run(f"A raw {which}", raw, "image/jpeg")
        run(f"B đã lột {which}", clean.data, clean.content_type)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
