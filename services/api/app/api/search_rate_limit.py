"""How much of the project's model quota one identity may spend per minute.

Four routes spend that quota and all are metered here: `POST /places/search`,
`POST /receipts/scan`, `POST /screenshots/scan`, and the F24 chat-expense draft
route. The receipt scan arrived
second and unmetered, which is the
worst of them to leave open -- it ships a photograph to a vision model, so
a loop against it drains the shared key faster than a loop against search.
The file is still named for search because that is the route it was written
for; the ceilings and the refusal wording are per caller, set at construction.

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
    "CHAT_EXPENSE_LIMIT_PER_WINDOW",
    "CHAT_EXPENSE_WINDOW_SECONDS",
    "COMPANION_TURN_LIMIT_PER_WINDOW",
    "COMPANION_TURN_WINDOW_SECONDS",
    "CONTEXTUAL_SUGGESTION_LIMIT_PER_WINDOW",
    "CONTEXTUAL_SUGGESTION_WINDOW_SECONDS",
    "FACE_DETECTION_LIMIT_PER_WINDOW",
    "FACE_DETECTION_WINDOW_SECONDS",
    "RECEIPT_SCAN_LIMIT_PER_WINDOW",
    "RECEIPT_SCAN_WINDOW_SECONDS",
    "SEARCH_LIMIT_PER_WINDOW",
    "SEARCH_WINDOW_SECONDS",
    "SCREENSHOT_SCAN_LIMIT_PER_WINDOW",
    "SCREENSHOT_SCAN_WINDOW_SECONDS",
    "SUGGESTION_LIMIT_PER_WINDOW",
    "SUGGESTION_WINDOW_SECONDS",
    "FixedWindowLimiter",
    "build_chat_expense_limiter",
    "build_companion_turn_limiter",
    "build_contextual_suggestion_limiter",
    "build_face_detection_limiter",
    "build_receipt_scan_limiter",
    "build_search_limiter",
    "build_screenshot_scan_limiter",
    "build_suggestion_limiter",
]

SEARCH_WINDOW_SECONDS = 60

# A person typing sentences into a search box does not reach twelve in a
# minute; a shell loop reaches it in under a second. Raising this is a decision
# about how much of a shared, paid quota one unverified header may spend.
SEARCH_LIMIT_PER_WINDOW = 12

RECEIPT_SCAN_WINDOW_SECONDS = 60

# Set by the asymmetry, not by what looks tidy. Against the thing this exists
# to stop -- a loop -- the choice barely matters: a loop issues hundreds of
# requests a second, so any ceiling in the tens caps the minute's spend at a
# small constant, and 10 versus 30 is the difference between two amounts that
# are both negligible. Against a real person the choice matters a lot. Someone
# re-shooting a bill that keeps coming out blurred, then a second bill, with
# the client retrying underneath them, reaches low double digits in a minute;
# refused at that point they watch the feature fail with nothing they can do.
#
# So the ceiling sits well above any plausible human burst and far below loop
# scale. This started at 10, chosen by intuition, and the suite disproved it:
# `tests/qa/rd-qa-38` drives one actor past 10 scans in a single window doing
# nothing unreasonable. That is evidence about real bursts, not a test being
# awkward, and the number moved because of it.
RECEIPT_SCAN_LIMIT_PER_WINDOW = 30

# F24 spends one text-model call per attempt. It gets the same human-burst
# allowance as receipt scanning, but a different counter: reading a bill must
# not consume the caller's ability to read a message, or vice versa.
CHAT_EXPENSE_WINDOW_SECONDS = RECEIPT_SCAN_WINDOW_SECONDS
CHAT_EXPENSE_LIMIT_PER_WINDOW = RECEIPT_SCAN_LIMIT_PER_WINDOW

# A screenshot spends the same kind of vision call as a receipt, but its own
# counter prevents one feature's retry loop from disabling its neighbour.
SCREENSHOT_SCAN_WINDOW_SECONDS = RECEIPT_SCAN_WINDOW_SECONDS
SCREENSHOT_SCAN_LIMIT_PER_WINDOW = RECEIPT_SCAN_LIMIT_PER_WINDOW

# `POST /contexts/{id}/ai-turn` spends one text-model call whenever the
# conversation cadence lets the companion speak. That cadence is not a ceiling:
# `plan_turn` refuses while the companion spoke last, and the caller lifts the
# refusal by posting one more message, so an unmetered loop costs two cheap
# requests per model call rather than one. Same human-burst allowance as the
# routes above, and its own counter for the same reason.
COMPANION_TURN_WINDOW_SECONDS = RECEIPT_SCAN_WINDOW_SECONDS
COMPANION_TURN_LIMIT_PER_WINDOW = RECEIPT_SCAN_LIMIT_PER_WINDOW

# `GET /contexts/{id}/suggestion` is the worst of the set: no cache, no
# cadence, one model call on every request, and a GET, so a client that polls
# spends the key without anybody meaning to. A home screen that remounts and
# refreshes reaches low double digits in a minute, which is why this is not
# tighter than its neighbours despite being the cheapest to trigger.
SUGGESTION_WINDOW_SECONDS = RECEIPT_SCAN_WINDOW_SECONDS
SUGGESTION_LIMIT_PER_WINDOW = RECEIPT_SCAN_LIMIT_PER_WINDOW

# `GET /contexts/{id}/contextual-suggestion` is the one above with a worse
# cache story. F32 at least reads history, which changes slowly; F33 reads the
# group's last few messages, so no cache coarser than one group's live
# conversation is even correct -- one keyed on anything else would serve one
# group's evening to another. That leaves one model call per GET, triggered by
# opening the chat screen, which a client that remounts issues without anybody
# deciding to. Its own counter, so a busy chat cannot spend the home screen's
# allowance and leave the group told it has no suggestion.
CONTEXTUAL_SUGGESTION_WINDOW_SECONDS = RECEIPT_SCAN_WINDOW_SECONDS
CONTEXTUAL_SUGGESTION_LIMIT_PER_WINDOW = RECEIPT_SCAN_LIMIT_PER_WINDOW

# F22 face detection. The ninth model door, and the first one that spends no
# paid quota at all: the cascade runs in this process, so a loop against it
# costs CPU and resident memory rather than somebody else's API key.
#
# That difference argues for a ceiling, not against one. Every other window
# here protects a budget that a second replica would also protect; this one
# protects the event loop of the box it runs on. `detectMultiScale` over a
# multi-megapixel photograph is tens to hundreds of milliseconds of CPU held by
# a threadpool worker, and the request that starts it has already passed
# membership -- so the cheapest denial of service against this product is a
# member looping this route until the API stops answering anything, including
# the routes that move money.
#
# Same number as its neighbours, chosen the same way: far above what a person
# re-tapping "find faces" on a photo that came out badly reaches in a minute,
# far below loop scale.
FACE_DETECTION_WINDOW_SECONDS = RECEIPT_SCAN_WINDOW_SECONDS
FACE_DETECTION_LIMIT_PER_WINDOW = RECEIPT_SCAN_LIMIT_PER_WINDOW

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
        code: str,
        message: str,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        # Required, not defaulted to the search wording. This class had both
        # hardcoded while it had one caller; the second caller would then have
        # answered a refused receipt scan with `search_rate_limited` and "Too
        # many searches", naming a feature the person was not using. A default
        # here is that bug with a place to hide.
        self.code = code
        self.message = message
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
                raise ApiProblem(429, self.code, self.message)

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
        limit=SEARCH_LIMIT_PER_WINDOW,
        window_seconds=SEARCH_WINDOW_SECONDS,
        code="search_rate_limited",
        message=(
            f"Too many searches; at most {SEARCH_LIMIT_PER_WINDOW} per "
            f"{SEARCH_WINDOW_SECONDS} seconds."
        ),
    )


def build_receipt_scan_limiter() -> FixedWindowLimiter:
    """The scan ceiling the app ships with, built once per application.

    Same lifetime argument as `build_search_limiter`, and a separate object on
    purpose: sharing one window between the two routes would let a burst of
    searches eat the scan budget of the person who never searched.
    """

    return FixedWindowLimiter(
        limit=RECEIPT_SCAN_LIMIT_PER_WINDOW,
        window_seconds=RECEIPT_SCAN_WINDOW_SECONDS,
        code="scan_rate_limited",
        message=(
            f"Quá nhiều lượt đọc bill; tối đa {RECEIPT_SCAN_LIMIT_PER_WINDOW} "
            f"lượt mỗi {RECEIPT_SCAN_WINDOW_SECONDS} giây. Thử lại sau ít phút."
        ),
    )


def build_chat_expense_limiter() -> FixedWindowLimiter:
    """The per-actor F24 ceiling, owned by one application instance."""

    return FixedWindowLimiter(
        limit=CHAT_EXPENSE_LIMIT_PER_WINDOW,
        window_seconds=CHAT_EXPENSE_WINDOW_SECONDS,
        code="chat_expense_rate_limited",
        message=(
            "Quá nhiều lượt đọc khoản chi từ tin nhắn; tối đa "
            f"{CHAT_EXPENSE_LIMIT_PER_WINDOW} lượt mỗi "
            f"{CHAT_EXPENSE_WINDOW_SECONDS} giây. Thử lại sau ít phút."
        ),
    )


def build_companion_turn_limiter() -> FixedWindowLimiter:
    """The per-actor ceiling on the group companion, owned by one application."""

    return FixedWindowLimiter(
        limit=COMPANION_TURN_LIMIT_PER_WINDOW,
        window_seconds=COMPANION_TURN_WINDOW_SECONDS,
        code="companion_turn_rate_limited",
        message=(
            "Quá nhiều lượt hỏi trợ lý nhóm; tối đa "
            f"{COMPANION_TURN_LIMIT_PER_WINDOW} lượt mỗi "
            f"{COMPANION_TURN_WINDOW_SECONDS} giây. Thử lại sau ít phút."
        ),
    )


def build_suggestion_limiter() -> FixedWindowLimiter:
    """The per-actor ceiling on the proactive card, separate from the turn.

    Separate because the two are triggered by different things: a turn is
    somebody typing, a card is a screen opening. Sharing a window would let a
    conversation spend the home screen's allowance, so the person who chatted
    the most is the one told the group has no suggestion.
    """

    return FixedWindowLimiter(
        limit=SUGGESTION_LIMIT_PER_WINDOW,
        window_seconds=SUGGESTION_WINDOW_SECONDS,
        code="suggestion_rate_limited",
        message=(
            "Quá nhiều lượt xin gợi ý; tối đa "
            f"{SUGGESTION_LIMIT_PER_WINDOW} lượt mỗi "
            f"{SUGGESTION_WINDOW_SECONDS} giây. Thử lại sau ít phút."
        ),
    )


def build_contextual_suggestion_limiter() -> FixedWindowLimiter:
    """The per-actor ceiling on the F33 card, separate from the F32 one.

    Two cards, two windows, for the same reason the turn and the card have
    two: they are triggered by different things. Opening the chat screen must
    not spend the allowance the home screen needs, or the group that talks the
    most is the one told there is nothing to suggest.
    """

    return FixedWindowLimiter(
        limit=CONTEXTUAL_SUGGESTION_LIMIT_PER_WINDOW,
        window_seconds=CONTEXTUAL_SUGGESTION_WINDOW_SECONDS,
        code="contextual_suggestion_rate_limited",
        message=(
            "Quá nhiều lượt xin gợi ý theo cuộc trò chuyện; tối đa "
            f"{CONTEXTUAL_SUGGESTION_LIMIT_PER_WINDOW} lượt mỗi "
            f"{CONTEXTUAL_SUGGESTION_WINDOW_SECONDS} giây. Thử lại sau ít phút."
        ),
    )


def build_face_detection_limiter() -> FixedWindowLimiter:
    """The per-actor F22 ceiling, its own window like every door before it.

    Sharing the receipt-scan window would have been defensible-sounding -- both
    are "a photo goes to a model" -- and wrong for the reason the whole file
    keeps repeating: the two are triggered by different taps. Re-shooting a
    blurred bill would then consume the allowance for finding the faces in the
    photo of the table, and the person who had the most trouble scanning is the
    one told they may not tag themselves.
    """

    return FixedWindowLimiter(
        limit=FACE_DETECTION_LIMIT_PER_WINDOW,
        window_seconds=FACE_DETECTION_WINDOW_SECONDS,
        code="face_detection_rate_limited",
        message=(
            "Quá nhiều lượt tìm khuôn mặt trong ảnh; tối đa "
            f"{FACE_DETECTION_LIMIT_PER_WINDOW} lượt mỗi "
            f"{FACE_DETECTION_WINDOW_SECONDS} giây. Thử lại sau ít phút."
        ),
    )


def build_screenshot_scan_limiter() -> FixedWindowLimiter:
    """The per-actor F26 ceiling, separate from every other model route."""

    return FixedWindowLimiter(
        limit=SCREENSHOT_SCAN_LIMIT_PER_WINDOW,
        window_seconds=SCREENSHOT_SCAN_WINDOW_SECONDS,
        code="screenshot_scan_rate_limited",
        message=(
            "Quá nhiều lượt đọc ảnh chụp màn hình; tối đa "
            f"{SCREENSHOT_SCAN_LIMIT_PER_WINDOW} lượt mỗi "
            f"{SCREENSHOT_SCAN_WINDOW_SECONDS} giây. Thử lại sau ít phút."
        ),
    )
