"""A route that writes and then fails must leave nothing behind.

`get_repository` used to be `with factory.begin() as session:`. That context
manager rolled back on any exception; nothing in the codebase had to say so.
Replacing it with a hand-written `try/except/else/finally` moved that guarantee
out of SQLAlchemy and into three lines this repository now owns, and no test in
the change that introduced them ever entered the `except` branch. Turning
`session.rollback()` into `session.commit()` there left the whole suite green,
so the rule "a failed request writes nothing" had no gate at all.

What the failure branch protects is the ledger. `POST /expenses` and
`confirm-receipt` write rows that decide who owes whom; a request that dies
half-way through must not leave the half it managed to write. Committing on the
way out of a failure is the one behaviour that silently produces money rows
nobody authorised.

These cases drive the real `create_app()` application over real PostgreSQL and
the real `get_repository`, and inject the fault at a service seam so the write
is performed by production code before the failure happens. Three failure
shapes travel three different paths out of the route:

* `HTTPException` -- caught by FastAPI's handler and turned into a 4xx body.
* `RuntimeError` -- unhandled, unwound through `ServerErrorMiddleware` as a 500.
* `asyncio.CancelledError` -- a `BaseException` that is not an `Exception`, the
  shape a client disconnect or a shutting-down worker takes. Nothing converts it
  into a response; it unwinds the entire stack.

What this file does and does not gate, measured rather than assumed. Deleting
the `except` branch outright, or narrowing it to `except Exception:`, leaves
every case here green -- and that is correct, not a hole: `finally:
session.close()` releases the connection, and releasing a connection with an
open transaction rolls it back. Those two mutants are equivalent, not escaped.
The mutant that changes behaviour is the one that *acts*: `session.rollback()`
becoming `session.commit()` turns the failure branch into a writer, and all
three cases below catch it.

The happy path is asserted in the same file on purpose. Without it a mutant
that rolls back unconditionally would look identical to a correct gate, and a
mutation table where every row is red cannot say which rule it is holding.
Committing is itself two layers -- `install_commit_before_response` commits
before the body is sent, and the `else` branch here commits anything it left --
so removing either one alone keeps the happy path green. Both have to go before
it turns red.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Generator

import anyio
import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.api.main import create_app
from app.api.service import ApiService
from app.db.session import get_engine, get_session_factory

pytestmark = pytest.mark.postgres


@pytest.fixture
def app_on_real_sessions(postgres_engine: Engine) -> Generator[FastAPI]:
    """Build the real application against the migrated test schema.

    `get_repository` takes its session from `get_session_factory`, which is
    cached per process and reads the URL once. Clearing both caches around the
    test is what lets the production dependency run unmodified instead of being
    replaced by a session the test owns -- an override has no teardown of its
    own, so it cannot fail to roll back.
    """

    previous = os.environ.get("MOBILE_DATABASE_URL")
    os.environ["MOBILE_DATABASE_URL"] = postgres_engine.url.render_as_string(
        hide_password=False
    )
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    try:
        yield create_app()
    finally:
        if previous is None:
            os.environ.pop("MOBILE_DATABASE_URL", None)
        else:
            os.environ["MOBILE_DATABASE_URL"] = previous
        get_engine.cache_clear()
        get_session_factory.cache_clear()


def _raise_after_registering(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    """Let the real write happen, then fail the request from inside the route.

    The seam is the service call the route makes, so everything up to and
    including the row landing in the request's transaction is production code.
    """

    registered = ApiService.register_person

    def failing(self: ApiService, *args: object, **kwargs: object) -> object:
        registered(self, *args, **kwargs)
        raise error

    monkeypatch.setattr(ApiService, "register_person", failing)


def _register(app: FastAPI, person_id: uuid.UUID, name: str) -> httpx.Response:
    async def exchange() -> httpx.Response:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.put(
                f"/people/{person_id}",
                headers={"X-Actor-ID": str(person_id), "X-Actor-Roles": "member"},
                json={"display_name": name},
            )

    return anyio.run(exchange)


def _rows_for(engine: Engine, person_id: uuid.UUID) -> int:
    # Its own connection, so it sees committed state only.
    with engine.connect() as connection:
        return connection.execute(
            text("select count(*) from people where id = :id"),
            {"id": person_id},
        ).scalar_one()


def _forget(engine: Engine, person_id: uuid.UUID) -> None:
    # A mutant commits for real into the schema every postgres test shares.
    # Leaving that row behind would fail somebody else's count in a file that
    # never mentions people.
    with engine.begin() as connection:
        connection.execute(text("delete from people where id = :id"), {"id": person_id})


@pytest.mark.parametrize(
    ("label", "error", "expected_status"),
    [
        ("http_exception", HTTPException(status_code=409, detail="conflict"), 409),
        ("unhandled_error", RuntimeError("the route died after writing"), 500),
    ],
    ids=["http_exception", "unhandled_error"],
)
def test_a_route_that_writes_then_fails_leaves_no_row(
    app_on_real_sessions: FastAPI,
    postgres_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    label: str,
    error: BaseException,
    expected_status: int,
) -> None:
    person_id = uuid.uuid4()
    _raise_after_registering(monkeypatch, error)

    try:
        response = _register(app_on_real_sessions, person_id, "phải bị cuộn lại")
        surviving = _rows_for(postgres_engine, person_id)

        assert response.status_code == expected_status, (
            f"[{label}] expected the request to fail with {expected_status}, "
            f"got {response.status_code}: {response.text}"
        )
        assert surviving == 0, (
            f"[{label}] the request failed with {response.status_code} but the "
            f"row it wrote survived: {surviving} row(s) are committed in "
            "`people`. A failed request must roll back its transaction."
        )
    finally:
        _forget(postgres_engine, person_id)


def test_a_cancelled_request_leaves_no_row(
    app_on_real_sessions: FastAPI,
    postgres_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancellation is a `BaseException`, and it must roll back too.

    A disconnecting client or a shutting-down worker cancels the task mid-route.
    Nothing converts that into an HTTP response -- it unwinds the whole stack,
    so there is no status code to assert and the exception is the outcome.

    This case exists because the failure path that never produces a response is
    the one nobody writes a test for, not because `except BaseException:` is
    load-bearing on its own: narrowing it to `except Exception:` still rolls
    back, via `finally: session.close()`. What this catches is the same thing
    the other two catch -- a failure branch that commits instead.
    """

    person_id = uuid.uuid4()
    _raise_after_registering(monkeypatch, asyncio.CancelledError())

    try:
        with pytest.raises(asyncio.CancelledError):
            _register(app_on_real_sessions, person_id, "phải bị cuộn lại")

        surviving = _rows_for(postgres_engine, person_id)
        assert surviving == 0, (
            "the request was cancelled after writing but the row survived: "
            f"{surviving} row(s) are committed in `people`"
        )
    finally:
        _forget(postgres_engine, person_id)


def test_a_route_that_succeeds_keeps_its_row(
    app_on_real_sessions: FastAPI, postgres_engine: Engine
) -> None:
    """The other half of the rule, so rolling back always is not a pass.

    Same application, same dependency, same table -- only the fault is missing.
    """

    person_id = uuid.uuid4()

    try:
        response = _register(app_on_real_sessions, person_id, "phải còn lại")
        surviving = _rows_for(postgres_engine, person_id)

        assert response.status_code == 201, response.text
        assert surviving == 1, (
            "the request answered 201 but no committed row exists for it: "
            f"{surviving} row(s) in `people`"
        )
    finally:
        _forget(postgres_engine, person_id)
