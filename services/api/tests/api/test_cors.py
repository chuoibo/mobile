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

from app.api.cors import ALLOWED_HEADERS, ALLOWED_METHODS  # noqa: E402
from app.api.deps import get_repository  # noqa: E402
from app.api.idempotency import IDEMPOTENCY_HEADER  # noqa: E402
from app.api.main import create_app  # noqa: E402

from .conftest import ASGITestClient  # noqa: E402

# Spelled out rather than imported: the variable name is the operator-facing
# contract, so a rename has to break a test instead of following the import.
ORIGINS_ENV_VAR = "MOBILE_CORS_ALLOW_ORIGINS"
WEB_BUILD_ORIGIN = "http://localhost:8080"
ACTOR_HEADERS = "content-type,x-actor-id,x-actor-roles,x-actor-contexts"
# What a browser really lists before a write: the client attaches an idempotency
# key to every write attempt, so this -- not ACTOR_HEADERS -- is the preflight
# that stands between the web build and any money changing hands.
WRITE_HEADERS = "content-type,idempotency-key,x-actor-id"


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


def test_preflight_for_renaming_a_person_is_allowed(client_factory):
    """The exact request the web build sends before ``PUT /people/{id}``.

    ``registerPerson`` in the client uses PUT. When PUT was missing from the
    allowlist the browser never sent the request at all, the name never reached
    the server, and the guest page kept printing "Phần của <uuid>" -- a bug that
    only the web build could see, because the native build sends no ``Origin``.
    """
    response = preflight(
        client_factory(),
        WEB_BUILD_ORIGIN,
        path=f"/people/{uuid.uuid4()}",
        method="PUT",
    )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == WEB_BUILD_ORIGIN
    assert "PUT" in response.headers["access-control-allow-methods"]


def test_preflight_carrying_the_idempotency_key_is_allowed(client_factory):
    """The exact request the browser sends before any write.

    ``POST /expenses`` and ``PUT /people/{id}`` both carry ``Idempotency-Key``,
    so this preflight -- not the one in ``ACTOR_HEADERS`` -- is the one the web
    build actually sends. While the header was missing from the allowlist the
    browser got a 400 here and cancelled the write before it reached a handler:
    on the web nobody could name a person, file an expense, or reach a split.
    The app blamed the network ("Không nối được...") while ``/healthz`` was 200,
    which sent the reader looking at Docker instead of at this list.

    This asserts what the *server* answers. It does not prove a browser then
    accepts the follow-up request; only a real browser can prove that.
    """
    response = preflight(client_factory(), WEB_BUILD_ORIGIN, headers=WRITE_HEADERS)

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == WEB_BUILD_ORIGIN

    allowed = {
        value.strip().lower()
        for value in response.headers["access-control-allow-headers"].split(",")
    }
    assert "idempotency-key" in allowed


def test_allowed_headers_covers_every_header_the_server_itself_demands():
    """The allowlist is derived from the server, not remembered by hand.

    ``Idempotency-Key`` went missing because the two halves live apart: the
    middleware in ``app.api.idempotency`` requires the header, the policy in
    ``app.api.cors`` decides whether a browser may send it, and neither file
    mentions the other. The API ended up refusing a header it demands.

    So the expected set is read back out of the server -- route signatures for
    what handlers declare, the middleware constant for what never appears in a
    signature -- and the next required header fails this case on arrival.
    """
    application = create_app()

    def collect(dependant, found):
        for param in dependant.header_params:
            found.add(param.alias.lower())
        for sub in dependant.dependencies:
            collect(sub, found)

    required = {IDEMPOTENCY_HEADER.lower()}
    for route in application.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is not None:
            collect(dependant, required)

    missing = required - {header.lower() for header in ALLOWED_HEADERS}

    assert not missing, (
        f"Máy chủ đọc header {sorted(missing)} nhưng ALLOWED_HEADERS không có; "
        "trình duyệt sẽ bị từ chối ở preflight trước khi chạm handler."
    )


def test_allowed_methods_covers_every_method_the_routers_expose(client_factory):
    """The allowlist is derived from the routers, not remembered by hand.

    ``PUT`` went missing because two pull requests merged forty seconds apart:
    one froze the method list, the next added a PUT route. Neither diff was
    wrong on its own. This case fails on the *combination*, so the next route
    that arrives with a new verb cannot slip through the same gap.
    """
    application = create_app()

    exposed = {
        method.upper()
        for route in application.routes
        for method in getattr(route, "methods", None) or ()
        # HEAD is synthesised by Starlette for every GET route and is on the
        # CORS-safelisted list, so a browser never preflights it.
        if method.upper() != "HEAD"
    }
    missing = exposed - set(ALLOWED_METHODS)

    assert not missing, (
        f"Router expose method {sorted(missing)} nhưng ALLOWED_METHODS không có; "
        "preflight của web build sẽ bị từ chối."
    )


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
