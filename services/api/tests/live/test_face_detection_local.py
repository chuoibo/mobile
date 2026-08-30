"""The live tier for F22: the REAL cascade, on real pictures of real faces.

Every other F22 test injects a stub detector, so none of them can answer the
question the feature is judged on: handed an actual photograph, does the
shipped model find the people in it? A stub proves the door, the ordering and
the privacy rules. It cannot prove the product does anything at all.

Skipped by default, and a skip here is not a green -- it is this claim going
unmade. Run it with::

    cd services/api && MOBILE_REQUIRE_FACE_TESTS=1 python -m pytest \\
        tests/live/test_face_detection_local.py -q

Why the corpus lives outside the repository
-------------------------------------------
Committing photographs of people is forbidden outright, and the repo guard
fails closed on new binaries besides. So this reads the product mockups under
`product/`, which are the only images on this machine that contain faces and
are not pictures of anybody real. That makes the corpus small and its absence
ordinary -- hence the skip rather than a failure, unless the environment
variable says the run was meant to measure this.

What this does NOT prove
------------------------
A detection rate. Four images is not a distribution, and a green run means
"found faces in these", never "finds faces". Nor does it prove the boxes land
on the right people: nothing here checks placement beyond the frame. What it
does prove is that the model loads, runs in-process, and returns more than zero
-- which is precisely what a stubbed suite cannot distinguish from a detector
that was never installed.
"""

from __future__ import annotations

import os
import pathlib

import pytest

from app.domain.faces import anonymous_boxes
from app.media.face_detection import FaceDetectorUnavailable, HaarFaceDetector

REQUIRE_ENV = "MOBILE_REQUIRE_FACE_TESTS"
CORPUS = pathlib.Path("/home/lakiet/mobile/product")
# Measured on 2026-08-30 with opencv 4.13.0: these four each yield at least one
# detection. Recorded as a floor, not as an expected count -- a cascade is
# allowed to find more faces after a library bump, and pinning the exact number
# would make this file red for an improvement.
WITH_FACES = (
    "mockup.png",
    "features/05-ky-niem-cua-nhom.png",
    "features/03-nhom-chat-va-ai-len-ke-hoach.png",
    "features/06-ho-so-va-hanh-trinh.png",
)


def _images() -> list[pathlib.Path]:
    return [CORPUS / name for name in WITH_FACES if (CORPUS / name).is_file()]


pytestmark = pytest.mark.skipif(
    not _images() and os.environ.get(REQUIRE_ENV) != "1",
    reason=(
        f"no face corpus at {CORPUS}; set {REQUIRE_ENV}=1 to make its absence "
        "a failure rather than a skip"
    ),
)


@pytest.fixture(scope="module")
def detector() -> HaarFaceDetector:
    return HaarFaceDetector()


def test_the_corpus_is_present_when_this_run_was_meant_to_measure_it():
    """Guards the skip above from swallowing the whole file silently.

    Without this, deleting the corpus turns a measurement into a pass.
    """

    if os.environ.get(REQUIRE_ENV) == "1":
        missing = [name for name in WITH_FACES if not (CORPUS / name).is_file()]
        assert not missing, f"{REQUIRE_ENV}=1 but these are missing: {missing}"


def test_the_model_loads_in_this_process(detector):
    """The distinction a stub erases: installed versus merely imported.

    `CascadeClassifier` answers a missing file by constructing an object that
    matches nothing, so "zero faces" and "no model" look identical from the
    outside. This is the case that tells them apart.
    """

    try:
        detection = detector.detect(
            (_images() or [CORPUS / WITH_FACES[0]])[0].read_bytes()
        )
    except FaceDetectorUnavailable as exc:
        pytest.fail(f"the shipped detector could not load: {exc}")

    assert detection.image_width > 0
    assert detection.image_height > 0


@pytest.mark.parametrize("name", WITH_FACES)
def test_the_shipped_cascade_finds_at_least_one_face(detector, name):
    path = CORPUS / name
    if not path.is_file():
        pytest.skip(f"{path} is not on this machine")

    detection = detector.detect(path.read_bytes())

    assert len(detection.boxes) >= 1, f"no faces found in {name}"


@pytest.mark.parametrize("name", WITH_FACES)
def test_real_output_survives_the_publishing_rules(detector, name):
    """The domain rules meet real detector output, not hand-written rectangles.

    `tests/domain/test_faces.py` feeds `anonymous_boxes` numbers a human chose.
    That cannot catch a real cascade emitting something the rules refuse -- a
    box running past the frame edge, say -- which would surface in production
    as a 502 on an ordinary photograph.
    """

    path = CORPUS / name
    if not path.is_file():
        pytest.skip(f"{path} is not on this machine")

    detection = detector.detect(path.read_bytes())
    boxes = anonymous_boxes(
        [
            {"x": box.x, "y": box.y, "width": box.width, "height": box.height}
            for box in detection.boxes
        ],
        image_width=detection.image_width,
        image_height=detection.image_height,
    )

    assert len(boxes) >= 1
    for box in boxes:
        assert 0.0 <= box["x"] <= 1.0
        assert 0.0 <= box["y"] <= 1.0
        assert 0.0 < box["width"] <= 1.0
        assert box["x"] + box["width"] <= 1.0 + 1e-9
        assert box["y"] + box["height"] <= 1.0 + 1e-9
        assert set(box) == {"box_key", "x", "y", "width", "height"}


def test_the_same_bytes_twice_give_the_same_boxes(detector):
    """Determinism is what makes the ordinal mean anything between two taps.

    If the cascade returned different rectangles on a second run, "face-2"
    would name a different person between the response somebody looked at and
    the one behind their next request.
    """

    images = _images()
    if not images:
        pytest.skip(f"no corpus at {CORPUS}")

    raw = images[0].read_bytes()
    first = detector.detect(raw)
    second = detector.detect(raw)

    assert first.boxes == second.boxes
