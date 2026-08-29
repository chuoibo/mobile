"""Scanned bill draft, assignment, and allocator-preview endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import (
    BillAssignmentsRequest,
    BillCreateRequest,
    BillResponse,
    BillSplitRequest,
    BillSplitResponse,
    ErrorResponse,
)
from app.api.service import ApiService

router = APIRouter(tags=["bills"])
ERRORS = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "/bills",
    response_model=BillResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def create_bill(
    request: BillCreateRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> BillResponse:
    return ApiService(repository).create_bill(request, actor)


@router.get(
    "/bills/{bill_id}",
    response_model=BillResponse,
    responses=ERRORS,
)
def get_bill(
    bill_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> BillResponse:
    return ApiService(repository).get_bill(bill_id, actor)


@router.put(
    "/bills/{bill_id}/assignments",
    response_model=BillResponse,
    responses=ERRORS,
)
def confirm_bill_assignments(
    bill_id: UUID,
    request: BillAssignmentsRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> BillResponse:
    return ApiService(repository).confirm_bill_assignments(bill_id, request, actor)


@router.post(
    "/bills/{bill_id}/split",
    response_model=BillSplitResponse,
    responses=ERRORS,
)
def split_bill(
    bill_id: UUID,
    request: BillSplitRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> BillSplitResponse:
    return ApiService(repository).split_bill(bill_id, request, actor)
