"""Member-only group budget awareness endpoint."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BeforeValidator, Field

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import ErrorResponse, GroupBudgetResponse
from app.api.service import ApiService

router = APIRouter(tags=["budget"])


def _parse_candidate_money(value: object) -> object:
    """Admit integer query spelling without laundering decimal notation."""

    if (
        isinstance(value, str)
        and value.isascii()
        and value.isdigit()
    ):
        return int(value)
    return value


CandidatePerPersonQuery = Annotated[
    int,
    BeforeValidator(_parse_candidate_money),
    Field(strict=True, ge=0),
]


@router.get(
    "/contexts/{context_id}/budget",
    response_model=GroupBudgetResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def read_group_budget(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    candidate_per_person_vnd: Annotated[
        CandidatePerPersonQuery | None,
        Query(),
    ] = None,
) -> GroupBudgetResponse:
    """Compare an optional candidate with ledger-backed group history."""

    return ApiService(repository).group_budget(
        context_id,
        actor,
        candidate_per_person_vnd=candidate_per_person_vnd,
    )
