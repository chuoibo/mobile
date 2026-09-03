"""Group message and membership-role endpoints."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.chat_expense_skill import ChatExpenseReader
from app.api.deps import (
    Actor,
    Companion,
    get_actor,
    get_chat_expense_reader,
    get_companion,
    get_repository,
)
from app.api.errors import ApiProblem
from app.api.repository import ApiRepository
from app.api.schemas import (
    ChatExpenseDraftResponse,
    CompanionTurnRequest,
    CompanionTurnResponse,
    ErrorResponse,
    MemberRoleRequest,
    MembershipResponse,
    MessageCreateRequest,
    MessageListResponse,
    MessageQuery,
    MessageResponse,
    ReadMarkRequest,
    ReadMarkResponse,
)
from app.api.search_rate_limit import FixedWindowLimiter
from app.api.service import ApiService
from app.domain.chat_expense import ChatExpenseError

router = APIRouter(tags=["messages"])
_LOGGER = logging.getLogger(__name__)
ERRORS = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}

_CHAT_UNREADABLE_DETAIL = (
    "Không đọc được khoản chi từ tin nhắn. Hãy kiểm tra lại nội dung."
)
_MODEL_NAMED_PERSON_DETAIL = (
    "AI đã cố nêu người trả hoặc người tham gia; bản nháp bị từ chối để danh "
    "tính chỉ được đọc từ dữ liệu nhóm."
)
_CHAT_READER_UNAVAILABLE_DETAIL = (
    "Không đọc được khoản chi từ tin nhắn lúc này, thử lại sau."
)
_CHAT_READER_NOT_CONFIGURED_DETAIL = (
    "Máy chủ chưa cấu hình khoá đọc khoản chi từ tin nhắn. Đây là lỗi cấu hình "
    "phía máy chủ; sửa lại tin nhắn không giúp được."
)


def get_chat_expense_limiter(request: Request) -> FixedWindowLimiter:
    """Resolve the one F24 limiter owned by this application instance."""

    return request.app.state.chat_expense_limiter


def get_companion_turn_limiter(request: Request) -> FixedWindowLimiter:
    """Resolve the one companion-turn limiter owned by this application.

    Read off the application rather than constructed here: a limiter built per
    request counts to one and forgets, which is a limiter-shaped object that
    limits nothing.
    """

    return request.app.state.companion_turn_limiter


@router.post(
    "/contexts/{context_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def post_context_message(
    context_id: UUID,
    request: MessageCreateRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> MessageResponse:
    return ApiService(repository).post_context_message(context_id, request, actor)


@router.get(
    "/contexts/{context_id}/messages",
    response_model=MessageListResponse,
    responses=ERRORS,
)
def list_context_messages(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before: str | None = None,
    after: str | None = None,
) -> MessageListResponse:
    query = MessageQuery(limit=limit, before=before, after=after)
    return ApiService(repository).list_context_messages(context_id, query, actor)


@router.post(
    "/contexts/{context_id}/messages/{message_id}/expense-draft",
    response_model=ChatExpenseDraftResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def create_chat_expense_draft(
    context_id: UUID,
    message_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    reader: Annotated[ChatExpenseReader, Depends(get_chat_expense_reader)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    limiter: Annotated[FixedWindowLimiter, Depends(get_chat_expense_limiter)],
) -> ChatExpenseDraftResponse:
    """Return a draft only; this route never creates or allocates an expense."""

    # Keep this outside the backend error boundary. `check` raises ApiProblem;
    # catching it as a reader failure would turn an honest 429 into a 502.
    limiter.check(actor.id)
    try:
        return ApiService(repository).create_chat_expense_draft(
            context_id,
            message_id,
            actor,
            reader,
        )
    except ChatExpenseError as exc:
        # Only our closed refusal code reaches the log. The message and raw
        # model answer are private group data and must never be interpolated.
        _LOGGER.info("chat expense draft refused: %s", exc.code)
        if exc.code == "CHAT_READER_NOT_CONFIGURED":
            raise ApiProblem(
                503,
                "chat_reader_not_configured",
                _CHAT_READER_NOT_CONFIGURED_DETAIL,
            ) from None
        if exc.code == "MODEL_NAMED_A_PERSON":
            raise ApiProblem(
                422,
                "chat_expense_model_named_a_person",
                _MODEL_NAMED_PERSON_DETAIL,
            ) from None
        raise ApiProblem(
            422,
            "chat_expense_unreadable",
            _CHAT_UNREADABLE_DETAIL,
        ) from None
    except RuntimeError as exc:
        # The adapter already discarded provider exception text and chaining.
        _LOGGER.warning("chat expense reader failed (%s)", type(exc).__name__)
        raise ApiProblem(
            502,
            "chat_reader_unavailable",
            _CHAT_READER_UNAVAILABLE_DETAIL,
        ) from None


@router.post(
    "/contexts/{context_id}/ai-turn",
    response_model=CompanionTurnResponse,
    responses=ERRORS | {429: {"model": ErrorResponse}},
)
def take_companion_turn(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    companion: Annotated[Companion, Depends(get_companion)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    limiter: Annotated[FixedWindowLimiter, Depends(get_companion_turn_limiter)],
    request: CompanionTurnRequest | None = None,
) -> CompanionTurnResponse:
    """One companion turn, capped per caller before the model is reached.

    `plan_turn` already refuses to speak while the companion spoke last, and
    that is a conversation cadence rather than a ceiling: the caller lifts it
    by posting one more message, so an unmetered loop costs two cheap requests
    per model call instead of one. The window is what makes the cost bounded.

    Charged before the cadence is consulted, so a poll that would have been
    answered `already_spoke_last` still spends a slot. That is deliberate: the
    order that spares those calls is the order that lets a loop drive the
    expensive path for free, because which one a request becomes is decided by
    the caller. Thirty a minute is far above anyone typing and far below a loop.

    That ordering is also why `requested` is safe to accept from the client. It
    lifts the cadence, never the window: a caller that sets it on every request
    buys the same thirty turns a minute as one that never sets it.

    The body is optional because the shipped client sends none -- it posts this
    route with a JSON content type over zero bytes, so a required model would
    turn every AI turn in the product into a 422.
    """

    limiter.check(actor.id)
    return ApiService(repository).take_companion_turn(
        context_id,
        actor,
        companion,
        requested=request.requested if request is not None else False,
    )


@router.put(
    "/contexts/{context_id}/members/{person_id}/role",
    response_model=MembershipResponse,
    responses=ERRORS,
)
def set_context_member_role(
    context_id: UUID,
    person_id: UUID,
    request: MemberRoleRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> MembershipResponse:
    return ApiService(repository).set_context_member_role(
        context_id, person_id, request, actor
    )


@router.put(
    "/contexts/{context_id}/read-mark",
    response_model=ReadMarkResponse,
    responses=ERRORS,
)
def mark_context_read(
    context_id: UUID,
    request: ReadMarkRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> ReadMarkResponse:
    """Where this person has read up to. Forward-only; a message outside this
    group is a 404. PUT because the resource is the mark itself and the call is
    idempotent by construction -- replaying it moves nothing."""
    return ApiService(repository).mark_context_read(context_id, request, actor)
