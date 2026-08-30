"""The read behind the group memory wall, and behind budget awareness.

Answers in two lists. `outings` is the wall itself -- trips that are over.
`in_progress` is the trip the group has not come home from yet, and it exists
because a spending figure that only arrives after the trip ends arrives at the
one moment nobody can act on it (F34, rd-be-15). Both are recomputed the same
way from the same ledger; neither is stored.


Pillar 5 of the spec starts here rather than at the photo grid, because the
part of a trip a group can still recover months later is not the pictures --
it is where they went and what it cost. Both already exist in the database as
consequences of other features, and neither was readable as one thing.

Every figure this route answers with is recomputed on the request that asks for
it. No trip carries a stored total, which is invariant 3 applied to a screen
whose whole job is to look backwards: a memory wall that reads a cached number
is a memory wall that disagrees with the ledger the first time somebody
corrects a bill, and disagrees quietly.

Private to the group. The same permission that guards the photos guards this,
because a trip's spending is no less the group's business than its pictures.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import ErrorResponse, GroupRecapResponse
from app.api.service import ApiService

router = APIRouter(tags=["recap"])


@router.get(
    "/contexts/{context_id}/recap",
    response_model=GroupRecapResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def read_group_recap(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> GroupRecapResponse:
    return ApiService(repository).group_recap(context_id, actor)
