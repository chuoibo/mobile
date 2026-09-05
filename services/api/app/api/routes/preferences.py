"""What a group is inferred to like, and what a person says they like.

Two kinds of preference live here on purpose, because they answer the same
question from opposite ends: `GET /contexts/{id}/preference-profile` reads a
group's behaviour (F31), and `PUT /people/me/interests` records what one person
claims (M11, ADR-0019). Behaviour is evidence a new account does not have yet;
a claim is available on the first screen and is exactly what a new account has.

## `GET /contexts/{id}/preference-profile` -- the group's implicit tastes.

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

## `GET /interests` and `PUT /people/me/interests`

The vocabulary is public: the personalization screen is drawn before there is a
session, so a route that required one could not answer the screen that needs it.
Nothing about any person travels on it.

Writing is `me` and only `me`. There is no `person_id` in the path and no
`viewer_id` in the body, for the reason the profile route above gives: a field
naming whose answers to write is a question no caller should be able to pose.
And there is no route that reads somebody else's answers at all -- not a
narrower one, none. A group shows tastes only summed across its members.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import (
    ErrorResponse,
    InterestsUpdateRequest,
    InterestVocabularyResponse,
    MyInterestsResponse,
    PreferenceProfileResponse,
)
from app.api.service import ApiService

router = APIRouter(tags=["preferences"])


@router.get("/interests", response_model=InterestVocabularyResponse)
def read_interest_vocabulary(
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> InterestVocabularyResponse:
    """The taste words and budget bands the server accepts (M11)."""
    return ApiService(repository).interest_vocabulary()


@router.put(
    "/people/me/interests",
    response_model=MyInterestsResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def put_my_interests(
    request: InterestsUpdateRequest,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> MyInterestsResponse:
    """Replace this person's own taste answers. `GET /people/me` reads them back."""
    return ApiService(repository).set_my_interests(request, actor)


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
