"""Build the bill fixtures rd-qa-37 pushes through the real upload path.

Every file here is generated, never a photograph of a real receipt: repo rules
forbid bill images in git, and these live under /tmp for exactly that reason.
The GPS coordinates are a landmark (Ben Thanh market), not anybody's home.

Six fixtures, each answering a different question at the upload boundary:

  ro.jpg        a legible bill            -> does the happy path reach the model
  mo.jpg        the same bill blurred     -> does "too blurry" reach the person
  xoay.jpg      EXIF Orientation=6 + GPS  -> does the app rotate it, and does
                                             the coordinate travel with it
  thucdon.jpg   a price list, not a bill  -> the one refusal with its own wording
  gia.jpg       text bytes named .jpg     -> does a non-image crash or refuse
  to.jpg        ~12 MP                    -> does the size gate fire before the model
"""

from __future__ import annotations

import io
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/rd-qa-37-anh")
OUT.mkdir(parents=True, exist_ok=True)

# Ben Thanh market. A landmark on purpose: the point of the test is that a
# coordinate survives the trip, and it must not be a coordinate of a real home.
LAT = (10, 46, 22.0)
LON = (106, 41, 53.0)

# Real diacritics on purpose. The first cut of this fixture was ASCII drawn in
# Pillow's bitmap font, and the model answered "unreadable" for it while
# correctly classifying the price list -- which said more about the fixture than
# about the product. A bill a person would recognise is the only fair input.
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
FONT_BIG = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40
)

BILL_LINES = [
    ("QUÁN CƠM TẤM BÀ GHIỀN", None),
    ("18 Nguyễn Trãi, Quận 1", None),
    ("HOÁ ĐƠN THANH TOÁN", None),
    ("", None),
    ("Cơm tấm sườn bì chả", "65.000"),
    ("Cơm tấm sườn nướng", "55.000"),
    ("Canh chua cá lóc", "45.000"),
    ("Trà đá x4", "20.000"),
    ("Bia Sài Gòn x2", "50.000"),
    ("", None),
    ("TỔNG CỘNG", "235.000"),
]

MENU_LINES = [
    ("THỰC ĐƠN - BẢNG GIÁ", None),
    ("", None),
    ("Cơm tấm sườn bì chả", "65.000"),
    ("Cơm tấm sườn nướng", "55.000"),
    ("Canh chua cá lóc", "45.000"),
    ("Trà đá", "5.000"),
    ("Bia Sài Gòn", "25.000"),
    ("Lẩu thái hải sản", "180.000"),
]


def _draw(lines: list[tuple[str, str | None]], size=(900, 1200)) -> Image.Image:
    """Paint a paper-looking document big enough for a model to read."""
    img = Image.new("RGB", size, (247, 244, 236))
    d = ImageDraw.Draw(img)
    y = 90
    for text, amount in lines:
        if text == "":
            d.line(
                [(70, y + 14), (size[0] - 70, y + 14)], fill=(150, 145, 135), width=2
            )
            y += 46
            continue
        f = FONT_BIG if text.isupper() else FONT
        d.text((70, y), text, fill=(25, 22, 18), font=f)
        if amount is not None:
            d.text((size[0] - 280, y), amount, fill=(25, 22, 18), font=f)
        y += 62
    return img


def _with_gps(img: Image.Image, orientation: int | None = None) -> bytes:
    """Encode as JPEG carrying GPS, and optionally an Orientation tag."""
    exif = img.getexif()
    exif[0x010F] = "RuDi QA"  # Make
    exif[0x0110] = "rd-qa-37 fixture"  # Model
    if orientation is not None:
        exif[0x0112] = orientation  # Orientation
    gps = exif.get_ifd(0x8825)
    gps[0] = b"\x02\x03\x00\x00"  # GPSVersionID
    gps[1] = "N"
    gps[2] = LAT
    gps[3] = "E"
    gps[4] = LON
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, exif=exif)
    return buf.getvalue()


def write(name: str, data: bytes) -> None:
    path = OUT / name
    path.write_bytes(data)
    print(f"{name:14s} {len(data):>9,d} bytes")


def main() -> None:
    bill = _draw(BILL_LINES)

    buf = io.BytesIO()
    bill.save(buf, format="JPEG", quality=92)
    write("ro.jpg", buf.getvalue())

    blurred = bill.filter(ImageFilter.GaussianBlur(radius=6))
    buf = io.BytesIO()
    blurred.save(buf, format="JPEG", quality=60)
    write("mo.jpg", buf.getvalue())

    # Orientation=6 means "stored rotated 90 CW, display upright". A viewer that
    # ignores the tag shows this bill lying on its side.
    sideways = bill.rotate(-90, expand=True)
    write("xoay.jpg", _with_gps(sideways, orientation=6))

    write("thucdon.jpg", _with_gps(_draw(MENU_LINES)))

    # Not an image at all. The extension is the only thing claiming it is.
    write("gia.jpg", b"Day khong phai anh. Chi la van ban doi duoi .jpg.\n" * 40)

    # ~12 MP: over MAX_PIXELS? no -- under the 50 MP bomb limit but well over
    # the 8 MB wire limit once encoded at high quality with noise.
    big = Image.new("RGB", (4000, 3000))
    px = big.load()
    for yy in range(0, 3000, 2):
        for xx in range(0, 4000, 2):
            v = (xx * 7 + yy * 13) % 256
            px[xx, yy] = (v, (v * 3) % 256, (v * 7) % 256)
    buf = io.BytesIO()
    big.save(buf, format="JPEG", quality=100, subsampling=0)
    write("to.jpg", buf.getvalue())

    print(f"\nthu muc: {OUT}")


if __name__ == "__main__":
    main()
