"""Persistence port and PostgreSQL adapter for API workflows.

The application service calls domain functions before invoking write methods in
this module. The adapter never invents allocations, merges debts, or stores an
obligation status. Receipt events remain the only input used to derive that
status.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from sqlalchemy import Date, cast, func, or_, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

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
    FriendRequest,
    FriendRequestState,
    GuestLink,
    GuestLinkStatus,
    Membership,
    MembershipOrigin,
    MembershipRole,
    MembershipState,
    Memory,
    MemoryKind,
    Message,
    MessageKind,
    Outing,
    OutingInvite,
    OutingInviteSource,
    OutingStop,
    OutingStopCheckin,
    PayerAcknowledgement,
    PaymentReport,
    Person,
    ReceiptConfirmation,
    UploadedImage,
    VerificationScope,
)
from app.domain.capability import capability_scope
from app.domain.friendship import Decision, FriendshipError
from app.domain.friendship import decide as decide_friendship
from app.domain.ledger import obligation_status
from app.payments.vietqr import build_payload
from app.web.qr import payload_to_png_data_uri

# A trip's `starts_on`/`ends_on` are wall-clock Vietnamese calendar days; an
# expense's `occurred_at` is an instant. Folding the instant with whatever
# timezone the database session happens to carry is the bug this constant
# exists to prevent: under UTC a 01:00 supper on the last night of the trip
# lands on the previous day, and under a UTC server it can fall out of the trip
# entirely. The product's days are Vietnam's days, so name the zone.
WALL_CLOCK_ZONE = "Asia/Ho_Chi_Minh"


def _wall_clock_date(column):
    """The Vietnamese calendar day of a timestamptz column, session-TZ-proof."""
    return cast(func.timezone(WALL_CLOCK_ZONE, column), Date)


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
    #: What this person is shown as. `memberships.person_id` is a foreign key
    #: into `people` and `people.display_name` is `NOT NULL`, so the name exists
    #: for every row this record can describe -- carrying only the id meant the
    #: roster handed a screen a hexadecimal string and nothing to render it as.
    display_name: str
    state: str
    role: str
    origin: str
    invited_by_id: uuid.UUID | None
    joined_at: datetime | None
    left_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """One row on the wall, photograph or check-in.

    The location fields are group-private in the same sense the wall is: they
    reach a caller only through `list_memories`, which every route behind it
    gates on membership. Nothing in this layer formats them into a log line or
    an exception message -- a `lat`/`lng` pair in a traceback is a person's
    whereabouts in a file the group never agreed to.
    """

    id: uuid.UUID
    context_id: uuid.UUID
    author_id: uuid.UUID
    kind: str
    #: Present on a photo, absent on a check-in. The database refuses a row
    #: that carries both this and a place.
    image_url: str | None
    caption: str | None
    place_id: str | None
    place_name: str | None
    lat: float | None
    lng: float | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class UploadedImageRecord:
    id: uuid.UUID
    storage_key: str
    context_id: uuid.UUID | None
    owner_person_id: uuid.UUID | None
    uploaded_by_id: uuid.UUID
    content_type: str
    byte_size: int
    width: int
    height: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MemoryPage:
    memories: tuple[MemoryRecord, ...]
    has_more: bool


@dataclass(frozen=True, slots=True)
class OutingStopRecord:
    id: uuid.UUID
    position: int
    minute_of_day: int
    label: str
    place_name: str | None


@dataclass(frozen=True, slots=True)
class StopCheckinRecord:
    """One arrival. Carries no coordinates -- see `OutingStopCheckin`."""

    id: uuid.UUID
    stop_id: uuid.UUID
    person_id: uuid.UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OutingRecord:
    id: uuid.UUID
    context_id: uuid.UUID
    created_by_id: uuid.UUID
    title: str
    starts_on: date
    ends_on: date
    headcount: int
    budget_per_person_vnd: int
    created_at: datetime
    stops: tuple[OutingStopRecord, ...]


@dataclass(frozen=True, slots=True)
class RecapOutingRecord:
    """One started trip, with its money recomputed rather than stored.

    `split_total_vnd` is not a column. It is the sum of the confirmed
    allocations of the expenses that happened inside the trip's days, summed on
    the request that asks -- invariant 3 for the memory wall. Storing a total
    on `outings` would have been one join cheaper and would have started
    drifting the first time somebody corrected an expense.
    """

    outing: OutingRecord
    in_progress: bool
    split_total_vnd: int
    expense_count: int
    memory_count: int


@dataclass(frozen=True, slots=True)
class OutingInviteRecord:
    id: uuid.UUID
    outing_id: uuid.UUID
    source: str
    invited_person_id: uuid.UUID | None
    invited_by_id: uuid.UUID
    accepted_at: datetime | None
    accepted_by_id: uuid.UUID | None
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


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


#: Which answer produces which rest state. The inverse of the domain's own
#: mapping, and the reason `decide_friend_request` can re-ask the domain without
#: the caller passing the decision down a second time: a target state names
#: exactly one answer. `pending` is absent because it is where an edge starts,
#: not somewhere a decision moves it to.
_ANSWER_PRODUCING: dict[FriendRequestState, Decision] = {
    FriendRequestState.ACCEPTED: Decision.ACCEPT,
    FriendRequestState.DECLINED: Decision.DECLINE,
    FriendRequestState.BLOCKED: Decision.BLOCK,
}


@dataclass(frozen=True, slots=True)
class FriendEdgeRecord:
    """One friend request, plus the name of whoever the reader is not.

    `other_person_id` and `other_display_name` are filled relative to a reader,
    because every screen that shows this row shows "the other person" -- the
    requester on an incoming request, the addressee on an outgoing one. Making
    the repository resolve it means no screen has to branch on direction, and
    no screen can get the branch backwards.

    There is no telephone number on this record and there is nowhere to put
    one: the table has no such column, by the design in
    `app/api/person_identity.py`.
    """

    id: uuid.UUID
    requester_id: uuid.UUID
    addressee_id: uuid.UUID
    other_person_id: uuid.UUID
    other_display_name: str
    state: str
    decided_by_id: uuid.UUID | None
    created_at: datetime
    decided_at: datetime | None


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

    def get_context(self, context_id: uuid.UUID) -> ContextRecord | None: ...

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

    def get_membership(self, membership_id: uuid.UUID) -> MembershipRecord | None: ...

    def leave_context(
        self, context_id: uuid.UUID, person_id: uuid.UUID, now: datetime
    ) -> MembershipRecord | None: ...

    def list_members(self, context_id: uuid.UUID) -> list[MembershipRecord]: ...

    def is_member(self, context_id: uuid.UUID, person_id: uuid.UUID) -> bool: ...

    def shares_active_context(
        self, viewer_id: uuid.UUID, subject_id: uuid.UUID
    ) -> bool: ...

    def membership_role(
        self, context_id: uuid.UUID, person_id: uuid.UUID
    ) -> str | None: ...

    def set_membership_role(
        self, context_id: uuid.UUID, person_id: uuid.UUID, role: str
    ) -> MembershipRecord | None: ...

    def create_outing(
        self,
        *,
        context_id: uuid.UUID,
        created_by_id: uuid.UUID,
        title: str,
        starts_on: date,
        ends_on: date,
        headcount: int,
        budget_per_person_vnd: int,
        now: datetime,
    ) -> OutingRecord: ...

    def get_outing(self, outing_id: uuid.UUID) -> OutingRecord | None: ...

    def list_outings(self, context_id: uuid.UUID) -> tuple[OutingRecord, ...]: ...

    def group_recap(
        self, context_id: uuid.UUID, *, today: date
    ) -> tuple[RecapOutingRecord, ...]: ...

    def replace_outing_stops(
        self,
        *,
        outing_id: uuid.UUID,
        stops: list[dict],
    ) -> OutingRecord: ...

    def get_outing_stop(
        self, stop_id: uuid.UUID
    ) -> tuple[OutingStopRecord, OutingRecord] | None: ...

    def create_stop_checkin(
        self,
        *,
        stop_id: uuid.UUID,
        person_id: uuid.UUID,
        now: datetime,
    ) -> StopCheckinRecord: ...

    def list_outing_checkins(
        self, outing_id: uuid.UUID
    ) -> tuple[StopCheckinRecord, ...]: ...

    def create_outing_invite(
        self,
        *,
        outing_id: uuid.UUID,
        source: str,
        invited_person_id: uuid.UUID | None,
        invited_by_id: uuid.UUID,
        token_digest: bytes | None,
        expires_at: datetime,
        now: datetime,
    ) -> OutingInviteRecord: ...

    def find_outing_invite_for_person(
        self, outing_id: uuid.UUID, person_id: uuid.UUID
    ) -> OutingInviteRecord | None: ...

    def get_outing_invite(self, invite_id: uuid.UUID) -> OutingInviteRecord | None: ...

    def get_outing_invite_by_digest(
        self, token_digest: bytes
    ) -> OutingInviteRecord | None: ...

    def accept_outing_invite(
        self,
        *,
        invite_id: uuid.UUID,
        accepted_by_id: uuid.UUID,
        now: datetime,
    ) -> OutingInviteRecord: ...

    def revoke_outing_invite(
        self,
        *,
        invite_id: uuid.UUID,
        now: datetime,
    ) -> OutingInviteRecord: ...

    def ensure_invited_membership(
        self,
        *,
        context_id: uuid.UUID,
        person_id: uuid.UUID,
        invited_by_id: uuid.UUID,
        now: datetime,
    ) -> MembershipRecord: ...

    def create_uploaded_image(
        self,
        *,
        storage_key: str,
        context_id: uuid.UUID | None,
        owner_person_id: uuid.UUID | None,
        uploaded_by_id: uuid.UUID,
        content_type: str,
        byte_size: int,
        width: int,
        height: int,
        now: datetime,
    ) -> UploadedImageRecord: ...

    def get_context_image(
        self, context_id: uuid.UUID, image_id: uuid.UUID
    ) -> UploadedImageRecord | None: ...

    def get_latest_avatar(self, person_id: uuid.UUID) -> UploadedImageRecord | None: ...

    def create_memory(
        self,
        *,
        context_id: uuid.UUID,
        author_id: uuid.UUID,
        image_url: str,
        caption: str | None,
        now: datetime,
    ) -> MemoryRecord: ...

    def create_checkin(
        self,
        *,
        context_id: uuid.UUID,
        author_id: uuid.UUID,
        place_id: str,
        place_name: str,
        lat: float,
        lng: float,
        caption: str | None,
        now: datetime,
    ) -> MemoryRecord: ...

    def list_memories(
        self,
        context_id: uuid.UUID,
        *,
        limit: int,
        before: tuple[datetime, uuid.UUID] | None = None,
        kind: str | None = None,
        place_id: str | None = None,
    ) -> MemoryPage: ...

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

    # --- friend graph (F03, F04) ---------------------------------------

    def get_friend_edge(
        self, person_a: uuid.UUID, person_b: uuid.UUID
    ) -> FriendEdgeRecord | None: ...

    def get_friend_request(
        self, request_id: uuid.UUID, reader_id: uuid.UUID
    ) -> FriendEdgeRecord | None: ...

    def open_friend_request(
        self,
        *,
        requester_id: uuid.UUID,
        addressee_id: uuid.UUID,
        now: datetime,
    ) -> FriendEdgeRecord: ...

    def decide_friend_request(
        self,
        *,
        request_id: uuid.UUID,
        state: str,
        decided_by_id: uuid.UUID,
        now: datetime,
    ) -> FriendEdgeRecord | None: ...

    def list_friend_requests(
        self, person_id: uuid.UUID, *, direction: str
    ) -> list[FriendEdgeRecord]: ...

    def list_friends(self, person_id: uuid.UUID) -> list[FriendEdgeRecord]: ...


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

    def _membership_record(
        self, membership: Membership, display_name: str | None = None
    ) -> MembershipRecord:
        # `display_name` is passed in only by callers that already hold it:
        # `list_members` reads every name in one statement rather than one per
        # row. Every other path here returns a single membership, so looking
        # the name up here costs one query and saves eight call sites from
        # remembering to.
        if display_name is None:
            display_name = self._display_names({membership.person_id})[
                membership.person_id
            ]
        return MembershipRecord(
            id=membership.id,
            context_id=membership.context_id,
            person_id=membership.person_id,
            display_name=display_name,
            state=membership.state.value,
            role=membership.role.value,
            origin=membership.origin.value,
            invited_by_id=membership.invited_by_id,
            joined_at=membership.joined_at,
            left_at=membership.left_at,
            created_at=membership.created_at,
        )

    @staticmethod
    def _memory_record(memory: Memory) -> MemoryRecord:
        return MemoryRecord(
            id=memory.id,
            context_id=memory.context_id,
            author_id=memory.author_id,
            kind=str(memory.kind),
            image_url=memory.image_url,
            caption=memory.caption,
            place_id=memory.place_id,
            place_name=memory.place_name,
            lat=memory.lat,
            lng=memory.lng,
            created_at=memory.created_at,
        )

    @staticmethod
    def _uploaded_image_record(image: UploadedImage) -> UploadedImageRecord:
        return UploadedImageRecord(
            id=image.id,
            storage_key=image.storage_key,
            context_id=image.context_id,
            owner_person_id=image.owner_person_id,
            uploaded_by_id=image.uploaded_by_id,
            content_type=image.content_type,
            byte_size=image.byte_size,
            width=image.width,
            height=image.height,
            created_at=image.created_at,
        )

    @staticmethod
    def _outing_stop_record(stop: OutingStop) -> OutingStopRecord:
        return OutingStopRecord(
            id=stop.id,
            position=stop.position,
            minute_of_day=stop.minute_of_day,
            label=stop.label,
            place_name=stop.place_name,
        )

    def _outing_record(self, outing: Outing) -> OutingRecord:
        stops = self.session.scalars(
            select(OutingStop)
            .where(OutingStop.outing_id == outing.id)
            .order_by(OutingStop.position)
        )
        return OutingRecord(
            id=outing.id,
            context_id=outing.context_id,
            created_by_id=outing.created_by_id,
            title=outing.title,
            starts_on=outing.starts_on,
            ends_on=outing.ends_on,
            headcount=outing.headcount,
            budget_per_person_vnd=outing.budget_per_person_vnd,
            created_at=outing.created_at,
            stops=tuple(self._outing_stop_record(stop) for stop in stops),
        )

    @staticmethod
    def _outing_invite_record(invite: OutingInvite) -> OutingInviteRecord:
        return OutingInviteRecord(
            id=invite.id,
            outing_id=invite.outing_id,
            source=invite.source.value,
            invited_person_id=invite.invited_person_id,
            invited_by_id=invite.invited_by_id,
            accepted_at=invite.accepted_at,
            accepted_by_id=invite.accepted_by_id,
            created_at=invite.created_at,
            expires_at=invite.expires_at,
            revoked_at=invite.revoked_at,
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
                .where(BillItemShare.bill_item_id.in_([item.id for item in item_rows]))
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
                select(Person.id, Person.display_name).where(Person.id.in_(person_ids))
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

    def get_context(self, context_id: uuid.UUID) -> ContextRecord | None:
        context = self.session.get(Context, context_id)
        if context is None:
            return None
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
            origin=MembershipOrigin.NAMED,
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

    def get_membership(self, membership_id: uuid.UUID) -> MembershipRecord | None:
        membership = self.session.scalar(
            select(Membership).where(Membership.id == membership_id)
        )
        return None if membership is None else self._membership_record(membership)

    def accept_membership(
        self, membership_id: uuid.UUID, now: datetime
    ) -> MembershipRecord | None:
        membership = self.session.scalar(
            select(Membership)
            .where(Membership.id == membership_id)
            .with_for_update()
            .execution_options(populate_existing=True)
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
        memberships = list(
            self.session.scalars(
                select(Membership)
                .where(
                    Membership.context_id == context_id,
                    Membership.left_at.is_(None),
                )
                .order_by(Membership.created_at, Membership.id)
            )
        )
        # One statement for the whole roster. A per-row lookup would make the
        # cost of naming a group grow with the group, on the request every
        # group screen opens with.
        names = self._display_names({row.person_id for row in memberships})
        return [
            self._membership_record(membership, names[membership.person_id])
            for membership in memberships
        ]

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

    def shares_active_context(
        self, viewer_id: uuid.UUID, subject_id: uuid.UUID
    ) -> bool:
        if viewer_id == subject_id:
            return True

        viewer_membership = aliased(Membership)
        subject_membership = aliased(Membership)
        shared_context = (
            select(viewer_membership.id)
            .join(
                subject_membership,
                subject_membership.context_id == viewer_membership.context_id,
            )
            .where(
                viewer_membership.person_id == viewer_id,
                viewer_membership.state == MembershipState.ACTIVE,
                subject_membership.person_id == subject_id,
                subject_membership.state == MembershipState.ACTIVE,
            )
            .exists()
        )
        return bool(self.session.scalar(select(shared_context)))

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

    def create_outing(
        self,
        *,
        context_id: uuid.UUID,
        created_by_id: uuid.UUID,
        title: str,
        starts_on: date,
        ends_on: date,
        headcount: int,
        budget_per_person_vnd: int,
        now: datetime,
    ) -> OutingRecord:
        outing = Outing(
            context_id=context_id,
            created_by_id=created_by_id,
            title=title,
            starts_on=starts_on,
            ends_on=ends_on,
            headcount=headcount,
            budget_per_person_vnd=budget_per_person_vnd,
            created_at=now,
        )
        self.session.add(outing)
        self.session.flush()
        return self._outing_record(outing)

    def get_outing(self, outing_id: uuid.UUID) -> OutingRecord | None:
        outing = self.session.get(Outing, outing_id)
        return None if outing is None else self._outing_record(outing)

    def list_outings(self, context_id: uuid.UUID) -> tuple[OutingRecord, ...]:
        outings = self.session.scalars(
            select(Outing)
            .where(Outing.context_id == context_id)
            .order_by(Outing.starts_on, Outing.id)
        )
        return tuple(self._outing_record(outing) for outing in outings)

    def group_recap(
        self, context_id: uuid.UUID, *, today: date
    ) -> tuple[RecapOutingRecord, ...]:
        """Started trips of one group, newest first, money read back from the ledger.

        There is no `expenses.outing_id`, so a trip claims the spending that
        happened on its days. That rule is stated on the screen rather than
        hidden here, because it is a rule and not a fact: a dinner split three
        days after the group got home belongs to nobody's trip.

        Two passes rather than one join. Allocations are per participant and
        memories are per photo; counting both in a single grouped query
        multiplies one by the other, and an inflated photo count is the kind of
        wrong number that still looks like a number.
        """
        started = (
            select(Outing)
            .where(Outing.context_id == context_id, Outing.starts_on <= today)
            .order_by(Outing.ends_on.desc(), Outing.id)
        )
        outings = tuple(self.session.scalars(started))
        if not outings:
            return ()

        # Only the newest version of each expense counts. A correction writes a
        # new version instead of overwriting, so an unfiltered sum adds the
        # mistake to the fix -- same subquery shape `person_finance_summary`
        # and `load_batch_inputs` already use, for the same reason.
        newest = (
            select(
                ExpenseVersion.expense_id.label("expense_id"),
                func.max(ExpenseVersion.version_number).label("version_number"),
            )
            .group_by(ExpenseVersion.expense_id)
            .subquery()
        )
        ledger = (
            select(
                Expense.id.label("expense_id"),
                ConfirmedAllocation.amount_vnd.label("amount_vnd"),
                _wall_clock_date(ExpenseVersion.occurred_at).label("on_date"),
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
            .join(Expense, Expense.id == ExpenseVersion.expense_id)
            .where(Expense.context_id == context_id)
            .subquery()
        )
        money = {
            row.outing_id: (int(row.split_total_vnd or 0), int(row.expense_count or 0))
            for row in self.session.execute(
                select(
                    Outing.id.label("outing_id"),
                    # `int(...)`, and not the driver's answer: PostgreSQL sums a
                    # bigint as `numeric`, which psycopg returns as `Decimal`,
                    # and a Decimal that escapes reaches JSON as `520000.0`.
                    # Law 1 is integer đồng end to end.
                    func.coalesce(func.sum(ledger.c.amount_vnd), 0).label(
                        "split_total_vnd"
                    ),
                    func.count(func.distinct(ledger.c.expense_id)).label(
                        "expense_count"
                    ),
                )
                .select_from(Outing)
                .outerjoin(
                    ledger,
                    ledger.c.on_date.between(Outing.starts_on, Outing.ends_on),
                )
                .where(Outing.id.in_([outing.id for outing in outings]))
                .group_by(Outing.id)
            )
        }
        photos = {
            row.outing_id: int(row.memory_count or 0)
            for row in self.session.execute(
                select(
                    Outing.id.label("outing_id"),
                    func.count(Memory.id).label("memory_count"),
                )
                .select_from(Outing)
                .outerjoin(
                    Memory,
                    (Memory.context_id == Outing.context_id)
                    & _wall_clock_date(Memory.created_at).between(
                        Outing.starts_on, Outing.ends_on
                    ),
                )
                .where(Outing.id.in_([outing.id for outing in outings]))
                .group_by(Outing.id)
            )
        }
        return tuple(
            RecapOutingRecord(
                outing=self._outing_record(outing),
                in_progress=outing.ends_on >= today,
                split_total_vnd=money.get(outing.id, (0, 0))[0],
                expense_count=money.get(outing.id, (0, 0))[1],
                memory_count=photos.get(outing.id, 0),
            )
            for outing in outings
        )

    def replace_outing_stops(
        self,
        *,
        outing_id: uuid.UUID,
        stops: list[dict],
    ) -> OutingRecord:
        outing = self.session.get(Outing, outing_id)
        if outing is None:
            raise RepositoryConflict("OUTING_NOT_FOUND")

        existing_stops = list(
            self.session.scalars(
                select(OutingStop).where(OutingStop.outing_id == outing_id)
            )
        )
        for stop in existing_stops:
            self.session.delete(stop)
        # Reused positions remain unique only after the previous plan is gone.
        self.session.flush()

        self.session.add_all(
            [
                OutingStop(
                    outing_id=outing_id,
                    position=position,
                    minute_of_day=stop["minute_of_day"],
                    label=stop["label"],
                    place_name=stop["place_name"],
                )
                for position, stop in enumerate(stops)
            ]
        )
        self.session.flush()
        return self._outing_record(outing)

    def get_outing_stop(
        self, stop_id: uuid.UUID
    ) -> tuple[OutingStopRecord, OutingRecord] | None:
        stop = self.session.get(OutingStop, stop_id)
        if stop is None:
            return None
        outing = self.session.get(Outing, stop.outing_id)
        if outing is None:
            return None
        return self._outing_stop_record(stop), self._outing_record(outing)

    def create_stop_checkin(
        self,
        *,
        stop_id: uuid.UUID,
        person_id: uuid.UUID,
        now: datetime,
    ) -> StopCheckinRecord:
        checkin = OutingStopCheckin(
            stop_id=stop_id, person_id=person_id, created_at=now
        )
        # The unique index is the rule, so the write is attempted and the
        # database answers. Asking "has this person checked in?" first and
        # branching on the answer is the same code with a race in it.
        try:
            with self.session.begin_nested():
                self.session.add(checkin)
                self.session.flush()
        except IntegrityError as exc:
            constraint = getattr(
                getattr(exc.orig, "diag", None), "constraint_name", None
            )
            if constraint == "uq_outing_stop_checkins_person":
                raise RepositoryConflict("ALREADY_CHECKED_IN") from exc
            raise
        return self._stop_checkin_record(checkin)

    def list_outing_checkins(
        self, outing_id: uuid.UUID
    ) -> tuple[StopCheckinRecord, ...]:
        rows = self.session.scalars(
            select(OutingStopCheckin)
            .join(OutingStop, OutingStop.id == OutingStopCheckin.stop_id)
            .where(OutingStop.outing_id == outing_id)
            .order_by(OutingStopCheckin.created_at, OutingStopCheckin.id)
        )
        return tuple(self._stop_checkin_record(row) for row in rows)

    @staticmethod
    def _stop_checkin_record(row: OutingStopCheckin) -> StopCheckinRecord:
        return StopCheckinRecord(
            id=row.id,
            stop_id=row.stop_id,
            person_id=row.person_id,
            created_at=row.created_at,
        )

    def create_outing_invite(
        self,
        *,
        outing_id: uuid.UUID,
        source: str,
        invited_person_id: uuid.UUID | None,
        invited_by_id: uuid.UUID,
        token_digest: bytes | None,
        expires_at: datetime,
        now: datetime,
    ) -> OutingInviteRecord:
        invite = OutingInvite(
            outing_id=outing_id,
            source=OutingInviteSource(source),
            invited_person_id=invited_person_id,
            invited_by_id=invited_by_id,
            token_digest=token_digest,
            created_at=now,
            expires_at=expires_at,
        )
        self.session.add(invite)
        self.session.flush()
        return self._outing_invite_record(invite)

    def find_outing_invite_for_person(
        self, outing_id: uuid.UUID, person_id: uuid.UUID
    ) -> OutingInviteRecord | None:
        invite = self.session.scalar(
            select(OutingInvite)
            .where(
                OutingInvite.outing_id == outing_id,
                OutingInvite.invited_person_id == person_id,
            )
            .limit(1)
        )
        return None if invite is None else self._outing_invite_record(invite)

    def get_outing_invite(self, invite_id: uuid.UUID) -> OutingInviteRecord | None:
        invite = self.session.get(OutingInvite, invite_id)
        return None if invite is None else self._outing_invite_record(invite)

    def get_outing_invite_by_digest(
        self, token_digest: bytes
    ) -> OutingInviteRecord | None:
        invite = self.session.scalar(
            select(OutingInvite)
            .where(OutingInvite.token_digest == token_digest)
            .limit(1)
        )
        return None if invite is None else self._outing_invite_record(invite)

    def accept_outing_invite(
        self,
        *,
        invite_id: uuid.UUID,
        accepted_by_id: uuid.UUID,
        now: datetime,
    ) -> OutingInviteRecord:
        invite = self.session.scalar(
            select(OutingInvite)
            .where(OutingInvite.id == invite_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if invite is None:
            raise RepositoryConflict("OUTING_INVITE_NOT_FOUND")
        if invite.accepted_at is not None:
            raise RepositoryConflict("OUTING_INVITE_ALREADY_ACCEPTED")
        if invite.revoked_at is not None or invite.expires_at <= now:
            raise RepositoryConflict("OUTING_INVITE_NOT_REDEEMABLE")
        invite.accepted_at = now
        invite.accepted_by_id = accepted_by_id
        self.session.flush()
        return self._outing_invite_record(invite)

    def revoke_outing_invite(
        self,
        *,
        invite_id: uuid.UUID,
        now: datetime,
    ) -> OutingInviteRecord:
        invite = self.session.scalar(
            select(OutingInvite)
            .where(OutingInvite.id == invite_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if invite is None:
            raise RepositoryConflict("OUTING_INVITE_NOT_FOUND")
        if invite.accepted_at is not None:
            raise RepositoryConflict("OUTING_INVITE_ALREADY_ACCEPTED")
        if invite.revoked_at is not None:
            return self._outing_invite_record(invite)
        invite.revoked_at = now
        self.session.flush()
        return self._outing_invite_record(invite)

    def ensure_invited_membership(
        self,
        *,
        context_id: uuid.UUID,
        person_id: uuid.UUID,
        invited_by_id: uuid.UUID,
        now: datetime,
    ) -> MembershipRecord:
        existing = self.session.scalar(
            select(Membership)
            .where(
                Membership.context_id == context_id,
                Membership.person_id == person_id,
                Membership.left_at.is_(None),
            )
            .limit(1)
        )
        if existing is not None:
            return self._membership_record(existing)

        membership = Membership(
            context_id=context_id,
            person_id=person_id,
            state=MembershipState.INVITED,
            role=MembershipRole.MEMBER,
            origin=MembershipOrigin.LINK,
            invited_by_id=invited_by_id,
            joined_at=None,
            left_at=None,
            created_at=now,
        )
        self.session.add(membership)
        self.session.flush()
        return self._membership_record(membership)

    def create_uploaded_image(
        self,
        *,
        storage_key: str,
        context_id: uuid.UUID | None,
        owner_person_id: uuid.UUID | None,
        uploaded_by_id: uuid.UUID,
        content_type: str,
        byte_size: int,
        width: int,
        height: int,
        now: datetime,
    ) -> UploadedImageRecord:
        image = UploadedImage(
            storage_key=storage_key,
            context_id=context_id,
            owner_person_id=owner_person_id,
            uploaded_by_id=uploaded_by_id,
            content_type=content_type,
            byte_size=byte_size,
            width=width,
            height=height,
            created_at=now,
        )
        self.session.add(image)
        self.session.flush()
        return self._uploaded_image_record(image)

    def get_context_image(
        self, context_id: uuid.UUID, image_id: uuid.UUID
    ) -> UploadedImageRecord | None:
        image = self.session.scalar(
            select(UploadedImage).where(
                UploadedImage.context_id == context_id,
                UploadedImage.id == image_id,
            )
        )
        return None if image is None else self._uploaded_image_record(image)

    def get_latest_avatar(self, person_id: uuid.UUID) -> UploadedImageRecord | None:
        image = self.session.scalar(
            select(UploadedImage)
            .where(UploadedImage.owner_person_id == person_id)
            .order_by(UploadedImage.created_at.desc(), UploadedImage.id.desc())
            .limit(1)
        )
        return None if image is None else self._uploaded_image_record(image)

    def create_memory(
        self,
        *,
        context_id: uuid.UUID,
        author_id: uuid.UUID,
        image_url: str,
        caption: str | None,
        now: datetime,
    ) -> MemoryRecord:
        memory = Memory(
            context_id=context_id,
            author_id=author_id,
            kind=MemoryKind.PHOTO,
            image_url=image_url,
            caption=caption,
            created_at=now,
        )
        self.session.add(memory)
        self.session.flush()
        return self._memory_record(memory)

    def create_checkin(
        self,
        *,
        context_id: uuid.UUID,
        author_id: uuid.UUID,
        place_id: str,
        place_name: str,
        lat: float,
        lng: float,
        caption: str | None,
        now: datetime,
    ) -> MemoryRecord:
        """Record that this group was at this place at this moment.

        Separate from `create_memory` rather than one method with six optional
        arguments. The two kinds have disjoint payloads and the database says
        so; a single writer taking everything would compile for the call that
        passes an image *and* a latitude, and the failure would arrive as an
        integrity error from a constraint instead of as a type error here.
        """

        memory = Memory(
            context_id=context_id,
            author_id=author_id,
            kind=MemoryKind.CHECKIN,
            image_url=None,
            caption=caption,
            place_id=place_id,
            place_name=place_name,
            lat=lat,
            lng=lng,
            created_at=now,
        )
        self.session.add(memory)
        self.session.flush()
        return self._memory_record(memory)

    def list_memories(
        self,
        context_id: uuid.UUID,
        *,
        limit: int,
        before: tuple[datetime, uuid.UUID] | None = None,
        kind: str | None = None,
        place_id: str | None = None,
    ) -> MemoryPage:
        statement = select(Memory).where(Memory.context_id == context_id)
        if kind is not None:
            statement = statement.where(Memory.kind == MemoryKind(kind))
        if place_id is not None:
            statement = statement.where(Memory.place_id == place_id)
        if before is not None:
            statement = statement.where(
                tuple_(Memory.created_at, Memory.id) < tuple_(*before)
            )
        statement = statement.order_by(Memory.created_at.desc(), Memory.id.desc())

        rows = list(self.session.scalars(statement.limit(limit + 1)))
        has_more = len(rows) > limit
        return MemoryPage(
            memories=tuple(self._memory_record(row) for row in rows[:limit]),
            has_more=has_more,
        )

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
            statement = statement.order_by(Message.created_at.desc(), Message.id.desc())

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
                select(BillItem).where(BillItem.bill_id == bill_id).with_for_update()
            )
        )
        items_by_key = {item.item_key: item for item in item_rows}
        assignments_by_key = {
            assignment["item_key"]: assignment for assignment in assignments
        }
        if set(assignments_by_key) - set(items_by_key):
            raise RepositoryConflict("UNKNOWN_BILL_ITEM")

        target_item_ids = [items_by_key[item_key].id for item_key in assignments_by_key]
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
                select(
                    func.coalesce(func.sum(current_allocations.c.amount_vnd), 0)
                ).where(current_allocations.c.paid_by_id != person_id)
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
            .join(
                CollectionBatch, CollectionBatch.id == CollectionBatchVersion.batch_id
            )
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
                    counterparty_name=counterparty.display_name
                    if counterparty
                    else None,
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
                ConfirmedAllocation.id
                == CollectionObligationSource.confirmed_allocation_id,
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

    # --- friend graph (F03, F04) ---------------------------------------

    def _friend_edge(
        self, row: FriendRequest, reader_id: uuid.UUID, name: str | None = None
    ) -> FriendEdgeRecord:
        """One row, oriented for whoever is reading it.

        The reader is always one of the two parties -- callers reach this only
        through queries filtered to their own id -- so "the other person" is
        well defined. If a future caller passes a stranger, they get the
        requester, which is wrong but not a disclosure: both ids are already
        in the row this caller was given.
        """
        other = row.addressee_id if row.requester_id == reader_id else row.requester_id
        return FriendEdgeRecord(
            id=row.id,
            requester_id=row.requester_id,
            addressee_id=row.addressee_id,
            other_person_id=other,
            other_display_name=name or self._display_names({other})[other],
            state=str(row.state),
            decided_by_id=row.decided_by_id,
            created_at=row.created_at,
            decided_at=row.decided_at,
        )

    def _edge_between(self, person_a: uuid.UUID, person_b: uuid.UUID):
        """The live edge for this unordered pair, whichever way it was asked.

        `DECLINED` rows are excluded because a declined edge does not occupy
        the pair -- the same states the partial unique index lists, and for the
        same reason. Two spellings of one rule; see the migration.
        """
        return self.session.scalar(
            select(FriendRequest)
            .where(
                or_(
                    (FriendRequest.requester_id == person_a)
                    & (FriendRequest.addressee_id == person_b),
                    (FriendRequest.requester_id == person_b)
                    & (FriendRequest.addressee_id == person_a),
                ),
                FriendRequest.state != FriendRequestState.DECLINED,
            )
            .order_by(FriendRequest.created_at.desc())
        )

    def get_friend_edge(
        self, person_a: uuid.UUID, person_b: uuid.UUID
    ) -> FriendEdgeRecord | None:
        row = self._edge_between(person_a, person_b)
        return None if row is None else self._friend_edge(row, person_a)

    def get_friend_request(
        self, request_id: uuid.UUID, reader_id: uuid.UUID
    ) -> FriendEdgeRecord | None:
        row = self.session.scalar(
            select(FriendRequest).where(FriendRequest.id == request_id)
        )
        if row is None:
            return None
        if reader_id not in (row.requester_id, row.addressee_id):
            # A stranger asking by id gets the same answer as a stranger asking
            # for an id that does not exist. Returning 403 here would confirm
            # that two particular people have an edge, to somebody who is not
            # either of them.
            return None
        return self._friend_edge(row, reader_id)

    def open_friend_request(
        self,
        *,
        requester_id: uuid.UUID,
        addressee_id: uuid.UUID,
        now: datetime,
    ) -> FriendEdgeRecord:
        row = FriendRequest(
            requester_id=requester_id,
            addressee_id=addressee_id,
            state=FriendRequestState.PENDING,
            created_at=now,
        )
        self.session.add(row)
        try:
            self.session.flush()
        except IntegrityError as exc:
            # `uq_friend_edge_live` fires when two people tap "add" at the same
            # moment. The service maps this to the same refusal the domain
            # raises for an edge it could see, so the two orderings of one race
            # are indistinguishable from outside -- which is what keeps a block
            # silent under concurrency too.
            raise RepositoryConflict("FRIEND_EDGE_EXISTS") from exc
        return self._friend_edge(row, requester_id)

    def decide_friend_request(
        self,
        *,
        request_id: uuid.UUID,
        state: str,
        decided_by_id: uuid.UUID,
        now: datetime,
    ) -> FriendEdgeRecord | None:
        row = self.session.scalar(
            select(FriendRequest)
            .where(FriendRequest.id == request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            return None

        target = FriendRequestState(state)
        answer = _ANSWER_PRODUCING.get(target)
        if answer is None:
            raise RepositoryConflict("NOT_A_DECISION")

        # The lock queues two writers; it does not tell the second one that the
        # edge moved while it waited. The service decided on a read taken
        # BEFORE this lock was held, so that decision is a proposal about a
        # state that may no longer exist -- `SELECT ... FOR UPDATE` returns the
        # row as the first writer committed it, and overwriting it blindly is
        # how a `block` that already answered 200 gets erased by an `accept`
        # that was approved against a stale `pending`.
        #
        # So ask the domain again, on the row we now hold. Asking rather than
        # re-deriving the rule here is the point: "BLOCKED is terminal" has to
        # have one spelling, and it lives in `app/domain/friendship.py`. This
        # adapter still invents nothing -- it re-runs the same pure function the
        # service ran, on fresher facts.
        try:
            decide_friendship(
                edge={
                    "requester_id": str(row.requester_id),
                    "addressee_id": str(row.addressee_id),
                    "state": str(row.state),
                },
                actor_id=str(decided_by_id),
                decision=str(answer),
            )
        except FriendshipError as refused:
            # The same code the service would have raised had this read come
            # first, so the two orderings of one race are indistinguishable
            # from outside -- the property `open_friend_request` keeps for the
            # other half of this feature.
            raise RepositoryConflict(refused.code) from refused

        row.state = target
        # The check constraint requires these to move together: a non-pending
        # row must carry a decision time, and a pending one must not.
        row.decided_at = now
        row.decided_by_id = decided_by_id
        try:
            self.session.flush()
        except IntegrityError as exc:
            # `uq_friend_edge_live` also covers UPDATEs into a live state, and
            # a decision can collide with it without any concurrency at all:
            # blocking a stale `declined` row while the pair already holds a
            # newer `pending` one. Uncaught, that reached
            # `ServerErrorMiddleware` as a 500 on an ordinary user path.
            raise RepositoryConflict("FRIEND_EDGE_EXISTS") from exc
        return self._friend_edge(row, decided_by_id)

    def list_friend_requests(
        self, person_id: uuid.UUID, *, direction: str
    ) -> list[FriendEdgeRecord]:
        """Pending requests only, in one direction.

        Answered requests are deliberately not listed here: an inbox that keeps
        showing declines is an inbox nobody opens, and a decline the requester
        can poll for is a decline that leaks the answer they were not given.
        A requester sees their outgoing request disappear; whether it was
        accepted is answered by the friend list, and only if it was.
        """
        side = (
            FriendRequest.addressee_id
            if direction == "incoming"
            else FriendRequest.requester_id
        )
        rows = list(
            self.session.scalars(
                select(FriendRequest)
                .where(side == person_id, FriendRequest.state == FriendRequestState.PENDING)
                .order_by(FriendRequest.created_at.desc(), FriendRequest.id)
            )
        )
        names = self._display_names(
            {
                row.addressee_id if row.requester_id == person_id else row.requester_id
                for row in rows
            }
        )
        return [
            self._friend_edge(row, person_id, names[
                row.addressee_id if row.requester_id == person_id else row.requester_id
            ])
            for row in rows
        ]

    def list_friends(self, person_id: uuid.UUID) -> list[FriendEdgeRecord]:
        """Friendship read back from the events that created it.

        `state = 'accepted'`, both directions. There is no `friends` table to
        drift from this query, which is the point.
        """
        rows = list(
            self.session.scalars(
                select(FriendRequest)
                .where(
                    or_(
                        FriendRequest.requester_id == person_id,
                        FriendRequest.addressee_id == person_id,
                    ),
                    FriendRequest.state == FriendRequestState.ACCEPTED,
                )
                .order_by(FriendRequest.decided_at.desc(), FriendRequest.id)
            )
        )
        names = self._display_names(
            {
                row.addressee_id if row.requester_id == person_id else row.requester_id
                for row in rows
            }
        )
        return [
            self._friend_edge(row, person_id, names[
                row.addressee_id if row.requester_id == person_id else row.requester_id
            ])
            for row in rows
        ]


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
    "FriendEdgeRecord",
    "FinanceMovement",
    "FrozenBatch",
    "FrozenObligation",
    "GuestEnvelopeRecord",
    "GuestLinkDraft",
    "MembershipRecord",
    "MemoryPage",
    "MemoryRecord",
    "MessagePage",
    "MessageRecord",
    "ObligationDraft",
    "OutingInviteRecord",
    "OutingRecord",
    "OutingStopRecord",
    "PaymentReportRecord",
    "PaymentReportTarget",
    "PersonFinanceSummary",
    "PersonRecord",
    "PublishObligation",
    "ReceiptRecord",
    "ReceiptTarget",
    "SqlAlchemyApiRepository",
    "StoredGuestLink",
    "UploadedImageRecord",
]
