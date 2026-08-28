"""Server-side enforcement of `Idempotency-Key` on write requests.

The mobile client already generates a key per attempt and reuses it on retry.
Until now the server ignored it, so a flaky network, a double tap, or an
automatic retry could write the same money twice. Holding the key on the client
is not protection: the client is the party that cannot be trusted to be online.

These tests drive the HTTP semantics against an in-memory store. They prove the
middleware's contract, NOT the database. The unique constraint, the race between
two connections, and the "one row landed" claim are proved in
``tests/postgres/test_idempotency_postgres.py`` against real PostgreSQL, because
a dict cannot refuse a duplicate insert.
"""

from __future__ import annotations

import json
import re
import uuid
from contextlib import contextmanager

import anyio
import pytest

from app.api.deps import get_repository
from app.api.idempotency import (
    IDEMPOTENCY_HEADER,
    REPLAY_HEADER,
    WRITE_METHODS,
    Conflict,
    IdempotencyMiddleware,
    InFlight,
    Replay,
    Reserved,
    StoredResponse,
    request_fingerprint,
)
from app.api.main import create_app

from .conftest import ASGITestClient
from .helpers import ADVANCER_ID, actor_headers, expense_payload

KEY = "1de11111-aaaa-4aaa-8aaa-0000a0000001"


class InMemoryIdempotencyStore:
    """Test double for the store seam only.

    It records calls so a test can prove the middleware consulted it. It does
    not model PostgreSQL: no unique index, no transaction, no concurrency.
    """

    def __init__(self):
        self.rows: dict[tuple[str, str], dict] = {}
        self.reservations: list[tuple[str, str, str]] = []

    def reserve(self, *, scope, key, fingerprint):
        self.reservations.append((scope, key, fingerprint))
        row = self.rows.get((scope, key))
        if row is None:
            self.rows[(scope, key)] = {
                "fingerprint": fingerprint,
                "response": None,
            }
            return Reserved()
        if row["fingerprint"] != fingerprint:
            return Conflict()
        if row["response"] is None:
            return InFlight()
        return Replay(row["response"])

    def complete(self, *, scope, key, response):
        self.rows[(scope, key)]["response"] = response

    def release(self, *, scope, key):
        self.rows.pop((scope, key), None)


@pytest.fixture
def store():
    return InMemoryIdempotencyStore()


@pytest.fixture
def client(repository, store, monkeypatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)

    @contextmanager
    def factory():
        yield store

    # A key nobody will finish is waited on before it is refused. The wait is
    # trimmed here so the abandoned-reservation test stays a test and not a nap.
    app = create_app(
        idempotency_store_factory=factory, idempotency_in_flight_wait_seconds=0.05
    )
    app.dependency_overrides[get_repository] = lambda: repository
    return ASGITestClient(app)


def _key_headers(key=KEY, **extra):
    return {IDEMPOTENCY_HEADER: key, **extra}


def test_the_same_key_replays_the_first_response_and_writes_once(client, repository):
    payload = expense_payload()

    first = client.post("/expenses", json=payload, headers=_key_headers())
    second = client.post("/expenses", json=payload, headers=_key_headers())

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json() == first.json()
    assert second.headers.get(REPLAY_HEADER) == "true"
    assert first.headers.get(REPLAY_HEADER) is None
    # The point of the whole feature: the handler ran once, so one expense exists.
    assert len(repository.expenses) == 1


def test_the_same_key_with_a_different_payload_is_refused(client, repository):
    first = client.post("/expenses", json=expense_payload(), headers=_key_headers())
    assert first.status_code == 201, first.text

    second = client.post(
        "/expenses",
        json=expense_payload(total=99000),
        headers=_key_headers(),
    )

    assert second.status_code == 422, second.text
    assert second.json()["code"] == "idempotency_key_reuse"
    # Refused means refused: the first answer is untouched and nothing new landed.
    assert len(repository.expenses) == 1


def test_a_request_without_the_header_is_left_alone(client, repository):
    payload = expense_payload()

    first = client.post("/expenses", json=payload)
    second = client.post("/expenses", json=payload)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json() != second.json()
    assert len(repository.expenses) == 2


def test_a_reservation_that_never_completed_reports_a_conflict(
    client, repository, store
):
    payload = expense_payload()
    client.post("/expenses", json=payload, headers=_key_headers())
    # Simulate the process dying after the money committed but before the
    # response was recorded: the row stays reserved forever.
    (row,) = list(store.rows.values())
    row["response"] = None

    retry = client.post("/expenses", json=payload, headers=_key_headers())

    assert retry.status_code == 409, retry.text
    assert retry.json()["code"] == "idempotency_request_in_flight"
    assert len(repository.expenses) == 1


def test_a_rejected_request_releases_the_key_so_a_real_retry_can_run(client, store):
    broken = {"context_id": "not-a-uuid"}

    first = client.post("/expenses", json=broken, headers=_key_headers())
    second = client.post("/expenses", json=broken, headers=_key_headers())

    assert first.status_code == 422, first.text
    assert second.status_code == 422, second.text
    # Not the idempotency error: the request never wrote anything, so the key is
    # free and the retry is a genuine second attempt.
    assert second.json().get("code") != "idempotency_key_reuse"
    assert store.rows == {}


def test_the_key_is_scoped_to_the_actor(client, repository):
    payload = expense_payload()
    mine = actor_headers()
    theirs = actor_headers(actor_id=uuid.UUID("5ee00000-eeee-4eee-8eee-0000e0000001"))

    first = client.post("/expenses", json=payload, headers=_key_headers(**mine))
    second = client.post("/expenses", json=payload, headers=_key_headers(**theirs))

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    # One person's key must never replay another person's answer.
    assert first.json() != second.json()
    assert len(repository.expenses) == 2


def test_the_middleware_is_installed_on_the_application():
    app = create_app()
    installed = [entry.cls for entry in app.user_middleware]
    assert IdempotencyMiddleware in installed


def test_registering_a_bank_account_twice_writes_once(client):
    """The seam between this middleware and `POST /bank-recipients`.

    Both branches edited the same lines of `main.py`. Resolving that by keeping
    only one side fails silently: the router still answers, the header is simply
    ignored, and a retried registration re-runs against where somebody's money
    lands.

    The status code is the discriminator, not the header alone. A replay returns
    the first answer verbatim, so it stays 201. A handler that genuinely ran a
    second time answers 200 -- the route's own "you re-sent digits that were
    already there" code -- so dropping either the router or the middleware turns
    this red.
    """

    body = {
        "recipient_id": str(ADVANCER_ID),
        "bank_bin": "970418",
        "account_number": "0000000000TEST",
        "account_name": "NGUYEN VAN NAM",
    }
    headers = _key_headers(**actor_headers())

    first = client.post("/bank-recipients", json=body, headers=headers)
    second = client.post("/bank-recipients", json=body, headers=headers)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.headers.get(REPLAY_HEADER) == "true"
    assert second.json() == first.json()


def test_every_write_route_consults_the_store(client, store):
    """Coverage by construction, not by a list somebody has to remember.

    A new write route added later is covered the moment it is registered. This
    test fails if the middleware is ever narrowed to a hand-maintained set.
    """

    placeholder = re.compile(r"\{[^}]+\}")
    write_routes = [
        (method, route.path)
        for route in client.app.routes
        for method in sorted(getattr(route, "methods", set()) & WRITE_METHODS)
    ]
    assert len(write_routes) >= 8, f"route discovery looks broken: {write_routes}"

    for method, template in write_routes:
        # The handler's own answer is irrelevant here -- most of these will 404
        # or 422 on a placeholder id. The only question is whether the request
        # reached the store at all.
        path = placeholder.sub(str(uuid.uuid4()), template)
        store.reservations.clear()
        client.request(
            method, path, json={}, headers=_key_headers(key=str(uuid.uuid4()))
        )
        assert store.reservations, f"{method} {template} bypassed the idempotency store"


def test_read_requests_never_touch_the_store(client, store):
    client.get("/healthz", headers=_key_headers())

    assert store.reservations == []


def test_a_replayed_response_keeps_the_original_status_and_body(store):
    """The stored response is returned verbatim, not re-serialised."""

    stored = StoredResponse(status_code=201, body=b'{"a": 1}', media_type="application/json")
    store.rows[("anonymous", KEY)] = {"fingerprint": "f", "response": stored}

    outcome = store.reserve(scope="anonymous", key=KEY, fingerprint="f")

    assert isinstance(outcome, Replay)
    assert outcome.response == stored


# --------------------------------------------------------------------------
# Two presses of one button
#
# Everything above drives the middleware one request at a time, and the store
# is a dict that completes instantly. Both of those hide the failure a person
# actually hit: the second press does not politely wait for the bookkeeping of
# the first. It arrives while the first answer is still on the wire, or on a
# second connection at the very same instant.
#
# Measured against a real server on the code these tests were written for:
#   back-to-back, gap 0s     -> 409 four times out of four
#   back-to-back, gap 0.05s  -> 201, replayed correctly
#   two at once, any gap     -> 409 four times out of four
#
# The 409 says "use a new key". A client that follows that advice writes the
# money twice, which is the single thing this feature exists to prevent.
# --------------------------------------------------------------------------

BODY = b'{"total_amount_vnd": 82000}'
ANSWER = b'{"expense_id": "the-one-answer"}'


class _Press:
    """One HTTP request driven straight at the middleware.

    Deliberately not `ASGITestClient`: these tests are about *when* bytes reach
    the caller relative to the store, so the test has to own `send` itself.
    """

    def __init__(self, key: str = KEY, body: bytes = BODY):
        self.scope = {
            "type": "http",
            "method": "POST",
            "path": "/expenses",
            "query_string": b"",
            "headers": [
                (b"content-type", b"application/json"),
                (IDEMPOTENCY_HEADER.lower().encode("latin-1"), key.encode("latin-1")),
            ],
        }
        self.body = body
        self.messages: list[dict] = []

    async def receive(self):
        return {"type": "http.request", "body": self.body, "more_body": False}

    async def send(self, message):
        self.messages.append(message)

    @property
    def status(self) -> int:
        for message in self.messages:
            if message["type"] == "http.response.start":
                return message["status"]
        raise AssertionError(f"no response was ever started: {self.messages}")

    @property
    def payload(self) -> bytes:
        return b"".join(
            message.get("body") or b""
            for message in self.messages
            if message["type"] == "http.response.body"
        )


def _factory(store):
    @contextmanager
    def factory():
        yield store

    return factory


def test_the_answer_is_not_released_before_the_key_is_recorded_complete(store):
    """Press 2 sent the instant press 1's bytes land must replay, not 409.

    A sleep is not the contract, and "wait 50ms" is not something a phone can
    promise. The contract is an order: nothing reaches the caller until the
    completion has been recorded, so no window exists in which a second press
    can read the key as unfinished.
    """

    handled: list[str] = []

    async def application(scope, receive, send):
        handled.append(scope["path"])
        await send(
            {
                "type": "http.response.start",
                "status": 201,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": ANSWER})

    middleware = IdempotencyMiddleware(application, _factory(store))
    first, second = _Press(), _Press()

    async def send_first(message):
        await first.send(message)
        if message["type"] == "http.response.body":
            # The caller is holding the answer now. Their thumb is faster than
            # any bookkeeping this server has left to do.
            await middleware(second.scope, second.receive, second.send)

    async def scenario():
        with anyio.fail_after(5):
            await middleware(first.scope, first.receive, send_first)

    anyio.run(scenario)

    assert first.status == 201
    assert second.status == 201, second.payload
    assert second.payload == first.payload
    assert second.messages[0]["headers"]
    assert handled == ["/expenses"], "the handler must not run a second time"


def test_two_presses_at_the_same_instant_both_receive_the_one_answer(store):
    """React double-render, or a retry racing the original. Same key, same bytes.

    The loser of the reservation race is not a client error. It is the same
    request, and the only answer that is true for it is the one the winner
    produced. Refusing it invites the caller to retry with a fresh key, which
    is how one dinner becomes two debts.
    """

    handled: list[str] = []
    saw_in_flight = None

    class _Signalling:
        """Wraps the store so the handler can be held open on purpose.

        Without this the test would depend on a sleep being long enough, and a
        test that depends on a sleep is a test that will lie on a loaded CI box.
        """

        def reserve(self, **kwargs):
            outcome = store.reserve(**kwargs)
            if isinstance(outcome, InFlight):
                saw_in_flight.set()
            return outcome

        def complete(self, **kwargs):
            store.complete(**kwargs)

        def release(self, **kwargs):
            store.release(**kwargs)

    async def application(scope, receive, send):
        handled.append(scope["path"])
        # Hold the first request inside the handler until the second one has
        # genuinely found the key reserved. That is the real race, pinned.
        await saw_in_flight.wait()
        await send(
            {
                "type": "http.response.start",
                "status": 201,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": ANSWER})

    middleware = IdempotencyMiddleware(application, _factory(_Signalling()))
    presses = [_Press(), _Press()]

    async def scenario():
        nonlocal saw_in_flight
        saw_in_flight = anyio.Event()
        with anyio.fail_after(10):
            async with anyio.create_task_group() as tasks:
                for press in presses:
                    tasks.start_soon(middleware, press.scope, press.receive, press.send)

    anyio.run(scenario)

    assert [press.status for press in presses] == [201, 201], [
        (press.status, press.payload) for press in presses
    ]
    assert {press.payload for press in presses} == {ANSWER}
    assert handled == ["/expenses"], "the handler must not run a second time"


def test_a_reservation_nobody_will_ever_finish_still_gives_up(store):
    """The wait is bounded, and it does not advise the caller into a double write.

    A process that died holding a key leaves a row no one will ever complete.
    Waiting forever would hang the caller; the honest answer is to stop. What
    the answer must not do is tell them to spend a new key, because a new key
    is exactly permission to write the money a second time.
    """

    async def application(scope, receive, send):  # pragma: no cover - never runs
        raise AssertionError("the handler must not run for a reserved key")

    store.rows[("anonymous", KEY)] = {
        "fingerprint": request_fingerprint(
            method="POST", path="/expenses", query=b"", body=BODY
        ),
        "response": None,
    }
    middleware = IdempotencyMiddleware(
        application, _factory(store), in_flight_wait_seconds=0.05
    )
    press = _Press()

    async def scenario():
        with anyio.fail_after(5):
            await middleware(press.scope, press.receive, press.send)

    anyio.run(scenario)

    assert press.status == 409
    assert json.loads(press.payload)["code"] == "idempotency_request_in_flight"
    assert "new key" not in json.loads(press.payload)["detail"].lower()
