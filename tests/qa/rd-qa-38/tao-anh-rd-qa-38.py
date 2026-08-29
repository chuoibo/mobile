"""Build bills that vary the way real bills vary, not just the way JPEG varies.

rd-qa-37 measured one generated bill and rd-be-20 measured another, and the two
disagreed. A third measurement on a third synthetic image would settle nothing,
so these fixtures are chosen to separate two candidate causes rather than to add
samples:

  nghieng.jpg  perspective skew, uneven light, sensor noise -- what a phone
               actually hands over when somebody photographs a bill on a table
  mo-nhe.jpg   mildly soft, not the unreadable blur rd-qa-37 already covers;
               the interesting case is the one near the decision boundary
  dai.jpg      20 lines on thermal-printer paper -- long and narrow, the shape
               a real restaurant bill has and a 900x1200 sheet does not
  cot-sl.jpg   the SAME items as rd-qa-37's bill but with a printed SL column
  khong-x.jpg  the SAME items with the "x4"/"x2" removed from the names

The last two exist because of what the first measurement found: rd-qa-37's bill
writes quantity into the item NAME ("Trà đá x4") and prints no quantity column,
and `_read_quantity` rejects the whole receipt when the reader copies "x4" into
quantity_text. If image quality is the cause, these two flake like the original.
If quantity parsing is the cause, they do not. One of those has to be false.

Every file is generated. Repo rules forbid real bills in git, and none of these
carries a coordinate, a name, or an account number.
"""

from __future__ import annotations

import io
import pathlib
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/rd-qa-38-anh")
OUT.mkdir(parents=True, exist_ok=True)

FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
FONT_BIG = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40
)
FONT_S = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
FONT_S_B = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30
)

# Identical to the rd-qa-37 bill, so a rate measured here is comparable to 6/11.
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

# Same money, same items, quantity moved out of the name and into a column.
BILL_COT_SL = [
    ("QUÁN CƠM TẤM BÀ GHIỀN", None, None),
    ("18 Nguyễn Trãi, Quận 1", None, None),
    ("HOÁ ĐƠN THANH TOÁN", None, None),
    ("", None, None),
    ("Tên món", "SL", "Thành tiền"),
    ("Cơm tấm sườn bì chả", "1", "65.000"),
    ("Cơm tấm sườn nướng", "1", "55.000"),
    ("Canh chua cá lóc", "1", "45.000"),
    ("Trà đá", "4", "20.000"),
    ("Bia Sài Gòn", "2", "50.000"),
    ("", None, None),
    ("TỔNG CỘNG", None, "235.000"),
]

# Same money, quantity simply not printed anywhere.
BILL_KHONG_X = [(t.replace(" x4", "").replace(" x2", ""), a) for t, a in BILL_LINES]

DAI_MON = [
    ("Gỏi cuốn tôm thịt", "45.000"),
    ("Chả giò rế", "55.000"),
    ("Bò lá lốt", "75.000"),
    ("Cơm chiên dương châu", "85.000"),
    ("Canh khổ qua nhồi thịt", "65.000"),
    ("Rau muống xào tỏi", "40.000"),
    ("Cá kho tộ", "120.000"),
    ("Tôm rang me", "150.000"),
    ("Mực chiên giòn", "135.000"),
    ("Lẩu thái hải sản", "280.000"),
    ("Bún tươi", "20.000"),
    ("Nấm kim châm", "35.000"),
    ("Đậu hũ chiên sả", "45.000"),
    ("Cơm trắng", "30.000"),
    ("Trà đá", "20.000"),
    ("Bia Sài Gòn", "175.000"),
    ("Nước suối", "30.000"),
    ("Khăn lạnh", "15.000"),
    ("Nước mắm chấm", "10.000"),
    ("Tráng miệng chè", "60.000"),
]


def _paper(lines, size=(900, 1200)) -> Image.Image:
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


def _paper_3cot(lines, size=(900, 1200)) -> Image.Image:
    img = Image.new("RGB", size, (247, 244, 236))
    d = ImageDraw.Draw(img)
    y = 90
    for text, sl, amount in lines:
        if text == "":
            d.line(
                [(70, y + 14), (size[0] - 70, y + 14)], fill=(150, 145, 135), width=2
            )
            y += 46
            continue
        f = FONT_BIG if text.isupper() else FONT
        d.text((70, y), text, fill=(25, 22, 18), font=f)
        if sl is not None:
            d.text((size[0] - 400, y), sl, fill=(25, 22, 18), font=f)
        if amount is not None:
            d.text((size[0] - 280, y), amount, fill=(25, 22, 18), font=f)
        y += 62
    return img


def _thermal() -> Image.Image:
    """A long narrow bill: 20 lines on 58mm-style paper."""
    w, h = 560, 1700
    img = Image.new("RGB", (w, h), (252, 251, 247))
    d = ImageDraw.Draw(img)
    d.text((80, 40), "NHÀ HÀNG SEN VIỆT", fill=(20, 20, 20), font=FONT_S_B)
    d.text((110, 78), "HOÁ ĐƠN THANH TOÁN", fill=(20, 20, 20), font=FONT_S)
    d.line([(30, 118), (w - 30, 118)], fill=(120, 120, 120), width=2)
    y = 138
    for name, amount in DAI_MON:
        d.text((30, y), name, fill=(25, 25, 25), font=FONT_S)
        d.text(
            (w - 30 - d.textlength(amount, font=FONT_S), y),
            amount,
            fill=(25, 25, 25),
            font=FONT_S,
        )
        y += 40
    d.line([(30, y + 8), (w - 30, y + 8)], fill=(120, 120, 120), width=2)
    d.text((30, y + 24), "TỔNG CỘNG", fill=(15, 15, 15), font=FONT_S_B)
    d.text(
        (w - 30 - d.textlength("1.490.000", font=FONT_S_B), y + 24),
        "1.490.000",
        fill=(15, 15, 15),
        font=FONT_S_B,
    )
    return img


def _chup_nghieng(flat: Image.Image, seed: int = 38) -> Image.Image:
    """Make a flat render look photographed: skew, uneven light, sensor noise."""
    rnd = random.Random(seed)
    w, h = flat.size
    pad = Image.new("RGB", (w + 160, h + 160), (58, 54, 50))  # table under the paper
    pad.paste(flat, (80, 80))
    W, H = pad.size

    # Perspective: the far edge of the paper is smaller than the near edge.
    dx, dy = 0.10 * W, 0.045 * H
    src = [(0, 0), (W, 0), (W, H), (0, H)]
    dst = [(dx, dy * 0.6), (W - dx * 0.35, 0), (W, H - dy * 0.5), (dx * 0.45, H)]
    coeffs = _perspective_coeffs(dst, src)
    skewed = pad.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BICUBIC)

    # A window on one side: brightness falls off across the sheet.
    grad = Image.linear_gradient("L").resize((W, H)).rotate(70, expand=False)
    skewed = Image.composite(skewed, Image.eval(skewed, lambda v: int(v * 0.72)), grad)

    skewed = skewed.filter(ImageFilter.GaussianBlur(radius=0.7))
    px = skewed.load()
    for yy in range(0, H, 3):
        for xx in range(0, W, 3):
            n = rnd.randint(-9, 9)
            r, g, b = px[xx, yy]
            px[xx, yy] = (
                max(0, min(255, r + n)),
                max(0, min(255, g + n)),
                max(0, min(255, b + n)),
            )
    return skewed


def _perspective_coeffs(src, dst):
    import numpy as np

    matrix = []
    for (x, y), (u, v) in zip(src, dst):
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    a = np.array(matrix, dtype=float)
    b = np.array(dst, dtype=float).reshape(8)
    return np.linalg.solve(a, b).tolist()


def write(name: str, img: Image.Image, quality: int = 86) -> None:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    (OUT / name).write_bytes(buf.getvalue())
    print(f"{name:14s} {len(buf.getvalue()):>9,d} bytes  {img.size[0]}x{img.size[1]}")


def main() -> None:
    bill = _paper(BILL_LINES)
    write("nghieng.jpg", _chup_nghieng(bill))
    write("mo-nhe.jpg", bill.filter(ImageFilter.GaussianBlur(radius=1.8)), quality=78)
    write("dai.jpg", _chup_nghieng(_thermal(), seed=99))
    write("cot-sl.jpg", _paper_3cot(BILL_COT_SL), quality=92)
    write("khong-x.jpg", _paper(BILL_KHONG_X), quality=92)
    print(f"\nthu muc: {OUT}")


if __name__ == "__main__":
    main()
