"""Build the three fixture images F26 is driven with.

Synthetic on purpose. Not one real bill, account, merchant or person: these are
drawn from constants in this file, so they can live beside a QA run without
anything in ADR-0010 6.5's "never from a session with real data" being bent.

Phone-screenshot proportions (720x1280) because that is the shape a person's
gallery actually holds, and a reader given a square crop is being asked an
easier question than the product asks it.

    python3 tests/qa/qa-tt-0034/tao_anh_mau.py /tmp/anh-qa

Writes grab.png, shopeefood.png, khong-phai-bill.png and khong-phai-anh.txt.
The last two are the negatives: a drawing with no transaction anywhere on it,
and a file that is not an image at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 720, 1280
_FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """A real TrueType face, falling back to the bitmap default."""

    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(f"{_FONT_DIR}/{name}", size)
    except OSError:
        return ImageFont.load_default()


def grab(path: Path) -> None:
    """A completed ride: header, two stops, a fare breakdown, one total."""

    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 190], fill=(0, 176, 79))
    d.text((40, 60), "Grab", font=font(58, True), fill="white")
    d.text((40, 130), "Chuyen di da hoan thanh", font=font(30), fill="white")
    d.text((40, 250), "29/08/2026  19:42", font=font(28), fill=(90, 90, 90))
    d.text((40, 320), "Diem don: 12 Nguyen Hue, Q1", font=font(30), fill=(20, 20, 20))
    d.text((40, 380), "Diem den: 45 Le Loi, Q1", font=font(30), fill=(20, 20, 20))
    d.line([40, 450, W - 40, 450], fill=(200, 200, 200), width=2)
    d.text((40, 490), "Cuoc phi", font=font(30), fill=(60, 60, 60))
    d.text((W - 220, 490), "78.000d", font=font(30), fill=(20, 20, 20))
    d.text((40, 550), "Phu phi", font=font(30), fill=(60, 60, 60))
    d.text((W - 220, 550), "7.000d", font=font(30), fill=(20, 20, 20))
    d.line([40, 620, W - 40, 620], fill=(200, 200, 200), width=2)
    d.text((40, 660), "Tong cong", font=font(38, True), fill=(20, 20, 20))
    d.text((W - 260, 660), "85.000d", font=font(38, True), fill=(0, 140, 60))
    d.text((40, 750), "Thanh toan: Tien mat", font=font(28), fill=(90, 90, 90))
    im.save(path)


def shopeefood(path: Path) -> None:
    """A delivered order: merchant, three lines, one total."""

    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 190], fill=(238, 77, 45))
    d.text((40, 60), "ShopeeFood", font=font(52, True), fill="white")
    d.text((40, 130), "Don hang da giao", font=font(30), fill="white")
    d.text((40, 250), "Bun bo Hue Co Ba", font=font(40, True), fill=(20, 20, 20))
    d.text((40, 310), "28/08/2026  12:15", font=font(28), fill=(90, 90, 90))
    rows = [
        ("2x Bun bo dac biet", "130.000d"),
        ("1x Tra tac", "22.000d"),
        ("Phi giao hang", "15.000d"),
    ]
    y = 390
    for name, amount in rows:
        d.text((40, y), name, font=font(30), fill=(30, 30, 30))
        d.text((W - 230, y), amount, font=font(30), fill=(30, 30, 30))
        y += 60
    d.line([40, y + 10, W - 40, y + 10], fill=(200, 200, 200), width=2)
    d.text((40, y + 50), "Tong cong", font=font(38, True), fill=(20, 20, 20))
    d.text((W - 270, y + 50), "167.000d", font=font(38, True), fill=(238, 77, 45))
    im.save(path)


def khong_phai_bill(path: Path) -> None:
    """A drawing. No amount, no merchant, no transaction anywhere on it.

    Deliberately not "a blurry bill": a blurry bill tests the reader's eyesight
    and this negative tests its judgement. The refusal under measurement is
    NOT_A_TRANSACTION, which is a different sentence from "khong doc duoc".
    """

    im = Image.new("RGB", (W, H), (135, 190, 235))
    d = ImageDraw.Draw(im)
    d.ellipse([500, 120, 660, 280], fill=(255, 214, 90))
    d.polygon([(0, 900), (240, 520), (470, 900)], fill=(90, 140, 95))
    d.polygon([(300, 900), (520, 600), (720, 900)], fill=(70, 115, 80))
    d.rectangle([0, 900, W, H], fill=(120, 170, 110))
    for x in range(60, W, 130):
        d.ellipse([x, 1000, x + 34, 1034], fill=(230, 90, 120))
        d.line([x + 17, 1034, x + 17, 1090], fill=(60, 110, 60), width=5)
    im.save(path)


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/qa-tt-0034-anh")
    out.mkdir(parents=True, exist_ok=True)
    grab(out / "grab.png")
    shopeefood(out / "shopeefood.png")
    khong_phai_bill(out / "khong-phai-bill.png")
    (out / "khong-phai-anh.txt").write_text(
        "day khong phai anh, chi la mot dong chu.\n", encoding="utf-8"
    )
    for name in (
        "grab.png",
        "shopeefood.png",
        "khong-phai-bill.png",
        "khong-phai-anh.txt",
    ):
        print(f"{out / name}  {(out / name).stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
