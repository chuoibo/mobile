"""Context membership endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import (
    ContextCreateRequest,
    ContextResponse,
    ErrorResponse,
    MembershipInviteRequest,
    MembershipListResponse,
    MembershipResponse,
)
from app.api.service import ApiService

router = APIRouter(tags=["contexts"])
ERRORS = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "/contexts",
    response_model=ContextResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def create_context(
    request: ContextCreateRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> ContextResponse:
    return ApiService(repository).create_context(request, actor)


@router.post(
    "/contexts/{context_id}/members",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def invite_context_member(
    context_id: UUID,
    request: MembershipInviteRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> MembershipResponse:
    return ApiService(repository).invite_context_member(context_id, request, actor)


@router.post(
    "/memberships/{membership_id}/accept",
    response_model=MembershipResponse,
    responses=ERRORS,
)
def accept_context_membership(
    membership_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> MembershipResponse:
    return ApiService(repository).accept_context_membership(membership_id, actor)


@router.delete(
    "/contexts/{context_id}/members/{person_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERRORS,
)
def leave_context(
    context_id: UUID,
    person_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> Response:
    ApiService(repository).leave_context(context_id, person_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/contexts/{context_id}/members",
    response_model=MembershipListResponse,
    responses=ERRORS,
)
def list_context_members(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> MembershipListResponse:
    return ApiService(repository).list_context_members(context_id, actor)
