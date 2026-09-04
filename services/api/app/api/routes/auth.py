"""The OTP doors and the Google door (ADR-0016). No actor: an identity is obtained here.

Bodies are parsed by hand for the same reason `routes/identity.py` parses its
own: FastAPI's validation error echoes the offending value, and the value here
is a telephone number or a bearer-grade ID token. No example number appears in
this file -- the repo guard refuses digit runs shaped like one.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    get_google_verifier,
    get_otp_debug_code,
    get_repository,
    get_sms_sender,
)
from app.api.errors import ApiProblem
from app.api.google_identity import GoogleTokenVerifier
from app.api.repository import ApiRepository
from app.api.routes.identity import FixedWindowLimit
from app.api.schemas import ErrorResponse, OtpRequestResponse, SessionResponse
from app.api.service import ApiService
from app.api.sms import SmsSender

router = APIRouter(tags=["auth"])

REQUEST_LIMIT = 10
VERIFY_LIMIT = 30
GOOGLE_LIMIT = 10
WINDOW_SECONDS = 60.0

_PHONE_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["phone"],
                    "properties": {"phone": {"type": "string"}},
                }
            }
        },
    }
}
_VERIFY_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["challenge_id", "phone", "code"],
                    "properties": {
                        "challenge_id": {"type": "string", "format": "uuid"},
                        "phone": {"type": "string"},
                        "code": {"type": "string"},
                    },
                }
            }
        },
    }
}
_GOOGLE_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["id_token"],
                    "properties": {"id_token": {"type": "string"}},
                }
            }
        },
    }
}
GOOGLE_ERRORS = {
    401: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}
ERRORS = {
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


def _limit(request: Request, name: str, limit: int) -> FixedWindowLimit:
    existing = getattr(request.app.state, name, None)
    if existing is None:
        existing = FixedWindowLimit(limit=limit, window_seconds=WINDOW_SECONDS)
        setattr(request.app.state, name, existing)
    return existing


def _caller(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _json_object(request: Request) -> dict:
    try:
        body = await request.json()
    except ValueError as broken:
        raise ApiProblem(422, "invalid_body", "Thân yêu cầu phải là JSON.") from broken
    if not isinstance(body, dict):
        raise ApiProblem(
            422, "invalid_body", "Thân yêu cầu phải là một đối tượng JSON."
        )
    return body


@router.post(
    "/auth/otp/request",
    response_model=OtpRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=ERRORS,
    openapi_extra=_PHONE_BODY,
)
async def request_otp(
    request: Request,
    repository: Annotated[ApiRepository, Depends(get_repository)],
    sender: Annotated[SmsSender, Depends(get_sms_sender)],
    debug_code: Annotated[str | None, Depends(get_otp_debug_code)],
) -> OtpRequestResponse:
    if not _limit(request, "otp_request_limit", REQUEST_LIMIT).allow(_caller(request)):
        raise ApiProblem(429, "rate_limited", "Thử lại sau một phút.")
    body = await _json_object(request)
    return ApiService(repository).request_otp(
        body.get("phone"), sender=sender, debug_code=debug_code
    )


@router.post(
    "/auth/otp/verify",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    openapi_extra=_VERIFY_BODY,
)
async def verify_otp(
    request: Request,
    repository: Annotated[ApiRepository, Depends(get_repository)],
) -> SessionResponse:
    if not _limit(request, "otp_verify_limit", VERIFY_LIMIT).allow(_caller(request)):
        raise ApiProblem(429, "rate_limited", "Thử lại sau một phút.")
    body = await _json_object(request)
    raw_id = body.get("challenge_id")
    try:
        challenge_id = UUID(str(raw_id)) if isinstance(raw_id, str) else None
    except ValueError:
        challenge_id = None
    if challenge_id is None:
        raise ApiProblem(422, "challenge_id_invalid", "Thiếu hoặc sai challenge_id.")
    return ApiService(repository).verify_otp(
        challenge_id, body.get("phone"), body.get("code")
    )


@router.post(
    "/auth/google",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=GOOGLE_ERRORS,
    openapi_extra=_GOOGLE_BODY,
)
async def login_google(
    request: Request,
    repository: Annotated[ApiRepository, Depends(get_repository)],
    verifier: Annotated[GoogleTokenVerifier | None, Depends(get_google_verifier)],
) -> SessionResponse:
    if not _limit(request, "google_login_limit", GOOGLE_LIMIT).allow(_caller(request)):
        raise ApiProblem(429, "rate_limited", "Thử lại sau một phút.")
    body = await _json_object(request)
    return ApiService(repository).login_with_google(
        body.get("id_token"), verifier=verifier
    )
