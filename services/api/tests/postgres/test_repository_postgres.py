"""Execute the production SQLAlchemy repository on PostgreSQL 16 or newer."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, inspect, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.api.repository import (
    GuestLinkDraft,
    ObligationDraft,
    SqlAlchemyApiRepository,
)
from app.api.schemas import ExpenseInput
from app.db.models import (
    AuditEvent,
    BankRecipient,
    BankRecipientSnapshot,
    CollectionBatch,
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
    PaymentReport,
    ReceiptConfirmation,
)

pytestmark = pytest.mark.postgres

NOW = datetime(2030, 8, 27, 12, tzinfo=UTC)
TOTAL_VND = 80_000
OBLIGATION_VND = 40_000
ORIGINAL_ACCOUNT = "TESTACCOUNT001"
CHANGED_ACCOUNT = "TESTACCOUNT002"


@dataclass(frozen=True, slots=True)
class LifecycleState:
    context_id: uuid.UUID
    owner_id: uuid.UUID
    sender_id: uuid.UUID
    recipient_id: uuid.UUID
    expense_version_id: uuid.UUID
    batch_id: uuid.UUID
    batch_version_id: uuid.UUID
    obligation_id: uuid.UUID
    source_allocation_id: uuid.UUID
    token_digest: bytes
    payment_report_id: uuid.UUID
    receipt_confirmation_ids: tuple[uuid.UUID, uuid.UUID]


def _proposal(
    *,
    context_id: uuid.UUID,
    owner_id: uuid.UUID,
    sender_id: uuid.UUID,
    recipient_id: uuid.UUID,
) -> ExpenseInput:
    return ExpenseInput(
        context_id=context_id,
        description="Synthetic dinner",
        recorded_by_id=owner_id,
        paid_by_id=recipient_id,
        verification_scope="items_reviewed",
        occurred_at=NOW,
        participants=[sender_id, recipient_id],
        total_amount_vnd=TOTAL_VND,
        items=[
            {
                "item_id": "meal",
                "label": "Synthetic meal",
                "amount_vnd": TOTAL_VND,
                "shared_by": [sender_id, recipient_id],
            }
        ],
        surcharges=[
            {
                "surcharge_id": "service",
                "kind": "service",
                "amount_vnd": 2_000,
                "mode": "even",
            }
        ],
        discounts=[
            {
                "discount_id": "voucher",
                "amount_vnd": 2_000,
                "scope": "global_proportional",
                "item_id": None,
            }
        ],
    )


def _persist_lifecycle(session: Session) -> LifecycleState:
    repository = SqlAlchemyApiRepository(session)
    context_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    sender_id = uuid.uuid4()
    recipient_id = uuid.uuid4()
    proposal = _proposal(
        context_id=context_id,
        owner_id=owner_id,
        sender_id=sender_id,
        recipient_id=recipient_id,
    )

    expense = repository.create_expense(context_id)
    assert repository.get_expense(expense.id) == expense
    confirmation = repository.save_expense_confirmation(
        expense_id=expense.id,
        proposal=proposal,
        allocator_expense={"warnings": []},
        rollups={
            "subtotal_amount_vnd": TOTAL_VND,
            "fee_amount_vnd": 2_000,
            "vat_amount_vnd": 0,
            "shipping_amount_vnd": 0,
            "discount_amount_vnd": 2_000,
            "total_amount_vnd": TOTAL_VND,
        },
        allocations={sender_id: OBLIGATION_VND, recipient_id: OBLIGATION_VND},
        confirmed_by_id=owner_id,
        payer_acknowledgement="acknowledged",
        now=NOW,
    )

    batch_inputs = repository.load_batch_inputs(
        context_id, (confirmation.expense_version_id,)
    )
    assert batch_inputs.unavailable_version_ids == ()
    source = next(
        row
        for row in batch_inputs.expenses[0].allocations
        if row.participant_id == sender_id
    )

    bank_recipient = BankRecipient(
        recipient_id=recipient_id,
        bank_bin="970415",
        account_number=ORIGINAL_ACCOUNT,
        account_name="SYNTHETIC RECIPIENT",
        confirmed_by_recipient_at=NOW,
        created_at=NOW,
    )
    session.add(bank_recipient)
    session.flush()
    bank_recipients = repository.load_bank_recipients(frozenset({recipient_id}))

    frozen = repository.save_frozen_batch(
        context_id=context_id,
        owner_id=owner_id,
        due_at=NOW + timedelta(days=7),
        obligations=(
            ObligationDraft(
                sender_id=sender_id,
                recipient_id=recipient_id,
                amount_vnd=OBLIGATION_VND,
                source_expense_version_ids=(confirmation.expense_version_id,),
                sources=(source,),
            ),
        ),
        bank_recipients=bank_recipients,
        now=NOW + timedelta(minutes=1),
    )
    batch = repository.load_batch_for_publish(frozen.id)
    assert batch is not None
    assert batch.advancer_acknowledged is True
    assert batch.bank_recipient_snapshot_valid is True

    # A later bank-recipient edit must not change the destination frozen into
    # this batch version.
    bank_recipient.account_number = CHANGED_ACCOUNT
    session.flush()

    token_digest = hashlib.sha256(b"synthetic repository integration token").digest()
    stored_links = repository.save_published_batch(
        batch=batch,
        status="published",
        links=(
            GuestLinkDraft(
                sender_id=sender_id,
                token_digest=token_digest,
                expires_at=NOW + timedelta(days=30),
            ),
        ),
        actor_id=owner_id,
        now=NOW + timedelta(minutes=2),
    )
    assert len(stored_links) == 1

    envelope = repository.get_guest_envelope(token_digest, NOW + timedelta(minutes=3))
    assert envelope is not None
    assert envelope.envelope["obligations"][0]["account_number"] == ORIGINAL_ACCOUNT

    report_target = repository.get_payment_report_target(
        token_digest,
        frozen.obligations[0].id,
        NOW + timedelta(minutes=4),
    )
    assert report_target is not None
    assert report_target.active_capability is True
    assert report_target.reports_used == 0
    report_key = uuid.uuid4()
    report = repository.save_payment_report(
        target=report_target,
        idempotency_key=report_key,
        now=NOW + timedelta(minutes=5),
    )
    repeated_report = repository.save_payment_report(
        target=report_target,
        idempotency_key=report_key,
        now=NOW + timedelta(minutes=6),
    )
    assert repeated_report.id == report.id

    receipt_target = repository.get_receipt_target(frozen.obligations[0].id)
    assert receipt_target is not None
    first_receipt_key = uuid.uuid4()
    first_receipt = repository.save_receipt_confirmation(
        target=receipt_target,
        confirmed_by_id=recipient_id,
        amount_vnd=15_000,
        payment_report_id=report.id,
        idempotency_key=first_receipt_key,
        now=NOW + timedelta(minutes=7),
    )
    repeated_receipt = repository.save_receipt_confirmation(
        target=receipt_target,
        confirmed_by_id=recipient_id,
        amount_vnd=15_000,
        payment_report_id=report.id,
        idempotency_key=first_receipt_key,
        now=NOW + timedelta(minutes=8),
    )
    assert repeated_receipt.id == first_receipt.id
    second_receipt = repository.save_receipt_confirmation(
        target=receipt_target,
        confirmed_by_id=recipient_id,
        amount_vnd=25_000,
        payment_report_id=None,
        idempotency_key=uuid.uuid4(),
        now=NOW + timedelta(minutes=9),
    )
    assert second_receipt.receipt_amounts_vnd == (15_000, 25_000)
    session.flush()

    return LifecycleState(
        context_id=context_id,
        owner_id=owner_id,
        sender_id=sender_id,
        recipient_id=recipient_id,
        expense_version_id=confirmation.expense_version_id,
        batch_id=frozen.id,
        batch_version_id=frozen.version_id,
        obligation_id=frozen.obligations[0].id,
        source_allocation_id=source.id,
        token_digest=token_digest,
        payment_report_id=report.id,
        receipt_confirmation_ids=(first_receipt.id, second_receipt.id),
    )


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None)


def test_suite_really_uses_postgresql_16_or_newer(postgres_session: Session):
    assert postgres_session.bind is not None
    assert postgres_session.bind.dialect.name == "postgresql"
    version_number = int(
        postgres_session.scalar(text("select current_setting('server_version_num')"))
    )
    assert version_number >= 160_000


def test_repository_lifecycle_reaches_confirmed_receipt(postgres_session: Session):
    state = _persist_lifecycle(postgres_session)
    repository = SqlAlchemyApiRepository(postgres_session)

    progress = (
        postgres_session.execute(
            text(
                """
            select amount_vnd, confirmed_amount_vnd, remaining_amount_vnd,
                   confirmation_state
            from collection_obligation_progress
            where obligation_id = :obligation_id
            """
            ),
            {"obligation_id": state.obligation_id},
        )
        .mappings()
        .one()
    )
    assert dict(progress) == {
        "amount_vnd": OBLIGATION_VND,
        "confirmed_amount_vnd": OBLIGATION_VND,
        "remaining_amount_vnd": 0,
        "confirmation_state": "confirmed",
    }

    envelope = repository.get_guest_envelope(
        state.token_digest, NOW + timedelta(minutes=10)
    )
    assert envelope is not None
    block = envelope.envelope["obligations"][0]
    assert block["already_reported"] is True
    assert block["receiver_confirmed"] is True
    assert block["account_number"] == ORIGINAL_ACCOUNT

    unavailable = repository.load_batch_inputs(
        state.context_id, (state.expense_version_id,)
    )
    assert unavailable.expenses == ()
    assert unavailable.unavailable_version_ids == (state.expense_version_id,)

    event_types = tuple(
        postgres_session.scalars(
            select(AuditEvent.event_type).order_by(AuditEvent.occurred_at)
        )
    )
    assert event_types == (
        "expense_confirmed",
        "collection_batch_frozen",
        "collection_batch_published",
        "payment_reported",
        "receipt_confirmed",
        "receipt_confirmed",
    )


def test_partial_unique_index_allows_only_one_active_bank_destination(
    postgres_session: Session,
):
    state = _persist_lifecycle(postgres_session)

    with pytest.raises(IntegrityError) as caught:
        with postgres_session.begin_nested():
            postgres_session.add(
                BankRecipient(
                    recipient_id=state.recipient_id,
                    bank_bin="970415",
                    account_number="TESTACCOUNT003",
                    account_name="SYNTHETIC DUPLICATE",
                    confirmed_by_recipient_at=NOW,
                    created_at=NOW,
                )
            )
            postgres_session.flush()
    assert _constraint_name(caught.value) == "uq_bank_recipients_active_recipient"

    with postgres_session.begin_nested():
        postgres_session.add(
            BankRecipient(
                recipient_id=state.recipient_id,
                bank_bin="970415",
                account_number="TESTACCOUNT004",
                account_name="SYNTHETIC REVOKED",
                confirmed_by_recipient_at=NOW,
                created_at=NOW,
                revoked_at=NOW + timedelta(minutes=1),
            )
        )
        postgres_session.flush()


def test_receipt_report_must_belong_to_the_same_obligation(
    postgres_session: Session,
):
    state = _persist_lifecycle(postgres_session)
    first_obligation = postgres_session.get(CollectionObligation, state.obligation_id)
    assert first_obligation is not None

    second_obligation = CollectionObligation(
        batch_version_id=state.batch_version_id,
        sender_id=uuid.uuid4(),
        recipient_id=state.recipient_id,
        amount_vnd=1_000,
        due_at=NOW + timedelta(days=7),
        bank_recipient_snapshot_id=first_obligation.bank_recipient_snapshot_id,
        created_at=NOW,
    )
    postgres_session.add(second_obligation)
    postgres_session.flush()

    with pytest.raises(IntegrityError) as caught:
        with postgres_session.begin_nested():
            postgres_session.add(
                ReceiptConfirmation(
                    obligation_id=second_obligation.id,
                    payment_report_id=state.payment_report_id,
                    confirmed_by_id=state.recipient_id,
                    amount_vnd=1_000,
                    idempotency_key=uuid.uuid4(),
                    confirmed_at=NOW,
                )
            )
            postgres_session.flush()
    assert (
        _constraint_name(caught.value)
        == "fk_receipt_confirmations_report_same_obligation"
    )


def test_every_material_fact_table_rejects_in_place_updates(
    postgres_session: Session,
):
    _persist_lifecycle(postgres_session)
    cases = (
        (ExpenseVersion, "description"),
        (ExpenseItem, "label"),
        (ExpenseItemShare, "participant_id"),
        (ExpenseSurcharge, "kind"),
        (ExpenseDiscount, "amount_vnd"),
        (ConfirmedAllocation, "amount_vnd"),
        (CollectionBatchVersion, "created_at"),
        (BankRecipientSnapshot, "account_name"),
        (CollectionObligation, "amount_vnd"),
        (CollectionObligationSource, "amount_vnd"),
        (CollectionEnvelope, "created_at"),
        (PaymentReport, "amount_vnd"),
        (ReceiptConfirmation, "amount_vnd"),
        (AuditEvent, "event_type"),
    )

    for model, column_name in cases:
        row = postgres_session.scalar(select(model).limit(1))
        assert row is not None, model.__tablename__
        predicate = [
            getattr(model, column.key) == getattr(row, column.key)
            for column in inspect(model).primary_key
        ]
        try:
            with postgres_session.begin_nested():
                postgres_session.execute(
                    update(model)
                    .where(*predicate)
                    .values({column_name: getattr(row, column_name)})
                )
                postgres_session.flush()
        except DBAPIError as error:
            assert _sqlstate(error) == "55000", model.__tablename__
        else:
            pytest.fail(f"{model.__tablename__} accepted an in-place update")
        postgres_session.expire_all()


def test_append_only_trigger_rejects_delete(postgres_session: Session):
    state = _persist_lifecycle(postgres_session)
    receipt = postgres_session.get(
        ReceiptConfirmation, state.receipt_confirmation_ids[0]
    )
    assert receipt is not None

    with pytest.raises(DBAPIError) as caught:
        with postgres_session.begin_nested():
            postgres_session.delete(receipt)
            postgres_session.flush()
    assert _sqlstate(caught.value) == "55000"


def test_expected_rows_exist_in_real_tables(postgres_session: Session):
    _persist_lifecycle(postgres_session)
    expected_counts = {
        Expense: 1,
        ExpenseVersion: 1,
        ExpenseItem: 1,
        ExpenseItemShare: 2,
        ExpenseSurcharge: 1,
        ExpenseDiscount: 1,
        ConfirmedAllocation: 2,
        CollectionBatch: 1,
        CollectionBatchVersion: 1,
        BankRecipient: 1,
        BankRecipientSnapshot: 1,
        CollectionObligation: 1,
        CollectionObligationSource: 1,
        CollectionEnvelope: 1,
        GuestLink: 1,
        PaymentReport: 1,
        ReceiptConfirmation: 2,
        AuditEvent: 6,
    }
    for model, expected in expected_counts.items():
        count = postgres_session.scalar(select(func.count()).select_from(model))
        assert count == expected, model.__tablename__
