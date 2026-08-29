"""The second half of the `image_url` gate, checked on its own.

The schema refuses anything that is not `/contexts/{uuid}/photos/{uuid}`, and
the service then compares the context in that path against the context being
written. Those are two layers, and this file pins the lower one down by
itself.

Why it deserves its own file: a mutation run that loosened the schema pattern
turned this helper into a `ValueError` -- a 500, from a request body. The
helper had quietly inherited the schema's promise that it would only ever see
a well formed path. A 500 is a worse answer than a 422 (it pages somebody, it
reads as a server bug, and it is the shape an attacker probes for), so the
helper now refuses malformed input on its own rather than trusting the layer
above it to have run.
"""

from __future__ import annotations

import unittest
import uuid

from app.api.service import ApiProblem, _require_photo_url_context

MALFORMED = (
    "",
    "/",
    "/contexts",
    "/contexts/not-a-uuid/photos/also-not",
    "/contexts//photos/",
    "https://tracker.example/pixel.png",
    "javascript:alert(1)",
    "/contexts/../../etc/passwd",
)


class PhotoUrlContextGuardTests(unittest.TestCase):
    def test_a_matching_context_is_allowed_through(self):
        context_id = uuid.uuid4()
        url = f"/contexts/{context_id}/photos/{uuid.uuid4()}"

        self.assertIsNone(_require_photo_url_context(context_id, url))

    def test_no_image_url_is_not_this_guards_business(self):
        """A text message carries no image. That is not a refusal."""

        self.assertIsNone(_require_photo_url_context(uuid.uuid4(), None))

    def test_another_groups_context_is_refused(self):
        url = f"/contexts/{uuid.uuid4()}/photos/{uuid.uuid4()}"

        with self.assertRaises(ApiProblem) as caught:
            _require_photo_url_context(uuid.uuid4(), url)

        self.assertEqual(caught.exception.status_code, 422)

    def test_malformed_input_is_a_422_and_never_an_unhandled_crash(self):
        """The layer above normally catches these. `normally` is not a gate."""

        for url in MALFORMED:
            with self.subTest(url=url):
                with self.assertRaises(ApiProblem) as caught:
                    _require_photo_url_context(uuid.uuid4(), url)

                self.assertEqual(caught.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
