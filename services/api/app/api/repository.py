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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.limits import OBJECTION_LIMIT, REPORT_LIMIT
from app.api.errors import RepositoryConflict
from app.api.schemas import ExpenseInput
from app.db.models import (
    AuditEvent,
    BankRecipient,
    BankRecipientSnapshot,
    CollectionBatch,
    CollectionBatchStatus,
    CollectionBatchVersion,
    CollectionEnvelope,
    CollectionObligation,
    CollectionObligationSource,
    ConfirmedAllocation,
    Expense,
    ExpenseDiscount,
    ExpenseItem,
    ExpenseItemShare,
    ExpenseSurcharge,
    ExpenseVersion,
    GuestLink,
    GuestLinkStatus,
    PayerAcknowledgement,
    PaymentReport,
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


class ApiRepository(Protocol):
    def create_expense(self, context_id: uuid.UUID) -> ExpenseIdentity: ...

    def get_expense(self, expense_id: uuid.UUID) -> ExpenseIdentity | None: ...

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

    def load_bank_recipients(
        self, recipient_ids: frozenset[uuid.UUID]
    ) -> dict[uuid.UUID, BankRecipientRecord]: ...

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


class SqlAlchemyApiRepository:
    """PostgreSQL implementation. One instance owns one request transaction."""


    # Section 8.6 caps objections so a leaked link cannot be used to bury

    # the recipient. Was hardcoded to zero while the two objection routes

    # did not exist, which made both buttons dead before they 404ed.


    def __init__(self, session: Session):
        self.session = session

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
            collectable = tuple(
                row
                for row in rows
                if row.participant_id != version.paid_by_id and row.amount_vnd > 0
            )
            source_ids: set[uuid.UUID] = set()
            if collectable:
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
        return {
            row.recipient_id: BankRecipientRecord(
                id=row.id,
                recipient_id=row.recipient_id,
                bank_bin=row.bank_bin,
                account_number=row.account_number,
                account_name=row.account_name,
                confirmed_at=row.confirmed_by_recipient_at,
            )
            for row in recipients
        }

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
                    "bank_name": f"Ngân hàng {snapshot.bank_bin}",
                    "bank_bin": snapshot.bank_bin,
                    "account_number": snapshot.account_number,
                    "account_holder_name": snapshot.account_name
                    or str(obligation.recipient_id),
                    "transfer_note": note,
                    "qr_payload": payload,
                    "qr_image_data_uri": payload_to_png_data_uri(payload),
                    "already_reported": already_reported,
                    "evidence_requested": str(obligation.id) in evidence_asked,
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
        recorded_by = (
            str(next(iter(recorded_by_ids)))
            if len(recorded_by_ids) == 1
            else "Người tạo đợt"
        )
        raw_envelope = {
            "recorded_by_display_name": recorded_by,
            "claimed_person_display_name": str(envelope.sender_id),
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


__all__ = [
    "AllocationRow",
    "ApiRepository",
    "BankRecipientRecord",
    "BatchForPublish",
    "BatchInputs",
    "ConfirmedExpense",
    "ConfirmationRecord",
    "ExpenseIdentity",
    "FrozenBatch",
    "FrozenObligation",
    "GuestEnvelopeRecord",
    "GuestLinkDraft",
    "ObligationDraft",
    "PaymentReportRecord",
    "PaymentReportTarget",
    "PublishObligation",
    "ReceiptRecord",
    "ReceiptTarget",
    "SqlAlchemyApiRepository",
    "StoredGuestLink",
]
