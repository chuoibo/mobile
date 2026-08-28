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

The one gap, stated plainly
---------------------------
The completion row is written *after* the request's own transaction has already
committed. If the process dies inside that window, the money is written but the
key stays reserved, and the retry gets 409 rather than a replay of the original
answer.

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

_HEADER_BYTES = IDEMPOTENCY_HEADER.lower().encode("latin-1")
_ACTOR_HEADER_BYTES = b"x-actor-id"


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
    def reserve(self, *, scope: str, key: str, fingerprint: str) -> Outcome: ...

    def complete(
        self, *, scope: str, key: str, response: StoredResponse
    ) -> None: ...

    def release(self, *, scope: str, key: str) -> None: ...


IdempotencyStoreFactory = Callable[[], AbstractContextManager[IdempotencyStore]]


class SqlAlchemyIdempotencyStore:
    """PostgreSQL-backed store. One instance per transaction."""

    __slots__ = ("_session",)

    def __init__(self, session: Session):
        self._session = session

    def reserve(self, *, scope: str, key: str, fingerprint: str) -> Outcome:
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
            return Conflict()
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


def request_fingerprint(*, method: str, path: str, query: bytes, body: bytes) -> str:
    """Identify the request a key was spent on.

    Method and path are part of the digest on purpose: the same key sent to a
    different endpoint is a client bug, and answering it with a replay of an
    unrelated call would hide that bug behind a plausible response.
    """

    digest = hashlib.sha256()
    digest.update(method.encode("utf-8"))
    digest.update(b"\n")
    digest.update(path.encode("utf-8"))
    digest.update(b"\n")
    digest.update(query)
    digest.update(b"\n")
    digest.update(body)
    return digest.hexdigest()


@dataclass(slots=True)
class _CapturedResponse:
    status_code: int = 0
    media_type: str | None = None
    chunks: list[bytes] = field(default_factory=list)

    def body(self) -> bytes:
        return b"".join(self.chunks)


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

    def __init__(self, app, store_factory: IdempotencyStoreFactory):
        self.app = app
        self.store_factory = store_factory

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
        actor = _header(headers, _ACTOR_HEADER_BYTES)
        key_scope = actor if actor else ANONYMOUS_SCOPE
        fingerprint = request_fingerprint(
            method=scope["method"],
            path=scope["path"],
            query=scope.get("query_string", b""),
            body=body,
        )

        with self.store_factory() as store:
            outcome = store.reserve(
                scope=key_scope, key=key, fingerprint=fingerprint
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
            await _send_problem(
                send,
                409,
                "idempotency_request_in_flight",
                "An earlier request with this key never finished; use a new key",
            )
            return
        if isinstance(outcome, Replay):
            await _send_stored(send, outcome.response)
            return

        captured = _CapturedResponse()

        async def capturing_send(message) -> None:
            if message["type"] == "http.response.start":
                captured.status_code = message["status"]
                captured.media_type = _header(
                    list(message.get("headers") or []), b"content-type"
                )
            elif message["type"] == "http.response.body":
                chunk = message.get("body") or b""
                if chunk:
                    captured.chunks.append(chunk)
            await send(message)

        try:
            await self.app(scope, _replaying(body), capturing_send)
        except BaseException:
            # Nothing committed: the repository dependency rolls its
            # transaction back on the way out. Free the key so the client's
            # retry is a real second attempt rather than a permanent 409.
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
            return

        with self.store_factory() as store:
            store.release(scope=key_scope, key=key)


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
