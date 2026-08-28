"""FastAPI dependencies for authentication context and persistence."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Header

from app.api.errors import ApiProblem
from app.api.receipt_skill import ReceiptReader
from app.api.repository import ApiRepository, SqlAlchemyApiRepository
from app.db.session import get_session_factory
from app.domain.permissions import ROLES


@dataclass(frozen=True, slots=True)
class Actor:
    """Identity asserted by the upstream authentication boundary.

    This slice has no account/session tables yet. The adapter therefore consumes
    headers that a trusted gateway must overwrite, never append. The limitation is
    recorded in the API implementation journal and is not a production auth claim.
    """

    id: UUID
    roles: frozenset[str]
    context_ids: frozenset[UUID]


def _csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def get_actor(
    actor_id: Annotated[str | None, Header(alias="X-Actor-ID")] = None,
    actor_roles: Annotated[str | None, Header(alias="X-Actor-Roles")] = None,
    actor_contexts: Annotated[str | None, Header(alias="X-Actor-Contexts")] = None,
) -> Actor:
    if actor_id is None:
        raise ApiProblem(401, "authentication_required", "Missing X-Actor-ID")
    try:
        parsed_id = UUID(actor_id)
    except ValueError as exc:
        raise ApiProblem(422, "invalid_actor_id", "X-Actor-ID must be a UUID") from exc

    roles = frozenset(_csv(actor_roles))
    unknown_roles = roles - set(ROLES)
    if unknown_roles:
        raise ApiProblem(
            422, "invalid_actor_roles", "X-Actor-Roles contains an unknown role"
        )

    try:
        contexts = frozenset(UUID(value) for value in _csv(actor_contexts))
    except ValueError as exc:
        raise ApiProblem(
            422,
            "invalid_actor_contexts",
            "X-Actor-Contexts must contain comma-separated UUIDs",
        ) from exc
    return Actor(id=parsed_id, roles=roles, context_ids=contexts)


def get_repository() -> Generator[ApiRepository]:
    factory = get_session_factory()
    with factory.begin() as session:
        yield SqlAlchemyApiRepository(session)


def get_receipt_reader() -> ReceiptReader:
    """Build the external reader lazily so importing the app needs no key."""

    from app.api.vision_gemini import GeminiReceiptReader

    return GeminiReceiptReader()
