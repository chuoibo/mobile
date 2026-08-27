"""FastAPI application for the group-expense vertical slice."""

from __future__ import annotations

import pathlib

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.errors import ApiProblem
from app.api.routes import batches, expenses, guests, obligations
from app.api.schemas import ErrorResponse

WEB_ROOT = pathlib.Path(__file__).resolve().parents[1] / "web"


def create_app() -> FastAPI:
    application = FastAPI(title="Group Expense API", version="0.1.0")
    application.mount(
        "/static",
        StaticFiles(directory=str(WEB_ROOT / "static")),
        name="static",
    )
    application.include_router(expenses.router)
    application.include_router(batches.router)
    application.include_router(guests.router)
    application.include_router(obligations.router)

    @application.exception_handler(ApiProblem)
    async def api_problem_handler(_request: Request, exc: ApiProblem) -> JSONResponse:
        body = ErrorResponse(code=exc.code, detail=exc.detail)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    return application


app = create_app()
