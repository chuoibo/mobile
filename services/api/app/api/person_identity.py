"""Turning a telephone number into the person id the database stores.

This used to live in the app, in `apps/mobile/src/screens/vao-cua/danh-tinh.ts`,
as FNV-1a fed through MurmurHash3's finaliser. Everything about that hash was
good except the only property that mattered.

## Why it moved, in numbers

`GET /contexts/{id}/members` returns every member's `person_id` to every member.
When the id is an unkeyed function of the number, anybody holding an id and a
clone of this repository can enumerate the input space until an id matches, and
Vietnamese mobile numbers are a space of about 5x10^8 -- small. Measured on the
shipped client before this change: 257,316 candidates/second in Node on one
core, which recovered a number from its id in 29.75 seconds. QA measured
142,630/second in Python and put the whole space at about an hour, or seconds in
C. Both are the same finding: a member of your group can read every other
member's telephone number.

The hash was not weak. `tests/danh-tinh.test.mjs` proved 20,000 consecutive
numbers gave 20,000 distinct ids and that neighbouring numbers came out half a
digest apart -- real avalanche, honestly measured. Avalanche is not preimage
resistance, and over a small input space no unkeyed digest has the second
property no matter how well it has the first. Only a secret the attacker does
not hold changes that arithmetic, which is what this module adds.

## What is protected and what is not

The derivation is HMAC-SHA256 under a key that exists only in the server's
environment. Given an id and this entire file, recovering the number needs the
key; the enumeration above becomes an attack on a 256-bit secret instead of on
a nine-digit number.

Two things are honestly worse than before, and both are deliberate trades:

  - The digits now cross the wire. They are in a POST body, never in a path or
    a query string, so they do not reach uvicorn's access log. Nothing here
    logs them and nothing stores them: no column, no cache, no file.
  - This module is an oracle. Anyone who can call the route can ask it to
    derive an id for a number they choose, so a determined attacker can rebuild
    the reverse map by querying rather than by computing. That is why the route
    is rate limited (`RATE_LIMIT` below). A limit is a cost, not a wall: it
    turns a 30-second offline sweep into days of visible traffic. Removing the
    oracle entirely needs a login the product does not have yet, which is the
    same sentence `api/deps.py` writes about `X-Actor-ID`.

The alternative design -- a random uuid stored beside a lookup column -- was
not chosen because the lookup column has to be derived from the number too, so
it needs this same key AND a table AND a migration, and it puts a
number-shaped value in a database dump that today has none.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from uuid import UUID

__all__ = [
    "KEY_ENV_VAR",
    "MIN_KEY_LENGTH",
    "PersonIdKeyMissing",
    "canonical_mobile",
    "derive_person_id",
    "read_key",
]

#: The environment variable the key is read from. Declared in `.env.example`
#: under exactly this name. #89 shipped an example file naming
#: `MOBILE_GEMINI_API_KEY` while the code read `GEMINI_API_KEY`, so anybody who
#: followed the instructions ended up with a key that looked set and was never
#: read; `tests/api/test_person_identity.py` pins this constant against the
#: example file so that cannot happen twice.
KEY_ENV_VAR = "MOBILE_PERSON_ID_KEY"

#: A short key is brute-forceable in its own right, which would restore exactly
#: the hole this module exists to close -- an attacker who guesses the key gets
#: the whole reverse map, not one number. 32 characters is the floor, and the
#: example file tells the reader to generate it rather than to invent it.
MIN_KEY_LENGTH = 32

#: Separates these ids from any other HMAC computed with the same key, and
#: names the scheme so a future change is a new version rather than a silent
#: reinterpretation of stored rows. `v2` because `v1` was the unkeyed client
#: derivation this replaces.
DOMAIN = b"ru-di:nguoi:v2:"

#: Vietnamese mobile numbers, after the trunk zero or the country code has been
#: taken off: nine digits starting with a mobile prefix. Landlines and short
#: codes are refused rather than accepted-and-derived, because an id derived
#: from something that is not a mobile number is an account nobody can log back
#: into. The client applies the same rule in `danh-tinh.ts` so the refusal can
#: be explained while somebody is still typing; this copy is the one that
#: decides, because the client's copy is advice a caller can skip.
_MOBILE = re.compile(r"^[35789]\d{8}$")

#: Only the separators people use for legibility. Letters are not stripped:
#: they make the input invalid, and quietly deleting them would turn a typo
#: into a different person's account.
_SEPARATORS = re.compile(r"[\s.\-()]")


class PersonIdKeyMissing(RuntimeError):
    """The server has no key, so it cannot mint an id.

    Raised rather than falling back to an unkeyed digest. A fallback would be
    the old vulnerability, reappearing exactly when nobody configured the fix,
    and it would mint ids indistinguishable from good ones.
    """


def read_key(environ: object | None = None) -> bytes:
    """The signing key, or `PersonIdKeyMissing`.

    Read on every call rather than captured at import: tests set and unset it,
    and a module-level snapshot would make the first import of the process
    decide the answer for the rest of it.

    The key is never in the exception message. A `RuntimeError` reaching a log
    with the secret interpolated into it would leak the one value this module
    keeps.
    """

    env = os.environ if environ is None else environ
    raw = env.get(KEY_ENV_VAR, "").strip()  # type: ignore[union-attr]
    if not raw:
        raise PersonIdKeyMissing(
            f"{KEY_ENV_VAR} is not set; person ids cannot be derived"
        )
    if len(raw) < MIN_KEY_LENGTH:
        raise PersonIdKeyMissing(
            f"{KEY_ENV_VAR} is shorter than {MIN_KEY_LENGTH} characters"
        )
    return raw.encode("utf-8")


def canonical_mobile(raw: str) -> str | None:
    """`84` followed by nine digits, or None.

    A trunk zero, a `+84`, a bare `84`, and any mixture of spaces, dots, dashes
    and brackets between the digits all describe one telephone and so must
    reach one account. Without this, the same person typing their own number
    with a space one day and without it the next arrives at two ids and two
    halves of their own money.
    """

    packed = _SEPARATORS.sub("", raw)
    if not packed:
        return None

    if packed.startswith("+84"):
        rest = packed[3:]
    elif packed.startswith("84"):
        rest = packed[2:]
    elif packed.startswith("0"):
        rest = packed[1:]
    else:
        rest = packed

    if not _MOBILE.fullmatch(rest):
        return None
    return "84" + rest


def derive_person_id(canonical: str, key: bytes) -> UUID:
    """The person id for a canonical number under a key.

    Same number and same key give the same id on every machine, which is the
    whole of "typing my number twice logs me back in". Different keys give
    unrelated ids, which is why rotating the key is an account migration and
    not a configuration change.

    Version nibble `8` -- RFC 9562's "custom" version, which is what this is.
    Claiming v4 would be a lie told to anybody reading a row in `people`, and
    claiming v5 would be a lie about the digest. The variant bits are forced to
    `10` so the value is a well-formed UUID.
    """

    digest = hmac.new(key, DOMAIN + canonical.encode("ascii"), hashlib.sha256).digest()
    raw = bytearray(digest[:16])
    raw[6] = (raw[6] & 0x0F) | 0x80  # version 8
    raw[8] = (raw[8] & 0x3F) | 0x80  # RFC 9562 variant
    return UUID(bytes=bytes(raw))
