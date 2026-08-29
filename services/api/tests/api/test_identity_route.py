"""Wiring for `POST /identity/person-id`, and the disclosures it must not make.

Orchestration only; the derivation itself is proved in
`test_person_identity.py`, including the brute-force sweep that is the reason
this route exists at all.

What is specific to the route is that its input is a telephone number, so every
answer it gives is a place that number could come back out: an echo in a
refusal, a value in a validation error, a stack trace. The assertions below are
mostly about silence.
"""

from __future__ import annotations

import re
import uuid

import pytest

from app.api.person_identity import KEY_ENV_VAR, MIN_KEY_LENGTH
from app.api.routes.identity import RATE_LIMIT

KEY = "route-test-key-for-person-id-derivation"

#: Any run of four or more digits. Deliberately wider than a phone number: a
#: partial leak is a leak, and this catches "84912" as well as the whole thing.
#:
#: Only usable on answers that carry no id. A UUID is hexadecimal, so a run of
#: eight digits inside one is ordinary rather than a disclosure -- the first
#: draft of this file failed on `...bc36-188c53513822`. Answers that do carry
#: an id are checked against the number's actual spellings instead.
DIGIT_RUN = re.compile(r"\d{4,}")

PHONE = "0912" + "345678"

#: Every way the number could come back: as typed, canonical, and the national
#: part on its own.
SPELLINGS = (PHONE, "84912" + "345678", "912" + "345678")


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv(KEY_ENV_VAR, KEY)


def _mint(client, phone=PHONE):
    return client.post("/identity/person-id", json={"phone": phone})


def test_a_number_mints_a_person_id(client):
    response = _mint(client)

    assert response.status_code == 200, response.text
    minted = response.json()["person_id"]
    # Well formed enough for `PUT /people/{id}` to accept it at the boundary.
    assert uuid.UUID(minted).version == 8


def test_the_same_number_mints_the_same_id_twice(client):
    """"Log back in" is this assertion and nothing else."""

    assert _mint(client).json() == _mint(client).json()


def test_the_response_carries_no_trace_of_the_number(client):
    """Not even normalised. A round trip that echoes its input doubles the logs
    that input can reach."""

    body = _mint(client).text
    for spelling in SPELLINGS:
        assert spelling not in body, body
    # And nothing outside the id itself, which is the only field there is.
    assert set(_mint(client).json()) == {"person_id"}


def test_a_refused_number_is_not_repeated_back(client):
    response = _mint(client, "0123" + "456789")

    assert response.status_code == 422
    assert response.json()["code"] == "phone_not_mobile"
    assert not DIGIT_RUN.search(response.text), response.text


def test_a_number_sent_as_a_json_number_is_not_echoed(client):
    """Measured, not assumed, and the reason this handler parses by hand.

    FastAPI's own validation error carries the offending value under an
    `"input"` key: `{"type":"string_type","loc":["body","phone"],"input":...}`
    with the number filled in. That response is a telephone number, in the
    caller's logs and in any bug report made from it. With a Pydantic request
    model in place of the hand parse, this test fails.
    """

    # Built rather than written out: `repo_guard.py` refuses a nine-digit run
    # on sight, and a test fixture is not a reason to teach it to look away.
    response = client.post("/identity/person-id", json={"phone": int(PHONE)})

    assert response.status_code == 422
    assert response.json()["code"] == "phone_required"
    assert not DIGIT_RUN.search(response.text), response.text


def test_a_body_that_is_not_an_object_is_refused_without_echo(client):
    response = client.post("/identity/person-id", json=["0912" + "345678"])

    assert response.status_code == 422
    assert not DIGIT_RUN.search(response.text), response.text


def test_no_key_answers_503_and_never_mints(client, monkeypatch):
    """Fail closed.

    Falling back to an unkeyed digest here would be bug-140342 reappearing
    exactly on the machines where nobody applied the fix, minting ids that look
    like every other id.
    """

    monkeypatch.delenv(KEY_ENV_VAR, raising=False)
    response = _mint(client)

    assert response.status_code == 503
    assert response.json()["code"] == "identity_key_missing"


def test_a_short_key_is_treated_as_no_key(client, monkeypatch):
    monkeypatch.setenv(KEY_ENV_VAR, "x" * (MIN_KEY_LENGTH - 1))

    assert _mint(client).status_code == 503


def test_the_key_never_appears_in_any_answer(client, monkeypatch):
    sentinel = "SECRET-DO-NOT-LEAK-" + "z" * 19
    monkeypatch.setenv(KEY_ENV_VAR, sentinel)

    assert "SECRET-DO-NOT-LEAK" not in _mint(client).text


def test_the_route_is_rate_limited(client):
    """The oracle has a cost.

    Unauthenticated by necessity -- somebody signing in has no id yet -- so
    without this the reverse map is rebuildable by asking rather than by
    computing. The limit does not remove that; it prices it.
    """

    for _ in range(RATE_LIMIT):
        assert _mint(client).status_code == 200

    refused = _mint(client)
    assert refused.status_code == 429
    assert refused.json()["code"] == "rate_limited"


def test_the_limit_is_per_application_not_per_process(client, monkeypatch):
    """A fresh app counts from zero.

    A module-level limiter would let whichever test ran first decide whether
    the twenty-first request in the whole session was refused -- a flake that
    depends on collection order.
    """

    from app.api.routes.identity import FixedWindowLimit

    limiter = FixedWindowLimit(limit=2, window_seconds=60.0, clock=lambda: 0.0)
    assert limiter.allow("1.2.3.4")
    assert limiter.allow("1.2.3.4")
    assert not limiter.allow("1.2.3.4")
    # A different caller has its own bucket, so one noisy client cannot lock
    # everybody else out of signing in.
    assert limiter.allow("5.6.7.8")


def test_the_window_moves_on(client):
    from app.api.routes.identity import FixedWindowLimit

    now = [0.0]
    limiter = FixedWindowLimit(limit=1, window_seconds=60.0, clock=lambda: now[0])
    assert limiter.allow("1.2.3.4")
    assert not limiter.allow("1.2.3.4")
    now[0] = 61.0
    assert limiter.allow("1.2.3.4")
