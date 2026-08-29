"""How much of the project's model quota one identity may spend per minute.

`POST /places/search` calls Gemini on every request, and until rd-be-13 it did
so for anyone who could reach the port. Requiring an actor closes the anonymous
half of that, but only half: `X-Actor-ID` is asserted by a trusted gateway that
this slice does not have yet (see `app/api/deps.py`), so today a header is a
claim rather than a credential. A gate that stops the anonymous caller and lets
the header-forging one through unmetered has moved the cost, not capped it.

Hence a window, and hence it is counted **per actor**. A single global counter
would be simpler and would be an outage waiting to happen: one person holding
down refresh would take search away from everybody, which is the exact failure
this module exists to prevent, merely caused by us instead of by them.

What this is not
----------------
Per-process, in memory. Two API replicas mean two windows and therefore twice
the ceiling, and a restart forgives everyone. That is honest for a single-box
demo and would be wrong to describe as a quota: the real one belongs in front
of the app, or in shared storage, and neither exists in this slice. The number
here is a blast-radius cap, not an accounting system.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from uuid import UUID

from app.api.errors import ApiProblem

__all__ = [
    "SEARCH_LIMIT_PER_WINDOW",
    "SEARCH_WINDOW_SECONDS",
    "FixedWindowLimiter",
    "build_search_limiter",
]

SEARCH_WINDOW_SECONDS = 60

# A person typing sentences into a search box does not reach twelve in a
# minute; a shell loop reaches it in under a second. Raising this is a decision
# about how much of a shared, paid quota one unverified header may spend.
SEARCH_LIMIT_PER_WINDOW = 12

# Below this many tracked identities the map is not worth walking. Above it,
# the sweep threshold doubles from whatever survived, so the O(n) walk happens
# once per doubling rather than once per request -- a sweep on every call would
# hand an attacker a cheaper way to burn CPU than the model call we are capping.
_MIN_SWEEP_AT = 1024


class FixedWindowLimiter:
    """Fixed window per key, with the two properties that make it survivable.

    A refusal does **not** move the window that refused it. Sliding `opened_at`
    to now on a 429 turns a one-minute cap into an indefinite ban: most clients
    retry on 429, each retry pushes the window out ahead of itself, and a burst
    that should have cost sixty seconds costs as long as the retry loop runs.

    Note how narrow that claim is, because the obvious wider one is false.
    *Counting* a refusal is harmless: the count is reset when the window rolls,
    and the roll is decided by `opened_at`, which a refusal leaves alone. Only
    the timestamp matters. This docstring said "counting" first, and a mutant
    that incremented on refusal passed the entire suite.

    Expired keys are dropped. The key is caller-supplied identity, so a map
    that is only ever written to is a way to exhaust the process politely, one
    fresh UUID at a time.
    """

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        # key -> (window opened at, calls admitted in that window)
        self._windows: dict[UUID, tuple[float, int]] = {}
        # Sync routes run in a threadpool, so this is genuine shared state and
        # `count + 1` is not atomic across threads.
        self._lock = threading.Lock()
        self._sweep_at = _MIN_SWEEP_AT
        self._last_sweep = self._clock()

    def check(self, key: UUID) -> None:
        """Admit one call, or raise 429 having spent nothing."""

        now = self._clock()
        with self._lock:
            opened_at, used = self._windows.get(key, (now, 0))
            if now - opened_at >= self.window_seconds:
                opened_at, used = now, 0

            if used >= self.limit:
                # `opened_at` written back unchanged, which is the whole point:
                # `now` here would be the indefinite ban. See the class docstring.
                self._windows[key] = (opened_at, used)
                raise ApiProblem(
                    429,
                    "search_rate_limited",
                    f"Too many searches; at most {self.limit} per "
                    f"{self.window_seconds} seconds.",
                )

            self._windows[key] = (opened_at, used + 1)
            # Two triggers, because size alone is not enough. Size handles the
            # map growing under load; the clock handles the burst that stops --
            # 5,000 identities that went quiet are all expired and all still
            # resident until something makes us look, and under a size-only
            # rule that something is the map doubling, which quiet never does.
            if (
                len(self._windows) >= self._sweep_at
                or now - self._last_sweep >= self.window_seconds
            ):
                self._sweep(now)

    def tracked(self) -> int:
        """How many identities are currently held. For tests and for operators."""

        with self._lock:
            return len(self._windows)

    def _sweep(self, now: float) -> None:
        """Drop windows that have rolled. Caller holds the lock."""

        self._windows = {
            key: entry
            for key, entry in self._windows.items()
            if now - entry[0] < self.window_seconds
        }
        self._sweep_at = max(_MIN_SWEEP_AT, len(self._windows) * 2)
        self._last_sweep = now


def build_search_limiter() -> FixedWindowLimiter:
    """The one the app ships with, built once per application.

    Deliberately not a module-level singleton. The window has to survive
    *between requests*, which a per-request object would not -- but a
    process-wide one survives between *tests* too, and a counter shared by
    every test in a session is a suite whose colour depends on execution
    order. `create_app` owns one; production builds the app once, so
    production still has exactly one.
    """

    return FixedWindowLimiter(
        limit=SEARCH_LIMIT_PER_WINDOW, window_seconds=SEARCH_WINDOW_SECONDS
    )
