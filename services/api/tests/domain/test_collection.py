"""Collection batch state machine, product spec section 8."""

from __future__ import annotations

import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.domain.collection import (  # noqa: E402
    CollectionError,
    counts_toward_collection_rate,
    is_stale,
    progress,
    terminal_state_for,
    transition,
    unmet_publish_gates,
)

READY = {
    "obligations": [{"sender_id": "ha", "status": "outstanding"}],
    "advancer_acknowledged": True,
    "bank_recipient_snapshot_valid": True,
    "delivery_method_chosen": True,
}


class StateMachine(unittest.TestCase):
    def test_happy_path(self):
        state = transition("accruing", "freeze", READY)
        self.assertEqual(state, "frozen")
        state = transition(state, "publish", READY)
        self.assertEqual(state, "published")
        state = transition(state, "expose_capability")
        self.assertEqual(state, "collecting")

    def test_only_accruing_accepts_new_expenses(self):
        """Section 8.1: 'add to the open batch' lists accruing batches only."""
        for state in ("frozen", "published", "collecting", "completed"):
            with self.subTest(state=state):
                with self.assertRaises(CollectionError):
                    transition(state, "freeze", READY)

    def test_terminal_states_accept_nothing(self):
        for state in ("completed", "closed_with_exceptions", "cancelled"):
            for event in ("freeze", "publish", "close", "cancel", "expose_capability"):
                with self.subTest(state=state, event=event):
                    with self.assertRaises(CollectionError) as caught:
                        transition(state, event, READY)
                    self.assertEqual(caught.exception.code, "ILLEGAL_TRANSITION")

    def test_cancel_is_available_before_the_end(self):
        for state in ("accruing", "frozen", "published", "collecting"):
            with self.subTest(state=state):
                self.assertEqual(transition(state, "cancel", READY), "cancelled")


class PublishGates(unittest.TestCase):
    def test_all_three_gates_are_reported(self):
        self.assertEqual(
            unmet_publish_gates({}),
            [
                "advancer_acknowledgement_required",
                "valid_bank_recipient_snapshot_required",
                "delivery_method_required",
            ],
        )

    def test_advancer_acknowledgement_cannot_be_skipped(self):
        """Section 8.3: gate 1 does not substitute for gate 2.

        If it did, a member could raise collections in someone else's name.
        """
        context = {**READY, "advancer_acknowledged": False}
        with self.assertRaises(CollectionError) as caught:
            transition("frozen", "publish", context)
        self.assertEqual(caught.exception.code, "ADVANCER_ACKNOWLEDGEMENT_REQUIRED")

    def test_unready_recipient_needs_an_explicit_choice(self):
        """Section 8.4: wait for everyone, or split them out. Not silence."""
        context = {**READY, "has_unready_recipient": True}
        with self.assertRaises(CollectionError) as caught:
            transition("accruing", "freeze", context)
        self.assertEqual(caught.exception.code, "UNREADY_RECIPIENT_CHOICE_REQUIRED")
        allowed = {**context, "unready_recipient_choice": "split_to_blocked_batch"}
        self.assertEqual(transition("accruing", "freeze", allowed), "frozen")


class Closing(unittest.TestCase):
    def test_clean_batch_completes(self):
        obligations = [{"sender_id": "ha", "status": "confirmed"}]
        self.assertEqual(terminal_state_for(obligations), "completed")

    def test_a_waiver_forces_closed_with_exceptions(self):
        """Otherwise a batch where someone was written off looks identical to
        one where everybody paid."""
        obligations = [
            {"sender_id": "ha", "status": "confirmed"},
            {"sender_id": "nam", "status": "waived"},
        ]
        self.assertEqual(terminal_state_for(obligations), "closed_with_exceptions")

    def test_open_obligations_block_closing(self):
        with self.assertRaises(CollectionError) as caught:
            terminal_state_for([{"sender_id": "ha", "status": "outstanding"}])
        self.assertEqual(caught.exception.code, "OBLIGATIONS_STILL_OPEN")

    def test_completed_is_never_chosen_by_the_caller(self):
        """Spec invariant 7: no arbitrary 'mark as done' button.

        `close` carries no target state; the machine derives it.
        """
        obligations = [{"sender_id": "ha", "status": "confirmed"}]
        self.assertEqual(transition("collecting", "close", {"obligations": obligations}), "completed")
        obligations.append({"sender_id": "nam", "status": "disputed"})
        self.assertEqual(
            transition("collecting", "close", {"obligations": obligations}),
            "closed_with_exceptions",
        )


class Progress(unittest.TestCase):
    def test_transfers_are_the_primary_denominator(self):
        """Section 8.7: counting people is wrong when one person owes two."""
        obligations = [
            {"sender_id": "ha", "status": "confirmed"},
            {"sender_id": "ha", "status": "outstanding"},
            {"sender_id": "nam", "status": "confirmed"},
        ]
        self.assertEqual(
            progress(obligations),
            {"transfers_done": 2, "transfers_total": 3, "people_done": 1, "people_total": 2},
        )

    def test_a_waiver_finishes_the_person_but_not_the_transfer(self):
        """No money moved, so it is not a completed transfer -- but the person
        who was forgiven has nothing left to do."""
        obligations = [
            {"sender_id": "ha", "status": "confirmed"},
            {"sender_id": "ha", "status": "waived"},
        ]
        result = progress(obligations)
        self.assertEqual(result["transfers_done"], 1)
        self.assertEqual(result["transfers_total"], 2)
        self.assertEqual(result["people_done"], 1)
        self.assertEqual(result["people_total"], 1)

    def test_a_dispute_leaves_the_person_unfinished(self):
        obligations = [{"sender_id": "ha", "status": "disputed"}]
        self.assertEqual(progress(obligations)["people_done"], 0)


class Staleness(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 27, tzinfo=timezone.utc)

    def test_both_conditions_are_required(self):
        long_overdue = self.now - timedelta(days=20)
        recent_activity = self.now - timedelta(days=2)
        quiet = self.now - timedelta(days=10)
        self.assertFalse(is_stale(self.now, long_overdue, recent_activity))
        self.assertFalse(is_stale(self.now, self.now - timedelta(days=3), quiet))
        self.assertTrue(is_stale(self.now, long_overdue, quiet))


class AntiCosmetics(unittest.TestCase):
    def test_abandoned_after_exposure_stays_in_the_denominator(self):
        """Section 8.9. Otherwise the collection rate can be groomed by
        cancelling every batch that went badly."""
        batch = {"state": "cancelled", "capability_exposed_at": "2026-08-01T00:00:00+07:00"}
        self.assertTrue(counts_toward_collection_rate(batch))

    def test_cancelled_before_anyone_was_asked_is_excluded(self):
        batch = {"state": "cancelled", "capability_exposed_at": None}
        self.assertFalse(counts_toward_collection_rate(batch))

    def test_live_batches_always_count(self):
        self.assertTrue(counts_toward_collection_rate({"state": "collecting", "capability_exposed_at": None}))


if __name__ == "__main__":
    unittest.main()
