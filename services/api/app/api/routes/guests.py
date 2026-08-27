"""Bearer-capability guest page and sender self-report endpoint."""

from __future__ import annotations

import pathlib
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Path, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.deps import get_repository
from app.api.repository import ApiRepository
from app.api.schemas import ErrorResponse, PaymentReportRequest, PaymentReportResponse
from app.api.service import ApiService
from app.web.guest_view import NEUTRAL_PREVIEW

router = APIRouter(tags=["guests"])
WEB_ROOT = pathlib.Path(__file__).resolve().parents[2] / "web"
templates = Jinja2Templates(directory=str(WEB_ROOT / "templates"))
Token = Annotated[
    str,
    Path(min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
]


@router.get(
    "/g/{token}",
    response_class=HTMLResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def guest_page(
    request: Request,
    token: Token,
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> HTMLResponse:
    # The only object handed to Jinja is the closed view model. The raw query
    # projection never enters the template context.
    view = ApiService(repository).guest_view(token)
    return templates.TemplateResponse(
        request=request,
        name="guest.html",
        context={"view": view, "preview": NEUTRAL_PREVIEW, "token": token},
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


@router.post(
    "/g/{token}/da-chuyen",
    response_model=PaymentReportResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        303: {"description": "Browser form submitted; render the guest page again"},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def report_payment(
    http_request: Request,
    token: Token,
    request: Annotated[PaymentReportRequest, Form()],
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> PaymentReportResponse | RedirectResponse:
    response = ApiService(repository).report_payment(token, request)
    if "text/html" in http_request.headers.get("accept", ""):
        return RedirectResponse(url=f"/g/{token}", status_code=303)
    return response
