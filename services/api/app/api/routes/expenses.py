"""Expense proposal and confirmation endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import (
    ErrorResponse,
    ExpenseConfirmationRequest,
    ExpenseConfirmationResponse,
    ExpenseInput,
    ExpenseProposalResponse,
)
from app.api.service import ApiService

router = APIRouter(tags=["expenses"])
ERRORS = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "/expenses",
    response_model=ExpenseProposalResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorResponse}},
)
def propose_expense(
    request: ExpenseInput,
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> ExpenseProposalResponse:
    return ApiService(repository).propose_expense(request)


@router.post(
    "/expenses/{expense_id}/confirm",
    response_model=ExpenseConfirmationResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def confirm_expense(
    expense_id: UUID,
    request: ExpenseConfirmationRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> ExpenseConfirmationResponse:
    return ApiService(repository).confirm_expense(expense_id, request, actor)
