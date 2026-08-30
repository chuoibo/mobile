"""F37 counts admissions per minute, not requests that have finished.

All callers start together and every admitted backend call remains in flight
until the full legitimate allowance has arrived.  A limiter moved below the
service still produces thirty 200s and five 429s, but it pays for thirty-five
model calls; the backend count is therefore the load-bearing assertion.
"""

from __future__ import annotations

import threading
from collections import Counter

import anyio

from app.api.deps import get_reeler, get_repository
from app.api.main import create_app
from app.api.search_rate_limit import REEL_LIMIT_PER_WINDOW

from .conftest import ASGITestClient
from .test_trip_reel import (
    CONTEXT_ID,
    HEADERS,
    LOW_HEART_ID,
    NOW,
    OUTING_ID,
    StubReelRepository,
)

FLEET = REEL_LIMIT_PER_WINDOW + 5
PATH = f"/contexts/{CONTEXT_ID}/albums/{OUTING_ID}/reel"


class OverlappingReeler:
    """Hold every admitted call open until the real ceiling has arrived."""

    def __init__(self) -> None:
        self.calls = 0
        self._lock = threading.Lock()
        self._admitted = threading.Event()

    def __call__(self, trip, memories):
        del trip, memories
        with self._lock:
            self.calls += 1
            if self.calls >= REEL_LIMIT_PER_WINDOW:
                self._admitted.set()
        if not self._admitted.wait(timeout=10):
            raise AssertionError("the admitted fleet never reached the ceiling")
        return {
            "title": "Những điều còn ở lại",
            "picks": [
                {
                    "memory_id": str(LOW_HEART_ID),
                    "note": "Một buổi sáng cả nhóm vẫn còn nhắc",
                }
            ],
        }


def test_the_reel_ceiling_counts_admissions_before_requests_finish(monkeypatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    backend = OverlappingReeler()
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: StubReelRepository()
    app.dependency_overrides[get_reeler] = lambda: backend
    client = ASGITestClient(app)

    start = threading.Barrier(FLEET, timeout=10)
    statuses: list[int] = []
    errors: list[BaseException] = []
    result_lock = threading.Lock()

    def request_reel() -> None:
        try:
            start.wait()
            response = client.get(PATH, headers=HEADERS)
            with result_lock:
                statuses.append(response.status_code)
        except BaseException as error:  # noqa: BLE001 - report every thread
            with result_lock:
                errors.append(error)

    threads = [threading.Thread(target=request_reel) for _ in range(FLEET)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    alive = [thread.name for thread in threads if thread.is_alive()]
    assert alive == [], f"concurrent reel requests deadlocked: {alive}"
    assert errors == [], f"concurrent reel requests raised: {errors[:3]}"
    assert Counter(statuses) == {
        200: REEL_LIMIT_PER_WINDOW,
        429: FLEET - REEL_LIMIT_PER_WINDOW,
    }
    assert backend.calls == REEL_LIMIT_PER_WINDOW
