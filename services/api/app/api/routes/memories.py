"""Private group memory-wall endpoints.

Two kinds of keepsake share one wall: a photograph (rd-be-07) and a check-in
(F46). They are one feed with one cursor because that is what the mockup draws
-- a single scrollable history -- and splitting them into two routes with two
paginations would put the merge in every client instead of in the database.

The write paths are separate even so. `POST .../memories` and
`POST .../checkins` take disjoint bodies, so a request that names both an
image and a place cannot be spelled; only the read is shared.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import (
    CheckinCreateRequest,
    ErrorResponse,
    MemoryCommentCreateRequest,
    MemoryCommentListResponse,
    MemoryCommentResponse,
    MemoryCreateRequest,
    MemoryListResponse,
    MemoryQuery,
    MemoryReactionResponse,
    MemoryResponse,
)
from app.api.service import ApiService

router = APIRouter(tags=["memories"])
ERRORS = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "/contexts/{context_id}/memories",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def post_context_memory(
    context_id: UUID,
    request: MemoryCreateRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> MemoryResponse:
    return ApiService(repository).post_context_memory(context_id, request, actor)


@router.post(
    "/contexts/{context_id}/checkins",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def post_context_checkin(
    context_id: UUID,
    request: CheckinCreateRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> MemoryResponse:
    """F46. The group is here; write it onto the wall.

    Answers with a `MemoryResponse` and not a shape of its own, because what
    was created is a row of the wall. A caller that posted a check-in and then
    listed the feed must be able to find the same object, field for field.
    """

    return ApiService(repository).post_context_checkin(context_id, request, actor)


@router.get(
    "/contexts/{context_id}/memories",
    response_model=MemoryListResponse,
    responses=ERRORS,
)
def list_context_memories(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before: str | None = None,
    kind: Annotated[Literal["photo", "checkin"] | None, Query()] = None,
    place_id: Annotated[str | None, Query(max_length=200)] = None,
) -> MemoryListResponse:
    """The wall, newest first, optionally narrowed.

    `kind` and `place_id` narrow *within* a group. Neither widens anything:
    both are applied after `view_group_memories` has already decided that this
    actor may read this context at all, and both sit on top of the
    `context_id` predicate rather than replacing it.
    """

    query = MemoryQuery(limit=limit, before=before, kind=kind, place_id=place_id)
    return ApiService(repository).list_context_memories(context_id, query, actor)


# --------------------------------------------------------------------------
# F40 and F41 -- hearts and comments
#
# Every one of these paths carries the context id even though a memory id
# alone would identify the row. That is the point: the membership check runs
# against the context in the path *before* the memory is looked up, so a
# stranger receives the same 403 whether or not the id names a real memory.
# Keyed on the memory alone, the pair of status codes would tell anyone
# holding a session which ids exist inside groups they are not in.
# --------------------------------------------------------------------------


@router.post(
    "/contexts/{context_id}/memories/{memory_id}/reactions",
    response_model=MemoryReactionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def post_memory_reaction(
    context_id: UUID,
    memory_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> MemoryReactionResponse:
    """F40. Leave a heart on one row of the wall.

    The route takes no request body. There is therefore no field in which a
    caller could name whose heart this is -- the reactor is the actor the
    gateway proved, and the shape of the route makes the alternative
    unspellable rather than merely unused.
    """

    return ApiService(repository).react_to_memory(context_id, memory_id, actor)


@router.delete(
    "/contexts/{context_id}/memories/{memory_id}/reactions",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERRORS,
)
def delete_memory_reaction(
    context_id: UUID,
    memory_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> None:
    """Take back one's own heart. There is no path to anybody else's."""

    ApiService(repository).unreact_to_memory(context_id, memory_id, actor)


@router.post(
    "/contexts/{context_id}/memories/{memory_id}/comments",
    response_model=MemoryCommentResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def post_memory_comment(
    context_id: UUID,
    memory_id: UUID,
    request: MemoryCommentCreateRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> MemoryCommentResponse:
    """F41. Say something under a photograph, as yourself."""

    return ApiService(repository).post_memory_comment(
        context_id, memory_id, request, actor
    )


@router.get(
    "/contexts/{context_id}/memories/{memory_id}/comments",
    response_model=MemoryCommentListResponse,
    responses=ERRORS,
)
def list_memory_comments(
    context_id: UUID,
    memory_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> MemoryCommentListResponse:
    """The conversation under one photograph, oldest first.

    Behind `view_group_memories`, the same gate the wall itself is behind. The
    bodies returned here are group-private text and reach no other surface --
    in particular not the guest page, whose view model is a whitelist with no
    slot for them.
    """

    return ApiService(repository).list_memory_comments(context_id, memory_id, actor)
