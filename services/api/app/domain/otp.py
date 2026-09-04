"""The rules of a one-time code, with no I/O behind them.

Dict in, dict out, like the rest of `app/domain`. The service decides what to
persist and what HTTP code to answer; this module decides only what is true
about a challenge at an instant: may a new one be issued, and what does this
attempt with this code mean.

Two refusals are deliberately indistinguishable to the caller of the API --
`not_found`, `consumed`, `expired` and `burned_already` all become one 404 --
because telling a guesser that a code *was once* real is worth more to them
than to the person who simply has to ask for a new one (same reasoning as
ADR-0014's 409 becoming 404). They are distinct here so tests can see them.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

DEFAULT_LIMITS: dict[str, int] = {
    "code_ttl_seconds": 300,
    "max_attempts": 5,
    "resend_cooldown_seconds": 60,
    "max_challenges_per_window": 5,
    "window_seconds": 900,
}

CODE_LENGTH = 6


def generate_code(random_below: Callable[[int], int]) -> str:
    """Six digits, zero-padded. The caller passes `secrets.randbelow`."""
    return f"{random_below(10**CODE_LENGTH):0{CODE_LENGTH}d}"


def plan_request(
    recent: Sequence[dict], now: datetime, limits: dict[str, int] | None = None
) -> dict:
    """May a new challenge be issued for this phone right now?

    `recent` carries the challenges already issued for the same digest, each a
    dict with `created_at`. Two ceilings: a cooldown since the latest one (a
    person tapping "send again" every second is a person the gateway bills us
    for), and a count per window (a script cycling through codes for one
    number). Both answer with how long to wait, so the client can say so.
    """
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    window_start = now - timedelta(seconds=lim["window_seconds"])
    in_window = [row for row in recent if row["created_at"] > window_start]
    if in_window:
        latest = max(row["created_at"] for row in in_window)
        cooldown_left = lim["resend_cooldown_seconds"] - (now - latest).total_seconds()
        if cooldown_left > 0:
            return {
                "allowed": False,
                "reason": "resend_too_soon",
                "retry_after_seconds": math.ceil(cooldown_left),
            }
        if len(in_window) >= lim["max_challenges_per_window"]:
            oldest = min(row["created_at"] for row in in_window)
            wait = lim["window_seconds"] - (now - oldest).total_seconds()
            return {
                "allowed": False,
                "reason": "too_many_requests",
                "retry_after_seconds": max(1, math.ceil(wait)),
            }
    return {"allowed": True, "reason": "ok", "retry_after_seconds": 0}


def plan_verify(
    challenge: dict | None,
    now: datetime,
    code_matches: bool,
    limits: dict[str, int] | None = None,
) -> dict:
    """What one attempt means for one challenge.

    `challenge` carries `expires_at`, `attempts`, `consumed_at`. The outcome
    names what to persist: `attempts` is the count AFTER this attempt, and
    `ok` / `burned` both end the challenge (the service marks it consumed).
    Order matters: a spent or expired challenge is refused before the code is
    even looked at, so a right guess on a dead challenge is still nothing.
    """
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    if challenge is None:
        return {"outcome": "not_found", "attempts": 0}
    attempts = int(challenge["attempts"])
    if challenge.get("consumed_at") is not None:
        return {"outcome": "consumed", "attempts": attempts}
    if challenge["expires_at"] <= now:
        return {"outcome": "expired", "attempts": attempts}
    if attempts >= lim["max_attempts"]:
        return {"outcome": "burned_already", "attempts": attempts}
    attempts += 1
    if code_matches:
        return {"outcome": "ok", "attempts": attempts}
    if attempts >= lim["max_attempts"]:
        return {"outcome": "burned", "attempts": attempts, "attempts_left": 0}
    return {
        "outcome": "wrong_code",
        "attempts": attempts,
        "attempts_left": lim["max_attempts"] - attempts,
    }
