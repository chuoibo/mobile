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
RelativePhotoUrl = Annotated[
    StrictStr,
    Field(
        pattern=(
            r"\A/contexts/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/photos/"
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\z"
        )
    ),
]


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
    amount_vnd: MoneyVnd
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
    spend_vnd: MoneyVnd
    settled_vnd: MoneyVnd
    outstanding_vnd: MoneyVnd
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
    budget_per_person_vnd: MoneyVnd
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
    """One person's standing in one group, including who they are.

    `display_name` is required rather than optional because the database makes
    it so: `memberships.person_id` is a foreign key into `people`, whose
    `display_name` is `NOT NULL`. An optional field would have invited every
    client to invent its own placeholder, and a placeholder shared by two
    unnamed people reads as one person on the screen whose job is telling them
    apart.

    Nothing may be derived from it. It repeats inside a group, it changes, and
    identity stays the id.
    """

    id: UUID
    context_id: UUID
    person_id: UUID
    display_name: StrictStr
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
    """One trip on the recap -- finished, or still under way.

    `split_total_vnd` is recomputed from the ledger per request. It counts the
    expenses that happened on this trip's days, which is a rule the screen
    states out loud -- there is no `expenses.outing_id` to be exact with.

    For a trip still under way that same rule reads as "so far": the trip's
    days run past today, and only the expenses already confirmed are in the
    ledger to be counted. The figure is a running one, and it is recomputed
    rather than accumulated, so it can go *down* when somebody corrects a bill.
    """

    outing_id: UUID
    title: str
    starts_on: date
    ends_on: date
    headcount: int
    stops: list[OutingStopResponse]
    split_total_vnd: MoneyVnd
    expense_count: int
    memory_count: int


class GroupRecapResponse(ApiModel):
    """Two lists, deliberately not one.

    `outings` is the memory wall: trips that have ended, newest first. It is
    unchanged, because a client is already reading it.

    `in_progress` is the trip the group is on right now -- started on or before
    today, ending today or later. It is separate rather than flagged inside
    `outings` so that adding it could not quietly turn an unfinished trip into
    a memory.

    `split_total_vnd` totals `outings` alone. A memory wall's total that drifted
    upward through the day, as the group kept eating, would stop matching the
    per-trip figures printed under it.
    """

    context_id: UUID
    outings: list[RecapOutingResponse]
    in_progress: list[RecapOutingResponse]
    split_total_vnd: MoneyVnd


class BudgetOutingView(ApiModel):
    outing_id: UUID
    title: StrictStr
    headcount: Annotated[int, Field(strict=True, ge=0)]
    budget_per_person_vnd: NonNegativeMoneyVnd
    spent_per_person_vnd: NonNegativeMoneyVnd
    remaining_per_person_vnd: MoneyVnd
    over_budget: StrictBool

    @model_validator(mode="after")
    def _remaining_matches_spend(self) -> BudgetOutingView:
        expected = self.budget_per_person_vnd - self.spent_per_person_vnd
        if self.remaining_per_person_vnd != expected:
            raise ValueError("remaining must be budget minus spent")
        if self.over_budget != (self.remaining_per_person_vnd < 0):
            raise ValueError("over_budget must match the remaining sign")
        return self


class BudgetComparison(ApiModel):
    candidate_per_person_vnd: NonNegativeMoneyVnd
    delta_vnd: MoneyVnd
    verdict: Literal["re-hon", "nhu-thuong", "cao-hon"]


class GroupBudgetResponse(ApiModel):
    context_id: UUID
    outing_count: Annotated[int, Field(strict=True, ge=0)]
    active_member_count: Annotated[int, Field(strict=True, ge=0)]
    avg_per_person_vnd: MoneyVnd | None
    in_progress: list[BudgetOutingView]
    comparison: BudgetComparison | None

    @model_validator(mode="after")
    def _comparison_has_a_real_baseline(self) -> GroupBudgetResponse:
        if self.comparison is not None:
            if self.avg_per_person_vnd is None:
                raise ValueError("comparison requires a historical average")
            expected = (
                self.comparison.candidate_per_person_vnd - self.avg_per_person_vnd
            )
            if self.comparison.delta_vnd != expected:
                raise ValueError("comparison delta must be candidate minus average")
        return self


class SuggestionPlace(ApiModel):
    """The catalogue row behind one stop, and nothing the model wrote.

    No `lat`/`lng`. The suggestion is about where a group might go next, not
    about where anybody is, and a coordinate pair on this response would be
    the first place F47 looked like it had been built.
    """

    id: str
    name: str
    category: str
    address: str
    price_min_vnd: MoneyVnd
    price_max_vnd: MoneyVnd
    rating: float
    distance_km: float
    open_hours: str


class SuggestionStop(ApiModel):
    """One stop. `reason` and `verdict` are one claim or neither.

    The app prints `reason` under the words AI MATCH and prints the badge from
    `verdict`, so half a pair renders as an endorsement nobody gave. They are
    tied in `app/domain/suggestion.py`, at the single point every stop passes
    through, rather than at each place that builds one of these.
    """

    time_text: str
    note: str
    reason: str | None
    verdict: Literal["hop", "tam", "khong-hop"] | None
    place: SuggestionPlace


class SuggestionBasis(ApiModel):
    """Why this suggestion, computed by the server from the group's own rows.

    Recomputed per request from the ledger and the memory wall -- invariant 3
    applied to a screen whose whole argument is "you have done this before".
    Deliberately not asked of the model: a basis the model wrote would be a
    number with nothing behind it, printed directly under one that has.
    """

    outing_count: int
    split_total_vnd: MoneyVnd
    avg_per_person_vnd: MoneyVnd | None
    top_categories: list[str]
    recent_titles: list[str]


class GroupSuggestionResponse(ApiModel):
    """F32. `suggested` is the honest half of the contract.

    `false` with a reason is a real answer -- a group with no finished trips
    has nothing to suggest from, and a model outage is not something to paper
    over with a hand-written card. There is deliberately no fallback: a
    plausible card served while the feature is broken is a broken feature
    nobody can see is broken.
    """

    context_id: UUID
    suggested: bool
    #: `ok` | `no_history` | `unavailable` | `ungrounded`
    reason: str
    title: str | None
    when_text: str | None
    stops: list[SuggestionStop]
    basis: SuggestionBasis
    #: A claim about who wrote the sentences on these cards.
    source: Literal["ai", "none"]


class UploadedImageResponse(ApiModel):
    id: UUID
    context_id: UUID | None
    url: str
    content_type: str
    byte_size: int
    width: int
    height: int
    created_at: datetime


class MemoryCreateRequest(ApiModel):
    image_url: RelativePhotoUrl
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
    #: F40/F41. The mockup draws "❤️ 18 · 💬 6" under every row, so the feed
    #: carries both totals. Recomputed per read from the reaction and comment
    #: rows -- never a stored counter, which would be a cache standing in for
    #: the sum it is meant to summarise.
    reaction_count: int = 0
    comment_count: int = 0
    #: Whether the actor making *this* request left a heart. It is a fact about
    #: the reader, so it is answered per request and never cached in a row.
    viewer_has_reacted: bool = False


class MemoryListResponse(ApiModel):
    context_id: UUID
    memories: list[MemoryResponse]
    next_cursor: str | None
    has_more: bool


class WidgetPhotoResponse(ApiModel):
    """F38. The one photograph a home-screen widget draws, and who left it.

    Deliberately not a `MemoryResponse`. The wall's row carries a cursor, two
    social counters, a `viewer_has_reacted` fact and four location columns; a
    widget draws none of them, and a shape that carries them anyway is four
    more group-private fields sitting on a surface that renders outside the
    app, next to a lock screen. What a widget needs is a picture, a name and a
    moment, so that is the whole of it.
    """

    memory_id: UUID
    #: The relative `/contexts/{id}/photos/{id}` url the wall already stores.
    #: The bytes it names were stripped of EXIF by `POST .../photos` on the way
    #: in; nothing here re-reads or re-writes an image.
    image_url: str
    caption: str | None
    author_id: UUID
    #: Read from `people` by the service, never echoed from a request. A widget
    #: says "Nam vừa đăng", and the name has to be the name the group knows.
    author_name: str
    created_at: datetime


class WidgetResponse(ApiModel):
    """F38. What one group's widget shows right now, or that it shows nothing.

    `photo` is null when the group has no photograph yet. That is a 200 and not
    a 404: a widget asking about a real group it belongs to has asked a valid
    question, and the honest answer is "nothing to draw". Answering 404 would
    also hand a caller a second status code to distinguish "empty" from
    "forbidden", which is exactly the difference a stranger is fishing for.

    `context_id` is echoed from the path and is the only other field. Nothing
    about the group -- its name, its size, its roster, when it was created --
    appears here in either state, so the empty body carries no fact the caller
    did not already have in hand when it built the URL.
    """

    context_id: UUID
    photo: WidgetPhotoResponse | None


class MemoryReactionResponse(ApiModel):
    """F40. One heart, named by who left it.

    `person_id` is echoed from the actor and never read off the request body.
    A body field naming the reactor would let anyone with a session put a
    heart under somebody else's name -- the shape that opened six holes on the
    money routes, avoided here by not offering the field at all.
    """

    id: UUID
    memory_id: UUID
    person_id: UUID
    created_at: datetime
    #: The total after this write, so a client need not re-read the feed to
    #: redraw one number.
    reaction_count: int


class MemoryCommentCreateRequest(ApiModel):
    """F41. What one member wants to say under one photograph.

    One field. There is deliberately no `author_id` here: the writer is the
    caller, proved by the gateway, not a name the body gets to assert.
    """

    body: Annotated[StrictStr, Field(min_length=1, max_length=2000)]


class MemoryCommentResponse(ApiModel):
    """One comment as it goes back to a member of the group that owns it.

    `body` is group-private. It leaves the server only on this model and on
    the list below, both of which sit behind `view_group_memories`. The guest
    page builds its view model from a whitelist (`app/web/guest_view.py`) that
    has no slot for any of these fields, so this text cannot reach a link
    holder standing outside the group.
    """

    id: UUID
    memory_id: UUID
    author_id: UUID
    display_name: str | None
    body: str
    created_at: datetime


class MemoryCommentListResponse(ApiModel):
    memory_id: UUID
    comments: list[MemoryCommentResponse]


class PostCreateRequest(ApiModel):
    """F39/F42. What a person said, and who they addressed it to.

    There is no `author_id` here and there is no recipient list. Both absences
    are the feature:

    * The author is the actor the gateway proved. A body field naming the
      writer is a field for writing in somebody else's name, and no downstream
      check recovers from one.
    * `audience` is one of four words, not a list of people. A route that took
      a list of identities from the body would be granting read access to
      people nobody verified the caller may name -- and it would freeze that
      list at write time, so removing a friend afterwards would take nothing
      back.

    `context_id` is meaningful only for `group`; the pairing is checked in
    `app.domain.post_audience.check_writable` and again by a CHECK constraint
    on the table.
    """

    body: Annotated[StrictStr, Field(min_length=1, max_length=5000)]
    audience: Literal["only_me", "friends", "group", "public"]
    #: Which group, when and only when `audience` is `group`. Naming a group
    #: here is a claim; membership of it is checked server-side against the
    #: roster, never against the caller's `X-Actor-Contexts` header.
    context_id: UUID | None = None
    image_url: RelativePhotoUrl | None = None


class PostResponse(ApiModel):
    """One post, as it goes back to a reader who is allowed to have it.

    Every route that emits this model has already run
    `app.domain.post_audience.can_read` for the actor making the request. The
    model itself carries no `visible_to` field and computes nothing: a reader
    holding this object is proof enough that they were allowed to.
    """

    id: UUID
    author_id: UUID
    audience: Literal["only_me", "friends", "group", "public"]
    context_id: UUID | None
    body: str
    image_url: str | None
    created_at: datetime


class PostListResponse(ApiModel):
    posts: list[PostResponse]


class PersonPostListResponse(ApiModel):
    """One person's wall, already narrowed to what this reader may see.

    `person_id` is echoed so a client can tell whose wall it drew. There is no
    total alongside it on purpose -- a count computed over all of somebody's
    posts and returned next to a filtered list is the leak this feature is
    about, stated as a number instead of as a row.
    """

    person_id: UUID
    posts: list[PostResponse]


class MessageCreateRequest(ApiModel):
    kind: Literal["text", "image", "ai_card"]
    body: Annotated[StrictStr, Field(max_length=4000)] | None = None
    image_url: RelativePhotoUrl | None = None
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


class ChatExpenseDraft(ApiModel):
    """A model-read draft whose identities come only from stored group facts."""

    title: StrictStr
    amount_vnd: PositiveMoneyVnd
    paid_by_id: UUID
    shared_by: list[UUID]
    needs_review: StrictBool


class ChatExpenseDraftResponse(ApiModel):
    context_id: UUID
    message_id: UUID
    detected: StrictBool
    draft: ChatExpenseDraft | None
    reason: StrictStr | None

    @model_validator(mode="after")
    def _detection_matches_payload(self) -> ChatExpenseDraftResponse:
        if self.detected != (self.draft is not None):
            raise ValueError("detected must match whether draft is present")
        if self.detected:
            if self.reason is not None:
                raise ValueError("a detected expense must not carry a refusal reason")
        elif self.reason is None or not self.reason.strip():
            raise ValueError("an undetected message must explain why")
        return self


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


class ScreenshotScanResponse(ApiModel):
    """One model-read transaction draft with no identity channel."""

    source: Literal["grab", "shopeefood", "banking", "receipt"]
    merchant: StrictStr
    total_vnd: PositiveMoneyVnd
    occurred_on: date | None
    needs_review: StrictBool


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


# --- friend graph (F03, F04) ------------------------------------------------


class FriendRequestCreate(ApiModel):
    """Who to ask. The requester is the actor header, never the body.

    Taking `requester_id` from the body would let anybody send requests in
    somebody else's name, and the recipient would see a request from a person
    who never sent it.
    """

    addressee_id: UUID


class FriendRequestDecision(ApiModel):
    """The addressee's answer. Accepting is one of three, not the default."""

    decision: Literal["accept", "decline", "block"]


class FriendRequestResponse(ApiModel):
    """One edge, as its two parties may see it.

    `other_display_name` is the name of whoever the reader is not, resolved by
    the repository. No telephone number appears in this model, and none can:
    the server never stored one -- see `app/api/person_identity.py`.
    """

    id: UUID
    requester_id: UUID
    addressee_id: UUID
    other_person_id: UUID
    other_display_name: str
    state: Literal["pending", "accepted", "declined", "blocked"]
    created_at: datetime
    decided_at: datetime | None = None


class FriendRequestListResponse(ApiModel):
    requests: list[FriendRequestResponse]


class FriendSummary(ApiModel):
    person_id: UUID
    display_name: str
    friends_since: datetime


class FriendListResponse(ApiModel):
    friends: list[FriendSummary]


class PersonMatchResponse(ApiModel):
    """The answer to "who holds this number".

    An id and a name. Deliberately not a telephone number, not an email, not a
    group list, not a friend count -- the caller supplied the only identifier
    in this exchange, and gets back the least the product needs to render
    "Send a friend request to Binh?".
    """

    person_id: UUID
    display_name: str


# ---------------------------------------------------------------------------
# F43 / F44 / F45 -- where the group goes
#
# Every model below is an *aggregate*. None of them carries a person id or a
# timestamp, and that is a property of the shapes rather than of the code that
# fills them: there is no field here in which an author could be returned.
# `app/places/social_map.py` explains why the audience never widens.
# ---------------------------------------------------------------------------


class MapPlace(ApiModel):
    """A pin. A place and where it is, with no visit attached."""

    place_id: StrictStr
    place_name: StrictStr
    lat: float
    lng: float
    rating: float
    rating_count: int


class VisitedPlace(ApiModel):
    """A pin the group has actually been to, and how often.

    `visit_count` and nothing else. Not "last visited", which is a timestamp in
    a friendlier coat, and not "visited by", which is the field this product
    refuses to compute.
    """

    place_id: StrictStr
    place_name: StrictStr
    lat: float
    lng: float
    visit_count: int


class UnavailableLayer(ApiModel):
    """A layer the map does not have, named rather than silently empty.

    An empty `saved` array renders as "you have saved nothing", which is a
    claim about the group. "This is not built" is a claim about the product,
    and only the second one is true.
    """

    layer: StrictStr
    reason: StrictStr


class SocialMapResponse(ApiModel):
    """F43. Four layers were specified; three are served and one is declared.

    `scanned` and `truncated` disclose how much history the counts were built
    from. A map summarising the first 500 check-ins of 900 and presenting
    itself as the group's habits is wrong in a way no reader could detect, so
    the bound ships with the answer.
    """

    context_id: UUID
    visited: list[VisitedPlace]
    trending: list[MapPlace]
    recommended: list[MapPlace]
    unavailable: list[UnavailableLayer]
    scanned_checkins: int
    truncated: bool


class HeatmapArea(ApiModel):
    id: StrictStr
    label: StrictStr
    lat: float
    lng: float
    visit_count: int
    share_percent: int


class GroupHeatmapResponse(ApiModel):
    """F44. Districts and counts -- the resolution is the privacy design.

    `unknown_area_count` is the number of check-ins that fell outside every
    district this product knows. Disclosed because a heatmap built from a
    fraction of the history, presented as the whole of it, is a confident
    wrong answer.
    """

    context_id: UUID
    areas: list[HeatmapArea]
    resolved_checkins: int
    unknown_area_count: int
    scanned_checkins: int
    truncated: bool


class MeetingPointRequest(ApiModel):
    """F45 input: areas, never people.

    There is no member field, and its absence is the feature. The mapping from
    a person to an area stays on the phone that knows it; this server receives
    an unlabelled multiset and therefore cannot disclose what it never held.
    See `app/places/meeting.py`.
    """

    from_areas: list[StrictStr]


class AreaSummary(ApiModel):
    """A district and the centroid every distance to it was measured from."""

    id: StrictStr
    label: StrictStr
    lat: float
    lng: float


class MeetingLeg(AreaSummary):
    """One journey, attributed to an area and to no one."""

    km: float


class MeetingFairness(ApiModel):
    """The arithmetic behind the ranking, so "cân bằng" is checkable.

    `worst_km` is the primary sort key: the longest journey anybody makes.
    Ranking on `total_km` instead would send the group to whichever district
    most of them already live in and hand the whole cost to the person
    furthest out, which is the opposite of meeting in the middle.
    """

    worst_km: float
    total_km: float
    spread_km: float


class MeetingCandidate(ApiModel):
    place_id: StrictStr
    place_name: StrictStr
    category: StrictStr
    address: StrictStr
    lat: float
    lng: float
    fairness: MeetingFairness
    travel: list[MeetingLeg]


class MeetingPointResponse(ApiModel):
    """F45 output: a meeting point, and the sums that justify it.

    `origins` echoes the areas the caller sent, resolved to their labels and
    centroids. Echoing is safe and necessary: the caller supplied them, and
    every kilometre in `travel` is measured from those centroids, so without
    them the fairness numbers could not be checked.

    `two_origin_inversion` is set when exactly two areas were supplied. With
    two origins the meeting point is invertible -- one origin plus the answer
    yields the other. That discloses nothing *here*, because both came from
    this caller a moment ago, but a screen that gathers areas from two members
    and shows the result to both has told each of them where the other is.
    The flag exists so that screen can say so before it does that.
    """

    context_id: UUID
    origins: list[AreaSummary]
    candidates: list[MeetingCandidate]
    two_origin_inversion: bool
