"""Group message and membership-role endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    Actor,
    Companion,
    get_actor,
    get_companion,
    get_repository,
)
from app.api.repository import ApiRepository
from app.api.schemas import (
    CompanionTurnResponse,
    ErrorResponse,
    MemberRoleRequest,
    MembershipResponse,
    MessageCreateRequest,
    MessageListResponse,
    MessageQuery,
    MessageResponse,
)
from app.api.service import ApiService

router = APIRouter(tags=["messages"])
ERRORS = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


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
