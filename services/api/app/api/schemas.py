"""Pydantic wire contracts for the first API vertical slice.

Money fields use strict integers deliberately. A JSON string such as ``"82000"``
or a float such as ``82000.0`` is a malformed caller precondition; neither is
allowed to reach the allocator and masquerade as an ``AllocationError``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    field_validator,
    model_validator,
)

MoneyVnd = Annotated[int, Field(strict=True)]
PositiveMoneyVnd = Annotated[int, Field(strict=True, gt=0)]
NonNegativeMoneyVnd = Annotated[int, Field(strict=True, ge=0)]


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


class BillItemCreateRequest(ApiModel):
    item_key: Annotated[StrictStr, Field(max_length=64)]
    name: StrictStr
    quantity: Annotated[int, Field(strict=True, gt=0)]
    unit_price_vnd: MoneyVnd | None
    line_total_vnd: PositiveMoneyVnd
    suggested_participant_ids: list[UUID]


class BillSurchargeCreateRequest(ApiModel):
    surcharge_key: Annotated[StrictStr, Field(max_length=64)]
    kind: Annotated[StrictStr, Field(max_length=32)]
    amount_vnd: PositiveMoneyVnd
    mode: Literal["proportional", "even"]


class BillDiscountCreateRequest(ApiModel):
    """A discount line, WITH its scope and, when item-scoped, its target.

    ADR-0004 owns this rule and calls the violation SCOPE_TARGET_MISMATCH, but
    the allocator never sees a draft that fails to store: a bill is written
    long before it is split, and `ck_bill_discounts_scope_target_match`
    refuses the incoherent row at INSERT. Checking it here keeps a malformed
    body a 422 about the body instead of a write conflict about the schema.
    """

    discount_key: Annotated[StrictStr, Field(max_length=64)]
    amount_vnd: PositiveMoneyVnd
    scope: Literal["global_proportional", "item"]
    item_key: Annotated[StrictStr, Field(max_length=64)] | None = None

    @model_validator(mode="after")
    def _target_matches_scope(self) -> BillDiscountCreateRequest:
        if (self.scope == "item") != (self.item_key is not None):
            # Both directions are wrong in their own way: a global discount
            # carrying a target reads as item-scoped to anybody skimming, and
            # an item-scoped one without a target has no item to subtract from.
            raise ValueError(
                "an item-scoped discount needs item_key and a global one "
                "must not carry it"
            )
        return self


class BillCreateRequest(ApiModel):
    context_id: UUID
    printed_total_vnd: NonNegativeMoneyVnd | None
    items_total_vnd: NonNegativeMoneyVnd
    confidence: Annotated[int, Field(strict=True, ge=0, le=100)]
    needs_review: StrictBool
    items: list[BillItemCreateRequest]
    surcharges: list[BillSurchargeCreateRequest] = Field(default_factory=list)
    discounts: list[BillDiscountCreateRequest] = Field(default_factory=list)


class BillAssignment(ApiModel):
    item_key: Annotated[StrictStr, Field(max_length=64)]
    participant_ids: list[UUID]


class BillAssignmentsRequest(ApiModel):
    assignments: list[BillAssignment]


class BillSplitRequest(ApiModel):
    for_ledger: StrictBool = False
    paid_by_id: UUID | None = None


class BillShareResponse(ApiModel):
    participant_id: UUID
    source: Literal["ai_suggested", "confirmed"]
    decided_by_id: UUID | None
    decided_at: datetime | None


class BillItemResponse(ApiModel):
    item_key: StrictStr
    name: StrictStr
    quantity: Annotated[int, Field(strict=True, gt=0)]
    unit_price_vnd: MoneyVnd | None
    line_total_vnd: PositiveMoneyVnd
    position: Annotated[int, Field(strict=True, ge=0)]
    shares: list[BillShareResponse]


class BillSurchargeResponse(ApiModel):
    surcharge_key: StrictStr
    kind: StrictStr
    amount_vnd: PositiveMoneyVnd
    mode: Literal["proportional", "even"]


class BillDiscountResponse(ApiModel):
    discount_key: StrictStr
    amount_vnd: PositiveMoneyVnd
    scope: Literal["global_proportional", "item"]
    item_key: StrictStr | None


class BillResponse(ApiModel):
    id: UUID
    context_id: UUID
    printed_total_vnd: NonNegativeMoneyVnd | None
    items_total_vnd: NonNegativeMoneyVnd
    needs_review: StrictBool
    created_by_id: UUID
    created_at: datetime
    assignment_state: Literal["confirmed", "ai_suggested"]
    suggested_item_keys: list[StrictStr]
    items: list[BillItemResponse]
    surcharges: list[BillSurchargeResponse]
    discounts: list[BillDiscountResponse]


class BillSplitResponse(ApiModel):
    allocation: AllocationProposal
    assignment_state: Literal["confirmed", "ai_suggested"]
    suggested_item_keys: list[StrictStr]
    total_amount_vnd: MoneyVnd


class PersonRegistrationRequest(ApiModel):
    """A name asserted for one person id, by whoever is asking.

    The id is not in the body: it is the path, because the caller already holds
    it. Participant ids are minted client-side and then used in expenses,
    obligations and envelopes long before anybody types a name, so this route
    names an id that already exists in the caller's world rather than handing
    out a new one.
    """

    display_name: Annotated[StrictStr, Field(min_length=1, max_length=200)]


class PersonResponse(ApiModel):
    id: UUID
    display_name: StrictStr
    created_at: datetime


class PersonIdResponse(ApiModel):
    """The id a telephone number derives to, and nothing else.

    No echo of the number, not even normalised. The request carried it; the
    response is what the caller did not already have. A round trip that returns
    its own input is a round trip that puts the input into a second set of
    logs.
    """

    person_id: UUID


class FinanceMovementView(ApiModel):
    """One confirmed movement, with the sign carried as a word.

    `direction` rather than a signed `amount_vnd` so no client can lose the
    sign by taking an absolute value for formatting -- which is precisely how
    a repayment renders as income.
    """

    obligation_id: UUID
    direction: Literal["in", "out"]
    amount_vnd: int
    counterparty_id: UUID
    counterparty_name: StrictStr | None
    context_id: UUID
    context_name: StrictStr | None
    occasion: StrictStr | None
    occurred_at: datetime


class PersonFinanceResponse(ApiModel):
    """Everything the personal screen shows, recomputed per request.

    `settled_vnd + outstanding_vnd == spend_vnd` by construction, so the two
    figures a reader sees under the total always account for all of it.
    """

    person_id: UUID
    display_name: StrictStr | None
    spend_vnd: int
    settled_vnd: int
    outstanding_vnd: int
    expense_count: int
    group_count: int
    movements: list[FinanceMovementView]


class ContextCreateRequest(ApiModel):
    display_name: Annotated[StrictStr, Field(min_length=1, max_length=200)]


class ContextResponse(ApiModel):
    id: UUID
    display_name: StrictStr
    created_by_id: UUID
    created_at: datetime


class OutingCreateRequest(ApiModel):
    title: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    starts_on: date
    ends_on: date
    headcount: Annotated[int, Field(strict=True, gt=0, le=1000)]
    budget_per_person_vnd: NonNegativeMoneyVnd

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("title must not be blank")
        return title

    @model_validator(mode="after")
    def _dates_are_in_order(self) -> OutingCreateRequest:
        if self.ends_on < self.starts_on:
            raise ValueError("ends_on must be on or after starts_on")
        return self


class OutingStopInput(ApiModel):
    at: Annotated[
        StrictStr,
        Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$"),
    ]
    label: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    place_name: Annotated[StrictStr, Field(max_length=200)] | None = None

    @field_validator("label")
    @classmethod
    def _strip_label(cls, value: str) -> str:
        label = value.strip()
        if not label:
            raise ValueError("label must not be blank")
        return label

    @field_validator("place_name")
    @classmethod
    def _strip_place_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class OutingTimelineRequest(ApiModel):
    stops: Annotated[list[OutingStopInput], Field(max_length=50)]


class OutingStopResponse(ApiModel):
    id: UUID
    position: int
    at: str
    label: str
    place_name: str | None


class StopCheckinResponse(ApiModel):
    """One arrival, named by person and moment.

    There is no latitude, longitude or accuracy on this model on purpose, and
    no request body to match it: F46 is somebody pressing "đã tới", not the
    phone reporting where it is. A coordinate attached to a person and a time
    is a movement record, and the group timeline is read by everyone in the
    group -- see `OutingStopCheckin` for why the column does not exist at all.
    """

    id: UUID
    stop_id: UUID
    person_id: UUID
    display_name: str | None
    created_at: datetime


class OutingCheckinListResponse(ApiModel):
    outing_id: UUID
    checkins: list[StopCheckinResponse]


class OutingResponse(ApiModel):
    id: UUID
    context_id: UUID
    created_by_id: UUID
    title: str
    starts_on: date
    ends_on: date
    headcount: int
    budget_per_person_vnd: int
    created_at: datetime
    stops: list[OutingStopResponse]


class OutingListResponse(ApiModel):
    context_id: UUID
    outings: list[OutingResponse]


class OutingInviteCreateRequest(ApiModel):
    source: Literal["group", "friend", "link"]
    person_id: UUID | None = None

    @model_validator(mode="after")
    def _person_matches_source(self) -> OutingInviteCreateRequest:
        if self.source == "link" and self.person_id is not None:
            raise ValueError("a link invite must not name a person")
        if self.source != "link" and self.person_id is None:
            raise ValueError("a group or friend invite must name a person")
        return self


class OutingInviteResponse(ApiModel):
    id: UUID
    outing_id: UUID
    source: Literal["group", "friend", "link"]
    invited_person_id: UUID | None
    invited_by_id: UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    invite_token: str | None
    invite_path: str | None


# A link redeemer is not a member yet, so this response must reveal neither the
# group name nor the trip name before the existing membership flow accepts them.
class OutingInviteAcceptResponse(ApiModel):
    invite_id: UUID
    outing_id: UUID
    context_id: UUID
    membership_id: UUID
    membership_state: Literal["invited", "active"]


class MembershipInviteRequest(ApiModel):
    person_id: UUID


class MemberRoleRequest(ApiModel):
    role: Literal["member", "admin"]


class MembershipResponse(ApiModel):
    id: UUID
    context_id: UUID
    person_id: UUID
    state: Literal["invited", "active", "left"]
    role: Literal["member", "admin"]
    invited_by_id: UUID | None
    joined_at: datetime | None
    left_at: datetime | None
    created_at: datetime


class MembershipListResponse(ApiModel):
    context_id: UUID
    members: list[MembershipResponse]


class ContextBalanceEntry(ApiModel):
    person_id: UUID
    net_vnd: MoneyVnd


class SettlementTransferProposal(ApiModel):
    """A suggested transfer that must not be treated as a frozen obligation."""

    sender_id: UUID
    recipient_id: UUID
    amount_vnd: PositiveMoneyVnd


class ContextBalancesResponse(ApiModel):
    balances: list[ContextBalanceEntry]
    transfers: list[SettlementTransferProposal] = Field(
        description="Settlement proposals that require participant consent"
    )
    proven_minimal: StrictBool
    transfer_count: Annotated[int, Field(strict=True, ge=0)]


class RecapOutingResponse(ApiModel):
    """One finished trip on the memory wall.

    `split_total_vnd` is recomputed from the ledger per request. It counts the
    expenses that happened on this trip's days, which is a rule the screen
    states out loud -- there is no `expenses.outing_id` to be exact with.
    """

    outing_id: UUID
    title: str
    starts_on: date
    ends_on: date
    headcount: int
    stops: list[OutingStopResponse]
    split_total_vnd: int
    expense_count: int
    memory_count: int


class GroupRecapResponse(ApiModel):
    context_id: UUID
    outings: list[RecapOutingResponse]
    split_total_vnd: int


class MemoryCreateRequest(ApiModel):
    image_url: Annotated[StrictStr, Field(min_length=1)]
    caption: str | None = None


class CheckinCreateRequest(ApiModel):
    """F46. The group arrived somewhere, and only the group says where.

    One field names the place and nothing describes it. The name and the
    coordinates are looked up server-side from `app/places/catalog.py`, so a
    caller cannot assert that the group was at "Nhà tôi, 0.0, 0.0" or move a
    real venue by a kilometre -- the same rule `POST /expenses` follows about
    who is allowed to state a fact. An unknown `place_id` is a 422 rather than
    a row: a check-in at a place this product has never heard of is a mark on
    a timeline that no screen can open.

    There is no latitude or longitude on this request on purpose. Reading the
    phone's GPS is F47 and is not built; taking coordinates from the body
    would let this route *look* like it had been.
    """

    place_id: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    caption: Annotated[str, Field(max_length=2000)] | None = None


class MemoryQuery(ApiModel):
    limit: int = Field(default=50, ge=1, le=100)
    before: str | None = None
    #: Narrows the wall to one kind, or to one place's check-ins. Both are
    #: filters on top of the membership gate, never instead of it.
    kind: Literal["photo", "checkin"] | None = None
    place_id: str | None = None


class MemoryResponse(ApiModel):
    """One row of the wall.

    `image_url` and the four place fields are mutually exclusive by database
    constraint, and `kind` says which pair of shoes this row is wearing so a
    reader never has to infer it from which field happens to be null.
    """

    id: UUID
    context_id: UUID
    author_id: UUID
    kind: Literal["photo", "checkin"]
    image_url: str | None
    caption: str | None
    place_id: str | None
    place_name: str | None
    #: Group-private, at the same rank as a phone number. It leaves the server
    #: only on this response, which every route behind it gates on membership.
    lat: float | None
    lng: float | None
    created_at: datetime
    cursor: str


class MemoryListResponse(ApiModel):
    context_id: UUID
    memories: list[MemoryResponse]
    next_cursor: str | None
    has_more: bool


class MessageCreateRequest(ApiModel):
    kind: Literal["text", "image", "ai_card"]
    body: Annotated[StrictStr, Field(max_length=4000)] | None = None
    image_url: Annotated[StrictStr, Field(max_length=2000)] | None = None
    card: dict | None = None


class MessageQuery(ApiModel):
    limit: int = Field(default=50, ge=1, le=100)
    before: str | None = None
    after: str | None = None


class MessageResponse(ApiModel):
    id: UUID
    context_id: UUID
    author_id: UUID | None
    kind: Literal["text", "image", "ai_card"]
    body: str | None
    image_url: str | None
    card: dict | None
    created_at: datetime
    cursor: str


class CompanionTurnResponse(ApiModel):
    context_id: UUID
    spoke: bool
    reason: str
    message: MessageResponse | None


class MessageListResponse(ApiModel):
    context_id: UUID
    messages: list[MessageResponse]
    next_cursor: str | None
    has_more: bool


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


class ReceiptItem(ApiModel):
    name: StrictStr
    quantity: Annotated[int, Field(strict=True, gt=0)]
    unit_price_vnd: MoneyVnd | None = None
    line_total_vnd: MoneyVnd


class ReceiptScanResponse(ApiModel):
    """What a scan is allowed to tell the client.

    No ``confidence``. ADR-0009 decision 4 refuses a confidence score on the
    grounds that a percentage invites an interface to auto-accept above a
    threshold, and rd-qa-03 measured the reason live: the number tracked how
    legible the print was, not whether the money was right, so a menu scored
    95-100 and a reading that got four lines wrong scored 70-75. The signal the
    client is meant to branch on is ``needs_review``; the rest is words a person
    reads. The number still exists server-side, where it gates.
    """

    items: list[ReceiptItem]
    items_total_vnd: MoneyVnd
    total_vnd: MoneyVnd | None = None
    totals_agree: StrictBool | None = None
    total_difference_vnd: MoneyVnd | None = None
    needs_review: StrictBool
    warnings: list[StrictStr] = Field(default_factory=list)


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


class PersonBankRecipientRequest(ApiModel):
    """The same destination, for the route that names its subject in the path.

    Deliberately without `recipient_id`. On `POST /bank-recipients` the subject
    is a body field, so "change my account" and "change somebody else's" are one
    request with one field different and the permission check is the only thing
    between them. Here the subject is part of the address, so the narrower
    request cannot be widened by a stray field -- and `extra="forbid"` means
    sending one is a 422 rather than a silently ignored second opinion about who
    this is for.
    """

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

    Three independent facts, deliberately kept apart, each created by a
    different person:

    * `payment_reported_at` -- the SENDER said they transferred it, at that
      time. One person's account of what they did.
    * `obligation_status` -- the RECIPIENT confirmed the money arrived. Still
      derived from receipt events only; a claim never moves it.
    * `disputed` -- somebody objects to the number.

    None of the three is evidence from a bank. Status and dispute were one
    field once, and that let the recipient close an argument by confirming
    receipt -- a click belonging to exactly the party the objection was
    against. The claim is kept out of status for the mirror-image reason:
    folding it in would let the sender close their own obligation by saying
    so.
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
    # `None` means nobody has said anything, and the key is always present so
    # that "no claim" and "a build older than this field" are not the same
    # thing on the wire.
    payment_reported_at: datetime | None = None


class BatchObligationsResponse(ApiModel):
    batch_id: UUID
    obligations: list[BatchObligationView]
    # Counted here so the board does not have to, and so "how many need a
    # human" is one number rather than a filter someone might forget. It
    # counts OPEN objections at any payment status: an obligation that was
    # paid and is still argued about still needs a person.
    disputed_count: int
    # How many obligations carry a sender's claim, at any payment status --
    # including ones already confirmed. Counting only the unconfirmed ones
    # would quietly make this a second opinion about payment status, which is
    # the exact blending the two fields exist to prevent.
    payment_reported_count: int = 0


class ErrorResponse(ApiModel):
    code: StrictStr
    detail: StrictStr
