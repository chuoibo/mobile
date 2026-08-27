"""Stateful fake repository for API tests.

SQLite is deliberately not used: the production schema relies on PostgreSQL
JSONB, regex checks, partial indexes, views, and append-only triggers. SQLite
would turn a green test into a false claim about those guarantees. This fake
tests HTTP/domain orchestration only; static tests cover migration/model parity,
while ``tests/postgres`` executes the production adapter and constraints on a
real PostgreSQL server.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime

import anyio
import httpx
import pytest

from app.api.deps import get_repository
from app.api.errors import RepositoryConflict
from app.api.main import create_app
from app.api.repository import (
    AllocationRow,
    BankRecipientRecord,
    BatchForPublish,
    BatchInputs,
    ConfirmationRecord,
    ConfirmedExpense,
    ExpenseIdentity,
    FrozenBatch,
    FrozenObligation,
    GuestEnvelopeRecord,
    GuestLinkDraft,
    ObligationDraft,
    PaymentReportRecord,
    PaymentReportTarget,
    PublishObligation,
    ReceiptRecord,
    ReceiptTarget,
    StoredGuestLink,
)
from app.domain.capability import capability_scope
from app.domain.ledger import obligation_status
from app.payments.vietqr import build_payload


@dataclass(slots=True)
class FakeLink:
    id: uuid.UUID
    sender_id: uuid.UUID
    batch_id: uuid.UUID
    expires_at: datetime
    status: str = "active"


@dataclass(slots=True)
class FakeReport:
    id: uuid.UUID
    link_id: uuid.UUID
    obligation_id: uuid.UUID
    amount_vnd: int
    idempotency_key: uuid.UUID


@dataclass(slots=True)
class FakeReceipt:
    id: uuid.UUID
    obligation_id: uuid.UUID
    confirmed_by_id: uuid.UUID
    amount_vnd: int
    payment_report_id: uuid.UUID | None
    idempotency_key: uuid.UUID


class FakeRepository:
    REPORT_LIMIT = 3

    def __init__(self):
        self.expenses: dict[uuid.UUID, ExpenseIdentity] = {}
        self.confirmed: dict[uuid.UUID, ConfirmedExpense] = {}
        self.version_to_expense: dict[uuid.UUID, uuid.UUID] = {}
        self.version_numbers: dict[uuid.UUID, int] = {}
        self.bank_recipients: dict[uuid.UUID, BankRecipientRecord] = {}
        self.batched_versions: set[uuid.UUID] = set()
        self.batches: dict[uuid.UUID, BatchForPublish] = {}
        self.obligations: dict[uuid.UUID, PublishObligation] = {}
        self.links: dict[bytes, FakeLink] = {}
        self.reports: dict[uuid.UUID, FakeReport] = {}
        self.receipts: dict[uuid.UUID, FakeReceipt] = {}
        self.leak_guest_input = False

    def create_expense(self, context_id):
        record = ExpenseIdentity(id=uuid.uuid4(), context_id=context_id)
        self.expenses[record.id] = record
        return record

    def get_expense(self, expense_id):
        return self.expenses.get(expense_id)

    def save_expense_confirmation(
        self,
        *,
        expense_id,
        proposal,
        allocator_expense,
        rollups,
        allocations,
        confirmed_by_id,
        payer_acknowledgement,
        now,
    ):
        del allocator_expense, rollups, confirmed_by_id, now
        version_id = uuid.uuid4()
        number = self.version_numbers.get(expense_id, 0) + 1
        self.version_numbers[expense_id] = number
        rows = tuple(
            AllocationRow(
                id=uuid.uuid4(), participant_id=participant, amount_vnd=amount
            )
            for participant, amount in allocations.items()
        )
        self.confirmed[version_id] = ConfirmedExpense(
            version_id=version_id,
            context_id=proposal.context_id,
            paid_by_id=proposal.paid_by_id,
            payer_acknowledgement=payer_acknowledgement,
            allocations=rows,
        )
        self.version_to_expense[version_id] = expense_id
        return ConfirmationRecord(expense_version_id=version_id, version_number=number)

    def load_batch_inputs(self, context_id, expense_version_ids):
        selected = set(expense_version_ids) if expense_version_ids is not None else None
        records = tuple(
            record
            for version_id, record in self.confirmed.items()
            if record.context_id == context_id
            and version_id not in self.batched_versions
            and (selected is None or version_id in selected)
        )
        unavailable = (
            tuple(sorted(selected - {record.version_id for record in records}, key=str))
            if selected is not None
            else ()
        )
        return BatchInputs(expenses=records, unavailable_version_ids=unavailable)

    def load_bank_recipients(self, recipient_ids):
        return {
            recipient_id: self.bank_recipients[recipient_id]
            for recipient_id in recipient_ids
            if recipient_id in self.bank_recipients
        }

    def save_frozen_batch(
        self,
        *,
        context_id,
        owner_id,
        due_at,
        obligations: tuple[ObligationDraft, ...],
        bank_recipients,
        now,
    ):
        del now
        batch_id = uuid.uuid4()
        version_id = uuid.uuid4()
        frozen = []
        publish = []
        for draft in obligations:
            obligation_id = uuid.uuid4()
            frozen.append(
                FrozenObligation(
                    id=obligation_id,
                    sender_id=draft.sender_id,
                    recipient_id=draft.recipient_id,
                    amount_vnd=draft.amount_vnd,
                    due_at=due_at,
                    source_expense_version_ids=draft.source_expense_version_ids,
                )
            )
            bank = bank_recipients[draft.recipient_id]
            record = PublishObligation(
                id=obligation_id,
                batch_version_id=version_id,
                sender_id=draft.sender_id,
                recipient_id=draft.recipient_id,
                amount_vnd=draft.amount_vnd,
                bank_bin=bank.bank_bin,
                account_number=bank.account_number,
                account_name=bank.account_name,
            )
            publish.append(record)
            self.obligations[obligation_id] = record
            self.batched_versions.update(draft.source_expense_version_ids)
        source_versions = {
            source
            for draft in obligations
            for source in draft.source_expense_version_ids
        }
        acknowledged = bool(source_versions) and all(
            self.confirmed[source].payer_acknowledgement == "acknowledged"
            for source in source_versions
        )
        self.batches[batch_id] = BatchForPublish(
            id=batch_id,
            version_id=version_id,
            owner_id=owner_id,
            status="frozen",
            context_id=context_id,
            advancer_acknowledged=acknowledged,
            bank_recipient_snapshot_valid=bool(publish),
            all_recipients_eligible=bool(publish),
            obligations=tuple(publish),
        )
        return FrozenBatch(
            id=batch_id, version_id=version_id, obligations=tuple(frozen)
        )

    def load_batch_for_publish(self, batch_id):
        return self.batches.get(batch_id)

    def save_published_batch(
        self,
        *,
        batch,
        status,
        links: tuple[GuestLinkDraft, ...],
        actor_id,
        now,
    ):
        del actor_id, now
        self.batches[batch.id] = replace(batch, status=status)
        stored = []
        for draft in links:
            link = FakeLink(
                id=uuid.uuid4(),
                sender_id=draft.sender_id,
                batch_id=batch.id,
                expires_at=draft.expires_at,
            )
            self.links[draft.token_digest] = link
            stored.append(
                StoredGuestLink(
                    id=link.id,
                    envelope_id=uuid.uuid4(),
                    sender_id=draft.sender_id,
                )
            )
        return tuple(stored)

    def get_guest_envelope(self, token_digest, now):
        link = self.links.get(token_digest)
        if link is None:
            return None
        batch = self.batches[link.batch_id]
        obligations = [
            item for item in batch.obligations if item.sender_id == link.sender_id
        ]
        capability_scope(
            {"batch_version_id": batch.version_id, "sender_id": link.sender_id},
            [
                {
                    "obligation_id": item.id,
                    "batch_version_id": item.batch_version_id,
                    "sender_id": item.sender_id,
                }
                for item in obligations
            ],
        )
        blocks = []
        for item in obligations:
            receipts = [
                receipt.amount_vnd
                for receipt in self.receipts.values()
                if receipt.obligation_id == item.id
            ]
            status = obligation_status(
                item.amount_vnd, [{"amount_vnd": amount} for amount in receipts]
            )
            note = f"TT {item.id.hex[:8]}"
            payload = build_payload(
                bank_bin=item.bank_bin,
                account_number=item.account_number,
                amount_vnd=item.amount_vnd,
                note=note,
            )
            blocks.append(
                {
                    "obligation_id": str(item.id),
                    "occasion_label": "bữa tối",
                    "amount_vnd": item.amount_vnd,
                    "recipient_display_name": "Nam",
                    "bank_name": "Ngân hàng thử nghiệm",
                    "bank_bin": item.bank_bin,
                    "account_number": item.account_number,
                    "account_holder_name": item.account_name or "NGUYEN VAN NAM",
                    "transfer_note": note,
                    "qr_payload": payload,
                    "qr_image_data_uri": None,
                    "already_reported": any(
                        report.link_id == link.id and report.obligation_id == item.id
                        for report in self.reports.values()
                    ),
                    "receiver_confirmed": status in {"confirmed", "over_confirmed"},
                }
            )
        state = "expired" if now >= link.expires_at else link.status
        envelope = {
            "recorded_by_display_name": "Nam",
            "claimed_person_display_name": "Hà",
            "link_state": state,
            "obligations": blocks,
            "reports_used": sum(
                report.link_id == link.id for report in self.reports.values()
            ),
            "reports_allowed": self.REPORT_LIMIT,
            "objections_used": 0,
            "objections_allowed": 0,
        }
        if self.leak_guest_input:
            envelope["group_balance"] = {"someone_else": 123}
        return GuestEnvelopeRecord(link_id=link.id, envelope=envelope)

    def get_payment_report_target(self, token_digest, obligation_id, now):
        link = self.links.get(token_digest)
        obligation = self.obligations.get(obligation_id)
        if link is None or obligation is None:
            return None
        batch = self.batches[link.batch_id]
        if (
            obligation.batch_version_id != batch.version_id
            or obligation.sender_id != link.sender_id
        ):
            return None
        return PaymentReportTarget(
            link_id=link.id,
            obligation_id=obligation.id,
            amount_vnd=obligation.amount_vnd,
            active_capability=link.status == "active" and now < link.expires_at,
            reports_used=sum(
                report.link_id == link.id for report in self.reports.values()
            ),
        )

    def save_payment_report(self, *, target, idempotency_key, now):
        del now
        existing = next(
            (
                report
                for report in self.reports.values()
                if report.idempotency_key == idempotency_key
            ),
            None,
        )
        if existing is not None:
            if (
                existing.link_id != target.link_id
                or existing.obligation_id != target.obligation_id
            ):
                raise RepositoryConflict("IDEMPOTENCY_KEY_REUSED")
            report = existing
        else:
            report = FakeReport(
                id=uuid.uuid4(),
                link_id=target.link_id,
                obligation_id=target.obligation_id,
                amount_vnd=target.amount_vnd,
                idempotency_key=idempotency_key,
            )
            self.reports[report.id] = report
        return PaymentReportRecord(
            id=report.id,
            obligation_id=report.obligation_id,
            amount_vnd=report.amount_vnd,
            receipt_amounts_vnd=tuple(
                receipt.amount_vnd
                for receipt in self.receipts.values()
                if receipt.obligation_id == report.obligation_id
            ),
        )

    def get_receipt_target(self, obligation_id):
        item = self.obligations.get(obligation_id)
        if item is None:
            return None
        return ReceiptTarget(
            obligation_id=item.id,
            recipient_id=item.recipient_id,
            amount_vnd=item.amount_vnd,
        )

    def save_receipt_confirmation(
        self,
        *,
        target,
        confirmed_by_id,
        amount_vnd,
        payment_report_id,
        idempotency_key,
        now,
    ):
        del now
        existing = next(
            (
                receipt
                for receipt in self.receipts.values()
                if receipt.idempotency_key == idempotency_key
            ),
            None,
        )
        if existing is not None:
            if (
                existing.obligation_id != target.obligation_id
                or existing.confirmed_by_id != confirmed_by_id
                or existing.amount_vnd != amount_vnd
                or existing.payment_report_id != payment_report_id
            ):
                raise RepositoryConflict("IDEMPOTENCY_KEY_REUSED")
            receipt = existing
        else:
            if payment_report_id is not None:
                report = self.reports.get(payment_report_id)
                if report is None or report.obligation_id != target.obligation_id:
                    raise RepositoryConflict("PAYMENT_REPORT_NOT_FOR_OBLIGATION")
            receipt = FakeReceipt(
                id=uuid.uuid4(),
                obligation_id=target.obligation_id,
                confirmed_by_id=confirmed_by_id,
                amount_vnd=amount_vnd,
                payment_report_id=payment_report_id,
                idempotency_key=idempotency_key,
            )
            self.receipts[receipt.id] = receipt
        return ReceiptRecord(
            id=receipt.id,
            obligation_id=receipt.obligation_id,
            amount_vnd=receipt.amount_vnd,
            receipt_amounts_vnd=tuple(
                value.amount_vnd
                for value in self.receipts.values()
                if value.obligation_id == receipt.obligation_id
            ),
        )


class ASGITestClient:
    """Small sync facade over HTTPX's ASGI transport.

    Starlette's synchronous TestClient deadlocks with the AnyIO/Python build in
    this execution environment. The app has no lifespan hooks, so invoking the
    ASGI transport directly exercises the same request stack without hiding the
    environment issue behind a sleep or timeout.
    """

    def __init__(self, app):
        self.app = app

    def request(self, method, path, **kwargs):
        async def send():
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.request(method, path, **kwargs)

        return anyio.run(send)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)


@pytest.fixture
def repository():
    return FakeRepository()


@pytest.fixture
def client(repository, monkeypatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    # This runner's Python 3.13 thread executor deadlocks even for
    # ``asyncio.to_thread(lambda: 1)``. Execute Starlette's sync adapters inline
    # for the fake-only tests; production routes remain conventional sync routes.
    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repository
    return ASGITestClient(app)
