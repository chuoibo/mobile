"""FastAPI application for the group-expense vertical slice."""

from __future__ import annotations

import logging
import pathlib
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth_mode import AUTH_MODE_ENV_VAR, resolve_auth_mode
from app.api.cors import install_cors
from app.api.errors import GUEST_LINK_NOT_FOUND, ApiProblem
from app.api.guest_privacy import (
    GuestPrivacyHeadersMiddleware,
    guest_aware_server_error_response,
    is_guest_path,
)
from app.api.idempotency import (
    IdempotencyMiddleware,
    IdempotencyStore,
    IdempotencyStoreFactory,
    SqlAlchemyIdempotencyStore,
)
from app.api.routes import (
    albums,
    bank_recipients,
    batches,
    bills,
    budget,
    contexts,
    expenses,
    faces,
    finance,
    friends,
    guests,
    identity,
    memories,
    messages,
    obligations,
    outings,
    people,
    photos,
    places,
    posts,
    preferences,
    recap,
    receipts,
    screenshots,
    sessions,
    social_map,
    suggestions,
    votes,
)
from app.api.routes.places import CachedReasonWriter
from app.api.schemas import ErrorResponse
from app.api.search_rate_limit import (
    build_chat_expense_limiter,
    build_companion_turn_limiter,
    build_contextual_suggestion_limiter,
    build_face_detection_limiter,
    build_receipt_scan_limiter,
    build_reel_limiter,
    build_screenshot_scan_limiter,
    build_search_limiter,
    build_suggestion_limiter,
)
from app.api.unit_of_work import install_commit_before_response
from app.db.session import get_session_factory

WEB_ROOT = pathlib.Path(__file__).resolve().parents[1] / "web"


@contextmanager
def sqlalchemy_store_factory() -> Iterator[IdempotencyStore]:
    """One short transaction per idempotency operation.

    Reservation has to be visible to other processes before the handler runs,
    so it cannot ride along inside the request's own transaction. The engine is
    built lazily, which keeps importing this module free of database access.
    """

    factory = get_session_factory()
    with factory.begin() as session:
        yield SqlAlchemyIdempotencyStore(session)


LOGGER = logging.getLogger("app.api")


def create_app(
    *,
    auth_mode: str | None = None,
    idempotency_store_factory: IdempotencyStoreFactory | None = None,
    idempotency_in_flight_wait_seconds: float | None = None,
) -> FastAPI:
    application = FastAPI(title="Group Expense API", version="0.1.0")

    # Resolved once, here, and read off the app afterwards. An environment
    # consulted per request could answer differently halfway through the life
    # of a process, and a test could not hold one app of each kind at once.
    # `None` means "ask the environment", where absent means prod.
    resolved_auth_mode = (
        resolve_auth_mode()
        if auth_mode is None
        else resolve_auth_mode({AUTH_MODE_ENV_VAR: auth_mode})
    )
    application.state.auth_mode = resolved_auth_mode
    # Said out loud at startup because the dangerous configuration is the
    # silent one: a box that kept trusting `X-Actor-*` looks exactly like a box
    # that does not, until somebody sends a header.
    LOGGER.info("auth mode: %s", resolved_auth_mode)

    # Per application, not per module: `POST /places/search` spends real model
    # quota, and the window that caps it has to outlive a request while not
    # outliving the app that owns it. See `app/api/search_rate_limit.py`.
    application.state.search_limiter = build_search_limiter()
    # `POST /receipts/scan` spends the same key on a vision call. Its own
    # window, not a share of the one above: see `build_receipt_scan_limiter`.
    application.state.receipt_scan_limiter = build_receipt_scan_limiter()
    # F24 is text rather than vision, but it spends the same shared model key.
    # Its own counter keeps a burst on one feature from disabling the other.
    application.state.chat_expense_limiter = build_chat_expense_limiter()
    # F26 uses vision too, but owns a fourth window so retries do not consume
    # the bill reader's allowance.
    application.state.screenshot_scan_limiter = build_screenshot_scan_limiter()
    # The companion talks with the same key. `plan_turn` is a conversation
    # cadence and not a ceiling -- the caller lifts it by saying one more
    # thing -- so the turn needs a window like every other model route.
    application.state.companion_turn_limiter = build_companion_turn_limiter()
    # And the proactive card, which had nothing at all in front of it: no
    # cache, no cadence, one model call per GET.
    application.state.suggestion_limiter = build_suggestion_limiter()
    # `GET /places` is the seventh door onto the same key and the only one with
    # no actor to key a window on. It is capped by a cache rather than a
    # window, which is why it is built here and not above -- but for the same
    # reason, and it belongs to the app for the same reason the limiters do.
    # See `CachedReasonWriter`: caching successes only made a row the model
    # refused cost a model call on every request.
    application.state.reason_writer = CachedReasonWriter()
    # F33 is the eighth door. It reads the group's live conversation, so it
    # cannot borrow the cache that caps the seventh -- two people typing
    # different things must not be served one another's answer -- which leaves
    # one model call per GET, on a screen that opens often. Hence its own
    # window, distinct from both the proactive card's and the cache above.
    application.state.contextual_suggestion_limiter = (
        build_contextual_suggestion_limiter()
    )
    # F22 runs its model locally, so this window guards the box's CPU rather
    # than the shared key -- and a member looping it is the cheapest way to
    # stop this API answering anything at all, money routes included.
    application.state.face_detection_limiter = build_face_detection_limiter()
    # F37 is the tenth model door and the ninth actor-keyed window.  It owns a
    # distinct object because a burst of reel-building must not spend the
    # allowance the group needs to read its own chat.
    application.state.reel_limiter = build_reel_limiter()

    application.mount(
        "/static",
        StaticFiles(directory=str(WEB_ROOT / "static")),
        name="static",
    )
    application.include_router(expenses.router)
    application.include_router(friends.router)
    application.include_router(bills.router)
    application.include_router(budget.router)
    application.include_router(contexts.router)
    application.include_router(memories.router)
    application.include_router(photos.router)
    application.include_router(posts.router)
    application.include_router(outings.router)
    application.include_router(messages.router)
    application.include_router(batches.router)
    application.include_router(guests.router)
    application.include_router(obligations.router)
    application.include_router(bank_recipients.router)
    application.include_router(people.router)
    application.include_router(sessions.router)
    application.include_router(identity.router)
    application.include_router(places.router)
    application.include_router(finance.router)
    application.include_router(recap.router)
    application.include_router(receipts.router)
    application.include_router(screenshots.router)
    application.include_router(suggestions.router)
    application.include_router(social_map.router)
    application.include_router(votes.router)
    application.include_router(albums.router)
    application.include_router(preferences.router)
    application.include_router(faces.router)

    # Middleware, not a decorator on each route: a write route added later is
    # covered the moment it is registered, with no list for anyone to forget.
    # `/receipts/scan` is the first one to arrive after that was written, and it
    # arrived covered without a line being added here -- which is the point, and
    # also worth knowing before reading its tests: a scan carrying a key is a
    # database-backed request, though the route itself still stores nothing.
    idempotency_options = {}
    if idempotency_in_flight_wait_seconds is not None:
        # Only tests pass this. They cannot afford to sit through the real wait
        # for a key that, by construction, nobody is ever going to finish.
        idempotency_options["in_flight_wait_seconds"] = (
            idempotency_in_flight_wait_seconds
        )
    application.add_middleware(
        IdempotencyMiddleware,
        store_factory=idempotency_store_factory or sqlalchemy_store_factory,
        **idempotency_options,
    )

    # Same argument as the layer above, on the other boundary: the guest URL
    # carries its own credential, so every answer under `/g` needs the same
    # no-store / no-referrer / noindex headers -- including the 404 for a token
    # that has been revoked, which is the answer most likely to be forwarded.
    # As a decorator on each handler this was already wrong on three of the
    # seven guest routes.
    application.add_middleware(GuestPrivacyHeadersMiddleware)

    # The one guest answer the middleware above cannot reach. Starlette's
    # `ServerErrorMiddleware` is prepended ahead of every middleware installed
    # here, so an unhandled exception unwinds past that layer and its 500 goes
    # out from above it -- bare. Handling `Exception` here runs *inside* that
    # outermost layer, which is the only place a crash page under `/g` can still
    # be stamped. Non-guest crashes keep Starlette's own answer, unchanged.
    application.add_exception_handler(Exception, guest_aware_server_error_response)

    # Installed last, which is what puts it outermost: `add_middleware`
    # prepends, and the first entry wraps everything after it.
    #
    # Outermost on purpose, and the order matters more than it looks. The
    # idempotency layer answers three refusals entirely on its own, before any
    # route is reached. Inside the CORS layer those answers go out with no
    # allow-origin header, the browser discards them, and the web build sees an
    # opaque network failure instead of the code it needs in order to say
    # anything useful to the person standing over their own money.
    install_cors(application)

    @application.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        """Liveness only: the process is up and can serve a request.

        Deliberately does NOT touch the database. A health check that fails
        when Postgres blips will have the orchestrator kill a process that was
        fine, and restarting the API does not fix a database. Readiness, when
        it is needed, belongs in a separate endpoint that says so.
        """
        return {"status": "ok"}

    @application.exception_handler(ApiProblem)
    async def api_problem_handler(request: Request, exc: ApiProblem) -> Response:
        """One branch, and only one: the guest boundary answers people.

        Everywhere else an `ApiProblem` is read by a client we wrote. Under
        `/g` it is read by a stranger on a phone who was sent a link, and a
        token that resolves to nothing is the answer they are most likely to
        get -- chat clients truncate long URLs when forwarding them, so a
        correct link arrives here missing its tail. That branch was handing
        them `{"code":"guest_link_not_found"}` in English while the repo
        already owned the right wording for a link that stopped working.

        Only this one code is redirected. An expired or revoked link is a
        different fact and already has its own page; every other problem under
        `/g` stays machine-readable.
        """

        if exc.code == GUEST_LINK_NOT_FOUND and is_guest_path(request.url.path):
            return guests.guest_link_broken_page(request)
        body = ErrorResponse(code=exc.code, detail=exc.detail)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @application.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request, exc: RequestValidationError
    ) -> Response:
        """A 422 says which field was wrong. It does not repeat what was sent.

        FastAPI's default handler puts the rejected value into `input`,
        verbatim. That is fine for an integer out of range and is a data leak
        for anything a person typed: a group chat message, a caption, a
        comment under a photograph. A validation error is also the part of a
        response most likely to be pasted into a bug report or a chat, which
        is precisely how private text travels furthest.

        Measured before the change, on `POST /contexts/{id}/memories/{id}/comments`
        with a 5800-character body: the 422 carried all 5800 characters back.
        The same shape existed on `messages.body` and on every other free-text
        field in the product, so this is fixed here rather than per route --
        one handler cannot be forgotten by the next field somebody adds.

        `type`, `loc` and `msg` stay. They name the field and the rule it
        broke, which is what a client needs, and none of them is a copy of the
        request: every `ValueError` raised by this app's validators carries a
        constant message.
        """

        redacted = [
            {key: value for key, value in error.items() if key != "input"}
            for error in exc.errors()
        ]
        # `jsonable_encoder` because `ctx` can hold a live exception object,
        # which is what FastAPI's own handler passes through it too.
        return JSONResponse(
            status_code=422, content=jsonable_encoder({"detail": redacted})
        )

    # Install last so every APIRoute commits its sessions before sending the body.
    install_commit_before_response(application)
    return application


app = create_app()
