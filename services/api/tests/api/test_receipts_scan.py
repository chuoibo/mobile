"""``POST /receipts/scan`` orchestration, with the vision backend faked.

No network and no API key are involved here. What this file proves is the part
that stays true whichever model is plugged in: the wire shape, that a receipt
whose lines disagree with its printed total reaches the client with BOTH
numbers intact, and that a backend failure never leaks a credential into the
response or the log.

What it does NOT prove is that any real model can read a real receipt. That
claim needs a real photo and a real call, and lives in ``tests/live/``.
"""

from __future__ import annotations

import logging

import anyio
import httpx
import pytest

from app.api.deps import get_receipt_reader
from app.api.main import create_app

from .conftest import ASGITestClient
from .helpers import ADVANCER_ID

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
)
HEADERS = {"X-Actor-ID": str(ADVANCER_ID)}

# The mockup receipt: eight lines summing to 936.000, with 1.125.000 printed at
# the bottom. It is used here because a reading whose numbers already agree
# cannot fail the test that matters.
MOCKUP_READING = {
    "items": [
        {"name": "Sườn nướng Mỹ", "quantity_text": "1", "line_total_text": "219.000"},
        {"name": "Ba chỉ heo", "quantity_text": "1", "line_total_text": "149.000"},
        {"name": "Bò cuộn phô mai", "quantity_text": "1", "line_total_text": "129.000"},
        {"name": "Lẩu kim chi", "quantity_text": "1", "line_total_text": "199.000"},
        {"name": "Tokbokki phô mai", "quantity_text": "1", "line_total_text": "79.000"},
        {"name": "Cơm chiên trứng", "quantity_text": "1", "line_total_text": "79.000"},
        {"name": "Pepsi", "quantity_text": "2", "line_total_text": "28.000"},
        {"name": "Tiger bạc", "quantity_text": "3", "line_total_text": "54.000"},
    ],
    "total_text": "1.125.000",
    "confidence": 0.92,
}

FAKE_KEY = "AIzaSyFAKEfakeFAKEfakeFAKEfakeFAKEfake123"


class FakeReader:
    """Records what it was handed; returns a canned reading."""

    def __init__(self, reading=None, error=None):
        self.reading = reading if reading is not None else MOCKUP_READING
        self.error = error
        self.calls: list[tuple[bytes, str]] = []

    def read(self, image: bytes, mime_type: str) -> dict:
        self.calls.append((image, mime_type))
        if self.error is not None:
            raise self.error
        return self.reading


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


def scan(client, *, content=PNG, filename="bill.png", content_type="image/png", **kw):
    return client.post(
        "/receipts/scan",
        files={"image": (filename, content, content_type)},
        headers=kw.pop("headers", HEADERS),
        **kw,
    )


class TestScanShape:
    """The schema the task names: items[], total_vnd, confidence."""

    def test_ok(self, scan_client):
        assert scan(scan_client).status_code == 200

    def test_every_item_carries_the_four_contracted_fields(self, scan_client):
        body = scan(scan_client).json()
        for item in body["items"]:
            assert set(item) >= {
                "name",
                "quantity",
                "unit_price_vnd",
                "line_total_vnd",
            }

    def test_eight_items_survive_the_round_trip(self, scan_client):
        assert len(scan(scan_client).json()["items"]) == 8

    def test_printed_total_is_reported(self, scan_client):
        assert scan(scan_client).json()["total_vnd"] == 1125000

    def test_confidence_is_reported(self, scan_client):
        assert scan(scan_client).json()["confidence"] == 92

    def test_money_crosses_the_wire_as_json_integers(self, scan_client):
        body = scan(scan_client).json()
        assert isinstance(body["total_vnd"], int)
        assert all(isinstance(i["line_total_vnd"], int) for i in body["items"])

    def test_the_uploaded_bytes_reach_the_reader(self, scan_client, reader):
        scan(scan_client)
        assert reader.calls == [(PNG, "image/png")]


class TestTotalsAreNotReconciled:
    """The money rule, checked at the boundary the client actually reads."""

    def test_both_totals_reach_the_client(self, scan_client):
        body = scan(scan_client).json()
        assert body["items_total_vnd"] == 936000
        assert body["total_vnd"] == 1125000

    def test_the_gap_is_named_rather_than_closed(self, scan_client):
        body = scan(scan_client).json()
        assert body["totals_agree"] is False
        assert body["total_difference_vnd"] == 1125000 - 936000

    def test_the_client_is_warned(self, scan_client):
        assert scan(scan_client).json()["warnings"]

    def test_no_line_was_rewritten_to_make_the_sum_come_out(self, scan_client):
        body = scan(scan_client).json()
        assert [i["line_total_vnd"] for i in body["items"]] == [
            219000,
            149000,
            129000,
            199000,
            79000,
            79000,
            28000,
            54000,
        ]


class TestUploadValidation:
    def test_a_missing_file_is_a_422(self, scan_client):
        assert scan_client.post("/receipts/scan", headers=HEADERS).status_code == 422

    def test_an_empty_file_is_refused(self, scan_client):
        assert scan(scan_client, content=b"").status_code == 422

    def test_a_pdf_is_refused_with_415(self, scan_client):
        response = scan(scan_client, content_type="application/pdf")
        assert response.status_code == 415

    def test_a_refused_upload_never_reaches_the_model(self, scan_client, reader):
        scan(scan_client, content_type="application/pdf")
        assert reader.calls == []

    def test_an_oversized_upload_is_refused_with_413(self, scan_client):
        response = scan(scan_client, content=b"\x89PNG" + b"\x00" * (12 * 1024 * 1024))
        assert response.status_code == 413

    def test_an_oversized_upload_never_reaches_the_model(self, scan_client, reader):
        scan(scan_client, content=b"\x89PNG" + b"\x00" * (12 * 1024 * 1024))
        assert reader.calls == []

    def test_jpeg_is_accepted(self, scan_client):
        assert scan(scan_client, content_type="image/jpeg").status_code == 200

    def test_an_anonymous_caller_is_refused(self, scan_client):
        assert scan(scan_client, headers={}).status_code == 401


class TestBackendFailure:
    @pytest.fixture
    def broken_client(self, monkeypatch):
        async def run_sync_inline(function, *args, **kwargs):
            del kwargs
            return function(*args)

        monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
        app = create_app()
        # An upstream error message that carries the credential in a query
        # string -- exactly how an SDK reports a 4xx, and exactly the string
        # that must not survive to the client or the log.
        broken = FakeReader(
            error=RuntimeError(
                "429 quota exceeded for "
                f"https://generativelanguage.googleapis.com/v1beta/models?key={FAKE_KEY}"
            )
        )
        app.dependency_overrides[get_receipt_reader] = lambda: broken
        return ASGITestClient(app)

    def test_a_backend_error_is_a_502(self, broken_client):
        assert scan(broken_client).status_code == 502

    def test_the_error_body_is_the_stable_shape(self, broken_client):
        body = scan(broken_client).json()
        assert set(body) == {"code", "detail"}
        assert body["code"] == "receipt_reader_unavailable"

    def test_the_api_key_is_not_in_the_response_body(self, broken_client):
        assert FAKE_KEY not in scan(broken_client).text

    def test_no_fragment_of_the_upstream_url_is_echoed(self, broken_client):
        """Echoing the upstream message is how keys escape. Do not echo it."""
        assert "googleapis.com" not in scan(broken_client).text

    def test_the_api_key_is_not_written_to_the_log(self, broken_client, caplog):
        with caplog.at_level(logging.DEBUG):
            scan(broken_client)
        assert FAKE_KEY not in caplog.text

    def test_an_unreadable_reading_is_a_422_not_a_500(self, monkeypatch):
        async def run_sync_inline(function, *args, **kwargs):
            del kwargs
            return function(*args)

        monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
        app = create_app()
        app.dependency_overrides[get_receipt_reader] = lambda: FakeReader(
            reading={"items": [], "confidence": 0.1}
        )
        response = scan(ASGITestClient(app))
        assert response.status_code == 422
        assert response.json()["code"] == "receipt_unreadable"


class TestTheImageIsNotKept:
    def test_the_response_does_not_echo_the_image(self, scan_client):
        """A bill photo is sensitive. It goes in, it does not come back out."""
        assert "iVBORw" not in scan(scan_client).text


def test_the_endpoint_is_reachable_over_a_plain_asgi_transport():
    """Guards against the route being registered only in a test-only app."""

    async def probe():
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get("/openapi.json")

    paths = anyio.run(probe).json()["paths"]
    assert "/receipts/scan" in paths
