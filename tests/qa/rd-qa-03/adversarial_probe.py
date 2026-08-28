"""Adversarial probe of the real Gemini receipt reader (rd-qa-03).

Opt-in: it calls Gemini over the network and costs money. Nothing here is a
pytest case, because a test that spends money and depends on a model revision
does not belong in the gate.

    cd services/api
    set -a; . /path/to/repo/.env; set +a          # GEMINI_API_KEY
    python3 ../../tests/qa/rd-qa-03/adversarial_probe.py

Requires `app.domain.receipt` and `app.api.vision_gemini`, so it only runs on a
branch that carries the Gemini receipt reader.

Every image is drawn from code with a fixed seed. No bill image is committed:
a real one is user data, and the repo guard fails closed on binaries anyway.

The corpus is built around one question -- does the reader refuse what it
cannot read, or does it invent? The positive control matters as much as the
adversarial cases: without it, "zero items" proves the harness is broken just
as well as it proves the model is honest.
"""

from __future__ import annotations

import io
import json
import pathlib
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_API = pathlib.Path(__file__).resolve().parents[3] / "services" / "api"
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from app.api.vision_gemini import GeminiReceiptReader  # noqa: E402
from app.domain.receipt import ReceiptError, read_receipt  # noqa: E402

W, H = 900, 1300
MOCKUP = pathlib.Path(
    "/home/lakiet/mobile/product/features/04-chia-bill-thong-minh.png"
)
# The receipt inside screen 1, with margin, enlarged to print scale.
CROP_BOX, UPSCALE = (52, 445, 268, 750), 6


def _font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if pathlib.Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def control(blur: float = 0.0) -> bytes:
    """The mockup receipt, cropped as the live test does. Ground truth known."""
    crop = Image.open(MOCKUP).crop(CROP_BOX)
    crop = crop.resize((crop.width * UPSCALE, crop.height * UPSCALE), Image.LANCZOS)
    if blur:
        crop = crop.convert("RGB").filter(ImageFilter.GaussianBlur(blur))
    return _png(crop)


def white() -> bytes:
    return _png(Image.new("RGB", (W, H), "white"))


def landscape() -> bytes:
    """Sky, sun, mountains, grass. No text anywhere on the image."""
    image = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(image)
    for y in range(H):
        t = y / H
        draw.line(
            [(0, y), (W, y)],
            fill=(int(120 + 100 * t), int(170 + 60 * t), int(235 - 40 * t)),
        )
    draw.ellipse([620, 120, 800, 300], fill=(255, 240, 150))
    draw.polygon([(0, 820), (250, 480), (480, 820)], fill=(96, 104, 120))
    draw.polygon([(300, 820), (600, 430), (900, 820)], fill=(78, 86, 102))
    draw.rectangle([0, 800, W, H], fill=(84, 140, 74))
    return _png(image)


def noise() -> bytes:
    rnd = random.Random(20260829)
    image = Image.new("RGB", (W, H))
    image.putdata(
        [
            (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
            for _ in range(W * H)
        ]
    )
    return _png(image)


def prose() -> bytes:
    """Vietnamese text is present; prices are not."""
    image = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(image)
    font = _font(30)
    lines = [
        "Quê hương là chùm khế ngọt",
        "Cho con trèo hái mỗi ngày",
        "Quê hương là đường đi học",
        "Con về rợp bướm vàng bay",
        "",
        "Quê hương là con diều biếc",
        "Tuổi thơ con thả trên đồng",
    ]
    for i, line in enumerate(lines):
        draw.text((70, 120 + i * 60), line, fill=(20, 20, 20), font=font)
    return _png(image)


def menu() -> bytes:
    """A price list, not a transaction: no total, no date, nothing was paid.

    The hardest case in the corpus, and the most likely real-world mistake --
    at a restaurant the menu is on the same table as the bill.
    """
    image = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(image)
    draw.text((250, 70), "THUC DON", fill=(0, 0, 0), font=_font(52))
    draw.text((300, 140), "Quan An Ngon", fill=(60, 60, 60), font=_font(28))
    draw.line([(70, 200), (830, 200)], fill=(0, 0, 0), width=3)
    dishes = [
        ("Pho bo tai", "65.000"),
        ("Bun cha Ha Noi", "70.000"),
        ("Com tam suon bi", "55.000"),
        ("Goi cuon tom thit", "45.000"),
        ("Banh xeo mien Tay", "60.000"),
        ("Che ba mau", "25.000"),
        ("Tra da", "5.000"),
        ("Nuoc mia", "15.000"),
    ]
    font = _font(32)
    for i, (name, price) in enumerate(dishes):
        draw.text((80, 250 + i * 62), name, fill=(0, 0, 0), font=font)
        draw.text((640, 250 + i * 62), price, fill=(0, 0, 0), font=font)
    return _png(image)


def blurry_prose() -> bytes:
    return _png(Image.open(io.BytesIO(prose())).filter(ImageFilter.GaussianBlur(12)))


def probe(reader: GeminiReceiptReader, data: bytes) -> dict:
    """One call, reported the way the API would have answered it."""
    try:
        raw = reader.read(data, "image/png")
    except Exception as exc:  # credential-safe: type name only
        return {"error": type(exc).__name__}

    record = {
        "raw_items": len(raw.get("items", [])),
        "raw_confidence": raw.get("confidence"),
        "raw_total_text": raw.get("total_text"),
        "item_names": [item.get("name") for item in raw.get("items", [])],
    }
    try:
        normalized = read_receipt(raw)
    except ReceiptError as exc:
        record["outcome"] = f"REFUSED:{exc.code}"
        return record
    record.update(
        outcome="ACCEPTED-200",
        api_confidence=normalized["confidence"],
        line_totals=[i["line_total_vnd"] for i in normalized["items"]],
        items_total_vnd=normalized["items_total_vnd"],
        total_vnd=normalized["total_vnd"],
        warnings=normalized["warnings"],
    )
    return record


def main() -> None:
    reader = GeminiReceiptReader()
    results: dict[str, object] = {}

    print("### A. Non-bill corpus -- refuse, or invent?")
    for name, data in [
        ("CONTROL-bill", control()),
        ("white", white()),
        ("landscape", landscape()),
        ("noise", noise()),
        ("prose", prose()),
        ("blurry-prose", blurry_prose()),
        ("menu", menu()),
    ]:
        record = results[name] = probe(reader, data)
        print(
            f"{name:14s} items={record.get('raw_items')} "
            f"conf={record.get('raw_confidence')} -> {record.get('outcome') or record}"
        )

    print("\n### B. Same bill, increasing blur -- does it degrade honestly?")
    series = results["blur_series"] = {}
    for radius in (0, 4, 8, 12):
        record = series[radius] = probe(reader, control(radius))
        print(
            f"blur r={radius:<3} conf={record.get('raw_confidence')} "
            f"outcome={record.get('outcome')} lines={record.get('line_totals')}"
        )

    out = pathlib.Path("rd-qa-03-probe.json")
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nwrote {out.resolve()}")


if __name__ == "__main__":
    main()
