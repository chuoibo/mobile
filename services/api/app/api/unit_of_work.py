"""Commit request-owned database sessions before an HTTP response is sent."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from fastapi import FastAPI, Request, Response
from fastapi.routing import APIRoute, request_response
from starlette.concurrency import run_in_threadpool
from starlette.types import Scope

SESSIONS_SCOPE_KEY = "mobile_request_sessions"
_COMMIT_MARKER = "__commits_before_response__"


class _CommitSession(Protocol):
    def in_transaction(self) -> bool: ...

    def commit(self) -> None: ...


_RouteHandler = Callable[[Request], Awaitable[Response]]


def register_session(request: Request, session: _CommitSession) -> None:
    """Register a session whose transaction belongs to this request."""

    sessions = request.scope.setdefault(SESSIONS_SCOPE_KEY, [])
    sessions.append(session)


async def commit_registered_sessions(scope: Scope) -> None:
    """Commit every still-active request session without blocking the event loop."""

    for session in scope.get(SESSIONS_SCOPE_KEY, []):
        if session.in_transaction():
            await run_in_threadpool(session.commit)


def _wrap_route_handler(handler: _RouteHandler) -> _RouteHandler:
    async def wrapped(request: Request) -> Response:
        response = await handler(request)
        await commit_registered_sessions(request.scope)
        return response

    setattr(wrapped, _COMMIT_MARKER, True)
    return wrapped


def install_commit_before_response(application: FastAPI) -> int:
    """Install a pre-send commit callback on every FastAPI route.

    The commit has to run inside ``f(request)`` because that is the only point
    after the route handler returns but before
    ``await response(scope, receive, send)`` sends the body. FastAPI's public
    ``APIRoute.get_route_handler`` and ``request_response`` hooks are stable
    across the supported ``fastapi>=0.115,<1`` range. Its ``request_response``
    also establishes FastAPI's dependency exit stacks, unlike Starlette's
    lookalike.
    """

    wrapped_count = 0
    for route in application.router.routes:
        if not isinstance(route, APIRoute):
            continue
        wrapped = _wrap_route_handler(route.get_route_handler())
        route_app = request_response(wrapped)
        setattr(route_app, _COMMIT_MARKER, True)
        route.app = route_app
        wrapped_count += 1
    return wrapped_count
