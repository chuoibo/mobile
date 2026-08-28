"""Idempotency against real PostgreSQL, because a dict cannot refuse an insert.

The API-layer tests drive the middleware over an in-memory store. That store
says yes to everything, so it can prove the HTTP contract and nothing else. Two
claims in this feature are claims about the database and can only be tested
here:

* one key can be reserved exactly once, even by two connections at the same
  instant -- that is a unique index doing the work, not Python;
* replaying returns the row that was committed, byte for byte.

The last two tests go through the real ASGI stack against a real schema and
count rows in ``expenses``. That is the acceptance criterion in its literal
form: the same key twice must leave one record behind.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager

import anyio
import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.idempotency import (
    IDEMPOTENCY_HEADER,
    REPLAY_HEADER,
    Conflict,
    InFlight,
    Replay,
    Reserved,
    SqlAlchemyIdempotencyStore,
    StoredResponse,
)
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository

CONTEXT_ID = uuid.UUID("1aa00000-aaaa-4aaa-8aaa-0000a0000001")
ADVANCER_ID = uuid.UUID("2bb00000-bbbb-4bbb-8bbb-0000b0000001")
SENDER_ID = uuid.UUID("3cc00000-cccc-4ccc-8ccc-0000c0000001")
SCOPE = str(ADVANCER_ID)
FINGERPRINT = "a" * 64
OTHER_FINGERPRINT = "b" * 64


@contextmanager
def _store(engine: Engine):
    """One store per transaction, which is how the middleware uses it."""

    with Session(engine) as session, session.begin():
        yield SqlAlchemyIdempotencyStore(session)


def _expense_payload(total: int = 82000) -> dict:
    return {
        "context_id": str(CONTEXT_ID),
        "description": "Bữa tối",
        "recorded_by_id": str(ADVANCER_ID),
        "paid_by_id": str(ADVANCER_ID),
        "verification_scope": "totals_only",
        "occurred_at": "2030-08-27T12:00:00+07:00",
        "participants": [str(SENDER_ID), str(ADVANCER_ID)],
        "total_amount_vnd": total,
        "items": [],
        "surcharges": [],
        "discounts": [],
    }


def test_a_fresh_key_is_reserved(postgres_engine: Engine):
    key = str(uuid.uuid4())

    with _store(postgres_engine) as store:
        outcome = store.reserve(scope=SCOPE, key=key, fingerprint=FINGERPRINT)

    assert isinstance(outcome, Reserved)


def test_two_connections_racing_for_one_key_produce_one_winner(postgres_engine: Engine):
    """The second caller must lose, not overwrite and not duplicate."""

    key = str(uuid.uuid4())

    with _store(postgres_engine) as first:
        first_outcome = first.reserve(scope=SCOPE, key=key, fingerprint=FINGERPRINT)
    with _store(postgres_engine) as second:
        second_outcome = second.reserve(scope=SCOPE, key=key, fingerprint=FINGERPRINT)

    assert isinstance(first_outcome, Reserved)
    assert isinstance(second_outcome, InFlight)


def test_a_completed_key_replays_the_stored_response(postgres_engine: Engine):
    key = str(uuid.uuid4())
    stored = StoredResponse(
        status_code=201,
        body=b'{"expense_id": "kept"}',
        media_type="application/json",
    )

    with _store(postgres_engine) as store:
        assert isinstance(store.reserve(scope=SCOPE, key=key, fingerprint=FINGERPRINT), Reserved)
    with _store(postgres_engine) as store:
        store.complete(scope=SCOPE, key=key, response=stored)
    with _store(postgres_engine) as store:
        outcome = store.reserve(scope=SCOPE, key=key, fingerprint=FINGERPRINT)

    assert isinstance(outcome, Replay)
    assert outcome.response == stored


def test_the_same_key_with_a_different_fingerprint_conflicts(postgres_engine: Engine):
    key = str(uuid.uuid4())

    with _store(postgres_engine) as store:
        store.reserve(scope=SCOPE, key=key, fingerprint=FINGERPRINT)
    with _store(postgres_engine) as store:
        outcome = store.reserve(scope=SCOPE, key=key, fingerprint=OTHER_FINGERPRINT)

    assert isinstance(outcome, Conflict)


def test_the_same_key_under_another_actor_is_a_different_reservation(
    postgres_engine: Engine,
):
    key = str(uuid.uuid4())

    with _store(postgres_engine) as store:
        store.reserve(scope=SCOPE, key=key, fingerprint=FINGERPRINT)
    with _store(postgres_engine) as store:
        outcome = store.reserve(scope=str(SENDER_ID), key=key, fingerprint=FINGERPRINT)

    assert isinstance(outcome, Reserved)


def test_a_released_key_can_be_reserved_again(postgres_engine: Engine):
    key = str(uuid.uuid4())

    with _store(postgres_engine) as store:
        store.reserve(scope=SCOPE, key=key, fingerprint=FINGERPRINT)
    with _store(postgres_engine) as store:
        store.release(scope=SCOPE, key=key)
    with _store(postgres_engine) as store:
        outcome = store.reserve(scope=SCOPE, key=key, fingerprint=OTHER_FINGERPRINT)

    assert isinstance(outcome, Reserved)


def test_the_database_itself_refuses_a_duplicate_row(postgres_engine: Engine):
    """The guarantee is a unique index, not an application-level check.

    Without this the store could be reimplemented as SELECT-then-INSERT and
    every other test here would still pass while two concurrent requests both
    wrote money.
    """

    key = str(uuid.uuid4())
    insert = text(
        "insert into idempotency_keys (id, scope, idempotency_key, request_fingerprint)"
        " values (:id, :scope, :key, :fingerprint)"
    )

    with Session(postgres_engine) as session, session.begin():
        session.execute(
            insert,
            {"id": uuid.uuid4(), "scope": SCOPE, "key": key, "fingerprint": FINGERPRINT},
        )

    with pytest.raises(IntegrityError):
        with Session(postgres_engine) as session, session.begin():
            session.execute(
                insert,
                {
                    "id": uuid.uuid4(),
                    "scope": SCOPE,
                    "key": key,
                    "fingerprint": FINGERPRINT,
                },
            )


class _Client:
    """Direct ASGI transport; Starlette's sync TestClient deadlocks here."""

    def __init__(self, app):
        self.app = app

    def post(self, path, **kwargs):
        async def send():
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.post(path, **kwargs)

        return anyio.run(send)


@pytest.fixture
def live_client(postgres_engine: Engine, monkeypatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)

    def repository_dependency():
        with Session(postgres_engine) as session, session.begin():
            yield SqlAlchemyApiRepository(session)

    app = create_app(idempotency_store_factory=lambda: _store(postgres_engine))
    app.dependency_overrides[get_repository] = repository_dependency
    return _Client(app)


def _count_expenses(engine: Engine, context_id: uuid.UUID) -> int:
    with Session(engine) as session:
        return session.scalar(
            text("select count(*) from expenses where context_id = :context_id"),
            {"context_id": context_id},
        )


def test_posting_the_same_expense_twice_with_one_key_writes_one_row(
    live_client, postgres_engine: Engine
):
    context_id = uuid.uuid4()
    payload = _expense_payload() | {"context_id": str(context_id)}
    headers = {IDEMPOTENCY_HEADER: str(uuid.uuid4())}

    first = live_client.post("/expenses", json=payload, headers=headers)
    second = live_client.post("/expenses", json=payload, headers=headers)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json() == first.json()
    assert second.headers.get(REPLAY_HEADER) == "true"
    assert _count_expenses(postgres_engine, context_id) == 1


def test_reusing_a_key_with_another_payload_writes_nothing(
    live_client, postgres_engine: Engine
):
    context_id = uuid.uuid4()
    headers = {IDEMPOTENCY_HEADER: str(uuid.uuid4())}

    first = live_client.post(
        "/expenses",
        json=_expense_payload() | {"context_id": str(context_id)},
        headers=headers,
    )
    second = live_client.post(
        "/expenses",
        json=_expense_payload(total=99000) | {"context_id": str(context_id)},
        headers=headers,
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 422, second.text
    assert second.json()["code"] == "idempotency_key_reuse"
    assert _count_expenses(postgres_engine, context_id) == 1
