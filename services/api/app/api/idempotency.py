"""Server-side enforcement of the `Idempotency-Key` header on write requests.

The mobile client already generates a key per attempt and reuses it on retry.
That is the client protecting itself, which is not protection: the client is
precisely the party that loses the network mid-request and cannot know whether
the write landed. Only the server can answer that, and until now it did not
look at the header at all. A double tap, a flaky connection, or an automatic
retry could write the same money twice.

Shape of the guarantee
----------------------
A key is reserved by a single `INSERT ... ON CONFLICT DO NOTHING`. Exactly one
caller can win that race, whatever the number of processes or connections. The
winner runs the handler; everyone else is told what happened rather than being
allowed to run it again.

Coverage is by construction. This is ASGI middleware, so a write route added
next month is covered the moment it is registered -- there is no list anybody
has to remember to update. Requests that carry no key pass through completely
untouched, original `receive` and `send`, so existing callers and the guest
page's browser form posts behave exactly as before.

A second press is not a second request
--------------------------------------
Two things decide whether the caller's *second* press is answered honestly, and
both were learned from a real server rather than from a dict:

*Order.* The answer is not handed to the caller until the completion has been
recorded. Sending first and bookkeeping afterwards leaves a window in which the
key reads as unfinished, and a thumb is faster than that window: pressing again
the instant the first answer landed was refused four times out of four, while
waiting 50ms was fine. "Be slower" is not something a phone can promise, so the
window is closed by ordering instead.

*Waiting.* Two presses can also arrive at the same instant -- a double render, a
retry racing the original. Exactly one wins the reservation; the loser is the
same request, and the only true answer for it is the winner's. So it waits for
that answer, briefly and with a bounded budget, rather than being refused.

Refusing either case is worse than it looks. It puts a 409 in front of somebody
who did nothing wrong, and an error that invites a fresh key is an invitation to
write the same money twice -- the one thing this file exists to prevent.

The one gap, stated plainly
---------------------------
The completion row is written *after* the request's own transaction has already
committed. If the process dies inside that window, the money is written but the
key stays reserved. A retry then waits out the budget and is told to stop.

That direction is deliberate. The failure mode is "the caller is told to stop
and ask a human", never "the money is written twice". Closing the window
completely means the request transaction itself must own the idempotency row,
which changes transaction ownership for every route and is an ADR-level
decision, not something to smuggle in here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Protocol

import anyio
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.schemas import ErrorResponse
from app.db.models import IdempotencyKey

IDEMPOTENCY_HEADER = "Idempotency-Key"
REPLAY_HEADER = "Idempotency-Replayed"
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

ANONYMOUS_SCOPE = "anonymous"
MAX_KEY_LENGTH = 255

# How long a caller who lost the reservation race waits for the winner's answer
# before being refused. Long enough to cover a write request that is merely
# slow; short enough that a key abandoned by a dead process does not hold a
# connection hostage.
DEFAULT_IN_FLIGHT_WAIT_SECONDS = 5.0
_FIRST_POLL_SECONDS = 0.02
_MAX_POLL_SECONDS = 0.1

_HEADER_BYTES = IDEMPOTENCY_HEADER.lower().encode("latin-1")
_ACTOR_HEADER_BYTES = b"x-actor-id"
_AUTH_HEADER_BYTES = b"authorization"


@dataclass(frozen=True, slots=True)
class StoredResponse:
    """The answer that was actually sent, kept verbatim for replay."""

    status_code: int
    body: bytes
    media_type: str | None


@dataclass(frozen=True, slots=True)
class Reserved:
    """This caller owns the key and must run the handler."""


@dataclass(frozen=True, slots=True)
class Replay:
    """The key already completed; return the recorded answer."""

    response: StoredResponse


@dataclass(frozen=True, slots=True)
class InFlight:
    """The key is reserved but never completed. Refuse rather than guess."""


@dataclass(frozen=True, slots=True)
class Conflict:
    """The key was used before for a different request."""


Outcome = Reserved | Replay | InFlight | Conflict


class IdempotencyStore(Protocol):
    def reserve(
        self,
        *,
        scope: str,
        key: str,
        fingerprint: str,
        legacy_fingerprint: str | None = None,
    ) -> Outcome: ...

    def complete(self, *, scope: str, key: str, response: StoredResponse) -> None: ...

    def release(self, *, scope: str, key: str) -> None: ...


IdempotencyStoreFactory = Callable[[], AbstractContextManager[IdempotencyStore]]


class SqlAlchemyIdempotencyStore:
    """PostgreSQL-backed store. One instance per transaction."""

    __slots__ = ("_session",)

    def __init__(self, session: Session):
        self._session = session

    def reserve(
        self,
        *,
        scope: str,
        key: str,
        fingerprint: str,
        legacy_fingerprint: str | None = None,
    ) -> Outcome:
        # A single statement decides the race. Written as SELECT-then-INSERT
        # this would let two concurrent requests both believe they were first,
        # which is the exact bug the feature exists to prevent.
        statement = (
            insert(IdempotencyKey)
            .values(scope=scope, idempotency_key=key, request_fingerprint=fingerprint)
            .on_conflict_do_nothing(index_elements=["scope", "idempotency_key"])
            .returning(IdempotencyKey.id)
        )
        if self._session.execute(statement).scalar_one_or_none() is not None:
            return Reserved()

        existing = self._session.execute(
            select(
                IdempotencyKey.request_fingerprint,
                IdempotencyKey.response_status,
                IdempotencyKey.response_body,
                IdempotencyKey.response_media_type,
            ).where(
                IdempotencyKey.scope == scope,
                IdempotencyKey.idempotency_key == key,
            )
        ).one_or_none()

        if existing is None:
            # The row vanished between the insert and the read: another caller
            # released it. Refusing is the safe direction; the client retries.
            return InFlight()

        stored_fingerprint, status_code, body, media_type = existing
        if stored_fingerprint != fingerprint:
            if legacy_fingerprint is None or stored_fingerprint != legacy_fingerprint:
                return Conflict()
            # The row was written by a server that hashed the body verbatim, and
            # it hashed *these* bytes: same request, older spelling. Adopting the
            # canonical digest is what lets a differently-encoding client replay
            # it afterwards, so a database that was seeded before this change
            # heals on the next write instead of refusing the app forever.
            self._session.execute(
                update(IdempotencyKey)
                .where(
                    IdempotencyKey.scope == scope,
                    IdempotencyKey.idempotency_key == key,
                )
                .values(request_fingerprint=fingerprint)
            )
        if status_code is None:
            return InFlight()
        return Replay(
            StoredResponse(
                status_code=status_code,
                body=bytes(body or b""),
                media_type=media_type,
            )
        )

    def complete(self, *, scope: str, key: str, response: StoredResponse) -> None:
        self._session.execute(
            update(IdempotencyKey)
            .where(
                IdempotencyKey.scope == scope,
                IdempotencyKey.idempotency_key == key,
            )
            .values(
                response_status=response.status_code,
                response_body=response.body,
                response_media_type=response.media_type,
                completed_at=func.now(),
            )
        )

    def release(self, *, scope: str, key: str) -> None:
        self._session.execute(
            delete(IdempotencyKey).where(
                IdempotencyKey.scope == scope,
                IdempotencyKey.idempotency_key == key,
            )
        )


def _declares_json(content_type: str | None) -> bool:
    if not content_type:
        return False
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")


def _canonical_body(body: bytes, content_type: str | None) -> bytes:
    """The body reduced to its meaning, for callers who declared JSON.

    Sorting object keys and dropping insignificant whitespace is what makes the
    digest a property of the request rather than of the library that encoded
    it. Arrays are left alone: their order is meaning, and `participants` is
    the list that decides who owes money.
    """

    if not _declares_json(content_type):
        return body
    try:
        parsed = json.loads(body)
    except ValueError:
        # It said JSON and it is not. The route will refuse it in a moment; all
        # the digest has to do is stay stable, so hash what actually arrived.
        return body
    return json.dumps(
        parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def request_fingerprint(
    *,
    method: str,
    path: str,
    query: bytes,
    body: bytes,
    content_type: str | None = None,
) -> str:
    """Identify the request a key was spent on.

    Method and path are part of the digest on purpose: the same key sent to a
    different endpoint is a client bug, and answering it with a replay of an
    unrelated call would hide that bug behind a plausible response.

    The body is canonicalised rather than hashed verbatim when the caller
    declares JSON, because two encoders agree on the value and disagree on the
    bytes:

        Python  json.dumps     -> {"display_name": "Team \\u0110\\u00e0 L\\u1ea1t"}
        JS      JSON.stringify -> {"display_name":"Team Đà Lạt"}

    Hashing those bytes made the digest a property of the *encoder*, so a key
    spent by the seed script could never be replayed by the app -- the second
    attempt was refused as reuse for a request nobody had made. Note that this
    was never only a non-ASCII problem: the space after the colon is enough on
    its own, so every JSON write crossing an encoder boundary was affected.

    Omitting `content_type` reproduces the raw-bytes digest an older version of
    this file wrote. That is not a leftover -- see `reserve`, which needs it to
    recognise the rows that version left in the table.
    """

    digest = hashlib.sha256()
    digest.update(method.encode("utf-8"))
    digest.update(b"\n")
    digest.update(path.encode("utf-8"))
    digest.update(b"\n")
    digest.update(query)
    digest.update(b"\n")
    digest.update(_canonical_body(body, content_type))
    return digest.hexdigest()


@dataclass(slots=True)
class _CapturedResponse:
    status_code: int = 0
    media_type: str | None = None
    chunks: list[bytes] = field(default_factory=list)
    # The raw ASGI messages, kept so the caller can be answered with exactly
    # what the route produced once the key has been settled.
    messages: list[dict] = field(default_factory=list)

    def body(self) -> bytes:
        return b"".join(self.chunks)


def _bearer_scope(authorization: str | None) -> str | None:
    """`bearer:<sha256>` for an `Authorization: Bearer x` header, else None."""
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    token = value.strip()
    if scheme.lower() != "bearer" or not token:
        return None
    return "bearer:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def _header(headers: list[tuple[bytes, bytes]], name: bytes) -> str | None:
    for raw_name, raw_value in headers:
        if raw_name.lower() == name:
            return raw_value.decode("latin-1")
    return None


class IdempotencyMiddleware:
    """Pure ASGI. Deliberately not `BaseHTTPMiddleware`.

    The API is driven through the ASGI transport directly in tests because
    Starlette's synchronous client deadlocks in this environment, and
    `BaseHTTPMiddleware` adds its own task groups on top of that. Owning
    `receive` and `send` here is also what makes the no-key path a genuine
    pass-through instead of a buffered copy.
    """

    def __init__(
        self,
        app,
        store_factory: IdempotencyStoreFactory,
        in_flight_wait_seconds: float = DEFAULT_IN_FLIGHT_WAIT_SECONDS,
    ):
        self.app = app
        self.store_factory = store_factory
        self.in_flight_wait_seconds = in_flight_wait_seconds

    async def _reserve(
        self,
        *,
        key_scope: str,
        key: str,
        fingerprint: str,
        legacy_fingerprint: str | None = None,
    ) -> Outcome:
        """Reserve the key, waiting out a reservation somebody else is finishing.

        A reserved-but-unfinished key means one of two things, and the store
        cannot tell them apart: a request that is still running, or one whose
        process died. Waiting distinguishes them by outcome instead of by
        guesswork -- the live one completes and this caller replays its answer,
        the dead one never does and the budget runs out.

        Each attempt takes its own short transaction. Holding one open across
        the wait would keep a connection busy doing nothing and, worse, would
        pin a snapshot in which the winner's commit can never appear.
        """

        deadline = anyio.current_time() + self.in_flight_wait_seconds
        delay = _FIRST_POLL_SECONDS
        while True:
            with self.store_factory() as store:
                outcome = store.reserve(
                    scope=key_scope,
                    key=key,
                    fingerprint=fingerprint,
                    legacy_fingerprint=legacy_fingerprint,
                )
            if not isinstance(outcome, InFlight):
                return outcome
            remaining = deadline - anyio.current_time()
            if remaining <= 0:
                return outcome
            await anyio.sleep(min(delay, remaining))
            delay = min(delay * 2, _MAX_POLL_SECONDS)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope["method"] not in WRITE_METHODS:
            await self.app(scope, receive, send)
            return

        headers = scope.get("headers") or []
        key = _header(headers, _HEADER_BYTES)
        if key is None:
            await self.app(scope, receive, send)
            return

        if not key or len(key) > MAX_KEY_LENGTH:
            await _send_problem(
                send,
                422,
                "invalid_idempotency_key",
                f"{IDEMPOTENCY_HEADER} must be 1..{MAX_KEY_LENGTH} characters",
            )
            return

        body = await _drain(receive)
        # Scope by WHO is writing. Under `prod` nobody sends `X-Actor-ID`, so the
        # old actor-only scope collapsed every bearer holder into "anonymous" and
        # two people reusing the same client-minted key collided. The bearer is
        # digested, never stored raw, for the same reason `account_sessions`
        # stores a digest.
        bearer = _bearer_scope(_header(headers, _AUTH_HEADER_BYTES))
        actor = _header(headers, _ACTOR_HEADER_BYTES)
        key_scope = bearer or actor or ANONYMOUS_SCOPE
        parts = {
            "method": scope["method"],
            "path": scope["path"],
            "query": scope.get("query_string", b""),
            "body": body,
        }
        fingerprint = request_fingerprint(
            **parts, content_type=_header(headers, b"content-type")
        )
        # The same bytes as an older server would have digested them. Passed
        # alongside so a key reserved before this change is still recognised as
        # the request it was, rather than refused as reuse.
        legacy_fingerprint = request_fingerprint(**parts)
        if legacy_fingerprint == fingerprint:
            legacy_fingerprint = None

        outcome = await self._reserve(
            key_scope=key_scope,
            key=key,
            fingerprint=fingerprint,
            legacy_fingerprint=legacy_fingerprint,
        )

        if isinstance(outcome, Conflict):
            await _send_problem(
                send,
                422,
                "idempotency_key_reuse",
                f"{IDEMPOTENCY_HEADER} was already used for a different request",
            )
            return
        if isinstance(outcome, InFlight):
            # Deliberately does not suggest a fresh key. A fresh key is
            # permission to write the same money a second time, which is the
            # failure this whole file is here to make impossible. Retrying the
            # same key is always safe: it either replays or refuses again.
            await _send_problem(
                send,
                409,
                "idempotency_request_in_flight",
                "An earlier request with this key has not finished. Retry with"
                " this same key; sending a different one would write it twice",
            )
            return
        if isinstance(outcome, Replay):
            await _send_stored(send, outcome.response)
            return

        captured = _CapturedResponse()

        async def capturing_send(message) -> None:
            # Held, not forwarded. Handing the caller their answer here would
            # leave the key reading as unfinished for as long as the completion
            # takes to commit, and a second press inside that window is refused
            # for something nobody did wrong.
            if message["type"] == "http.response.start":
                captured.status_code = message["status"]
                captured.media_type = _header(
                    list(message.get("headers") or []), b"content-type"
                )
            elif message["type"] == "http.response.body":
                chunk = message.get("body") or b""
                if chunk:
                    captured.chunks.append(chunk)
            captured.messages.append(message)

        try:
            await self.app(scope, _replaying(body), capturing_send)
        except BaseException:
            # Nothing committed: the repository dependency rolls its
            # transaction back on the way out. Free the key so the client's
            # retry is a real second attempt rather than a permanent 409.
            # Nothing was forwarded either, so there is no half-sent answer.
            with self.store_factory() as store:
                store.release(scope=key_scope, key=key)
            raise

        if 200 <= captured.status_code < 300:
            with self.store_factory() as store:
                store.complete(
                    scope=key_scope,
                    key=key,
                    response=StoredResponse(
                        status_code=captured.status_code,
                        body=captured.body(),
                        media_type=captured.media_type,
                    ),
                )
        else:
            with self.store_factory() as store:
                store.release(scope=key_scope, key=key)

        # Only now, with the key settled either way, does the caller get to see
        # anything. Messages go out verbatim and in order: rebuilding them here
        # would let this middleware quietly answer in a different dialect from
        # the route that produced them.
        for message in captured.messages:
            await send(message)


async def _drain(receive) -> bytes:
    chunks: list[bytes] = []
    more_body = True
    while more_body:
        message = await receive()
        if message["type"] != "http.request":
            break
        chunk = message.get("body") or b""
        if chunk:
            chunks.append(chunk)
        more_body = message.get("more_body", False)
    return b"".join(chunks)


def _replaying(body: bytes):
    """Hand the buffered body to the downstream app exactly once."""

    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return receive


async def _send_stored(send, response: StoredResponse) -> None:
    headers = [
        (b"content-length", str(len(response.body)).encode("latin-1")),
        (REPLAY_HEADER.lower().encode("latin-1"), b"true"),
    ]
    if response.media_type:
        headers.append((b"content-type", response.media_type.encode("latin-1")))
    await send(
        {
            "type": "http.response.start",
            "status": response.status_code,
            "headers": headers,
        }
    )
    await send({"type": "http.response.body", "body": response.body})


async def _send_problem(send, status_code: int, code: str, detail: str) -> None:
    # Built from the same model the routes use, so a change to the wire shape of
    # an error cannot leave the middleware answering in an older dialect.
    body = json.dumps(ErrorResponse(code=code, detail=detail).model_dump()).encode(
        "utf-8"
    )
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("latin-1")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
