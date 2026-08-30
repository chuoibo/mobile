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

from fastapi import APIRouter, Depends, Request

from app.api.deps import Actor, Suggester, get_actor, get_repository, get_suggester
from app.api.repository import ApiRepository
from app.api.schemas import ErrorResponse, GroupSuggestionResponse
from app.api.search_rate_limit import FixedWindowLimiter
from app.api.service import ApiService

router = APIRouter(tags=["suggestions"])


def get_suggestion_limiter(request: Request) -> FixedWindowLimiter:
    """Resolve the one suggestion limiter owned by this application instance.

    Read off the application rather than constructed here: a limiter built per
    request counts to one and forgets, which is a limiter-shaped object that
    limits nothing.
    """

    return request.app.state.suggestion_limiter


@router.get(
    "/contexts/{context_id}/suggestion",
    response_model=GroupSuggestionResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
def read_group_suggestion(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    suggester: Annotated[Suggester, Depends(get_suggester)],
    limiter: Annotated[FixedWindowLimiter, Depends(get_suggestion_limiter)],
) -> GroupSuggestionResponse:
    """F32, capped per caller before the model is reached.

    This route had nothing in front of it. `GET /places` reaches Gemini too and
    is bounded by `CachedReasonWriter`, one call per place over a fixed
    catalogue per cooldown -- a bound this comment claimed before it was true,
    see `tests/api/test_places_reason_retry_storm.py`;
    there is no equivalent here, because a suggestion is a function of a
    group's own history and caching one keyed on anything coarser would serve
    one group's evening to another. So it is one model call per request, on a
    GET, which a screen that remounts or a client that polls issues without
    anybody deciding to.
    """

    limiter.check(actor.id)
    return ApiService(repository).group_suggestion(context_id, actor, suggester)
