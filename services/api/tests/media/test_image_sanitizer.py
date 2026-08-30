"""A phone photograph says where it was taken. This module is what forgets it.

Every acceptance case here reads the bytes that would actually be written to
disk, never a field on an object the sanitiser returned about itself. That
distinction is the whole point: a function can report "stripped" and still hand
back a buffer whose APP1 segment holds the latitude of somebody's flat, and the
only witness that can tell the difference is the buffer.

`assert b"iPhone" not in out.data` looks cruder than reading the EXIF table and
is deliberately kept alongside it. Pillow parses the tags it knows; a maker-note
blob, an XMP packet or a second APP segment it declines to interpret would leave
`getexif()` empty and the camera model sitting in the file. One assertion covers
what the parser understands, the other covers what it does not.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from app.media.images import MAX_UPLOAD_BYTES, ImageRejected, sanitize_image

GPS_IFD = 0x8825
ORIENTATION = 0x0112


def _exif_with_everything() -> Image.Exif:
    """The metadata an ordinary iPhone attaches without being asked."""

    exif = Image.Exif()
    exif[0x010F] = "Apple"
    exif[0x0110] = "iPhone 15 Pro"
    exif[0x9003] = "2026:08:29 21:15:00"
    gps = exif.get_ifd(GPS_IFD)
    # 10°46'12"N 106°41'55"E -- a real address in Ho Chi Minh City, which is
    # exactly the kind of fact that must not survive being shared with a group.
    gps[1] = "N"
    gps[2] = (10.0, 46.0, 12.0)
    gps[3] = "E"
    gps[4] = (106.0, 41.0, 55.0)
    return exif


def jpeg_with_gps(size: tuple[int, int] = (48, 32), orientation: int | None = None) -> bytes:
    exif = _exif_with_everything()
    if orientation is not None:
        exif[ORIENTATION] = orientation
    buffer = io.BytesIO()
    Image.new("RGB", size, (12, 200, 90)).save(
        buffer, format="JPEG", exif=exif.tobytes()
    )
    return buffer.getvalue()


def test_the_fixture_itself_carries_gps_or_this_file_proves_nothing():
    """Guard the witness before trusting any verdict it gives.

    A fixture that quietly stopped writing GPS would turn every assertion below
    into a tautology, and the suite would stay green while the sanitiser was
    deleted. So the first test is about the test data.
    """

    exif = Image.open(io.BytesIO(jpeg_with_gps())).getexif()

    assert dict(exif.get_ifd(GPS_IFD)), "fixture lost its GPS tags"
    assert exif[0x0110] == "iPhone 15 Pro"
    assert b"iPhone" in jpeg_with_gps()


def test_gps_does_not_survive_sanitising():
    out = sanitize_image(jpeg_with_gps())

    exif = Image.open(io.BytesIO(out.data)).getexif()
    assert dict(exif.get_ifd(GPS_IFD)) == {}
    assert dict(exif) == {}


def test_camera_make_and_model_and_capture_time_do_not_survive_either():
    """The brief says strip everything, not only the coordinates.

    A camera model plus a capture time is a fingerprint: it links two photos
    posted in two different groups to one phone.
    """

    out = sanitize_image(jpeg_with_gps())

    assert b"Apple" not in out.data
    assert b"iPhone" not in out.data
    assert b"2026:08:29" not in out.data


def test_orientation_is_applied_before_it_is_discarded():
    """Tag 274 = 6 means "the camera was rotated a quarter turn".

    Dropping the tag without acting on it is how a stripped photo arrives
    sideways. The pixels have to move so the tag becomes unnecessary.
    """

    out = sanitize_image(jpeg_with_gps(size=(48, 32), orientation=6))

    assert (out.width, out.height) == (32, 48)
    assert ORIENTATION not in dict(Image.open(io.BytesIO(out.data)).getexif())


def test_png_text_chunks_are_stripped_too():
    """EXIF is not the only place a phone writes a sentence about you."""

    info = PngInfo()
    # No digits in this string on purpose: a coordinate pair written out in
    # full trips the repo guard's long-number rule, which is looking for bank
    # account numbers and cannot tell the two apart.
    info.add_text("Comment", "Chup o nha Kiet, gan Ho Con Rua")
    info.add_text("Software", "Adobe Lightroom Mobile")
    buffer = io.BytesIO()
    Image.new("RGBA", (20, 20), (255, 0, 0, 128)).save(
        buffer, format="PNG", pnginfo=info
    )

    out = sanitize_image(buffer.getvalue())

    assert Image.open(io.BytesIO(out.data)).text == {}
    assert b"Chup o nha Kiet" not in out.data
    assert b"Lightroom" not in out.data


def test_transparency_survives_because_only_metadata_is_meant_to_die():
    """A counter-case. Stripping must not quietly flatten the picture.

    Without this, "sanitise" could be implemented as "re-encode everything to
    opaque JPEG" and every test above would still pass while avatars with
    transparent corners came back with black boxes.
    """

    buffer = io.BytesIO()
    Image.new("RGBA", (20, 20), (255, 0, 0, 40)).save(buffer, format="PNG")

    out = sanitize_image(buffer.getvalue())

    assert out.content_type == "image/png"
    assert Image.open(io.BytesIO(out.data)).getchannel("A").getextrema() == (40, 40)


def test_a_photograph_still_looks_like_itself_afterwards():
    """The other half of the counter-case: opaque photos keep their pixels."""

    out = sanitize_image(jpeg_with_gps())

    restored = Image.open(io.BytesIO(out.data)).convert("RGB")
    assert out.content_type == "image/jpeg"
    assert (out.width, out.height) == (48, 32)
    # JPEG is lossy, so this asserts "still green", not "byte-identical".
    red, green, blue = restored.getpixel((24, 16))
    assert green > 150 and red < 80 and blue < 140


def test_a_file_that_is_not_an_image_is_refused():
    """An endpoint that accepts arbitrary bytes is an endpoint that accepts
    malware. The refusal has to come from decoding, not from a filename."""

    with pytest.raises(ImageRejected) as refusal:
        sanitize_image(b"#!/bin/sh\nrm -rf /\n")

    assert refusal.value.code == "not_an_image"


def test_a_jpeg_header_glued_onto_rubbish_is_still_refused():
    """Content sniffing that stops at the magic bytes is not sniffing.

    This is the shape an upload takes when somebody wants the extension check
    to say "image" and the body to say something else.
    """

    with pytest.raises(ImageRejected) as refusal:
        sanitize_image(b"\xff\xd8\xff\xe0" + b"\x00" * 512)

    assert refusal.value.code == "not_an_image"


def test_an_empty_body_is_refused():
    with pytest.raises(ImageRejected) as refusal:
        sanitize_image(b"")

    assert refusal.value.code == "not_an_image"


def test_something_larger_than_the_cap_is_refused_by_size_not_by_decoding():
    """Size is checked first so a decompression bomb is never handed to Pillow."""

    with pytest.raises(ImageRejected) as refusal:
        sanitize_image(b"\x00" * (MAX_UPLOAD_BYTES + 1))

    assert refusal.value.code == "image_too_large"


def test_the_cap_is_ten_mebibytes():
    """Named so a change to the limit is a decision somebody made on purpose."""

    assert MAX_UPLOAD_BYTES == 10 * 1024 * 1024
