"""The single permission table, spec section 9."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.domain.permissions import (  # noqa: E402
    ACTIONS,
    AuthorizationFacts,
    PermissionError_,
    can,
    denial_reason,
)


def facts(roles, proven=(), actor="u1", resource="r1"):
    """Build facts the way an adapter would, with provenance recorded."""
    return AuthorizationFacts(
        actor_id=actor,
        roles=frozenset(roles),
        resource_id=resource,
        proven=frozenset(proven),
        provenance="test_fixture",
    )


class TableShape(unittest.TestCase):
    def test_unknown_action_raises_rather_than_silently_denying(self):
        """A typo in an action name must fail loudly.

        Returning False would turn a misspelled permission check into a silent
        deny that looks exactly like a correct deny in production.
        """
        with self.assertRaises(PermissionError_) as caught:
            can("publsh_batch", facts({"batch_owner"}))
        self.assertEqual(caught.exception.code, "UNKNOWN_ACTION")

    def test_covers_the_eleven_action_groups_of_section_9(self):
        self.assertGreaterEqual(len(ACTIONS), 25)


class FactsAreTheTrustBoundary(unittest.TestCase):
    """Blocker P1-02. A dict of booleans from a request body and a dict from
    the database look identical to a function signature, so the type is the
    boundary rather than a convention."""

    def test_a_plain_dict_is_refused(self):
        with self.assertRaises(PermissionError_) as caught:
            can("publish_batch", {"owns_batch": True})
        self.assertEqual(caught.exception.code, "UNTYPED_FACTS")

    def test_facts_without_provenance_are_refused(self):
        """An unattributed fact cannot be audited later, and the whole point of
        one permission table is that every decision can be explained."""
        with self.assertRaises(PermissionError_) as caught:
            AuthorizationFacts(actor_id="u1", roles=frozenset({"member"}), resource_id="r1")
        self.assertEqual(caught.exception.code, "FACTS_WITHOUT_PROVENANCE")

    def test_anonymous_actor_is_refused(self):
        with self.assertRaises(PermissionError_) as caught:
            AuthorizationFacts(actor_id="", roles=frozenset(), resource_id=None, provenance="x")
        self.assertEqual(caught.exception.code, "ANONYMOUS_ACTOR")

    def test_unknown_role_is_refused(self):
        with self.assertRaises(PermissionError_) as caught:
            AuthorizationFacts(actor_id="u1", roles=frozenset({"superuser"}),
                               resource_id=None, provenance="x")
        self.assertEqual(caught.exception.code, "UNKNOWN_ROLE")


class BatchOwnerIsNotOmnipotent(unittest.TestCase):
    """Section 9.1 lists what the batch owner may NOT do alone."""

    def test_may_freeze_and_publish_own_batch(self):
        proven = ["owns_batch", "all_recipients_eligible"]
        self.assertTrue(can("freeze_batch", facts({"batch_owner"}, proven)))
        self.assertTrue(can("publish_batch", facts({"batch_owner"}, proven)))

    def test_may_not_publish_until_every_recipient_is_eligible(self):
        self.assertEqual(
            denial_reason("publish_batch", facts({"batch_owner"}, ['owns_batch'])),
            "all_recipients_eligible",
        )

    def test_may_not_freeze_someone_elses_batch(self):
        self.assertEqual(denial_reason("freeze_batch", facts({"batch_owner"})), "owns_batch")

    def test_may_not_cancel_an_obligation_alone(self):
        self.assertEqual(
            denial_reason("cancel_obligation", facts({"batch_owner"})),
            "all_affected_parties_consented",
        )

    def test_nobody_may_delete_payment_or_receipt_events(self):
        """Deleting these would let the ledger be rewritten to suit whoever
        holds the button."""
        for action in ("delete_payment_report", "delete_receipt_confirmation", "delete_audit_history"):
            for roles in ({"batch_owner"}, {"group_admin"}, {"platform_moderator"}):
                with self.subTest(action=action, roles=roles):
                    self.assertEqual(denial_reason(action, facts(roles)), "action_permitted_to_nobody")


class GroupAdminIsLogisticsNotFinance(unittest.TestCase):
    """Section 9.2."""

    def test_can_do_membership_logistics(self):
        for action in ("manage_members_and_invites", "remove_member_from_group", "transfer_group_admin"):
            with self.subTest(action=action):
                self.assertTrue(can(action, facts({"group_admin"})))

    def test_cannot_adjudicate_identity(self):
        """In a group identity dispute the attacker is a group member, so the
        group cannot be the judge."""
        self.assertEqual(
            denial_reason("adjudicate_person_stub_claim", facts({"group_admin"})),
            "role_not_permitted",
        )

    def test_cannot_set_someone_elses_bank_recipient(self):
        self.assertEqual(
            denial_reason("set_bank_recipient", facts({"group_admin", "member"}, ['is_authenticated_account'])),
            "is_own_account",
        )

    def test_cannot_remove_other_peoples_content(self):
        self.assertEqual(denial_reason("remove_others_content", facts({"group_admin"})), "role_not_permitted")


class WaiverBelongsToTheCreditor(unittest.TestCase):
    def test_organiser_cannot_forgive_on_someone_elses_behalf(self):
        self.assertEqual(
            denial_reason("waive_obligation", facts({"batch_owner", "member"})),
            "role_not_permitted",
        )

    def test_creditor_of_this_receivable_can(self):
        self.assertTrue(
            can("waive_obligation", facts({"creditor"}, ['is_creditor_of_this_obligation']))
        )

    def test_creditor_of_a_different_receivable_cannot(self):
        self.assertEqual(
            denial_reason("waive_obligation", facts({"creditor"})),
            "is_creditor_of_this_obligation",
        )


class RevocationFollowsRisk(unittest.TestCase):
    """Section 9.1: whoever holds data or risk in a capability may pull it back."""

    def test_three_subjects_three_scopes(self):
        self.assertTrue(can("revoke_capability_whole_batch", facts({"batch_owner"}, ['owns_batch'])))
        self.assertTrue(can("revoke_capability_own_recipient_account", facts({"recipient"}, ['envelope_contains_own_account'])))
        self.assertTrue(can("revoke_capability_own_envelope", facts({"sender"}, ['is_own_capability'])))

    def test_a_sender_cannot_revoke_the_whole_batch(self):
        self.assertEqual(
            denial_reason("revoke_capability_whole_batch", facts({"sender"}, ['owns_batch'])),
            "role_not_permitted",
        )


class AdvancerAcknowledgement(unittest.TestCase):
    def test_only_the_named_advancer_may_acknowledge(self):
        """Gate 2 of section 8.3. Otherwise a member raises collections in
        someone else's name."""
        self.assertEqual(
            denial_reason("acknowledge_advancer_role", facts({"advancer"})),
            "is_named_advancer",
        )
        self.assertTrue(can("acknowledge_advancer_role", facts({"advancer"}, ['is_named_advancer'])))


if __name__ == "__main__":
    unittest.main()
