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
_RECEIPT_TOO_BLURRY_DETAIL = "Ảnh bill quá mờ. Vui lòng chụp lại ảnh rõ hơn."
# One wire code, two sentences. The app branches once; the person gets told
# which mistake they actually made. The price-list wording exists because that
# is the mistake a real table produces: the menu lies next to the bill.
_PRICE_LIST_DETAIL = (
    "Đây là thực đơn hoặc bảng giá, không phải hoá đơn. Bảng giá chỉ nói món "
    "bao nhiêu tiền, không nói ai đã gọi gì, nên không chia tiền được. "
    "Hãy chụp tờ bill có dòng tổng tiền."
)
_NOT_A_RECEIPT_DETAIL = (
    "Ảnh này không phải hoá đơn. Hãy chụp tờ bill có danh sách món và dòng "
    "tổng tiền."
)
_READER_UNAVAILABLE_DETAIL = "Không đọc được bill lúc này, thử lại sau."
# A server with no credential is not a bad photograph, and must not be
# answerable with the same code as one. rd-qa-05 measured what happens when it
# is: a stack built by `make up` answered `422 receipt_unreadable` in 2.5ms --
# no network call, just a missing variable -- while the same image on a process
# with the key returned eight items in 7.06s. On a stage the presenter re-shoots
# the bill three times before suspecting the server, because every signal they
# can see says the photo was the problem. A distinct code is what lets the
# client, and the person reading the response, tell the two faults apart.
_READER_NOT_CONFIGURED_DETAIL = (
    "Máy chủ chưa cấu hình khoá đọc bill nên không gọi được AI. Đây là lỗi "
    "cấu hình phía máy chủ, không phải ảnh bạn chụp — chụp lại cũng không "
    "giúp được. Người dựng hệ cần đặt biến GEMINI_API_KEY rồi khởi động lại API."
)


@router.post(
    "/receipts/scan",
    response_model=ReceiptScanResponse,
    responses={
        401: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
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
        if exc.code == "RECEIPT_TOO_BLURRY":
            raise ApiProblem(
                422,
                "receipt_too_blurry",
                _RECEIPT_TOO_BLURRY_DETAIL,
            ) from None
        if exc.code == "RECEIPT_READER_NOT_CONFIGURED":
            # 503 and not 422: nothing the caller sends can fix this, so it is
            # not their request that is wrong. 502 next door means "the
            # upstream call failed"; here no call was attempted at all.
            raise ApiProblem(
                503,
                "receipt_reader_not_configured",
                _READER_NOT_CONFIGURED_DETAIL,
            ) from None
        if exc.code in {"NOT_A_RECEIPT", "NOT_A_RECEIPT_PRICE_LIST"}:
            raise ApiProblem(
                422,
                "not_a_receipt",
                _PRICE_LIST_DETAIL
                if exc.code == "NOT_A_RECEIPT_PRICE_LIST"
                else _NOT_A_RECEIPT_DETAIL,
            ) from None
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
