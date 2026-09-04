"""FastAPI dependencies for authentication context and persistence."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends, Header, Request

from app.api.auth_mode import PROD, trusts_actor_headers
from app.api.chat_expense_skill import ChatExpenseReader
from app.api.errors import ApiProblem
from app.api.receipt_skill import ReceiptReader
from app.api.repository import ApiRepository, SqlAlchemyApiRepository
from app.api.screenshot_skill import ScreenshotReader
from app.api.unit_of_work import register_session
from app.db.session import get_session_factory
from app.domain.permissions import ROLES

# Safe at module scope: this module defers cv2, numpy and PIL into function
# bodies, so importing it costs a Protocol and two dataclasses.
from app.media.face_detection import FaceDetector
from app.media.storage import PhotoStorage


@dataclass(frozen=True, slots=True)
class Actor:
    """Who the server is answering as, and what the roster says they may claim.

    Where this comes from depends on the mode this process runs in. Under
    `prod` it is built from a session row the server issued and from the
    memberships table -- nothing in it is copied from the request. Under `dev`
    it is still read from `X-Actor-*`, which is a claim the client writes about
    itself and is why the flag defaults the other way (ADR-0014).
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

    def __call__(self, history: dict, places: list[dict]) -> dict | None: ...


class ContextualSuggester(Protocol):
    """A model backend that returns an untrusted, raw F33 card.

    Separate from `Suggester` on purpose. This one is handed a digest of what
    the group just *said*, which is the only place in the product where a
    member's own sentences are put in front of a model; keeping the two seams
    apart means a test that stubs one cannot silently stand in for the other,
    and the riskier prompt cannot inherit the safer one's envelope by accident.
    """

    def __call__(self, digest: dict, places: list[dict]) -> dict | None: ...


class Reeler(Protocol):
    """A model backend that returns an untrusted, raw F37 reel."""

    def __call__(self, trip: dict, memories: list[dict]) -> dict | None: ...


def _csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def bearer_token(authorization: str | None) -> str:
    """The token out of an `Authorization` header, or 401.

    A malformed header and a missing one answer identically. "Bearer" is
    matched case-insensitively because RFC 7235 says the scheme is, and a
    client that capitalises it differently is not an attacker.
    """

    if authorization is None:
        raise ApiProblem(401, "authentication_required", "Missing bearer session")
    scheme, _, value = authorization.partition(" ")
    token = value.strip()
    if scheme.lower() != "bearer" or not token:
        raise ApiProblem(401, "authentication_required", "Missing bearer session")
    return token


def get_actor(
    request: Request,
    repository: Annotated[ApiRepository, Depends(get_repository)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    actor_id: Annotated[str | None, Header(alias="X-Actor-ID")] = None,
    actor_roles: Annotated[str | None, Header(alias="X-Actor-Roles")] = None,
    actor_contexts: Annotated[str | None, Header(alias="X-Actor-Contexts")] = None,
) -> Actor:
    """The identity for this request.

    The mode is read off the application rather than the environment on every
    call, so a test can build one app of each kind in one process and neither
    can drift from what it was created as.

    In `prod` the `X-Actor-*` parameters are still declared and still ignored.
    Removing them would have been the tidier signature and the worse
    behaviour: a client that keeps sending them gets a plain 401 rather than a
    422 about an unexpected header, and the schema keeps saying they exist for
    the mode where they still work.
    """

    mode = getattr(request.app.state, "auth_mode", PROD)
    if not trusts_actor_headers(mode):
        # Imported here because `app.api.service` imports this module for
        # `Actor`; the auth check lives in the service so that the session
        # rules have one implementation rather than two.
        from app.api.service import ApiService

        return ApiService(repository).actor_for_session_token(
            bearer_token(authorization)
        )

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


def get_repository(request: Request) -> Generator[ApiRepository]:
    factory = get_session_factory()
    session = factory()
    register_session(request, session)
    try:
        yield SqlAlchemyApiRepository(session)
    except BaseException:
        session.rollback()
        raise
    else:
        if session.in_transaction():
            session.commit()
    finally:
        session.close()


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


def get_face_detector() -> FaceDetector:
    """Seam for tests, and the shipped local detector for everyone else.

    Imported lazily like its neighbours, but for a different reason. Those
    defer a *credential*; this defers a *wheel*. `opencv-python-headless` is
    the largest dependency the image carries, and importing it at module scope
    would mean a machine without it cannot start the API at all rather than
    losing one route -- the shape of the outage that killed the demo box on
    2026-08-30.

    Note what is not here: no parameter. A caller cannot name a detector,
    because a seam reachable from a request body is not a seam, it is a way to
    choose which code runs over somebody else's photograph.
    """

    from app.media.face_detection import HaarFaceDetector

    return HaarFaceDetector()


def get_contextual_suggester() -> ContextualSuggester:
    """Seam for tests, and the F33 backend for everyone else.

    Not memoised, for the reason above and one more: a contextual card is a
    function of one group's last few messages, and any cache coarser than that
    would hand one group's conversation to another.
    """

    from app.api.suggestion_gemini import gemini_contextual_suggestion

    return gemini_contextual_suggestion


def get_reeler() -> Reeler:
    """Seam for tests, and the uncached F37 backend for everyone else."""

    from app.api.reel_gemini import gemini_reel

    return gemini_reel


def get_sms_sender(request: Request):
    """The SMS seam the application was built with (see `app.api.sms`)."""
    return request.app.state.sms_sender


def get_otp_debug_code(request: Request) -> str | None:
    """The fixed OTP code, only ever set beside the log sender."""
    return getattr(request.app.state, "otp_debug_code", None)


def get_google_verifier(request: Request):
    """The Google ID-token verifier, or `None` on a host with no client ids."""
    return getattr(request.app.state, "google_verifier", None)
