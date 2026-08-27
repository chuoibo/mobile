"""Recipient-only receipt confirmation endpoint."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import (
    ErrorResponse,
    ReceiptConfirmationRequest,
    ReceiptConfirmationResponse,
)
from app.api.service import ApiService

router = APIRouter(tags=["obligations"])


@router.post(
    "/obligations/{obligation_id}/confirm-receipt",
    response_model=ReceiptConfirmationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def confirm_receipt(
    obligation_id: UUID,
    request: ReceiptConfirmationRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> ReceiptConfirmationResponse:
    return ApiService(repository).confirm_receipt(obligation_id, request, actor)
