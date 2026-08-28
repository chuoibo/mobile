"""Cross-origin policy for browser clients.

The native app sends no ``Origin`` header and is unaffected by any of this. The
web build is not: a browser preflights every request that carries ``X-Actor-ID``,
and a response the browser cannot attribute to an allowed origin is discarded
before the app ever sees it.

The policy is an allowlist, never a wildcard by default. Actor identity travels
in plain headers that a trusted gateway is supposed to overwrite (see
``app.api.deps``), so the set of pages allowed to talk to this API is a decision
an operator makes on purpose, not one this module makes for them.
"""

from __future__ import annotations

import os
from collections.abc import Iterable

from starlette.datastructures import Headers
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response

ORIGINS_ENV_VAR = "MOBILE_CORS_ALLOW_ORIGINS"

# Fallback for local development only. Any port, because Expo chooses its own
# and pinning one here would break on the next run; loopback only, because the
# fallback must not become a way to ship an open API by forgetting a variable.
LOOPBACK_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

# The headers the client actually sends; anything unlisted fails preflight.
# Content-Type is also on Starlette's safelist, so it ends up in the response
# twice. Listing it anyway keeps this module the full answer to "what may the
# browser send", instead of half of it plus a library's default.
ALLOWED_HEADERS = [
    "content-type",
    "x-actor-id",
    "x-actor-roles",
    "x-actor-contexts",
]

# The methods the routers expose, plus the preflight itself.
ALLOWED_METHODS = ["GET", "POST", "DELETE", "OPTIONS"]

PREFLIGHT_MAX_AGE_SECONDS = 600

_BODY_HEADERS = frozenset({"content-type", "content-length"})


def parse_origins(raw: str | None) -> list[str]:
    """Read the configured allowlist. Blank and unset both mean "not set"."""
    if raw is None:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


class PreflightNoContentCORSMiddleware(CORSMiddleware):
    """Answer a successful preflight with 204 instead of 200 and an "OK" body.

    A preflight response carries no payload; sending one invites a client to
    parse it. Failed preflights keep Starlette's 400 and its explanation,
    because that text is the only clue an operator gets about which origin,
    method, or header was refused.
    """

    def preflight_response(self, request_headers: Headers) -> Response:
        response = super().preflight_response(request_headers)
        if response.status_code != 200:
            return response
        headers = {
            name: value
            for name, value in response.headers.items()
            if name.lower() not in _BODY_HEADERS
        }
        return Response(status_code=204, headers=headers)


def cors_options(raw_origins: str | None) -> dict[str, object]:
    """Middleware keyword arguments for a given configuration value."""
    origins = parse_origins(raw_origins)
    return {
        "allow_origins": origins,
        # Exactly one source of allowed origins: naming any origin drops the
        # loopback fallback, so a deployment cannot keep it by accident.
        "allow_origin_regex": None if origins else LOOPBACK_ORIGIN_REGEX,
        "allow_methods": ALLOWED_METHODS,
        "allow_headers": ALLOWED_HEADERS,
        # No cookies, no HTTP auth: this API authenticates on headers the
        # client sets explicitly. Allowing credentials would let an already
        # authenticated browser session be driven from another page.
        "allow_credentials": False,
        "max_age": PREFLIGHT_MAX_AGE_SECONDS,
    }


def install_cors(application, raw_origins: str | None = None) -> None:
    """Attach the policy, reading the environment unless told otherwise."""
    if raw_origins is None:
        raw_origins = os.environ.get(ORIGINS_ENV_VAR)
    application.add_middleware(
        PreflightNoContentCORSMiddleware, **cors_options(raw_origins)
    )


__all__: Iterable[str] = (
    "ALLOWED_HEADERS",
    "ALLOWED_METHODS",
    "LOOPBACK_ORIGIN_REGEX",
    "ORIGINS_ENV_VAR",
    "PreflightNoContentCORSMiddleware",
    "cors_options",
    "install_cors",
    "parse_origins",
)
