"""Cross-origin policy for the browser build of the app.

The native build sends no ``Origin`` header, so it never noticed that the API
had no CORS policy at all. The web build did: the browser preflights every
request that carries ``X-Actor-ID``, the preflight reached the router instead of
a CORS layer, and the router answered 405 for a method it has no route for. Not
one request got through.

These tests pin the browser-visible contract, not the middleware's identity.
"""

from __future__ import annotations

import pathlib
import sys
import uuid

import anyio
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.api.deps import get_repository  # noqa: E402
from app.api.main import create_app  # noqa: E402

from .conftest import ASGITestClient  # noqa: E402

# Spelled out rather than imported: the variable name is the operator-facing
# contract, so a rename has to break a test instead of following the import.
ORIGINS_ENV_VAR = "MOBILE_CORS_ALLOW_ORIGINS"
WEB_BUILD_ORIGIN = "http://localhost:8080"
ACTOR_HEADERS = "content-type,x-actor-id,x-actor-roles,x-actor-contexts"


@pytest.fixture
def client_factory(repository, monkeypatch):
    """Build an app whose CORS policy comes from a chosen environment.

    The policy is read at ``create_app`` time, so the environment has to be set
    before the app exists; the shared ``client`` fixture builds it too early.
    """

    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)

    def build(allow_origins: str | None = None):
        if allow_origins is None:
            monkeypatch.delenv(ORIGINS_ENV_VAR, raising=False)
        else:
            monkeypatch.setenv(ORIGINS_ENV_VAR, allow_origins)
        app = create_app()
        app.dependency_overrides[get_repository] = lambda: repository
        return ASGITestClient(app)

    return build


def preflight(client, origin, path="/expenses", method="POST", headers=ACTOR_HEADERS):
    return client.request(
        "OPTIONS",
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": headers,
        },
    )


def test_preflight_from_the_web_build_is_allowed(client_factory):
    """The exact request the browser sends before POST /expenses."""
    response = preflight(client_factory(), WEB_BUILD_ORIGIN)

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == WEB_BUILD_ORIGIN

    allowed = {
        value.strip().lower()
        for value in response.headers["access-control-allow-headers"].split(",")
    }
    assert {
        "content-type",
        "x-actor-id",
        "x-actor-roles",
        "x-actor-contexts",
    } <= allowed
    assert "POST" in response.headers["access-control-allow-methods"]


def test_refused_authentication_still_carries_the_allow_origin_header(client_factory):
    """A 401 the browser cannot read looks like the network is broken.

    Without the allow-origin header on error responses the web build reports an
    opaque failure and the person debugging it never sees the real status. This
    is the ``ApiProblem`` handler's path.
    """
    client = client_factory()

    response = client.get(
        f"/batches/{uuid.uuid4()}/obligations", headers={"Origin": WEB_BUILD_ORIGIN}
    )

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == WEB_BUILD_ORIGIN


def test_validation_errors_still_carry_the_allow_origin_header(client_factory):
    """FastAPI's own 422 handler is a different path and needs the header too."""
    response = client_factory().post("/expenses", headers={"Origin": WEB_BUILD_ORIGIN})

    assert response.status_code == 422
    assert response.headers["access-control-allow-origin"] == WEB_BUILD_ORIGIN


def test_credentials_are_never_allowed(client_factory):
    """Ambient cookies must not drive a money API from a foreign page."""
    response = preflight(client_factory(), WEB_BUILD_ORIGIN)

    assert "access-control-allow-credentials" not in response.headers


def test_configured_allowlist_is_honoured(client_factory):
    client = client_factory("https://app.example.com,https://chi.example.com")

    response = preflight(client, "https://chi.example.com")

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "https://chi.example.com"


def test_unlisted_origin_gets_no_allow_origin_header(client_factory):
    client = client_factory("https://app.example.com")

    response = preflight(client, "https://evil.example.com")

    assert "access-control-allow-origin" not in response.headers


def test_configured_allowlist_replaces_the_localhost_default(client_factory):
    """A deployment that names its origins does not silently keep loopback."""
    client = client_factory("https://app.example.com")

    response = preflight(client, WEB_BUILD_ORIGIN)

    assert "access-control-allow-origin" not in response.headers


def test_loopback_is_allowed_on_any_port_when_unconfigured(client_factory):
    """Expo picks its own port; pinning one would break on the next run."""
    client = client_factory()

    for origin in ("http://localhost:8081", "http://127.0.0.1:19006"):
        response = preflight(client, origin)
        assert response.status_code == 204, origin
        assert response.headers["access-control-allow-origin"] == origin


def test_unconfigured_policy_is_not_a_wildcard(client_factory):
    """The dev default is loopback-only, never ``*``."""
    response = preflight(client_factory(), "https://evil.example.com")

    assert response.headers.get("access-control-allow-origin") != "*"
    assert "access-control-allow-origin" not in response.headers
