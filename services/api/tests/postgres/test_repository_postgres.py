"""Execute the production SQLAlchemy repository on PostgreSQL 16 or newer."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import anyio
import httpx
import pytest
from sqlalchemy import func, inspect, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.main import create_app
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
GUEST_TOKEN = "synthetic_repository_integration_token"
KNOWN_BANK_BIN = "970407"


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


def _persist_lifecycle(
    session: Session, *, confirm_receipts: bool = True
) -> LifecycleState:
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
        bank_bin=KNOWN_BANK_BIN,
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

    token_digest = hashlib.sha256(GUEST_TOKEN.encode()).digest()
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
    if not confirm_receipts:
        # An obligation nobody has confirmed yet -- the only state in which a
        # dispute can still stop anything.
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
            receipt_confirmation_ids=(),
        )
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


def test_guest_http_uses_name_derived_from_real_postgres_projection(
    postgres_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    state = _persist_lifecycle(postgres_session)
    repository = SqlAlchemyApiRepository(postgres_session)
    envelope = repository.get_guest_envelope(
        state.token_digest, NOW + timedelta(minutes=10)
    )
    assert envelope is not None
    assert envelope.envelope["obligations"][0]["bank_bin"] == KNOWN_BANK_BIN

    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW + timedelta(minutes=10))
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repository

    async def get_page():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(f"/g/{GUEST_TOKEN}")

    response = anyio.run(get_page)

    assert response.status_code == 200
    assert "Techcombank" in response.text
    assert f"Ngân hàng {KNOWN_BANK_BIN}" not in response.text


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


def test_money_that_already_arrived_outranks_a_late_objection(
    postgres_session: Session,
):
    """PR11-03, and a rule the real database made me state out loud.

    The lifecycle fixture ends with the obligation fully confirmed: 15.000 plus
    25.000 against a 40.000 obligation. I first asserted that an objection here
    flips it to `disputed`, and PostgreSQL said no -- correctly. Once an
    obligation is confirmed there is nothing left to collect, so marking it
    disputed would stop a collection that already ended and hide a payment that
    already happened. A disagreement after the fact is a conversation, not a
    collection state.

    The fake let the wrong expectation through. This is the layer that did not.
    """
    state = _persist_lifecycle(postgres_session)
    repository = SqlAlchemyApiRepository(postgres_session)

    repository.save_guest_objection(
        token_digest=state.token_digest,
        kind="wrong_amount",
        obligation_id=state.obligation_id,
        reason="amount_too_high",
        now=NOW + timedelta(minutes=12),
    )
    postgres_session.flush()

    rows = repository.list_batch_obligations(state.batch_id)
    assert rows is not None, "the collection board could not find the batch"
    target = [row for row in rows if row.obligation_id == state.obligation_id]
    assert target, "the obligation vanished from the board"
    assert target[0].status == "confirmed"
    # The objection is not lost -- it is recorded and readable, it just does
    # not reopen a settled obligation.
    assert target[0].disputed_reason == "amount_too_high"


def test_an_objection_disputes_an_outstanding_obligation_in_postgres(
    postgres_session: Session,
):
    """The case that actually stops a collection round.

    A wrong-amount objection is stored as an audit event and read back as a
    derived status. Nothing about that is exercised by a dict-backed fake: it
    depends on JSONB `event_data` round-tripping and on the query that filters
    events by aggregate. Both are SQL, and SQL is what the fake cannot have.
    """
    state = _persist_lifecycle(postgres_session, confirm_receipts=False)
    repository = SqlAlchemyApiRepository(postgres_session)

    before = repository.list_batch_obligations(state.batch_id)
    assert before is not None
    assert [row.status for row in before] == ["outstanding"]

    repository.save_guest_objection(
        token_digest=state.token_digest,
        kind="wrong_amount",
        obligation_id=state.obligation_id,
        reason="amount_too_high",
        now=NOW + timedelta(minutes=12),
    )
    postgres_session.flush()

    after = repository.list_batch_obligations(state.batch_id)
    assert after is not None
    target = [row for row in after if row.obligation_id == state.obligation_id]
    assert target and target[0].status == "disputed"
    assert target[0].disputed_reason == "amount_too_high"

    envelope = repository.get_guest_envelope(
        state.token_digest, NOW + timedelta(minutes=13)
    )
    assert envelope is not None
    block = [
        item
        for item in envelope.envelope["obligations"]
        if item["obligation_id"] == str(state.obligation_id)
    ][0]
    assert block["disputed"] is True


def test_asking_for_the_calculation_never_makes_an_obligation_disputed(
    postgres_session: Session,
):
    """`evidence_request` is a question, not an objection. Storing both as
    audit events makes it easy to widen one query by accident and turn asking
    how a number was reached into a dispute -- which would teach a group not
    to ask."""
    state = _persist_lifecycle(postgres_session)
    repository = SqlAlchemyApiRepository(postgres_session)

    repository.save_guest_objection(
        token_digest=state.token_digest,
        kind="evidence_request",
        obligation_id=state.obligation_id,
        reason=None,
        now=NOW + timedelta(minutes=2),
    )
    postgres_session.flush()

    envelope = repository.get_guest_envelope(
        state.token_digest, NOW + timedelta(minutes=3)
    )
    assert envelope is not None
    block = [
        item
        for item in envelope.envelope["obligations"]
        if item["obligation_id"] == str(state.obligation_id)
    ][0]
    assert block["disputed"] is False
    assert block["evidence_requested"] is True
    assert envelope.envelope["objections_used"] == 0
