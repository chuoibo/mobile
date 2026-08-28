"""Ledger behaviour, product spec sections 4 and 8."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.domain.allocator import allocate  # noqa: E402
from app.domain.ledger import (  # noqa: E402
    LedgerError,
    group_balances,
    merge_obligations,
    obligation_status,
    obligations_from_allocations,
    settlement_suggestions,
)


class ObligationsFromAllocations(unittest.TestCase):
    def test_advancer_owes_nothing_to_themselves(self):
        obligations = obligations_from_allocations({"ha": 82000, "nam": 100000}, "nam", "v1")
        self.assertEqual([o["sender_id"] for o in obligations], ["ha"])
        self.assertTrue(all(o["recipient_id"] == "nam" for o in obligations))

    def test_zero_share_creates_no_obligation(self):
        """A zero-dong payment request is pure noise."""
        obligations = obligations_from_allocations({"ha": 0, "nam": 100}, "nam", "v1")
        self.assertEqual(obligations, [])

    def test_obligations_sum_to_total_minus_the_advancer_share(self):
        allocations = {"ha": 82000, "nam": 100000, "binh": 55000}
        obligations = obligations_from_allocations(allocations, "nam", "v1")
        self.assertEqual(
            sum(o["amount_vnd"] for o in obligations),
            sum(allocations.values()) - allocations["nam"],
        )

    def test_advancer_outside_the_participant_set_is_still_the_creditor(self):
        """ADR-0004 decision 7 denies them a share, not the money they fronted."""
        obligations = obligations_from_allocations({"ha": 50, "nam": 50}, "outsider", "v1")
        self.assertEqual(len(obligations), 2)
        self.assertEqual(sum(o["amount_vnd"] for o in obligations), 100)

    def test_no_advancer_is_rejected(self):
        with self.assertRaises(LedgerError) as caught:
            obligations_from_allocations({"ha": 50}, None, "v1")
        self.assertEqual(caught.exception.code, "NO_ADVANCER")

    def test_flows_from_the_real_allocator(self):
        result = allocate({
            "participants": ["ha", "nam", "binh"], "total_vnd": 100000,
            "items": [], "surcharges": [], "discounts": [], "advancer_id": "nam",
        })
        obligations = obligations_from_allocations(result["allocations"], "nam", "v1")
        self.assertEqual(
            sum(o["amount_vnd"] for o in obligations),
            100000 - result["allocations"]["nam"],
        )


class MoneyValidation(unittest.TestCase):
    """Blocker P1-01. Review found three separate ways an invalid amount got
    in, because each entry point checked differently or not at all."""

    def test_a_negative_advancer_allocation_is_caught(self):
        """The advancer branch ran before validation, so an amount that never
        became an obligation was also never checked."""
        with self.assertRaises(LedgerError) as caught:
            obligations_from_allocations({"a": 100, "nam": -100}, "nam", "v1")
        self.assertEqual(caught.exception.code, "NEGATIVE_AMOUNT")

    def test_merge_refuses_a_negative_amount(self):
        """100 and -80 used to merge into a cheerful obligation of 20."""
        with self.assertRaises(LedgerError) as caught:
            merge_obligations([
                {"sender_id": "a", "recipient_id": "b", "amount_vnd": 100, "source_expense_version_id": "v1"},
                {"sender_id": "a", "recipient_id": "b", "amount_vnd": -80, "source_expense_version_id": "v2"},
            ])
        self.assertEqual(caught.exception.code, "NEGATIVE_AMOUNT")

    def test_floats_and_bools_are_refused_everywhere(self):
        for bad in (0.5, True, "100"):
            with self.subTest(bad=bad):
                with self.assertRaises(LedgerError):
                    obligations_from_allocations({"a": bad}, "nam", "v1")

    def test_settlement_suggestions_refuse_float_balances(self):
        with self.assertRaises(LedgerError) as caught:
            settlement_suggestions({"a": -0.5, "b": 0.5})
        self.assertEqual(caught.exception.code, "AMOUNT_NOT_INTEGER")


class ReceiptsAreSubtractedOnce(unittest.TestCase):
    """Blocker P1-01, the one that showed a wrong number to a real person."""

    def test_two_obligations_in_one_pair_share_one_receipt(self):
        """The receipt used to be subtracted from every obligation in the pair,
        so 60 + 40 against a receipt of 50 showed 10 remaining instead of 50.

        Reading low is the dangerous direction: nobody chases what they believe
        they have already been paid.
        """
        obligations = [
            {"sender_id": "a", "recipient_id": "b", "amount_vnd": 60},
            {"sender_id": "a", "recipient_id": "b", "amount_vnd": 40},
        ]
        self.assertEqual(group_balances(obligations, {("a", "b"): 50}), {"a": -50, "b": 50})

    def test_a_full_receipt_clears_the_pair(self):
        obligations = [
            {"sender_id": "a", "recipient_id": "b", "amount_vnd": 60},
            {"sender_id": "a", "recipient_id": "b", "amount_vnd": 40},
        ]
        self.assertEqual(group_balances(obligations, {("a", "b"): 100}), {})

    def test_suggestions_are_shaped_as_drafts_not_obligations(self):
        """An obligation-shaped dict invites a caller to persist it, and
        section 8.8 requires every affected party to accept an offset first."""
        for transfer in settlement_suggestions({"a": -70, "b": 70}):
            self.assertEqual(transfer["kind"], "offset_proposal_draft")


class Merging(unittest.TestCase):
    def test_same_pair_is_summed(self):
        merged = merge_obligations([
            {"sender_id": "ha", "recipient_id": "nam", "amount_vnd": 82000, "source_expense_version_id": "v1"},
            {"sender_id": "ha", "recipient_id": "nam", "amount_vnd": 18000, "source_expense_version_id": "v2"},
        ])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["amount_vnd"], 100000)
        self.assertEqual(merged[0]["source_expense_version_ids"], ("v1", "v2"))

    def test_opposite_directions_are_never_netted(self):
        """Section 8.8 makes offsetting a social agreement, not arithmetic."""
        merged = merge_obligations([
            {"sender_id": "ha", "recipient_id": "nam", "amount_vnd": 50000, "source_expense_version_id": "v1"},
            {"sender_id": "nam", "recipient_id": "ha", "amount_vnd": 30000, "source_expense_version_id": "v2"},
        ])
        self.assertEqual(len(merged), 2)
        self.assertEqual({o["amount_vnd"] for o in merged}, {50000, 30000})

    def test_different_recipients_are_never_merged(self):
        merged = merge_obligations([
            {"sender_id": "ha", "recipient_id": "nam", "amount_vnd": 50000, "source_expense_version_id": "v1"},
            {"sender_id": "ha", "recipient_id": "binh", "amount_vnd": 30000, "source_expense_version_id": "v1"},
        ])
        self.assertEqual(len(merged), 2)

    def test_self_obligation_is_rejected(self):
        with self.assertRaises(LedgerError) as caught:
            merge_obligations([
                {"sender_id": "ha", "recipient_id": "ha", "amount_vnd": 1, "source_expense_version_id": "v1"}
            ])
        self.assertEqual(caught.exception.code, "SELF_OBLIGATION")

    def test_merge_order_does_not_matter(self):
        a = {"sender_id": "ha", "recipient_id": "nam", "amount_vnd": 1, "source_expense_version_id": "v1"}
        b = {"sender_id": "binh", "recipient_id": "nam", "amount_vnd": 2, "source_expense_version_id": "v2"}
        self.assertEqual(merge_obligations([a, b]), merge_obligations([b, a]))


class DerivedStatus(unittest.TestCase):
    def test_status_comes_from_confirmed_amounts(self):
        self.assertEqual(obligation_status(100, []), "outstanding")
        self.assertEqual(obligation_status(100, [{"amount_vnd": 60}]), "partially_confirmed")
        self.assertEqual(obligation_status(100, [{"amount_vnd": 60}, {"amount_vnd": 40}]), "confirmed")
        self.assertEqual(obligation_status(100, [{"amount_vnd": 150}]), "over_confirmed")

    def test_sender_self_report_is_not_an_input(self):
        """Section 8.6: 'I transferred' never closes an obligation.

        This used to pin the exact parameter list, which broke the moment a
        legitimate parameter was added -- and a test that fails on any change
        is a test people edit to match instead of reading. It now asserts the
        thing it was protecting: nothing about a sender's own claim can reach
        this function, whatever else the signature grows.
        """
        import inspect

        parameters = list(inspect.signature(obligation_status).parameters)
        for forbidden in ("report", "payment", "sender", "claim", "self"):
            assert not any(forbidden in name for name in parameters), (
                f"a parameter mentioning {forbidden!r} appeared: {parameters}"
            )
        # The two positional inputs are the whole of the evidence: what was
        # declared, and what the recipient confirmed.
        signature = inspect.signature(obligation_status)
        positional = [
            name
            for name, param in signature.parameters.items()
            if param.kind is not inspect.Parameter.KEYWORD_ONLY
        ]
        self.assertEqual(positional, ["declared_amount_vnd", "receipt_confirmations"])

    def test_a_dispute_is_not_one_of_these_values(self):
        """This function briefly took a `disputed` argument and could return
        "disputed", with "money already arrived wins" as the tie-break. QA
        broke that from both sides in an hour: a recipient could erase an
        objection by confirming receipt, and a guest who objected after a
        mistaken confirmation could never be shown as disputed at all.

        Two facts had been collapsed into one field. Whether the money arrived
        is settled by a receipt; whether anyone disagrees is not."""
        import inspect

        parameters = list(inspect.signature(obligation_status).parameters)
        assert "disputed" not in parameters, (
            "a dispute is a separate fact and does not belong in this signature"
        )
        for amounts, expected in (
            ([], "outstanding"),
            ([{"amount_vnd": 60}], "partially_confirmed"),
            ([{"amount_vnd": 100}], "confirmed"),
            ([{"amount_vnd": 150}], "over_confirmed"),
        ):
            self.assertEqual(obligation_status(100, amounts), expected)


class Balances(unittest.TestCase):
    def test_group_balance_is_netted_and_sums_to_zero(self):
        obligations = [
            {"sender_id": "ha", "recipient_id": "nam", "amount_vnd": 50000},
            {"sender_id": "nam", "recipient_id": "ha", "amount_vnd": 30000},
        ]
        balances = group_balances(obligations)
        self.assertEqual(balances, {"ha": -20000, "nam": 20000})
        self.assertEqual(sum(balances.values()), 0)

    def test_confirmed_receipts_reduce_the_balance(self):
        obligations = [{"sender_id": "ha", "recipient_id": "nam", "amount_vnd": 50000}]
        self.assertEqual(group_balances(obligations, {("ha", "nam"): 50000}), {})

    def test_settlement_suggestions_clear_the_same_positions(self):
        balances = {"a": -70, "b": -30, "c": 60, "d": 40}
        transfers = settlement_suggestions(balances)
        rebuilt: dict[str, int] = {}
        for transfer in transfers:
            rebuilt[transfer["sender_id"]] = rebuilt.get(transfer["sender_id"], 0) - transfer["amount_vnd"]
            rebuilt[transfer["recipient_id"]] = rebuilt.get(transfer["recipient_id"], 0) + transfer["amount_vnd"]
        self.assertEqual(rebuilt, balances)
        self.assertTrue(all(t["amount_vnd"] > 0 for t in transfers))

    def test_settlement_suggestions_reject_unbalanced_input(self):
        with self.assertRaises(LedgerError) as caught:
            settlement_suggestions({"a": -10, "b": 5})
        self.assertEqual(caught.exception.code, "BALANCES_DO_NOT_NET_TO_ZERO")


if __name__ == "__main__":
    unittest.main()
