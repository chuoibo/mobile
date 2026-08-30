"""FastAPI dependencies for authentication context and persistence."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Header

from app.api.chat_expense_skill import ChatExpenseReader
from app.api.errors import ApiProblem
from app.api.receipt_skill import ReceiptReader
from app.api.repository import ApiRepository, SqlAlchemyApiRepository
from app.api.screenshot_skill import ScreenshotReader
from app.db.session import get_session_factory
from app.domain.permissions import ROLES
from app.media.storage import PhotoStorage


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


class Companion(Protocol):
    """A model backend that returns an untrusted, raw companion card."""

    def reply(
        self,
        *,
        conversation: list[dict],
        members: list[dict],
        places: list[dict],
        budget_per_person_vnd: int | None,
    ) -> dict: ...


class Suggester(Protocol):
    """A model backend that returns an untrusted, raw F32 suggestion card.

    Takes the server's own history digest, never a conversation: a proactive
    card is built from what the group did, not from what anybody just said.
    Returning `None` is an allowed answer and means "no suggestion right now".
    """

    def __call__(
        self, history: dict, places: list[dict]
    ) -> dict | None: ...


class ContextualSuggester(Protocol):
    """A model backend that returns an untrusted, raw F33 card.

    Separate from `Suggester` on purpose. This one is handed a digest of what
    the group just *said*, which is the only place in the product where a
    member's own sentences are put in front of a model; keeping the two seams
    apart means a test that stubs one cannot silently stand in for the other,
    and the riskier prompt cannot inherit the safer one's envelope by accident.
    """

    def __call__(
        self, digest: dict, places: list[dict]
    ) -> dict | None: ...


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


def get_photo_storage() -> PhotoStorage:
    return PhotoStorage()


def get_receipt_reader() -> ReceiptReader:
    """Build the external reader lazily so importing the app needs no key."""

    from app.api.vision_gemini import GeminiReceiptReader

    return GeminiReceiptReader()


def get_chat_expense_reader() -> ChatExpenseReader:
    """Build the text reader lazily so importing the app needs no key."""

    from app.api.chat_expense_gemini import GeminiChatExpenseReader

    return GeminiChatExpenseReader()


def get_screenshot_reader() -> ScreenshotReader:
    """Build the screenshot reader lazily so importing the app needs no key."""

    from app.api.screenshot_gemini import GeminiScreenshotReader

    return GeminiScreenshotReader()


def get_companion() -> Companion:
    """Build the external companion lazily so importing the app needs no key."""

    from app.api.companion_gemini import GeminiCompanion

    return GeminiCompanion()


def get_suggester() -> Suggester:
    """Seam for tests, and the F32 backend for everyone else.

    Returned as a plain function rather than a memoised object: a suggestion is
    a function of a group's history, and caching one keyed on anything coarser
    would serve one group's evening to another.
    """

    from app.api.suggestion_gemini import gemini_suggestion

    return gemini_suggestion


def get_contextual_suggester() -> ContextualSuggester:
    """Seam for tests, and the F33 backend for everyone else.

    Not memoised, for the reason above and one more: a contextual card is a
    function of one group's last few messages, and any cache coarser than that
    would hand one group's conversation to another.
    """

    from app.api.suggestion_gemini import gemini_contextual_suggestion

    return gemini_contextual_suggestion
