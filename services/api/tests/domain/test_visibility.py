"""Visibility matrix and the anti-laundering rule, spec section 10."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.domain.visibility import (  # noqa: E402
    DEFAULT_VISIBILITY,
    LEVELS,
    SETTLEMENT_VIEW_FIELDS,
    VisibilityError,
    can_view_history,
    check_no_context_laundering,
    declassify,
    permitted_output_visibility,
    settlement_view,
)


class Ceiling(unittest.TestCase):
    def test_output_is_capped_by_the_narrowest_input(self):
        self.assertEqual(
            permitted_output_visibility(["private_to_invoker", "group_visible"]),
            "private_to_invoker",
        )

    def test_widening_beyond_the_ceiling_is_refused(self):
        with self.assertRaises(VisibilityError) as caught:
            check_no_context_laundering("output_summary", "group_visible", ["private_to_invoker"])
        self.assertEqual(caught.exception.code, "CONTEXT_LAUNDERING")

    def test_redaction_alone_is_not_enough(self):
        """Redacting without consent takes a decision that belongs to the owner."""
        with self.assertRaises(VisibilityError):
            check_no_context_laundering(
                "output_summary", "group_visible", ["private_to_invoker"], redacted=True
            )

    def test_consent_alone_is_not_enough(self):
        """Consent without redaction just moves the sensitive bytes wider."""
        with self.assertRaises(VisibilityError):
            check_no_context_laundering(
                "output_summary", "group_visible", ["private_to_invoker"], owner_consented=True
            )

    def test_redaction_plus_consent_opens_the_door(self):
        check_no_context_laundering(
            "output_summary", "group_visible", ["private_to_invoker"],
            redacted=True, owner_consented=True,
        )


class BankAccountNumber(unittest.TestCase):
    def test_never_group_visible_even_with_redaction_and_consent(self):
        """Not a default that may be widened -- a ceiling. The number reaches
        exactly one person: whoever has to transfer to it."""
        with self.assertRaises(VisibilityError) as caught:
            check_no_context_laundering(
                "bank_account_number", "group_visible", ["group_visible"],
                redacted=True, owner_consented=True,
            )
        self.assertEqual(caught.exception.code, "NEVER_GROUP_VISIBLE")


class Defaults(unittest.TestCase):
    def test_matrix_matches_section_10_2(self):
        self.assertEqual(DEFAULT_VISIBILITY["user_typed_text"], "private_to_invoker")
        self.assertEqual(DEFAULT_VISIBILITY["attachment"], "private_to_invoker")
        self.assertEqual(DEFAULT_VISIBILITY["output_per_person_allocation"], "private_to_invoker")
        self.assertEqual(DEFAULT_VISIBILITY["invocation_event"], "group_summary_private_details")
        self.assertEqual(DEFAULT_VISIBILITY["output_summary"], "group_summary_private_details")

    def test_every_default_is_a_known_level(self):
        for component, level in DEFAULT_VISIBILITY.items():
            with self.subTest(component=component):
                self.assertIn(level, LEVELS)


class Declassification(unittest.TestCase):
    def field(self):
        return {
            "id": "f1", "owner_id": "ha", "component": "output_summary",
            "visibility": "private_to_invoker",
        }

    def test_creates_a_derivative_and_leaves_the_original_alone(self):
        original = self.field()
        derived = declassify(original, "group_visible", actor_id="ha", redaction={"masked": ["phone"]})
        self.assertEqual(derived["derived_from_id"], "f1")
        self.assertEqual(derived["visibility"], "group_visible")
        self.assertEqual(original["visibility"], "private_to_invoker")
        self.assertEqual(derived["source_visibility_unchanged"], "private_to_invoker")

    def test_only_the_field_owner_may_declassify(self):
        with self.assertRaises(VisibilityError) as caught:
            declassify(self.field(), "group_visible", actor_id="nam", redaction={"masked": []})
        self.assertEqual(caught.exception.code, "NOT_FIELD_OWNER")

    def test_redaction_is_mandatory(self):
        with self.assertRaises(VisibilityError) as caught:
            declassify(self.field(), "group_visible", actor_id="ha", redaction={})
        self.assertEqual(caught.exception.code, "REDACTION_REQUIRED")


class HistoryAccess(unittest.TestCase):
    """Section 10.4: the intersection of three conditions, not any one."""

    def base(self, **overrides):
        args = {
            "object_visibility": "group_summary_private_details",
            "viewer_joined_at": 100, "viewer_left_at": None,
            "object_created_at": 150,
            "audience_snapshot": {"ha"}, "viewer_id": "ha",
        }
        args.update(overrides)
        return args

    def test_all_three_satisfied(self):
        self.assertTrue(can_view_history(**self.base()))

    def test_new_member_sees_nothing_from_before_joining(self):
        self.assertFalse(can_view_history(**self.base(object_created_at=50)))

    def test_departed_member_sees_nothing_created_after_leaving(self):
        self.assertFalse(can_view_history(**self.base(viewer_left_at=120)))

    def test_membership_does_not_unlock_a_private_invocation(self):
        """The trap this rule exists for: being a member at the time is not
        the same as being an intended audience."""
        self.assertFalse(can_view_history(**self.base(object_visibility="private_to_invoker")))

    def test_not_in_the_audience_snapshot_means_no(self):
        self.assertFalse(can_view_history(**self.base(audience_snapshot={"nam"})))


class SettlementView(unittest.TestCase):
    def full_obligation(self):
        data = {field: f"value-{field}" for field in SETTLEMENT_VIEW_FIELDS}
        data["someone_elses_allocation"] = "SECRET"
        data["original_bill_image"] = "SECRET"
        return data

    def test_is_a_whitelist_not_a_blacklist(self):
        """A blacklist grows a hole the first time somebody adds a field and
        forgets to exclude it -- and the forgotten field is somebody else's
        allocation."""
        view = settlement_view(self.full_obligation())
        self.assertEqual(set(view), set(SETTLEMENT_VIEW_FIELDS))
        self.assertNotIn("someone_elses_allocation", view)
        self.assertNotIn("original_bill_image", view)

    def test_incomplete_input_is_refused(self):
        with self.assertRaises(VisibilityError) as caught:
            settlement_view({"own_amount_vnd": 1})
        self.assertEqual(caught.exception.code, "INCOMPLETE_SETTLEMENT_VIEW")


if __name__ == "__main__":
    unittest.main()
