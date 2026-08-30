"""Authenticated transaction-screenshot scanning endpoint."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, UploadFile

from app.api.deps import Actor, get_actor, get_screenshot_reader
from app.api.errors import ApiProblem
from app.api.schemas import ErrorResponse, ScreenshotScanResponse
from app.api.screenshot_skill import ScreenshotReader, run_screenshot_skill
from app.api.search_rate_limit import FixedWindowLimiter
from app.domain.screenshot import ScreenshotError

router = APIRouter(tags=["screenshots"])
_LOGGER = logging.getLogger(__name__)

_UNSUPPORTED_IMAGE_DETAIL = "Định dạng ảnh chụp màn hình không được hỗ trợ."
_IMAGE_TOO_LARGE_DETAIL = "Ảnh chụp màn hình vượt quá giới hạn 8 MB."
_SCREENSHOT_UNREADABLE_DETAIL = (
    "Không đọc được giao dịch từ ảnh chụp màn hình. Vui lòng kiểm tra ảnh."
)
_NOT_A_TRANSACTION_DETAIL = (
    "Ảnh này không thể hiện một giao dịch đã hoàn tất để tạo khoản chi."
)
_MODEL_NAMED_PERSON_DETAIL = (
    "AI đã cố nêu một người; kết quả bị từ chối để định danh chỉ đến từ "
    "phiên đăng nhập."
)
_READER_UNAVAILABLE_DETAIL = (
    "Dịch vụ đọc ảnh chụp màn hình đang lỗi phía máy chủ. Vui lòng thử lại sau."
)
_READER_NOT_CONFIGURED_DETAIL = (
    "Máy chủ chưa cấu hình khoá đọc ảnh chụp màn hình. Đây là lỗi cấu hình "
    "phía máy chủ, không phải ảnh bạn tải lên."
)


def get_screenshot_scan_limiter(request: Request) -> FixedWindowLimiter:
    """Resolve the one F26 limiter owned by this application instance."""

    return request.app.state.screenshot_scan_limiter


@router.post(
    "/screenshots/scan",
    response_model=ScreenshotScanResponse,
    responses={
        401: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def scan_screenshot(
    image: UploadFile,
    actor: Annotated[Actor, Depends(get_actor)],
    reader: Annotated[ScreenshotReader, Depends(get_screenshot_reader)],
    limiter: Annotated[FixedWindowLimiter, Depends(get_screenshot_scan_limiter)],
) -> ScreenshotScanResponse:
    """Read one private upload without echoing its pixels or transcription."""

    limiter.check(actor.id)
    try:
        result = run_screenshot_skill(
            image.file.read(),
            image.content_type or "",
            reader=reader,
        )
        return ScreenshotScanResponse.model_validate(result)
    except ScreenshotError as exc:
        # Log only the closed code. Pixels, transcription, and provider output
        # are private financial data and never belong in diagnostic text.
        _LOGGER.info("screenshot scan refused: %s", exc.code)
        if exc.code == "UNSUPPORTED_IMAGE_TYPE":
            raise ApiProblem(
                415,
                "unsupported_image_type",
                _UNSUPPORTED_IMAGE_DETAIL,
            ) from None
        if exc.code == "IMAGE_TOO_LARGE":
            raise ApiProblem(
                413,
                "image_too_large",
                _IMAGE_TOO_LARGE_DETAIL,
            ) from None
        if exc.code == "NOT_A_TRANSACTION":
            raise ApiProblem(
                422,
                "not_a_transaction",
                _NOT_A_TRANSACTION_DETAIL,
            ) from None
        if exc.code == "MODEL_NAMED_A_PERSON":
            raise ApiProblem(
                422,
                "screenshot_model_named_a_person",
                _MODEL_NAMED_PERSON_DETAIL,
            ) from None
        if exc.code == "SCREENSHOT_READER_NOT_CONFIGURED":
            raise ApiProblem(
                503,
                "screenshot_reader_not_configured",
                _READER_NOT_CONFIGURED_DETAIL,
            ) from None
        raise ApiProblem(
            422,
            "screenshot_unreadable",
            _SCREENSHOT_UNREADABLE_DETAIL,
        ) from None
    except Exception as exc:
        _LOGGER.warning("screenshot reader failed (%s)", type(exc).__name__)
        raise ApiProblem(
            502,
            "screenshot_reader_unavailable",
            _READER_UNAVAILABLE_DETAIL,
        ) from None
