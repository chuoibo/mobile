"""What the personal screen reads, proved against the real ledger.

The screen this covers is the last stop on the demo path: split a bill, come
back, and the totals have moved. That sentence is the whole feature, and it is
untestable against the fake repository -- the fake stores whatever it is
handed, so a summary computed from it proves only that a dict round-trips.
Every figure here is recomputed by SQL from append-only tables, so this file
runs on real PostgreSQL after Alembic has migrated a schema.

Four things are asserted that a "does it return 200" test would miss, each of
which was wrong in the first draft of the query:

- **A share becomes owed when the expense is confirmed, not when somebody gets
  around to sending the collection round.** The draft counted only published
  obligations, which meant the moment right after a split -- the exact moment
  the demo returns to this screen -- showed the new share under *Đã thanh
  toán*. The debt existed; the screen called it paid.
- **The payer's own share is not a debt.** They handed the money to the
  restaurant. Nobody bills them, and no obligation row is ever written for
  them, so a query keyed on obligations cannot see the difference.
- **Editing an expense must not double the spend.** Corrections write a new
  version rather than overwriting, so summing every allocation counts both the
  wrong answer and the right one.
- **`settled + outstanding == spend`, at every intermediate state**, because
  the mockup puts the two numbers directly under the total and a reader adds
  them up.

Uses `flush`, never `commit`: `postgres_session` rolls back per test, and the
schema is shared with row-counting tests in this directory that go red if rows
from here survive.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.api.repository import (
    GuestLinkDraft,
    ObligationDraft,
    SqlAlchemyApiRepository,
)
from app.api.service import ExpenseInput
from app.db.models import BankRecipient

NOW = datetime(2030, 8, 29, 12, 0, tzinfo=UTC)

# Two participants, an even split of a round number, so every figure below can
# be read without arithmetic getting in the way of what is being asserted.
TOTAL_VND = 300_000
SHARE_VND = 150_000
KNOWN_BANK_BIN = "970415"


class Slice:
    """One group, one payer, one person who owes them."""

    def __init__(self, session: Session):
        self.session = session
        self.repository = SqlAlchemyApiRepository(session)
        self.context_id = uuid.uuid4()
        # `payer` fronts the bill; `sender` owes them a share. The names are
        # the roles the ledger uses, not the roles the screen shows.
        self.payer_id = uuid.uuid4()
        self.sender_id = uuid.uuid4()

    def summary(self, person_id: uuid.UUID):
        return self.repository.person_finance_summary(person_id, movement_limit=20)

    def confirm_expense(
        self,
        *,
        description: str = "Lẩu nấm",
        total_vnd: int = TOTAL_VND,
        share_vnd: int = SHARE_VND,
        expense_id: uuid.UUID | None = None,
    ):
        """Record and confirm one expense, split evenly between the two."""
        if expense_id is None:
            expense_id = self.repository.create_expense(self.context_id).id
        proposal = ExpenseInput(
            context_id=self.context_id,
            description=description,
            recorded_by_id=self.payer_id,
            paid_by_id=self.payer_id,
            verification_scope="totals_only",
            occurred_at=NOW,
            participants=[self.sender_id, self.payer_id],
            total_amount_vnd=total_vnd,
            items=[],
            surcharges=[],
            discounts=[],
        )
        confirmation = self.repository.save_expense_confirmation(
            expense_id=expense_id,
            proposal=proposal,
            allocator_expense={"warnings": []},
            rollups={
                "subtotal_amount_vnd": total_vnd,
                "fee_amount_vnd": 0,
                "vat_amount_vnd": 0,
                "shipping_amount_vnd": 0,
                "discount_amount_vnd": 0,
                "total_amount_vnd": total_vnd,
            },
            allocations={self.sender_id: share_vnd, self.payer_id: total_vnd - share_vnd},
            confirmed_by_id=self.payer_id,
            payer_acknowledgement="acknowledged",
            now=NOW,
        )
        self.session.flush()
        return expense_id, confirmation

    def publish(self, expense_version_id: uuid.UUID, *, amount_vnd: int = SHARE_VND):
        """Freeze and publish a batch billing `sender` for their share."""
        inputs = self.repository.load_batch_inputs(
            self.context_id, (expense_version_id,)
        )
        source = next(
            row
            for row in inputs.expenses[0].allocations
            if row.participant_id == self.sender_id
        )
        self.session.add(
            BankRecipient(
                recipient_id=self.payer_id,
                bank_bin=KNOWN_BANK_BIN,
                account_number="DEMOFINANCE",
                account_name="NGUOI NHAN - DU LIEU DEMO",
                confirmed_by_recipient_at=NOW,
                created_at=NOW,
            )
        )
        self.session.flush()
        frozen = self.repository.save_frozen_batch(
            context_id=self.context_id,
            owner_id=self.payer_id,
            due_at=NOW + timedelta(days=7),
            obligations=(
                ObligationDraft(
                    sender_id=self.sender_id,
                    recipient_id=self.payer_id,
                    amount_vnd=amount_vnd,
                    source_expense_version_ids=(expense_version_id,),
                    sources=(source,),
                ),
            ),
            bank_recipients=self.repository.load_bank_recipients(
                frozenset({self.payer_id})
            ),
            now=NOW + timedelta(minutes=1),
        )
        batch = self.repository.load_batch_for_publish(frozen.id)
        assert batch is not None
        self.repository.save_published_batch(
            batch=batch,
            status="published",
            links=(
                GuestLinkDraft(
                    sender_id=self.sender_id,
                    token_digest=hashlib.sha256(uuid.uuid4().bytes).digest(),
                    expires_at=NOW + timedelta(days=30),
                ),
            ),
            actor_id=self.payer_id,
            now=NOW + timedelta(minutes=2),
        )
        self.session.flush()
        return frozen.obligations[0].id

    def confirm_receipt(self, obligation_id: uuid.UUID, amount_vnd: int, minute: int):
        target = self.repository.get_receipt_target(obligation_id)
        assert target is not None
        record = self.repository.save_receipt_confirmation(
            target=target,
            confirmed_by_id=self.payer_id,
            amount_vnd=amount_vnd,
            payment_report_id=None,
            idempotency_key=uuid.uuid4(),
            now=NOW + timedelta(minutes=minute),
        )
        self.session.flush()
        return record


@pytest.fixture
def slice_(postgres_session: Session) -> Slice:
    return Slice(postgres_session)


def test_a_person_with_no_ledger_rows_reads_as_zero_not_as_missing(slice_: Slice):
    """A new account is answerable, and the answer is zero.

    Not a 404: a person who has not split anything yet is a real state, and
    404 would make it indistinguishable from a mistyped id.
    """
    summary = slice_.summary(uuid.uuid4())

    assert summary.spend_vnd == 0
    assert summary.settled_vnd == 0
    assert summary.outstanding_vnd == 0
    assert summary.expense_count == 0
    assert summary.movements == ()


def test_confirming_a_split_makes_the_share_owed_immediately(slice_: Slice):
    """The regression that matters most, because it is the demo's last step.

    Between confirming a split and publishing the collection round, the sender
    owes their share and nobody has been paid. Counting only published
    obligations reported this state as fully settled -- so returning to the
    personal screen right after a split showed the new money under *Đã thanh
    toán* rather than under *Còn nợ*.
    """
    slice_.confirm_expense()

    summary = slice_.summary(slice_.sender_id)

    assert summary.spend_vnd == SHARE_VND
    assert summary.outstanding_vnd == SHARE_VND, "a confirmed share is owed at once"
    assert summary.settled_vnd == 0, "nobody has paid anybody yet"
    assert summary.expense_count == 1


def test_the_person_who_fronted_the_bill_owes_nothing_for_their_own_share(
    slice_: Slice,
):
    """They already handed the money over, so their share is spend, not debt.

    No obligation row is ever written against a payer for their own share, so
    this case is invisible to any query that starts from obligations.
    """
    slice_.confirm_expense()

    summary = slice_.summary(slice_.payer_id)

    assert summary.spend_vnd == TOTAL_VND - SHARE_VND
    assert summary.outstanding_vnd == 0
    assert summary.settled_vnd == TOTAL_VND - SHARE_VND


def test_publishing_the_round_does_not_move_the_money_again(slice_: Slice):
    """Sending the request is not a second debt.

    The share is already owed from confirmation; publishing announces it. If
    both steps added, one dinner would bill the sender twice.
    """
    _, confirmation = slice_.confirm_expense()
    before = slice_.summary(slice_.sender_id)

    slice_.publish(confirmation.expense_version_id)
    after = slice_.summary(slice_.sender_id)

    assert after.outstanding_vnd == before.outstanding_vnd == SHARE_VND
    assert after.spend_vnd == before.spend_vnd


def test_a_partial_receipt_leaves_only_the_remainder_owed(slice_: Slice):
    _, confirmation = slice_.confirm_expense()
    obligation_id = slice_.publish(confirmation.expense_version_id)

    slice_.confirm_receipt(obligation_id, 50_000, minute=7)
    summary = slice_.summary(slice_.sender_id)

    assert summary.outstanding_vnd == SHARE_VND - 50_000
    assert summary.settled_vnd == 50_000
    assert summary.settled_vnd + summary.outstanding_vnd == summary.spend_vnd


def test_a_confirmed_receipt_clears_the_debt_and_appears_as_an_outgoing_movement(
    slice_: Slice,
):
    """Receipt confirmation is what settles. A payment *report* is not.

    The sender saying they transferred is a claim; the recipient confirming
    arrival is the event. A screen that settled on the report would tell
    somebody their debt was cleared because they themselves said so.
    """
    _, confirmation = slice_.confirm_expense()
    obligation_id = slice_.publish(confirmation.expense_version_id)

    slice_.confirm_receipt(obligation_id, SHARE_VND, minute=7)
    summary = slice_.summary(slice_.sender_id)

    assert summary.outstanding_vnd == 0
    assert summary.settled_vnd == SHARE_VND

    (movement,) = summary.movements
    assert movement.direction == "out", "the sender sent this money"
    assert movement.amount_vnd == SHARE_VND
    assert movement.counterparty_id == slice_.payer_id
    assert movement.occasion == "Lẩu nấm"


def test_the_same_settlement_is_an_incoming_movement_for_the_recipient(
    slice_: Slice,
):
    """One transfer, two people, opposite signs. Read from one row each way."""
    _, confirmation = slice_.confirm_expense()
    obligation_id = slice_.publish(confirmation.expense_version_id)
    slice_.confirm_receipt(obligation_id, SHARE_VND, minute=7)

    (movement,) = slice_.summary(slice_.payer_id).movements

    assert movement.direction == "in"
    assert movement.amount_vnd == SHARE_VND
    assert movement.counterparty_id == slice_.sender_id


def test_correcting_an_expense_does_not_count_both_versions(slice_: Slice):
    """Corrections write a new version; only the newest is what was spent.

    Summing every `confirmed_allocations` row counts the mistake and the fix
    together. On a money screen that reads as a total, which is the one kind
    of wrong number nobody spots by looking at it.
    """
    expense_id, _ = slice_.confirm_expense(total_vnd=TOTAL_VND, share_vnd=SHARE_VND)

    # Same expense, corrected: the bill was actually half what was recorded.
    slice_.confirm_expense(
        expense_id=expense_id,
        description="Lẩu nấm",
        total_vnd=100_000,
        share_vnd=50_000,
    )

    summary = slice_.summary(slice_.sender_id)

    assert summary.spend_vnd == 50_000, "the correction replaces, it does not add"
    assert summary.expense_count == 1, "one dinner, corrected once"
    assert summary.settled_vnd + summary.outstanding_vnd == summary.spend_vnd


def test_the_two_figures_under_the_total_always_add_back_up_to_it(slice_: Slice):
    """The invariant the mockup's layout promises, held at every stage.

    Checked as a walk rather than at the end, because the states in between
    are the ones a person actually looks at.
    """
    _, confirmation = slice_.confirm_expense()

    def holds(stage: str):
        for person_id in (slice_.sender_id, slice_.payer_id):
            summary = slice_.summary(person_id)
            assert (
                summary.settled_vnd + summary.outstanding_vnd == summary.spend_vnd
            ), stage
            assert summary.outstanding_vnd >= 0, stage
            assert summary.settled_vnd >= 0, stage

    holds("after confirmation")
    obligation_id = slice_.publish(confirmation.expense_version_id)
    holds("after publish")
    slice_.confirm_receipt(obligation_id, 40_000, minute=7)
    holds("after a partial receipt")
    slice_.confirm_receipt(obligation_id, SHARE_VND - 40_000, minute=8)
    holds("after the balance arrives")
