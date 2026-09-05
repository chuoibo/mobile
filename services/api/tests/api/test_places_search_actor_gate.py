"""`POST /places/search` costs money to call, so it asks who is calling (rd-be-13).

Why this file exists at all
---------------------------
Every other route in this service takes an ``Actor``. This one did not, because
it reads no aggregate and touches no ledger -- and by the structural argument
QA used at rd-qa-18 that is correct: with no repository dependency there is no
path from this handler to anybody else's data, so an open route here was never
a leak.

What it was instead is a **spend**. The handler calls a real model on every
request. Open, unauthenticated and unmetered, a `while true; do curl; done`
drains the project's Gemini quota, and the way that failure shows up is not an
alert -- it is search quietly not working for every real person at once.

So there are two gates here and they stop two different attackers:

* ``get_actor`` stops the anonymous caller. Cheap, and it is the same gate the
  rest of the service already uses.
* the per-actor window stops the *authenticated* caller, who in this slice is
  anybody who can invent a UUID and put it in a header. Without it the first
  gate buys almost nothing: ``X-Actor-ID`` is asserted by a trusted gateway
  that does not exist yet (``app/api/deps.py``), so a header is not yet proof
  of a person.

Both gates are written with their counter-case beside them. A test that only
checks the refusal passes just as green when the fix refuses everybody, which
is the failure mode this repo caught at #137.
"""

from __future__ import annotations

import uuid

import pytest

from app.api.routes.places import get_place_searcher, get_search_rate_limiter
from app.api.search_rate_limit import (
    SEARCH_LIMIT_PER_WINDOW,
    SEARCH_WINDOW_SECONDS,
    FixedWindowLimiter,
)

from .helpers import OTHER_ID, actor_headers

QUERY = "quán nướng ngoài trời cho 6 người dưới 300k"

ANSWER = {
    "understood": {
        "budget_per_person_vnd": 300_000,
        "group_size": 6,
        "max_distance_km": 5,
        "categories": ["quan-an-local"],
        "traits": ["Ngoài trời"],
    },
    "results": [
        {"id": "p-tiem-nuong-xom-lao", "reason": "Đồ nướng, ngồi ngoài trời."},
    ],
}


class Clock:
    """A hand-wound clock, so the window is tested rather than waited out."""

    def __init__(self, now: float = 1_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class CountingSearcher:
    """Stands in for Gemini and, crucially, counts how often it was reached.

    The status code alone cannot prove a refusal saved anything: a route that
    answers 429 *after* calling the model has already spent the token it was
    refusing to spend.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, query: str, places=None):
        # `places` is the catalogue the route read (M9). Counted stubs take it
        # and ignore it: what this one measures is whether it was reached.
        del places
        self.calls.append(query)
        return ANSWER


@pytest.fixture
def searcher(client) -> CountingSearcher:
    counter = CountingSearcher()
    client.app.dependency_overrides[get_place_searcher] = lambda: counter
    return counter


def search(client, headers=None, query: str = QUERY):
    return client.post("/places/search", json={"query": query}, headers=headers)


# ---------------------------------------------------------------------------
# Gate one: somebody has to be asking
# ---------------------------------------------------------------------------


def test_an_anonymous_search_is_refused_and_never_reaches_the_model(client, searcher):
    response = search(client)

    assert response.status_code == 401, response.text
    assert response.json()["code"] == "authentication_required"
    assert searcher.calls == [], "a request with no actor still spent a model call"


def test_a_signed_in_person_still_gets_their_places(client, searcher):
    """The counter-case. Without it, refusing everybody would read as a pass."""

    response = search(client, headers=actor_headers())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "ai"
    assert [place["id"] for place in body["places"]] == ["p-tiem-nuong-xom-lao"]
    assert searcher.calls == [QUERY]


def test_an_unparseable_actor_id_is_refused_before_the_prompt_is_built(
    client, searcher
):
    response = search(client, headers={"X-Actor-ID": "khong-phai-uuid"})

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "invalid_actor_id"
    assert searcher.calls == []


# ---------------------------------------------------------------------------
# Gate two: one person cannot be everybody
# ---------------------------------------------------------------------------


@pytest.fixture
def metered(client):
    """Three calls per window, so a burst is four requests rather than thirteen.

    The shipped numbers are asserted separately, in
    ``test_the_route_ships_the_limit_this_module_declares``. Testing the
    mechanism at the shipped limit would only make this file slower at proving
    the same thing.
    """

    clock = Clock()
    limiter = FixedWindowLimiter(
        limit=3,
        window_seconds=60,
        clock=clock,
        code="search_rate_limited",
        message="Too many searches.",
    )
    client.app.dependency_overrides[get_search_rate_limiter] = lambda: limiter
    return clock


def test_a_burst_from_one_person_is_cut_off(client, searcher, metered):
    for attempt in range(3):
        assert search(client, headers=actor_headers()).status_code == 200, attempt

    response = search(client, headers=actor_headers())

    assert response.status_code == 429, response.text
    assert response.json()["code"] == "search_rate_limited"


def test_the_refused_calls_are_the_ones_that_never_reach_the_model(
    client, searcher, metered
):
    for _ in range(9):
        search(client, headers=actor_headers())

    assert len(searcher.calls) == 3, (
        "the window refused the request after paying for it: "
        f"{len(searcher.calls)} model calls for 9 requests, expected 3"
    )


def test_the_cut_off_is_per_person_not_a_switch_that_stops_the_feature(
    client, searcher, metered
):
    """The counter-case for gate two, and the one that catches a global counter.

    A single shared counter passes every test above. It also means one person
    holding down refresh takes search away from the whole group, which is the
    outage this gate exists to prevent -- caused by the gate itself.
    """

    for _ in range(3):
        assert search(client, headers=actor_headers()).status_code == 200

    assert search(client, headers=actor_headers()).status_code == 429
    assert search(client, headers=actor_headers(actor_id=OTHER_ID)).status_code == 200


def test_the_block_expires_so_a_person_is_not_locked_out_for_good(
    client, searcher, metered
):
    for _ in range(3):
        search(client, headers=actor_headers())
    assert search(client, headers=actor_headers()).status_code == 429

    metered.advance(61)

    assert search(client, headers=actor_headers()).status_code == 200


def test_retrying_against_the_wall_does_not_push_the_wall_further_out(
    client, searcher, metered
):
    """A refusal must not move the window it was refused by.

    This is the difference between a one-minute cap and an indefinite ban. If
    a 429 slides `opened_at` to now, any client that retries on 429 -- which is
    most of them -- holds its own window open for as long as it keeps retrying,
    and a burst that should have cost sixty seconds costs however long the
    retry loop runs.

    The clock has to advance *during* the retries for this to be a real test.
    An earlier version of it burst against a frozen clock, where sliding the
    window to `now` slides it to where it already was: the assertion passed
    against a deliberately broken limiter, which is a test that reads as
    protection while providing none.
    """

    for _ in range(3):
        assert search(client, headers=actor_headers()).status_code == 200

    # 50 seconds of a client hammering a wall it is being told about.
    for _ in range(50):
        metered.advance(1)
        assert search(client, headers=actor_headers()).status_code == 429

    # Now past 60s from the *first* call, which is when the window is due.
    metered.advance(11)

    assert search(client, headers=actor_headers()).status_code == 200, (
        "the retries pushed the window out ahead of themselves"
    )


def test_one_person_hitting_the_wall_does_not_grow_memory_without_bound(metered):
    """Old windows are dropped, or a public route becomes a memory leak.

    Keyed on caller-supplied identity, a counter map that is only ever written
    to is a way to make the process fall over by asking it politely, 10 million
    times, with a different UUID each time.
    """

    clock = Clock()
    limiter = FixedWindowLimiter(
        limit=3,
        window_seconds=60,
        clock=clock,
        code="search_rate_limited",
        message="Too many searches.",
    )

    for _ in range(5_000):
        limiter.check(uuid.uuid4())
    clock.advance(61)
    limiter.check(uuid.uuid4())

    assert limiter.tracked() < 5_000, (
        f"{limiter.tracked()} expired windows still held after the window rolled"
    )


# ---------------------------------------------------------------------------
# The wiring, not the mechanism
# ---------------------------------------------------------------------------


def test_the_shipped_route_meters_without_any_test_installing_a_limiter(
    client, searcher
):
    """What the mechanism tests above deliberately do not cover.

    Every one of them installs its own limiter, so every one stays green if the
    app ships with no limiter at all, or with one configured to a number nobody
    meant. This burst goes through whatever `create_app` actually built.

    Thirteen is the shipped limit plus one. A person typing sentences does not
    reach twelve in a minute; a shell loop reaches it in under a second. Raising
    the number is a decision about how much shared, paid quota one unverified
    header may spend.
    """

    assert SEARCH_LIMIT_PER_WINDOW == 12
    assert SEARCH_WINDOW_SECONDS == 60

    codes = [
        search(client, headers=actor_headers()).status_code
        for _ in range(SEARCH_LIMIT_PER_WINDOW + 1)
    ]

    assert codes == [200] * SEARCH_LIMIT_PER_WINDOW + [429]
    assert len(searcher.calls) == SEARCH_LIMIT_PER_WINDOW


def test_each_application_carries_its_own_window(client, searcher):
    """A window shared across applications is a suite whose colour is ordered.

    It is also the wrong production shape by accident rather than by decision:
    a module-level counter would be shared by every app object in the process,
    which is right for the one app production builds and wrong for every test
    that builds another.
    """

    from app.api.main import create_app

    other = create_app()

    assert client.app.state.search_limiter is not other.state.search_limiter


def test_the_gate_is_on_the_paid_route_and_not_on_the_catalogue(client):
    """`GET /places` stays open, and that is a choice with a reason.

    Its model calls are memoised per place (`CachedReasonWriter`), so a loop
    against it cannot spend more than the catalogue costs once per cooldown.
    `POST /places/search` has no such ceiling: every distinct sentence is a new
    call, which is exactly why the two routes are treated differently.

    That memoisation is younger than this test. It used to read "per place per
    process", which held only while the model answered every row; a row it
    refused was re-asked on every request. This test stayed green throughout --
    it asserts a status code, not a call count -- which is why the count is
    asserted in `tests/api/test_places_reason_retry_storm.py` instead.
    """

    assert client.get("/places").status_code == 200

    assert search(client).status_code == 401
