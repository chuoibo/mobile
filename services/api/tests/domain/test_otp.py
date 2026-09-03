"""The one-time-code rules, checked as a table of instants.

Pure functions: no clock, no store. The service owns persistence and HTTP; this
file owns the boundaries -- the fifth wrong guess burns, the sixth on the same
challenge is "not there", a spent code is refused before it is compared, and a
resend inside the cooldown is told how long to wait.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.otp import DEFAULT_LIMITS, generate_code, plan_request, plan_verify

NOW = datetime(2030, 10, 17, 9, 0, tzinfo=UTC)


def _challenge(*, attempts=0, consumed=False, expired=False):
    return {
        "expires_at": NOW - timedelta(seconds=1)
        if expired
        else NOW + timedelta(minutes=4),
        "attempts": attempts,
        "consumed_at": NOW - timedelta(seconds=30) if consumed else None,
    }


def test_generate_code_is_six_zero_padded_digits():
    assert generate_code(lambda n: 7) == "000007"
    assert generate_code(lambda n: 999_999) == "999999"
    assert len(generate_code(lambda n: n - 1)) == 6


def test_a_fresh_phone_may_request():
    assert plan_request([], NOW) == {
        "allowed": True,
        "reason": "ok",
        "retry_after_seconds": 0,
    }


def test_a_resend_inside_the_cooldown_is_told_how_long_to_wait():
    plan = plan_request([{"created_at": NOW - timedelta(seconds=20)}], NOW)
    assert plan["allowed"] is False
    assert plan["reason"] == "resend_too_soon"
    assert plan["retry_after_seconds"] == DEFAULT_LIMITS["resend_cooldown_seconds"] - 20


def test_the_sixth_challenge_in_a_window_is_refused_even_after_the_cooldown():
    recent = [
        {"created_at": NOW - timedelta(minutes=2 * i + 2)}
        for i in range(DEFAULT_LIMITS["max_challenges_per_window"])
    ]
    plan = plan_request(recent, NOW)
    assert plan["allowed"] is False
    assert plan["reason"] == "too_many_requests"
    assert plan["retry_after_seconds"] > 0


def test_challenges_outside_the_window_do_not_count():
    old = [{"created_at": NOW - timedelta(hours=2)} for _ in range(10)]
    assert plan_request(old, NOW)["allowed"] is True


@pytest.mark.parametrize(
    ("challenge", "outcome"),
    [
        (None, "not_found"),
        (_challenge(consumed=True), "consumed"),
        (_challenge(expired=True), "expired"),
        (_challenge(attempts=DEFAULT_LIMITS["max_attempts"]), "burned_already"),
    ],
)
def test_dead_challenges_are_refused_before_the_code_is_looked_at(challenge, outcome):
    # `code_matches=True` on purpose: a right guess on a dead challenge is nothing.
    assert plan_verify(challenge, NOW, True)["outcome"] == outcome


def test_a_right_code_on_a_live_challenge_is_ok_and_counts_the_attempt():
    plan = plan_verify(_challenge(attempts=2), NOW, True)
    assert plan == {"outcome": "ok", "attempts": 3}


def test_wrong_guesses_count_down_and_the_last_one_burns():
    limit = DEFAULT_LIMITS["max_attempts"]
    fourth = plan_verify(_challenge(attempts=limit - 2), NOW, False)
    assert fourth == {
        "outcome": "wrong_code",
        "attempts": limit - 1,
        "attempts_left": 1,
    }
    fifth = plan_verify(_challenge(attempts=limit - 1), NOW, False)
    assert fifth == {"outcome": "burned", "attempts": limit, "attempts_left": 0}
    # And the same challenge afterwards is simply not there, right code or not.
    assert (
        plan_verify(_challenge(attempts=limit), NOW, True)["outcome"]
        == "burned_already"
    )
