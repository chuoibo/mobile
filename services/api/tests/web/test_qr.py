"""QR image generation, and the preview server a human reviews the page with."""

from __future__ import annotations

import base64
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.payments.vietqr import build_payload  # noqa: E402
from app.web.qr import QRError, payload_to_png_data_uri  # noqa: E402


def payload(amount=82000):
    return build_payload(bank_bin="970407", account_number="19036812345678",
                         amount_vnd=amount, note="Lau T7")


class Rendering(unittest.TestCase):
    def test_produces_a_png_data_uri(self):
        uri = payload_to_png_data_uri(payload())
        self.assertTrue(uri.startswith("data:image/png;base64,"))
        raw = base64.b64decode(uri.split(",", 1)[1])
        self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")

    def test_is_deterministic(self):
        self.assertEqual(payload_to_png_data_uri(payload()), payload_to_png_data_uri(payload()))

    def test_a_different_amount_gives_a_different_code(self):
        """Rendering a valid PNG is not the same as rendering the right code.

        A banking app that cannot read the code gives no error; it just fails.
        So the image has to actually track the payload.
        """
        self.assertNotEqual(payload_to_png_data_uri(payload(82000)),
                            payload_to_png_data_uri(payload(82001)))

    def test_empty_payload_is_refused(self):
        for bad in ("", "   "):
            with self.subTest(bad=bad):
                with self.assertRaises(QRError) as caught:
                    payload_to_png_data_uri(bad)
                self.assertEqual(caught.exception.code, "EMPTY_PAYLOAD")

    def test_stays_small_enough_for_a_mobile_connection(self):
        self.assertLess(len(payload_to_png_data_uri(payload())), 60_000)


class PreviewServer(unittest.TestCase):
    def test_every_declared_state_renders(self):
        """The preview is how a human reviews this page, so a broken state is
        a broken review, not just a broken demo."""
        from app.web.preview import STATES, render
        for state in STATES:
            with self.subTest(state=state):
                html = render(state)
                self.assertIn(b"<!doctype html>", html.lower())
                self.assertNotIn("—".encode(), html)

    def test_inactive_states_show_no_account_number(self):
        from app.web.preview import render
        for state in ("expired", "revoked"):
            with self.subTest(state=state):
                self.assertNotIn(b"19036812345678", render(state))

    def test_active_states_carry_a_qr_image(self):
        from app.web.preview import render
        self.assertIn(b"data:image/png", render("one"))


if __name__ == "__main__":
    unittest.main()
