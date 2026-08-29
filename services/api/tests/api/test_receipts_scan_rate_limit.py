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
from app.api.errors import ApiProblem
from app.api.main import create_app
from app.api.routes.places import get_place_searcher
from app.api.routes.receipts import get_receipt_scan_limiter
from app.api.search_rate_limit import (
    RECEIPT_SCAN_LIMIT_PER_WINDOW,
    SEARCH_LIMIT_PER_WINDOW,
    FixedWindowLimiter,
    build_receipt_scan_limiter,
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


class SilentSearcher:
    """Stands in for Gemini on the neighbouring paid route."""

    def __call__(self, query: str) -> dict:
        del query
        return {
            "understood": {
                "budget_per_person_vnd": 300_000,
                "group_size": 6,
                "max_distance_km": 5,
                "categories": ["quan-an-local"],
                "traits": ["Ngoài trời"],
            },
            "results": [
                {"id": "p-tiem-nuong-xom-lao", "reason": "Đồ nướng, ngồi ngoài trời."}
            ],
        }


def test_spending_the_search_ceiling_leaves_the_scan_ceiling_whole(client, reader):
    """The two paid routes are metered apart, and this is the only case saying so.

    Every other case in this file, and every case in the search file, stays
    green if the two routes count into ONE window: scans alone still stop at
    their own ceiling, searches alone still stop at theirs, and each app still
    builds its own pair of limiters. A shared window is only visible when one
    identity uses both routes -- and then the searches quietly spend the scan
    allowance, so somebody who has photographed two bills is refused the third
    in a sentence blaming how much they have been scanning.

    Established by mutation, not by argument. Sharing one window store between
    the two limiters inside ``create_app`` -- ceilings untouched, objects still
    distinct, per-app isolation intact -- left all 1486 cases in the repository
    green. Three blunter spellings of the same bug were each caught only by an
    assertion pinning a ceiling number, which is why none of them counted.
    """

    client.app.dependency_overrides[get_place_searcher] = lambda: SilentSearcher()

    search_codes = [
        client.post("/places/search", json={"query": "quán nướng"}, headers=HEADERS)
        .status_code
        for _ in range(SEARCH_LIMIT_PER_WINDOW + 1)
    ]
    assert search_codes == [200] * SEARCH_LIMIT_PER_WINDOW + [429], (
        "the search ceiling has to be genuinely spent, or this proves nothing"
    )

    scan_codes = [scan(client).status_code for _ in range(RECEIPT_SCAN_LIMIT_PER_WINDOW)]

    assert scan_codes == [200] * RECEIPT_SCAN_LIMIT_PER_WINDOW
    assert len(reader.calls) == RECEIPT_SCAN_LIMIT_PER_WINDOW


# The burst one real person produces in one minute. Not chosen to look tidy:
# `#227` shipped 10 first and the suite disproved it -- `tests/qa/rd-qa-38`
# drives one actor past 10 scans in a single window doing nothing unreasonable,
# and the measured peak of the whole suite on the shared process-level limiter
# is 23. Twenty sits above the disproved region and below the shipped ceiling.
HUMAN_BURST_PER_MINUTE = 20

# Five, because `tests/qa/qa-tt-0005` admits any window up to 300 seconds. A
# window at that ceiling has to roll at least once inside this span, so five
# consecutive minutes is what it takes to tell a per-minute cap apart from a
# five-minute budget. Fewer minutes and the two are indistinguishable.
CONSECUTIVE_MINUTES = 5


def test_the_human_burst_gets_through_in_every_minute_not_just_the_first():
    """The ceiling has to be a rate, and no gate in the repository said so.

    `tests/qa/qa-tt-0005` bounds the two numbers **separately** -- the limit
    lands in (20, 60] and the window in [60, 300] -- and never their ratio. So
    the pair (30, 300) satisfies both bounds while being a fivefold tightening
    of the real ceiling: 30 scans per five minutes rather than per minute.
    Measured, not argued: raising `RECEIPT_SCAN_WINDOW_SECONDS` from 60 to 300
    with the limit untouched leaves the entire repository at 1527 passed, the
    same count as the clean tree. Nothing anywhere goes red.

    What that costs is the hero path. Someone photographing a blurry bill,
    re-shooting it, then starting a second bill spends their whole budget in
    the first minute and is refused for the next four -- the exact failure the
    ceiling was raised from 10 to 30 to avoid, reintroduced through the
    denominator instead of the numerator.

    Configuration is read off the shipped limiter rather than re-imported from
    the constants, so a ship wired to numbers nobody intended still fails here.
    The clock is the one thing substituted: `FixedWindowLimiter` takes one by
    construction, and a gate that waited out five real minutes would be a gate
    nobody runs. That the shipped object reads a real clock is covered above,
    by `test_the_shipped_route_meters_without_any_test_installing_a_limiter`.
    """

    shipped = build_receipt_scan_limiter()
    clock = Clock()
    probe = FixedWindowLimiter(
        limit=shipped.limit,
        window_seconds=shipped.window_seconds,
        code=shipped.code,
        message=shipped.message,
        clock=clock,
    )
    person = uuid.uuid4()

    for minute in range(1, CONSECUTIVE_MINUTES + 1):
        for attempt in range(1, HUMAN_BURST_PER_MINUTE + 1):
            try:
                probe.check(person)
            except ApiProblem as exc:  # pragma: no cover - only when red
                raise AssertionError(
                    f"scan {attempt} of minute {minute} was refused. A ceiling "
                    f"of {shipped.limit} per {shipped.window_seconds}s is "
                    f"{shipped.limit * 60 / shipped.window_seconds:.0f} scans "
                    f"per minute, below the {HUMAN_BURST_PER_MINUTE} one person "
                    "produces re-shooting a blurry bill. Both numbers are "
                    "individually inside the band qa-tt-0005 allows; it is "
                    "their ratio that is not a ceiling any more"
                ) from exc
        clock.advance(61)
