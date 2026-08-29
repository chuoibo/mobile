"""`GET /contexts/{id}/suggestion` -- F32, the card nobody asked for.

A GET because opening a screen is what triggers it. The route creates nothing:
a suggestion is a proposal a group can ignore, and the moment it wrote an
outing row it would be the product deciding for them, which spec section 3
spends a page refusing.

Membership is checked in the service against an ACTIVE row, not here. The
route's whole job is to name the permission-bearing workflow and hand it a
model backend it does not construct itself.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import Actor, Suggester, get_actor, get_repository, get_suggester
from app.api.repository import ApiRepository
from app.api.schemas import ErrorResponse, GroupSuggestionResponse
from app.api.service import ApiService

router = APIRouter(tags=["suggestions"])


@router.get(
    "/contexts/{context_id}/suggestion",
    response_model=GroupSuggestionResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def read_group_suggestion(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    suggester: Annotated[Suggester, Depends(get_suggester)],
) -> GroupSuggestionResponse:
    return ApiService(repository).group_suggestion(context_id, actor, suggester)
