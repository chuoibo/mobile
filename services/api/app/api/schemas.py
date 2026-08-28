"""Pydantic wire contracts for the first API vertical slice.

Money fields use strict integers deliberately. A JSON string such as ``"82000"``
or a float such as ``82000.0`` is a malformed caller precondition; neither is
allowed to reach the allocator and masquerade as an ``AllocationError``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    field_validator,
)

MoneyVnd = Annotated[int, Field(strict=True)]
PositiveMoneyVnd = Annotated[int, Field(strict=True, gt=0)]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _require_timezone(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a UTC offset")
    return value


class ExpenseItemInput(ApiModel):
    item_id: StrictStr
    label: StrictStr | None = None
    amount_vnd: MoneyVnd
    shared_by: list[UUID]


class ExpenseSurchargeInput(ApiModel):
    surcharge_id: StrictStr
    kind: StrictStr
    amount_vnd: MoneyVnd
    mode: Literal["proportional", "even"]


class ExpenseDiscountInput(ApiModel):
    discount_id: StrictStr
    amount_vnd: MoneyVnd
    scope: Literal["global_proportional", "item"]
    item_id: StrictStr | None = None


class ExpenseInput(ApiModel):
    context_id: UUID
    description: StrictStr | None = None
    recorded_by_id: UUID
    paid_by_id: UUID
    verification_scope: Literal["totals_only", "items_reviewed"]
    occurred_at: datetime
    participants: list[UUID]
    total_amount_vnd: MoneyVnd
    items: list[ExpenseItemInput] = Field(default_factory=list)
    surcharges: list[ExpenseSurchargeInput] = Field(default_factory=list)
    discounts: list[ExpenseDiscountInput] = Field(default_factory=list)

    _occurred_at_has_timezone = field_validator("occurred_at")(_require_timezone)


class AllocationProposal(ApiModel):
    allocations: dict[UUID, MoneyVnd]
    exact_shares: dict[UUID, StrictStr]
    rounding_gainers: list[UUID]
    warnings: list[StrictStr]


class ExpenseProposalResponse(ApiModel):
    expense_id: UUID
    proposal: ExpenseInput
    allocation: AllocationProposal


class ExpenseConfirmationRequest(ApiModel):
    proposal: ExpenseInput
    expected_allocations: dict[UUID, MoneyVnd]
    acknowledge_as_advancer: StrictBool = False


class ExpenseConfirmationResponse(ApiModel):
    expense_id: UUID
    expense_version_id: UUID
    version_number: int
    total_amount_vnd: MoneyVnd
    payer_acknowledgement: Literal["pending", "acknowledged"]
    allocations: dict[UUID, MoneyVnd]


class ContextCreateRequest(ApiModel):
    display_name: Annotated[StrictStr, Field(min_length=1, max_length=200)]


class ContextResponse(ApiModel):
    id: UUID
    display_name: StrictStr
    created_by_id: UUID
    created_at: datetime


class MembershipInviteRequest(ApiModel):
    person_id: UUID


class MembershipResponse(ApiModel):
    id: UUID
    context_id: UUID
    person_id: UUID
    state: Literal["invited", "active", "left"]
    invited_by_id: UUID | None
    joined_at: datetime | None
    left_at: datetime | None
    created_at: datetime


class MembershipListResponse(ApiModel):
    context_id: UUID
    members: list[MembershipResponse]


class BatchCreateRequest(ApiModel):
    context_id: UUID
    expense_version_ids: list[UUID] | None = None
    due_at: datetime
    unready_recipient_choice: Literal["wait", "split_to_blocked_batch"] | None = None

    _due_at_has_timezone = field_validator("due_at")(_require_timezone)


class ObligationResponse(ApiModel):
    obligation_id: UUID
    sender_id: UUID
    recipient_id: UUID
    amount_vnd: PositiveMoneyVnd
    due_at: datetime
    source_expense_version_ids: list[UUID]


class BatchCreateResponse(ApiModel):
    batch_id: UUID
    batch_version_id: UUID
    status: Literal["frozen"]
    obligations: list[ObligationResponse]


class BatchPublishRequest(ApiModel):
    delivery_method: Literal["personal_link"]
    guest_link_expires_at: datetime

    _expiry_has_timezone = field_validator("guest_link_expires_at")(_require_timezone)


class PublishedObligation(ApiModel):
    obligation_id: UUID
    amount_vnd: PositiveMoneyVnd
    vietqr_payload: StrictStr


class PublishedGuestLink(ApiModel):
    sender_id: UUID
    path: StrictStr
    expires_at: datetime
    obligations: list[PublishedObligation]


class BatchPublishResponse(ApiModel):
    batch_id: UUID
    status: Literal["published"]
    guest_links: list[PublishedGuestLink]


class PaymentReportRequest(ApiModel):
    obligation_id: UUID
    idempotency_key: UUID | None = None


class PaymentReportResponse(ApiModel):
    payment_report_id: UUID
    obligation_id: UUID
    amount_vnd: PositiveMoneyVnd
    obligation_status: Literal[
        "outstanding", "partially_confirmed", "confirmed", "over_confirmed"
    ]


class ReceiptConfirmationRequest(ApiModel):
    amount_vnd: PositiveMoneyVnd
    idempotency_key: UUID
    payment_report_id: UUID | None = None


class ReceiptConfirmationResponse(ApiModel):
    receipt_confirmation_id: UUID
    obligation_id: UUID
    amount_vnd: PositiveMoneyVnd
    obligation_status: Literal[
        "outstanding", "partially_confirmed", "confirmed", "over_confirmed"
    ]


class BankRecipientRequest(ApiModel):
    """Where a recipient wants their money to land.

    The three destination fields are plain strings on purpose. Shape is decided
    by `app.domain.bank_account`, so a malformed bank code comes back as a 422
    carrying `INVALID_BANK_BIN` -- a code the caller can branch on. Encoding the
    same rules as pydantic constraints would answer with FastAPI's generic
    validation body instead, which has no such code in it.
    """

    recipient_id: UUID
    bank_bin: StrictStr
    account_number: StrictStr
    account_name: StrictStr | None = None


class BankRecipientResponse(ApiModel):
    id: UUID
    recipient_id: UUID
    bank_bin: StrictStr
    # A routing code nobody can act on, plus the name they will actually look
    # for in their banking app, plus whether we recognised it at all.
    bank_name: StrictStr
    bank_recognised: StrictBool
    account_number: StrictStr
    account_name: StrictStr | None
    confirmed_at: datetime


class BatchObligationView(ApiModel):
    """One obligation on the collection board.

    Two independent facts, deliberately kept apart. `obligation_status` says
    whether the money arrived; `disputed` says whether anybody disagrees. They
    were one field once, and that let the recipient close an argument by
    confirming receipt -- a click belonging to exactly the party the objection
    was against.
    """

    obligation_id: UUID
    sender_id: UUID
    recipient_id: UUID
    amount_vnd: PositiveMoneyVnd
    obligation_status: Literal[
        "outstanding", "partially_confirmed", "confirmed", "over_confirmed"
    ]
    disputed: bool = False
    disputed_reason: StrictStr | None = None


class BatchObligationsResponse(ApiModel):
    batch_id: UUID
    obligations: list[BatchObligationView]
    # Counted here so the board does not have to, and so "how many need a
    # human" is one number rather than a filter someone might forget. It
    # counts OPEN objections at any payment status: an obligation that was
    # paid and is still argued about still needs a person.
    disputed_count: int


class ErrorResponse(ApiModel):
    code: StrictStr
    detail: StrictStr
