"""The wire outcome rd-qa-37 measured: one bill, two answers.

QA sent one unchanged file (sha256 43bcfa4a056f) at ``POST /receipts/scan``
eleven times and got 200 six times and ``422 receipt_unreadable`` five times.
The reading below is the verbatim payload from a failing call, captured by
instrumenting the reader seam over 12 real Gemini calls.

The domain contract for the marker lives in
``tests/domain/test_receipt_quantity_marker.py``. What this file adds is the
status code, because that is the part a person on a stage actually sees: the
generic 422 tells them the photograph was bad and invites them to shoot the
bill again, and re-shooting cannot change what the paper says.

The reader is faked here on purpose. Pinning the payload is what makes the test
deterministic -- the live nondeterminism is the thing under test, so depending
on it would reproduce the flake inside the suite.
"""

from __future__ import annotations

import anyio
import pytest

from app.api.deps import get_receipt_reader
from app.api.main import create_app

from .conftest import ASGITestClient
from .helpers import ADVANCER_ID, png_bytes

PNG = png_bytes()
HEADERS = {"X-Actor-ID": str(ADVANCER_ID)}

# Verbatim, /tmp/rd-be-21-diag/records.json attempt 1. Five items, 235.000.
READING_WITH_MARKERS = {
    "document_type": "receipt",
    "items": [
        {
            "name": "Cơm tấm sườn bì chả",
            "unit_price_text": None,
            "line_total_text": "65.000",
        },
        {
            "name": "Cơm tấm sườn nướng",
            "unit_price_text": None,
            "line_total_text": "55.000",
        },
        {
            "name": "Canh chua cá lóc",
            "unit_price_text": None,
            "line_total_text": "45.000",
        },
        {
            "name": "Trà đá",
            "quantity_text": "X4",
            "unit_price_text": None,
            "line_total_text": "20.000",
        },
        {
            "name": "Bia Sài Gòn",
            "quantity_text": "X2",
            "unit_price_text": None,
            "line_total_text": "50.000",
        },
    ],
    "total_text": "235.000",
    "confidence": 0.95,
}

# The same paper, transcribed the other way: the count folded into the dish
# name. This shape already answered 200 before the fix, and the assertion that
# matters is that BOTH now agree on the money.
READING_WITH_MARKERS_IN_THE_NAME = {
    "document_type": "receipt",
    "items": [
        {"name": "Cơm tấm sườn bì chả", "line_total_text": "65.000"},
        {"name": "Cơm tấm sườn nướng", "line_total_text": "55.000"},
        {"name": "Canh chua cá lóc", "line_total_text": "45.000"},
        {"name": "Trà đá X4", "line_total_text": "20.000"},
        {"name": "Bia Sài Gòn X2", "line_total_text": "50.000"},
    ],
    "total_text": "235.000",
    "confidence": 0.98,
}


class PinnedReader:
    def __init__(self, reading):
        self.reading = reading

    def read(self, image: bytes, mime_type: str) -> dict:
        del image, mime_type
        return self.reading


def client_reading(reading, monkeypatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    app = create_app()
    app.dependency_overrides[get_receipt_reader] = lambda: PinnedReader(reading)
    return ASGITestClient(app)


def scan(client):
    return client.post(
        "/receipts/scan",
        files={"image": ("bill.png", PNG, "image/png")},
        headers=HEADERS,
    )


class TestMarkerReadingIsAccepted:
    def test_it_is_not_refused(self, monkeypatch):
        response = scan(client_reading(READING_WITH_MARKERS, monkeypatch))
        assert response.status_code == 200

    def test_the_person_is_not_told_to_reshoot_a_readable_bill(self, monkeypatch):
        response = scan(client_reading(READING_WITH_MARKERS, monkeypatch))
        assert response.json().get("code") != "receipt_unreadable"

    def test_the_printed_total_survives(self, monkeypatch):
        body = scan(client_reading(READING_WITH_MARKERS, monkeypatch)).json()
        assert body["total_vnd"] == 235000
        assert body["items_total_vnd"] == 235000
        assert body["totals_agree"] is True

    def test_the_counts_reach_the_client(self, monkeypatch):
        body = scan(client_reading(READING_WITH_MARKERS, monkeypatch)).json()
        assert [item["quantity"] for item in body["items"]] == [1, 1, 1, 4, 2]


class TestBothTranscriptionsAgreeOnMoney:
    """Whichever way the model splits the line, the bill is 235.000."""

    @pytest.mark.parametrize(
        "reading",
        [READING_WITH_MARKERS, READING_WITH_MARKERS_IN_THE_NAME],
        ids=["quantity_in_its_own_field", "quantity_folded_into_the_name"],
    )
    def test_same_paper_same_total(self, reading, monkeypatch):
        body = scan(client_reading(reading, monkeypatch)).json()
        assert body["total_vnd"] == 235000
        assert body["items_total_vnd"] == 235000

    @pytest.mark.parametrize(
        "reading",
        [READING_WITH_MARKERS, READING_WITH_MARKERS_IN_THE_NAME],
        ids=["quantity_in_its_own_field", "quantity_folded_into_the_name"],
    )
    def test_same_paper_same_status(self, reading, monkeypatch):
        assert scan(client_reading(reading, monkeypatch)).status_code == 200
