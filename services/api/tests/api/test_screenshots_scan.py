"""F26 HTTP and image-boundary tests with a deterministic screenshot reader."""

from __future__ import annotations

import io
from importlib import import_module

import pytest
from PIL import Image
from pydantic import ValidationError

from app.api.search_rate_limit import FixedWindowLimiter
from app.media.images import SanitizedImage

from .helpers import ADVANCER_ID, SENDER_ID, png_bytes
from .test_receipts_scan_strips_exif import gps_tags_of, jpeg_with_gps

PNG = png_bytes()
HEADERS = {"X-Actor-ID": str(ADVANCER_ID)}
READING = {
    "source": "grab",
    "merchant": "  GrabFood  ",
    "total_text": "180k",
    "occurred_on": "2030-08-30",
    "confidence": 0.97,
}


class PinnedScreenshotReader:
    def __init__(self, reading: dict | None = None, error: Exception | None = None):
        self.reading = dict(READING if reading is None else reading)
        self.error = error
        self.calls: list[tuple[bytes, str]] = []

    def read(self, image: bytes, mime_type: str) -> dict:
        self.calls.append((image, mime_type))
        if self.error is not None:
            raise self.error
        return dict(self.reading)


@pytest.fixture
def reader():
    return PinnedScreenshotReader()


@pytest.fixture
def screenshot_client(client, reader):
    deps = import_module("app.api.deps")
    client.app.dependency_overrides[deps.get_screenshot_reader] = lambda: reader
    return client


def _scan(
    client,
    *,
    content: bytes = PNG,
    filename: str = "screenshot.png",
    content_type: str = "image/png",
    headers: dict | None = None,
):
    return client.post(
        "/screenshots/scan",
        files={"image": (filename, content, content_type)},
        headers=HEADERS if headers is None else headers,
    )


def test_screenshot_route_is_registered(client) -> None:
    routes = {
        (method, route.path)
        for route in client.app.routes
        for method in (getattr(route, "methods", None) or ())
    }

    assert ("POST", "/screenshots/scan") in routes


def test_screenshot_form_declares_only_the_image_field(client) -> None:
    document = client.app.openapi()
    operation = document["paths"]["/screenshots/scan"]["post"]
    body_schema = operation["requestBody"]["content"]["multipart/form-data"][
        "schema"
    ]
    component = document["components"]["schemas"][body_schema["$ref"].rsplit("/", 1)[1]]

    assert set(component["properties"]) == {"image"}


def test_screenshot_happy_path_has_the_exact_public_shape(
    screenshot_client, reader
) -> None:
    response = _scan(screenshot_client)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "source": "grab",
        "merchant": "GrabFood",
        "total_vnd": 180_000,
        "occurred_on": "2030-08-30",
        "needs_review": True,
    }
    assert "confidence" not in response.json()
    assert len(reader.calls) == 1


def test_screenshot_reader_gets_rebuilt_pixels_and_their_real_content_type(
    screenshot_client, reader
) -> None:
    response = _scan(screenshot_client)

    assert response.status_code == 200
    [(sent, mime_type)] = reader.calls
    assert sent != PNG
    with Image.open(io.BytesIO(sent)) as rebuilt:
        rebuilt.load()
        assert rebuilt.format == "JPEG"
        assert rebuilt.size == (40, 24)
    assert mime_type == "image/jpeg"


def test_screenshot_phone_metadata_never_reaches_the_reader(
    screenshot_client, reader
) -> None:
    original = jpeg_with_gps()

    response = _scan(
        screenshot_client,
        content=original,
        filename="screenshot.jpg",
        content_type="image/jpeg",
    )

    assert response.status_code == 200
    [(sent, mime_type)] = reader.calls
    assert sent != original
    assert gps_tags_of(sent) == {}
    assert b"iPhone" not in sent
    assert mime_type == "image/jpeg"


def test_screenshot_byte_ceiling_runs_before_sanitizing_or_reading(
    monkeypatch,
) -> None:
    skill = import_module("app.api.screenshot_skill")
    reader = PinnedScreenshotReader()
    sanitizer_calls: list[bytes] = []

    def should_not_decode(raw: bytes) -> SanitizedImage:
        sanitizer_calls.append(raw)
        raise AssertionError("oversized upload reached the decoder")

    monkeypatch.setattr(skill, "sanitize_image", should_not_decode)

    with pytest.raises(skill.ScreenshotError) as caught:
        skill.run_screenshot_skill(
            b"x" * (skill.MAX_IMAGE_BYTES + 1),
            "image/png",
            reader=reader,
        )

    assert caught.value.code == "IMAGE_TOO_LARGE"
    assert sanitizer_calls == []
    assert reader.calls == []


def test_screenshot_skill_reuses_receipt_image_limits_and_rejection_map() -> None:
    receipt = import_module("app.api.receipt_skill")
    screenshot = import_module("app.api.screenshot_skill")

    assert screenshot.ALLOWED_MIME_TYPES is receipt.ALLOWED_MIME_TYPES
    assert screenshot.MAX_IMAGE_BYTES == receipt.MAX_IMAGE_BYTES
    assert (
        screenshot._REJECTION_TO_SCREENSHOT_CODE
        is receipt._REJECTION_TO_RECEIPT_CODE
    )


@pytest.mark.parametrize(
    ("content", "content_type", "status_code", "code"),
    [
        (b"", "image/png", 422, "screenshot_unreadable"),
        (PNG, "application/pdf", 415, "unsupported_image_type"),
        (
            b"x" * ((8 * 1024 * 1024) + 1),
            "image/png",
            413,
            "image_too_large",
        ),
        (b"not an image", "image/png", 415, "unsupported_image_type"),
    ],
)
def test_screenshot_upload_refusals_have_stable_wire_errors(
    screenshot_client,
    reader,
    content: bytes,
    content_type: str,
    status_code: int,
    code: str,
) -> None:
    response = _scan(
        screenshot_client,
        content=content,
        content_type=content_type,
    )

    assert response.status_code == status_code
    assert response.json()["code"] == code
    assert reader.calls == []


def test_screenshot_missing_file_is_a_422(screenshot_client) -> None:
    response = screenshot_client.post("/screenshots/scan", headers=HEADERS)

    assert response.status_code == 422


def test_screenshot_requires_an_actor_before_reading(screenshot_client, reader) -> None:
    response = _scan(screenshot_client, headers={})

    assert response.status_code == 401
    assert reader.calls == []


@pytest.mark.parametrize(
    ("reading", "code"),
    [
        ({**READING, "source": "other"}, "not_a_transaction"),
        ({**READING, "total_text": 180_000.0}, "screenshot_unreadable"),
        (
            {**READING, "paid_by": "Người trong ảnh"},
            "screenshot_model_named_a_person",
        ),
    ],
)
def test_screenshot_domain_refusals_are_422(
    screenshot_client, reader, reading: dict, code: str
) -> None:
    reader.reading = reading

    response = _scan(screenshot_client)

    assert response.status_code == 422
    assert response.json()["code"] == code


def test_screenshot_missing_backend_key_is_a_503(screenshot_client, reader) -> None:
    module = import_module("app.domain.screenshot")
    reader.error = module.ScreenshotError("SCREENSHOT_READER_NOT_CONFIGURED")

    response = _scan(screenshot_client)

    assert response.status_code == 503
    assert response.json()["code"] == "screenshot_reader_not_configured"


def test_screenshot_backend_failure_leaks_neither_output_nor_image(
    screenshot_client, reader, caplog
) -> None:
    private_output = "private model output and synthetic api key"
    reader.error = RuntimeError(private_output)

    response = _scan(screenshot_client)

    assert response.status_code == 502
    assert response.json()["code"] == "screenshot_reader_unavailable"
    assert private_output not in response.text
    assert private_output not in caplog.text
    assert PNG.hex() not in caplog.text


def test_screenshot_rate_limit_is_per_actor(screenshot_client, reader) -> None:
    routes = import_module("app.api.routes.screenshots")
    limiter = FixedWindowLimiter(
        limit=1,
        window_seconds=60,
        code="screenshot_scan_rate_limited",
        message="Quá nhiều lượt đọc ảnh chụp màn hình.",
    )
    screenshot_client.app.dependency_overrides[
        routes.get_screenshot_scan_limiter
    ] = lambda: limiter

    first = _scan(screenshot_client)
    refused = _scan(screenshot_client)
    other_actor = _scan(
        screenshot_client,
        headers={"X-Actor-ID": str(SENDER_ID)},
    )

    assert first.status_code == 200
    assert refused.status_code == 429
    assert refused.json()["code"] == "screenshot_scan_rate_limited"
    assert other_actor.status_code == 200
    assert len(reader.calls) == 2


def test_screenshot_limiter_is_independent_from_receipt_limiter(client) -> None:
    assert (
        client.app.state.screenshot_scan_limiter
        is not client.app.state.receipt_scan_limiter
    )


@pytest.mark.parametrize("bad_total", [180_000.0, "180000", True, 0])
def test_screenshot_response_money_is_strict_and_positive(bad_total) -> None:
    schemas = import_module("app.api.schemas")

    with pytest.raises(ValidationError):
        schemas.ScreenshotScanResponse(
            source="grab",
            merchant="GrabFood",
            total_vnd=bad_total,
            occurred_on="2030-08-30",
            needs_review=True,
        )


def test_screenshot_source_excludes_the_non_transaction_escape_hatch() -> None:
    schemas = import_module("app.api.schemas")

    with pytest.raises(ValidationError):
        schemas.ScreenshotScanResponse(
            source="other",
            merchant="Không có giao dịch",
            total_vnd=180_000,
            occurred_on=None,
            needs_review=True,
        )
