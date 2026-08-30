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
    CompanionTurnResponse,
    ErrorResponse,
    MemberRoleRequest,
    MembershipResponse,
    MessageCreateRequest,
    MessageListResponse,
    MessageQuery,
    MessageResponse,
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
    responses=ERRORS,
)
def take_companion_turn(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    companion: Annotated[Companion, Depends(get_companion)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> CompanionTurnResponse:
    return ApiService(repository).take_companion_turn(context_id, actor, companion)


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
