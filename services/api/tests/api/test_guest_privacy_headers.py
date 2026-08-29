"""Every answer on the guest boundary carries the same privacy headers.

The guest URL *is* the credential: the bearer token sits in the path. So an
answer to a guest request must not be kept by a shared cache, must not be
indexed, and must not carry the URL into a third party's ``Referer`` log.

Those three headers used to be a dict copied by hand into two handlers, which
left three of the seven guest routes with none of them -- and the only test
looking at any of it read two headers on one route, so nothing could notice.
"""

from __future__ import annotations

import anyio
import httpx
import pytest

from app.api.deps import get_repository
from app.api.main import create_app

from .helpers import create_batch, propose_and_confirm, publish_batch

GUEST_PRIVACY_HEADERS = {
    "cache-control": "no-store",
    "referrer-policy": "no-referrer",
    "x-robots-tag": "noindex, nofollow",
}


class _BoomRepository:
    """Every read raises: the shape of a database that has just fallen over.

    Deliberately not a route that raises on its own. The 500 has to come out of
    a real guest handler, because the layer under test is chosen by the request
    path and a hand-registered ``/g/...`` route would be answered by
    ``/g/{token}`` instead.
    """

    def __getattr__(self, name):
        raise RuntimeError("repository unavailable")


class _ServerErrorClient:
    """Reads the 500 the way a reader's browser does.

    ``ASGITestClient`` lets the exception through, which is right everywhere
    else: there the crash is the finding. Here the *response* is the subject,
    so the transport has to hand back the bytes that go over the wire.
    """

    def __init__(self, app):
        self.app = app

    def get(self, path):
        async def send():
            transport = httpx.ASGITransport(app=self.app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.get(path)

        return anyio.run(send)


@pytest.fixture
def crashing_client(monkeypatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    # Same reason as the shared `client` fixture: this runner's thread executor
    # deadlocks, and the guest page is a sync route.
    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: _BoomRepository()

    @app.get("/boom", include_in_schema=False)
    async def boom() -> None:
        raise RuntimeError("repository unavailable")

    return _ServerErrorClient(app)


def _fresh_guest_token(client, repository) -> str:
    """A published envelope per probe.

    Minted fresh each time because one of the routes under test revokes the
    link as its whole purpose; sharing a token would make every later probe
    read a revoked link instead of the route it names.
    """

    propose_and_confirm(client)
    batch = create_batch(client, repository)
    published = publish_batch(client, batch["batch_id"])
    return published["guest_links"][0]["path"].rsplit("/", 1)[-1]


def _guest_routes(client):
    return [
        (method, route.path)
        for route in client.app.routes
        if route.path.startswith("/g/")
        for method in sorted(getattr(route, "methods", None) or set())
        if method not in {"HEAD", "OPTIONS"}
    ]


def test_every_guest_route_carries_the_privacy_headers(client, repository):
    """Coverage by construction, not by a dict each handler has to remember.

    A ``/g/`` route added later is covered the moment it is registered. This
    test fails if the headers are ever narrowed back to per-handler literals.
    """

    guest_routes = _guest_routes(client)
    assert len(guest_routes) >= 7, f"route discovery looks broken: {guest_routes}"

    for method, template in guest_routes:
        token = _fresh_guest_token(client, repository)
        # The handler's own answer is irrelevant here; most of these refuse a
        # request carrying no form body. A refusal is still an answer sent to a
        # URL with the credential in it, so it needs what a 200 needs.
        kwargs = {"data": {}} if method != "GET" else {}
        response = client.request(method, template.replace("{token}", token), **kwargs)

        for header, expected in GUEST_PRIVACY_HEADERS.items():
            assert response.headers.get(header) == expected, (
                f"{method} {template} -> {response.status_code} carries "
                f"{header}={response.headers.get(header)!r}, want {expected!r}"
            )


def test_a_refused_guest_token_still_answers_with_the_privacy_headers(client):
    """The 404 for an unknown token is the most forwarded answer of all.

    Someone pasting a link into a group chat produces exactly this response for
    everyone who is not the addressee. Leaving it bare would put the URL that
    failed into the ``Referer`` of whatever they click next.
    """

    response = client.get("/g/" + "z" * 43)

    assert response.status_code == 404
    for header, expected in GUEST_PRIVACY_HEADERS.items():
        assert response.headers.get(header) == expected


def test_a_crash_under_g_still_answers_with_the_privacy_headers(crashing_client):
    """A 500 is rare, but it is still a page whose URL is the credential.

    Starlette answers an unhandled exception from ``ServerErrorMiddleware``,
    which sits *above* every middleware this app installs -- the exception
    unwinds past the privacy layer's send-wrapper, so the crash page used to go
    out bare. Bare means the reader's next click carries the token in
    ``Referer``, and a shared cache may keep the page.
    """

    response = crashing_client.get("/g/" + "a" * 43)

    assert response.status_code == 500
    for header, expected in GUEST_PRIVACY_HEADERS.items():
        assert response.headers.get(header) == expected, (
            f"500 under /g carries {header}={response.headers.get(header)!r}, "
            f"want {expected!r}"
        )


def test_a_crash_under_g_still_says_nothing_about_the_failure(crashing_client):
    """Stamping the crash page must not make it talkative.

    The headers arrive because this boundary now builds its own 500 response
    rather than letting Starlette's go out untouched -- and a response we build
    is one somebody could later decide to make helpful. Whoever holds the link
    reads whatever it says, so the body stays the exact string Starlette sends:
    no connection string, no database name, no traceback.
    """

    response = crashing_client.get("/g/" + "a" * 43)

    assert response.text == "Internal Server Error"
    assert "unavailable" not in response.text


def test_a_crash_outside_g_stays_bare(crashing_client):
    """The negative control for the 500 path.

    Without it, "the fix reaches the crash page" and "the fix stamps every
    crash page in the app" read identically green.
    """

    response = crashing_client.get("/boom")

    assert response.status_code == 500
    for header in GUEST_PRIVACY_HEADERS:
        assert response.headers.get(header) is None


@pytest.mark.parametrize("path", ["/healthz", "/openapi.json"])
def test_routes_outside_g_carry_none_of_the_privacy_headers(client, path):
    """The negative control for the happy path, same frame as #156.

    "nearly the right place" and "nearly everywhere" are the same shade of
    green without this.
    """

    response = client.get(path)

    assert response.status_code == 200
    assert [h for h in GUEST_PRIVACY_HEADERS if h in response.headers] == []
