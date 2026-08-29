"""FastAPI application for the group-expense vertical slice."""

from __future__ import annotations

import pathlib
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

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
    bank_recipients,
    batches,
    bills,
    contexts,
    expenses,
    finance,
    guests,
    identity,
    memories,
    messages,
    obligations,
    outings,
    people,
    places,
    recap,
    receipts,
    suggestions,
)
from app.api.schemas import ErrorResponse
from app.api.search_rate_limit import build_search_limiter
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


def create_app(
    *,
    idempotency_store_factory: IdempotencyStoreFactory | None = None,
    idempotency_in_flight_wait_seconds: float | None = None,
) -> FastAPI:
    application = FastAPI(title="Group Expense API", version="0.1.0")

    # Per application, not per module: `POST /places/search` spends real model
    # quota, and the window that caps it has to outlive a request while not
    # outliving the app that owns it. See `app/api/search_rate_limit.py`.
    application.state.search_limiter = build_search_limiter()

    application.mount(
        "/static",
        StaticFiles(directory=str(WEB_ROOT / "static")),
        name="static",
    )
    application.include_router(expenses.router)
    application.include_router(bills.router)
    application.include_router(contexts.router)
    application.include_router(memories.router)
    application.include_router(outings.router)
    application.include_router(messages.router)
    application.include_router(batches.router)
    application.include_router(guests.router)
    application.include_router(obligations.router)
    application.include_router(bank_recipients.router)
    application.include_router(people.router)
    application.include_router(identity.router)
    application.include_router(places.router)
    application.include_router(finance.router)
    application.include_router(recap.router)
    application.include_router(receipts.router)
    application.include_router(suggestions.router)

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

    return application


app = create_app()
