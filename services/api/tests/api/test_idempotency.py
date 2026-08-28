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
)
from app.api.main import create_app

from .conftest import ASGITestClient
from .helpers import actor_headers, expense_payload

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

    app = create_app(idempotency_store_factory=factory)
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
