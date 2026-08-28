"""The document gate as the client sees it, plus what ADR-0009 forbids sending.

Two things are pinned here that the domain tests cannot see.

First: ``run_receipt_skill`` must route through the gate. The gate lives in its
own function so that ``read_receipt`` keeps the normalizer contract the rd-qa-03
regression file on ``main`` calls directly. That split is only safe if the one
production path provably takes the guarded door -- otherwise the guard is a
function nobody calls. These cases are that proof.

Second: ADR-0009 decision 4 says the skill returns no confidence score, because
"một con số tin cậy sẽ mời gọi giao diện tự động chấp nhận khi vượt ngưỡng".
rd-qa-03 then measured exactly why that decision was right: confidence tracked
legibility rather than correctness, and drifted 1.00/1.00/0.95/0.95/0.95 across
repeat calls on one image at temperature 0. So the number stays inside the
server, where it gates, and never reaches a screen, where it would be read as a
score. ``needs_review`` and ``warnings`` are the whole public contract.

The vision backend is faked. This proves the wiring, not that any model reads
any receipt.
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

# Four of the eight lines rd-qa-03 got back from a photographed menu, with the
# confidence and the absent printed total that made it look clean.
MENU_READING = {
    "document_type": "price_list",
    "items": [
        {"name": "Phở bò tái", "line_total_text": "65.000"},
        {"name": "Bún chả Hà Nội", "line_total_text": "70.000"},
        {"name": "Cơm tấm sườn", "line_total_text": "60.000"},
        {"name": "Gỏi cuốn", "line_total_text": "45.000"},
    ],
    "total_text": None,
    "confidence": 0.95,
}


def receipt_reading(**overrides) -> dict:
    reading = {
        "document_type": "receipt",
        "items": [
            {"name": "Sườn nướng Mỹ", "quantity_text": "1", "line_total_text": "219.000"},
            {"name": "Ba chỉ heo", "quantity_text": "1", "line_total_text": "149.000"},
        ],
        "total_text": "368.000",
        "confidence": 0.98,
    }
    reading.update(overrides)
    return reading


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


class TestAPhotographedMenuIsRefused:
    """The rd-qa-03 finding, end to end over HTTP."""

    def test_it_is_a_422(self, client_for):
        assert scan(client_for(MENU_READING)).status_code == 422

    def test_it_has_its_own_error_code(self, client_for):
        """Not ``receipt_unreadable``: the photo was read fine, it is the wrong paper."""
        assert scan(client_for(MENU_READING)).json()["code"] == "not_a_receipt"

    def test_the_message_names_the_mistake_the_person_made(self, client_for):
        detail = scan(client_for(MENU_READING)).json()["detail"].lower()
        assert "thực đơn" in detail or "bảng giá" in detail

    def test_no_items_and_no_total_come_back(self, client_for):
        """340.000 dong nobody spent must not reach a screen at all."""
        body = scan(client_for(MENU_READING)).json()
        assert "items" not in body
        assert "items_total_vnd" not in body

    def test_an_unclassified_reading_is_refused_too(self, client_for):
        """A backend that skipped the question does not get the benefit of doubt."""
        reading = receipt_reading()
        del reading["document_type"]
        response = scan(client_for(reading))
        assert response.status_code == 422
        assert response.json()["code"] == "not_a_receipt"

    def test_a_document_that_is_neither_is_refused(self, client_for):
        response = scan(client_for(receipt_reading(document_type="other")))
        assert response.status_code == 422
        assert response.json()["code"] == "not_a_receipt"

    def test_a_blurry_photo_is_still_reported_as_blur_not_as_wrong_paper(
        self, client_for
    ):
        """Ordering survives the route: unreadable beats unclassifiable."""
        response = scan(
            client_for(receipt_reading(document_type="other", confidence=0.10))
        )
        assert response.json()["code"] == "receipt_too_blurry"


class TestARealReceiptStillPasses:
    def test_it_is_a_200(self, client_for):
        assert scan(client_for(receipt_reading())).status_code == 200

    def test_the_money_arrives_untouched(self, client_for):
        body = scan(client_for(receipt_reading())).json()
        assert body["items_total_vnd"] == 368_000
        assert body["total_vnd"] == 368_000
        assert [item["line_total_vnd"] for item in body["items"]] == [219_000, 149_000]


class TestConfidenceNeverReachesTheClient:
    """ADR-0009 decision 4, enforced at the wire instead of by convention."""

    def test_the_field_is_absent_from_a_clean_reading(self, client_for):
        assert "confidence" not in scan(client_for(receipt_reading())).json()

    def test_the_field_is_absent_from_a_flagged_reading(self, client_for):
        body = scan(client_for(receipt_reading(confidence=0.75))).json()
        assert body["needs_review"] is True
        assert "confidence" not in body

    def test_no_percentage_leaks_through_the_warnings(self, client_for):
        """A warning reading "độ tin cậy 75%" would reintroduce the score."""
        body = scan(client_for(receipt_reading(confidence=0.75))).json()
        assert not any("%" in warning for warning in body["warnings"])

    def test_the_gate_still_uses_it(self, client_for):
        """Hidden, not deleted: the same number still decides the outcome."""
        assert scan(client_for(receipt_reading(confidence=0.10))).status_code == 422
        assert scan(client_for(receipt_reading(confidence=0.98))).status_code == 200

    def test_the_replacement_signal_is_a_flag_not_a_number(self, client_for):
        body = scan(client_for(receipt_reading())).json()
        assert body["needs_review"] is False
        assert isinstance(body["needs_review"], bool)
