"""SQLAlchemy models for the first expense-to-collection vertical slice.

Money is represented exclusively as integer Vietnamese dong. Financial facts and
batch compositions are append-only; the first migration enforces that property for
the corresponding tables at the PostgreSQL layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
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


def _enum_type(enum_class: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_class,
        values_callable=lambda members: [member.value for member in members],
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )


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
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
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
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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
        UniqueConstraint("expense_version_id", "item_key", name="uq_expense_items_version_key"),
        # ADR-0004 rejects a zero-amount line item (ZERO_AMOUNT) even though a
        # zero-amount expense total is fine.
        CheckConstraint("amount_vnd > 0", name="amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expense_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expense_versions.id"), nullable=False, index=True
    )
    item_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ExpenseItemShare(Base):
    """Which participant shares which item. The `shared_by` set of ADR-0004."""

    __tablename__ = "expense_item_shares"
    __table_args__ = (
        UniqueConstraint("expense_item_id", "participant_id", name="uq_item_share_unique"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expense_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expense_items.id"), nullable=False, index=True
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExpenseSurcharge(Base):
    """A fee, VAT or shipping line, WITH its distribution mode.

    Added under review blocker D-03. The flat `fee_amount_vnd` columns cannot
    express mode: two expenses with identical totals but different modes
    allocate differently (golden G10 gives {a: 66000, b: 44000} proportional
    and {a: 65000, b: 45000} even). Storing them identically loses money facts.
    """

    __tablename__ = "expense_surcharges"
    __table_args__ = (
        UniqueConstraint("expense_version_id", "surcharge_key", name="uq_surcharges_version_key"),
        CheckConstraint("amount_vnd > 0", name="amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expense_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expense_versions.id"), nullable=False, index=True
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
        UniqueConstraint("expense_version_id", "discount_key", name="uq_discounts_version_key"),
        CheckConstraint("amount_vnd > 0", name="amount_positive"),
        # ADR-0004 SCOPE_TARGET_MISMATCH: an item-scoped discount needs a
        # target and a global one must not carry one.
        CheckConstraint(
            "(scope = 'item' AND target_item_id IS NOT NULL) OR "
            "(scope = 'global_proportional' AND target_item_id IS NULL)",
            name="scope_target_match",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expense_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expense_versions.id"), nullable=False, index=True
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
    participant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    confirmed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
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
            ["collection_batch_versions.batch_id", "collection_batch_versions.version_number"],
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
            ["bank_recipient_snapshots.id", "bank_recipient_snapshots.batch_version_id"],
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
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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
    confirmed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
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
        UniqueConstraint("scope", "idempotency_key", name="uq_idempotency_keys_scope_key"),
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
    "MembershipRole",
    "Message",
    "MessageKind",
    "PayerAcknowledgement",
    "PaymentReport",
    "ReceiptConfirmation",
    "VerificationScope",
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
        UUID(as_uuid=True), ForeignKey("people.id", name="fk_contexts_created_by"),
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
        Index("ix_memberships_person_open", "person_id", postgresql_where=text("left_at IS NULL")),
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
