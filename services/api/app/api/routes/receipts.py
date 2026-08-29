"""Authenticated receipt-image scanning endpoint."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, UploadFile

from app.api.deps import Actor, get_actor, get_receipt_reader
from app.api.errors import ApiProblem
from app.api.receipt_skill import ReceiptReader, run_receipt_skill
from app.api.schemas import ErrorResponse, ReceiptScanResponse
from app.api.search_rate_limit import FixedWindowLimiter
from app.domain.receipt import ReceiptError

router = APIRouter(tags=["receipts"])


def get_receipt_scan_limiter(request: Request) -> FixedWindowLimiter:
    """Seam for tests, resolving the one object `create_app` built.

    Read off the application, never constructed here: a limiter built per
    request counts to one and forgets, which is a limiter-shaped object that
    limits nothing.
    """

    return request.app.state.receipt_scan_limiter

# Seven of the domain's refusal codes share one wire code and one sentence, so
# the access log recorded the same `422` line for all of them -- and for a
# malformed `X-Actor-ID` too. rd-qa-38 grepped the full logs of five failing
# scans and found zero lines naming a cause. The code is the only thing written
# down here: a bill photograph is private data and so is its transcription, so
# neither the reading nor the image may ever reach a log line.
_LOGGER = logging.getLogger(__name__)

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
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def scan_receipt(
    image: UploadFile,
    actor: Annotated[Actor, Depends(get_actor)],
    reader: Annotated[ReceiptReader, Depends(get_receipt_reader)],
    limiter: Annotated[FixedWindowLimiter, Depends(get_receipt_scan_limiter)],
) -> ReceiptScanResponse:
    """Read one upload without echoing image bytes or upstream failures."""

    # Before the body is read and before the model is reached, because a 429
    # raised after the vision call has already spent what it was refusing.
    limiter.check(actor.id)
    try:
        content = image.file.read()
        result = run_receipt_skill(
            content,
            image.content_type or "",
            reader=reader,
        )
        return ReceiptScanResponse.model_validate(result)
    except ReceiptError as exc:
        # Every refused scan, not only the catch-all ones: the named branches
        # are distinguishable on the wire but were just as anonymous in the log.
        _LOGGER.info("receipt scan refused: %s", exc.code)
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
