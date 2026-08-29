"""Every answer on the guest boundary carries the same privacy headers.

The guest URL *is* the credential: the bearer token sits in the path. So an
answer to a guest request must not be kept by a shared cache, must not be
indexed, and must not carry the URL into a third party's ``Referer`` log.

Those three headers used to be a dict copied by hand into two handlers, which
left three of the seven guest routes with none of them -- and the only test
looking at any of it read two headers on one route, so nothing could notice.
"""

from __future__ import annotations

from .helpers import create_batch, propose_and_confirm, publish_batch

GUEST_PRIVACY_HEADERS = {
    "cache-control": "no-store",
    "referrer-policy": "no-referrer",
    "x-robots-tag": "noindex, nofollow",
}


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
