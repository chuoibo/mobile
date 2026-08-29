"""The one route that mints a person id from a telephone number.

`PUT /people/{id}` names an id the caller already holds; this is where the
caller gets one. It exists because the derivation had to become keyed, and a
key the client holds is not a key -- see `app/api/person_identity.py` for the
measurement that forced the move.

Three things about this handler are deliberate and would each be a leak if
written the ordinary way.

**The body is parsed by hand.** FastAPI's validation error echoes the offending
value. A caller who posts `phone` as a JSON *number* rather than a string gets
that number straight back in the 422, under an `"input"` key -- so the refusal
is a telephone number, in whatever logs or bug reports the caller's side keeps.
Measured against this very app, not assumed. So this handler reads the JSON
itself and every refusal it writes is a fixed sentence.
`tests/api/test_identity_route.py` posts exactly that malformed body and
asserts no long digit run appears in the answer.

No example number is written in this file, here or anywhere: `repo_guard.py`
refuses digit runs that look like telephone numbers and cannot tell an
invented one from somebody's real one.

**Nothing is logged and nothing is stored.** No column, no cache, no file. The
number exists for the length of one HMAC. uvicorn's access log records method
and path only, which is why the number is in the body and not in the path.

**No actor header.** Somebody signing in does not have an id yet -- asking for
one here would be asking for the thing being requested. That makes the route
unauthenticated, which makes it an oracle, which is why it is rate limited.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import APIRouter, Request

from app.api.errors import ApiProblem
from app.api.person_identity import (
    PersonIdKeyMissing,
    canonical_mobile,
    derive_person_id,
    read_key,
)
from app.api.schemas import ErrorResponse, PersonIdResponse

router = APIRouter(tags=["identity"])

#: Signing in is one request. Twenty a minute leaves room for a person
#: fat-fingering their number several times and for a demo where several
#: phones share one NAT address, while making the enumeration attack in
#: `person_identity.py` cost about 10^7 minutes instead of 30 seconds.
RATE_LIMIT = 20
RATE_WINDOW_SECONDS = 60.0

#: Above this many distinct callers in one window the table is dropped rather
#: than grown. An unauthenticated endpoint that allocates one dict entry per
#: source address is a memory exhaustion bug wearing a rate limiter's clothes.
_MAX_TRACKED = 10_000


class FixedWindowLimit:
    """Requests per source address per window, in memory.

    In memory and therefore per process: two uvicorn workers allow twice this,
    and a restart forgets everything. That is the honest shape of it. The
    alternative is a shared store, which is a dependency this slice does not
    have, and the number it protects is a cost multiplier rather than a
    boundary -- see the module docstring of `person_identity.py`.
    """

    def __init__(
        self,
        limit: int = RATE_LIMIT,
        window_seconds: float = RATE_WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._seen: dict[tuple[str, int], int] = {}

    def allow(self, caller: str) -> bool:
        window = int(self._clock() / self._window)
        if len(self._seen) > _MAX_TRACKED:
            self._seen.clear()
        key = (caller, window)
        used = self._seen.get(key, 0)
        if used >= self._limit:
            return False
        self._seen[key] = used + 1
        return True


def _limiter(request: Request) -> FixedWindowLimit:
    """One limiter per application instance.

    On `app.state` rather than at module scope so that a test building a fresh
    app gets a fresh count. A module-level limiter would make the first test to
    run decide whether the twenty-first request in the whole session was
    refused.
    """

    existing = getattr(request.app.state, "person_id_limit", None)
    if existing is None:
        existing = FixedWindowLimit()
        request.app.state.person_id_limit = existing
    return existing


def _caller(request: Request) -> str:
    """Who to count against.

    The socket address, not a forwarded header: a header the caller writes is a
    header the caller can vary, and counting by it would be a rate limit an
    attacker opts out of. Behind a real proxy this counts the proxy, which is
    wrong in the safe direction -- everybody shares one bucket -- and is a note
    for whoever installs that proxy.
    """

    return request.client.host if request.client else "unknown"


@router.post(
    "/identity/person-id",
    response_model=PersonIdResponse,
    responses={
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["phone"],
                        "properties": {
                            "phone": {
                                "type": "string",
                                "description": (
                                    "A Vietnamese mobile number, in any"
                                    " spelling. Never logged, never stored."
                                ),
                            }
                        },
                    }
                }
            },
        }
    },
)
async def mint_person_id(request: Request) -> PersonIdResponse:
    if not _limiter(request).allow(_caller(request)):
        raise ApiProblem(
            429,
            "rate_limited",
            "Thử lại sau một phút. Máy chủ đang giới hạn số lần tra danh tính.",
        )

    try:
        body = await request.json()
    except ValueError as broken:
        raise ApiProblem(
            422, "invalid_body", "Thân yêu cầu phải là JSON."
        ) from broken

    phone = body.get("phone") if isinstance(body, dict) else None
    if not isinstance(phone, str):
        raise ApiProblem(
            422, "phone_required", "Thiếu trường phone, và phải là chuỗi."
        )

    canonical = canonical_mobile(phone)
    if canonical is None:
        # The number is not in this sentence. It is the input, and echoing an
        # input is how a refusal becomes a disclosure.
        raise ApiProblem(
            422,
            "phone_not_mobile",
            "Chưa đúng dạng số di động Việt Nam.",
        )

    try:
        key = read_key()
    except PersonIdKeyMissing as missing:
        # 503, not 500: the server is working and is not configured. Refusing
        # is the whole point -- a fallback to an unkeyed digest here would be
        # the vulnerability this route was written to close, reappearing
        # precisely when nobody set the key. The key is not in the sentence.
        raise ApiProblem(
            503,
            "identity_key_missing",
            "Máy chủ chưa cấu hình khoá danh tính nên chưa đăng nhập được.",
        ) from missing

    return PersonIdResponse(person_id=derive_person_id(canonical, key))
