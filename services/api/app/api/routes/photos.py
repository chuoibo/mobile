"""Private endpoints for sanitized group photos and personal avatars."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from app.api.deps import Actor, get_actor, get_photo_storage, get_repository
from app.api.repository import ApiRepository
from app.api.schemas import ErrorResponse, UploadedImageResponse
from app.api.service import ApiService
from app.media.images import MAX_UPLOAD_BYTES
from app.media.storage import PhotoStorage

router = APIRouter(tags=["photos"])
ERRORS = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    415: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}

_UPLOAD_CHUNK_BYTES = 1024 * 1024
_PRIVATE_CACHE_HEADERS = {"Cache-Control": "private, max-age=300"}


async def _read_upload(file: UploadFile) -> bytes:
    """Retain only enough bytes for the sanitizer to prove an oversize body."""

    content = bytearray()
    while len(content) <= MAX_UPLOAD_BYTES:
        remaining = MAX_UPLOAD_BYTES + 1 - len(content)
        chunk = await file.read(min(_UPLOAD_CHUNK_BYTES, remaining))
        if not chunk:
            break
        content.extend(chunk)
    return bytes(content)


@router.post(
    "/contexts/{context_id}/photos",
    response_model=UploadedImageResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
async def upload_context_photo(
    context_id: UUID,
    file: Annotated[UploadFile, File()],
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    photo_storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> UploadedImageResponse:
    raw = await _read_upload(file)
    return ApiService(repository, photo_storage=photo_storage).upload_context_photo(
        context_id, raw, actor
    )


@router.get(
    "/contexts/{context_id}/photos/{photo_id}",
    responses=ERRORS,
)
def read_context_photo(
    context_id: UUID,
    photo_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    photo_storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> Response:
    content, content_type = ApiService(
        repository, photo_storage=photo_storage
    ).read_context_photo(context_id, photo_id, actor)
    return Response(
        content=content,
        media_type=content_type,
        headers=_PRIVATE_CACHE_HEADERS,
    )


@router.post(
    "/people/{person_id}/avatar",
    response_model=UploadedImageResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
async def set_person_avatar(
    person_id: UUID,
    file: Annotated[UploadFile, File()],
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    photo_storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> UploadedImageResponse:
    raw = await _read_upload(file)
    return ApiService(repository, photo_storage=photo_storage).set_person_avatar(
        person_id, raw, actor
    )


@router.get(
    "/people/{person_id}/avatar",
    responses=ERRORS,
)
def read_person_avatar(
    person_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    photo_storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> Response:
    content, content_type = ApiService(
        repository, photo_storage=photo_storage
    ).read_person_avatar(person_id, actor)
    return Response(
        content=content,
        media_type=content_type,
        headers=_PRIVATE_CACHE_HEADERS,
    )
