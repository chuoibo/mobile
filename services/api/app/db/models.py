"""SQLAlchemy models for the first expense-to-collection vertical slice.

Money is represented exclusively as integer Vietnamese dong. Financial facts and
batch compositions are append-only; the first migration enforces that property for
the corresponding tables at the PostgreSQL layer.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PayerAcknowledgement(StrEnum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    DISPUTED = "disputed"


class VerificationScope(StrEnum):
    TOTALS_ONLY = "totals_only"
    ITEMS_REVIEWED = "items_reviewed"


class CollectionBatchStatus(StrEnum):
    ACCRUING = "accruing"
    FROZEN = "frozen"
    PUBLISHED = "published"
    COLLECTING = "collecting"
    COMPLETED = "completed"
    CLOSED_WITH_EXCEPTIONS = "closed_with_exceptions"
    CANCELLED = "cancelled"


class GuestLinkStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    ROTATED = "rotated"


class SurchargeMode(StrEnum):
    """ADR-0004: how a surcharge spreads across participants."""

    PROPORTIONAL = "proportional"
    EVEN = "even"


class DiscountScope(StrEnum):
    """ADR-0004: a discount is either proportional across the bill or tied to
    one item, and the two allocate very differently."""

    GLOBAL_PROPORTIONAL = "global_proportional"
    ITEM = "item"


class BillShareSource(StrEnum):
    """Whether a bill-item assignment is suggested or user-confirmed."""

    AI_SUGGESTED = "ai_suggested"
    CONFIRMED = "confirmed"


def _enum_type(enum_class: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_class,
        values_callable=lambda members: [member.value for member in members],
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )


class Bill(Base):
    """A scanned bill draft that has not entered the ledger."""

    __tablename__ = "bills"
    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 100", name="confidence_range"),
        CheckConstraint(
            "printed_total_vnd IS NULL OR printed_total_vnd >= 0",
            name="printed_total_nonnegative",
        ),
        CheckConstraint("items_total_vnd >= 0", name="items_total_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    printed_total_vnd: Mapped[int | None] = mapped_column(BigInteger)
    items_total_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BillItem(Base):
    """One line read from a scanned bill draft."""

    __tablename__ = "bill_items"
    __table_args__ = (
        UniqueConstraint("bill_id", "item_key", name="uq_bill_items_bill_item_key"),
        CheckConstraint("line_total_vnd > 0", name="line_total_positive"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bills.id", name="fk_bill_items_bill"),
        nullable=False,
        index=True,
    )
    item_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_vnd: Mapped[int | None] = mapped_column(BigInteger)
    line_total_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class BillSurcharge(Base):
    """A surcharge line retained with the mode used by the allocator."""

    __tablename__ = "bill_surcharges"
    __table_args__ = (
        UniqueConstraint(
            "bill_id",
            "surcharge_key",
            name="uq_bill_surcharges_bill_surcharge_key",
        ),
        CheckConstraint("amount_vnd > 0", name="amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bills.id", name="fk_bill_surcharges_bill"),
        nullable=False,
        index=True,
    )
    surcharge_key: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mode: Mapped[SurchargeMode] = mapped_column(
        _enum_type(SurchargeMode, "surcharge_mode"), nullable=False
    )


class BillDiscount(Base):
    """A discount line retained without pre-resolving its item reference."""

    __tablename__ = "bill_discounts"
    __table_args__ = (
        UniqueConstraint(
            "bill_id",
            "discount_key",
            name="uq_bill_discounts_bill_discount_key",
        ),
        CheckConstraint("amount_vnd > 0", name="amount_positive"),
        CheckConstraint(
            "(scope = 'item' AND target_item_key IS NOT NULL) OR "
            "(scope = 'global_proportional' AND target_item_key IS NULL)",
            name="scope_target_match",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bills.id", name="fk_bill_discounts_bill"),
        nullable=False,
        index=True,
    )
    discount_key: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scope: Mapped[DiscountScope] = mapped_column(
        _enum_type(DiscountScope, "discount_scope"), nullable=False
    )
    # This stays a plain key so the allocator remains authoritative for
    # UNKNOWN_ITEM and its error precedence.
    target_item_key: Mapped[str | None] = mapped_column(String(64))


class BillItemShare(Base):
    """One suggested or confirmed participant assignment for a bill item."""

    __tablename__ = "bill_item_shares"
    __table_args__ = (
        UniqueConstraint(
            "bill_item_id",
            "participant_id",
            name="uq_bill_item_shares_item_participant",
        ),
        CheckConstraint(
            "(source = 'confirmed' AND decided_by_id IS NOT NULL AND "
            "decided_at IS NOT NULL) OR "
            "(source = 'ai_suggested' AND decided_by_id IS NULL AND "
            "decided_at IS NULL)",
            name="decision_matches_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bill_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bill_items.id", name="fk_bill_item_shares_item"),
        nullable=False,
        index=True,
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    source: Mapped[BillShareSource] = mapped_column(
        _enum_type(BillShareSource, "bill_share_source"), nullable=False
    )
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Expense(Base):
    """Stable identity for an expense whose facts live in immutable versions."""

    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ExpenseVersion(Base):
    """Immutable material state of an expense at one version number."""

    __tablename__ = "expense_versions"
    __table_args__ = (
        UniqueConstraint(
            "expense_id", "version_number", name="uq_expense_versions_expense_version"
        ),
        ForeignKeyConstraint(
            ["expense_id", "previous_version_number"],
            ["expense_versions.expense_id", "expense_versions.version_number"],
            name="fk_expense_versions_previous_version",
        ),
        CheckConstraint(
            "(version_number = 1 AND previous_version_number IS NULL) OR "
            "(version_number > 1 AND previous_version_number = version_number - 1)",
            name="version_chain",
        ),
        CheckConstraint("subtotal_amount_vnd >= 0", name="subtotal_nonnegative"),
        CheckConstraint("fee_amount_vnd >= 0", name="fee_nonnegative"),
        CheckConstraint("vat_amount_vnd >= 0", name="vat_nonnegative"),
        CheckConstraint("shipping_amount_vnd >= 0", name="shipping_nonnegative"),
        CheckConstraint("discount_amount_vnd >= 0", name="discount_nonnegative"),
        # ADR-0004 decision 9 and golden vector G06: a zero-dong expense is
        # valid and allocates to zeroes. A `> 0` check here would reject an
        # expense the allocator accepts, and only at write time -- after the
        # user had already confirmed it.
        CheckConstraint("total_amount_vnd >= 0", name="total_nonnegative"),
        CheckConstraint(
            "total_amount_vnd = subtotal_amount_vnd + fee_amount_vnd + "
            "vat_amount_vnd + shipping_amount_vnd - discount_amount_vnd",
            name="total_components_match",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    expense_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expenses.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_version_number: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    paid_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payer_acknowledgement: Mapped[PayerAcknowledgement] = mapped_column(
        _enum_type(PayerAcknowledgement, "payer_acknowledgement"),
        nullable=False,
        default=PayerAcknowledgement.PENDING,
        server_default=PayerAcknowledgement.PENDING.value,
    )
    verification_scope: Mapped[VerificationScope] = mapped_column(
        _enum_type(VerificationScope, "verification_scope"), nullable=False
    )
    # The five scalar columns below are DERIVED roll-ups kept for fast queries.
    # After blocker D-03 the source of truth for surcharges and discounts is the
    # child tables, which carry mode and scope. Do not reconstruct an allocation
    # from these five numbers -- the information needed to do so is not here.
    subtotal_amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fee_amount_vnd: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    vat_amount_vnd: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    shipping_amount_vnd: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    discount_amount_vnd: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    total_amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ExpenseItem(Base):
    """One line on the bill, belonging to one immutable expense version.

    Added under review blocker D-02. Without items there is no way to rebuild
    the "who ate what" drill-down, and spec section 3 requires that drill-down
    to be either recomputed or marked stale after an edit -- neither of which
    is possible if the items were never stored.
    """

    __tablename__ = "expense_items"
    __table_args__ = (
        UniqueConstraint(
            "expense_version_id", "item_key", name="uq_expense_items_version_key"
        ),
        # ADR-0004 rejects a zero-amount line item (ZERO_AMOUNT) even though a
        # zero-amount expense total is fine.
        CheckConstraint("amount_vnd > 0", name="amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    expense_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expense_versions.id"),
        nullable=False,
        index=True,
    )
    item_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ExpenseItemShare(Base):
    """Which participant shares which item. The `shared_by` set of ADR-0004."""

    __tablename__ = "expense_item_shares"
    __table_args__ = (
        UniqueConstraint(
            "expense_item_id", "participant_id", name="uq_item_share_unique"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    expense_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expense_items.id"), nullable=False, index=True
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )


class ExpenseSurcharge(Base):
    """A fee, VAT or shipping line, WITH its distribution mode.

    Added under review blocker D-03. The flat `fee_amount_vnd` columns cannot
    express mode: two expenses with identical totals but different modes
    allocate differently (golden G10 gives {a: 66000, b: 44000} proportional
    and {a: 65000, b: 45000} even). Storing them identically loses money facts.
    """

    __tablename__ = "expense_surcharges"
    __table_args__ = (
        UniqueConstraint(
            "expense_version_id", "surcharge_key", name="uq_surcharges_version_key"
        ),
        CheckConstraint("amount_vnd > 0", name="amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    expense_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expense_versions.id"),
        nullable=False,
        index=True,
    )
    surcharge_key: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mode: Mapped[SurchargeMode] = mapped_column(
        _enum_type(SurchargeMode, "surcharge_mode"), nullable=False
    )


class ExpenseDiscount(Base):
    """A discount line, WITH its scope and, when item-scoped, its target."""

    __tablename__ = "expense_discounts"
    __table_args__ = (
        UniqueConstraint(
            "expense_version_id", "discount_key", name="uq_discounts_version_key"
        ),
        CheckConstraint("amount_vnd > 0", name="amount_positive"),
        # ADR-0004 SCOPE_TARGET_MISMATCH: an item-scoped discount needs a
        # target and a global one must not carry one.
        CheckConstraint(
            "(scope = 'item' AND target_item_id IS NOT NULL) OR "
            "(scope = 'global_proportional' AND target_item_id IS NULL)",
            name="scope_target_match",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    expense_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expense_versions.id"),
        nullable=False,
        index=True,
    )
    discount_key: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scope: Mapped[DiscountScope] = mapped_column(
        _enum_type(DiscountScope, "discount_scope"), nullable=False
    )
    target_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expense_items.id")
    )


class ConfirmedAllocation(Base):
    """Append-only official ledger allocation for one expense version and person."""

    __tablename__ = "confirmed_allocations"
    __table_args__ = (
        UniqueConstraint(
            "expense_version_id",
            "participant_id",
            name="uq_confirmed_allocations_version_participant",
        ),
        CheckConstraint("amount_vnd >= 0", name="amount_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    expense_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expense_versions.id"),
        nullable=False,
        index=True,
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    confirmed_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CollectionBatch(Base):
    """Mutable state-machine shell around immutable batch compositions."""

    __tablename__ = "collection_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[CollectionBatchStatus] = mapped_column(
        _enum_type(CollectionBatchStatus, "collection_batch_status"),
        nullable=False,
        default=CollectionBatchStatus.ACCRUING,
        server_default=CollectionBatchStatus.ACCRUING.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collecting_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CollectionBatchVersion(Base):
    """Immutable composition version used by snapshots, obligations, and envelopes."""

    __tablename__ = "collection_batch_versions"
    __table_args__ = (
        UniqueConstraint(
            "batch_id", "version_number", name="uq_batch_versions_batch_version"
        ),
        ForeignKeyConstraint(
            ["batch_id", "previous_version_number"],
            [
                "collection_batch_versions.batch_id",
                "collection_batch_versions.version_number",
            ],
            name="fk_batch_versions_previous_version",
        ),
        CheckConstraint(
            "(version_number = 1 AND previous_version_number IS NULL) OR "
            "(version_number > 1 AND previous_version_number = version_number - 1)",
            name="version_chain",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collection_batches.id"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_version_number: Mapped[int | None] = mapped_column(Integer)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BankRecipient(Base):
    """Recipient-confirmed bank destination; not proof of bank-account ownership."""

    __tablename__ = "bank_recipients"
    __table_args__ = (
        CheckConstraint("bank_bin ~ '^[0-9]{6}$'", name="bank_bin_format"),
        CheckConstraint(
            "account_number ~ '^[A-Za-z0-9]{1,19}$'", name="account_number_format"
        ),
        Index(
            "uq_bank_recipients_active_recipient",
            "recipient_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    bank_bin: Mapped[str] = mapped_column(String(6), nullable=False)
    account_number: Mapped[str] = mapped_column(String(19), nullable=False)
    account_name: Mapped[str | None] = mapped_column(String(255))
    confirmed_by_recipient_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BankRecipientSnapshot(Base):
    """Immutable bank destination frozen into one batch composition version."""

    __tablename__ = "bank_recipient_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "id", "batch_version_id", name="uq_bank_snapshots_id_batch_version"
        ),
        UniqueConstraint(
            "batch_version_id",
            "recipient_id",
            name="uq_bank_snapshots_batch_recipient",
        ),
        CheckConstraint("bank_bin ~ '^[0-9]{6}$'", name="bank_bin_format"),
        CheckConstraint(
            "account_number ~ '^[A-Za-z0-9]{1,19}$'", name="account_number_format"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collection_batch_versions.id"),
        nullable=False,
        index=True,
    )
    bank_recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_recipients.id"), nullable=False
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    bank_bin: Mapped[str] = mapped_column(String(6), nullable=False)
    account_number: Mapped[str] = mapped_column(String(19), nullable=False)
    account_name: Mapped[str | None] = mapped_column(String(255))
    confirmed_by_recipient_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    snapshotted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CollectionObligation(Base):
    """One sender-to-recipient edge with its own due date and frozen destination."""

    __tablename__ = "collection_obligations"
    __table_args__ = (
        UniqueConstraint(
            "batch_version_id",
            "sender_id",
            "recipient_id",
            name="uq_obligations_batch_sender_recipient",
        ),
        ForeignKeyConstraint(
            ["bank_recipient_snapshot_id", "batch_version_id"],
            [
                "bank_recipient_snapshots.id",
                "bank_recipient_snapshots.batch_version_id",
            ],
            name="fk_obligations_snapshot_same_batch_version",
        ),
        CheckConstraint("sender_id <> recipient_id", name="different_parties"),
        CheckConstraint("amount_vnd > 0", name="amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collection_batch_versions.id"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recipient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bank_recipient_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CollectionObligationSource(Base):
    """Normalized provenance from confirmed allocations into an obligation."""

    __tablename__ = "collection_obligation_sources"
    __table_args__ = (CheckConstraint("amount_vnd > 0", name="amount_positive"),)

    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collection_obligations.id"),
        primary_key=True,
    )
    confirmed_allocation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("confirmed_allocations.id"),
        primary_key=True,
        index=True,
    )
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CollectionEnvelope(Base):
    """One immutable capability scope for a sender in a batch version."""

    __tablename__ = "collection_envelopes"
    __table_args__ = (
        UniqueConstraint(
            "batch_version_id",
            "sender_id",
            name="uq_collection_envelopes_batch_sender",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collection_batch_versions.id"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class GuestLink(Base):
    """Rotatable bearer capability; only a SHA-256 token digest is persisted."""

    __tablename__ = "guest_links"
    __table_args__ = (
        UniqueConstraint("rotated_from_id", name="uq_guest_links_rotated_from"),
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    envelope_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collection_envelopes.id"),
        nullable=False,
        index=True,
    )
    token_digest: Mapped[bytes] = mapped_column(
        LargeBinary(32), nullable=False, unique=True
    )
    status: Mapped[GuestLinkStatus] = mapped_column(
        _enum_type(GuestLinkStatus, "guest_link_status"),
        nullable=False,
        default=GuestLinkStatus.ACTIVE,
        server_default=GuestLinkStatus.ACTIVE.value,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    capability_exposed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    first_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rotated_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guest_links.id")
    )


class PaymentReport(Base):
    """Append-only sender report; it never settles an obligation by itself."""

    __tablename__ = "payment_reports"
    __table_args__ = (
        UniqueConstraint(
            "id", "obligation_id", name="uq_payment_reports_id_obligation"
        ),
        CheckConstraint("amount_vnd > 0", name="amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collection_obligations.id"),
        nullable=False,
        index=True,
    )
    guest_link_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guest_links.id")
    )
    reported_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True
    )
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ReceiptConfirmation(Base):
    """Append-only recipient confirmation carrying an explicit VND amount."""

    __tablename__ = "receipt_confirmations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["payment_report_id", "obligation_id"],
            ["payment_reports.id", "payment_reports.obligation_id"],
            name="fk_receipt_confirmations_report_same_obligation",
        ),
        CheckConstraint("amount_vnd > 0", name="amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collection_obligations.id"),
        nullable=False,
        index=True,
    )
    payment_report_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    confirmed_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True
    )
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IdempotencyKey(Base):
    """One row per write request the server has agreed to perform.

    The unique constraint is the whole mechanism: reservation is a single
    `INSERT ... ON CONFLICT DO NOTHING`, so exactly one caller can win the race
    for a key no matter how many processes are serving requests. The recorded
    response is kept as raw bytes and replayed verbatim, because re-serialising
    it would let a later schema change silently answer an old request with a
    different body.
    """

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "scope", "idempotency_key", name="uq_idempotency_keys_scope_key"
        ),
        CheckConstraint(
            "(response_status IS NULL) = (completed_at IS NULL)",
            name="completion_is_all_or_nothing",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Text rather than a UUID foreign key: an unauthenticated write has no
    # actor, and a key must never be readable across people.
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[bytes | None] = mapped_column(LargeBinary)
    response_media_type: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    """Append-only record of material actions and transitions."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    event_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = [
    "AuditEvent",
    "BankRecipient",
    "BankRecipientSnapshot",
    "CollectionBatch",
    "CollectionBatchStatus",
    "CollectionBatchVersion",
    "CollectionEnvelope",
    "CollectionObligation",
    "CollectionObligationSource",
    "ConfirmedAllocation",
    "Expense",
    "ExpenseVersion",
    "GuestLink",
    "GuestLinkStatus",
    "IdempotencyKey",
    "MembershipOrigin",
    "MembershipRole",
    "Memory",
    "Message",
    "MessageKind",
    "Outing",
    "OutingInvite",
    "OutingInviteSource",
    "OutingStop",
    "PayerAcknowledgement",
    "PaymentReport",
    "ReceiptConfirmation",
    "UploadedImage",
    "VerificationScope",
    "Vote",
    "VoteBallot",
    "VoteOption",
]


class MembershipState(StrEnum):
    """Where a person stands in a group.

    `INVITED` exists because being added to a group is something that happens
    to you. Section 9 treats membership as a permission boundary, and a
    boundary somebody was placed inside without agreeing is not one.
    """

    INVITED = "invited"
    ACTIVE = "active"
    LEFT = "left"


class MembershipRole(StrEnum):
    MEMBER = "member"
    ADMIN = "admin"


class MembershipOrigin(StrEnum):
    """Preserve why an invited membership exists.

    A named invitation identifies someone chosen by an existing member, while
    a link request proves only possession of a forwardable bearer token. The
    `is_invitee` predicate is true in both cases, so it cannot distinguish
    these different trust levels without durable provenance.
    """

    NAMED = "named"
    LINK = "link"


class OutingInviteSource(StrEnum):
    GROUP = "group"
    FRIEND = "friend"
    LINK = "link"


class MessageKind(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    AI_CARD = "ai_card"


class Person(Base):
    """One human being, stable across groups and across display names.

    Identity is an id, never a name. Two friends called Nam are two people, and
    anything keyed by name collapses them into one -- which in this product
    means one of them silently stops owing money. The mobile client learned the
    same lesson the same way.

    `display_name` is what a person is shown as. It can change, it can repeat
    inside one group, and nothing may be derived from it.
    """

    __tablename__ = "people"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Context(Base):
    """A group of people who share expenses.

    Called `context` because every table that already references one calls it
    `context_id` -- and those columns were plain UUIDs pointing at nothing.
    An id with no table behind it looks like a relationship and enforces
    nothing: any UUID was a valid group, including one nobody belongs to.

    Renaming to `group` would read better and would touch eighteen tables and
    a migration for a word. The columns stay; what changes is that they now
    point somewhere.
    """

    __tablename__ = "contexts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_contexts_created_by"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Membership(Base):
    """One person's standing in one group, over time.

    Leaving is recorded, not deleted. A person who leaves still appears in the
    obligations they were part of, and erasing the membership row would leave
    those pointing at somebody who, as far as the database is concerned, was
    never in the group. Money that was owed does not stop having been owed.

    Re-joining creates a NEW row rather than reviving the old one. The two
    stretches are different facts: what someone could see during the first is
    not what they may see during the second, and one row cannot answer both.
    The partial unique index below is what makes that safe -- at most one
    membership that has not ended, per person per group. It cannot be expressed
    in a dict-backed fake, which is exactly why the PostgreSQL tests exist.
    """

    __tablename__ = "memberships"
    __table_args__ = (
        Index(
            "uq_memberships_open_per_person",
            "context_id",
            "person_id",
            unique=True,
            postgresql_where=text("left_at IS NULL"),
        ),
        Index(
            "ix_memberships_person_open",
            "person_id",
            postgresql_where=text("left_at IS NULL"),
        ),
        CheckConstraint(
            "(state = 'left') = (left_at IS NOT NULL)",
            # The convention adds the `ck_<table>_` prefix; naming it here too
            # produced `ck_memberships_ck_memberships_...`, which is how a
            # constraint name creeps toward the 63-character limit that has
            # already bitten this repo once.
            name="left_state_matches_timestamp",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contexts.id", name="fk_memberships_context"),
        nullable=False,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_memberships_person"),
        nullable=False,
    )
    state: Mapped[MembershipState] = mapped_column(
        # `_enum_type`, not a fresh `Enum(...)`. The helper passes
        # `values_callable`, which stores the enum VALUE. Declaring it by
        # hand stored the NAME instead -- `LEFT` where the check constraint
        # below looks for `left` -- so the constraint could never match and
        # leaving a group failed outright. PostgreSQL caught it; a fake
        # holding Python objects never would have.
        _enum_type(MembershipState, "membership_state"),
        nullable=False,
        default=MembershipState.INVITED,
    )
    role: Mapped[MembershipRole] = mapped_column(
        _enum_type(MembershipRole, "membership_role"),
        nullable=False,
        server_default=MembershipRole.MEMBER.value,
        default=MembershipRole.MEMBER,
    )
    origin: Mapped[MembershipOrigin] = mapped_column(
        _enum_type(MembershipOrigin, "membership_origin"),
        nullable=False,
        server_default=MembershipOrigin.NAMED.value,
        default=MembershipOrigin.NAMED,
    )
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_memberships_invited_by"),
        nullable=True,
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Outing(Base):
    """A group's trip plan anchored to calendar dates.

    The dates are plain `DATE` values with no timezone because trip dates are
    calendar facts, not instants; a timestamp would shift by seven hours
    between the phone that wrote it and a UTC server. The per-person budget is
    integer dong and only a reference figure, so nothing may refuse an action
    because a total exceeds it.
    """

    __tablename__ = "outings"
    __table_args__ = (
        CheckConstraint("ends_on >= starts_on", name="dates_in_order"),
        CheckConstraint("headcount > 0", name="headcount_positive"),
        CheckConstraint("budget_per_person_vnd >= 0", name="budget_not_negative"),
        CheckConstraint("title <> ''", name="title_not_blank"),
        Index(
            "ix_outings_context_schedule",
            "context_id",
            "starts_on",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contexts.id", name="fk_outings_context"),
        nullable=False,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_outings_created_by"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    headcount: Mapped[int] = mapped_column(Integer, nullable=False)
    budget_per_person_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OutingStop(Base):
    """One wall-clock stop in the order the group built its timeline.

    `minute_of_day` is an integer rather than a timestamp or `TIME` because a
    stop is a wall-clock time of day with no timezone at all. `position`, not
    `minute_of_day`, is the sort key because F15 preserves builder order: a bar
    placed before a cafe must stay before it even when its clock time is later.
    """

    __tablename__ = "outing_stops"
    __table_args__ = (
        UniqueConstraint("outing_id", "position", name="uq_outing_stops_position"),
        CheckConstraint("minute_of_day BETWEEN 0 AND 1439", name="minute_in_day"),
        CheckConstraint("position >= 0", name="position_not_negative"),
        CheckConstraint("label <> ''", name="label_not_blank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    outing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outings.id", name="fk_outing_stops_outing"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    minute_of_day: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    place_name: Mapped[str | None] = mapped_column(Text, nullable=True)


class OutingStopCheckin(Base):
    """One person saying they reached one stop, and the moment they said it.

    ## This table holds no location

    F46 in this product is a button, not a sensor. The row says *who* pressed
    *which stop* and *when* -- and a stop is a plan the group typed, not a
    place the phone observed. Reading the phone's GPS is F47 and is not built.

    There is deliberately no `lat`/`lng` here even though `memories` has them.
    A check-in on the memory wall stores the *catalogue's* coordinates for a
    public venue, which is a fact about a restaurant. A coordinate recorded
    against a person and a timestamp is a fact about a person's movements, and
    that is a different class of data with no way to un-share it once it is in
    a group's permanent history. The column does not exist so that no later
    change can quietly start filling it.

    ## Why the row dies with its stop

    `stop_id` cascades because `replace_outing_stops` deletes and re-inserts
    every stop on each timeline save. A check-in therefore does not survive an
    edit of the plan it refers to. That is the honest behaviour for a deleted
    stop and the WRONG behaviour for a renamed one, and the difference is not
    visible from here -- the repository cannot tell a rewrite from a removal.
    Fixing it means making the timeline save preserve unchanged stops, which
    is a change to code this file does not own. Recorded rather than hidden.
    """

    __tablename__ = "outing_stop_checkins"
    __table_args__ = (
        # The one-per-person-per-stop rule, held by the database rather than by
        # a read-then-write in Python. Two phones pressing the button in the
        # same instant both pass an `if not exists` check; only one of them
        # gets past this index.
        UniqueConstraint("stop_id", "person_id", name="uq_outing_stop_checkins_person"),
        # "Who has arrived at this stop" is the read the timeline screen makes,
        # once per stop it draws.
        Index("ix_outing_stop_checkins_stop", "stop_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    stop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "outing_stops.id",
            name="fk_outing_stop_checkins_stop",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_outing_stop_checkins_person"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OutingInvite(Base):
    """An outing invitation that never persists a bearer secret.

    Link invites persist only a SHA-256 digest. The raw token is handed to the
    minter exactly once and never stored, matching the existing guest-page
    capability shape. The partial unique index turns inviting the same person
    twice into a 409 instead of allowing a duplicate row.
    """

    __tablename__ = "outing_invites"
    __table_args__ = (
        CheckConstraint(
            "(source = 'link') = (token_digest IS NOT NULL)",
            name="link_carries_digest",
        ),
        CheckConstraint(
            "(source = 'link') = (invited_person_id IS NULL)",
            name="link_names_nobody",
        ),
        CheckConstraint(
            "(accepted_at IS NULL) = (accepted_by_id IS NULL)",
            name="acceptance_is_whole",
        ),
        CheckConstraint(
            "expires_at >= created_at",
            name="expiry_after_creation",
        ),
        Index(
            "uq_outing_invites_person",
            "outing_id",
            "invited_person_id",
            unique=True,
            postgresql_where=text("invited_person_id IS NOT NULL"),
        ),
        Index("ix_outing_invites_outing", "outing_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    outing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outings.id", name="fk_outing_invites_outing"),
        nullable=False,
    )
    source: Mapped[OutingInviteSource] = mapped_column(
        _enum_type(OutingInviteSource, "outing_invite_source"), nullable=False
    )
    invited_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_outing_invites_person"),
        nullable=True,
    )
    invited_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_outing_invites_inviter"),
        nullable=False,
    )
    token_digest: Mapped[bytes | None] = mapped_column(
        LargeBinary(32), nullable=True, unique=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_outing_invites_accepter"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class UploadedImage(Base):
    """One sanitized image with exactly one private owner."""

    __tablename__ = "uploaded_images"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(context_id, owner_person_id) = 1",
            name="image_has_one_owner",
        ),
        CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png')",
            name="content_type_allowed",
        ),
        CheckConstraint(
            "byte_size > 0 AND width > 0 AND height > 0",
            name="image_dimensions_positive",
        ),
        Index(
            "ix_uploaded_images_context",
            "context_id",
            desc("created_at"),
            postgresql_where=text("context_id IS NOT NULL"),
        ),
        Index(
            "ix_uploaded_images_avatar",
            "owner_person_id",
            desc("created_at"),
            postgresql_where=text("owner_person_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    storage_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contexts.id", name="fk_uploaded_images_context"),
        nullable=True,
    )
    owner_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_uploaded_images_owner"),
        nullable=True,
    )
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_uploaded_images_uploaded_by"),
        nullable=False,
    )
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MemoryKind(StrEnum):
    """What a row on the memory wall is a record of.

    `checkin` is F46: the group arrived somewhere, and that is a keepsake with
    coordinates and a moment instead of a photograph. It shares this table
    rather than getting its own because the wall is one timeline -- two tables
    would mean two feeds, two cursors and a merge in the reader, and the merge
    is where a check-in silently stops appearing.
    """

    PHOTO = "photo"
    CHECKIN = "checkin"


class Vote(Base):
    """A group question whose closure cannot be recorded only halfway.

    Keeping the closing actor and instant paired prevents a row from looking
    closed to one reader and open to another.  The optional outing link adds
    planning context only; a vote never participates in the financial graph.
    """

    __tablename__ = "votes"
    __table_args__ = (
        CheckConstraint("question <> ''", name="question_not_blank"),
        CheckConstraint(
            "(closed_at IS NULL) = (closed_by_id IS NULL)",
            name="closing_is_whole",
        ),
        Index(
            "ix_votes_context_created",
            "context_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contexts.id", name="fk_votes_context"),
        nullable=False,
    )
    outing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outings.id", name="fk_votes_outing"),
        nullable=True,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_votes_created_by"),
        nullable=False,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_votes_closed_by"),
        nullable=True,
    )


class VoteOption(Base):
    """A stable choice order keeps tied leaders from moving between reads."""

    __tablename__ = "vote_options"
    __table_args__ = (
        UniqueConstraint("vote_id", "position", name="uq_vote_options_position"),
        CheckConstraint("position >= 0", name="position_not_negative"),
        CheckConstraint("label <> ''", name="label_not_blank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("votes.id", name="fk_vote_options_vote"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    place_name: Mapped[str | None] = mapped_column(Text, nullable=True)


class VoteBallot(Base):
    """A changed mind replaces one row so it can never become two votes.

    The unique constraint is the authority for one-person-one-ballot even
    under concurrent requests; tallying never depends on an in-memory check.
    """

    __tablename__ = "vote_ballots"
    __table_args__ = (
        UniqueConstraint("vote_id", "voter_id", name="uq_vote_ballots_one_per_person"),
        Index("ix_vote_ballots_vote", "vote_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("votes.id", name="fk_vote_ballots_vote"),
        nullable=False,
    )
    option_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vote_options.id", name="fk_vote_ballots_option"),
        nullable=False,
    )
    voter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_vote_ballots_voter"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class Memory(Base):
    """One immutable keepsake attached to a context's private memory wall.

    A memory belongs to the context rather than its author because the group,
    not one person's continuing membership, defines the shared history.

    ## Why a check-in stores coordinates it could have looked up

    `place_id` names a row in `app/places/catalog.py`, so `place_name`, `lat`
    and `lng` are derivable from it today and are stored anyway. The catalogue
    is seed data with a stated expiry -- its own docstring says the file "gets
    replaced" when places become user-editable -- and a venue that moves, is
    renamed or is deleted would then rewrite where the group was last March.
    A keepsake that changes after the fact is not a keepsake. These five
    columns are the snapshot taken at the moment somebody pressed the button.
    """

    __tablename__ = "memories"
    __table_args__ = (
        Index(
            "ix_memories_context_feed",
            "context_id",
            desc("created_at"),
            desc("id"),
        ),
        # Check-ins are read per place ("who has been here") as well as per
        # feed, and the partial predicate keeps photo rows -- which have no
        # place -- out of an index that could never serve them.
        Index(
            "ix_memories_context_place",
            "context_id",
            "place_id",
            desc("created_at"),
            postgresql_where=text("place_id IS NOT NULL"),
        ),
        # One constraint rather than five, because the invariant is a shape and
        # not a set of independent facts: a photo has no location, a check-in
        # has no image, and a row carrying both is a row no screen knows how to
        # draw. Written the same way `messages.payload_matches_kind` is.
        CheckConstraint(
            "(kind = 'photo' AND image_url IS NOT NULL AND image_url <> '' "
            "AND place_id IS NULL AND place_name IS NULL "
            "AND lat IS NULL AND lng IS NULL) OR "
            "(kind = 'checkin' AND image_url IS NULL "
            "AND place_id IS NOT NULL AND place_id <> '' "
            "AND place_name IS NOT NULL AND place_name <> '' "
            "AND lat IS NOT NULL AND lng IS NOT NULL)",
            name="payload_matches_kind",
        ),
        # A coordinate outside these ranges is not a place on Earth, and the
        # map strip would draw it somewhere plausible-looking anyway.
        CheckConstraint("lat IS NULL OR lat BETWEEN -90 AND 90", name="lat_range"),
        CheckConstraint("lng IS NULL OR lng BETWEEN -180 AND 180", name="lng_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contexts.id", name="fk_memories_context"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_memories_author"),
        nullable=False,
    )
    # `server_default` exists so the rows written before F46 became photos
    # without the migration having to guess. New rows always name their kind;
    # a write that forgot to would land on 'photo' and then be refused by the
    # payload constraint above rather than stored as the wrong thing.
    kind: Mapped[MemoryKind] = mapped_column(
        _enum_type(MemoryKind, "memory_kind"),
        nullable=False,
        server_default=MemoryKind.PHOTO.value,
    )
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    place_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    place_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MemoryReaction(Base):
    """F40. One person, one memory, one heart.

    ## Why the uniqueness lives here and not in a read

    The mockup draws "❤️ 18" -- a count. A count computed by a reader that
    de-duplicates on the way out looks identical to a correct one until two
    devices press the heart in the same second, and then the wall says 19 for
    a photograph eighteen people liked. `uq_memory_reactions_person` is the
    rule; the writer attempts the insert and lets the index answer, the same
    way `OutingStopCheckin` does.

    ## There is no `kind`

    One reaction, spelled one way. A `kind` column would be the seed of an
    emoji palette nobody has designed, and every row written before that
    design would have to be migrated into whichever default it picked.

    ## The row dies with the memory it is about

    `ON DELETE CASCADE`: a heart on a deleted photograph is a count attached
    to nothing, and there is no screen that could ever draw it.
    """

    __tablename__ = "memory_reactions"
    __table_args__ = (
        UniqueConstraint("memory_id", "person_id", name="uq_memory_reactions_person"),
        # "How many hearts does this row have, and did I leave one" is the read
        # the wall makes, once per memory it draws.
        Index("ix_memory_reactions_memory", "memory_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "memories.id", name="fk_memory_reactions_memory", ondelete="CASCADE"
        ),
        nullable=False,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_memory_reactions_person"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MemoryComment(Base):
    """F41. What somebody said under a photograph on the group's own wall.

    ## This body is group-private data

    It is written by a member, addressed to a group, and read only behind the
    same `view_group_memories` gate the wall itself is behind. It is at the
    rank of a phone number: it never reaches a log line, an exception message
    or the guest page. The guest page matters specifically -- that link is a
    bearer capability held by somebody outside the group, and its view model
    (`app/web/guest_view.py`) is a whitelist for exactly this reason.

    ## No `edited_at`, no soft delete

    A comment is either there or it is not. An edit history on a sentence in a
    friend group is a feature with a privacy question attached, and answering
    it is not what F41 asks for. Recorded rather than hidden.
    """

    __tablename__ = "memory_comments"
    __table_args__ = (
        CheckConstraint("body <> ''", name="body_not_blank"),
        # The read is "this memory's comments, oldest first" -- a conversation
        # under a photograph runs forward, unlike the feed above it.
        Index("ix_memory_comments_memory", "memory_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", name="fk_memory_comments_memory", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_memory_comments_author"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Message(Base):
    """One immutable entry in a context's conversation feed."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'text' AND body IS NOT NULL AND image_url IS NULL "
            "AND card IS NULL) OR "
            "(kind = 'image' AND image_url IS NOT NULL AND card IS NULL) OR "
            "(kind = 'ai_card' AND card IS NOT NULL AND image_url IS NULL "
            "AND body IS NULL)",
            name="payload_matches_kind",
        ),
        CheckConstraint(
            "kind = 'ai_card' OR author_id IS NOT NULL",
            name="human_kinds_have_author",
        ),
        Index(
            "ix_messages_context_feed",
            "context_id",
            desc("created_at"),
            desc("id"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contexts.id", name="fk_messages_context_id"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_messages_author_id"),
        nullable=True,
    )
    kind: Mapped[MessageKind] = mapped_column(
        _enum_type(MessageKind, "message_kind"), nullable=False
    )
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # `none_as_null` is not decoration. SQLAlchemy defaults it to False, which
    # stores Python `None` as the JSON value `null` rather than SQL NULL -- so
    # `card IS NULL` is false for a text message, and the payload check
    # constraint below rejects every ordinary message. psycopg prints both as
    # `null` in the error detail, so the two are indistinguishable in the log
    # that is supposed to explain the rejection.
    card: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FriendRequestState(StrEnum):
    """F04's four states, spelled the way the spec spells them.

    Stored rather than derived because the transition itself is the fact worth
    keeping: "Binh declined on Tuesday" and "Binh never answered" are different
    events, and a schema that only records current friendship cannot tell them
    apart when somebody asks why a name stopped appearing.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    BLOCKED = "blocked"


class FriendRequest(Base):
    """One directed ask between two people, and its answer.

    Friendship is not a column anywhere. It is `state = 'accepted'` on a row of
    this table, read through `app.domain.friendship.are_friends`. The same
    reasoning as invariant 3 for money: a relationship that is stored
    separately from the events that created it will eventually disagree with
    them, and the disagreement surfaces as one screen showing a friend another
    screen does not.

    `requester_id` and `addressee_id` keep their direction after the answer.
    Losing it would lose the only thing that makes the consent rule checkable
    after the fact -- with an undirected row, "the addressee accepted" is not a
    statement anybody can verify.
    """

    __tablename__ = "friend_requests"
    __table_args__ = (
        CheckConstraint(
            "requester_id <> addressee_id",
            # `pair_key` raises SELF_EDGE for the same reason. The domain
            # refuses it, this makes the refusal true of the data even if some
            # future writer skips the domain.
            name="no_self_friendship",
        ),
        CheckConstraint(
            "(state = 'pending') = (decided_at IS NULL)",
            name="decided_state_matches_timestamp",
        ),
        # At most one LIVE edge per unordered pair. `least`/`greatest` are what
        # make (A,B) and (B,A) the same key, so two people who tap "add" at the
        # same moment produce one row and one conflict rather than two pending
        # requests that can both be accepted into two friendships.
        #
        # This mirrors `app.domain.friendship.pair_key`, which sorts the same
        # two values in Python. Two spellings of one rule: change either and
        # change both. `tests/postgres/test_friend_requests_postgres.py` is
        # where the SQL spelling is actually exercised -- a dict-backed fake
        # cannot express a functional partial unique index, so the API-level
        # tests are blind to it by construction.
        Index(
            "uq_friend_edge_live",
            text("least(requester_id, addressee_id)"),
            text("greatest(requester_id, addressee_id)"),
            unique=True,
            postgresql_where=text("state IN ('pending', 'accepted', 'blocked')"),
        ),
        Index("ix_friend_requests_addressee", "addressee_id", "state"),
        Index("ix_friend_requests_requester", "requester_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_friend_requests_requester"),
        nullable=False,
    )
    addressee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_friend_requests_addressee"),
        nullable=False,
    )
    state: Mapped[FriendRequestState] = mapped_column(
        _enum_type(FriendRequestState, "friend_request_state"), nullable=False
    )
    #: Who answered. Null while pending. This is the audit trail for the
    #: consent rule: an accepted row whose `decided_by_id` is the requester is
    #: evidence of the bug this feature is built to make impossible.
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", name="fk_friend_requests_decided_by"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
