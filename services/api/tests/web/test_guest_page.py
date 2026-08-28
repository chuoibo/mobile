"""The guest page: what it may show, and what it must never show.

This is the one surface a stranger reaches without installing anything, so it
is also the easiest place to leak a group's finances by accident.
"""

from __future__ import annotations

import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from jinja2 import Environment, FileSystemLoader  # noqa: E402

from app.api.limits import OBJECTION_LIMIT, REPORT_LIMIT
from app.web.guest_view import (  # noqa: E402
    ALLOWED_BLOCK,
    ALLOWED_TOP_LEVEL,
    NEUTRAL_PREVIEW,
    GuestViewError,
    build_guest_view,
    format_vnd,
)

WEB = pathlib.Path(__file__).resolve().parents[2] / "app/web"


def envelope(*, obligation_overrides=None, **overrides):
    """`obligation_overrides` sets fields on the single obligation.

    The objection budget moved onto each obligation: a link can carry debts to
    two different people, and three objections about one of them must not use
    up the right to say anything about the other.
    """
    data = {
        "recorded_by_display_name": "Nam",
        "claimed_person_display_name": "Hà",
        "link_state": "active",
        "obligations": [{
            "obligation_id": "o1",
            "occasion_label": "bữa lẩu tối thứ bảy",
            "amount_vnd": 82000,
            "recipient_display_name": "Nam",
            "bank_name": "Techcombank",
            "bank_bin": "970407",
            # repo-guard: allow=long-number reason=synthetic-test-fixture-never-real-participant-data
            "account_number": "19036812345678",
            "account_holder_name": "NGUYEN VAN NAM",
            "transfer_note": "Bua lau",
            "qr_payload": "00020101",
            "objections_used": 0,
            "objections_allowed": OBJECTION_LIMIT,
            **(obligation_overrides or {}),
        }],
        "reports_used": 0,
        "reports_allowed": REPORT_LIMIT,
        "objections_used": 0,
        "objections_allowed": OBJECTION_LIMIT,
    }
    data.update(overrides)
    return data


def render(view, token="tok"):
    env = Environment(loader=FileSystemLoader(str(WEB / "templates")), autoescape=True)
    return env.get_template("guest.html").render(view=view, preview=NEUTRAL_PREVIEW, token=token)


class Formatting(unittest.TestCase):
    def test_vietnamese_thousands_grouping(self):
        self.assertEqual(format_vnd(82000), "82.000")
        self.assertEqual(format_vnd(1250000), "1.250.000")
        self.assertEqual(format_vnd(0), "0")

    def test_rejects_non_integer_money(self):
        for bad in (1.5, True, "82000"):
            with self.subTest(bad=bad):
                with self.assertRaises(GuestViewError):
                    format_vnd(bad)


class LeakGuard(unittest.TestCase):
    def test_group_data_in_the_input_is_an_error_not_a_silent_drop(self):
        """Upstream handing us a group balance is a bug in the caller. Dropping
        it quietly would let the same bug reach a surface that does render it."""
        for field in ("group_balance", "group_history", "other_allocations",
                      "invocation_thread", "original_bill_url", "member_list"):
            with self.subTest(field=field):
                with self.assertRaises(GuestViewError) as caught:
                    build_guest_view(envelope(**{field: "anything"}))
                self.assertEqual(caught.exception.code, "FORBIDDEN_FIELD_IN_INPUT")

    def test_view_model_is_a_closed_whitelist(self):
        view = build_guest_view(envelope())
        self.assertLessEqual(set(view), ALLOWED_TOP_LEVEL)
        for block in view["blocks"]:
            self.assertLessEqual(set(block), ALLOWED_BLOCK)

    def test_rendered_page_says_it_shows_only_your_share(self):
        html = render(build_guest_view(envelope()))
        self.assertIn("Chỉ hiển thị phần của bạn", html)


class LinkLifecycle(unittest.TestCase):
    def test_an_inactive_link_stops_showing_account_numbers(self):
        for state in ("revoked", "expired", "rotated"):
            with self.subTest(state=state):
                view = build_guest_view(envelope(link_state=state))
                html = render(view)
                self.assertEqual(view["blocks"], [])
                # repo-guard: allow=long-number reason=synthetic-test-fixture-never-real-participant-data
                self.assertNotIn("19036812345678", html)
                self.assertFalse(view["can_report_payment"])

    def test_an_expired_link_does_not_make_the_obligation_disappear(self):
        """Spec section 8.2 is explicit about this."""
        html = render(build_guest_view(envelope(link_state="expired")))
        self.assertIn("vẫn còn", html)

    def test_unknown_state_is_refused(self):
        with self.assertRaises(GuestViewError) as caught:
            build_guest_view(envelope(link_state="probably_fine"))
        self.assertEqual(caught.exception.code, "UNKNOWN_LINK_STATE")


class RateLimits(unittest.TestCase):
    def test_report_and_objection_budgets_run_out(self):
        """Section 8.6 caps both so a leaked link cannot spam the recipient."""
        view = build_guest_view(
            envelope(
                reports_used=3,
                reports_allowed=3,
                obligation_overrides={"objections_used": 2, "objections_allowed": 2},
            )
        )
        self.assertFalse(view["can_report_payment"])
        # Top level is "is there anything left to object to anywhere", derived
        # from the blocks rather than counted separately.
        self.assertFalse(view["can_object"])
        self.assertFalse(view["blocks"][0]["can_object"])
        html = render(view)
        self.assertNotIn("Tôi đã chuyển", html)
        self.assertIn("Nhắn trực tiếp", html)


class WordingNeverAssumesIdentity(unittest.TestCase):
    """Section 8.6: the page must not assume the opener is the named person."""

    def setUp(self):
        self.html = render(build_guest_view(envelope()))

    def test_the_claim_is_attributed_to_whoever_recorded_it(self):
        self.assertIn("Nam", self.html)
        self.assertIn("đã ghi", self.html)

    def test_all_three_outcomes_are_offered(self):
        self.assertIn("Đúng, xem cách chuyển", self.html)
        self.assertIn("Số tiền không đúng", self.html)
        self.assertIn("Tôi không phải Hà", self.html)

    def test_self_report_wording_does_not_imply_the_debt_is_closed(self):
        self.assertIn("Khoản chỉ đóng khi họ xác nhận", self.html)

    def test_receiver_confirmation_is_attributed_to_a_person(self):
        confirmed = envelope()
        confirmed["obligations"][0]["receiver_confirmed"] = True
        html = render(build_guest_view(confirmed))
        self.assertIn("đã xác nhận nhận được", html)


class PreviewMetadata(unittest.TestCase):
    def test_preview_carries_no_name_and_no_amount(self):
        """Whoever sees the link card in a group chat is not necessarily the
        intended reader (section 8.6)."""
        blob = NEUTRAL_PREVIEW["title"] + NEUTRAL_PREVIEW["description"]
        self.assertNotIn("Hà", blob)
        self.assertNotIn("Nam", blob)
        self.assertFalse(re.search(r"\d", blob))

    def test_page_is_not_indexable(self):
        html = render(build_guest_view(envelope()))
        self.assertIn("noindex", html)


class DesignDiscipline(unittest.TestCase):
    def setUp(self):
        self.css = (WEB / "static/guest.css").read_text(encoding="utf-8")
        self.html = render(build_guest_view(envelope()))

    def test_no_em_dash_anywhere(self):
        for name, text in (("html", self.html), ("css", self.css)):
            with self.subTest(name):
                self.assertNotIn("—", text)
                self.assertNotIn("–", text)

    def test_dark_mode_is_defined(self):
        self.assertIn("prefers-color-scheme: dark", self.css)

    def test_reduced_motion_is_honoured(self):
        self.assertIn("prefers-reduced-motion: reduce", self.css)

    def test_uses_dvh_not_vh(self):
        """100vh jumps when the iOS Safari address bar moves."""
        self.assertIn("100dvh", self.css)
        self.assertNotIn("100vh", self.css)

    def test_shape_lock_holds(self):
        """Two documented radius steps, no stray hard-coded third."""
        strays = re.findall(r"border-radius:\s*(\d+)px", self.css)
        self.assertEqual(strays, [], f"hard-coded radii: {strays}")

    def test_focus_is_visible(self):
        self.assertIn("focus-visible", self.css)

    def test_no_js_guest_can_still_reach_the_account_number(self):
        """The claim this file used to make was false.

        An earlier version shipped `hidden` straight on the transfer panel, so
        a guest with scripting disabled could not reach the account number at
        all -- while three commit messages and a PR description said the
        opposite. Codex caught it in review.

        Collapsing now happens in CSS gated on a .js class, so scripting off
        means the panel stays open.
        """
        markup = (WEB / "templates/guest.html").read_text(encoding="utf-8")
        panel = re.search(r"<div class=\"transfer\"[^>]*>", markup)
        self.assertIsNotNone(panel)
        self.assertNotIn("hidden", panel.group(0), "no-JS guests cannot pay")

        self.assertIn(".js .transfer { display: none; }", self.css)
        js = (WEB / "static/guest.js").read_text(encoding="utf-8")
        self.assertNotIn("panel.hidden = true", js, "hiding must not live in script")

    def test_the_rendered_account_number_is_present_without_running_script(self):
        """Server-rendered, so it is in the HTML the browser receives."""
        # repo-guard: allow=long-number reason=synthetic-test-fixture-never-real-participant-data
        self.assertIn("19036812345678", self.html)


if __name__ == "__main__":
    unittest.main()


class StandingIsVisibleWithoutPressingAnything(unittest.TestCase):
    """Where a person stands, on the face they land on.

    This state used to live inside the transfer panel, which only opens when
    the "Đúng, xem cách chuyển" button is pressed. So somebody who transferred
    yesterday reopened their link and saw the untouched first screen: same
    amount, same "Đúng, xem cách chuyển", no sign they had already reported
    anything. The obvious thing to do from that screen is pay again.

    Splitting the page at the reveal is what makes these tests worth having:
    asserting the words are *somewhere in the HTML* would pass in the broken
    version too, because they were there all along -- just behind a button.
    """

    def first_face(self, state: str) -> str:
        """The part of the page shown before anything is pressed."""
        from app.web.preview import render

        html = render(state).decode()
        # The transfer panel is everything from `data-transfer` onward. What
        # comes before it is what a person actually sees on arrival.
        head, _, _ = html.partition("data-transfer")
        # Collapsed, because a sentence in the template wraps across lines and
        # a reader does not see the break. Without this the tests would fail
        # when somebody rewraps a paragraph, which is not a thing to fail on.
        return " ".join(head.split())

    def test_someone_who_reported_is_told_so_before_pressing_anything(self):
        face = self.first_face("reported")
        self.assertIn("đã báo là đã chuyển", face)
        self.assertIn("không cần chuyển lại", face)

    def test_someone_whose_money_arrived_is_told_so_before_pressing_anything(self):
        face = self.first_face("confirmed")
        self.assertIn("đã xác nhận nhận được", face)
        self.assertIn("không cần làm gì thêm", face)

    def test_a_fresh_link_makes_no_claim_about_having_paid(self):
        # The other direction, and the one a careless fix breaks: somebody who
        # has done nothing must not be told they have.
        face = self.first_face("one")
        self.assertNotIn("đã báo là đã chuyển", face)
        self.assertNotIn("đã xác nhận nhận được", face)

    def test_the_button_stops_instructing_people_who_already_did_it(self):
        for state in ("reported", "confirmed"):
            with self.subTest(state=state):
                self.assertIn("Xem lại cách chuyển", self.first_face(state))
        self.assertIn("Đúng, xem cách chuyển", self.first_face("one"))

    def test_nothing_shouts_once_the_money_is_confirmed(self):
        # A finished task should not leave the loudest control on the page
        # pointing at itself.
        self.assertNotIn("btn--primary", self.first_face("confirmed"))
        self.assertIn("btn--primary", self.first_face("one"))

    def test_objecting_stays_possible_after_the_money_arrived(self):
        # Disagreeing about an amount is independent of whether it was paid,
        # so confirmation must not quietly remove the way to say so.
        face = self.first_face("confirmed")
        self.assertIn("Số tiền không đúng", face)
