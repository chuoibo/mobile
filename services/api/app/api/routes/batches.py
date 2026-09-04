"""Collection batch creation and publication endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import (
    BatchCreateRequest,
    BatchCreateResponse,
    BatchObligationsResponse,
    BatchPublishRequest,
    BatchPublishResponse,
    ContextBatchesResponse,
    ErrorResponse,
)
from app.api.service import ApiService

router = APIRouter(tags=["batches"])
ERRORS = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "/batches",
    response_model=BatchCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def create_batch(
    request: BatchCreateRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> BatchCreateResponse:
    return ApiService(repository).create_batch(request, actor)


@router.post(
    "/batches/{batch_id}/publish",
    response_model=BatchPublishResponse,
    responses=ERRORS,
)
def publish_batch(
    batch_id: UUID,
    request: BatchPublishRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> BatchPublishResponse:
    return ApiService(repository).publish_batch(batch_id, request, actor)


@router.get(
    "/batches/{batch_id}/obligations",
    response_model=BatchObligationsResponse,
    responses={404: {"model": ErrorResponse}},
)
def list_batch_obligations(
    batch_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> BatchObligationsResponse:
    """The collection board. Read-only, and the only place a dispute shows up.

    Section 8.2 stops collection on a disputed obligation. That guarantee is
    worth nothing if the person collecting cannot see which one it is.
    """
    return ApiService(repository).list_batch_obligations(batch_id, actor)


@router.get(
    "/contexts/{context_id}/batches",
    response_model=ContextBatchesResponse,
    responses={403: {"model": ErrorResponse}},
)
def list_context_batches(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> ContextBatchesResponse:
    """The group's collection rounds, newest first, each summarised from its board.

    Read-only. A member reaches a round from here after the phone that opened
    it has forgotten the id; the board itself stays at `/batches/{id}/obligations`.
    """
    return ApiService(repository).list_context_batches(context_id, actor)
