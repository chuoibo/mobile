"""Anonymous face rectangles on a group photo. No identity, nothing stored."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.deps import (
    Actor,
    get_actor,
    get_face_detector,
    get_photo_storage,
    get_repository,
)
from app.api.repository import ApiRepository
from app.api.schemas import ErrorResponse, FaceBoxesResponse
from app.api.search_rate_limit import FixedWindowLimiter
from app.api.service import ApiService
from app.media.face_detection import FaceDetector
from app.media.storage import PhotoStorage

router = APIRouter(tags=["faces"])


def get_face_detection_limiter(request: Request) -> FixedWindowLimiter:
    """Resolve the one window `create_app` built for this route.

    Read off the application, never constructed here. A limiter built per
    request counts to one and forgets, which is a limiter-shaped object that
    limits nothing -- the shape every sibling route file warns about.
    """

    return request.app.state.face_detection_limiter


# POST rather than GET, on a route that reads and stores nothing.
#
# The usual argument for GET -- it has no side effects -- is exactly what makes
# it wrong here. A GET invites a client to poll it, a browser or proxy to
# repeat it, and a screen that remounts to issue it again, and each of those
# runs a multi-megapixel cascade on this box's CPU. F32 shipped as a GET for
# that reason and had to have a window retrofitted. The cost here is CPU rather
# than paid quota, but the failure is worse: the thread this holds is one the
# money routes need.
@router.post(
    "/contexts/{context_id}/photos/{photo_id}/face-boxes",
    response_model=FaceBoxesResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def detect_faces(
    context_id: UUID,
    photo_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    photo_storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    detector: Annotated[FaceDetector, Depends(get_face_detector)],
    limiter: Annotated[FixedWindowLimiter, Depends(get_face_detection_limiter)],
) -> FaceBoxesResponse:
    """Find faces in one group photo the caller is already allowed to see.

    There is no request body at all, so there is no field through which a
    caller could name a person, supply a candidate list, or select a detector.
    The only inputs are two path ids and the actor header.
    """

    # Before the photo is read off disk and before the cascade runs, because a
    # 429 raised afterwards has already spent the CPU it was refusing.
    limiter.check(actor.id)
    return ApiService(
        repository, photo_storage=photo_storage
    ).detect_faces_in_context_photo(context_id, photo_id, actor, detector)
