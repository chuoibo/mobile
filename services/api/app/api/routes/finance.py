"""The read behind the personal screen.

Exists because the alternative was a screen with numbers typed into it. The
demo path ends here -- split a bill, come back, and the totals have moved --
and that only means anything if the totals were never in the client to begin
with. Every figure this route answers with is recomputed from the ledger on
the request that asks for it, which is invariant 3 stated as an endpoint.

Self-only. The service enforces it rather than this module, because the rule
belongs to the data and not to the transport; see `person_finance_summary`.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import (
    ErrorResponse,
    FinanceMovementView,
    PersonFinanceResponse,
)
from app.api.service import ApiService

router = APIRouter(tags=["finance"])


@router.get(
    "/people/{person_id}/finance",
    response_model=PersonFinanceResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def read_person_finance(
    person_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> PersonFinanceResponse:
    summary = ApiService(repository).person_finance_summary(person_id, actor)
    return PersonFinanceResponse(
        person_id=summary.person_id,
        display_name=summary.display_name,
        spend_vnd=summary.spend_vnd,
        settled_vnd=summary.settled_vnd,
        outstanding_vnd=summary.outstanding_vnd,
        expense_count=summary.expense_count,
        group_count=summary.group_count,
        movements=[
            FinanceMovementView(
                obligation_id=movement.obligation_id,
                direction=movement.direction,
                amount_vnd=movement.amount_vnd,
                counterparty_id=movement.counterparty_id,
                counterparty_name=movement.counterparty_name,
                context_id=movement.context_id,
                context_name=movement.context_name,
                occasion=movement.occasion,
                occurred_at=movement.occurred_at,
            )
            for movement in summary.movements
        ],
    )
