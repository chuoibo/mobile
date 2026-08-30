"""`GET /places` re-asks Gemini on every request for any reason it cannot get.

The hole
--------
`cached_gemini_reasons` caches **successes only**. That is deliberate and three
files say so approvingly -- a model blip during startup must not leave the
catalogue permanently unlabelled. What none of them noticed is that it makes
"asked and got nothing" indistinguishable from "never asked", so a row the
model will not answer is re-asked on *every* request, forever.

Three files then wrote the resulting bound down as a safety property and used
it to justify leaving this route unmetered:

    tests/api/test_companion_rate_limit.py  "bounded already ... one call per
                                             place per process"
    tests/api/test_places_search_actor_gate.py  "memoised per place per process"
    app/api/routes/suggestions.py           "bounded by `_reason_cache`, one
                                             call per place over a fixed
                                             catalogue"

Measured on `d4bf672`, 25 requests to `GET /places`, real `cached_gemini_reasons`
with only the outbound call stubbed:

    model answers every row      ->   1 model call     (the claim holds)
    model answers nothing        ->  25 model calls
    ONE row's reason dropped     ->  25 model calls

The third line is the one that matters. It is not an outage: `parse_reasons`
drops a reason whose figures are not grounded in the place record, by design,
and `tests/places/test_reasons_batch_robustness.py` measured roughly one first
load in ten arriving with reasons missing. One permanently-ungrounded row in a
twelve-place catalogue re-arms the whole batch on every request.

And `GET /places` is the **only** model-spending route with no actor at all --
`POST /places/search` requires one since rd-be-13, and the five metered routes
key their window on it. So this is an anonymous door onto the shared, paid
`GEMINI_API_KEY` that a `while true; do curl; done` walks straight through.

What this file proves and what it does not
------------------------------------------
It proves the writer stops paying for an answer it has already been refused,
and that it starts asking again when the cooldown rolls. It does **not** prove
the cooldown is the right length, and it proves nothing about Gemini itself:
the outbound call is stubbed by a counter. The live call has its own tier in
`tests/live/`, which is skipped without a key -- and a skip is not a green.

The clock is injected and **advanced**, never frozen. A frozen clock would make
the cooldown untestable in the only direction that matters: a mutant that never
retries would keep every assertion here green while the reasons went away for
the life of the process.
"""

from __future__ import annotations

import pytest

from app.api.routes.places import (
    REASON_RETRY_COOLDOWN_SECONDS,
    CachedReasonWriter,
    get_reason_writer,
)
from app.places.catalog import PLACES
from app.places.reasons import PlaceReason

REQUESTS = 25


class FakeClock:
    """Monotonic seconds the test moves on purpose."""

    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class CountingWriter:
    """The outbound half of `gemini_reasons`, counted.

    `answers` decides which place ids come back. Rows asked about but absent
    from it are the drop this file is about: the model was paid for them and
    returned nothing usable.
    """

    def __init__(self, answers) -> None:
        self.answers = answers
        self.calls = 0
        self.rows_asked: list[list[str]] = []

    def __call__(self, rows, group):
        del group
        self.calls += 1
        self.rows_asked.append([row.place["id"] for row in rows])
        return {
            row.place["id"]: PlaceReason(verdict="hop", reason="ok")
            for row in rows
            if row.place["id"] in self.answers
        }


def install(client, writer, clock):
    """Wire a real `CachedReasonWriter` into the app, with a test clock."""

    cached = CachedReasonWriter(writer=writer, clock=clock)
    client.app.dependency_overrides[get_reason_writer] = lambda: cached
    return cached


def hit(client, times=REQUESTS):
    codes = set()
    for _ in range(times):
        codes.add(client.get("/places").status_code)
    return codes


ALL_IDS = {place["id"] for place in PLACES}
DROPPED_ID = PLACES[0]["id"]
ALL_BUT_ONE = ALL_IDS - {DROPPED_ID}


def test_a_row_the_model_never_answers_is_asked_once_not_once_per_request(client):
    """The reproduction: 25 anonymous requests used to buy 25 model calls.

    Fails if the writer stops recording that it already asked about a row and
    got nothing back.
    """

    clock = FakeClock()
    writer = CountingWriter(answers=ALL_BUT_ONE)
    install(client, writer, clock)

    codes = hit(client)

    assert codes == {200}
    assert writer.calls == 1, (
        f"{REQUESTS} requests spent {writer.calls} model calls; one dropped "
        "reason re-arms the whole batch every request"
    )


def test_the_catalogue_still_costs_exactly_one_call_when_every_row_answers(client):
    """Property-preserving control: the happy path was already bounded.

    This is the number the three docstrings quoted, and it must not move. Fails
    if the fix charges a call for rows it can serve from cache.
    """

    clock = FakeClock()
    writer = CountingWriter(answers=ALL_IDS)
    install(client, writer, clock)

    codes = hit(client)

    assert codes == {200}
    assert writer.calls == 1


def test_the_model_is_asked_again_once_the_cooldown_rolls(client):
    """Suppression is a cooldown, not a tombstone.

    Fails if the fix simply never re-asks: a row dropped once would then stay
    unlabelled for the life of the process, which is the failure
    `cached_gemini_reasons` cached successes-only to avoid in the first place.
    """

    clock = FakeClock()
    writer = CountingWriter(answers=ALL_BUT_ONE)
    install(client, writer, clock)

    hit(client)
    assert writer.calls == 1

    clock.advance(REASON_RETRY_COOLDOWN_SECONDS + 1)
    hit(client)

    assert writer.calls == 2, "the cooldown rolled and nobody asked again"
    assert writer.rows_asked[-1] == [DROPPED_ID], (
        "the retry re-asked rows that are already cached"
    )


def test_a_row_that_answers_on_the_retry_stops_costing_calls(client):
    """A transient failure recovers and then goes quiet.

    Fails if a row that was once refused stays on the cooldown path after it
    has been answered -- that would keep paying for a reason already in hand.
    """

    clock = FakeClock()
    writer = CountingWriter(answers=ALL_BUT_ONE)
    install(client, writer, clock)

    hit(client)
    writer.answers = ALL_IDS
    clock.advance(REASON_RETRY_COOLDOWN_SECONDS + 1)
    hit(client)
    assert writer.calls == 2

    clock.advance(REASON_RETRY_COOLDOWN_SECONDS + 1)
    hit(client)

    assert writer.calls == 2, "the row answered, and was asked about again anyway"


def test_a_suppressed_row_still_serves_every_reason_the_model_did_give(client):
    """Bounding the spend must not cost the cards that did come back.

    Fails if suppression drops the whole batch rather than the one row: the
    other eleven places would lose their AI MATCH label on the hero screen.
    """

    clock = FakeClock()
    writer = CountingWriter(answers=ALL_BUT_ONE)
    install(client, writer, clock)

    hit(client)
    body = client.get("/places").json()

    # `source`, not `reason`: an unlabelled card still carries a sentence, the
    # server's own template. `source: "ai"` is the claim that a model wrote it.
    by_id = {place["id"]: place for place in body["places"]}
    assert by_id[DROPPED_ID]["match"]["source"] == "none"
    assert by_id[DROPPED_ID]["match"]["verdict"] is None
    labelled = {
        place_id
        for place_id, place in by_id.items()
        if place["match"]["source"] == "ai"
    }
    assert labelled == ALL_BUT_ONE


def test_two_apps_do_not_share_one_reason_cache():
    """The cache was a module global, so it outlived the app that owned it.

    `build_search_limiter` refuses to be a module-level singleton for exactly
    this reason, in the same codebase. Fails if the state goes back onto the
    module: two apps would then share it, and this suite's colour would depend
    on execution order.
    """

    first = CachedReasonWriter(
        writer=CountingWriter(answers=ALL_IDS), clock=FakeClock()
    )
    second_writer = CountingWriter(answers=ALL_IDS)
    second = CachedReasonWriter(writer=second_writer, clock=FakeClock())

    rows = [row for row in _rows()]
    first(rows)
    second(rows)

    assert second_writer.calls == 1, "the second writer read the first one's cache"


def _rows():
    from app.places.reasons import ReasonRow

    return [ReasonRow(place=place) for place in PLACES]


@pytest.mark.parametrize("cooldown", [REASON_RETRY_COOLDOWN_SECONDS])
def test_the_cooldown_is_a_real_number_of_seconds(cooldown):
    """Guards the constant against being set to zero, which disables the fix."""

    assert cooldown > 0
