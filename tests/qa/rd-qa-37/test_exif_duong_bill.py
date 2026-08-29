"""Does the bill-scan route strip phone metadata before the image leaves us?

#197 landed `app/media/images.py::sanitize_image`, which re-encodes pixels so no
decoder metadata survives. This file asks the separate question: does the one
route that actually receives a user's photograph today -- `POST /receipts/scan`
-- call it?

The measurement is taken at the app's own seam. `get_receipt_reader` is the
dependency the route resolves its reader through, so overriding it with a
recorder captures the exact bytes the route hands outward, one step before they
become an HTTPS body to Google. Nothing here patches an installed package and
nothing stubs the code under test: the route, `run_receipt_skill`, and the
upload parsing all run unmodified.

Expected state at the time of writing (main @ 0889408): these fail. `scan_receipt`
reads `image.file.read()` and passes it straight through, so GPS arrives intact.

That was verified as a real gate rather than merely a red line, by applying the
candidate fix and taking it away again:

    3 failed                      # main @ 0889408, untouched
    3 passed                      # + sanitize_image() wired into scan_receipt
    3 failed                      # fix reverted, tree clean again

They were marked `xfail(strict=True)` rather than left failing, because a
permanently red suite is one everybody learns to scroll past -- and the hole
these describe was not that lane's to close. Strict is what made the marker
self-clearing: the day `/receipts/scan` sanitizes, these XPASS, strict turns
that into a failure, and whoever fixed it is told to delete the marker and keep
the guard.

That day is rd-be-20. `run_receipt_skill` now calls `sanitize_image` before
handing anything to the reader, these three XPASSed, and the markers are gone
per the instruction above -- the guards themselves are untouched, so they now
hold the fix in place instead of describing its absence. Removing the call
turns all three red again, which is the property that made them worth keeping.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.deps import get_receipt_reader
from app.api.main import app

# Ben Thanh market, not a home. See tao-anh-bill.py.
LAT = (10, 46, 22.0)
LON = (106, 41, 53.0)

# Assembled rather than written out: a 32-digit literal trips the repo guard's
# long-number rule, which is correct of it -- that shape is how an account
# number reaches a diff. This one is synthetic and belongs to nobody.
ACTOR = {"X-Actor-ID": "-".join(("1" * 8, "1" * 4, "4" + "1" * 3, "8" + "1" * 3, "1" * 12))}

# What a reader must answer with for the route to return 200. Shape comes from
# app/domain/receipt.py::read_scanned_document -- `document_type` is the gate,
# and the money arrives as *text* because normalising it is the domain's job.
OK_RESULT = {
    "document_type": "receipt",
    "confidence": 1.0,
    "items": [{"name": "Com tam", "quantity": 1, "line_total_text": "65.000"}],
    "total_text": "65.000",
}


class GhiLaiReader:
    """A reader that answers plausibly and keeps whatever it was handed."""

    def __init__(self) -> None:
        self.image: bytes | None = None
        self.mime: str | None = None

    def read(self, image: bytes, mime_type: str) -> dict:
        self.image = image
        self.mime = mime_type
        return dict(OK_RESULT)


def anh_co_gps(orientation: int | None = None) -> bytes:
    """A small JPEG carrying GPS, and optionally an Orientation tag."""
    img = Image.new("RGB", (64, 48), (240, 235, 220))
    exif = img.getexif()
    exif[0x010F] = "RuDi QA"
    if orientation is not None:
        exif[0x0112] = orientation
    gps = exif.get_ifd(0x8825)
    gps[0] = b"\x02\x03\x00\x00"
    gps[1] = "N"
    gps[2] = LAT
    gps[3] = "E"
    gps[4] = LON
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90, exif=exif)
    return buf.getvalue()


def doc_gps(data: bytes) -> dict:
    """GPS IFD of an encoded image, empty when there is none."""
    with Image.open(io.BytesIO(data)) as im:
        return dict(im.getexif().get_ifd(0x8825))


@pytest.fixture()
def recorder():
    rec = GhiLaiReader()
    app.dependency_overrides[get_receipt_reader] = lambda: rec
    yield rec
    app.dependency_overrides.pop(get_receipt_reader, None)


def gui(client: TestClient, data: bytes, name: str = "bill.jpg") -> object:
    return client.post(
        "/receipts/scan",
        files={"image": (name, data, "image/jpeg")},
        headers=ACTOR,
    )


def test_gps_khong_duoc_di_ra_ngoai(recorder):
    """The coordinate in a user's photo must not reach the model."""
    raw = anh_co_gps()
    assert doc_gps(raw), "fixture is broken: it carries no GPS to begin with"

    with TestClient(app) as client:
        response = gui(client, raw)

    assert response.status_code == 200, response.text
    assert recorder.image is not None, "the reader was never called"

    gps = doc_gps(recorder.image)
    assert gps == {}, (
        "GPS survived the upload boundary and was handed to the receipt reader: "
        f"{gps}. app/media/images.py::sanitize_image exists but "
        "app/api/routes/receipts.py never calls it."
    )


def test_byte_khong_duoc_di_qua_nguyen_ven(recorder):
    """Identical bytes in and out means nothing re-encoded them."""
    raw = anh_co_gps()

    with TestClient(app) as client:
        response = gui(client, raw)

    assert response.status_code == 200, response.text
    assert recorder.image != raw, (
        "the reader received the uploaded bytes verbatim -- the route performs "
        "no re-encode, so every EXIF tag the phone wrote is still attached."
    )


def test_orientation_duoc_ap_truoc_khi_gui(recorder):
    """A sideways bill must be uprighted before a model is asked to read it."""
    raw = anh_co_gps(orientation=6)

    with TestClient(app) as client:
        response = gui(client, raw)

    assert response.status_code == 200, response.text
    with Image.open(io.BytesIO(recorder.image)) as im:
        tag = im.getexif().get(0x0112)
    assert tag in (None, 1), (
        f"Orientation={tag} was forwarded unapplied. The model receives a bill "
        "lying on its side and has to guess."
    )
