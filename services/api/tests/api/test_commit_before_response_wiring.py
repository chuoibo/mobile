"""Application wiring for committing request sessions before response bodies."""

from __future__ import annotations

import anyio
import httpx
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api import unit_of_work
from app.api.main import create_app
from app.api.unit_of_work import (
    install_commit_before_response,
    register_session,
)

_COMMIT_MARKER = "__commits_before_response__"


class RecordingSession:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self._transaction_open = True

    def in_transaction(self) -> bool:
        return self._transaction_open

    def commit(self) -> None:
        self._events.append("commit")
        self._transaction_open = False


class BodyEventRecorder:
    def __init__(self, application: ASGIApp, events: list[str]) -> None:
        self._application = application
        self._events = events

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def watched(message: Message) -> None:
            if message["type"] == "http.response.body":
                self._events.append("body")
            await send(message)

        await self._application(scope, receive, watched)


def test_create_app_wraps_every_api_route() -> None:
    application = create_app()
    api_routes = [
        route for route in application.router.routes if isinstance(route, APIRoute)
    ]
    wrapped_count = sum(
        getattr(route.app, _COMMIT_MARKER, False) is True for route in api_routes
    )

    assert api_routes
    assert wrapped_count == len(api_routes)


def test_registered_session_commits_before_body_is_sent(monkeypatch) -> None:
    events: list[str] = []
    session = RecordingSession(events)
    application = FastAPI()

    @application.post("/write")
    async def write(request: Request) -> dict[str, str]:
        register_session(request, session)
        return {"status": "created"}

    assert install_commit_before_response(application) == 1

    async def run_in_threadpool_inline(function, *args, **kwargs):
        events.append("threadpool")
        return function(*args, **kwargs)

    monkeypatch.setattr(unit_of_work, "run_in_threadpool", run_in_threadpool_inline)
    observed_application = BodyEventRecorder(application, events)

    async def exchange() -> httpx.Response:
        transport = httpx.ASGITransport(app=observed_application)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.post("/write")

    response = anyio.run(exchange)

    assert response.status_code == 200
    assert events == ["threadpool", "commit", "body"]
