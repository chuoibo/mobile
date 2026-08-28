"""The route that gives the money somewhere to land.

Nothing in the HTTP surface wrote `bank_recipients` before this, so no batch
could ever freeze: `POST /batches` answered `recipient_setup_incomplete`
forever, and the mobile end-to-end test had to reach past the API and INSERT
the row itself.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import BankRecipientRequest, BankRecipientResponse, ErrorResponse
from app.api.service import ApiService

router = APIRouter(tags=["bank-recipients"])


@router.post(
    "/bank-recipients",
    response_model=BankRecipientResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": BankRecipientResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def set_bank_recipient(
    request: BankRecipientRequest,
    response: Response,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> BankRecipientResponse:
    body, created = ApiService(repository).set_bank_recipient(request, actor)
    # 201 when a destination was written or replaced, 200 when the caller
    # re-sent digits that were already there. The difference is what tells a
    # client whether anything material happened -- section 8.5 wants a change
    # audited and announced, and a retry is not a change.
    response.status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    return body


@router.get(
    "/bank-recipients/{recipient_id}",
    response_model=BankRecipientResponse,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_bank_recipient(
    recipient_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> BankRecipientResponse:
    return ApiService(repository).get_bank_recipient(recipient_id, actor)
