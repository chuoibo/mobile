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

# Single source of truth: `app.api.routes.guests` mounts its router here and the
# middleware matches on the same string, so the two cannot drift apart.
GUEST_PATH_PREFIX = "/g"

GUEST_PRIVACY_HEADERS = {
    "cache-control": "no-store",
    "referrer-policy": "no-referrer",
    "x-robots-tag": "noindex, nofollow",
}


class GuestPrivacyHeadersMiddleware:
    """Pure ASGI, deliberately not ``BaseHTTPMiddleware``.

    Same reason as ``IdempotencyMiddleware``: the API is driven through the
    ASGI transport directly in tests, and ``BaseHTTPMiddleware`` adds task
    groups that deadlock there.
    """

    def __init__(self, app, prefix: str = GUEST_PATH_PREFIX):
        self.app = app
        self.prefix = prefix

    def _is_guest_path(self, path: str) -> bool:
        # `/g/...` and `/g` itself, but never `/goals`.
        return path == self.prefix or path.startswith(f"{self.prefix}/")

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
