"""Authenticated receipt-image scanning endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile

from app.api.deps import Actor, get_actor, get_receipt_reader
from app.api.errors import ApiProblem
from app.api.receipt_skill import ReceiptReader, run_receipt_skill
from app.api.schemas import ErrorResponse, ReceiptScanResponse
from app.domain.receipt import ReceiptError

router = APIRouter(tags=["receipts"])

_UNSUPPORTED_IMAGE_DETAIL = "Định dạng ảnh không được hỗ trợ."
_IMAGE_TOO_LARGE_DETAIL = "Ảnh bill vượt quá giới hạn 8 MB."
_RECEIPT_UNREADABLE_DETAIL = "Không đọc được bill. Vui lòng kiểm tra ảnh và thử lại."
_READER_UNAVAILABLE_DETAIL = "Không đọc được bill lúc này, thử lại sau."


@router.post(
    "/receipts/scan",
    response_model=ReceiptScanResponse,
    responses={
        401: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
def scan_receipt(
    image: UploadFile,
    actor: Annotated[Actor, Depends(get_actor)],
    reader: Annotated[ReceiptReader, Depends(get_receipt_reader)],
) -> ReceiptScanResponse:
    """Read one upload without echoing image bytes or upstream failures."""

    del actor
    try:
        content = image.file.read()
        result = run_receipt_skill(
            content,
            image.content_type or "",
            reader=reader,
        )
        return ReceiptScanResponse.model_validate(result)
    except ReceiptError as exc:
        if exc.code == "UNSUPPORTED_IMAGE_TYPE":
            raise ApiProblem(
                415,
                "unsupported_image_type",
                _UNSUPPORTED_IMAGE_DETAIL,
            ) from None
        if exc.code == "IMAGE_TOO_LARGE":
            raise ApiProblem(413, "image_too_large", _IMAGE_TOO_LARGE_DETAIL) from None
        raise ApiProblem(
            422,
            "receipt_unreadable",
            _RECEIPT_UNREADABLE_DETAIL,
        ) from None
    except Exception:
        raise ApiProblem(
            502,
            "receipt_reader_unavailable",
            _READER_UNAVAILABLE_DETAIL,
        ) from None
