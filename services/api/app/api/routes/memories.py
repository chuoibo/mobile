"""Private group memory-wall endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import (
    ErrorResponse,
    MemoryCreateRequest,
    MemoryListResponse,
    MemoryQuery,
    MemoryResponse,
)
from app.api.service import ApiService

router = APIRouter(tags=["memories"])
ERRORS = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "/contexts/{context_id}/memories",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def post_context_memory(
    context_id: UUID,
    request: MemoryCreateRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> MemoryResponse:
    return ApiService(repository).post_context_memory(context_id, request, actor)


@router.get(
    "/contexts/{context_id}/memories",
    response_model=MemoryListResponse,
    responses=ERRORS,
)
def list_context_memories(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before: str | None = None,
) -> MemoryListResponse:
    query = MemoryQuery(limit=limit, before=before)
    return ApiService(repository).list_context_memories(context_id, query, actor)
