"""A bill is photographed at the table, so the photograph says which table.

``app/media/images.py`` has known how to forget that since #197, and
``tests/media/test_image_sanitizer.py`` proves it forgets. Neither fact helped
this route: the scan endpoint read ``image.file`` and handed the bytes straight
to a vision backend, so every split of a restaurant bill also told a third party
where the phone was standing, at what time, on which camera.

The witness here is deliberately not the sanitiser's own report. Every
acceptance case below reads the bytes the *reader* was handed and asks the EXIF
parser about those, because a route can call a sanitiser and still forward the
original buffer -- that is exactly the bug, and only the reader's copy can see
it.

`b"iPhone" not in sent` sits next to the parsed check for the reason
``test_image_sanitizer.py`` gives: Pillow reports the tags it understands, while
a maker-note blob or a second APP segment it declines to parse would leave
``getexif()`` empty and the camera model sitting in the file.
"""

from __future__ import annotations

import io

import anyio
import pytest
from PIL import Image

from app.api.deps import get_receipt_reader
from app.api.main import create_app

from .conftest import ASGITestClient
from .helpers import ADVANCER_ID
from .test_receipts_scan import MOCKUP_READING, FakeReader

GPS_IFD = 0x8825
ORIENTATION = 0x0112
HEADERS = {"X-Actor-ID": str(ADVANCER_ID)}


def _exif_of_a_phone_at_a_restaurant() -> Image.Exif:
    exif = Image.Exif()
    exif[0x010F] = "Apple"
    exif[0x0110] = "iPhone 15 Pro"
    exif[0x9003] = "2026:08:30 20:15:00"
    gps = exif.get_ifd(GPS_IFD)
    # Hoan Kiem lake, 21°01'44"N 105°51'08"E. A real place, chosen because the
    # point of the case is that a real place is what leaks.
    gps[1] = "N"
    gps[2] = (21.0, 1.0, 44.0)
    gps[3] = "E"
    gps[4] = (105.0, 51.0, 8.0)
    return exif


def jpeg_with_gps(
    size: tuple[int, int] = (48, 32), orientation: int | None = None
) -> bytes:
    exif = _exif_of_a_phone_at_a_restaurant()
    if orientation is not None:
        exif[ORIENTATION] = orientation
    buffer = io.BytesIO()
    Image.new("RGB", size, (240, 240, 235)).save(
        buffer, format="JPEG", exif=exif.tobytes()
    )
    return buffer.getvalue()


def real_png(size: tuple[int, int] = (40, 24)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (250, 250, 248)).save(buffer, format="PNG")
    return buffer.getvalue()


def gps_tags_of(data: bytes) -> dict:
    with Image.open(io.BytesIO(data)) as image:
        return dict(image.getexif().get_ifd(GPS_IFD))


def size_of(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.size


@pytest.fixture
def reader():
    return FakeReader()


@pytest.fixture
def scan_client(monkeypatch, reader):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    app = create_app()
    app.dependency_overrides[get_receipt_reader] = lambda: reader
    return ASGITestClient(app)


def scan(client, *, content, filename="bill.jpg", content_type="image/jpeg"):
    return client.post(
        "/receipts/scan",
        files={"image": (filename, content, content_type)},
        headers=HEADERS,
    )


class TestTheWitnessIsReal:
    """Guard the fixture before trusting any verdict drawn from it."""

    def test_the_fixture_itself_carries_gps_or_this_file_proves_nothing(self):
        assert gps_tags_of(jpeg_with_gps()) != {}

    def test_the_fixture_itself_names_the_camera(self):
        assert b"iPhone" in jpeg_with_gps()


class TestNothingAboutThePhoneReachesTheReader:
    """rd-be-20: the bytes leaving this process must not carry the table."""

    def test_gps_does_not_reach_the_reader(self, scan_client, reader):
        scan(scan_client, content=jpeg_with_gps())
        sent, _ = reader.calls[0]
        assert gps_tags_of(sent) == {}

    def test_the_camera_model_does_not_reach_the_reader(self, scan_client, reader):
        scan(scan_client, content=jpeg_with_gps())
        sent, _ = reader.calls[0]
        assert b"iPhone" not in sent

    def test_the_capture_timestamp_does_not_reach_the_reader(self, scan_client, reader):
        scan(scan_client, content=jpeg_with_gps())
        sent, _ = reader.calls[0]
        assert b"2026:08:30" not in sent

    def test_the_original_upload_is_not_what_the_reader_receives(
        self, scan_client, reader
    ):
        """Blunt, and the one case a pass-through cannot fake."""

        original = jpeg_with_gps()
        scan(scan_client, content=original)
        sent, _ = reader.calls[0]
        assert sent != original

    def test_the_reader_is_told_the_type_of_the_bytes_it_actually_got(
        self, scan_client, reader
    ):
        """An opaque PNG comes back as JPEG, so the declared type must follow.

        Forwarding the *upload's* content type after re-encoding would hand the
        backend a label describing bytes that no longer exist.
        """

        scan(
            scan_client,
            content=real_png(),
            filename="bill.png",
            content_type="image/png",
        )
        sent, mime = reader.calls[0]
        with Image.open(io.BytesIO(sent)) as image:
            assert image.format == "JPEG"
        assert mime == "image/jpeg"


class TestReadingQualityIsNotTradedAway:
    """Stripping happens on the way in, so the reading must survive it."""

    def test_a_bill_still_scans(self, scan_client):
        assert scan(scan_client, content=jpeg_with_gps()).status_code == 200

    def test_the_same_eight_lines_and_the_same_printed_total_come_back(
        self, scan_client
    ):
        body = scan(scan_client, content=jpeg_with_gps()).json()
        assert len(body["items"]) == len(MOCKUP_READING["items"])
        assert body["total_vnd"] == 1125000

    def test_the_reader_still_receives_a_decodable_image(self, scan_client, reader):
        scan(scan_client, content=jpeg_with_gps())
        sent, _ = reader.calls[0]
        with Image.open(io.BytesIO(sent)) as image:
            image.load()
            assert image.size == (48, 32)

    def test_a_sideways_photograph_arrives_upright(self, scan_client, reader):
        """EXIF orientation 6 means "rotate 90°"; a bill held sideways is common.

        Backends read pixels, not the orientation tag, so applying the rotation
        before the call is what stops a legible bill arriving on its side.
        """

        scan(scan_client, content=jpeg_with_gps(size=(48, 32), orientation=6))
        sent, _ = reader.calls[0]
        assert size_of(sent) == (32, 48)


class TestBrokenUploadsKeepTheAnswerTheyAlreadyHad:
    """Adding a decoder must not turn a 4xx into a 500."""

    def test_bytes_that_are_not_an_image_still_answer_415(self, scan_client):
        response = scan(scan_client, content=b"this is not an image at all" * 40)
        assert response.status_code == 415
        assert response.json()["code"] == "unsupported_image_type"

    def test_a_truncated_image_still_answers_415(self, scan_client):
        """A header with no pixel data behind it. The old stub fixture, in fact.

        It reached the vision backend before this change, because nothing on the
        route had ever tried to decode it.
        """

        response = scan(scan_client, content=jpeg_with_gps()[:60])
        assert response.status_code == 415

    def test_a_broken_upload_never_reaches_the_reader(self, scan_client, reader):
        scan(scan_client, content=b"not an image" * 40)
        assert reader.calls == []


class TestTheSizeLimitStillGuardsTheDecoder:
    """Order matters: a limit applied after decoding is not a limit."""

    def test_an_oversize_upload_is_refused_before_anything_decodes_it(
        self, scan_client
    ):
        """9 MB of rubbish. 413 proves the byte check ran first.

        Were the sanitiser called before the 8 MB check, this payload would sit
        under its own 10 MB ceiling, get handed to the decoder, and come back
        415 ``unsupported_image_type`` -- a decode this route must never spend.
        """

        response = scan(scan_client, content=b"\x00" * (9 * 1024 * 1024))
        assert response.status_code == 413
        assert response.json()["code"] == "image_too_large"

    def test_an_oversize_upload_never_reaches_the_reader(self, scan_client, reader):
        scan(scan_client, content=b"\x00" * (9 * 1024 * 1024))
        assert reader.calls == []

    def test_a_pixel_bomb_under_the_byte_limit_is_refused(self, scan_client, reader):
        """50 megapixels of one colour compresses to a few kilobytes.

        The byte limit cannot see this one; only the pixel count can. It is
        refused as too large rather than allowed to expand in memory.
        """

        buffer = io.BytesIO()
        Image.new("L", (7100, 7100), 255).save(buffer, format="PNG")
        response = scan(
            scan_client,
            content=buffer.getvalue(),
            filename="bomb.png",
            content_type="image/png",
        )
        assert response.status_code == 413
        assert reader.calls == []
