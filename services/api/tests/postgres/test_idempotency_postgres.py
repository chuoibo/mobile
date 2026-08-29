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

import json
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
    IdempotencyMiddleware,
    InFlight,
    Replay,
    Reserved,
    SqlAlchemyIdempotencyStore,
    StoredResponse,
    request_fingerprint,
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

    def __init__(self, app, connection):
        self.app = app
        self.connection = connection

    def post(self, path, **kwargs):
        async def send():
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.post(path, **kwargs)

        return anyio.run(send)

    def count_expenses(self, context_id: uuid.UUID) -> int:
        return self.connection.scalar(
            text("select count(*) from expenses where context_id = :context_id"),
            {"context_id": context_id},
        )

    def seed_group(self, context_id: uuid.UUID) -> None:
        """Put the two people in `_expense_payload` into a real group.

        Confirming an expense now refuses to charge anyone the roster does not
        contain, and this file's `context_id` is a bare `uuid4` with no rows
        behind it. That was invisible while the ledger took its participants
        from the request body; it is a 422 now.

        Seeding through the same connection as everything else, so the outer
        rollback still leaves the shared schema untouched -- see the fixture
        below for why that matters to `test_repository_postgres`.
        """

        for person_id, name in ((ADVANCER_ID, "Nam"), (SENDER_ID, "Hà")):
            self.connection.execute(
                text(
                    "insert into people (id, display_name) values (:id, :name)"
                    " on conflict (id) do nothing"
                ),
                {"id": person_id, "name": name},
            )
        self.connection.execute(
            text(
                "insert into contexts (id, display_name, created_by_id)"
                " values (:id, 'Nhóm ăn tối', :owner) on conflict (id) do nothing"
            ),
            {"id": context_id, "owner": ADVANCER_ID},
        )
        for person_id in (ADVANCER_ID, SENDER_ID):
            self.connection.execute(
                text(
                    "insert into memberships"
                    " (id, context_id, person_id, state, role, origin, joined_at)"
                    " values (:id, :context_id, :person_id, 'active', 'member',"
                    " 'named', now())"
                ),
                {
                    "id": uuid.uuid4(),
                    "context_id": context_id,
                    "person_id": person_id,
                },
            )

    def put(self, path, **kwargs):
        async def send():
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.put(path, **kwargs)

        return anyio.run(send)

    def count_expense_versions(self, expense_id: uuid.UUID) -> int:
        return self.connection.scalar(
            text(
                "select count(*) from expense_versions"
                " where expense_id = :expense_id"
            ),
            {"expense_id": expense_id},
        )

    def count_contexts_named(self, display_name: str) -> int:
        return self.connection.scalar(
            text("select count(*) from contexts where display_name = :display_name"),
            {"display_name": display_name},
        )

    def stored_fingerprint(self, scope: str, key: str) -> str:
        return self.connection.scalar(
            text(
                "select request_fingerprint from idempotency_keys"
                " where scope = :scope and idempotency_key = :key"
            ),
            {"scope": scope, "key": key},
        )

    def rewrite_fingerprint(self, scope: str, key: str, fingerprint: str) -> None:
        """Put the row back the way a server that hashed raw bytes left it."""

        self.connection.execute(
            text(
                "update idempotency_keys set request_fingerprint = :fingerprint"
                " where scope = :scope and idempotency_key = :key"
            ),
            {"scope": scope, "key": key, "fingerprint": fingerprint},
        )


@pytest.fixture
def live_client(postgres_engine: Engine, monkeypatch):
    """The real ASGI stack over the real schema, on one throwaway transaction.

    Every session below is bound to a single connection whose outer transaction
    is rolled back at teardown, so these two tests leave the shared schema
    exactly as they found it. `test_repository_postgres` asserts exact row
    counts in `expenses`, and a test that quietly adds rows to another test's
    table turns a real failure somewhere else into a mystery.

    Rolling back does not weaken what is being proved here: both requests go
    through the middleware, the SQL store and its `ON CONFLICT` for real, and
    the row count is taken after both have run. That one reservation can be won
    by only one caller across separate committed transactions is proved by the
    store-level tests above, which do commit.
    """

    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)

    connection = postgres_engine.connect()
    outer = connection.begin()

    @contextmanager
    def session_on_connection():
        with Session(
            bind=connection, join_transaction_mode="create_savepoint"
        ) as session, session.begin():
            yield session

    @contextmanager
    def store_factory():
        with session_on_connection() as session:
            yield SqlAlchemyIdempotencyStore(session)

    def repository_dependency():
        with session_on_connection() as session:
            yield SqlAlchemyApiRepository(session)

    app = create_app(idempotency_store_factory=store_factory)
    app.dependency_overrides[get_repository] = repository_dependency
    try:
        yield _Client(app, connection)
    finally:
        outer.rollback()
        connection.close()


def test_posting_the_same_expense_twice_with_one_key_writes_one_row(live_client):
    context_id = uuid.uuid4()
    payload = _expense_payload() | {"context_id": str(context_id)}
    headers = {IDEMPOTENCY_HEADER: str(uuid.uuid4())}

    first = live_client.post("/expenses", json=payload, headers=headers)
    second = live_client.post("/expenses", json=payload, headers=headers)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json() == first.json()
    assert second.headers.get(REPLAY_HEADER) == "true"
    assert live_client.count_expenses(context_id) == 1


ANSWER = b'{"expense_id": "the-one-answer"}'


class _Press:
    """One request driven at the middleware, with the test owning `send`."""

    def __init__(self, key: str):
        self.scope = {
            "type": "http",
            "method": "POST",
            "path": "/expenses",
            "query_string": b"",
            "headers": [
                (b"content-type", b"application/json"),
                (b"x-actor-id", SCOPE.encode("latin-1")),
                (IDEMPOTENCY_HEADER.lower().encode("latin-1"), key.encode("latin-1")),
            ],
        }
        self.messages: list[dict] = []

    async def receive(self):
        return {"type": "http.request", "body": b"{}", "more_body": False}

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


def _completed_at(engine: Engine, key: str):
    """Read the row on a separate connection: only committed work is visible."""

    with engine.connect() as connection:
        return connection.scalar(
            text(
                "select completed_at from idempotency_keys"
                " where scope = :scope and idempotency_key = :key"
            ),
            {"scope": SCOPE, "key": key},
        )


async def _answer_201(scope, receive, send):
    await send(
        {
            "type": "http.response.start",
            "status": 201,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": ANSWER})


def test_the_answer_is_released_only_after_the_completion_has_committed(
    postgres_engine: Engine,
):
    """The claim the fake store cannot make, because a dict has no commit.

    ``live_client`` runs every session on one connection, so a write is visible
    to the next read the instant it happens and this ordering bug is invisible
    there. A second connection sees committed rows and nothing else, which is
    exactly what a second press arriving on its own connection sees.
    """

    key = str(uuid.uuid4())
    press = _Press(key)
    seen: dict[str, object] = {}

    async def send(message):
        if message["type"] == "http.response.body" and "completed_at" not in seen:
            seen["completed_at"] = _completed_at(postgres_engine, key)
        await press.send(message)

    middleware = IdempotencyMiddleware(_answer_201, lambda: _store(postgres_engine))

    async def scenario():
        with anyio.fail_after(10):
            await middleware(press.scope, press.receive, send)

    anyio.run(scenario)

    assert press.status == 201
    assert seen["completed_at"] is not None, (
        "the caller held the answer while the key still read as unfinished;"
        " a second press on another connection would be told 409"
    )


def test_two_presses_racing_on_real_postgres_both_receive_the_one_answer(
    postgres_engine: Engine,
):
    """The parallel case, on the unique index that actually decides it.

    One caller wins the ``ON CONFLICT`` race and runs the handler. The other is
    the same request, so it must be given the winner's answer -- not a 409 that
    invites it to spend a fresh key on a second write of the same money.
    """

    key = str(uuid.uuid4())
    handled: list[int] = []
    saw_in_flight = None

    class _Signalling:
        """Real SQL store, plus a signal when a caller finds the key taken."""

        def __init__(self, inner):
            self.inner = inner

        def reserve(self, **kwargs):
            outcome = self.inner.reserve(**kwargs)
            if isinstance(outcome, InFlight):
                saw_in_flight.set()
            return outcome

        def complete(self, **kwargs):
            self.inner.complete(**kwargs)

        def release(self, **kwargs):
            self.inner.release(**kwargs)

    @contextmanager
    def store_factory():
        with _store(postgres_engine) as inner:
            yield _Signalling(inner)

    async def application(scope, receive, send):
        handled.append(1)
        # Hold the winner inside the handler until the loser has really found
        # the key reserved, so the race is pinned rather than hoped for.
        await saw_in_flight.wait()
        await _answer_201(scope, receive, send)

    middleware = IdempotencyMiddleware(application, store_factory)
    presses = [_Press(key), _Press(key)]

    async def scenario():
        nonlocal saw_in_flight
        saw_in_flight = anyio.Event()
        with anyio.fail_after(15):
            async with anyio.create_task_group() as tasks:
                for press in presses:
                    tasks.start_soon(middleware, press.scope, press.receive, press.send)

    anyio.run(scenario)

    assert [press.status for press in presses] == [201, 201], [
        (press.status, press.payload) for press in presses
    ]
    assert {press.payload for press in presses} == {ANSWER}
    assert handled == [1], "the handler must not run a second time"


def test_reusing_a_key_with_another_payload_writes_nothing(live_client):
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
    assert live_client.count_expenses(context_id) == 1


def _actor_headers(context_id: uuid.UUID) -> dict[str, str]:
    return {
        "X-Actor-ID": str(ADVANCER_ID),
        "X-Actor-Roles": "member,advancer",
        "X-Actor-Contexts": str(context_id),
    }


def _confirm_body(proposed: dict) -> dict:
    return {
        "proposal": proposed["proposal"],
        "expected_allocations": proposed["allocation"]["allocations"],
        "acknowledge_as_advancer": True,
    }


def _propose(live_client, context_id: uuid.UUID) -> dict:
    response = live_client.post(
        "/expenses", json=_expense_payload() | {"context_id": str(context_id)}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_confirming_the_same_expense_twice_with_one_key_writes_one_version(
    live_client,
):
    """The second press of *Xác nhận*, which is where the money is written.

    `/expenses` only drafts; this route is the one that puts rows in the ledger,
    and a double tap here was writing a whole second version of the same meal.
    Counted in `expense_versions` rather than compared through the response,
    because the response could match while a row was written anyway.
    """

    context_id = uuid.uuid4()
    live_client.seed_group(context_id)
    proposed = _propose(live_client, context_id)
    expense_id = uuid.UUID(proposed["expense_id"])
    headers = _actor_headers(context_id) | {IDEMPOTENCY_HEADER: str(uuid.uuid4())}
    body = _confirm_body(proposed)

    first = live_client.post(
        f"/expenses/{expense_id}/confirm", json=body, headers=headers
    )
    second = live_client.post(
        f"/expenses/{expense_id}/confirm", json=body, headers=headers
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json() == first.json()
    assert second.headers.get(REPLAY_HEADER) == "true"
    assert live_client.count_expense_versions(expense_id) == 1


def test_a_second_confirmation_under_its_own_key_still_writes_its_own_version(
    live_client,
):
    """The control, and it is not optional.

    Without it the test above also passes on a server that refuses every second
    confirmation, or answers every caller with the first version it ever made.
    Editing an expense is supposed to produce a new version, so a genuinely
    different press must still write one.
    """

    context_id = uuid.uuid4()
    live_client.seed_group(context_id)
    proposed = _propose(live_client, context_id)
    expense_id = uuid.UUID(proposed["expense_id"])
    body = _confirm_body(proposed)

    first = live_client.post(
        f"/expenses/{expense_id}/confirm",
        json=body,
        headers=_actor_headers(context_id) | {IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    )
    second = live_client.post(
        f"/expenses/{expense_id}/confirm",
        json=body,
        headers=_actor_headers(context_id) | {IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json()["expense_version_id"] != first.json()["expense_version_id"]
    assert second.json()["version_number"] == first.json()["version_number"] + 1
    assert live_client.count_expense_versions(expense_id) == 2


# ---------------------------------------------------------------------------
# One key, two encoders
# ---------------------------------------------------------------------------
#
# The seed script writes every group through the HTTP API with Python's
# `json.dumps`; the app retries the same key with JavaScript's `JSON.stringify`.
# Those produce different bytes for the same value, so a digest taken over the
# bytes refused the app's request as reuse. On a seeded machine -- which is
# every demo machine -- the group screen showed the server's English refusal
# where the member list belonged.
#
# Proved here rather than against the fake because the recovery path writes:
# a row left by the older server is rewritten in place, and a dict cannot show
# that the update landed on the row the next request reads.

GROUP_NAME = "Team Đà Lạt"
SEED_PERSON = uuid.UUID("4dd00000-dddd-4ddd-8ddd-0000d0000001")


def _seed_headers(key: str) -> dict:
    return {
        "X-Actor-ID": str(SEED_PERSON),
        "X-Actor-Roles": "group_admin,member",
        "Content-Type": "application/json",
        IDEMPOTENCY_HEADER: key,
    }


def _python_bytes(payload: dict) -> bytes:
    """`json.dumps`: non-ASCII escaped, a space after every separator."""

    return json.dumps(payload).encode("utf-8")


def _javascript_bytes(payload: dict) -> bytes:
    """`JSON.stringify`: literal UTF-8, no spaces."""

    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def _register_seed_person(live_client) -> None:
    registered = live_client.put(
        f"/people/{SEED_PERSON}",
        json={"display_name": "Minh"},
        headers={
            "X-Actor-ID": str(SEED_PERSON),
            "X-Actor-Roles": "group_admin,member",
        },
    )
    assert registered.status_code in (200, 201), registered.text


def test_the_app_replays_the_group_the_seed_created_instead_of_being_refused(
    live_client,
):
    """The reported bug, end to end, on the route it was reported against."""

    _register_seed_person(live_client)
    key = str(uuid.uuid4())
    payload = {"display_name": GROUP_NAME}
    assert _python_bytes(payload) != _javascript_bytes(payload)

    from_seed = live_client.post(
        "/contexts", content=_python_bytes(payload), headers=_seed_headers(key)
    )
    from_app = live_client.post(
        "/contexts", content=_javascript_bytes(payload), headers=_seed_headers(key)
    )

    assert from_seed.status_code == 201, from_seed.text
    assert from_app.status_code == 201, from_app.text
    assert from_app.json() == from_seed.json()
    assert from_app.headers.get(REPLAY_HEADER) == "true"
    # Replayed, not re-run. A second row here would be the other half of the
    # bug: a duplicate "Team Đà Lạt" beside the one holding all the history.
    assert live_client.count_contexts_named(GROUP_NAME) == 1


def test_a_key_reserved_by_the_older_server_is_recognised_and_upgraded(live_client):
    """The machines that are already broken, which a fresh schema never shows.

    Their `idempotency_keys` rows hold a digest of raw bytes. Canonicalising
    without recognising those rows would refuse the seed script itself on every
    machine it had ever run on -- turning a bug that blocks one screen into one
    that blocks re-seeding at all.
    """

    _register_seed_person(live_client)
    key = str(uuid.uuid4())
    payload = {"display_name": GROUP_NAME}
    scope = str(SEED_PERSON)

    from_seed = live_client.post(
        "/contexts", content=_python_bytes(payload), headers=_seed_headers(key)
    )
    assert from_seed.status_code == 201, from_seed.text

    # Rewind the row to what the previous version of this file wrote.
    legacy = request_fingerprint(
        method="POST", path="/contexts", query=b"", body=_python_bytes(payload)
    )
    live_client.rewrite_fingerprint(scope, key, legacy)
    assert live_client.stored_fingerprint(scope, key) == legacy

    # Re-running the seed must still replay rather than be refused as reuse.
    reseeded = live_client.post(
        "/contexts", content=_python_bytes(payload), headers=_seed_headers(key)
    )
    assert reseeded.status_code == 201, reseeded.text
    assert reseeded.headers.get(REPLAY_HEADER) == "true"

    # ...and it healed the row, so the app's spelling now replays too.
    assert live_client.stored_fingerprint(scope, key) != legacy
    from_app = live_client.post(
        "/contexts", content=_javascript_bytes(payload), headers=_seed_headers(key)
    )
    assert from_app.status_code == 201, from_app.text
    assert from_app.headers.get(REPLAY_HEADER) == "true"
    assert live_client.count_contexts_named(GROUP_NAME) == 1


def test_an_older_row_for_a_genuinely_different_request_is_still_refused(live_client):
    """The control. Recognising old rows must not mean accepting any old row.

    Without this, `reserve` could return the stored answer whenever the digests
    disagree -- which would replay one group's creation in answer to another's.
    """

    _register_seed_person(live_client)
    key = str(uuid.uuid4())
    scope = str(SEED_PERSON)

    created = live_client.post(
        "/contexts",
        content=_python_bytes({"display_name": GROUP_NAME}),
        headers=_seed_headers(key),
    )
    assert created.status_code == 201, created.text
    live_client.rewrite_fingerprint(
        scope,
        key,
        request_fingerprint(
            method="POST",
            path="/contexts",
            query=b"",
            body=_python_bytes({"display_name": GROUP_NAME}),
        ),
    )

    refused = live_client.post(
        "/contexts",
        content=_python_bytes({"display_name": "Nhóm khác"}),
        headers=_seed_headers(key),
    )

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "idempotency_key_reuse"
    assert live_client.count_contexts_named("Nhóm khác") == 0
