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
    BatchPublishRequest,
    BatchPublishResponse,
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
