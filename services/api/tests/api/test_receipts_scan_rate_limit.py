"""How much of the project's vision quota one identity may spend on scans.

``POST /receipts/scan`` hands a photograph to Gemini on every request. Until
this file there was no ceiling on it at all: ``POST /places/search`` had been
metered since rd-be-13, and the more expensive route beside it had not. A
scan is a vision call, so a loop against this endpoint spends the shared key
faster than a loop against search does -- and the key is the one the demo
runs on.

The gate is per actor, for the reason given in ``app/api/search_rate_limit.py``:
a single global counter turns one person holding down the shutter into an
outage for everybody, which is the failure this exists to prevent.

What this does NOT prove: that the ceiling is the right number, or that it
survives a second replica. The window is per process and in memory, so two
API replicas mean twice the ceiling and a restart forgives everyone. That is
a blast-radius cap for a single-box demo, not a quota.
"""

from __future__ import annotations

import uuid

import anyio
import pytest

from app.api.deps import get_receipt_reader
from app.api.main import create_app
from app.api.routes.receipts import get_receipt_scan_limiter
from app.api.search_rate_limit import (
    RECEIPT_SCAN_LIMIT_PER_WINDOW,
    FixedWindowLimiter,
)

from .conftest import ASGITestClient
from .helpers import ADVANCER_ID, png_bytes

PNG = png_bytes()
HEADERS = {"X-Actor-ID": str(ADVANCER_ID)}

READING = {
    "document_type": "receipt",
    "items": [{"name": "Pepsi", "quantity_text": "2", "line_total_text": "28.000"}],
    "total_text": "28.000",
    "confidence": 0.92,
}


class FakeReader:
    """Records every call, so a refusal that still paid can be seen."""

    def __init__(self) -> None:
        self.calls: list[tuple[bytes, str]] = []

    def read(self, image: bytes, mime_type: str) -> dict:
        self.calls.append((image, mime_type))
        return READING


class Clock:
    """A hand-wound clock, so the window is tested rather than waited out."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def reader():
    return FakeReader()


@pytest.fixture
def client(monkeypatch, reader):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    app = create_app()
    app.dependency_overrides[get_receipt_reader] = lambda: reader
    return ASGITestClient(app)


def scan(client, headers=None):
    return client.post(
        "/receipts/scan",
        files={"image": ("bill.png", PNG, "image/png")},
        headers=HEADERS if headers is None else headers,
    )


def other_actor():
    return {"X-Actor-ID": str(uuid.uuid4())}


@pytest.fixture
def metered(client):
    """A three-per-window ceiling, so a burst is three calls and not twelve."""

    clock = Clock()
    limiter = FixedWindowLimiter(
        limit=3,
        window_seconds=60,
        clock=clock,
        code="scan_rate_limited",
        message="Too many scans.",
    )
    client.app.dependency_overrides[get_receipt_scan_limiter] = lambda: limiter
    return clock


def test_a_burst_of_scans_from_one_person_is_cut_off(client, metered):
    for _ in range(3):
        assert scan(client).status_code == 200

    assert scan(client).status_code == 429


def test_the_refused_scans_are_the_ones_that_never_reach_the_model(
    client, reader, metered
):
    """A 429 raised after the model ran has spent exactly what it refused.

    This is the assertion that makes the gate worth having: the point is not
    the status code, it is that the vision call did not happen.
    """

    for _ in range(6):
        scan(client)

    assert len(reader.calls) == 3


def test_a_refused_scan_says_scans_and_not_searches(client, metered):
    """The refusal names the thing that was refused.

    The limiter this reuses was written for search and had its code and
    sentence hardcoded. Reusing it without parameterising them would answer a
    receipt scan with ``search_rate_limited`` and "Too many searches", which
    tells the person -- and the client branching on the code -- about a
    feature they were not using.
    """

    for _ in range(3):
        scan(client)
    body = scan(client).json()

    assert body["code"] == "scan_rate_limited"
    assert "search" not in body["detail"].lower()


def test_the_cut_off_is_per_person_not_a_switch_that_stops_scanning(client, metered):
    for _ in range(3):
        assert scan(client).status_code == 200

    assert scan(client, headers=other_actor()).status_code == 200
    assert scan(client).status_code == 429


def test_the_block_expires_so_a_person_is_not_locked_out_for_good(client, metered):
    for _ in range(3):
        scan(client)
    assert scan(client).status_code == 429

    metered.advance(61)

    assert scan(client).status_code == 200


def test_retrying_against_the_wall_does_not_push_the_wall_further_out(client, metered):
    """A refusal must not slide the window that refused it.

    Most clients retry on 429. If each refusal moved ``opened_at`` to now, a
    burst that should cost sixty seconds would cost as long as the retry loop
    runs. The clock has to advance *during* the retries or a broken limiter
    passes: against a frozen clock, sliding the window is invisible.
    """

    for _ in range(3):
        scan(client)

    for _ in range(10):
        metered.advance(5)
        assert scan(client).status_code == 429

    metered.advance(11)

    assert scan(client).status_code == 200


def test_the_shipped_route_meters_without_any_test_installing_a_limiter(client, reader):
    """Every other case here installs its own limiter, so every other case
    stays green if the app ships with none. This one spends the real ceiling.
    """

    codes = [scan(client).status_code for _ in range(RECEIPT_SCAN_LIMIT_PER_WINDOW + 1)]

    assert codes == [200] * RECEIPT_SCAN_LIMIT_PER_WINDOW + [429]
    assert len(reader.calls) == RECEIPT_SCAN_LIMIT_PER_WINDOW


def test_each_application_carries_its_own_scan_window(client):
    """A module-level limiter would make a suite's colour depend on its order."""

    other = create_app()

    assert client.app.state.receipt_scan_limiter is not other.state.receipt_scan_limiter
