"""The two halves of rd-be-22, at the tier the ticket actually measured.

#220 fixed both halves and #213 fixed the marker before it, but the gates the
two shipped with do not cover this tier:

1. A blank ``quantity_text`` reads as 1. That is proven in
   ``tests/domain/test_receipt_quantity_absent.py``, which imports
   ``read_receipt`` and never builds a request. The ticket measured the damage
   over HTTP -- "5/10 read, 5 x 422 receipt_unreadable" -- and no case in
   ``tests/api/`` sends a blank count at all, so nothing here would notice if
   the route stopped agreeing with the domain.

2. Every refusal writes its CODE down. Deleting the ``_LOGGER.info`` line from
   ``routes/receipts.py`` and running the whole suite gives 1451 passed, 0
   failed: the line shipped with no gate under it. It is the reason a
   deterministic domain bug wore "the model is nondeterministic" for hours, so
   losing it silently costs the next person the same hours.

The privacy assertion is deliberately paired with a positive one in the same
test. ``assert transcription not in caplog.text`` is satisfied perfectly by a
dead logging channel -- the exact failure ``tests/postgres/
test_log_channel_postgres.py`` exists to catch -- so on its own it would prove
nothing. Asserting the code IS present first means a dead channel fails the
test instead of flattering it.

The reader is pinned rather than live. The nondeterminism is the subject here,
so depending on it would reproduce the flake inside the suite.
"""

from __future__ import annotations

import logging

import anyio
import pytest

from app.api.deps import get_receipt_reader
from app.api.main import create_app

from .conftest import ASGITestClient
from .helpers import ADVANCER_ID, png_bytes

PNG = png_bytes()
HEADERS = {"X-Actor-ID": str(ADVANCER_ID)}
ROUTE_LOGGER = "app.api.routes.receipts"

# The shape rd-be-22 captured at the reader seam: three of eight sampled
# readings came back with quantity_text='' on a line the model could not find a
# count for. Everything else on the paper was read correctly, which is what
# made refusing the whole document so expensive.
READING_WITH_A_BLANK_COUNT = {
    "document_type": "receipt",
    "items": [
        {"name": "Cơm tấm sườn bì chả", "line_total_text": "65.000"},
        {"name": "Canh chua cá lóc", "quantity_text": "", "line_total_text": "45.000"},
        {"name": "Trà đá", "quantity_text": "X4", "line_total_text": "20.000"},
    ],
    "total_text": "130.000",
    "confidence": 0.95,
}

# "vài" is a count that was printed and cannot be read -- still a refusal after
# #220, and the code the ticket saw 153 times out of 153 failures.
READING_WITH_AN_UNREADABLE_COUNT = {
    "document_type": "receipt",
    "items": [
        {"name": "Cơm tấm sườn bì chả", "line_total_text": "65.000"},
        {"name": "Trà đá", "quantity_text": "vài", "line_total_text": "20.000"},
    ],
    "total_text": "85.000",
    "confidence": 0.95,
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


def scan(client, *, filename="bill.png", content_type="image/png"):
    return client.post(
        "/receipts/scan",
        files={"image": (filename, PNG, content_type)},
        headers=HEADERS,
    )


def route_records(caplog):
    return [record for record in caplog.records if record.name == ROUTE_LOGGER]


class TestABlankCountSurvivesTheRoute:
    """Half one, at the tier the 5/10 was measured on."""

    def test_the_bill_is_not_refused(self, monkeypatch):
        response = scan(client_reading(READING_WITH_A_BLANK_COUNT, monkeypatch))
        assert response.status_code == 200

    def test_the_person_is_not_told_to_reshoot_a_readable_bill(self, monkeypatch):
        body = scan(client_reading(READING_WITH_A_BLANK_COUNT, monkeypatch)).json()
        assert body.get("code") != "receipt_unreadable"

    def test_the_blank_line_reads_as_one(self, monkeypatch):
        body = scan(client_reading(READING_WITH_A_BLANK_COUNT, monkeypatch)).json()
        assert [item["quantity"] for item in body["items"]] == [1, 1, 4]

    def test_the_money_is_what_the_paper_prints(self, monkeypatch):
        """The blank changed a count, so it must not have changed an amount."""

        body = scan(client_reading(READING_WITH_A_BLANK_COUNT, monkeypatch)).json()
        assert body["total_vnd"] == 130000
        assert body["items_total_vnd"] == 130000
        assert body["totals_agree"] is True


class TestARefusalWritesItsCodeDown:
    """Half two: the catch-all branch, which is where the seven codes land."""

    def test_the_catch_all_still_refuses_an_unreadable_count(self, monkeypatch):
        client = client_reading(READING_WITH_AN_UNREADABLE_COUNT, monkeypatch)
        response = scan(client)
        assert response.status_code == 422
        assert response.json()["code"] == "receipt_unreadable"

    def test_the_domain_code_reaches_the_log(self, monkeypatch, caplog):
        client = client_reading(READING_WITH_AN_UNREADABLE_COUNT, monkeypatch)
        with caplog.at_level(logging.INFO, logger=ROUTE_LOGGER):
            scan(client)
        assert route_records(caplog), (
            f"no record from {ROUTE_LOGGER} reached caplog: the refusal that "
            "the wire reports as a generic receipt_unreadable left no cause "
            "behind, which is the state rd-be-22 was filed about"
        )
        assert "INVALID_QUANTITY" in caplog.text

    def test_a_named_branch_writes_its_code_down_too(self, monkeypatch, caplog):
        """415 is distinguishable on the wire but was just as anonymous in the log."""

        client = client_reading(READING_WITH_A_BLANK_COUNT, monkeypatch)
        with caplog.at_level(logging.INFO, logger=ROUTE_LOGGER):
            response = scan(client, filename="bill.gif", content_type="image/gif")
        assert response.status_code == 415
        assert "UNSUPPORTED_IMAGE_TYPE" in caplog.text


class TestTheBillItselfNeverReachesTheLog:
    """A photograph of a bill is private data, and so is its transcription."""

    def test_the_code_is_logged_and_the_reading_is_not(self, monkeypatch, caplog):
        client = client_reading(READING_WITH_AN_UNREADABLE_COUNT, monkeypatch)
        with caplog.at_level(logging.DEBUG):
            scan(client)

        # Positive first, on purpose: a dead channel makes every "not in"
        # assertion below vacuously true, so this is what gives them meaning.
        assert "INVALID_QUANTITY" in caplog.text

        for secret in ("Cơm tấm sườn bì chả", "Trà đá", "vài", "85.000", "65.000"):
            assert secret not in caplog.text, (
                f"the transcription leaked into the log: {secret!r}"
            )


@pytest.mark.parametrize(
    "blank",
    ["", "   ", "\t"],
    ids=["empty", "spaces", "tab"],
)
def test_every_blank_shape_survives_the_route(blank, monkeypatch):
    """The domain accepts three shapes of "no count printed"; so must the route."""

    reading = {
        "document_type": "receipt",
        "items": [{"name": "Trà đá", "quantity_text": blank, "line_total_text": "20.000"}],
        "total_text": "20.000",
        "confidence": 0.95,
    }
    response = scan(client_reading(reading, monkeypatch))
    assert response.status_code == 200
    assert response.json()["items"][0]["quantity"] == 1
