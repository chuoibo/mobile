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
    """The split, and -- said out loud -- the set of people it was split between.

    `BillSplitRequest` names nobody, so the caller does not choose that set:
    the server reads the group roster and keeps the `active` rows. A client
    that renders its own member list and looks amounts up by id therefore has
    no way to notice it is showing fewer people than were paid, which is how
    one diner and 160.000d left a screen with a "write to the ledger" button
    on it while the printed total stayed right.

    `participant_ids` is not new information -- `allocation.allocations` has
    always been keyed by exactly this set, zero-amount members included -- but
    it is newly *named*, and the validator below is what keeps the name true.
    `excluded_member_ids` is new: an invited member is on the roster the
    client renders, is not split between, and appears nowhere else here.
    """

    allocation: AllocationProposal
    assignment_state: Literal["confirmed", "ai_suggested"]
    suggested_item_keys: list[StrictStr]
    total_amount_vnd: MoneyVnd
    participant_ids: list[UUID]
    excluded_member_ids: list[UUID]

    @model_validator(mode="after")
    def _named_set_matches_the_paid_set(self) -> BillSplitResponse:
        if set(self.participant_ids) != set(self.allocation.allocations):
            # A declaration that can drift from the money is worse than none:
            # a client would compare its roster against a list nobody pays.
            raise ValueError(
                "participant_ids must be exactly the ids the allocation pays"
            )
        if set(self.participant_ids) & set(self.excluded_member_ids):
            raise ValueError("nobody can be both split between and left out")
        return self


class BillSelfClaimRequest(ApiModel):
    """The dishes the caller is claiming as their own. Nobody else's.

    Look at what is not declared here. There is no `participant_id`, no
    `person_id`, no `on_behalf_of`, and `ApiModel` forbids extras -- so a body
    that names anybody is a 422 from pydantic before a line of our code runs.
    That is the point: `PUT /bills/{id}/assignments` next door takes ids from
    the body and therefore needs a roster check to stay honest, and this route
    is the one that cannot need one, because the only identity it can express
    is the caller's own.

    The list is the caller's COMPLETE set of claims on this bill, not an
    addition to it. Absent keys are released, which is how a mis-tap is undone
    without a second endpoint, and it makes repeated submissions idempotent.
    It releases only the caller's own shares; everyone else's are untouched.
    """

    item_keys: list[Annotated[StrictStr, Field(max_length=64)]]


class FaceBoxResponse(ApiModel):
    """One rectangle, as a fraction of the image, and nothing identifying.

    `box_key` is an ordinal within this response. It is not stable between
    requests and is not derived from the pixels, so two responses cannot be
    joined on it -- see `app/domain/faces.py` for why that is deliberate.
    """

    box_key: StrictStr
    x: Annotated[float, Field(ge=0.0, le=1.0)]
    y: Annotated[float, Field(ge=0.0, le=1.0)]
    width: Annotated[float, Field(gt=0.0, le=1.0)]
    height: Annotated[float, Field(gt=0.0, le=1.0)]


class FaceBoxesResponse(ApiModel):
    photo_id: UUID
    boxes: list[FaceBoxResponse]


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

    `receivable_vnd` is deliberately outside that identity: it is what other
    people owe this person, not a share of what this person spent, and a
    reader adding it to the total would be adding money that is not theirs to
    have spent.
    """

    person_id: UUID
    display_name: StrictStr | None
    spend_vnd: MoneyVnd
    settled_vnd: MoneyVnd
    outstanding_vnd: MoneyVnd
    receivable_vnd: MoneyVnd
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
    # Catalogue key (M4). Checked against the catalogue by the service; a stop
    # may carry none and stay a free-text label.
    place_id: Annotated[StrictStr, Field(min_length=1, max_length=80)] | None = None

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
    place_id: str | None = None


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


class VoteOptionInput(ApiModel):
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


class VoteCreateRequest(ApiModel):
    question: Annotated[StrictStr, Field(min_length=1, max_length=300)]
    options: Annotated[list[VoteOptionInput], Field(min_length=2, max_length=20)]
    outing_id: UUID | None = None

    @field_validator("question")
    @classmethod
    def _strip_question(cls, value: str) -> str:
        question = value.strip()
        if not question:
            raise ValueError("question must not be blank")
        return question


class VoteBallotRequest(ApiModel):
    option_id: UUID


class VoteOptionResultResponse(ApiModel):
    id: UUID
    position: int
    label: str
    place_name: str | None
    ballot_count: int


class VoteResponse(ApiModel):
    id: UUID
    context_id: UUID
    outing_id: UUID | None
    created_by_id: UUID
    question: str
    created_at: datetime
    closed_at: datetime | None
    is_closed: bool
    options: list[VoteOptionResultResponse]
    total_ballots: int
    leading_option_ids: list[UUID]
    is_tie: bool
    decided_option_id: UUID | None
    my_option_id: UUID | None


class VoteListResponse(ApiModel):
    context_id: UUID
    votes: list[VoteResponse]


class VoteBallotResponse(ApiModel):
    vote_id: UUID
    option_id: UUID
    voter_id: UUID
    created_at: datetime
    updated_at: datetime
    replaced_previous_ballot: bool


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


class ContextLastMessage(ApiModel):
    """The newest message of a group, reduced to what a list row shows."""

    id: UUID
    kind: Literal["text", "image", "ai_card"]
    preview: StrictStr
    author_id: UUID | None
    author_display_name: StrictStr | None
    created_at: datetime


class ContextSummary(ApiModel):
    """One group in a person's conversation list.

    `my_state` is `invited` or `active` only -- a group you left is not a
    conversation you are in. `membership_id` is here so an invitee can consent
    for themselves (`POST /memberships/{id}/accept`, ADR-0014 s8) without a
    roster route that is itself behind the membership. `unread_count` is
    derived from `context_read_marks` and the feed on every read; nothing
    stores it.
    """

    id: UUID
    display_name: StrictStr
    member_count: Annotated[int, Field(strict=True, ge=0)]
    my_role: Literal["member", "admin"]
    my_state: Literal["invited", "active"]
    membership_id: UUID
    joined_at: datetime | None
    last_message: ContextLastMessage | None
    unread_count: Annotated[int, Field(strict=True, ge=0)]


class PersonContextListResponse(ApiModel):
    contexts: list[ContextSummary]


class ReadMarkRequest(ApiModel):
    """The message the reader has seen up to; the mark never moves backwards."""

    message_id: UUID


class ReadMarkResponse(ApiModel):
    context_id: UUID
    last_read_message_id: UUID
    unread_count: Annotated[int, Field(strict=True, ge=0)]


class ProfileSummary(ApiModel):
    """What a session holder is called. Nothing else is derived from it."""

    display_name: StrictStr


class ProfileCountsResponse(ApiModel):
    friends: int
    contexts: int
    outings: int
    places_checked_in: int
    memories: int


class ProfileResponse(ApiModel):
    """The caller's own profile: text they wrote, numbers the server counted,
    and which doors they have signed in through."""

    id: UUID
    display_name: StrictStr
    bio: StrictStr | None
    city: StrictStr | None
    created_at: datetime
    counts: ProfileCountsResponse
    login_methods: list[StrictStr]
    #: The person's own taste answers (M11). Present here and in no other
    #: response: `PublicPersonResponse` deliberately does not carry them.
    interests: list[StrictStr]
    budget_band: StrictStr | None


class InterestTagResponse(ApiModel):
    """One word from the closed taste vocabulary (M11, ADR-0019)."""

    id: StrictStr
    label: StrictStr


class BudgetBandResponse(ApiModel):
    """One spending band, per person per outing, in integer đồng.

    `min_vnd` inclusive, `max_vnd` exclusive; `max_vnd` null means no ceiling.
    The band travels as two bounds and never as a midpoint: a midpoint is
    arithmetic, and arithmetic on money belongs to the server that does it,
    not to the wire.
    """

    id: StrictStr
    label: StrictStr
    min_vnd: NonNegativeMoneyVnd
    max_vnd: NonNegativeMoneyVnd | None


class InterestVocabularyResponse(ApiModel):
    """Everything the personalization step is allowed to say (`GET /interests`).

    Public: the list is a product vocabulary, not anybody's data, and a client
    that cannot read it before signing in could not draw the screen that comes
    before signing in.
    """

    interests: list[InterestTagResponse]
    budget_bands: list[BudgetBandResponse]


class MyInterestsResponse(ApiModel):
    """What this person said about themself. Nobody else ever reads this shape.

    `budget_band` is null for «skipped», which is not the cheapest band: the
    recommendation falls back to «unknown» rather than guessing hard.
    """

    interests: list[StrictStr]
    budget_band: StrictStr | None


class InterestsUpdateRequest(ApiModel):
    """The whole answer, not a patch.

    `interests` is required and may be empty -- finishing the step having
    chosen nothing is a supported answer, and it has to be distinguishable
    from never having answered. `budget_band` absent or null means skipped.

    A PUT rather than a PATCH because the screen holds the complete answer: a
    partial update would need the client to say what it removed, and a client
    that gets that wrong leaves a taste nobody can see to take back.
    """

    interests: list[StrictStr]
    budget_band: StrictStr | None = None


class ProfileUpdateRequest(ApiModel):
    """A partial update. At least one field, and no field this model does not
    name (`extra=forbid` on `ApiModel`). Empty `bio`/`city` clears the field."""

    display_name: Annotated[StrictStr, Field(min_length=1, max_length=200)] | None = (
        None
    )
    bio: Annotated[StrictStr, Field(max_length=500)] | None = None
    city: Annotated[StrictStr, Field(max_length=120)] | None = None

    @model_validator(mode="after")
    def _something_to_change(self) -> ProfileUpdateRequest:
        if self.display_name is None and self.bio is None and self.city is None:
            raise ValueError("cần ít nhất một trường để sửa")
        if self.display_name is not None and not self.display_name.strip():
            raise ValueError("tên hiển thị không được rỗng")
        return self


class PublicPersonResponse(ApiModel):
    """What a friend or a groupmate may see of somebody. No counts, no login
    methods, no telephone number -- the profile is the person's, the view is
    the reader's."""

    id: UUID
    display_name: StrictStr
    bio: StrictStr | None
    city: StrictStr | None
    created_at: datetime
    relation: Literal["self", "friend", "groupmate"]


class SavedPlaceSummary(ApiModel):
    place_id: StrictStr
    name: StrictStr
    category: StrictStr
    saved_at: datetime


class SavedPlacesResponse(ApiModel):
    saved: list[SavedPlaceSummary]


class OtpRequestResponse(ApiModel):
    """A challenge was issued. The code went to the phone, never into this body."""

    challenge_id: UUID
    expires_in_seconds: Annotated[int, Field(strict=True, gt=0)]
    resend_after_seconds: Annotated[int, Field(strict=True, ge=0)]


class SessionBootstrapRequest(ApiModel):
    """One field: the secret written on a named invitation.

    There is deliberately no `person_id`. Whose session this becomes is read
    from `outing_invites.invited_person_id`, because a caller allowed to name
    the person they are about to become is a caller who may be anybody -- the
    `X-Actor-ID` hole with a token wrapped around it.
    """

    invite_token: Annotated[StrictStr, Field(min_length=1, max_length=512)]


class SessionResponse(ApiModel):
    """The raw token, handed over once; only its digest is persisted."""

    token: str
    person_id: UUID
    expires_at: datetime
    #: Which door minted this session (ADR-0016): `invite` for a redeemed
    #: named invitation, `otp` / `google` for the two self-serve doors,
    #: `genesis` for the out-of-band first session on a clean host.
    issued_via: Literal["invite", "otp", "google", "genesis"]
    #: True when this door just created the `people` row -- the client sends
    #: the person to name themselves instead of into a group they do not have.
    is_new_person: StrictBool = False
    profile: ProfileSummary
    #: Every group this person is in or invited to, so a client told who it is
    #: is also told where it may go. Same rows as `GET /people/me/contexts`.
    contexts: list[ContextSummary]
    #: The group the invitation belonged to. `None` for doors that are not an
    #: invitation (OTP, Google): those sessions may belong to no group yet.
    #:
    #: Carried because a session without it is a session that cannot show
    #: anybody anything. Signing in happens by redeeming an invitation to a
    #: TRIP, so the server knows the group at the moment it issues the session
    #: -- and there is no route that lists a person's contexts, so a client
    #: that is not told here has no second way to find out. The mobile app's
    #: `src/rudi/nguon.ts` sat in fixture mode for exactly this reason.
    #:
    #: `OutingInviteAcceptResponse` already answers with `context_id` for the
    #: link door. This makes the two doors say the same thing.
    context_id: UUID | None
    #: Where this person stands in the group the invitation belonged to.
    #: Carried so the screen can say one true sentence instead of guessing:
    #: signing in is not joining, and somebody redeeming their first invitation
    #: is `invited` and still waiting on a member, while somebody signing back
    #: in on a new phone is `active` and is not waiting on anybody.
    membership_state: Literal["invited", "active", "left"] | None
    #: The membership row this session's person may consent for.
    #:
    #: Carried for the same reason as `context_id` one field up, and it closes
    #: the same kind of gap. A named invitation means an existing member chose
    #: this person BY NAME, so ADR-0014 s8 lets the invitee consent for
    #: themselves -- `accept_context_membership` requires only `is_invitee`.
    #: But consenting means calling `POST /memberships/{membership_id}/accept`,
    #: and a client that is told only who it is and which group cannot name the
    #: row: `GET /contexts/{id}/members` is behind the very membership being
    #: accepted, so the id is unreachable until after it is no longer needed.
    #:
    #: Without this field the product had a door that opened onto a wall.
    #: Somebody could redeem a real invitation, get a real session, and then
    #: sit at `invited` forever with no button that could work.
    #:
    #: Free of charge: `ensure_invited_membership` returns the row, so this is
    #: a field on an object already in hand rather than a second query.
    #:
    #: `OutingInviteAcceptResponse` has answered with `membership_id` all
    #: along -- the LINK door has always named the row. The named door was the
    #: one that did not, which is the same asymmetry `context_id` fixed one
    #: field up, found the same way. `None` when the door was not an invitation.
    membership_id: UUID | None


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
    """A photograph onto the group's wall, optionally naming where it was taken.

    `place_id` is the second of the two photo sources ADR-0017 §2.4 allows on a
    place: the group's own pictures, shown only to that group. It names a row
    in the catalogue and nothing more -- the display name and the coordinates
    are read server-side, exactly as `CheckinCreateRequest` does, so a caller
    cannot photograph their kitchen and file it under a restaurant's name.

    Optional, and staying optional matters: most pictures on a wall are of
    people, not of venues, and forcing a place onto them would fill the
    catalogue with rows that answer «what does this place look like» with a
    photograph of somebody's birthday cake.
    """

    image_url: RelativePhotoUrl
    caption: str | None = None
    place_id: Annotated[StrictStr, Field(min_length=1, max_length=200)] | None = None


class CheckinCreateRequest(ApiModel):
    """F46. The group arrived somewhere, and only the group says where.

    One field names the place and nothing describes it. The name and the
    coordinates are looked up server-side from the `places` table, so a
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


ReactionKind = Literal["heart", "haha", "like", "wow", "sad", "fire"]


class ReactionSummary(ApiModel):
    """One kind of reaction on one message: how many, and whether the reader
    is among them. Names are not listed; the count is what a chat shows."""

    kind: ReactionKind
    count: Annotated[int, Field(strict=True, ge=1)]
    mine: StrictBool


class ReactionRequest(ApiModel):
    kind: ReactionKind


class MessageReactionsResponse(ApiModel):
    message_id: UUID
    reactions: list[ReactionSummary]


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
    reactions: list[ReactionSummary] = []


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


class CompanionTurnRequest(ApiModel):
    """Whether a person asked for this turn or the client is offering one.

    The body is optional and the default is the offer, because that is what the
    shipped client sends: it posts this route after every message with no body
    at all. Only a caller that knows a human addressed the companion should set
    the flag -- the server cannot tell, and deliberately does not look, since
    `plan_turn` is handed message metadata and never message text.
    """

    requested: bool = False


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


class PostedMessageResponse(MessageResponse):
    """`POST /messages` answers with the stored message and what the server did
    about a slash command or mention in it (M3, `app/domain/chat_intent.py`).

    The message is ALWAYS stored first; the companion, the vote or a refusal
    ride along in the same answer so a rate-limited or refused intent never
    turns into a lost message and a retried duplicate.
    """

    intent: Literal["plan", "chia_bill", "vote", "mention"] | None = None
    companion: CompanionTurnResponse | None = None
    vote: VoteResponse | None = None
    # `/chia-bill`: one server-authored `expense_draft` card, or nothing.
    expense_card: MessageResponse | None = None
    intent_error: (
        Literal[
            "vote_malformed",
            "companion_rate_limited",
            "chia_bill_not_available",
            "chia_bill_no_expenses",
            "chia_bill_refused",
        ]
        | None
    ) = None


class BatchCreateRequest(ApiModel):
    context_id: UUID
    expense_version_ids: list[UUID] | None = None
    due_at: datetime

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


class ContextBatchView(ApiModel):
    """One collection round of a group, as the settlement screen lists it.

    `status` is the batch's own state (`app.domain.collection.STATES`). The
    counts are folded from the board (`GET /batches/{batch_id}/obligations`)
    so the two never disagree; `total_vnd` adds the obligations' amounts on
    the server. Nothing here is a share.
    """

    batch_id: UUID
    status: Literal[
        "accruing",
        "frozen",
        "published",
        "collecting",
        "completed",
        "closed_with_exceptions",
        "cancelled",
    ]
    created_at: datetime
    published_at: datetime | None
    obligation_count: int
    confirmed_count: int
    disputed_count: int
    total_vnd: MoneyVnd


class ContextBatchesResponse(ApiModel):
    context_id: UUID
    batches: list[ContextBatchView]


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


# -- F31 / F33 / F36: what the companion knows about a group -----------------


class PreferenceTaste(ApiModel):
    """One taste, with the count that produced its score.

    `score` is a ratio, and a ratio printed by itself cannot be checked by the
    person reading it. `checkin_count` is the numerator, shipped alongside, so
    the arithmetic is auditable from the response -- the same rule
    `SuggestionBasis` follows for money.

    `score` is a float on purpose and is **not** money. Law 1 governs đồng, and
    every money field in this file is a strict integer named `_vnd`; an
    affinity has no unit and rounding one to two decimals loses nothing anybody
    can be owed.
    """

    label: StrictStr
    checkin_count: int
    #: 0.0 – 1.0. The taste's share of the busiest taste *in its own section*,
    #: so the top row of each section is 1.0.
    score: float


class PreferenceSection(ApiModel):
    """One heading of the profile.

    `taste_count` is how many distinct tastes were found; `tastes` is capped.
    Both travel because a truncated list with no count reads as a complete one.
    """

    section: Literal["food", "activity"]
    taste_count: int
    tastes: list[PreferenceTaste]


class PreferenceProfileResponse(ApiModel):
    """F31. What this group keeps choosing, recomputed from its own rows.

    There is no `group_preferences` table. Every figure here is derived on the
    request that asks, from check-ins and from ledger-summed trip totals --
    invariant 3, because a stored profile is a cache and a stale affinity has
    no receipt attached for anybody to notice it by.

    `has_profile` is the honest half. A group that has checked in nowhere has
    no tastes to report, and inventing one from photographs would be the
    product asserting a preference nobody expressed.
    """

    context_id: UUID
    has_profile: bool
    #: `ok` | `no_behaviour`
    reason: str
    sections: list[PreferenceSection]
    #: Check-ins that carried a catalogue category. Rows whose place has left
    #: the catalogue are counted nowhere rather than under a stale id.
    checkin_count: int
    outing_count: int
    split_total_vnd: MoneyVnd
    avg_per_person_vnd: MoneyVnd | None


class ConversationBasis(ApiModel):
    """Why the companion spoke, in counts only.

    Deliberately carries no message text and no author. The group's own words
    are what the model reads -- that is the feature -- but they are not echoed
    back onto a card, and nothing here is written to a log.

    `member_count` counts ACTIVE members. The mockup's line says "4 người đang
    online"; this product has no presence signal at all, so the field is named
    for what it actually counts rather than for what the mockup wished it said.
    """

    message_count: int
    speaker_count: int
    member_count: int


class ContextualSuggestionResponse(ApiModel):
    """F33. The card that answers what the group is saying right now.

    Same shape as `GroupSuggestionResponse` and a different question: F32 reads
    the group's history, F33 reads its last few turns. `suggested: false` with
    a reason stays the honest answer -- a silent group has nothing to react to,
    and a model outage is not something to paper over with a written-in card.
    """

    context_id: UUID
    suggested: bool
    #: `ok` | `no_conversation` | `unavailable` | `ungrounded`
    reason: str
    title: str | None
    when_text: str | None
    stops: list[SuggestionStop]
    basis: ConversationBasis
    #: A claim about who wrote the sentences on this card.
    source: Literal["ai", "none"]


class AlbumPhoto(ApiModel):
    """One photograph in an album, pointing at the wall's own URL.

    `image_url` is the `/contexts/{id}/photos/{id}` path the memory wall
    serves, verbatim. The album copies no bytes and mints no second media
    route, so reading a photograph out of an album still goes through the one
    gate that guards it.
    """

    memory_id: UUID
    image_url: RelativePhotoUrl
    caption: str | None
    created_at: datetime
    reaction_count: int
    comment_count: int


class AlbumPlace(ApiModel):
    place_id: StrictStr
    place_name: str | None


class AlbumSummary(ApiModel):
    """One row of the album shelf.

    `photo_count` is the same figure the recap screen prints for this trip,
    because both come from the same window over the same rows.
    """

    outing_id: UUID
    title: StrictStr
    period_label: StrictStr
    starts_on: date
    ends_on: date
    in_progress: bool
    photo_count: int
    checkin_count: int
    place_count: int
    split_total_vnd: MoneyVnd
    expense_count: int
    headcount: int
    #: The album's newest photograph, or null for a trip with none. A cover is
    #: a photograph the group already published to its own wall, never a
    #: thumbnail generated somewhere else.
    cover: AlbumPhoto | None


class AlbumListResponse(ApiModel):
    context_id: UUID
    albums: list[AlbumSummary]


class AlbumResponse(ApiModel):
    """F36. One trip, read as an album.

    Nothing here is generated. `title` is the outing's own title and
    `period_label` is its year, computed by the server and kept in separate
    fields so a client never has to guess which half a machine wrote -- the
    spec's AI-composed album name is not implemented, and this response does
    not pretend otherwise.

    `highlights` is a subset of `photos`, ordered by the hearts the group
    itself left. It is their judgement counted, not a model's guess at it.
    """

    context_id: UUID
    outing_id: UUID
    title: StrictStr
    period_label: StrictStr
    starts_on: date
    ends_on: date
    in_progress: bool
    photos: list[AlbumPhoto]
    photo_count: int
    places: list[AlbumPlace]
    place_count: int
    checkin_count: int
    highlights: list[AlbumPhoto]
    split_total_vnd: MoneyVnd
    expense_count: int
    headcount: int


class ReelPick(ApiModel):
    """One AI-picked memory with every displayed fact owned by the server."""

    memory_id: UUID
    image_url: RelativePhotoUrl | None
    caption: str | None
    place_name: str | None
    created_at: datetime
    reaction_count: int
    comment_count: int
    note: StrictStr

    _created_at_has_timezone = field_validator("created_at")(_require_timezone)


class ReelResponse(ApiModel):
    """F37. AI provenance stays separate from the group's heart highlights."""

    context_id: UUID
    outing_id: UUID
    reeled: bool
    reason: Literal["ok", "no_memories", "unavailable", "ungrounded"]
    source: Literal["ai", "none"]
    title: StrictStr | None
    picks: list[ReelPick]
    #: Rows offered by the server, never a count restated by the model.
    considered_count: int
