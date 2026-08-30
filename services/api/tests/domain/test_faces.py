"""What a detector is allowed to publish, decided without a detector present.

Every case here runs on hand-written rectangles. That is deliberate: the
property under test is what the product does with detector output, and a case
that fed a real cascade a real photograph would go red the day OpenCV changes
a default, for a reason that has nothing to do with the rule it was checking.

The live behaviour of the shipped detector is a separate claim and is measured
in `tests/live/test_face_detection_local.py`.
"""

from __future__ import annotations

import pytest

from app.domain.faces import MAX_FACES, FaceError, anonymous_boxes


def test_boxes_are_fractions_of_the_image_not_pixels():
    boxes = anonymous_boxes(
        [{"x": 100, "y": 50, "width": 200, "height": 100}],
        image_width=400,
        image_height=200,
    )

    assert boxes == [
        {"box_key": "face-1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}
    ]


def test_the_key_is_a_position_and_carries_nothing_from_the_pixels():
    """A key derived from the box would be a join key across photographs.

    This is the case that fails if somebody later replaces the ordinal with a
    hash of the coordinates "so the client can cache". The same face, in the
    same place, in two different pictures, must not come back wearing the same
    name -- that is how a set of anonymous rectangles turns into a record of
    who was where.
    """

    first = anonymous_boxes(
        [{"x": 10, "y": 10, "width": 40, "height": 40}],
        image_width=100,
        image_height=100,
    )
    # A different picture, same geometry. Different subject entirely.
    second = anonymous_boxes(
        [{"x": 10, "y": 10, "width": 40, "height": 40}],
        image_width=100,
        image_height=100,
    )

    assert first[0]["box_key"] == second[0]["box_key"] == "face-1"
    # And the key must not be a function of the geometry: move the box, keep
    # the key. If these ever differ, the key has started describing the face.
    moved = anonymous_boxes(
        [{"x": 55, "y": 55, "width": 40, "height": 40}],
        image_width=100,
        image_height=100,
    )
    assert moved[0]["box_key"] == "face-1"


def test_nothing_but_geometry_survives():
    """No confidence, no landmarks, no crop -- four numbers and an index."""

    boxes = anonymous_boxes(
        [{"x": 0, "y": 0, "width": 10, "height": 10, "confidence": 0.97}],
        image_width=100,
        image_height=100,
    )

    assert set(boxes[0]) == {"box_key", "x", "y", "width", "height"}


def test_order_comes_from_the_picture_not_from_the_detector():
    """Two scans of one photo may report the same faces in either order.

    If the ordinal followed input order, "face-2" would name a different person
    between the response a member looked at and the one behind their next tap.
    """

    top_left = {"x": 0, "y": 0, "width": 10, "height": 10}
    top_right = {"x": 80, "y": 0, "width": 10, "height": 10}
    lower = {"x": 40, "y": 50, "width": 10, "height": 10}

    one = anonymous_boxes(
        [lower, top_right, top_left], image_width=100, image_height=100
    )
    two = anonymous_boxes(
        [top_left, lower, top_right], image_width=100, image_height=100
    )

    assert one == two
    # Top-to-bottom, then left-to-right, which is how a person reads the photo.
    assert [(box["x"], box["y"]) for box in one] == [
        (0.0, 0.0),
        (0.8, 0.0),
        (0.4, 0.5),
    ]


def test_a_face_at_the_edge_is_kept_and_clamped():
    """Clamped, not dropped: the person at the end of the table is a person."""

    boxes = anonymous_boxes(
        [{"x": -20, "y": 90, "width": 40, "height": 40}],
        image_width=100,
        image_height=100,
    )

    assert boxes == [
        {"box_key": "face-1", "x": 0.0, "y": 0.9, "width": 0.2, "height": 0.1}
    ]


def test_a_rectangle_entirely_outside_the_picture_is_refused():
    with pytest.raises(FaceError) as excinfo:
        anonymous_boxes(
            [{"x": 500, "y": 500, "width": 40, "height": 40}],
            image_width=100,
            image_height=100,
        )

    assert excinfo.value.code == "FACE_BOX_OUTSIDE_IMAGE"


def test_the_same_face_reported_twice_is_one_box():
    """Otherwise a duplicate-happy detector spends the cap on one person."""

    box = {"x": 10, "y": 10, "width": 20, "height": 20}
    boxes = anonymous_boxes([box, dict(box)], image_width=100, image_height=100)

    assert len(boxes) == 1


def test_too_many_faces_is_refused_rather_than_truncated():
    """Keeping the first N would lock the dropped person out of the feature.

    They would have no box to tap, and nothing in the response would say a box
    had been removed. A refusal the caller can read is the honest failure.
    """

    crowd = [
        {"x": index, "y": index, "width": 5, "height": 5}
        for index in range(MAX_FACES + 1)
    ]

    with pytest.raises(FaceError) as excinfo:
        anonymous_boxes(crowd, image_width=1000, image_height=1000)

    assert excinfo.value.code == "TOO_MANY_FACES"


def test_exactly_the_cap_is_allowed():
    """The control for the case above: the boundary is not off by one."""

    crowd = [
        {"x": index, "y": index, "width": 5, "height": 5} for index in range(MAX_FACES)
    ]

    assert len(anonymous_boxes(crowd, image_width=1000, image_height=1000)) == MAX_FACES


@pytest.mark.parametrize(
    ("box", "code"),
    [
        ({"x": 0, "y": 0, "width": 0, "height": 10}, "FACE_BOX_DEGENERATE"),
        ({"x": 0, "y": 0, "width": 10, "height": -5}, "FACE_BOX_DEGENERATE"),
        ({"x": 0, "y": 0, "width": 10}, "FACE_BOX_MALFORMED"),
        ({"x": None, "y": 0, "width": 10, "height": 10}, "FACE_BOX_MALFORMED"),
    ],
)
def test_a_detector_contradicting_itself_is_refused(box, code):
    with pytest.raises(FaceError) as excinfo:
        anonymous_boxes([box], image_width=100, image_height=100)

    assert excinfo.value.code == code


def test_an_image_with_no_size_cannot_be_a_denominator():
    with pytest.raises(FaceError) as excinfo:
        anonymous_boxes([], image_width=0, image_height=100)

    assert excinfo.value.code == "IMAGE_DIMENSIONS_INVALID"


def test_a_photo_with_nobody_in_it_is_an_empty_list_not_an_error():
    assert anonymous_boxes([], image_width=100, image_height=100) == []
