"""F37's ninth window, discovered from the app instead of a name roster.

The gate starts at FastAPI's dependency graph.  A new model dependency is a
new door whether or not anybody remembered to append its limiter to a list;
that is the N+1 failure the earlier window tests could not see.  Each door must
resolve a guard in the same graph, and every actor-keyed window must be a
different object.  The two public place reads intentionally share one
``CachedReasonWriter``; it is a cache, not a window, so the identity claim is
made only over ``FixedWindowLimiter`` instances.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
import uuid
from types import SimpleNamespace

import anyio
import pytest
from fastapi.routing import APIRoute

from app.api.deps import get_reeler, get_repository
from app.api.errors import ApiProblem
from app.api.main import create_app
from app.api.routes.places import CachedReasonWriter
from app.api.search_rate_limit import REEL_LIMIT_PER_WINDOW, FixedWindowLimiter

from .conftest import ASGITestClient
from .test_trip_reel import (
    CONTEXT_ID,
    HEADERS,
    MEMBER_ID,
    NOW,
    OUTING_ID,
    SECOND_MEMBER_ID,
    RecordingReeler,
    StubReelRepository,
    actor_headers,
)

REEL_PATH = f"/contexts/{CONTEXT_ID}/albums/{OUTING_ID}/reel"
REEL_ROUTE_TEMPLATE = "/contexts/{context_id}/albums/{outing_id}/reel"
_GUARD_TYPES = (FixedWindowLimiter, CachedReasonWriter)


def _walk(dependant):
    yield dependant
    for child in dependant.dependencies:
        yield from _walk(child)


def _source(call) -> str:
    try:
        return textwrap.dedent(inspect.getsource(call))
    except (OSError, TypeError):
        return ""


def _imports_model(call) -> bool:
    """Recognise a model provider from source, never from a route roster."""

    source = _source(call)
    if not source:
        return False
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    if any(
        module.endswith("_gemini")
        or module.endswith("_skill")
        or module == "app.media.face_detection"
        for module in imported
    ):
        return True

    # The place searcher is imported at module scope and returned by its
    # dependency provider.  Source still names the callable, so a renamed or
    # removed provider changes discovery rather than leaving a stale path list.
    return "gemini_search" in source


def _resolve_state_guard(call, app):
    """Resolve only dependencies that explicitly read an app-state object."""

    source = _source(call)
    if "request.app.state" not in source:
        return None
    return call(SimpleNamespace(app=app))


def _discover_model_doors(app) -> dict[str, tuple[object, ...]]:
    doors: dict[str, tuple[object, ...]] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        calls = [node.call for node in _walk(route.dependant) if node.call]
        guards = tuple(
            guard
            for call in calls
            if (guard := _resolve_state_guard(call, app)) is not None
            and isinstance(guard, _GUARD_TYPES)
        )
        is_model_door = any(_imports_model(call) for call in calls) or any(
            isinstance(guard, CachedReasonWriter) for guard in guards
        )
        if not is_model_door:
            continue
        methods = sorted((route.methods or set()) - {"HEAD"})
        for method in methods:
            doors[f"{method} {route.path}"] = guards
    return doors


def _windows(app) -> dict[str, FixedWindowLimiter]:
    state = vars(app.state).get("_state", {})
    found = {
        name: value
        for name, value in state.items()
        if isinstance(value, FixedWindowLimiter)
    }
    assert found, f"discovered no windows in app.state: {sorted(state)}"
    return found


def _spend(limiter: FixedWindowLimiter, actor_id: uuid.UUID) -> None:
    for _ in range(limiter.limit):
        limiter.check(actor_id)


def _is_open(limiter: FixedWindowLimiter, actor_id: uuid.UUID) -> bool:
    try:
        limiter.check(actor_id)
    except ApiProblem as problem:
        assert problem.status_code == 429
        return False
    return True


@pytest.fixture
def window_reeler():
    return RecordingReeler()


@pytest.fixture
def window_client(monkeypatch, window_reeler):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: StubReelRepository()
    app.dependency_overrides[get_reeler] = lambda: window_reeler
    return ASGITestClient(app)


def test_every_model_door_is_capped():
    app = create_app()
    doors = _discover_model_doors(app)

    assert doors, "dependency walk discovered no model doors"
    assert f"GET {REEL_ROUTE_TEMPLATE}" in doors
    uncapped = [name for name, guards in doors.items() if not guards]
    assert uncapped == [], f"model doors without a guard: {uncapped}"


def test_no_two_model_doors_resolve_to_one_window():
    doors = _discover_model_doors(create_app())
    windows = {
        name: next(
            (guard for guard in guards if isinstance(guard, FixedWindowLimiter)),
            None,
        )
        for name, guards in doors.items()
    }
    windows = {name: window for name, window in windows.items() if window is not None}
    by_identity: dict[int, list[str]] = {}
    for name, window in windows.items():
        by_identity.setdefault(id(window), []).append(name)
    shared = [names for names in by_identity.values() if len(names) > 1]

    assert f"GET {REEL_ROUTE_TEMPLATE}" in windows
    assert shared == [], f"model doors sharing one window: {shared}"


def test_spending_the_whole_reel_window_leaves_every_other_door_open(
    window_client, window_reeler
):
    codes = [
        window_client.get(REEL_PATH, headers=HEADERS).status_code
        for _ in range(REEL_LIMIT_PER_WINDOW + 1)
    ]

    assert codes == [200] * REEL_LIMIT_PER_WINDOW + [429]
    assert len(window_reeler.calls) == REEL_LIMIT_PER_WINDOW
    reel = window_client.app.state.reel_limiter
    shut = [
        name
        for name, limiter in _windows(window_client.app).items()
        if limiter is not reel and not _is_open(limiter, MEMBER_ID)
    ]
    assert shut == [], f"the reel burst closed windows it does not own: {shut}"


def test_emptying_every_other_door_leaves_the_reel_answering(
    window_client, window_reeler
):
    reel = window_client.app.state.reel_limiter
    others = {
        name: limiter
        for name, limiter in _windows(window_client.app).items()
        if limiter is not reel
    }
    assert others, "no neighbouring window was discovered"
    for limiter in others.values():
        _spend(limiter, MEMBER_ID)

    response = window_client.get(REEL_PATH, headers=HEADERS)

    assert response.status_code == 200, response.text
    assert len(window_reeler.calls) == 1


def test_the_reel_ceiling_is_counted_per_person(window_client):
    for _ in range(REEL_LIMIT_PER_WINDOW):
        assert window_client.get(REEL_PATH, headers=HEADERS).status_code == 200
    assert window_client.get(REEL_PATH, headers=HEADERS).status_code == 429

    other = window_client.get(
        REEL_PATH,
        headers=actor_headers(SECOND_MEMBER_ID, claimed_context=CONTEXT_ID),
    )

    assert other.status_code == 200, other.text
