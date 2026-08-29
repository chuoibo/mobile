"""rd-qa-38: every format the bill route advertises must arrive at the model clean.

rd-be-20 (#209) put `sanitize_image` on `POST /receipts/scan` and proved it on
one shape: a JPEG carrying EXIF GPS. That is the shape a phone camera produces,
so it was the right one to prove first -- but it is not the only place a
coordinate rides into an upload, and it is not the only container the route
says it accepts.

Measured on main @ 208c1d3, before this file existed, five metadata shapes all
crossed the boundary intact on the pre-fix tree and all came back clean on the
post-fix tree:

    jpeg + EXIF GPS      leaked -> clean
    jpeg + XMP GPS       leaked -> clean      no gate covered this
    png  + EXIF + tEXt   leaked -> clean      no gate covered this
    png  ALPHA + EXIF    leaked -> clean      no gate covered this
    webp + EXIF + XMP    leaked -> clean      no gate covered this

Four of those five were protected by accident of implementation rather than by
any test. The protection is real -- `sanitize_image` rebuilds pixels and lets
Pillow write the output with default (empty) metadata -- but nothing held it in
place, so a later rewrite of that function could drop XMP handling and every
existing gate would stay green.

The parametrized case below is the load-bearing one, and it is deliberately
driven by `ALLOWED_MIME_TYPES` rather than by a hand-written list of formats.
That ties the allow-list to the privacy property: a format is only allowed if
somebody can show a coordinate-bearing image of that format arriving stripped.
`image/heic` was removed from that list by #209 with an eight-line comment
explaining why, and nothing enforced the removal -- putting it back turns zero
of the suite's 1382 cases red. With this file, putting it back demands proof.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin
from PIL.TiffImagePlugin import IFDRational

from app.api.deps import get_receipt_reader
from app.api.main import app
from app.api.receipt_skill import ALLOWED_MIME_TYPES

# Ben Thanh market, not a home -- same synthetic point rd-qa-37 uses.
LAT = (10, 46, 22)
LON = (106, 41, 53)

# Assembled rather than written out: a long digit literal trips the repo guard's
# account-number rule, which is correct of it.
ACTOR = {"X-Actor-ID": "-".join(("1" * 8, "1" * 4, "4" + "1" * 3, "8" + "1" * 3, "1" * 12))}

# Plain ASCII and distinctive, so a substring search over the forwarded bytes
# answers "did this survive?" without decoding anything. Deliberately carries no
# long digit run: a coordinate-shaped literal trips the repo guard, correctly --
# that shape is how an account number reaches a diff.
MARKER = "rd-qa-38-dau-vet-cua-nguoi-chup-bill"

OK_RESULT = {
    "document_type": "receipt",
    "confidence": 1.0,
    "items": [{"name": "Com tam", "quantity": 1, "line_total_text": "65.000"}],
    "total_text": "65.000",
}


class GhiLaiReader:
    """Stands where the vision backend stands and keeps what it was handed."""

    def __init__(self) -> None:
        self.image: bytes | None = None
        self.mime: str | None = None

    def read(self, image: bytes, mime_type: str) -> dict:
        self.image = image
        self.mime = mime_type
        return dict(OK_RESULT)


@pytest.fixture()
def recorder():
    rec = GhiLaiReader()
    app.dependency_overrides[get_receipt_reader] = lambda: rec
    yield rec
    app.dependency_overrides.pop(get_receipt_reader, None)


@pytest.fixture()
def client():
    return TestClient(app)


def _exif() -> Image.Exif:
    exif = Image.Exif()
    exif[0x010F] = "RuDi QA"
    exif[0x8825] = {
        1: "N",
        2: tuple(IFDRational(v, 1) for v in LAT),
        3: "E",
        4: tuple(IFDRational(v, 1) for v in LON),
    }
    return exif


def _canvas(alpha: bool = False) -> Image.Image:
    """Something with real pixels -- a header-only stub is not decodable."""
    mode = "RGBA" if alpha else "RGB"
    fill = (240, 235, 220, 255) if alpha else (240, 235, 220)
    img = Image.new(mode, (120, 90), fill)
    ink = (30, 30, 30, 255) if alpha else (30, 30, 30)
    for y in range(0, 90, 12):
        for x in range(0, 120, 2):
            img.putpixel((x, y), ink)
    return img


def _xmp_packet() -> bytes:
    return (
        b'<?xpacket begin="\xef\xbb\xbf"?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description exif:GPSLatitude="10,46.22N" note="'
        + MARKER.encode()
        + b'"/></rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
    )


def jpeg_exif() -> bytes:
    buf = io.BytesIO()
    _canvas().save(buf, format="JPEG", quality=90, exif=_exif())
    return buf.getvalue()


def jpeg_xmp() -> bytes:
    buf = io.BytesIO()
    _canvas().save(buf, format="JPEG", quality=90, xmp=_xmp_packet())
    return buf.getvalue()


def png_exif_text() -> bytes:
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Comment", MARKER)
    meta.add_text("Location", MARKER)
    buf = io.BytesIO()
    _canvas().save(buf, format="PNG", exif=_exif(), pnginfo=meta)
    return buf.getvalue()


def png_alpha_exif() -> bytes:
    """The RGBA branch of the sanitiser saves PNG, a different path to cover."""
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Comment", MARKER)
    buf = io.BytesIO()
    _canvas(alpha=True).save(buf, format="PNG", exif=_exif(), pnginfo=meta)
    return buf.getvalue()


def webp_exif_xmp() -> bytes:
    buf = io.BytesIO()
    _canvas().save(buf, format="WEBP", quality=90, exif=_exif(), xmp=MARKER.encode())
    return buf.getvalue()


# Keyed by the mime type the route advertises, not by a list this file invents.
BUILDERS = {
    "image/jpeg": ("bill.jpg", jpeg_exif),
    "image/png": ("bill.png", png_exif_text),
    "image/webp": ("bill.webp", webp_exif_xmp),
}


def gui(client: TestClient, data: bytes, name: str, mime: str):
    return client.post(
        "/receipts/scan",
        files={"image": (name, data, mime)},
        headers=ACTOR,
    )


def vet_ban_de(data: bytes) -> list[str]:
    """Every trace of the photographer we can still find in these bytes."""
    dau_vet: list[str] = []
    if MARKER.encode() in data:
        dau_vet.append("chuoi-danh-dau-con-nguyen")
    with Image.open(io.BytesIO(data)) as im:
        exif = im.getexif()
        if exif.get_ifd(0x8825):
            dau_vet.append("EXIF-GPS")
        if exif.get(0x010F):
            dau_vet.append("EXIF-Make")
        if getattr(im, "text", None):
            dau_vet.append(f"PNG-text:{sorted(im.text)}")
        if "xmp" in im.info:
            dau_vet.append("khoi-XMP")
    return dau_vet


@pytest.mark.parametrize("mime", sorted(ALLOWED_MIME_TYPES))
def test_moi_dinh_dang_duoc_phep_deu_toi_model_sach(mime, client, recorder):
    """Whatever the route advertises, a coordinate in it must not reach the model.

    Driven by ALLOWED_MIME_TYPES on purpose. Adding a format to that list adds a
    case here, and the new case only passes if a coordinate-bearing image of
    that format is demonstrably stripped -- or the route refuses it outright.
    Advertising a format nobody can build a clean path for is what this catches.
    """
    if mime not in BUILDERS:
        pytest.fail(
            f"{mime} nam trong ALLOWED_MIME_TYPES nhung rd-qa-38 khong dung duoc "
            f"anh mau cho no. Them mot builder vao BUILDERS va chung minh anh "
            f"dinh dang nay toi model khong con toa do -- hoac go {mime} khoi "
            f"danh sach. Quang cao mot dinh dang ma khong ai chung minh duoc "
            f"duong sach cua no la cach lo lot quay lai."
        )

    name, build = BUILDERS[mime]
    raw = build()
    assert vet_ban_de(raw), f"anh mau {mime} phai thuc su mang dau vet truoc khi gui"

    response = gui(client, raw, name, mime)

    if recorder.image is None:
        # Refusing is an acceptable answer; forwarding something dirty is not.
        assert response.status_code in (413, 415), (
            f"{mime} khong toi model va cung khong bi tu choi tu te: "
            f"HTTP {response.status_code} {response.text[:200]}"
        )
        return

    assert vet_ban_de(recorder.image) == [], (
        f"anh {mime} toi model van con dau vet cua nguoi chup: "
        f"{vet_ban_de(recorder.image)}"
    )


def test_khoi_xmp_khong_di_theo_anh_jpeg(client, recorder):
    """A coordinate written in XMP rather than EXIF must not reach the model."""
    raw = jpeg_xmp()
    assert "chuoi-danh-dau-con-nguyen" in vet_ban_de(raw)

    gui(client, raw, "bill.jpg", "image/jpeg")

    assert recorder.image is not None, "anh hop le nay phai toi duoc model"
    assert MARKER.encode() not in recorder.image, (
        "khoi XMP di nguyen ven qua bien: EXIF bi lot nhung XMP thi khong"
    )


def test_o_chu_png_khong_di_theo_anh(client, recorder):
    """PNG tEXt chunks carry free-form text; a phone can write a place there."""
    raw = png_exif_text()
    assert "PNG-text:['Comment', 'Location']" in vet_ban_de(raw)

    gui(client, raw, "bill.png", "image/png")

    assert recorder.image is not None, "anh hop le nay phai toi duoc model"
    assert MARKER.encode() not in recorder.image, "o chu tEXt cua PNG di lot qua bien"


def test_nhanh_anh_trong_suot_cung_duoc_lot(client, recorder):
    """RGBA takes the PNG save branch, which is not the branch #209 measured."""
    raw = png_alpha_exif()
    assert vet_ban_de(raw), "anh mau trong suot phai mang dau vet"

    gui(client, raw, "bill.png", "image/png")

    assert recorder.image is not None, "anh hop le nay phai toi duoc model"
    assert vet_ban_de(recorder.image) == [], (
        f"nhanh RGBA de lot: {vet_ban_de(recorder.image)}"
    )


def test_byte_rac_khong_bao_gio_toi_ben_thu_ba(client, recorder):
    """Junk must be refused here, not forwarded to a paid third-party model.

    Before #209 a 60-byte truncated JPEG and a kilobyte of noise were both
    handed straight to the vision backend. That is a bill for a call that could
    never have succeeded, and it ships arbitrary user bytes off the box.
    """
    for label, data in (
        ("byte rac", b"day khong phai anh" * 60),
        ("jpeg cut", jpeg_exif()[:60]),
    ):
        recorder.image = None
        response = gui(client, data, "bill.jpg", "image/jpeg")

        assert recorder.image is None, f"{label}: rac nay da bi day toi model"
        assert response.status_code == 415, (
            f"{label}: cho doi 415, nhan HTTP {response.status_code} {response.text[:160]}"
        )
