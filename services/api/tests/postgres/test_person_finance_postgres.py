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

from .conftest import seed_context

NOW = datetime(2030, 8, 29, 12, 0, tzinfo=UTC)

# Two participants, an even split of a round number, so every figure below can
# be read without arithmetic getting in the way of what is being asserted.
TOTAL_VND = 300_000
SHARE_VND = 150_000


class Slice:
    """One group, one payer, one person who owes them."""

    def __init__(self, session: Session):
        self.session = session
        self.repository = SqlAlchemyApiRepository(session)
        self.context_id = seed_context(session)
        # `payer` fronts the bill; `sender` owes them a share. The names are
        # the roles the ledger uses, not the roles the screen shows.
        self.payer_id = uuid.uuid4()
        self.sender_id = uuid.uuid4()
        #: Set by `publish`; the sender's guest link, needed to file a claim.
        self.token_digest: bytes | None = None

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
            allocations={
                self.sender_id: share_vnd,
                self.payer_id: total_vnd - share_vnd,
            },
            confirmed_by_id=self.payer_id,
            payer_acknowledgement="acknowledged",
            now=NOW,
        )
        self.session.flush()
        return expense_id, confirmation

    def publish(self, expense_version_id: uuid.UUID, *, amount_vnd: int = SHARE_VND):
        """Freeze and publish a batch billing `sender` for their share.

        Keeps the guest link's digest, because the sender's own claim that they
        transferred can only be recorded through that link -- see
        `report_payment`.
        """
        inputs = self.repository.load_batch_inputs(
            self.context_id, (expense_version_id,)
        )
        source = next(
            row
            for row in inputs.expenses[0].allocations
            if row.participant_id == self.sender_id
        )
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
            now=NOW + timedelta(minutes=1),
        )
        batch = self.repository.load_batch_for_publish(frozen.id)
        assert batch is not None
        self.token_digest = hashlib.sha256(uuid.uuid4().bytes).digest()
        self.repository.save_published_batch(
            batch=batch,
            status="published",
            links=(
                GuestLinkDraft(
                    sender_id=self.sender_id,
                    token_digest=self.token_digest,
                    expires_at=NOW + timedelta(days=30),
                ),
            ),
            actor_id=self.payer_id,
            now=NOW + timedelta(minutes=2),
        )
        self.session.flush()
        return frozen.obligations[0].id

    def report_payment(self, obligation_id: uuid.UUID, minute: int):
        """The guest pressing *Tôi đã chuyển*, and nothing else after it.

        Same two repository calls `POST /g/{token}/da-chuyen` makes, so this is
        the state a real sender can put the ledger into on their own: a claim
        on the record, with no `ReceiptConfirmation` anywhere.
        """
        assert self.token_digest is not None, "publish first: the claim needs a link"
        now = NOW + timedelta(minutes=minute)
        target = self.repository.get_payment_report_target(
            self.token_digest, obligation_id, now
        )
        assert target is not None
        record = self.repository.save_payment_report(
            target=target, idempotency_key=uuid.uuid4(), now=now
        )
        self.session.flush()
        return record

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
    assert summary.receivable_vnd == 0
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


def test_saying_you_transferred_settles_nothing_by_itself(slice_: Slice):
    """Nobody clears their own debt by pressing a button.

    `POST /g/{token}/da-chuyen` writes a `PaymentReport`: the sender's claim
    that they sent the money. Only a `ReceiptConfirmation` -- the other side
    saying it arrived -- may move this screen.

    This is the case the file spent its first draft only asserting from the
    positive side. Every test above drives the ledger through
    `confirm_receipt`, which passes `payment_report_id=None`, so no
    `PaymentReport` row had ever existed in this file and a summary that
    counted reports as payments would have passed all of them. The precondition
    is not hypothetical: the guest route that writes this row is live, and the
    obvious repair for "the board still says chưa gửi" is exactly the query
    this test forbids.
    """
    _, confirmation = slice_.confirm_expense()
    obligation_id = slice_.publish(confirmation.expense_version_id)
    before = slice_.summary(slice_.sender_id)

    report = slice_.report_payment(obligation_id, minute=7)

    # Without this the test is vacuous: it would pass against a summary that
    # sums reports, simply because there was nothing to sum.
    assert report.amount_vnd == SHARE_VND, "the claim covers the whole debt"
    assert report.receipt_amounts_vnd == (), "and nobody has confirmed anything"

    after = slice_.summary(slice_.sender_id)

    assert after.outstanding_vnd == before.outstanding_vnd == SHARE_VND
    assert after.settled_vnd == before.settled_vnd == 0
    assert after.movements == (), "a claim is not an arrival"


def test_confirming_more_than_was_owed_never_makes_the_debt_negative(slice_: Slice):
    """Over-confirmation is a state the ledger permits, so the screen must survive it.

    Nothing stops a recipient confirming twice -- there is no cap in
    `save_receipt_confirmation`, and the ledger is append-only, so a mistaken
    second confirmation stays there for good. Unclamped, this person's debt
    would read as -50.000đ and `settled` would climb to 200.000đ on a dinner
    that cost them 150.000đ: money that was never spent, shown as paid, for the
    rest of the account's life.
    """
    _, confirmation = slice_.confirm_expense()
    obligation_id = slice_.publish(confirmation.expense_version_id)

    slice_.confirm_receipt(obligation_id, SHARE_VND, minute=7)
    # The same arrival confirmed a second time, for part of the amount.
    slice_.confirm_receipt(obligation_id, 50_000, minute=8)

    summary = slice_.summary(slice_.sender_id)

    assert summary.outstanding_vnd >= 0, "a debt does not go below nothing"
    assert summary.outstanding_vnd == 0
    assert summary.spend_vnd == SHARE_VND
    assert summary.settled_vnd == SHARE_VND, "settled cannot exceed what was spent"
    assert summary.settled_vnd + summary.outstanding_vnd == summary.spend_vnd


def test_the_payer_is_owed_the_share_they_fronted_for_somebody_else(slice_: Slice):
    """The other half of the debt question, and the one the screen never asked.

    Every test above reads the ledger from the side of the person who owes.
    Mockup 07.02 puts three cards in a row -- *Đã trả*, *Còn nhận*, *Còn phải
    trả* -- and the middle one is this number: what other people owe you
    because you put the money down for them. Without it the person who fronts
    the bill, which on the demo path is the person doing the demo, opens Cá
    nhân after a split and reads `Còn nợ 0đ` with nothing anywhere saying that
    150.000đ is coming back to them.

    Symmetric to `outstanding_vnd` by construction: their share of the newest
    version of every expense they paid for, less what has actually arrived.
    Not derived from `spend_vnd` -- money advanced for other people was never
    this person's spend, and adding the two would invent a total nobody owes.
    """
    slice_.confirm_expense()

    summary = slice_.summary(slice_.payer_id)

    assert summary.receivable_vnd == SHARE_VND, "the sender's share is owed to them"
    assert summary.outstanding_vnd == 0, "and they owe nobody"
    assert summary.spend_vnd == TOTAL_VND - SHARE_VND, (
        "what they advanced for somebody else is not their own spend"
    )


def test_the_person_who_owes_is_not_owed_anything_back(slice_: Slice):
    """The negative half. Without it the pair could both read the same number.

    A query that forgot `participant_id != person_id` would count this
    person's own share as money owed to themselves, and the sender -- who
    fronted nothing -- would read *Còn nhận 150.000đ* on a dinner somebody
    else paid for.
    """
    slice_.confirm_expense()

    summary = slice_.summary(slice_.sender_id)

    assert summary.receivable_vnd == 0
    assert summary.outstanding_vnd == SHARE_VND


def test_an_arrival_clears_what_the_payer_was_owed(slice_: Slice):
    """Confirmed receipt moves both sides of the same transfer, once each."""
    _, confirmation = slice_.confirm_expense()
    obligation_id = slice_.publish(confirmation.expense_version_id)

    before = slice_.summary(slice_.payer_id)
    slice_.confirm_receipt(obligation_id, SHARE_VND, minute=7)
    after = slice_.summary(slice_.payer_id)

    assert before.receivable_vnd == SHARE_VND
    assert after.receivable_vnd == 0
    assert after.spend_vnd == before.spend_vnd, "an arrival is not a purchase"


def test_a_partial_arrival_leaves_only_the_remainder_receivable(slice_: Slice):
    _, confirmation = slice_.confirm_expense()
    obligation_id = slice_.publish(confirmation.expense_version_id)

    slice_.confirm_receipt(obligation_id, 50_000, minute=7)

    assert slice_.summary(slice_.payer_id).receivable_vnd == SHARE_VND - 50_000


def test_saying_you_transferred_does_not_reduce_what_the_payer_is_owed(slice_: Slice):
    """A claim is not an arrival, read from the creditor's side this time.

    `test_saying_you_transferred_settles_nothing_by_itself` pins this for the
    debtor. The same mistake on this side is worse: it would tell the person
    holding the money that they had been paid, on the word of the person who
    owes them.
    """
    _, confirmation = slice_.confirm_expense()
    obligation_id = slice_.publish(confirmation.expense_version_id)

    report = slice_.report_payment(obligation_id, minute=7)

    # Without this the case is vacuous -- it would pass against a summary that
    # counts reports, purely because there was nothing to count.
    assert report.amount_vnd == SHARE_VND
    assert report.receipt_amounts_vnd == ()

    assert slice_.summary(slice_.payer_id).receivable_vnd == SHARE_VND


def test_confirming_more_than_was_owed_never_makes_the_receivable_negative(
    slice_: Slice,
):
    """Same clamp as the debt, same reason: the ledger permits the state."""
    _, confirmation = slice_.confirm_expense()
    obligation_id = slice_.publish(confirmation.expense_version_id)

    slice_.confirm_receipt(obligation_id, SHARE_VND, minute=7)
    slice_.confirm_receipt(obligation_id, 50_000, minute=8)

    assert slice_.summary(slice_.payer_id).receivable_vnd == 0


def test_correcting_an_expense_does_not_double_what_the_payer_is_owed(slice_: Slice):
    """Only the newest version counts, on this side of the ledger too.

    `test_correcting_an_expense_does_not_count_both_versions` pins the same
    rule for spend. A receivable query written without the newest-version
    filter would bill the sender for the mistake and the fix together, and the
    payer would be shown 200.000đ arriving on a dinner that cost 100.000đ.
    """
    expense_id, _ = slice_.confirm_expense()
    slice_.confirm_expense(expense_id=expense_id, total_vnd=100_000, share_vnd=50_000)

    assert slice_.summary(slice_.payer_id).receivable_vnd == 50_000


def test_every_money_figure_arrives_as_a_python_int(slice_: Slice):
    """Law 1, checked at the boundary that breaks it.

    PostgreSQL sums a `bigint` column as `numeric`; psycopg hands that back as
    `Decimal`; FastAPI serialises a `Decimal` as `750000.0`. The value stays
    right and the type goes wrong, so every assertion on amounts elsewhere in
    this file still passes -- `Decimal("150000") == 150000` is true. Only the
    type says it happened.

    `type(...) is int`, not `isinstance`: `bool` and `Decimal` both compare
    equal to integers in places, and this asserts what the driver returned, not
    what it is worth.
    """
    _, confirmation = slice_.confirm_expense()
    obligation_id = slice_.publish(confirmation.expense_version_id)
    slice_.confirm_receipt(obligation_id, 40_000, minute=7)

    summary = slice_.summary(slice_.sender_id)

    for field in ("spend_vnd", "settled_vnd", "outstanding_vnd", "receivable_vnd"):
        value = getattr(summary, field)
        assert type(value) is int, (
            f"{field} came back as {type(value).__name__}: {value!r}"
        )

    (movement,) = summary.movements
    assert type(movement.amount_vnd) is int, (
        f"movement amount came back as {type(movement.amount_vnd).__name__}"
    )


def test_a_confirmed_receipt_clears_the_debt_and_appears_as_an_outgoing_movement(
    slice_: Slice,
):
    """Receipt confirmation is what settles. A payment *report* is not.

    The sender saying they transferred is a claim; the recipient confirming
    arrival is the event. A screen that settled on the report would tell
    somebody their debt was cleared because they themselves said so.

    Only the first half of that is asserted here; the negative half lives in
    `test_saying_you_transferred_settles_nothing_by_itself`, because this test
    creates no `PaymentReport` and so cannot see it counted.
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
            assert summary.settled_vnd + summary.outstanding_vnd == summary.spend_vnd, (
                stage
            )
            assert summary.outstanding_vnd >= 0, stage
            assert summary.settled_vnd >= 0, stage

    holds("after confirmation")
    obligation_id = slice_.publish(confirmation.expense_version_id)
    holds("after publish")
    slice_.confirm_receipt(obligation_id, 40_000, minute=7)
    holds("after a partial receipt")
    slice_.confirm_receipt(obligation_id, SHARE_VND - 40_000, minute=8)
    holds("after the balance arrives")
