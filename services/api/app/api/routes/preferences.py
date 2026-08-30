"""`GET /contexts/{id}/preference-profile` -- F31, the group's implicit tastes.

A GET because the profile is not a thing that gets made. There is no table
behind it and no "rebuild" button: the service recomputes it from check-ins and
the ledger on the request that asks, so there is no stale state for a POST to
refresh and no moment at which the screen and the rows can disagree.

There is no request body and no query parameter naming a person. The only
identity involved is the actor the gateway proved, and the only group is the
one in the path -- a `viewer_id` or `person_id` field here would be a way to
ask the server whose profile to hand back, which is a question no caller
should be able to pose.

Membership is checked in the service against an ACTIVE row, not here.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import ErrorResponse, PreferenceProfileResponse
from app.api.service import ApiService

router = APIRouter(tags=["preferences"])


@router.get(
    "/contexts/{context_id}/preference-profile",
    response_model=PreferenceProfileResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def read_preference_profile(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> PreferenceProfileResponse:
    return ApiService(repository).preference_profile(context_id, actor)
