"""Persistence port and PostgreSQL adapter for API workflows.

The application service calls domain functions before invoking write methods in
this module. The adapter never invents allocations, merges debts, or stores an
obligation status. Receipt events remain the only input used to derive that
status.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import RepositoryConflict
from app.api.limits import OBJECTION_LIMIT, REPORT_LIMIT
from app.api.schemas import ExpenseInput
from app.db.models import (
    AuditEvent,
    BankRecipient,
    BankRecipientSnapshot,
    Bill,
    BillDiscount,
    BillItem,
    BillItemShare,
    BillShareSource,
    BillSurcharge,
    CollectionBatch,
    CollectionBatchStatus,
    CollectionBatchVersion,
    CollectionEnvelope,
    CollectionObligation,
    CollectionObligationSource,
    ConfirmedAllocation,
    Context,
    Expense,
    ExpenseDiscount,
    ExpenseItem,
    ExpenseItemShare,
    ExpenseSurcharge,
    ExpenseVersion,
    GuestLink,
    GuestLinkStatus,
    Membership,
    MembershipRole,
    MembershipState,
    Message,
    MessageKind,
    PayerAcknowledgement,
    PaymentReport,
    Person,
    ReceiptConfirmation,
    VerificationScope,
)
from app.domain.capability import capability_scope
from app.domain.ledger import obligation_status
from app.payments.vietqr import build_payload
from app.web.qr import payload_to_png_data_uri


@dataclass(frozen=True, slots=True)
class ExpenseIdentity:
    id: uuid.UUID
    context_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PersonRecord:
    id: uuid.UUID
    display_name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ContextRecord:
    id: uuid.UUID
    display_name: str
    created_by_id: uuid.UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MembershipRecord:
    id: uuid.UUID
    context_id: uuid.UUID
    person_id: uuid.UUID
    state: str
    role: str
    invited_by_id: uuid.UUID | None
    joined_at: datetime | None
    left_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MessageRecord:
    id: uuid.UUID
    context_id: uuid.UUID
    author_id: uuid.UUID | None
    kind: str
    body: str | None
    image_url: str | None
    card: dict | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MessagePage:
    messages: tuple[MessageRecord, ...]
    has_more: bool


@dataclass(frozen=True, slots=True)
class AllocationRow:
    id: uuid.UUID
    participant_id: uuid.UUID
    amount_vnd: int


@dataclass(frozen=True, slots=True)
class ConfirmedExpense:
    version_id: uuid.UUID
    context_id: uuid.UUID
    paid_by_id: uuid.UUID
    payer_acknowledgement: str
    allocations: tuple[AllocationRow, ...]


@dataclass(frozen=True, slots=True)
class ConfirmationRecord:
    expense_version_id: uuid.UUID
    version_number: int


@dataclass(frozen=True, slots=True)
class BatchInputs:
    expenses: tuple[ConfirmedExpense, ...]
    unavailable_version_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True, slots=True)
class BankRecipientRecord:
    id: uuid.UUID
    recipient_id: uuid.UUID
    bank_bin: str
    account_number: str
    account_name: str | None
    confirmed_at: datetime


@dataclass(frozen=True, slots=True)
class ObligationDraft:
    sender_id: uuid.UUID
    recipient_id: uuid.UUID
    amount_vnd: int
    source_expense_version_ids: tuple[uuid.UUID, ...]
    sources: tuple[AllocationRow, ...]


@dataclass(frozen=True, slots=True)
class FrozenObligation:
    id: uuid.UUID
    sender_id: uuid.UUID
    recipient_id: uuid.UUID
    amount_vnd: int
    due_at: datetime
    source_expense_version_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True, slots=True)
class FrozenBatch:
    id: uuid.UUID
    version_id: uuid.UUID
    obligations: tuple[FrozenObligation, ...]


@dataclass(frozen=True, slots=True)
class PublishObligation:
    id: uuid.UUID
    batch_version_id: uuid.UUID
    sender_id: uuid.UUID
    recipient_id: uuid.UUID
    amount_vnd: int
    bank_bin: str
    account_number: str
    account_name: str | None


@dataclass(frozen=True, slots=True)
class BatchForPublish:
    id: uuid.UUID
    version_id: uuid.UUID
    owner_id: uuid.UUID
    status: str
    context_id: uuid.UUID
    advancer_acknowledged: bool
    bank_recipient_snapshot_valid: bool
    all_recipients_eligible: bool
    obligations: tuple[PublishObligation, ...]


@dataclass(frozen=True, slots=True)
class BatchObligationRow:
    """One obligation as the person collecting sees it.

    Status is derived, never stored -- including `disputed`, which is read
    back from the objection events rather than kept in a column that could
    drift from them.
    """

    obligation_id: uuid.UUID
    sender_id: uuid.UUID
    recipient_id: uuid.UUID
    amount_vnd: int
    #: Whether the money arrived. Says nothing about whether anyone agrees.
    status: str
    #: Whether an objection is open. A receipt does not close one, because
    #: the person confirming receipt is the person being objected to.
    disputed: bool
    disputed_reason: str | None
    #: When the sender said they had transferred it, or `None` if they never
    #: did. A CLAIM by one person, carried next to `status` and never folded
    #: into it: the guest page promises "waiting for NAM to confirm", and
    #: before this the board had nowhere to read that promise back from, so
    #: somebody who had done everything asked of them looked identical to
    #: somebody who had done nothing. It is not evidence from a bank, and no
    #: value here may ever move `status` -- that stays derived from
    #: `ReceiptConfirmation` alone.
    payment_reported_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class BatchBoard:
    """The collection board plus the context that owns it.

    `context_id` travels with the rows because the service cannot decide who
    may read them without it, and looking it up separately is how a caller
    forgets. Shipping the rows without it is exactly the mistake this type
    exists to make impossible.
    """

    context_id: uuid.UUID
    obligations: tuple[BatchObligationRow, ...]


@dataclass(frozen=True, slots=True)
class FinanceMovement:
    """One movement of money that actually happened, as this person sees it.

    Only receipt-confirmed obligations become movements. A `PaymentReport` --
    the sender saying they transferred -- is deliberately not one, for the same
    reason `obligation_status` refuses it: self-report is not arrival. A screen
    that counted reports would tell somebody their money came in because the
    other side said so.
    """

    obligation_id: uuid.UUID
    #: `out` when this person sent it, `in` when they collected it.
    direction: str
    #: Always positive. The sign belongs to `direction`, so a reader cannot
    #: lose it by formatting the number.
    amount_vnd: int
    counterparty_id: uuid.UUID
    counterparty_name: str | None
    context_id: uuid.UUID
    #: `None` when the group id on the batch has no `contexts` row behind it.
    #: That is a reachable state, not a broken one: the column is not a foreign
    #: key and the expense flow never creates the group it posts against.
    context_name: str | None
    #: What the money was for -- the description of the expense the obligation
    #: was built from. `None` when the sources carry no description.
    occasion: str | None
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class PersonFinanceSummary:
    """One person's standing, recomputed from the ledger on every read.

    Nothing here is cached and nothing is stored. That is invariant 3, and it
    is the whole reason this type exists rather than a `people.balance_vnd`
    column: a column would be a second answer to a question the ledger already
    answers, and the two would disagree the first time a write half-landed.

    `spend_vnd` is the person's own confirmed allocations -- what the meals
    cost *them*, not what anybody advanced. `outstanding_vnd` is the part of
    that they still owe somebody. `settled_vnd` is the remainder, and it is
    subtraction rather than its own query on purpose: the two figures on screen
    have to add up to the total above them, and deriving one of them from the
    other is the only way to guarantee that without a reconciliation step
    nobody would run.
    """

    person_id: uuid.UUID
    display_name: str | None
    spend_vnd: int
    settled_vnd: int
    outstanding_vnd: int
    #: Confirmed expenses this person appears in. A count, not money.
    expense_count: int
    #: Groups they are an accepted member of.
    group_count: int
    movements: tuple[FinanceMovement, ...]


@dataclass(frozen=True, slots=True)
class GuestLinkDraft:
    sender_id: uuid.UUID
    token_digest: bytes
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class StoredGuestLink:
    id: uuid.UUID
    envelope_id: uuid.UUID
    sender_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class GuestEnvelopeRecord:
    link_id: uuid.UUID
    envelope: dict


@dataclass(frozen=True, slots=True)
class PaymentReportTarget:
    link_id: uuid.UUID
    obligation_id: uuid.UUID
    amount_vnd: int
    active_capability: bool
    reports_used: int


@dataclass(frozen=True, slots=True)
class PaymentReportRecord:
    id: uuid.UUID
    obligation_id: uuid.UUID
    amount_vnd: int
    receipt_amounts_vnd: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ReceiptTarget:
    obligation_id: uuid.UUID
    recipient_id: uuid.UUID
    amount_vnd: int


@dataclass(frozen=True, slots=True)
class ReceiptRecord:
    id: uuid.UUID
    obligation_id: uuid.UUID
    amount_vnd: int
    receipt_amounts_vnd: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class BillShareRecord:
    participant_id: uuid.UUID
    source: str
    decided_by_id: uuid.UUID | None
    decided_at: datetime | None


@dataclass(frozen=True, slots=True)
class BillItemRecord:
    item_key: str
    name: str
    quantity: int
    unit_price_vnd: int | None
    line_total_vnd: int
    position: int
    shares: list[BillShareRecord]


# One code per bill-draft constraint a caller can actually trip. A Vietnamese
# bill repeats dish names constantly, so whoever mints these keys collides on
# the second "Bia Sài Gòn" line; the answer has to say which key repeated.
_BILL_WRITE_CONFLICTS = {
    "uq_bill_items_bill_item_key": "DUPLICATE_BILL_ITEM_KEY",
    "uq_bill_surcharges_bill_surcharge_key": "DUPLICATE_BILL_SURCHARGE_KEY",
    "uq_bill_discounts_bill_discount_key": "DUPLICATE_BILL_DISCOUNT_KEY",
}


@dataclass(frozen=True, slots=True)
class BillSurchargeRecord:
    surcharge_key: str
    kind: str
    amount_vnd: int
    mode: str


@dataclass(frozen=True, slots=True)
class BillDiscountRecord:
    discount_key: str
    amount_vnd: int
    scope: str
    target_item_key: str | None


@dataclass(frozen=True, slots=True)
class BillRecord:
    id: uuid.UUID
    context_id: uuid.UUID
    printed_total_vnd: int | None
    items_total_vnd: int
    confidence: int
    needs_review: bool
    created_by_id: uuid.UUID
    created_at: datetime
    items: list[BillItemRecord]
    surcharges: list[BillSurchargeRecord]
    discounts: list[BillDiscountRecord]


class ApiRepository(Protocol):
    def get_person(self, person_id: uuid.UUID) -> PersonRecord | None: ...

    def create_person(
        self, person_id: uuid.UUID, display_name: str
    ) -> PersonRecord: ...

    def rename_person(
        self, person_id: uuid.UUID, display_name: str
    ) -> PersonRecord | None: ...

    def create_context(
        self, display_name: str, created_by_id: uuid.UUID
    ) -> ContextRecord: ...

    def add_member(
        self,
        context_id: uuid.UUID,
        person_id: uuid.UUID,
        invited_by_id: uuid.UUID,
        *,
        role: str = "member",
    ) -> MembershipRecord: ...

    def accept_membership(
        self, membership_id: uuid.UUID, now: datetime
    ) -> MembershipRecord | None: ...

    def leave_context(
        self, context_id: uuid.UUID, person_id: uuid.UUID, now: datetime
    ) -> MembershipRecord | None: ...

    def list_members(self, context_id: uuid.UUID) -> list[MembershipRecord]: ...

    def is_member(self, context_id: uuid.UUID, person_id: uuid.UUID) -> bool: ...

    def membership_role(
        self, context_id: uuid.UUID, person_id: uuid.UUID
    ) -> str | None: ...

    def set_membership_role(
        self, context_id: uuid.UUID, person_id: uuid.UUID, role: str
    ) -> MembershipRecord | None: ...

    def create_message(
        self,
        *,
        context_id: uuid.UUID,
        author_id: uuid.UUID | None,
        kind: str,
        body: str | None,
        image_url: str | None,
        card: dict | None,
        now: datetime,
    ) -> MessageRecord: ...

    def list_messages(
        self,
        context_id: uuid.UUID,
        *,
        limit: int,
        before: tuple[datetime, uuid.UUID] | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> MessagePage: ...

    def create_expense(self, context_id: uuid.UUID) -> ExpenseIdentity: ...

    def get_expense(self, expense_id: uuid.UUID) -> ExpenseIdentity | None: ...

    def create_bill(
        self,
        *,
        context_id: uuid.UUID,
        created_by_id: uuid.UUID,
        printed_total_vnd: int | None,
        items_total_vnd: int,
        confidence: int,
        needs_review: bool,
        items: list[dict],
        surcharges: list[dict],
        discounts: list[dict],
        now: datetime,
    ) -> BillRecord: ...

    def get_bill(self, bill_id: uuid.UUID) -> BillRecord | None: ...

    def confirm_bill_assignments(
        self,
        *,
        bill_id: uuid.UUID,
        assignments: list[dict],
        decided_by_id: uuid.UUID,
        now: datetime,
    ) -> BillRecord: ...

    def save_expense_confirmation(
        self,
        *,
        expense_id: uuid.UUID,
        proposal: ExpenseInput,
        allocator_expense: dict,
        rollups: dict[str, int],
        allocations: dict[uuid.UUID, int],
        confirmed_by_id: uuid.UUID,
        payer_acknowledgement: str,
        now: datetime,
    ) -> ConfirmationRecord: ...

    def load_batch_inputs(
        self,
        context_id: uuid.UUID,
        expense_version_ids: tuple[uuid.UUID, ...] | None,
    ) -> BatchInputs: ...

    def load_confirmed_receipts(
        self, context_id: uuid.UUID
    ) -> dict[tuple[uuid.UUID, uuid.UUID], int]: ...

    def load_bank_recipients(
        self, recipient_ids: frozenset[uuid.UUID]
    ) -> dict[uuid.UUID, BankRecipientRecord]: ...

    def get_active_bank_recipient(
        self, recipient_id: uuid.UUID
    ) -> BankRecipientRecord | None: ...

    def save_bank_recipient(
        self,
        *,
        recipient_id: uuid.UUID,
        bank_bin: str,
        account_number: str,
        account_name: str | None,
        actor_id: uuid.UUID,
        now: datetime,
    ) -> tuple[BankRecipientRecord, bool]: ...

    def save_frozen_batch(
        self,
        *,
        context_id: uuid.UUID,
        owner_id: uuid.UUID,
        due_at: datetime,
        obligations: tuple[ObligationDraft, ...],
        bank_recipients: dict[uuid.UUID, BankRecipientRecord],
        now: datetime,
    ) -> FrozenBatch: ...

    def load_batch_for_publish(self, batch_id: uuid.UUID) -> BatchForPublish | None: ...

    def save_published_batch(
        self,
        *,
        batch: BatchForPublish,
        status: str,
        links: tuple[GuestLinkDraft, ...],
        actor_id: uuid.UUID,
        now: datetime,
    ) -> tuple[StoredGuestLink, ...]: ...

    def get_guest_envelope(
        self, token_digest: bytes, now: datetime
    ) -> GuestEnvelopeRecord | None: ...

    def get_payment_report_target(
        self, token_digest: bytes, obligation_id: uuid.UUID, now: datetime
    ) -> PaymentReportTarget | None: ...

    def save_payment_report(
        self,
        *,
        target: PaymentReportTarget,
        idempotency_key: uuid.UUID,
        now: datetime,
    ) -> PaymentReportRecord: ...

    def save_guest_objection(
        self,
        *,
        token_digest: bytes,
        kind: str,
        obligation_id: uuid.UUID | None,
        reason: str | None,
        now: datetime,
    ) -> None:
        """Record that a guest disagreed, and revoke the link for `not_me`.

        Stored as an audit event rather than a new table. An objection IS an
        audited fact -- who said what, about which obligation, when -- and the
        append-only guarantee is exactly what it needs. A dedicated table would
        have added a status column that could drift from the events.
        """
        ...

    def list_batch_obligations(self, batch_id: uuid.UUID) -> BatchBoard | None: ...

    def person_finance_summary(
        self, person_id: uuid.UUID, *, movement_limit: int
    ) -> PersonFinanceSummary: ...

    def get_receipt_target(self, obligation_id: uuid.UUID) -> ReceiptTarget | None: ...

    def save_receipt_confirmation(
        self,
        *,
        target: ReceiptTarget,
        confirmed_by_id: uuid.UUID,
        amount_vnd: int,
        payment_report_id: uuid.UUID | None,
        idempotency_key: uuid.UUID,
        now: datetime,
    ) -> ReceiptRecord: ...


def _bank_recipient(row: BankRecipient) -> BankRecipientRecord:
    return BankRecipientRecord(
        id=row.id,
        recipient_id=row.recipient_id,
        bank_bin=row.bank_bin,
        account_number=row.account_number,
        account_name=row.account_name,
        confirmed_at=row.confirmed_by_recipient_at,
    )


class SqlAlchemyApiRepository:
    """PostgreSQL implementation. One instance owns one request transaction."""

    # Section 8.6 caps objections so a leaked link cannot be used to bury

    # the recipient. Was hardcoded to zero while the two objection routes

    # did not exist, which made both buttons dead before they 404ed.

    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _membership_record(membership: Membership) -> MembershipRecord:
        return MembershipRecord(
            id=membership.id,
            context_id=membership.context_id,
            person_id=membership.person_id,
            state=membership.state.value,
            role=membership.role.value,
            invited_by_id=membership.invited_by_id,
            joined_at=membership.joined_at,
            left_at=membership.left_at,
            created_at=membership.created_at,
        )

    @staticmethod
    def _message_record(message: Message) -> MessageRecord:
        return MessageRecord(
            id=message.id,
            context_id=message.context_id,
            author_id=message.author_id,
            kind=message.kind.value,
            body=message.body,
            image_url=message.image_url,
            card=message.card,
            created_at=message.created_at,
        )

    @staticmethod
    def _person_record(person: Person) -> PersonRecord:
        return PersonRecord(
            id=person.id,
            display_name=person.display_name,
            created_at=person.created_at,
        )

    @staticmethod
    def _bill_share_record(share: BillItemShare) -> BillShareRecord:
        return BillShareRecord(
            participant_id=share.participant_id,
            source=share.source.value,
            decided_by_id=share.decided_by_id,
            decided_at=share.decided_at,
        )

    def _bill_record(self, bill: Bill) -> BillRecord:
        item_rows = list(
            self.session.scalars(
                select(BillItem)
                .where(BillItem.bill_id == bill.id)
                .order_by(BillItem.position, BillItem.item_key)
            )
        )
        shares_by_item: dict[uuid.UUID, list[BillShareRecord]] = {
            item.id: [] for item in item_rows
        }
        if item_rows:
            share_rows = self.session.scalars(
                select(BillItemShare)
                .where(
                    BillItemShare.bill_item_id.in_(
                        [item.id for item in item_rows]
                    )
                )
                .order_by(
                    BillItemShare.bill_item_id,
                    BillItemShare.participant_id,
                )
            )
            for share in share_rows:
                shares_by_item[share.bill_item_id].append(
                    self._bill_share_record(share)
                )

        surcharge_rows = list(
            self.session.scalars(
                select(BillSurcharge)
                .where(BillSurcharge.bill_id == bill.id)
                .order_by(BillSurcharge.surcharge_key)
            )
        )
        discount_rows = list(
            self.session.scalars(
                select(BillDiscount)
                .where(BillDiscount.bill_id == bill.id)
                .order_by(BillDiscount.discount_key)
            )
        )

        return BillRecord(
            id=bill.id,
            context_id=bill.context_id,
            printed_total_vnd=bill.printed_total_vnd,
            items_total_vnd=bill.items_total_vnd,
            confidence=bill.confidence,
            needs_review=bill.needs_review,
            created_by_id=bill.created_by_id,
            created_at=bill.created_at,
            items=[
                BillItemRecord(
                    item_key=item.item_key,
                    name=item.name,
                    quantity=item.quantity,
                    unit_price_vnd=item.unit_price_vnd,
                    line_total_vnd=item.line_total_vnd,
                    position=item.position,
                    shares=shares_by_item[item.id],
                )
                for item in item_rows
            ],
            surcharges=[
                BillSurchargeRecord(
                    surcharge_key=surcharge.surcharge_key,
                    kind=surcharge.kind,
                    amount_vnd=surcharge.amount_vnd,
                    mode=surcharge.mode.value,
                )
                for surcharge in surcharge_rows
            ],
            discounts=[
                BillDiscountRecord(
                    discount_key=discount.discount_key,
                    amount_vnd=discount.amount_vnd,
                    scope=discount.scope.value,
                    target_item_key=discount.target_item_key,
                )
                for discount in discount_rows
            ],
        )

    def get_person(self, person_id: uuid.UUID) -> PersonRecord | None:
        person = self.session.get(Person, person_id)
        return None if person is None else self._person_record(person)

    def _display_names(self, person_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        """Names for these ids, falling back to the id itself.

        The fallback is deliberately still an id and deliberately not a
        friendly placeholder. "Thành viên" would make two different unnamed
        people read as one person, on the single screen whose job is telling
        them apart -- and it would do it silently, which is worse than ugly.
        """
        if not person_ids:
            return {}
        found = {
            person_id: display_name
            for person_id, display_name in self.session.execute(
                select(Person.id, Person.display_name).where(
                    Person.id.in_(person_ids)
                )
            )
        }
        return {
            person_id: found.get(person_id) or str(person_id)
            for person_id in person_ids
        }

    def create_person(self, person_id: uuid.UUID, display_name: str) -> PersonRecord:
        # The id comes from the caller because the rest of the system already
        # uses it: participants, obligations and envelopes all carry ids minted
        # before anybody typed a name. Minting a second id here would leave the
        # name attached to a person no expense refers to.
        person = Person(id=person_id, display_name=display_name)
        try:
            with self.session.begin_nested():
                self.session.add(person)
                self.session.flush()
        except IntegrityError as exc:
            # Two devices naming the same friend at once. The loser is told so
            # rather than overwriting a name it never read.
            raise RepositoryConflict("PERSON_ALREADY_EXISTS") from exc
        return self._person_record(person)

    def rename_person(
        self, person_id: uuid.UUID, display_name: str
    ) -> PersonRecord | None:
        person = self.session.get(Person, person_id, with_for_update=True)
        if person is None:
            return None
        person.display_name = display_name
        self.session.flush()
        return self._person_record(person)

    def create_context(
        self, display_name: str, created_by_id: uuid.UUID
    ) -> ContextRecord:
        context = Context(display_name=display_name, created_by_id=created_by_id)
        self.session.add(context)
        self.session.flush()
        return ContextRecord(
            id=context.id,
            display_name=context.display_name,
            created_by_id=context.created_by_id,
            created_at=context.created_at,
        )

    def add_member(
        self,
        context_id: uuid.UUID,
        person_id: uuid.UUID,
        invited_by_id: uuid.UUID,
        *,
        role: str = "member",
    ) -> MembershipRecord:
        # Always insert. Rejoining is a new membership period; reviving the old
        # row would silently backdate what the person was allowed to see.
        membership = Membership(
            context_id=context_id,
            person_id=person_id,
            state=MembershipState.INVITED,
            role=MembershipRole(role),
            invited_by_id=invited_by_id,
        )
        try:
            with self.session.begin_nested():
                self.session.add(membership)
                self.session.flush()
        except IntegrityError as exc:
            constraint = getattr(
                getattr(exc.orig, "diag", None), "constraint_name", None
            )
            if constraint == "uq_memberships_open_per_person":
                raise RepositoryConflict("MEMBERSHIP_ALREADY_OPEN") from exc
            raise
        return self._membership_record(membership)

    def accept_membership(
        self, membership_id: uuid.UUID, now: datetime
    ) -> MembershipRecord | None:
        membership = self.session.scalar(
            select(Membership).where(Membership.id == membership_id).with_for_update()
        )
        if membership is None:
            return None
        if membership.state is not MembershipState.INVITED:
            raise RepositoryConflict("MEMBERSHIP_NOT_INVITED")
        membership.state = MembershipState.ACTIVE
        membership.joined_at = now
        self.session.flush()
        return self._membership_record(membership)

    def leave_context(
        self, context_id: uuid.UUID, person_id: uuid.UUID, now: datetime
    ) -> MembershipRecord | None:
        membership = self.session.scalar(
            select(Membership)
            .where(
                Membership.context_id == context_id,
                Membership.person_id == person_id,
                Membership.state == MembershipState.ACTIVE,
                Membership.left_at.is_(None),
            )
            .with_for_update()
        )
        if membership is None:
            return None
        # The database check constraint requires these two facts to move
        # together; neither an open LEFT row nor a dated ACTIVE row is valid.
        membership.state = MembershipState.LEFT
        membership.left_at = now
        self.session.flush()
        return self._membership_record(membership)

    def list_members(self, context_id: uuid.UUID) -> list[MembershipRecord]:
        memberships = self.session.scalars(
            select(Membership)
            .where(
                Membership.context_id == context_id,
                Membership.left_at.is_(None),
            )
            .order_by(Membership.created_at, Membership.id)
        )
        return [self._membership_record(membership) for membership in memberships]

    def is_member(self, context_id: uuid.UUID, person_id: uuid.UUID) -> bool:
        return (
            self.session.scalar(
                select(Membership.id)
                .where(
                    Membership.context_id == context_id,
                    Membership.person_id == person_id,
                    Membership.state == MembershipState.ACTIVE,
                    Membership.left_at.is_(None),
                )
                .limit(1)
            )
            is not None
        )

    def membership_role(
        self, context_id: uuid.UUID, person_id: uuid.UUID
    ) -> str | None:
        role = self.session.scalar(
            select(Membership.role)
            .where(
                Membership.context_id == context_id,
                Membership.person_id == person_id,
                Membership.state == MembershipState.ACTIVE,
                Membership.left_at.is_(None),
            )
            .limit(1)
        )
        return None if role is None else role.value

    def set_membership_role(
        self, context_id: uuid.UUID, person_id: uuid.UUID, role: str
    ) -> MembershipRecord | None:
        membership = self.session.scalar(
            select(Membership)
            .where(
                Membership.context_id == context_id,
                Membership.person_id == person_id,
                Membership.state == MembershipState.ACTIVE,
                Membership.left_at.is_(None),
            )
            .with_for_update()
        )
        if membership is None:
            return None
        membership.role = MembershipRole(role)
        self.session.flush()
        return self._membership_record(membership)

    def create_message(
        self,
        *,
        context_id: uuid.UUID,
        author_id: uuid.UUID | None,
        kind: str,
        body: str | None,
        image_url: str | None,
        card: dict | None,
        now: datetime,
    ) -> MessageRecord:
        message = Message(
            context_id=context_id,
            author_id=author_id,
            kind=MessageKind(kind),
            body=body,
            image_url=image_url,
            card=card,
            created_at=now,
        )
        self.session.add(message)
        self.session.flush()
        return self._message_record(message)

    def list_messages(
        self,
        context_id: uuid.UUID,
        *,
        limit: int,
        before: tuple[datetime, uuid.UUID] | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> MessagePage:
        statement = select(Message).where(Message.context_id == context_id)
        if before is not None:
            statement = statement.where(
                tuple_(Message.created_at, Message.id) < tuple_(*before)
            ).order_by(Message.created_at.desc(), Message.id.desc())
        elif after is not None:
            statement = statement.where(
                tuple_(Message.created_at, Message.id) > tuple_(*after)
            ).order_by(Message.created_at.asc(), Message.id.asc())
        else:
            statement = statement.order_by(
                Message.created_at.desc(), Message.id.desc()
            )

        rows = list(self.session.scalars(statement.limit(limit + 1)))
        has_more = len(rows) > limit
        return MessagePage(
            messages=tuple(self._message_record(row) for row in rows[:limit]),
            has_more=has_more,
        )
    def create_bill(
        self,
        *,
        context_id: uuid.UUID,
        created_by_id: uuid.UUID,
        printed_total_vnd: int | None,
        items_total_vnd: int,
        confidence: int,
        needs_review: bool,
        items: list[dict],
        surcharges: list[dict],
        discounts: list[dict],
        now: datetime,
    ) -> BillRecord:
        try:
            with self.session.begin_nested():
                bill = Bill(
                    context_id=context_id,
                    created_by_id=created_by_id,
                    printed_total_vnd=printed_total_vnd,
                    items_total_vnd=items_total_vnd,
                    confidence=confidence,
                    needs_review=needs_review,
                    created_at=now,
                )
                self.session.add(bill)
                self.session.flush()

                item_models: list[tuple[dict, BillItem]] = []
                for item in items:
                    model = BillItem(
                        bill_id=bill.id,
                        item_key=item["item_key"],
                        name=item["name"],
                        quantity=item["quantity"],
                        unit_price_vnd=item["unit_price_vnd"],
                        line_total_vnd=item["line_total_vnd"],
                        position=item["position"],
                    )
                    self.session.add(model)
                    item_models.append((item, model))
                self.session.flush()

                for item, model in item_models:
                    for participant_id in item["suggested_participant_ids"]:
                        self.session.add(
                            BillItemShare(
                                bill_item_id=model.id,
                                participant_id=participant_id,
                                source=BillShareSource.AI_SUGGESTED,
                                decided_by_id=None,
                                decided_at=None,
                            )
                        )
                for surcharge in surcharges:
                    self.session.add(
                        BillSurcharge(
                            bill_id=bill.id,
                            surcharge_key=surcharge["surcharge_key"],
                            kind=surcharge["kind"],
                            amount_vnd=surcharge["amount_vnd"],
                            mode=surcharge["mode"],
                        )
                    )
                for discount in discounts:
                    self.session.add(
                        BillDiscount(
                            bill_id=bill.id,
                            discount_key=discount["discount_key"],
                            amount_vnd=discount["amount_vnd"],
                            scope=discount["scope"],
                            target_item_key=discount["target_item_key"],
                        )
                    )
                self.session.flush()
        except IntegrityError as exc:
            constraint = getattr(
                getattr(exc.orig, "diag", None), "constraint_name", None
            )
            # Fail closed. Naming each constraint gives the caller something
            # it can act on, but a name list is a list somebody has to
            # remember to extend, and the constraint added next would go back
            # to escaping as a raw database error -- which is the 500 this
            # translation exists to stop. The default is a conflict, and the
            # psycopg DETAIL line (it carries the bill id and the raw
            # constraint name) never reaches the caller either way.
            raise RepositoryConflict(
                _BILL_WRITE_CONFLICTS.get(constraint, "BILL_WRITE_CONFLICT")
            ) from exc
        return self._bill_record(bill)

    def get_bill(self, bill_id: uuid.UUID) -> BillRecord | None:
        bill = self.session.get(Bill, bill_id)
        return None if bill is None else self._bill_record(bill)

    def confirm_bill_assignments(
        self,
        *,
        bill_id: uuid.UUID,
        assignments: list[dict],
        decided_by_id: uuid.UUID,
        now: datetime,
    ) -> BillRecord:
        bill = self.session.scalar(
            select(Bill).where(Bill.id == bill_id).with_for_update()
        )
        if bill is None:
            raise RepositoryConflict("BILL_NOT_FOUND")

        item_rows = list(
            self.session.scalars(
                select(BillItem)
                .where(BillItem.bill_id == bill_id)
                .with_for_update()
            )
        )
        items_by_key = {item.item_key: item for item in item_rows}
        assignments_by_key = {
            assignment["item_key"]: assignment for assignment in assignments
        }
        if set(assignments_by_key) - set(items_by_key):
            raise RepositoryConflict("UNKNOWN_BILL_ITEM")

        target_item_ids = [
            items_by_key[item_key].id for item_key in assignments_by_key
        ]
        if target_item_ids:
            existing_shares = self.session.scalars(
                select(BillItemShare)
                .where(BillItemShare.bill_item_id.in_(target_item_ids))
                .with_for_update()
            )
            for share in existing_shares:
                self.session.delete(share)
            self.session.flush()

        for item_key, assignment in assignments_by_key.items():
            item = items_by_key[item_key]
            for participant_id in assignment["participant_ids"]:
                self.session.add(
                    BillItemShare(
                        bill_item_id=item.id,
                        participant_id=participant_id,
                        source=BillShareSource.CONFIRMED,
                        decided_by_id=decided_by_id,
                        decided_at=now,
                    )
                )
        self.session.flush()
        return self._bill_record(bill)

    def create_expense(self, context_id: uuid.UUID) -> ExpenseIdentity:
        expense = Expense(context_id=context_id)
        self.session.add(expense)
        self.session.flush()
        return ExpenseIdentity(id=expense.id, context_id=expense.context_id)

    def get_expense(self, expense_id: uuid.UUID) -> ExpenseIdentity | None:
        expense = self.session.scalar(
            select(Expense).where(Expense.id == expense_id).with_for_update()
        )
        if expense is None:
            return None
        return ExpenseIdentity(id=expense.id, context_id=expense.context_id)

    def save_expense_confirmation(
        self,
        *,
        expense_id: uuid.UUID,
        proposal: ExpenseInput,
        allocator_expense: dict,
        rollups: dict[str, int],
        allocations: dict[uuid.UUID, int],
        confirmed_by_id: uuid.UUID,
        payer_acknowledgement: str,
        now: datetime,
    ) -> ConfirmationRecord:
        # Lock the stable identity so concurrent confirmations cannot both pick
        # the same version number.
        expense = self.session.scalar(
            select(Expense).where(Expense.id == expense_id).with_for_update()
        )
        if expense is None:
            raise RepositoryConflict("EXPENSE_NOT_FOUND")

        latest = self.session.scalar(
            select(func.max(ExpenseVersion.version_number)).where(
                ExpenseVersion.expense_id == expense_id
            )
        )
        version_number = (latest or 0) + 1
        version = ExpenseVersion(
            expense_id=expense_id,
            version_number=version_number,
            previous_version_number=latest,
            description=proposal.description,
            recorded_by_id=proposal.recorded_by_id,
            paid_by_id=proposal.paid_by_id,
            payer_acknowledgement=PayerAcknowledgement(payer_acknowledgement),
            verification_scope=VerificationScope(proposal.verification_scope),
            occurred_at=proposal.occurred_at,
            created_at=now,
            **rollups,
        )
        self.session.add(version)
        self.session.flush()

        item_models: dict[str, ExpenseItem] = {}
        for item in proposal.items:
            model = ExpenseItem(
                expense_version_id=version.id,
                item_key=item.item_id,
                label=item.label,
                amount_vnd=item.amount_vnd,
            )
            self.session.add(model)
            item_models[item.item_id] = model
        self.session.flush()

        for item in proposal.items:
            model = item_models[item.item_id]
            for participant_id in item.shared_by:
                self.session.add(
                    ExpenseItemShare(
                        expense_item_id=model.id,
                        participant_id=participant_id,
                    )
                )
        for surcharge in proposal.surcharges:
            self.session.add(
                ExpenseSurcharge(
                    expense_version_id=version.id,
                    surcharge_key=surcharge.surcharge_id,
                    kind=surcharge.kind,
                    amount_vnd=surcharge.amount_vnd,
                    mode=surcharge.mode,
                )
            )
        for discount in proposal.discounts:
            target = (
                item_models.get(discount.item_id)
                if discount.item_id is not None
                else None
            )
            self.session.add(
                ExpenseDiscount(
                    expense_version_id=version.id,
                    discount_key=discount.discount_id,
                    amount_vnd=discount.amount_vnd,
                    scope=discount.scope,
                    target_item_id=target.id if target is not None else None,
                )
            )
        for participant_id, amount_vnd in sorted(
            allocations.items(), key=lambda item: item[0].bytes
        ):
            self.session.add(
                ConfirmedAllocation(
                    expense_version_id=version.id,
                    participant_id=participant_id,
                    amount_vnd=amount_vnd,
                    confirmed_by_id=confirmed_by_id,
                    confirmed_at=now,
                )
            )
        self.session.add(
            AuditEvent(
                actor_id=confirmed_by_id,
                event_type="expense_confirmed",
                aggregate_type="expense",
                aggregate_id=expense_id,
                event_data={
                    "expense_version_id": str(version.id),
                    "version_number": version_number,
                    "allocator_warnings": allocator_expense.get("warnings", []),
                },
                occurred_at=now,
            )
        )
        self.session.flush()
        return ConfirmationRecord(
            expense_version_id=version.id,
            version_number=version_number,
        )

    def load_batch_inputs(
        self,
        context_id: uuid.UUID,
        expense_version_ids: tuple[uuid.UUID, ...] | None,
    ) -> BatchInputs:
        """Load latest confirmed expenses, optionally enforcing batch availability.

        ``None`` is the read model used by group balances and therefore includes
        expenses already placed in a collection batch. A concrete tuple is the
        batch-creation path and excludes any allocation already used as a source.
        """
        latest = (
            select(
                ExpenseVersion.expense_id.label("expense_id"),
                func.max(ExpenseVersion.version_number).label("version_number"),
            )
            .group_by(ExpenseVersion.expense_id)
            .subquery()
        )
        statement = (
            select(ExpenseVersion)
            .join(Expense, Expense.id == ExpenseVersion.expense_id)
            .join(
                latest,
                (latest.c.expense_id == ExpenseVersion.expense_id)
                & (latest.c.version_number == ExpenseVersion.version_number),
            )
            .where(Expense.context_id == context_id)
            .order_by(ExpenseVersion.id)
            # The query joins a grouped subquery to select the latest version.
            # PostgreSQL cannot apply an unqualified locking clause to an
            # aggregate result because those rows do not map one-to-one to
            # physical rows. Only the material version rows need locking here.
            .with_for_update(of=ExpenseVersion)
        )
        if expense_version_ids is not None:
            statement = statement.where(ExpenseVersion.id.in_(expense_version_ids))
        versions = tuple(self.session.scalars(statement))

        available: list[ConfirmedExpense] = []
        unavailable = set(expense_version_ids or ()) - {
            version.id for version in versions
        }
        for version in versions:
            rows = tuple(
                self.session.scalars(
                    select(ConfirmedAllocation)
                    .where(ConfirmedAllocation.expense_version_id == version.id)
                    .order_by(ConfirmedAllocation.participant_id)
                    .with_for_update()
                )
            )
            if not rows:
                unavailable.add(version.id)
                continue
            source_ids: set[uuid.UUID] = set()
            if expense_version_ids is not None:
                collectable = tuple(
                    row
                    for row in rows
                    if row.participant_id != version.paid_by_id and row.amount_vnd > 0
                )
                source_ids = set(
                    self.session.scalars(
                        select(
                            CollectionObligationSource.confirmed_allocation_id
                        ).where(
                            CollectionObligationSource.confirmed_allocation_id.in_(
                                [row.id for row in collectable]
                            )
                        )
                    )
                )
            if source_ids:
                unavailable.add(version.id)
                continue
            available.append(
                ConfirmedExpense(
                    version_id=version.id,
                    context_id=context_id,
                    paid_by_id=version.paid_by_id,
                    payer_acknowledgement=version.payer_acknowledgement.value,
                    allocations=tuple(
                        AllocationRow(
                            id=row.id,
                            participant_id=row.participant_id,
                            amount_vnd=row.amount_vnd,
                        )
                        for row in rows
                    ),
                )
            )
        return BatchInputs(
            expenses=tuple(available),
            unavailable_version_ids=tuple(
                sorted(unavailable, key=lambda value: value.bytes)
            ),
        )

    def load_confirmed_receipts(
        self, context_id: uuid.UUID
    ) -> dict[tuple[uuid.UUID, uuid.UUID], int]:
        """Sum recipient-confirmed receipt events for batches in one context."""

        rows = self.session.execute(
            select(
                CollectionObligation.sender_id,
                CollectionObligation.recipient_id,
                func.sum(ReceiptConfirmation.amount_vnd),
            )
            .join(
                ReceiptConfirmation,
                ReceiptConfirmation.obligation_id == CollectionObligation.id,
            )
            .join(
                CollectionBatchVersion,
                CollectionBatchVersion.id == CollectionObligation.batch_version_id,
            )
            .join(
                CollectionBatch,
                CollectionBatch.id == CollectionBatchVersion.batch_id,
            )
            .where(
                CollectionBatch.context_id == context_id,
                ReceiptConfirmation.confirmed_by_id
                == CollectionObligation.recipient_id,
            )
            .group_by(
                CollectionObligation.sender_id,
                CollectionObligation.recipient_id,
            )
            .order_by(
                CollectionObligation.sender_id,
                CollectionObligation.recipient_id,
            )
        )
        return {
            (sender_id, recipient_id): int(confirmed_amount_vnd)
            for sender_id, recipient_id, confirmed_amount_vnd in rows
        }

    def load_bank_recipients(
        self, recipient_ids: frozenset[uuid.UUID]
    ) -> dict[uuid.UUID, BankRecipientRecord]:
        if not recipient_ids:
            return {}
        recipients = self.session.scalars(
            select(BankRecipient)
            .where(
                BankRecipient.recipient_id.in_(recipient_ids),
                BankRecipient.revoked_at.is_(None),
            )
            .with_for_update()
        )
        return {row.recipient_id: _bank_recipient(row) for row in recipients}

    def get_active_bank_recipient(
        self, recipient_id: uuid.UUID
    ) -> BankRecipientRecord | None:
        row = self._active_bank_recipient(recipient_id)
        return None if row is None else _bank_recipient(row)

    def save_bank_recipient(
        self,
        *,
        recipient_id: uuid.UUID,
        bank_bin: str,
        account_number: str,
        account_name: str | None,
        actor_id: uuid.UUID,
        now: datetime,
    ) -> tuple[BankRecipientRecord, bool]:
        """Register a destination, returning it and whether anything changed.

        The flag is not a convenience. Section 8.5 makes adding or changing a
        destination a material event that has to be audited and told to the
        affected parties; a retry that re-sends the same digits changed nothing
        and must not fire that.
        """

        current = self._active_bank_recipient(recipient_id)
        if current is not None and (
            current.bank_bin == bank_bin
            and current.account_number == account_number
            and current.account_name == account_name
        ):
            return _bank_recipient(current), False

        if current is not None:
            # `uq_bank_recipients_active_recipient` is a partial unique index
            # over `revoked_at IS NULL`, so the revocation has to reach the
            # table before the replacement row does; inserting first raises
            # UniqueViolation and loses the whole request.
            #
            # SQLAlchemy's unit of work happens to emit this UPDATE before the
            # INSERT below even without the explicit flush -- verified by
            # removing it and watching the PostgreSQL tests stay green. The
            # flush stays anyway: that ordering is an internal detail of the
            # unit of work, and a money invariant should not rest on one.
            #
            # Revoked, not deleted. This row is what an already published
            # envelope was frozen from, and the audit has to be able to explain
            # that envelope long after the account behind it changed.
            current.revoked_at = now
            self.session.flush()

        row = BankRecipient(
            recipient_id=recipient_id,
            bank_bin=bank_bin,
            account_number=account_number,
            account_name=account_name,
            confirmed_by_recipient_at=now,
            created_at=now,
        )
        self.session.add(row)
        self.session.flush()
        self.session.add(
            AuditEvent(
                actor_id=actor_id,
                event_type="bank_recipient_confirmed_by_recipient",
                aggregate_type="bank_recipient",
                aggregate_id=row.id,
                event_data={
                    # Deliberately no account number and no holder name. An
                    # audit row is read far more widely than the table it
                    # describes; the number already lives in `bank_recipients`,
                    # and copying it into a JSONB blob that every audit query
                    # scans spreads it for nothing.
                    "recipient_id": str(recipient_id),
                    "bank_bin": bank_bin,
                    "replaced_bank_recipient_id": (
                        str(current.id) if current is not None else None
                    ),
                },
                occurred_at=now,
            )
        )
        self.session.flush()
        return _bank_recipient(row), True

    def _active_bank_recipient(self, recipient_id: uuid.UUID) -> BankRecipient | None:
        return self.session.scalar(
            select(BankRecipient)
            .where(
                BankRecipient.recipient_id == recipient_id,
                BankRecipient.revoked_at.is_(None),
            )
            .with_for_update()
        )

    def save_frozen_batch(
        self,
        *,
        context_id: uuid.UUID,
        owner_id: uuid.UUID,
        due_at: datetime,
        obligations: tuple[ObligationDraft, ...],
        bank_recipients: dict[uuid.UUID, BankRecipientRecord],
        now: datetime,
    ) -> FrozenBatch:
        batch = CollectionBatch(
            context_id=context_id,
            owner_id=owner_id,
            status=CollectionBatchStatus.FROZEN,
            created_at=now,
            frozen_at=now,
        )
        self.session.add(batch)
        self.session.flush()
        version = CollectionBatchVersion(
            batch_id=batch.id,
            version_number=1,
            previous_version_number=None,
            created_by_id=owner_id,
            created_at=now,
        )
        self.session.add(version)
        self.session.flush()

        snapshots: dict[uuid.UUID, BankRecipientSnapshot] = {}
        for recipient_id in sorted(bank_recipients, key=lambda value: value.bytes):
            recipient = bank_recipients[recipient_id]
            snapshot = BankRecipientSnapshot(
                batch_version_id=version.id,
                bank_recipient_id=recipient.id,
                recipient_id=recipient.recipient_id,
                bank_bin=recipient.bank_bin,
                account_number=recipient.account_number,
                account_name=recipient.account_name,
                confirmed_by_recipient_at=recipient.confirmed_at,
                snapshotted_at=now,
            )
            self.session.add(snapshot)
            snapshots[recipient_id] = snapshot
        self.session.flush()

        stored: list[FrozenObligation] = []
        for draft in obligations:
            obligation = CollectionObligation(
                batch_version_id=version.id,
                sender_id=draft.sender_id,
                recipient_id=draft.recipient_id,
                amount_vnd=draft.amount_vnd,
                due_at=due_at,
                bank_recipient_snapshot_id=snapshots[draft.recipient_id].id,
                created_at=now,
            )
            self.session.add(obligation)
            self.session.flush()
            for source in draft.sources:
                self.session.add(
                    CollectionObligationSource(
                        obligation_id=obligation.id,
                        confirmed_allocation_id=source.id,
                        amount_vnd=source.amount_vnd,
                        created_at=now,
                    )
                )
            stored.append(
                FrozenObligation(
                    id=obligation.id,
                    sender_id=draft.sender_id,
                    recipient_id=draft.recipient_id,
                    amount_vnd=draft.amount_vnd,
                    due_at=due_at,
                    source_expense_version_ids=draft.source_expense_version_ids,
                )
            )
        self.session.add(
            AuditEvent(
                actor_id=owner_id,
                event_type="collection_batch_frozen",
                aggregate_type="collection_batch",
                aggregate_id=batch.id,
                event_data={
                    "batch_version_id": str(version.id),
                    "obligation_count": len(stored),
                },
                occurred_at=now,
            )
        )
        self.session.flush()
        return FrozenBatch(
            id=batch.id, version_id=version.id, obligations=tuple(stored)
        )

    def load_batch_for_publish(self, batch_id: uuid.UUID) -> BatchForPublish | None:
        batch = self.session.scalar(
            select(CollectionBatch)
            .where(CollectionBatch.id == batch_id)
            .with_for_update()
        )
        if batch is None:
            return None
        version = self.session.scalar(
            select(CollectionBatchVersion)
            .where(CollectionBatchVersion.batch_id == batch_id)
            .order_by(CollectionBatchVersion.version_number.desc())
            .limit(1)
        )
        if version is None:
            raise RepositoryConflict("BATCH_HAS_NO_VERSION")

        obligation_models = tuple(
            self.session.scalars(
                select(CollectionObligation)
                .where(CollectionObligation.batch_version_id == version.id)
                .order_by(
                    CollectionObligation.sender_id,
                    CollectionObligation.recipient_id,
                )
            )
        )
        snapshots = {
            row.id: row
            for row in self.session.scalars(
                select(BankRecipientSnapshot).where(
                    BankRecipientSnapshot.batch_version_id == version.id
                )
            )
        }
        expense_versions = tuple(
            self.session.scalars(
                select(ExpenseVersion)
                .join(
                    ConfirmedAllocation,
                    ConfirmedAllocation.expense_version_id == ExpenseVersion.id,
                )
                .join(
                    CollectionObligationSource,
                    CollectionObligationSource.confirmed_allocation_id
                    == ConfirmedAllocation.id,
                )
                .join(
                    CollectionObligation,
                    CollectionObligation.id == CollectionObligationSource.obligation_id,
                )
                .where(CollectionObligation.batch_version_id == version.id)
            )
        )
        unique_expense_versions = {row.id: row for row in expense_versions}.values()
        advancer_acknowledged = bool(expense_versions) and all(
            row.payer_acknowledgement == PayerAcknowledgement.ACKNOWLEDGED
            for row in unique_expense_versions
        )
        bank_valid = bool(obligation_models) and all(
            obligation.bank_recipient_snapshot_id in snapshots
            and snapshots[
                obligation.bank_recipient_snapshot_id
            ].confirmed_by_recipient_at
            is not None
            for obligation in obligation_models
        )
        obligations = tuple(
            PublishObligation(
                id=obligation.id,
                batch_version_id=version.id,
                sender_id=obligation.sender_id,
                recipient_id=obligation.recipient_id,
                amount_vnd=obligation.amount_vnd,
                bank_bin=snapshots[obligation.bank_recipient_snapshot_id].bank_bin,
                account_number=snapshots[
                    obligation.bank_recipient_snapshot_id
                ].account_number,
                account_name=snapshots[
                    obligation.bank_recipient_snapshot_id
                ].account_name,
            )
            for obligation in obligation_models
        )
        return BatchForPublish(
            id=batch.id,
            version_id=version.id,
            owner_id=batch.owner_id,
            status=batch.status.value,
            context_id=batch.context_id,
            advancer_acknowledged=advancer_acknowledged,
            bank_recipient_snapshot_valid=bank_valid,
            # Identity-claim tables are not part of the merged schema yet. An
            # active recipient-confirmed snapshot is the strongest available
            # eligibility fact; the journal records this limitation.
            all_recipients_eligible=bank_valid,
            obligations=obligations,
        )

    def save_published_batch(
        self,
        *,
        batch: BatchForPublish,
        status: str,
        links: tuple[GuestLinkDraft, ...],
        actor_id: uuid.UUID,
        now: datetime,
    ) -> tuple[StoredGuestLink, ...]:
        model = self.session.get(CollectionBatch, batch.id)
        if model is None:
            raise RepositoryConflict("BATCH_NOT_FOUND")
        model.status = CollectionBatchStatus(status)
        model.published_at = now

        stored: list[StoredGuestLink] = []
        for draft in links:
            envelope = CollectionEnvelope(
                batch_version_id=batch.version_id,
                sender_id=draft.sender_id,
                created_at=now,
            )
            self.session.add(envelope)
            self.session.flush()
            link = GuestLink(
                envelope_id=envelope.id,
                token_digest=draft.token_digest,
                status=GuestLinkStatus.ACTIVE,
                expires_at=draft.expires_at,
                created_at=now,
            )
            self.session.add(link)
            self.session.flush()
            stored.append(
                StoredGuestLink(
                    id=link.id,
                    envelope_id=envelope.id,
                    sender_id=draft.sender_id,
                )
            )
        self.session.add(
            AuditEvent(
                actor_id=actor_id,
                event_type="collection_batch_published",
                aggregate_type="collection_batch",
                aggregate_id=batch.id,
                event_data={
                    "batch_version_id": str(batch.version_id),
                    "guest_link_count": len(stored),
                },
                occurred_at=now,
            )
        )
        self.session.flush()
        return tuple(stored)

    def get_guest_envelope(
        self, token_digest: bytes, now: datetime
    ) -> GuestEnvelopeRecord | None:
        row = self.session.execute(
            select(
                GuestLink, CollectionEnvelope, CollectionBatchVersion, CollectionBatch
            )
            .join(CollectionEnvelope, CollectionEnvelope.id == GuestLink.envelope_id)
            .join(
                CollectionBatchVersion,
                CollectionBatchVersion.id == CollectionEnvelope.batch_version_id,
            )
            .join(
                CollectionBatch, CollectionBatch.id == CollectionBatchVersion.batch_id
            )
            .where(GuestLink.token_digest == token_digest)
            .with_for_update()
        ).one_or_none()
        if row is None:
            return None
        link, envelope, batch_version, batch = row
        if link.first_opened_at is None:
            link.first_opened_at = now

        state = link.status.value
        if state == GuestLinkStatus.ACTIVE.value and now >= link.expires_at:
            state = GuestLinkStatus.EXPIRED.value
            link.status = GuestLinkStatus.EXPIRED

        obligations = tuple(
            self.session.scalars(
                select(CollectionObligation)
                .where(
                    CollectionObligation.batch_version_id == envelope.batch_version_id,
                    CollectionObligation.sender_id == envelope.sender_id,
                )
                .order_by(CollectionObligation.recipient_id)
            )
        )
        capability_scope(
            {
                "batch_version_id": envelope.batch_version_id,
                "sender_id": envelope.sender_id,
            },
            [
                {
                    "obligation_id": obligation.id,
                    "batch_version_id": obligation.batch_version_id,
                    "sender_id": obligation.sender_id,
                }
                for obligation in obligations
            ],
        )

        # Asking for the calculation is stored as an audit event, same as an
        # objection. Without reading it back the page offered the button
        # forever and never acknowledged the ask.
        evidence_asked = {
            str(row["obligation_id"])
            for row in self.session.scalars(
                select(AuditEvent.event_data).where(
                    AuditEvent.aggregate_type == "guest_link",
                    AuditEvent.aggregate_id == link.id,
                    AuditEvent.event_type == "guest_objection.evidence_request",
                )
            )
            if row.get("obligation_id")
        }
        # Section 8.2. "This amount is wrong" stops collection on THAT
        # obligation and nothing else. It was only ever written to the audit
        # log, so the page could tell a guest their objection was recorded
        # while every collection path carried on as if nothing had happened.
        # Reading it back here is what turns a stored event into a state.
        disputed_ids = {
            str(row["obligation_id"])
            for row in self.session.scalars(
                select(AuditEvent.event_data).where(
                    AuditEvent.aggregate_type == "guest_link",
                    AuditEvent.aggregate_id == link.id,
                    AuditEvent.event_type == "guest_objection.wrong_amount",
                )
            )
            if row.get("obligation_id")
        }
        # Counted per obligation, not per link. A link can carry debts to two
        # different people; spending three objections arguing with one of them
        # used to leave nothing to say about the other, which made the quota a
        # way to silence a debt by exhausting a neighbour's.
        objection_counts: dict[str, int] = {}
        for row in self.session.scalars(
            select(AuditEvent.event_data).where(
                AuditEvent.aggregate_type == "guest_link",
                AuditEvent.aggregate_id == link.id,
                AuditEvent.event_type.in_(
                    ("guest_objection.not_me", "guest_objection.wrong_amount")
                ),
            )
        ):
            target = row.get("obligation_id")
            key = str(target) if target else "*"
            objection_counts[key] = objection_counts.get(key, 0) + 1

        blocks = []
        recorded_by_ids: set[uuid.UUID] = set()
        for obligation in obligations:
            snapshot = self.session.get(
                BankRecipientSnapshot, obligation.bank_recipient_snapshot_id
            )
            if snapshot is None:
                raise RepositoryConflict("OBLIGATION_SNAPSHOT_NOT_FOUND")
            source_rows = tuple(
                self.session.execute(
                    select(ExpenseVersion.description, ExpenseVersion.recorded_by_id)
                    .join(
                        ConfirmedAllocation,
                        ConfirmedAllocation.expense_version_id == ExpenseVersion.id,
                    )
                    .join(
                        CollectionObligationSource,
                        CollectionObligationSource.confirmed_allocation_id
                        == ConfirmedAllocation.id,
                    )
                    .where(CollectionObligationSource.obligation_id == obligation.id)
                )
            )
            recorded_by_ids.update(value for _, value in source_rows)
            labels = sorted({label for label, _ in source_rows if label})
            occasion = ", ".join(labels) if labels else "đợt thu này"
            receipt_amounts = [
                amount
                for amount in self.session.scalars(
                    select(ReceiptConfirmation.amount_vnd).where(
                        ReceiptConfirmation.obligation_id == obligation.id
                    )
                )
            ]
            derived_status = obligation_status(
                obligation.amount_vnd,
                [{"amount_vnd": amount} for amount in receipt_amounts],
            )
            already_reported = (
                self.session.scalar(
                    select(func.count(PaymentReport.id)).where(
                        PaymentReport.guest_link_id == link.id,
                        PaymentReport.obligation_id == obligation.id,
                    )
                )
                > 0
            )
            note = f"TT {obligation.id.hex[:8]}"
            payload = build_payload(
                bank_bin=snapshot.bank_bin,
                account_number=snapshot.account_number,
                amount_vnd=obligation.amount_vnd,
                note=note,
            )
            blocks.append(
                {
                    "obligation_id": str(obligation.id),
                    "occasion_label": occasion,
                    "amount_vnd": obligation.amount_vnd,
                    "recipient_display_name": snapshot.account_name
                    or str(obligation.recipient_id),
                    # A routing BIN is not a display name. Leave naming to the
                    # closed guest projection, which can also fall back honestly.
                    "bank_bin": snapshot.bank_bin,
                    "account_number": snapshot.account_number,
                    "account_holder_name": snapshot.account_name
                    or str(obligation.recipient_id),
                    "transfer_note": note,
                    "qr_payload": payload,
                    "qr_image_data_uri": payload_to_png_data_uri(payload),
                    "already_reported": already_reported,
                    "evidence_requested": str(obligation.id) in evidence_asked,
                    "disputed": str(obligation.id) in disputed_ids,
                    "objections_used": objection_counts.get(str(obligation.id), 0),
                    "objections_allowed": OBJECTION_LIMIT,
                    "receiver_confirmed": derived_status
                    in {"confirmed", "over_confirmed"},
                }
            )
        report_count = self.session.scalar(
            select(func.count(PaymentReport.id)).where(
                PaymentReport.guest_link_id == link.id
            )
        )
        objection_count = self.session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.aggregate_type == "guest_link",
                AuditEvent.aggregate_id == link.id,
                AuditEvent.event_type.in_(
                    ("guest_objection.not_me", "guest_objection.wrong_amount")
                ),
            )
        )
        # The one join that turns this page from machine output into a
        # sentence. `people` was never read here, so both fields below were
        # `str(uuid)` and the guest page asked a stranger for money in the name
        # of "b40dec6d-...". Read once for every id this envelope will print.
        names = self._display_names(recorded_by_ids | {envelope.sender_id})
        recorded_by = (
            names[next(iter(recorded_by_ids))]
            if len(recorded_by_ids) == 1
            else "Người tạo đợt"
        )
        raw_envelope = {
            "recorded_by_display_name": recorded_by,
            "claimed_person_display_name": names[envelope.sender_id],
            "link_state": state,
            "obligations": blocks,
            "reports_used": report_count,
            "reports_allowed": REPORT_LIMIT,
            # Objections are stored as audit events by save_guest_objection,
            # so they can be counted without a Dispute table. Asking for the
            # calculation is not an objection and does not spend the quota --
            # charging someone for asking how a number was reached is how a
            # group learns not to ask.
            "objections_used": objection_count,
            "objections_allowed": OBJECTION_LIMIT,
        }
        return GuestEnvelopeRecord(link_id=link.id, envelope=raw_envelope)

    def get_payment_report_target(
        self, token_digest: bytes, obligation_id: uuid.UUID, now: datetime
    ) -> PaymentReportTarget | None:
        link_row = self.session.execute(
            select(GuestLink, CollectionEnvelope)
            .join(CollectionEnvelope, CollectionEnvelope.id == GuestLink.envelope_id)
            .where(GuestLink.token_digest == token_digest)
            .with_for_update()
        ).one_or_none()
        if link_row is None:
            return None
        link, envelope = link_row
        obligation = self.session.scalar(
            select(CollectionObligation).where(
                CollectionObligation.id == obligation_id,
                CollectionObligation.batch_version_id == envelope.batch_version_id,
                CollectionObligation.sender_id == envelope.sender_id,
            )
        )
        if obligation is None:
            return None
        active = link.status == GuestLinkStatus.ACTIVE and now < link.expires_at
        reports_used = self.session.scalar(
            select(func.count(PaymentReport.id)).where(
                PaymentReport.guest_link_id == link.id
            )
        )
        return PaymentReportTarget(
            link_id=link.id,
            obligation_id=obligation.id,
            amount_vnd=obligation.amount_vnd,
            active_capability=active,
            reports_used=reports_used,
        )

    def save_payment_report(
        self,
        *,
        target: PaymentReportTarget,
        idempotency_key: uuid.UUID,
        now: datetime,
    ) -> PaymentReportRecord:
        existing = self.session.scalar(
            select(PaymentReport).where(
                PaymentReport.idempotency_key == idempotency_key
            )
        )
        if existing is not None:
            if (
                existing.obligation_id != target.obligation_id
                or existing.guest_link_id != target.link_id
                or existing.amount_vnd != target.amount_vnd
            ):
                raise RepositoryConflict("IDEMPOTENCY_KEY_REUSED")
            return PaymentReportRecord(
                id=existing.id,
                obligation_id=existing.obligation_id,
                amount_vnd=existing.amount_vnd,
                receipt_amounts_vnd=self._receipt_amounts(existing.obligation_id),
            )
        report = PaymentReport(
            obligation_id=target.obligation_id,
            guest_link_id=target.link_id,
            reported_by_id=None,
            amount_vnd=target.amount_vnd,
            idempotency_key=idempotency_key,
            reported_at=now,
        )
        self.session.add(report)
        self.session.flush()
        self.session.add(
            AuditEvent(
                actor_id=None,
                event_type="payment_reported",
                aggregate_type="collection_obligation",
                aggregate_id=target.obligation_id,
                request_id=idempotency_key,
                event_data={"payment_report_id": str(report.id)},
                occurred_at=now,
            )
        )
        return PaymentReportRecord(
            id=report.id,
            obligation_id=report.obligation_id,
            amount_vnd=report.amount_vnd,
            receipt_amounts_vnd=self._receipt_amounts(report.obligation_id),
        )

    def list_batch_obligations(self, batch_id: uuid.UUID) -> BatchBoard | None:
        """What the person collecting needs to see, disputes included.

        Without this there was no surface at all on which a "this amount is
        wrong" could be noticed. A guest could file one, be told truthfully
        that it had been recorded, and the collection round would carry on --
        because nobody on the other side had anywhere to read it.
        """
        batch = self.session.get(CollectionBatch, batch_id)
        if batch is None:
            return None
        version = self.session.scalar(
            select(CollectionBatchVersion)
            .where(CollectionBatchVersion.batch_id == batch_id)
            .order_by(CollectionBatchVersion.version_number.desc())
            .limit(1)
        )
        if version is None:
            return None

        obligations = list(
            self.session.scalars(
                select(CollectionObligation)
                .where(CollectionObligation.batch_version_id == version.id)
                .order_by(CollectionObligation.sender_id)
            )
        )

        # One query for every dispute in this batch rather than one per
        # obligation. The link ids are the aggregate the events hang off.
        link_ids = list(
            self.session.scalars(
                select(GuestLink.id)
                .join(
                    CollectionEnvelope, CollectionEnvelope.id == GuestLink.envelope_id
                )
                .where(CollectionEnvelope.batch_version_id == version.id)
            )
        )
        disputes: dict[str, str | None] = {}
        if link_ids:
            # Ordered on purpose. `setdefault` below means "the first reason
            # wins", and without an ORDER BY PostgreSQL is free to return rows
            # in whatever order a scan produces -- so "first" would have meant
            # whichever row the planner happened to reach first, and the reason
            # shown on the board could change between two identical requests.
            for row in self.session.scalars(
                select(AuditEvent.event_data)
                .where(
                    AuditEvent.aggregate_type == "guest_link",
                    AuditEvent.aggregate_id.in_(link_ids),
                    AuditEvent.event_type == "guest_objection.wrong_amount",
                )
                .order_by(AuditEvent.occurred_at, AuditEvent.id)
            ):
                target = row.get("obligation_id")
                if target:
                    # First reason wins: a second objection on the same
                    # obligation does not overwrite why it was first raised.
                    disputes.setdefault(str(target), row.get("reason"))

        # The senders' own claims, one aggregate rather than a query per row.
        # MIN, not MAX: a guest gets three reports, and every retry after the
        # first is the same claim repeated rather than a new fact. Taking the
        # latest would make the time on the board drift each time somebody
        # pressed the button again while nothing about the claim had changed.
        claims: dict[uuid.UUID, datetime] = dict(
            self.session.execute(
                select(
                    PaymentReport.obligation_id,
                    func.min(PaymentReport.reported_at),
                )
                .join(
                    CollectionObligation,
                    CollectionObligation.id == PaymentReport.obligation_id,
                )
                .where(CollectionObligation.batch_version_id == version.id)
                .group_by(PaymentReport.obligation_id)
            ).all()
        )

        rows = []
        for obligation in obligations:
            key = str(obligation.id)
            rows.append(
                BatchObligationRow(
                    obligation_id=obligation.id,
                    sender_id=obligation.sender_id,
                    recipient_id=obligation.recipient_id,
                    amount_vnd=obligation.amount_vnd,
                    status=obligation_status(
                        obligation.amount_vnd,
                        [
                            {"amount_vnd": amount}
                            for amount in self._receipt_amounts(obligation.id)
                        ],
                    ),
                    disputed=key in disputes,
                    disputed_reason=disputes.get(key),
                    payment_reported_at=claims.get(obligation.id),
                )
            )
        return BatchBoard(context_id=batch.context_id, obligations=tuple(rows))

    def get_receipt_target(self, obligation_id: uuid.UUID) -> ReceiptTarget | None:
        obligation = self.session.scalar(
            select(CollectionObligation)
            .where(CollectionObligation.id == obligation_id)
            .with_for_update()
        )
        if obligation is None:
            return None
        return ReceiptTarget(
            obligation_id=obligation.id,
            recipient_id=obligation.recipient_id,
            amount_vnd=obligation.amount_vnd,
        )

    def save_receipt_confirmation(
        self,
        *,
        target: ReceiptTarget,
        confirmed_by_id: uuid.UUID,
        amount_vnd: int,
        payment_report_id: uuid.UUID | None,
        idempotency_key: uuid.UUID,
        now: datetime,
    ) -> ReceiptRecord:
        existing = self.session.scalar(
            select(ReceiptConfirmation).where(
                ReceiptConfirmation.idempotency_key == idempotency_key
            )
        )
        if existing is not None:
            if (
                existing.obligation_id != target.obligation_id
                or existing.confirmed_by_id != confirmed_by_id
                or existing.amount_vnd != amount_vnd
                or existing.payment_report_id != payment_report_id
            ):
                raise RepositoryConflict("IDEMPOTENCY_KEY_REUSED")
            return ReceiptRecord(
                id=existing.id,
                obligation_id=existing.obligation_id,
                amount_vnd=existing.amount_vnd,
                receipt_amounts_vnd=self._receipt_amounts(existing.obligation_id),
            )
        if payment_report_id is not None:
            report = self.session.get(PaymentReport, payment_report_id)
            if report is None or report.obligation_id != target.obligation_id:
                raise RepositoryConflict("PAYMENT_REPORT_NOT_FOR_OBLIGATION")
        confirmation = ReceiptConfirmation(
            obligation_id=target.obligation_id,
            payment_report_id=payment_report_id,
            confirmed_by_id=confirmed_by_id,
            amount_vnd=amount_vnd,
            idempotency_key=idempotency_key,
            confirmed_at=now,
        )
        self.session.add(confirmation)
        self.session.flush()
        self.session.add(
            AuditEvent(
                actor_id=confirmed_by_id,
                event_type="receipt_confirmed",
                aggregate_type="collection_obligation",
                aggregate_id=target.obligation_id,
                request_id=idempotency_key,
                event_data={"receipt_confirmation_id": str(confirmation.id)},
                occurred_at=now,
            )
        )
        return ReceiptRecord(
            id=confirmation.id,
            obligation_id=confirmation.obligation_id,
            amount_vnd=confirmation.amount_vnd,
            receipt_amounts_vnd=self._receipt_amounts(confirmation.obligation_id),
        )

    def _receipt_amounts(self, obligation_id: uuid.UUID) -> tuple[int, ...]:
        return tuple(
            self.session.scalars(
                select(ReceiptConfirmation.amount_vnd)
                .where(ReceiptConfirmation.obligation_id == obligation_id)
                .order_by(ReceiptConfirmation.confirmed_at, ReceiptConfirmation.id)
            )
        )

    def save_guest_objection(
        self,
        *,
        token_digest: bytes,
        kind: str,
        obligation_id: uuid.UUID | None,
        reason: str | None,
        now: datetime,
    ) -> None:
        link = self.session.scalar(
            select(GuestLink).where(GuestLink.token_digest == token_digest)
        )
        if link is None:
            return

        self.session.add(
            AuditEvent(
                actor_id=None,  # a guest has no account; the capability is the subject
                event_type=f"guest_objection.{kind}",
                aggregate_type="guest_link",
                aggregate_id=link.id,
                event_data={
                    "kind": kind,
                    "obligation_id": str(obligation_id) if obligation_id else None,
                    "reason": reason,
                },
                occurred_at=now,
            )
        )

        if kind == "not_me":
            # The reader says this link is not theirs, so it stops showing an
            # amount and an account number immediately. The obligation itself
            # survives: section 8.2 is explicit that a dead link does not make
            # a debt disappear.
            link.status = GuestLinkStatus.REVOKED
            link.revoked_at = now

    def person_finance_summary(
        self, person_id: uuid.UUID, *, movement_limit: int
    ) -> PersonFinanceSummary:
        """Recompute one person's standing from the ledger. No stored totals.

        Read in several passes rather than one join because they answer
        different questions and a single query would have to pick one grain.
        Allocations are per expense version; obligations are per sender pair;
        joining them multiplies rows and quietly doubles money -- which is the
        one bug on this screen nobody would catch by looking, because a wrong
        total still looks like a total.
        """
        person = self.session.get(Person, person_id)

        # Only the newest version of each expense counts. Corrections write a
        # new version rather than overwriting, so an unfiltered sum adds the
        # mistake to the fix -- the first draft of this method reported a
        # corrected 100k dinner as 200k, and a wrong total still reads as a
        # total. Same shape as the subquery `load_batch_inputs` already uses.
        newest = (
            select(
                ExpenseVersion.expense_id.label("expense_id"),
                func.max(ExpenseVersion.version_number).label("version_number"),
            )
            .group_by(ExpenseVersion.expense_id)
            .subquery()
        )
        current_allocations = (
            select(
                ConfirmedAllocation.amount_vnd.label("amount_vnd"),
                ExpenseVersion.expense_id.label("expense_id"),
                ExpenseVersion.paid_by_id.label("paid_by_id"),
            )
            .select_from(ConfirmedAllocation)
            .join(
                ExpenseVersion,
                ExpenseVersion.id == ConfirmedAllocation.expense_version_id,
            )
            .join(
                newest,
                (newest.c.expense_id == ExpenseVersion.expense_id)
                & (newest.c.version_number == ExpenseVersion.version_number),
            )
            .where(ConfirmedAllocation.participant_id == person_id)
            .subquery()
        )

        # Spend: this person's own share of every confirmed expense. Invariant
        # 3 in one query -- nothing is read from a balance column because
        # there is no balance column.
        #
        # `int(...)` rather than the driver's own answer: PostgreSQL sums a
        # bigint column as `numeric`, which psycopg hands back as `Decimal`.
        # Law 1 of this product is integer đồng end to end, and a Decimal that
        # escapes here reaches JSON as `200000.0`.
        spend_vnd = int(
            self.session.scalar(
                select(func.coalesce(func.sum(current_allocations.c.amount_vnd), 0))
            )
            or 0
        )
        expense_count = int(
            self.session.scalar(
                select(func.count(func.distinct(current_allocations.c.expense_id)))
            )
            or 0
        )
        group_count = int(
            self.session.scalar(
                select(func.count(Membership.id)).where(
                    Membership.person_id == person_id,
                    Membership.state == MembershipState.ACTIVE,
                )
            )
            or 0
        )

        # What this person owes is decided at confirmation, not at publication.
        #
        # This used to read only obligations inside an announced batch, on the
        # argument that a round nobody has sent is not yet a debt. That is
        # wrong in the one moment this screen exists for: between splitting a
        # bill and sending the round, the share is owed and nobody has paid
        # anything -- and because `settled` is the remainder, the whole of a
        # just-split dinner showed up under *Đã thanh toán*. The demo path ends
        # on this screen, so the state it passes through is the state a viewer
        # sees.
        #
        # A share is owed when somebody else fronted it. The payer's own share
        # is spend and never debt: they handed the money to the restaurant, and
        # no obligation row is ever written against them for it -- which is
        # exactly why a query starting from obligations cannot tell the two
        # apart.
        owed_vnd = int(
            self.session.scalar(
                select(func.coalesce(func.sum(current_allocations.c.amount_vnd), 0)).where(
                    current_allocations.c.paid_by_id != person_id
                )
            )
            or 0
        )
        # Settled by arrival, never by self-report. A `PaymentReport` is the
        # sender saying they transferred; `ReceiptConfirmation` is the other
        # side saying it arrived. Counting reports would let anybody clear
        # their own debt by pressing a button.
        paid_vnd = int(
            self.session.scalar(
                select(func.coalesce(func.sum(ReceiptConfirmation.amount_vnd), 0))
                .select_from(ReceiptConfirmation)
                .join(
                    CollectionObligation,
                    CollectionObligation.id == ReceiptConfirmation.obligation_id,
                )
                .where(CollectionObligation.sender_id == person_id)
            )
            or 0
        )
        # Clamped: an over-confirmation is a real state the ledger permits, and
        # it must not turn into a negative debt that then inflates `settled`
        # past what was ever spent.
        outstanding_vnd = max(0, owed_vnd - paid_vnd)

        return PersonFinanceSummary(
            person_id=person_id,
            display_name=person.display_name if person else None,
            spend_vnd=spend_vnd,
            # Subtraction, not a fifth query: the two figures under the total
            # have to add back up to it on screen.
            settled_vnd=spend_vnd - outstanding_vnd,
            outstanding_vnd=outstanding_vnd,
            expense_count=expense_count,
            group_count=group_count,
            movements=self._finance_movements(person_id, movement_limit),
        )

    def _finance_movements(
        self, person_id: uuid.UUID, limit: int
    ) -> tuple[FinanceMovement, ...]:
        """Confirmed arrivals, newest first, in both directions."""
        rows = self.session.execute(
            select(
                CollectionObligation.id,
                CollectionObligation.sender_id,
                CollectionObligation.recipient_id,
                ReceiptConfirmation.amount_vnd,
                ReceiptConfirmation.confirmed_at,
                CollectionBatch.context_id,
                Context.display_name,
            )
            .select_from(ReceiptConfirmation)
            .join(
                CollectionObligation,
                CollectionObligation.id == ReceiptConfirmation.obligation_id,
            )
            .join(
                CollectionBatchVersion,
                CollectionBatchVersion.id == CollectionObligation.batch_version_id,
            )
            .join(CollectionBatch, CollectionBatch.id == CollectionBatchVersion.batch_id)
            # OUTER, and this is not defensive padding. `collection_batches`
            # .context_id carries no foreign key into `contexts`, and nothing
            # in the vertical slice writes a context row -- the app posts
            # expenses against a fixed synthetic group id that only
            # `POST /contexts` would ever create. An inner join therefore
            # dropped every movement for the app's own group and returned an
            # empty list that looked exactly like "no transactions yet".
            .outerjoin(Context, Context.id == CollectionBatch.context_id)
            .where(
                (CollectionObligation.sender_id == person_id)
                | (CollectionObligation.recipient_id == person_id)
            )
            .order_by(ReceiptConfirmation.confirmed_at.desc(), ReceiptConfirmation.id)
            .limit(limit)
        ).all()

        movements: list[FinanceMovement] = []
        for (
            obligation_id,
            sender_id,
            recipient_id,
            amount_vnd,
            confirmed_at,
            context_id,
            context_name,
        ) in rows:
            outgoing = sender_id == person_id
            counterparty_id = recipient_id if outgoing else sender_id
            counterparty = self.session.get(Person, counterparty_id)
            movements.append(
                FinanceMovement(
                    obligation_id=obligation_id,
                    direction="out" if outgoing else "in",
                    amount_vnd=amount_vnd,
                    counterparty_id=counterparty_id,
                    counterparty_name=counterparty.display_name if counterparty else None,
                    context_id=context_id,
                    context_name=context_name,
                    occasion=self._obligation_occasion(obligation_id),
                    occurred_at=confirmed_at,
                )
            )
        return tuple(movements)

    def _obligation_occasion(self, obligation_id: uuid.UUID) -> str | None:
        """What the money was for, read back through the obligation's sources.

        An obligation can be built from more than one expense. When it is,
        naming only the first would be a lie of omission on a money screen, so
        the count travels with the name instead.
        """
        descriptions = self.session.scalars(
            select(ExpenseVersion.description)
            .select_from(CollectionObligationSource)
            .join(
                ConfirmedAllocation,
                ConfirmedAllocation.id == CollectionObligationSource.confirmed_allocation_id,
            )
            .join(
                ExpenseVersion,
                ExpenseVersion.id == ConfirmedAllocation.expense_version_id,
            )
            .where(CollectionObligationSource.obligation_id == obligation_id)
            .order_by(ExpenseVersion.occurred_at)
        ).all()
        named = [text for text in descriptions if text]
        if not named:
            return None
        unique = list(dict.fromkeys(named))
        if len(unique) == 1:
            return unique[0]
        return f"{unique[0]} +{len(unique) - 1}"


__all__ = [
    "AllocationRow",
    "ApiRepository",
    "BankRecipientRecord",
    "BatchForPublish",
    "BatchInputs",
    "ConfirmedExpense",
    "ConfirmationRecord",
    "ContextRecord",
    "ExpenseIdentity",
    "FinanceMovement",
    "FrozenBatch",
    "FrozenObligation",
    "GuestEnvelopeRecord",
    "GuestLinkDraft",
    "MembershipRecord",
    "MessagePage",
    "MessageRecord",
    "ObligationDraft",
    "PaymentReportRecord",
    "PaymentReportTarget",
    "PersonFinanceSummary",
    "PersonRecord",
    "PublishObligation",
    "ReceiptRecord",
    "ReceiptTarget",
    "SqlAlchemyApiRepository",
    "StoredGuestLink",
]
