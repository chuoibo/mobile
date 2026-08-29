"""Private group outing, timeline, and invitation endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import (
    ErrorResponse,
    OutingCreateRequest,
    OutingInviteAcceptResponse,
    OutingInviteCreateRequest,
    OutingInviteResponse,
    OutingListResponse,
    OutingResponse,
    OutingTimelineRequest,
)
from app.api.service import ApiService

router = APIRouter(tags=["outings"])
ERRORS = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "/contexts/{context_id}/outings",
    response_model=OutingResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def create_outing(
    context_id: UUID,
    request: OutingCreateRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> OutingResponse:
    return ApiService(repository).create_outing(context_id, request, actor)


@router.get(
    "/contexts/{context_id}/outings",
    response_model=OutingListResponse,
    responses=ERRORS,
)
def list_context_outings(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> OutingListResponse:
    return ApiService(repository).list_context_outings(context_id, actor)


@router.put(
    "/outings/{outing_id}/timeline",
    response_model=OutingResponse,
    responses=ERRORS,
)
def replace_outing_timeline(
    outing_id: UUID,
    request: OutingTimelineRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> OutingResponse:
    return ApiService(repository).replace_outing_timeline(outing_id, request, actor)


@router.post(
    "/outings/{outing_id}/invites",
    response_model=OutingInviteResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def create_outing_invite(
    outing_id: UUID,
    request: OutingInviteCreateRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> OutingInviteResponse:
    return ApiService(repository).create_outing_invite(outing_id, request, actor)


@router.post(
    "/outings/{outing_id}/invites/{invite_id}/revoke",
    response_model=OutingInviteResponse,
    responses=ERRORS,
)
def revoke_outing_invite(
    outing_id: UUID,
    invite_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> OutingInviteResponse:
    return ApiService(repository).revoke_outing_invite(
        outing_id, invite_id, actor
    )


@router.post(
    "/outing-invites/{token}/accept",
    response_model=OutingInviteAcceptResponse,
    responses=ERRORS,
)
def accept_outing_invite(
    token: str,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> OutingInviteAcceptResponse:
    return ApiService(repository).accept_outing_invite(token, actor)
