"""Where one person's money should land.

This is the endpoint whose absence made the vertical slice a dead end. An
advancer could record an expense and confirm it, and then `POST /batches`
answered `advancer_bank_recipient_missing` forever, because no HTTP route
wrote `bank_recipients`. The end-to-end test papered over it with a raw INSERT.

The subject is in the path rather than implied by the actor on purpose. With
`/me` the `is_own_account` predicate is true by construction and proves
nothing; with `/people/{person_id}` a request to change someone else's
destination is a real request that gets a real 403, which is the rule spec
section 9.2 actually states.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import (
    BankRecipientRequest,
    BankRecipientResponse,
    ErrorResponse,
)
from app.api.service import ApiService

router = APIRouter(tags=["bank-recipients"])
ERRORS = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.put(
    "/people/{person_id}/bank-recipient",
    response_model=BankRecipientResponse,
    status_code=status.HTTP_200_OK,
    responses=ERRORS,
)
def set_bank_recipient(
    person_id: UUID,
    request: BankRecipientRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> BankRecipientResponse:
    """PUT, because a person has one live destination, not a growing list.

    The call is idempotent from the caller's side -- send the same account
    twice and the live answer is the same account. It is not idempotent in
    storage: each call revokes the previous row and writes a new one, so the
    record of which account was live when survives.
    """
    return ApiService(repository).set_bank_recipient(person_id, request, actor)


@router.get(
    "/people/{person_id}/bank-recipient",
    response_model=BankRecipientResponse,
    responses=ERRORS,
)
def get_bank_recipient(
    person_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> BankRecipientResponse:
    """404 only after the permission check, never before.

    Ordering matters: answering 404 for a stranger's person_id and 403 for a
    peer's would turn this route into an oracle for who has already set an
    account up.
    """
    return ApiService(repository).get_bank_recipient(person_id, actor)
