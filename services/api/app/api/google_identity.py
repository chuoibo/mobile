"""Google ID tokens as a door (ADR-0016), verified here and nowhere else.

The phone asks Google for an ID token (`@react-native-google-signin`, with the
Web client id so a token is issued at all) and hands it to `POST /auth/google`.
This module is the only place the server decides whether that token is real:
signature against Google's published certificates, issuer, expiry, and an
audience that is one of OUR client ids. The Android and Web client ids are
both ours, so the audience check is a set, not a string.

## What comes out, and what deliberately does not

`GoogleClaims` carries the stable `sub` and a display name. It does not carry
the e-mail address, and that is the design rather than an omission: ADR-0016
forbids merging accounts by e-mail, and the surest way to keep a future change
from doing it "just this once" is for the address never to reach the service
layer. A Google `sub` seen for the first time is a new person.

## The seam

`GoogleTokenVerifier` is a Protocol so tests can hand the route a verifier
that answers from a table, exactly as `SmsSender` lets the OTP tests read the
code from a recording fake. `build_google_verifier` returns `None` when no
client id is configured, and the route answers 503 `google_not_configured`
before it looks at the token -- a host without ids has no Google door, and it
says so instead of failing the token.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

CLIENT_IDS_ENV = "MOBILE_GOOGLE_CLIENT_IDS"
ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})
# Google's own guidance for server-side verification; covers a phone whose
# clock is a few seconds off without accepting a token that is minutes old.
CLOCK_SKEW_SECONDS = 10


class GoogleTokenInvalid(ValueError):
    """The token is not one Google issued for this application, or is stale."""


@dataclass(frozen=True)
class GoogleClaims:
    """What the service is allowed to know about a verified token."""

    subject: str
    display_name: str | None


class GoogleTokenVerifier(Protocol):
    def verify(self, id_token: str) -> GoogleClaims: ...


def claims_from(payload: dict, client_ids: frozenset[str]) -> GoogleClaims:
    """Reduce a verified JWT payload to `GoogleClaims`, or refuse it.

    Pure, so the audience/issuer/subject rules are testable without a token
    signed by Google. `verify_oauth2_token` already checks the issuer and the
    signature; the checks are repeated here because a verifier that skipped
    them (a test double, a future library swap) must not be able to pass a
    payload through.
    """
    aud = payload.get("aud")
    if not isinstance(aud, str) or aud not in client_ids:
        raise GoogleTokenInvalid("audience is not one of this server's client ids")
    if payload.get("iss") not in ISSUERS:
        raise GoogleTokenInvalid("issuer is not Google")
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise GoogleTokenInvalid("token carries no subject")
    name = payload.get("name")
    display_name = name.strip() if isinstance(name, str) and name.strip() else None
    return GoogleClaims(subject=sub.strip(), display_name=display_name)


class GoogleAuthLibraryVerifier:
    """`google-auth` doing the cryptography; this class doing the policy."""

    def __init__(self, client_ids: frozenset[str]) -> None:
        if not client_ids:
            raise ValueError("a Google verifier needs at least one client id")
        self.client_ids = client_ids

    def verify(self, id_token: str) -> GoogleClaims:
        # Imported here so the module (and `claims_from`) load without the
        # library present, and so a test of the policy does not pay for it.
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token

        try:
            payload = google_id_token.verify_oauth2_token(
                id_token,
                google_requests.Request(),
                # Audience is checked by `claims_from` against the whole set;
                # the library only accepts a single string here.
                audience=None,
                clock_skew_in_seconds=CLOCK_SKEW_SECONDS,
            )
        except ValueError as broken:
            # Expired, bad signature, wrong issuer, malformed: the library says
            # which, and the person on the phone must not -- one 401 for all.
            raise GoogleTokenInvalid(str(broken)) from broken
        return claims_from(payload, self.client_ids)


def build_google_verifier(environ) -> GoogleTokenVerifier | None:
    """The verifier for this host, or `None` when no client id is configured."""
    raw = (environ.get(CLIENT_IDS_ENV) or "").strip()
    ids = frozenset(part.strip() for part in raw.split(",") if part.strip())
    if not ids:
        return None
    return GoogleAuthLibraryVerifier(ids)
