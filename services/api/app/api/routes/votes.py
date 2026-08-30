"""Private group voting endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import (
    ErrorResponse,
    VoteBallotRequest,
    VoteBallotResponse,
    VoteCreateRequest,
    VoteListResponse,
    VoteResponse,
)
from app.api.service import ApiService

router = APIRouter(tags=["votes"])
ERRORS = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "/contexts/{context_id}/votes",
    response_model=VoteResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def create_vote(
    context_id: UUID,
    request: VoteCreateRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> VoteResponse:
    return ApiService(repository).create_vote(context_id, request, actor)


@router.get(
    "/contexts/{context_id}/votes",
    response_model=VoteListResponse,
    responses=ERRORS,
)
def list_context_votes(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> VoteListResponse:
    return ApiService(repository).list_context_votes(context_id, actor)


@router.get(
    "/votes/{vote_id}",
    response_model=VoteResponse,
    responses=ERRORS,
)
def get_vote_results(
    vote_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> VoteResponse:
    return ApiService(repository).get_vote_results(vote_id, actor)


@router.post(
    "/votes/{vote_id}/ballots",
    response_model=VoteBallotResponse,
    responses=ERRORS,
)
def cast_vote_ballot(
    vote_id: UUID,
    request: VoteBallotRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> VoteBallotResponse:
    return ApiService(repository).cast_vote_ballot(vote_id, request, actor)


@router.post(
    "/votes/{vote_id}/close",
    response_model=VoteResponse,
    responses=ERRORS,
)
def close_vote(
    vote_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> VoteResponse:
    return ApiService(repository).close_vote(vote_id, actor)
