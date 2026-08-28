"""FastAPI application for the group-expense vertical slice."""

from __future__ import annotations

import pathlib

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.cors import install_cors
from app.api.errors import ApiProblem
from app.api.routes import batches, contexts, expenses, guests, obligations
from app.api.schemas import ErrorResponse

WEB_ROOT = pathlib.Path(__file__).resolve().parents[1] / "web"


def create_app() -> FastAPI:
    application = FastAPI(title="Group Expense API", version="0.1.0")
    # Outermost layer on purpose: an error response without the allow-origin
    # header reaches the browser as an opaque network failure, which hides the
    # status the client needed to read.
    install_cors(application)
    application.mount(
        "/static",
        StaticFiles(directory=str(WEB_ROOT / "static")),
        name="static",
    )
    application.include_router(expenses.router)
    application.include_router(contexts.router)
    application.include_router(batches.router)
    application.include_router(guests.router)
    application.include_router(obligations.router)

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
    async def api_problem_handler(_request: Request, exc: ApiProblem) -> JSONResponse:
        body = ErrorResponse(code=exc.code, detail=exc.detail)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    return application


app = create_app()
