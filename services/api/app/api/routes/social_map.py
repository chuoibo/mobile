"""F43, F44, F45 -- the map, the heatmap, and the meeting point.

Three group-scoped routes about places. They live together because they share
one safety argument, stated once in `app/places/social_map.py`: the two that
read history answer with strictly less than the memory wall the same caller
could already read, and the third reads no history at all.

Nothing here is a write path. There is no route in this module that records
where anybody is, and `OutingStopCheckin` explains why this product does not
have one.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import (
    AreaSummary,
    ErrorResponse,
    GroupHeatmapResponse,
    MeetingPointRequest,
    MeetingPointResponse,
    SocialMapResponse,
)
from app.api.service import ApiService
from app.places.areas import AREAS, area_summary

router = APIRouter(tags=["places"])
ERRORS = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.get("/areas", response_model=list[AreaSummary])
def list_areas() -> list[AreaSummary]:
    """The districts `POST /contexts/{id}/meet` will accept, and their centroids.

    Ungated on purpose, and it is the one route in this module that is: the
    answer is a fixed list of Vietnamese districts. It contains no group, no
    person and no history, and it is identical for every caller, so there is
    nothing here for membership to protect.

    It exists because the screen that collects origins has to offer real ids.
    The alternative was to write the eight ids into the app, which
    `scripts/check_api_contract.py` describes precisely in its own header: a
    list kept by hand is a third copy to drift. Then the day a district is
    added or renamed, the picker offers an id the server answers 422 for, and
    the only symptom is a form that refuses a perfectly reasonable answer.
    """

    return [AreaSummary.model_validate(area_summary(area)) for area in AREAS]


@router.get(
    "/contexts/{context_id}/map",
    response_model=SocialMapResponse,
    responses=ERRORS,
)
def get_social_map(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> SocialMapResponse:
    """F43. Where this group has been, what is busy, what to try next.

    403 for a non-member, and the message says "you are not in this group"
    rather than an error code, because that is what it means.
    """

    return ApiService(repository).get_social_map(context_id, actor)


@router.get(
    "/contexts/{context_id}/heatmap",
    response_model=GroupHeatmapResponse,
    responses=ERRORS,
)
def get_group_heatmap(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> GroupHeatmapResponse:
    """F44. The group's districts, by how often they turn up in them.

    Districts and counts. No author, no timestamp -- see
    `app/places/social_map.py` for why that is a property of the shape rather
    than of this handler's manners.
    """

    return ApiService(repository).get_group_heatmap(context_id, actor)


@router.post(
    "/contexts/{context_id}/meet",
    response_model=MeetingPointResponse,
    responses=ERRORS,
)
def post_meeting_point(
    context_id: UUID,
    request: MeetingPointRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> MeetingPointResponse:
    """F45. Given where people are starting from, where should everyone meet?

    POST rather than GET despite reading nothing: the input is a list, and a
    list of origins in a query string is a list of origins in every access log
    and every browser history on the way. It is not identifying data -- there
    are no people in it -- but it is still the group's plan for tonight, and a
    body keeps it out of infrastructure that was never asked to hold it.

    Not idempotency-keyed, because it writes nothing. Sending it twice returns
    the same answer and changes no row.
    """

    return ApiService(repository).get_meeting_point(context_id, request, actor)
