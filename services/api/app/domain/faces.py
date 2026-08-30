"""Turn raw detector output into anonymous rectangles, and nothing else.

F22 without identity. A detector hands back pixel rectangles; this module
decides what of that is allowed to leave the process. The answer is: four
numbers per face and an ordinal, and the ordinal is deliberately worthless.

Why an ordinal and not a hash of the coordinates
------------------------------------------------
A key derived from the box itself is stable: the same face in the same photo
produces the same key on every call, and a face photographed twice in the same
spot produces it twice. That is a join key. Two responses carrying it can be
lined up, and lining up "who appeared in which photo" is identity built out of
parts none of which is called identity. ADR-0011 says a cross-photo face join
must be a thing that cannot be *written*, not a thing that is forbidden by
comment, so the key here is a position in one sorted list and means nothing
outside the single response it came in.

That also fixes the ordering requirement. Detector output order is an artefact
of the scan; two calls on the same bytes may return the same rectangles in a
different order, and then "face-2" would name different people between two
taps of the same button. Sorting top-to-bottom, then left-to-right, makes the
ordinal a function of the picture rather than of the library's internals.

What is deliberately absent
---------------------------
No confidence score. A confidence is a knob, and the first thing a knob like
that gets used for is "only show boxes above 0.9", which is a quality filter on
faces -- one step from ranking them. No landmarks, no embeddings, no crops, no
descriptor of any kind. Four numbers and an index.

Coordinates are fractions of the image, not pixels. The client draws on a
scaled copy, so pixels would make every caller redo this division, and a caller
that redoes it against the *rendered* size rather than the stored size draws
the box over the wrong person.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

__all__ = [
    "MAX_FACES",
    "FaceError",
    "anonymous_boxes",
]

# A bill photograph of a table has faces in the low tens. Past this the
# detector is reporting texture, not people, and the honest answer is to say
# so: silently keeping the first 24 would drop somebody's box, and a person
# whose box is missing cannot tap "this is me" -- they are locked out of the
# feature by a truncation nobody told them about.
MAX_FACES = 24


class FaceError(Exception):
    """One stable refusal code for a detection that cannot be published."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def anonymous_boxes(
    boxes: Iterable[Mapping[str, int]],
    *,
    image_width: int,
    image_height: int,
) -> list[dict]:
    """Normalize, clamp, de-duplicate and order detector rectangles.

    `boxes` are pixel rectangles from whatever detector ran. The image size
    must come from the same decode that produced them: a size read from a
    database row can disagree with the bytes actually scanned, and then every
    fraction here is computed against the wrong denominator and every box is
    drawn slightly off the person it belongs to.
    """

    if image_width <= 0 or image_height <= 0:
        raise FaceError("IMAGE_DIMENSIONS_INVALID")

    clamped: list[tuple[int, int, int, int]] = []
    for box in boxes:
        try:
            x = int(box["x"])
            y = int(box["y"])
            width = int(box["width"])
            height = int(box["height"])
        except (KeyError, TypeError, ValueError):
            raise FaceError("FACE_BOX_MALFORMED") from None

        if width <= 0 or height <= 0:
            raise FaceError("FACE_BOX_DEGENERATE")

        # Clamp rather than reject: a face at the edge of the frame is a real
        # face that the detector legitimately reports as running past the
        # border. Clamping keeps it; rejecting would drop the person sitting
        # at the end of the table.
        left = max(0, min(x, image_width))
        top = max(0, min(y, image_height))
        right = max(0, min(x + width, image_width))
        bottom = max(0, min(y + height, image_height))

        # Nothing survived the clamp, so the rectangle was entirely outside the
        # picture. That is a detector fault rather than an edge case, and a
        # zero-area box would render as an invisible tap target.
        if right <= left or bottom <= top:
            raise FaceError("FACE_BOX_OUTSIDE_IMAGE")

        clamped.append((left, top, right - left, bottom - top))

    # De-duplicate before the cap, so a detector that reports the same face
    # twice cannot spend the budget meant for real ones. Sorted on the tuple:
    # top-to-bottom, then left-to-right, then by size, which is a total order
    # over the values themselves and therefore independent of input order.
    ordered = sorted(
        {(top, left, width, height) for left, top, width, height in clamped}
    )

    if len(ordered) > MAX_FACES:
        raise FaceError("TOO_MANY_FACES")

    return [
        {
            # Position in this list, and nothing else. Not stable across
            # requests on purpose -- see the module docstring.
            "box_key": f"face-{index}",
            "x": left / image_width,
            "y": top / image_height,
            "width": width / image_width,
            "height": height / image_height,
        }
        for index, (top, left, width, height) in enumerate(ordered, start=1)
    ]
