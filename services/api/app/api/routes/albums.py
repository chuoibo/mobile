"""F36 -- trip albums. Two GETs that create nothing.

`context_id` is in the path on both, and that is a design decision rather than
a URL style. It lets the service prove ACTIVE membership of the group *before*
it looks any outing up, so a stranger receives the same 403 whether the id
names a real trip or nothing at all. Keyed on a bare `outing_id`, the
403/404 pair becomes an oracle for walking another group's trip ids.

Neither route serves image bytes. An album carries the memory wall's own
`/contexts/{id}/photos/{id}` paths, so a photograph is still fetched through
the one route that guards it -- the album is a way of reading rows, never a
second door to the files.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.deps import Actor, Reeler, get_actor, get_reeler, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import (
    AlbumListResponse,
    AlbumResponse,
    ErrorResponse,
    ReelResponse,
)
from app.api.search_rate_limit import FixedWindowLimiter
from app.api.service import ApiService

router = APIRouter(tags=["albums"])


def get_reel_limiter(request: Request) -> FixedWindowLimiter:
    """Resolve the F37 window owned by this application instance."""

    return request.app.state.reel_limiter


@router.get(
    "/contexts/{context_id}/albums",
    response_model=AlbumListResponse,
    responses={
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def list_trip_albums(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> AlbumListResponse:
    return ApiService(repository).list_trip_albums(context_id, actor)


@router.get(
    "/contexts/{context_id}/albums/{outing_id}",
    response_model=AlbumResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def read_trip_album(
    context_id: UUID,
    outing_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> AlbumResponse:
    return ApiService(repository).trip_album(context_id, outing_id, actor)


@router.get(
    "/contexts/{context_id}/albums/{outing_id}/reel",
    response_model=ReelResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
def read_trip_reel(
    context_id: UUID,
    outing_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    reeler: Annotated[Reeler, Depends(get_reeler)],
    limiter: Annotated[FixedWindowLimiter, Depends(get_reel_limiter)],
) -> ReelResponse:
    """Build one reel after charging the caller, before reaching the model."""

    limiter.check(actor.id)
    return ApiService(repository).trip_reel(context_id, outing_id, actor, reeler)
