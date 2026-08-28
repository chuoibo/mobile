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
from app.api.schemas import (
    BankRecipientRequest,
    BankRecipientResponse,
    ErrorResponse,
    PersonBankRecipientRequest,
)
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


# The same destination, addressed by person. Both shapes call the same service
# and read the same row -- this is an alias, not a second write path. Two paths
# each holding their own state would answer with different accounts depending on
# which screen asked, and one of those answers would be sending real money to a
# stale account.
#
# Worth having because the subject moves from the body into the address: the
# request that changes somebody else's account is no longer this request with
# one field edited, it is a different URL. The permission check below is
# unchanged and still the thing that enforces section 9.2 -- the path shape
# narrows what a caller can ask for by accident, it does not replace the check.


@router.put(
    "/people/{person_id}/bank-recipient",
    response_model=BankRecipientResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": BankRecipientResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def set_person_bank_recipient(
    person_id: UUID,
    request: PersonBankRecipientRequest,
    response: Response,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> BankRecipientResponse:
    body, created = ApiService(repository).set_bank_recipient(
        BankRecipientRequest(
            recipient_id=person_id,
            bank_bin=request.bank_bin,
            account_number=request.account_number,
            account_name=request.account_name,
        ),
        actor,
    )
    # Same 201/200 split as the collection route: section 8.5 wants a change
    # audited and announced, and a retry that re-sent the same digits is not a
    # change. A PUT answering 201 on create is ordinary HTTP.
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return body


@router.get(
    "/people/{person_id}/bank-recipient",
    response_model=BankRecipientResponse,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_person_bank_recipient(
    person_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> BankRecipientResponse:
    return ApiService(repository).get_bank_recipient(person_id, actor)
