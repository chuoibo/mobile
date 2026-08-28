"""The route that gives a person id a name.

`contexts.created_by_id` and `memberships.person_id` are foreign keys into
`people`, and no HTTP surface ever wrote that table. `POST /contexts` therefore
answered 500 for every caller -- `ForeignKeyViolation` on
`fk_contexts_created_by` -- and no request existed that would have fixed it.

The same gap reached the reader: `get_guest_envelope` had no names to join, so
the guest page said "Phần của a5b2c277-9b99-4699-a875-ed324e886237" to somebody
being asked for money.

PUT rather than POST because the caller already holds the id. Participant ids
are minted client-side and used in expenses, obligations and envelopes long
before anybody types a name; a server-minted id here would name a person no
expense refers to.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import Actor, get_actor, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import ErrorResponse, PersonRegistrationRequest, PersonResponse
from app.api.service import ApiService

router = APIRouter(tags=["people"])


@router.put(
    "/people/{person_id}",
    response_model=PersonResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": PersonResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def register_person(
    person_id: UUID,
    request: PersonRegistrationRequest,
    response: Response,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> PersonResponse:
    record, created = ApiService(repository).register_person(
        person_id, request.display_name, actor
    )
    # 201 when this id became a person, 200 when it already was one. A client
    # retrying a lost response needs to be able to tell those apart without
    # the answer changing under it.
    response.status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    return PersonResponse(
        id=record.id,
        display_name=record.display_name,
        created_at=record.created_at,
    )
