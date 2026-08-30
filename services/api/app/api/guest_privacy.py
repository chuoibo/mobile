"""Privacy headers for the guest bearer-token boundary.

The guest URL *is* the credential -- the token is a path segment, not a header
somebody has to attach. Everything that follows comes from that one fact:

``Cache-Control: no-store``   a shared cache holding the answer holds one
                              person's envelope under a key anyone can replay.
``Referrer-Policy: no-referrer``  without it the URL travels in ``Referer`` to
                              whatever the reader clicks next, handing the
                              credential to a third party.
``X-Robots-Tag: noindex, nofollow``  a crawler that reaches one link must not
                              publish it, and must not walk to the next one.

This lives in middleware rather than in each handler for the reason the
idempotency layer does: a guest route added later is covered the moment it is
registered, with no dict for anyone to forget. It was a per-handler dict once,
and three of the seven guest routes were already going out bare.
"""

from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

# Single source of truth: `app.api.routes.guests` mounts its router here and the
# middleware matches on the same string, so the two cannot drift apart.
GUEST_PATH_PREFIX = "/g"

GUEST_PRIVACY_HEADERS = {
    "cache-control": "no-store",
    "referrer-policy": "no-referrer",
    "x-robots-tag": "noindex, nofollow",
}


def is_guest_path(path: str, prefix: str = GUEST_PATH_PREFIX) -> bool:
    """`/g/...` and `/g` itself, but never `/goals`."""

    return path == prefix or path.startswith(f"{prefix}/")


async def guest_aware_server_error_response(
    request: Request, _exc: Exception
) -> Response:
    """The one answer under `/g` the middleware below cannot reach.

    Starlette builds its stack with ``ServerErrorMiddleware`` prepended *ahead*
    of every application middleware, so an unhandled exception unwinds straight
    past the send-wrapper below -- the wrapper never sees an
    ``http.response.start`` to stamp -- and the 500 goes out from a layer above
    us, bare. Rare, but a bare crash page is still a page whose URL is the
    credential: the reader's next click carries the token in ``Referer``, and a
    shared cache is free to keep the answer.

    Registering it as the app's ``Exception`` handler is what puts it inside
    that outermost layer. The body is Starlette's own default so that a crash
    off the guest boundary is answered exactly as before; ``ServerErrorMiddleware``
    still re-raises afterwards, so nothing here swallows the traceback.

    Async on purpose: a sync handler would be dispatched through the thread
    pool, which this repository's test runner cannot use.
    """

    response = PlainTextResponse("Internal Server Error", status_code=500)
    # `scope["path"]`, not `request.url.path`: the same string the middleware
    # below matches on, so the two cannot disagree about what `/g` means.
    if is_guest_path(request.scope.get("path", "")):
        for name, value in GUEST_PRIVACY_HEADERS.items():
            response.headers[name] = value
    return response


class GuestPrivacyHeadersMiddleware:
    """Pure ASGI, deliberately not ``BaseHTTPMiddleware``.

    Same reason as ``IdempotencyMiddleware``: the API is driven through the
    ASGI transport directly in tests, and ``BaseHTTPMiddleware`` adds task
    groups that deadlock there.

    Covers every answer a handler actually produces, including the 404 for a
    revoked token. It cannot cover an unhandled exception; see
    ``guest_aware_server_error_response`` above for that one.
    """

    def __init__(self, app, prefix: str = GUEST_PATH_PREFIX):
        self.app = app
        self.prefix = prefix

    def _is_guest_path(self, path: str) -> bool:
        return is_guest_path(path, self.prefix)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self._is_guest_path(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        async def send_with_privacy_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=message["headers"])
                # Assignment, not `setdefault`: on this boundary the answer is
                # the same for every route, and a handler that disagrees is a
                # mistake rather than an override worth honouring.
                for name, value in GUEST_PRIVACY_HEADERS.items():
                    headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_privacy_headers)
