from __future__ import annotations  # <-- the load-bearing line

from fastapi import APIRouter, status
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    detail: str


ERRORS = {c: {"model": ErrorResponse} for c in (403, 404, 409, 422)}
router = APIRouter()


@router.delete("/x", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
def f() -> None: ...


print("imported fine")
