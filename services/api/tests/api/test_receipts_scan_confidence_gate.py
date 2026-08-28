"""The confidence gate as the client sees it over HTTP.

The domain decides; this file proves the decision survives the route. A refused
reading must arrive as its own error code -- not the generic unreadable one --
because the app has to tell the user to photograph the bill again rather than
to try a different bill. A flagged reading must carry ``needs_review`` on the
wire, because that flag is what makes the app demand per-item confirmation.

The vision backend is faked here. This proves the wiring, not that any model
reads any receipt.
"""

from __future__ import annotations

import anyio
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


def reading(confidence: float, total_text: str | None = "368.000") -> dict:
    return {
        "document_type": "receipt",
        "items": [
            {"name": "Sườn nướng Mỹ", "quantity_text": "1", "line_total_text": "219.000"},
            {"name": "Ba chỉ heo", "quantity_text": "1", "line_total_text": "149.000"},
        ],
        "total_text": total_text,
        "confidence": confidence,
    }


class FakeReader:
    def __init__(self, reading: dict):
        self._reading = reading

    def read(self, image: bytes, mime_type: str) -> dict:
        del image, mime_type
        return self._reading


@pytest.fixture
def client_for(monkeypatch):
    def build(raw: dict) -> ASGITestClient:
        async def run_sync_inline(function, *args, **kwargs):
            del kwargs
            return function(*args)

        monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
        app = create_app()
        app.dependency_overrides[get_receipt_reader] = lambda: FakeReader(raw)
        return ASGITestClient(app)

    return build


def scan(client):
    return client.post(
        "/receipts/scan",
        files={"image": ("bill.png", PNG, "image/png")},
        headers=HEADERS,
    )


class TestABlurryPhotoIsRefused:
    def test_it_is_a_422(self, client_for):
        assert scan(client_for(reading(0.10))).status_code == 422

    def test_it_has_its_own_error_code(self, client_for):
        body = scan(client_for(reading(0.10))).json()
        assert body["code"] == "receipt_too_blurry"

    def test_the_message_tells_the_user_to_photograph_it_again(self, client_for):
        detail = scan(client_for(reading(0.10))).json()["detail"]
        assert "chụp lại" in detail.lower()

    def test_no_invented_items_come_back_for_the_user_to_confirm(self, client_for):
        """The whole point: refuse, do not hand over a list to rubber-stamp."""
        body = scan(client_for(reading(0.10))).json()
        assert "items" not in body

    def test_a_self_agreeing_fabrication_is_still_refused(self, client_for):
        """Totals agree and nothing warns; only confidence gives it away."""
        fabricated = {
            "document_type": "receipt",
            "items": [
                {"name": "Món 1", "quantity_text": "1", "line_total_text": "330.000"},
                {"name": "Món 2", "quantity_text": "1", "line_total_text": "330.000"},
            ],
            "total_text": "660.000",
            "confidence": 0.20,
        }
        response = scan(client_for(fabricated))
        assert response.status_code == 422
        assert response.json()["code"] == "receipt_too_blurry"


class TestTheMiddleBandCrossesTheWireFlagged:
    def test_it_is_still_a_200(self, client_for):
        assert scan(client_for(reading(0.75))).status_code == 200

    def test_needs_review_is_true(self, client_for):
        assert scan(client_for(reading(0.75))).json()["needs_review"] is True

    def test_the_items_are_there_to_confirm(self, client_for):
        assert len(scan(client_for(reading(0.75))).json()["items"]) == 2

    def test_a_warning_explains_why(self, client_for):
        assert scan(client_for(reading(0.75))).json()["warnings"]

    def test_the_money_is_untouched_by_the_flag(self, client_for):
        body = scan(client_for(reading(0.75))).json()
        assert body["items_total_vnd"] == 368000
        assert body["total_vnd"] == 368000


class TestAConfidentReadingIsNotFlagged:
    def test_needs_review_is_false(self, client_for):
        assert scan(client_for(reading(0.98))).json()["needs_review"] is False

    def test_needs_review_is_always_on_the_wire(self, client_for):
        """The app branches on it, so it may never be missing."""
        assert "needs_review" in scan(client_for(reading(0.98))).json()

    def test_a_reading_with_no_printed_total_is_flagged(self, client_for):
        body = scan(client_for(reading(0.98, total_text=None))).json()
        assert body["needs_review"] is True
