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
import uuid

from app.api.errors import ApiProblem
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


def _page(request: Request, name: str, view: dict, token: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name=name,
        context={"view": view, "preview": NEUTRAL_PREVIEW, "token": token},
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


@router.get("/g/{token}/khong-phai-toi", response_class=HTMLResponse)
def not_me_page(
    request: Request,
    token: Token,
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> HTMLResponse:
    """Spec section 8.6 lists this beside "yes, show me how to transfer".

    It used to be a link to a route that did not exist, so pressing it gave a
    404: the page invited an objection and then behaved as though objecting had
    broken something.
    """
    return _page(request, "guest_not_me.html", ApiService(repository).not_me_view(token), token)


@router.post("/g/{token}/khong-phai-toi", response_class=HTMLResponse)
def not_me_submit(
    request: Request,
    token: Token,
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> HTMLResponse:
    service = ApiService(repository)
    # Read the names before objecting: recording it revokes the link, and after
    # that the envelope refuses to load. Rendering empty strings put a blank
    # where the reader had just been shown a name, and left the confirmation
    # telling them nothing about who to contact.
    seen = service.not_me_view(token)
    service.record_objection(token, "not_me", None, None)
    return _page(
        request,
        "guest_not_me.html",
        {
            "claimed_person_display_name": seen["claimed_person_display_name"],
            "recorded_by_display_name": seen["recorded_by_display_name"],
            "already_reported": True,
            "can_object": False,
        },
        token,
    )


@router.get("/g/{token}/doi-so-tien", response_class=HTMLResponse)
def wrong_amount_page(
    request: Request,
    token: Token,
    repository: Annotated[ApiRepository, Depends(get_repository)],
    obligation_id: str | None = None,
) -> HTMLResponse:
    service = ApiService(repository)
    if obligation_id is None:
        view = service.guest_view(token)
        if not view["blocks"]:
            raise ApiProblem(409, "no_open_obligation", "Nothing to dispute on this link")
        obligation_id = view["blocks"][0]["obligation_id"]
    return _page(
        request, "guest_wrong_amount.html", service.wrong_amount_view(token, obligation_id), token
    )


@router.post("/g/{token}/doi-so-tien", response_class=RedirectResponse)
def wrong_amount_submit(
    token: Token,
    repository: Annotated[ApiRepository, Depends(get_repository)],
    obligation_id: Annotated[str, Form()],
    reason: Annotated[str, Form()],
) -> RedirectResponse:
    ApiService(repository).record_objection(
        token, "wrong_amount", uuid.UUID(obligation_id), reason
    )
    return RedirectResponse(url=f"/g/{token}", status_code=303)


@router.post("/g/{token}/xin-cach-tinh", response_class=RedirectResponse)
def request_evidence(
    token: Token,
    repository: Annotated[ApiRepository, Depends(get_repository)],
    obligation_id: Annotated[str, Form()],
) -> RedirectResponse:
    """Section 10.5: the charged party may ask for redacted evidence.

    Asking is all this does. If the person who recorded the expense declines,
    the dispute stands and collection stays stopped -- the system must never
    read missing evidence as the charged party being wrong.
    """
    ApiService(repository).record_objection(
        token, "evidence_request", uuid.UUID(obligation_id), None
    )
    return RedirectResponse(url=f"/g/{token}/doi-so-tien?obligation_id={obligation_id}", status_code=303)
