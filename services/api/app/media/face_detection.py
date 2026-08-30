"""Find rectangles that look like faces, in this process, on this machine.

AGENTS.md line 64 forbids sending participant data out of the product, and a
group photograph is the densest participant data the product holds. So there is
no vendor call here and no place to configure one: the model is a file that
ships inside the `opencv-python-headless` wheel, loaded into this process, and
the bytes never leave it.

The seam
--------
`FaceDetector` exists so tests can install a fixed answer and assert on the
route without depending on what a real detector thinks of a JPEG. It is
resolved by `app/api/deps.py` on the server side only. There is deliberately no
request field, header or query parameter that selects a detector: a seam the
caller can reach is not a test seam, it is an endpoint that runs code of the
caller's choosing over another group's photographs.

Why Haar and not something better
---------------------------------
Because "better" here means a learned embedding model, and an embedding is the
one output F22 must not produce. A cascade emits rectangles and has nothing
else to emit -- the property is enforced by the model's shape rather than by
our restraint in reading it. It is also small, CPU-only and deterministic, so
two calls on the same bytes give the same rectangles and the ordinals in
`app/domain/faces.py` stay meaningful.

It misses profiles and hard-lit faces. That is a real limitation and it is
survivable here precisely because nothing downstream is automatic: a missed
face costs one person one tap on a list instead of one tap on a photo.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

__all__ = [
    "Detection",
    "FaceDetector",
    "FaceDetectorUnavailable",
    "HaarFaceDetector",
    "PixelBox",
]


@dataclass(frozen=True, slots=True)
class PixelBox:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class Detection:
    """Rectangles plus the size they were measured against.

    One object rather than two returns, because the size is only useful as the
    denominator for these boxes. Handing the caller the boxes and letting them
    find a size elsewhere is how a box gets normalized against the stored
    dimensions of a differently-oriented copy and lands on the wrong person.
    """

    boxes: tuple[PixelBox, ...]
    image_width: int
    image_height: int


class FaceDetector(Protocol):
    def detect(self, image: bytes) -> Detection: ...


class FaceDetectorUnavailable(Exception):
    """The local model could not be loaded. Not a fault of the image."""


@lru_cache(maxsize=1)
def _cascade():
    """Load the classifier once per process.

    Imported inside the function, not at module scope. `app.api.main` imports
    the route module at startup, and a missing wheel at import time is an API
    that will not boot at all -- the failure mode that killed the demo box on
    2026-08-30. Deferred, the same missing wheel is one route answering 503
    while every other route serves.
    """

    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - exercised by the 503 path
        raise FaceDetectorUnavailable("opencv is not installed") from exc

    path = f"{cv2.data.haarcascades}haarcascade_frontalface_default.xml"
    classifier = cv2.CascadeClassifier(path)
    # `CascadeClassifier` reports a missing or unreadable file by constructing
    # an object that silently matches nothing, so this check is the difference
    # between "no faces in this photo" and "the model never loaded".
    if classifier.empty():
        raise FaceDetectorUnavailable(f"cascade did not load from {path}")
    return classifier


class HaarFaceDetector:
    """The detector the app ships with. CPU-only, in-process, no network."""

    def detect(self, image: bytes) -> Detection:
        try:
            import cv2
            import numpy
        except ImportError as exc:  # pragma: no cover - exercised by the 503 path
            raise FaceDetectorUnavailable("opencv is not installed") from exc

        from PIL import Image, ImageOps

        classifier = _cascade()

        with Image.open(io.BytesIO(image)) as source:
            # Same transpose the upload sanitiser applies, so the coordinates
            # returned here describe the picture as a person sees it rather
            # than as the phone stored it. Without it a portrait photo gets
            # boxes rotated ninety degrees away from the faces.
            upright = ImageOps.exif_transpose(source)
            grey = upright.convert("L")
            width, height = grey.size
            pixels = numpy.asarray(grey)

        found = classifier.detectMultiScale(
            pixels,
            scaleFactor=1.1,
            minNeighbors=5,
            # A face smaller than this on a table photo is either far behind
            # the group or is not a face. Anchored to the image so it means the
            # same thing on a phone photo and on a downscaled copy.
            minSize=(max(24, width // 40), max(24, height // 40)),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )

        return Detection(
            boxes=tuple(
                PixelBox(x=int(x), y=int(y), width=int(w), height=int(h))
                for x, y, w, h in found
            ),
            image_width=width,
            image_height=height,
        )
