"""The friend graph over HTTP. F03 (find and ask) and F04 (answer).

Five routes, and one of them needs care that the other four do not.

`POST /friends/lookup` is the only place in this file where a telephone number
crosses the wire, and everything about the handler is shaped by keeping it from
coming back out. Three specific ways it would have leaked, all closed here:

**FastAPI's own 422 echoes the input.** A pydantic model for the body means a
caller who posts `phone` as a JSON *number* gets that number returned under an
`"input"` key. `routes/identity.py` measured that against this app and parses
its body by hand for the same reason; so does this. Every refusal below is a
fixed sentence with no interpolation.

**The number must not reach a path or a query string.** uvicorn's access log
records method and path. So this is a POST with the number in the body, never
`GET /friends/lookup?phone=...`.

**The answer must be an id and a name, not a record.** The response model is
`PersonMatchResponse`: `person_id` and `display_name`. There is no field for a
telephone number, and there is no column behind one either -- the server never
stored the number in the first place (`app/api/person_identity.py`). So "find a
friend by phone must not return somebody else's phone" is not a filter someone
has to remember to apply; it is a thing the schema cannot express and the
database cannot supply.

What this route *is*, honestly: an oracle for "does this number have an
account". A caller who did not know Binh uses Rủ Đi learns it by asking. That
is the same trade `person_identity.py` documents for id derivation, narrowed
two ways -- it needs an actor header, so it is not anonymous, and it is rate
limited per caller. A limit is a cost, not a wall. Removing the oracle needs a
mutual-contacts design the product does not have yet, and pretending otherwise
in a comment would be worse than saying so.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import Actor, get_actor, get_repository
from app.api.errors import ApiProblem
from app.api.person_identity import (
    PersonIdKeyMissing,
    canonical_mobile,
    derive_person_id,
    read_key,
)
from app.api.repository import ApiRepository
from app.api.routes.identity import FixedWindowLimit
from app.api.schemas import (
    ErrorResponse,
    FriendListResponse,
    FriendRequestCreate,
    FriendRequestDecision,
    FriendRequestListResponse,
    FriendRequestResponse,
    PersonMatchResponse,
)
from app.api.service import ApiService

router = APIRouter(tags=["friends"])

#: Looking somebody up is one request per person you are adding. Thirty a
#: minute covers pasting a contact list by hand and makes sweeping the ~5x10^8
#: Vietnamese mobile space through this route take on the order of 10^7
#: minutes -- the same arithmetic `person_identity.py` does for the derivation
#: route, which this deliberately mirrors rather than reinvents.
LOOKUP_RATE_LIMIT = 30
LOOKUP_WINDOW_SECONDS = 60.0


def _lookup_limiter(request: Request) -> FixedWindowLimit:
    """One limiter per application instance, separate from the identity one.

    On `app.state` so a test building a fresh app gets a fresh count. Separate
    from `person_id_limit` because sharing it would let ordinary sign-ins use
    up the budget for adding friends and vice versa -- one bucket, two
    unrelated activities, and whichever is busier silently disables the other.
    """
    existing = getattr(request.app.state, "friend_lookup_limit", None)
    if existing is None:
        existing = FixedWindowLimit(LOOKUP_RATE_LIMIT, LOOKUP_WINDOW_SECONDS)
        request.app.state.friend_lookup_limit = existing
    return existing


def _caller(request: Request) -> str:
    """The socket address. A header the caller writes, they can also vary."""
    return request.client.host if request.client else "unknown"


@router.post(
    "/friends/requests",
    response_model=FriendRequestResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def send_friend_request(
    body: FriendRequestCreate,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> FriendRequestResponse:
    """Ask somebody to be friends. 201 means asked, never means friends."""
    return ApiService(repository).send_friend_request(body, actor)


@router.post(
    "/friends/requests/{request_id}/respond",
    response_model=FriendRequestResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
def respond_to_friend_request(
    request_id: UUID,
    body: FriendRequestDecision,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> FriendRequestResponse:
    """Accept, decline or block. Only the addressee may accept or decline."""
    return ApiService(repository).respond_to_friend_request(request_id, body, actor)


@router.get(
    "/people/{person_id}/friend-requests",
    response_model=FriendRequestListResponse,
    responses={403: {"model": ErrorResponse}},
)
def list_friend_requests(
    person_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    direction: str = "incoming",
) -> FriendRequestListResponse:
    """Pending requests, incoming by default.

    `direction` is read as "incoming unless the caller said outgoing" rather
    than validated into an enum, because an unknown value must not widen the
    result. Anything unrecognised gives the narrower list.
    """
    return ApiService(repository).list_friend_requests(
        person_id, "outgoing" if direction == "outgoing" else "incoming", actor
    )


@router.get(
    "/people/{person_id}/friends",
    response_model=FriendListResponse,
    responses={403: {"model": ErrorResponse}},
)
def list_friends(
    person_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> FriendListResponse:
    """Your friends. `is_self` keeps this from being anybody else's."""
    return ApiService(repository).list_friends(person_id, actor)


@router.post(
    "/friends/lookup",
    response_model=PersonMatchResponse,
    responses={
        404: {"model": ErrorResponse},
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
                                    "A Vietnamese mobile number the caller"
                                    " already holds. Never logged, never"
                                    " stored, never returned."
                                ),
                            }
                        },
                    }
                }
            },
        }
    },
)
async def find_person_by_phone(
    request: Request,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> PersonMatchResponse:
    """Who holds this number. Answers with an id and a name, or 404.

    Read the module docstring before changing anything in this function: the
    hand-parsed body and every fixed refusal sentence are load-bearing.
    """
    if not _lookup_limiter(request).allow(_caller(request)):
        raise ApiProblem(
            429,
            "rate_limited",
            "Thử lại sau một phút. Máy chủ đang giới hạn số lần tìm bạn.",
        )

    try:
        body = await request.json()
    except ValueError as broken:
        raise ApiProblem(422, "invalid_body", "Thân yêu cầu phải là JSON.") from broken

    phone = body.get("phone") if isinstance(body, dict) else None
    if not isinstance(phone, str):
        raise ApiProblem(422, "phone_required", "Thiếu trường phone, và phải là chuỗi.")

    canonical = canonical_mobile(phone)
    if canonical is None:
        # The number is the input, and echoing an input is how a refusal
        # becomes a disclosure. No interpolation on this line, ever.
        raise ApiProblem(422, "phone_not_mobile", "Chưa đúng dạng số di động Việt Nam.")

    try:
        key = read_key()
    except PersonIdKeyMissing as missing:
        # 503, not 500: configured wrongly, not broken. Falling back to an
        # unkeyed digest here would reopen the enumeration attack
        # `person_identity.py` exists to close, exactly when nobody set a key.
        raise ApiProblem(
            503,
            "identity_key_missing",
            "Máy chủ chưa cấu hình khoá danh tính nên chưa tìm bạn được.",
        ) from missing

    # The number ends here. What continues is an opaque id, so nothing
    # downstream -- service, repository, logs, error handlers -- is holding a
    # telephone number it could accidentally render.
    return ApiService(repository).find_person_by_person_id(
        derive_person_id(canonical, key), actor
    )
