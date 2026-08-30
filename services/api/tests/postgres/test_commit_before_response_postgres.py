"""A write must be durable before its answer reaches the client.

FastAPI closes the `yield`-dependency exit stack *after* it has already sent
the response: in `fastapi/routing.py::request_response` the body goes out on
`await response(scope, receive, send)` and only then does the enclosing
`async with AsyncExitStack() as request_stack` unwind. `get_repository` commits
inside that unwind, so a client can hold a 201 for a row no other connection can
see yet. Read-after-write on the next connection then answers 404. Measured on
real HTTP at roughly one round trip in two hundred.

This file refuses to hunt that race by repetition -- a one-in-two-hundred test
is a flaky test, and a green run of it would prove nothing. It observes the
ordering directly instead. Every middleware in this app is pure ASGI, so no
layer buffers the response; when `http.response.body` reaches an outermost
wrapper, the route's exit stack is still open. That is the exact instant the
client learns the write succeeded, so that is when a SEPARATE connection is
asked whether the row exists. Before the fix it is invisible every single time,
after the fix visible every single time.

The real `get_repository` is used on purpose. Every other HTTP test in this
directory overrides it with a session the test itself owns, which is why none
of them can see this bug: the overriding dependency has no teardown commit to
be late.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Generator

import anyio
import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.api.main import create_app
from app.db.session import get_engine, get_session_factory

pytestmark = pytest.mark.postgres


class ProbeWhenBodyGoesOut:
    """Outermost ASGI wrapper that looks at the database as the body departs.

    The probe runs before the message is forwarded, so it observes the world a
    client racing the response would observe: the route has produced its answer
    and nothing downstream of the route has been torn down yet.
    """

    def __init__(self, app: FastAPI, probe: Callable[[], int]) -> None:
        self._app = app
        self._probe = probe
        self.seen: list[int] = []

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
        async def watched(message) -> None:  # noqa: ANN001
            if message["type"] == "http.response.body":
                self.seen.append(self._probe())
            await send(message)

        await self._app(scope, receive, watched)


@pytest.fixture
def app_on_real_sessions(postgres_engine: Engine) -> Generator[FastAPI]:
    """Point the application's own session factory at the migrated schema.

    `get_repository` builds its session from `get_session_factory`, which is
    cached per process and reads the URL once. Clearing both caches around the
    test is what lets the production dependency run unmodified.
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


def _counts_person(engine: Engine, person_id: uuid.UUID) -> Callable[[], int]:
    def probe() -> int:
        # A connection of its own, so this sees only what has been committed.
        # A plain SELECT never blocks on an uncommitted INSERT in PostgreSQL,
        # so an open writing transaction cannot deadlock this.
        with engine.connect() as connection:
            return connection.execute(
                text("select count(*) from people where id = :id"),
                {"id": person_id},
            ).scalar_one()

    return probe


def test_row_is_visible_to_other_connections_when_201_goes_out(
    app_on_real_sessions: FastAPI, postgres_engine: Engine
) -> None:
    person_id = uuid.uuid4()
    watcher = ProbeWhenBodyGoesOut(
        app_on_real_sessions, _counts_person(postgres_engine, person_id)
    )

    async def exchange() -> httpx.Response:
        transport = httpx.ASGITransport(app=watcher)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.put(
                f"/people/{person_id}",
                headers={"X-Actor-ID": str(person_id), "X-Actor-Roles": "member"},
                json={"display_name": "Người vừa đăng ký"},
            )

    try:
        response = anyio.run(exchange)

        assert response.status_code == 201, response.text
        assert watcher.seen, "the response body never reached the outermost wrapper"
        assert watcher.seen[0] == 1, (
            "the client was told 201 while the row was still uncommitted: "
            "another connection counted "
            f"{watcher.seen[0]} rows at the moment the body went out"
        )
    finally:
        # This test commits for real into the schema every postgres test
        # shares. Leaving the row behind would make somebody else's count
        # assertion fail in a file that never mentioned people.
        with postgres_engine.begin() as connection:
            connection.execute(
                text("delete from people where id = :id"), {"id": person_id}
            )


def test_read_after_write_on_a_fresh_connection_finds_the_row(
    app_on_real_sessions: FastAPI, postgres_engine: Engine
) -> None:
    """The behaviour the ordering above exists to protect.

    A client that creates something and immediately navigates to it must not be
    told the thing does not exist. The probe issues the follow-up read at the
    earliest moment a real client could issue it -- while the body is still
    being handed over -- so no sleep, retry or repetition is involved.
    """

    person_id = uuid.uuid4()
    lookups: list[int] = []

    def probe() -> int:
        with postgres_engine.connect() as connection:
            found = connection.execute(
                text("select display_name from people where id = :id"),
                {"id": person_id},
            ).scalar_one_or_none()
        lookups.append(0 if found is None else 1)
        return lookups[-1]

    watcher = ProbeWhenBodyGoesOut(app_on_real_sessions, probe)

    async def exchange() -> httpx.Response:
        transport = httpx.ASGITransport(app=watcher)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.put(
                f"/people/{person_id}",
                headers={"X-Actor-ID": str(person_id), "X-Actor-Roles": "member"},
                json={"display_name": "Đọc lại ngay"},
            )

    try:
        response = anyio.run(exchange)

        assert response.status_code == 201, response.text
        assert lookups == [1], (
            "a read issued the moment the 201 was delivered did not find the "
            f"person the 201 was about: {lookups}"
        )
    finally:
        with postgres_engine.begin() as connection:
            connection.execute(
                text("delete from people where id = :id"), {"id": person_id}
            )
