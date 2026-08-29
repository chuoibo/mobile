"""Application workflows that connect HTTP validation, domain, and storage."""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.api import companion_places
from app.api.cursors import CursorError, decode_cursor, encode_cursor
from app.api.deps import Actor, Companion, Suggester
from app.api.errors import ApiProblem, RepositoryConflict
from app.api.limits import OBJECTION_KINDS, QUOTA_CONSUMING_OBJECTIONS
from app.api.repository import (
    WALL_CLOCK_ZONE,
    ApiRepository,
    BankRecipientRecord,
    BillRecord,
    FriendEdgeRecord,
    GuestLinkDraft,
    MembershipRecord,
    MemoryRecord,
    MessageRecord,
    ObligationDraft,
    OutingInviteRecord,
    OutingRecord,
    PersonFinanceSummary,
    PersonRecord,
    RecapOutingRecord,
    StopCheckinRecord,
    UploadedImageRecord,
)
from app.api.schemas import (
    AllocationProposal,
    BankRecipientRequest,
    BankRecipientResponse,
    BatchCreateRequest,
    BatchCreateResponse,
    BatchObligationsResponse,
    BatchObligationView,
    BatchPublishRequest,
    BatchPublishResponse,
    BillAssignmentsRequest,
    BillCreateRequest,
    BillDiscountResponse,
    BillItemResponse,
    BillResponse,
    BillShareResponse,
    BillSplitRequest,
    BillSplitResponse,
    BillSurchargeResponse,
    CheckinCreateRequest,
    CompanionTurnResponse,
    ContextBalanceEntry,
    ContextBalancesResponse,
    ContextCreateRequest,
    ContextResponse,
    ExpenseConfirmationRequest,
    ExpenseConfirmationResponse,
    ExpenseInput,
    ExpenseProposalResponse,
    FriendListResponse,
    FriendRequestCreate,
    FriendRequestDecision,
    FriendRequestListResponse,
    FriendRequestResponse,
    FriendSummary,
    GroupRecapResponse,
    GroupSuggestionResponse,
    MemberRoleRequest,
    MembershipInviteRequest,
    MembershipListResponse,
    MembershipResponse,
    MemoryCreateRequest,
    MemoryListResponse,
    MemoryQuery,
    MemoryResponse,
    MessageCreateRequest,
    MessageListResponse,
    MessageQuery,
    MessageResponse,
    ObligationResponse,
    OutingCheckinListResponse,
    OutingCreateRequest,
    OutingInviteAcceptResponse,
    OutingInviteCreateRequest,
    OutingInviteResponse,
    OutingListResponse,
    OutingResponse,
    OutingStopResponse,
    OutingTimelineRequest,
    PaymentReportRequest,
    PaymentReportResponse,
    PersonMatchResponse,
    PublishedGuestLink,
    PublishedObligation,
    RecapOutingResponse,
    ReceiptConfirmationRequest,
    ReceiptConfirmationResponse,
    SettlementTransferProposal,
    StopCheckinResponse,
    SuggestionBasis,
    SuggestionStop,
    UploadedImageResponse,
)
from app.domain import permissions
from app.domain.allocator import allocate
from app.domain.bank_account import BankAccountError, normalise_destination
from app.domain.bill import BillError, allocator_input_from_bill
from app.domain.capability import CapabilityScopeError, capability_scope
from app.domain.collection import CollectionError, transition, unmet_publish_gates
from app.domain.companion import CompanionError, ground_card, plan_turn
from app.domain.contract import AllocationError
from app.domain.expense import component_rollups
from app.domain.friendship import (
    BLOCKED_IS_SILENT,
    Decision,
    FriendshipError,
)
from app.domain.friendship import (
    decide as decide_friendship,
)
from app.domain.friendship import (
    open_request as open_friendship_request,
)
from app.domain.ledger import (
    LedgerError,
    group_balances,
    merge_obligations,
    obligation_status,
    obligations_from_allocations,
    settlement_plan,
)
from app.domain.suggestion import (
    SuggestionError,
    ground_suggestion,
    summarise_history,
)
from app.media.images import ImageRejected, sanitize_image
from app.media.storage import PhotoStorage, new_storage_key
from app.payments.banks import describe_bank
from app.payments.vietqr import VietQRError, build_payload
from app.places.catalog import find_place
from app.web.guest_view import GuestViewError, build_guest_view
from app.web.objection_view import (
    OBJECTION_REASONS,
    ObjectionError,
    build_not_me_view,
    build_wrong_amount_view,
)

logger = logging.getLogger(__name__)

CONTEXT_WINDOW = 40
#: How far back F32 reads check-ins when working out what kind of place a
#: group keeps choosing. A ceiling rather than a window: the digest is a
#: shape, and one more year of arrivals does not change it.
SUGGESTION_HISTORY_LIMIT = 100
OUTING_INVITE_TTL = timedelta(days=7)


def _now() -> datetime:
    return datetime.now(UTC)


def token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def _minute_of_day(value: str) -> int:
    # A stop is a wall-clock time of day with no timezone, so it must never
    # pass through a datetime that the server could shift.
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def _clock(minute: int) -> str:
    # Convert the stored wall-clock value directly for the same timezone-free
    # reason; this representation is stable in every server timezone.
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _guest_actor(token: str) -> Actor:
    """A guest has no account, and the product deliberately keeps it that way:
    spec section 8.6 rules out OTP for guests in v1 because it would break the
    spread that makes the collection loop work at all.

    So the subject of a guest action is the capability itself. The token digest
    names the bearer without pretending to know which person is holding it,
    which is exactly the claim the guest page is careful never to make.
    """
    return Actor(
        id=f"capability:{token_digest(token).hex()[:16]}",
        roles=frozenset({"guest"}),
        context_ids=frozenset(),
    )


def _require_permission(
    action: str,
    actor: Actor,
    context: dict,
    *,
    extra_roles: frozenset[str] | set[str] = frozenset(),
) -> None:
    """The one place a permission is decided.

    Facts are built here rather than accepted from a caller. `denial_reason`
    refuses a plain dict on purpose: a dict assembled from a request body and a
    dict read out of the database look identical to a function signature, and
    that resemblance is how a confused deputy gets in.

    `provenance` records which layer proved the predicates, so a later audit can
    answer "who said so" rather than only "it was allowed".
    """
    facts = permissions.AuthorizationFacts(
        actor_id=str(actor.id),
        # `extra_roles` carries a role the service just derived from the
        # resource, such as "you are the owner because you created this batch
        # one line ago". It is never read from a request body.
        roles=frozenset(actor.roles) | frozenset(extra_roles),
        resource_id=context.get("resource_id"),
        proven=frozenset(name for name, proved in context.items() if proved is True),
        provenance="api_service",
    )
    reason = permissions.denial_reason(action, facts)
    if reason is not None:
        raise ApiProblem(403, "permission_denied", reason)


def _image_rejection_problem(exc: ImageRejected) -> ApiProblem:
    status_code = {
        "image_too_large": 413,
        "image_dimensions_too_large": 413,
        "not_an_image": 415,
    }[exc.code]
    return ApiProblem(status_code, exc.code, exc.detail)


def _require_photo_url_context(
    context_id: uuid.UUID, image_url: str | None
) -> None:
    """Refuse a photo url that points into another group's storage.

    The schema already pins `image_url` to `/contexts/{uuid}/photos/{uuid}`,
    so a malformed value should not arrive here. "Should not" is not a gate:
    this parses defensively rather than inheriting the promise of the layer
    above it, because the day that promise moves, a bad request body becomes a
    500 instead of a 422.
    """

    if image_url is None:
        return
    # ["", "contexts", <context id>, "photos", <photo id>]
    parts = image_url.split("/")
    try:
        if (
            len(parts) != 5
            or parts[0]
            or parts[1] != "contexts"
            or parts[3] != "photos"
        ):
            raise ValueError(image_url)
        photo_context_id = uuid.UUID(parts[2])
        uuid.UUID(parts[4])
    except ValueError:
        raise ApiProblem(
            422,
            "photo_url_invalid",
            "Photo URL is not a path into this product's photo storage",
        ) from None
    if photo_context_id != context_id:
        raise ApiProblem(
            422,
            "photo_context_mismatch",
            "Photo URL context does not match the requested context",
        )


def _uploaded_image_response(
    record: UploadedImageRecord, url: str
) -> UploadedImageResponse:
    return UploadedImageResponse(
        id=record.id,
        context_id=record.context_id,
        url=url,
        content_type=record.content_type,
        byte_size=record.byte_size,
        width=record.width,
        height=record.height,
        created_at=record.created_at,
    )


def _bank_recipient_response(record: BankRecipientRecord) -> BankRecipientResponse:
    bank = describe_bank(record.bank_bin)
    return BankRecipientResponse(
        id=record.id,
        recipient_id=record.recipient_id,
        bank_bin=record.bank_bin,
        bank_name=bank.name,
        bank_recognised=bank.recognised,
        account_number=record.account_number,
        account_name=record.account_name,
        confirmed_at=record.confirmed_at,
    )


def _allocator_input(proposal: ExpenseInput) -> dict:
    """Translate validated UUID wire identities to the frozen domain contract."""

    return {
        "participants": [str(value) for value in proposal.participants],
        "total_vnd": proposal.total_amount_vnd,
        "items": [
            {
                "item_id": item.item_id,
                "amount_vnd": item.amount_vnd,
                "shared_by": [str(value) for value in item.shared_by],
            }
            for item in proposal.items
        ],
        "surcharges": [
            {
                "surcharge_id": surcharge.surcharge_id,
                "kind": surcharge.kind,
                "amount_vnd": surcharge.amount_vnd,
                "mode": surcharge.mode,
            }
            for surcharge in proposal.surcharges
        ],
        "discounts": [
            {
                "discount_id": discount.discount_id,
                "amount_vnd": discount.amount_vnd,
                "scope": discount.scope,
                "item_id": discount.item_id,
            }
            for discount in proposal.discounts
        ],
        "advancer_id": str(proposal.paid_by_id),
    }


def _wire_allocation(result: dict) -> AllocationProposal:
    return AllocationProposal(
        allocations={
            uuid.UUID(key): value for key, value in result["allocations"].items()
        },
        exact_shares={
            uuid.UUID(key): value for key, value in result["exact_shares"].items()
        },
        rounding_gainers=[uuid.UUID(value) for value in result["rounding_gainers"]],
        warnings=result["warnings"],
    )


def _wire_bill(record: BillRecord) -> BillResponse:
    suggested_item_keys = sorted(
        (
            item.item_key
            for item in record.items
            if any(share.source == "ai_suggested" for share in item.shares)
        ),
        key=lambda key: key.encode("utf-8"),
    )
    all_confirmed = bool(record.items) and all(
        item.shares and all(share.source == "confirmed" for share in item.shares)
        for item in record.items
    )
    return BillResponse(
        id=record.id,
        context_id=record.context_id,
        printed_total_vnd=record.printed_total_vnd,
        items_total_vnd=record.items_total_vnd,
        needs_review=record.needs_review,
        created_by_id=record.created_by_id,
        created_at=record.created_at,
        assignment_state="confirmed" if all_confirmed else "ai_suggested",
        suggested_item_keys=suggested_item_keys,
        surcharges=[
            BillSurchargeResponse(
                surcharge_key=surcharge.surcharge_key,
                kind=surcharge.kind,
                amount_vnd=surcharge.amount_vnd,
                mode=surcharge.mode,
            )
            for surcharge in record.surcharges
        ],
        discounts=[
            BillDiscountResponse(
                discount_key=discount.discount_key,
                amount_vnd=discount.amount_vnd,
                scope=discount.scope,
                item_key=discount.target_item_key,
            )
            for discount in record.discounts
        ],
        items=[
            BillItemResponse(
                item_key=item.item_key,
                name=item.name,
                quantity=item.quantity,
                unit_price_vnd=item.unit_price_vnd,
                line_total_vnd=item.line_total_vnd,
                position=item.position,
                shares=[
                    BillShareResponse(
                        participant_id=share.participant_id,
                        source=share.source,
                        decided_by_id=share.decided_by_id,
                        decided_at=share.decided_at,
                    )
                    for share in item.shares
                ],
            )
            for item in record.items
        ],
    )


def _wire_membership(record: MembershipRecord) -> MembershipResponse:
    return MembershipResponse(
        id=record.id,
        context_id=record.context_id,
        person_id=record.person_id,
        display_name=record.display_name,
        state=record.state,
        role=record.role,
        invited_by_id=record.invited_by_id,
        joined_at=record.joined_at,
        left_at=record.left_at,
        created_at=record.created_at,
    )


def _wire_friend_edge(record: FriendEdgeRecord) -> FriendRequestResponse:
    """One edge onto the wire. No telephone number exists to omit."""
    return FriendRequestResponse(
        id=record.id,
        requester_id=record.requester_id,
        addressee_id=record.addressee_id,
        other_person_id=record.other_person_id,
        other_display_name=record.other_display_name,
        state=record.state,
        created_at=record.created_at,
        decided_at=record.decided_at,
    )


def _wire_memory(record: MemoryRecord) -> MemoryResponse:
    return MemoryResponse(
        id=record.id,
        context_id=record.context_id,
        author_id=record.author_id,
        kind=record.kind,  # type: ignore[arg-type]
        image_url=record.image_url,
        caption=record.caption,
        place_id=record.place_id,
        place_name=record.place_name,
        lat=record.lat,
        lng=record.lng,
        created_at=record.created_at,
        cursor=encode_cursor(record.created_at, record.id),
    )


def _wire_outing(record: OutingRecord) -> OutingResponse:
    return OutingResponse(
        id=record.id,
        context_id=record.context_id,
        created_by_id=record.created_by_id,
        title=record.title,
        starts_on=record.starts_on,
        ends_on=record.ends_on,
        headcount=record.headcount,
        budget_per_person_vnd=record.budget_per_person_vnd,
        created_at=record.created_at,
        stops=[
            OutingStopResponse(
                id=stop.id,
                position=stop.position,
                at=_clock(stop.minute_of_day),
                label=stop.label,
                place_name=stop.place_name,
            )
            for stop in record.stops
        ],
    )


def _wire_recap_outing(record: RecapOutingRecord) -> RecapOutingResponse:
    """One trip on the recap, finished or under way.

    Shared by both lists on purpose. A trip the group is still on has to arrive
    in the same shape as one that is over, or the screen ends up with two ways
    to read a trip's spending and two chances to read one of them wrong.
    """

    return RecapOutingResponse(
        outing_id=record.outing.id,
        title=record.outing.title,
        starts_on=record.outing.starts_on,
        ends_on=record.outing.ends_on,
        headcount=record.outing.headcount,
        stops=_wire_outing(record.outing).stops,
        split_total_vnd=record.split_total_vnd,
        expense_count=record.expense_count,
        memory_count=record.memory_count,
    )


def _wire_outing_invite(
    record: OutingInviteRecord, raw_token: str | None
) -> OutingInviteResponse:
    return OutingInviteResponse(
        id=record.id,
        outing_id=record.outing_id,
        source=record.source,
        invited_person_id=record.invited_person_id,
        invited_by_id=record.invited_by_id,
        created_at=record.created_at,
        expires_at=record.expires_at,
        revoked_at=record.revoked_at,
        invite_token=raw_token,
        invite_path=f"/outing-invites/{raw_token}" if raw_token is not None else None,
    )


def _wire_message(record: MessageRecord) -> MessageResponse:
    return MessageResponse(
        id=record.id,
        context_id=record.context_id,
        author_id=record.author_id,
        kind=record.kind,
        body=record.body,
        image_url=record.image_url,
        card=record.card,
        created_at=record.created_at,
        cursor=encode_cursor(record.created_at, record.id),
    )


def _group_budget_per_person_vnd() -> int | None:
    """Read the optional catalogue budget without creating a second source."""

    try:
        from app.places.catalog import GROUP
    except ImportError:
        return None
    budget = GROUP.get("budget_per_person_vnd")
    return budget if isinstance(budget, int) else None


class ApiService:
    def __init__(
        self,
        repository: ApiRepository,
        *,
        photo_storage: PhotoStorage | None = None,
    ):
        self.repository = repository
        self.photo_storage = PhotoStorage() if photo_storage is None else photo_storage

    def register_person(
        self, person_id: uuid.UUID, display_name: str, actor: Actor
    ) -> tuple[PersonRecord, bool]:
        """Say who an id belongs to. Returns the record and whether it is new.

        Creating and renaming are two different acts with two different rules,
        so they are two entries in the permission table rather than one. A
        member may name somebody who has no row -- that is the only way a name
        ever enters this product, since nobody signs up before a friend adds
        them to a dinner. Changing a name that already exists is the person's
        own business: a display name is what a stranger reads on a guest page
        while deciding whether to send money.
        """
        existing = self.repository.get_person(person_id)
        if existing is None:
            _require_permission("register_person_identity", actor, {})
            try:
                return self.repository.create_person(person_id, display_name), True
            except RepositoryConflict as exc:
                raise ApiProblem(
                    409, exc.code.lower(), "Person identity conflicted"
                ) from exc
        if existing.display_name == display_name:
            # A retry is not an attempt to change anything, and answering 403
            # to a client's own retry makes a dropped response look like an
            # attack. Checked before the rename permission for that reason.
            return existing, False
        _require_permission(
            "rename_person_identity", actor, {"is_self": actor.id == person_id}
        )
        renamed = self.repository.rename_person(person_id, display_name)
        if renamed is None:
            raise ApiProblem(
                404, "person_not_found", "Person disappeared during rename"
            )
        return renamed, False

    #: How many confirmed movements the personal screen reads back. The screen
    #: shows a handful and links to the rest; an unbounded read here would let
    #: one long-lived group make this route the slowest in the product.
    FINANCE_MOVEMENT_LIMIT = 20

    def person_finance_summary(
        self, person_id: uuid.UUID, actor: Actor
    ) -> PersonFinanceSummary:
        """One person's money, readable only by that person.

        Self-only, and checked here rather than in the route, because this is
        the whole privacy rule for the screen: spend, debts and the names of
        everyone they have settled with. There is no group-admin exception --
        an admin runs the collection round, which is a different question from
        what a member has spent all year.

        No 404 for an id with no ledger rows. A person who has not split
        anything yet has a real and correct answer, and it is zero; answering
        404 would make a new account indistinguishable from a typo, and the
        screen would have to guess which.
        """
        if actor.id != person_id:
            raise ApiProblem(
                403,
                "not_your_finances",
                "A finance summary is readable only by the person it describes",
            )
        return self.repository.person_finance_summary(
            person_id, movement_limit=self.FINANCE_MOVEMENT_LIMIT
        )

    def _require_registered_person(self, person_id: uuid.UUID) -> None:
        """Refuse before the foreign key does.

        `contexts.created_by_id` and `memberships.person_id` both point at
        `people`, and nothing wrote that table until `PUT /people/{id}` existed.
        Every call reached PostgreSQL and came back as `ForeignKeyViolation` on
        `fk_contexts_created_by` -- HTTP 500, no code, and nothing telling the
        caller that the fix is one request away.
        """
        if self.repository.get_person(person_id) is None:
            raise ApiProblem(
                409,
                "person_not_registered",
                "Register this person with PUT /people/{person_id} first",
            )

    def create_context(
        self, request: ContextCreateRequest, actor: Actor
    ) -> ContextResponse:
        _require_permission("create_context", actor, {})
        self._require_registered_person(actor.id)
        context = self.repository.create_context(request.display_name, actor.id)

        # A context must not be born with nobody allowed to administer it.
        # Bootstrap the creator through the same invited -> active transition
        # used by every later member, inside the request transaction.
        membership = self.repository.add_member(
            context.id, actor.id, actor.id, role="admin"
        )
        accepted = self.repository.accept_membership(membership.id, _now())
        if accepted is None:
            raise ApiProblem(
                409,
                "creator_membership_missing",
                "Creator membership disappeared during context creation",
            )
        return ContextResponse(
            id=context.id,
            display_name=context.display_name,
            created_by_id=context.created_by_id,
            created_at=context.created_at,
        )

    def invite_context_member(
        self,
        context_id: uuid.UUID,
        request: MembershipInviteRequest,
        actor: Actor,
    ) -> MembershipResponse:
        _require_permission(
            "invite_context_member",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        self._require_registered_person(request.person_id)
        try:
            membership = self.repository.add_member(
                context_id, request.person_id, actor.id
            )
        except RepositoryConflict as exc:
            raise ApiProblem(
                409, exc.code.lower(), "Membership invitation conflicted"
            ) from exc
        return _wire_membership(membership)

    def accept_context_membership(
        self, membership_id: uuid.UUID, actor: Actor
    ) -> MembershipResponse:
        """Apply the authorization predicate warranted by invitation provenance.

        A named invite carries an existing member's identity choice, so the
        invitee may consent. A bearer link identifies only its holder, so a
        different person who is already active in the group must approve it.
        """
        membership = self.repository.get_membership(membership_id)
        if membership is None:
            raise ApiProblem(404, "membership_not_found", "Membership does not exist")

        if membership.origin == "link":
            _require_permission(
                "approve_link_join_request",
                actor,
                {
                    "is_group_member": self.repository.is_member(
                        membership.context_id, actor.id
                    ),
                    "is_not_self": actor.id != membership.person_id,
                },
            )
        else:
            _require_permission(
                "accept_context_membership",
                actor,
                {"is_invitee": membership.person_id == actor.id},
            )

        try:
            membership = self.repository.accept_membership(membership_id, _now())
        except RepositoryConflict as exc:
            raise ApiProblem(
                409, exc.code.lower(), "Membership acceptance conflicted"
            ) from exc
        if membership is None:
            raise ApiProblem(404, "membership_not_found", "Membership does not exist")
        return _wire_membership(membership)

    def leave_context(
        self, context_id: uuid.UUID, person_id: uuid.UUID, actor: Actor
    ) -> None:
        _require_permission(
            "leave_context",
            actor,
            {
                "is_group_member": self.repository.is_member(context_id, actor.id),
                "is_self": actor.id == person_id,
            },
        )
        membership = self.repository.leave_context(context_id, person_id, _now())
        if membership is None:
            raise ApiProblem(
                404, "membership_not_found", "Active membership does not exist"
            )

    def get_context(self, context_id: uuid.UUID, actor: Actor) -> ContextResponse:
        """Trade a group id for the group's name, for members only.

        The order of the two checks below is the security property, not an
        implementation detail. A group id travels in share links, so answering
        404 for an unknown id and 403 for a real one would turn this route into
        an oracle: a stranger could enumerate ids and learn which groups exist.
        Membership is therefore decided before the row is read, and a
        non-member gets the same 403 either way.
        """
        _require_permission(
            "view_context_members",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        record = self.repository.get_context(context_id)
        if record is None:
            raise ApiProblem(404, "context_not_found", "Context does not exist")
        return ContextResponse(
            id=record.id,
            display_name=record.display_name,
            created_by_id=record.created_by_id,
            created_at=record.created_at,
        )

    def list_context_members(
        self, context_id: uuid.UUID, actor: Actor
    ) -> MembershipListResponse:
        # Former members are denied. Historical obligations remain visible
        # through their own scoped resources; the current roster is current
        # group data and must not extend access after somebody leaves.
        _require_permission(
            "view_context_members",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        return MembershipListResponse(
            context_id=context_id,
            members=[
                _wire_membership(member)
                for member in self.repository.list_members(context_id)
            ],
        )

    def get_context_balances(
        self, context_id: uuid.UUID, actor: Actor
    ) -> ContextBalancesResponse:
        """Derive net positions and consent-required transfer proposals."""

        _require_permission(
            "view_context_members",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )

        inputs = self.repository.load_batch_inputs(context_id, None)
        receipt_rows = self.repository.load_confirmed_receipts(context_id)
        receipts = {
            (str(sender_id), str(recipient_id)): amount_vnd
            for (sender_id, recipient_id), amount_vnd in receipt_rows.items()
        }
        try:
            obligations = merge_obligations(
                [
                    obligation
                    for expense in inputs.expenses
                    for obligation in obligations_from_allocations(
                        {
                            str(allocation.participant_id): allocation.amount_vnd
                            for allocation in expense.allocations
                        },
                        str(expense.paid_by_id),
                        str(expense.version_id),
                    )
                ]
            )
            balances = group_balances(obligations, receipts)
            plan = settlement_plan(balances)
        except LedgerError as exc:
            raise ApiProblem(
                409, exc.code, "Confirmed ledger events cannot be balanced"
            ) from exc

        return ContextBalancesResponse(
            balances=[
                ContextBalanceEntry(person_id=uuid.UUID(person_id), net_vnd=net_vnd)
                for person_id, net_vnd in sorted(
                    balances.items(), key=lambda item: uuid.UUID(item[0]).bytes
                )
            ],
            transfers=[
                SettlementTransferProposal(
                    sender_id=uuid.UUID(transfer["sender_id"]),
                    recipient_id=uuid.UUID(transfer["recipient_id"]),
                    amount_vnd=transfer["amount_vnd"],
                )
                for transfer in plan["transfers"]
            ],
            proven_minimal=plan["proven_minimal"],
            transfer_count=plan["transfer_count"],
        )

    def _store_uploaded_image(
        self,
        raw: bytes,
        *,
        context_id: uuid.UUID | None,
        owner_person_id: uuid.UUID | None,
        uploaded_by_id: uuid.UUID,
    ) -> UploadedImageRecord:
        try:
            sanitized = sanitize_image(raw)
        except ImageRejected as exc:
            raise _image_rejection_problem(exc) from None

        storage_key = new_storage_key()
        self.photo_storage.write(storage_key, sanitized.data)
        return self.repository.create_uploaded_image(
            storage_key=storage_key,
            context_id=context_id,
            owner_person_id=owner_person_id,
            uploaded_by_id=uploaded_by_id,
            content_type=sanitized.content_type,
            byte_size=len(sanitized.data),
            width=sanitized.width,
            height=sanitized.height,
            now=_now(),
        )

    def upload_context_photo(
        self, context_id: uuid.UUID, raw: bytes, actor: Actor
    ) -> UploadedImageResponse:
        _require_permission(
            "post_group_memory",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        record = self._store_uploaded_image(
            raw,
            context_id=context_id,
            owner_person_id=None,
            uploaded_by_id=actor.id,
        )
        return _uploaded_image_response(
            record, f"/contexts/{context_id}/photos/{record.id}"
        )

    def read_context_photo(
        self, context_id: uuid.UUID, image_id: uuid.UUID, actor: Actor
    ) -> tuple[bytes, str]:
        _require_permission(
            "view_group_memories",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        record = self.repository.get_context_image(context_id, image_id)
        if record is None:
            raise ApiProblem(404, "photo_not_found", "Photo does not exist")
        try:
            content = self.photo_storage.read(record.storage_key)
        except FileNotFoundError:
            raise ApiProblem(404, "photo_not_found", "Photo does not exist") from None
        return content, record.content_type

    def set_person_avatar(
        self, person_id: uuid.UUID, raw: bytes, actor: Actor
    ) -> UploadedImageResponse:
        _require_permission(
            "set_own_avatar",
            actor,
            {"is_self": actor.id == person_id},
        )
        record = self._store_uploaded_image(
            raw,
            context_id=None,
            owner_person_id=person_id,
            uploaded_by_id=actor.id,
        )
        return _uploaded_image_response(record, f"/people/{person_id}/avatar")

    def read_person_avatar(
        self, person_id: uuid.UUID, actor: Actor
    ) -> tuple[bytes, str]:
        _require_permission(
            "view_person_avatar",
            actor,
            {
                "shares_a_group_with_subject": (
                    self.repository.shares_active_context(actor.id, person_id)
                )
            },
        )
        record = self.repository.get_latest_avatar(person_id)
        if record is None:
            raise ApiProblem(404, "avatar_not_found", "Avatar does not exist")
        try:
            content = self.photo_storage.read(record.storage_key)
        except FileNotFoundError:
            raise ApiProblem(404, "avatar_not_found", "Avatar does not exist") from None
        return content, record.content_type

    def post_context_memory(
        self,
        context_id: uuid.UUID,
        request: MemoryCreateRequest,
        actor: Actor,
    ) -> MemoryResponse:
        _require_permission(
            "post_group_memory",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        _require_photo_url_context(context_id, request.image_url)
        record = self.repository.create_memory(
            context_id=context_id,
            author_id=actor.id,
            image_url=request.image_url,
            caption=request.caption,
            now=_now(),
        )
        return _wire_memory(record)

    def create_outing(
        self,
        context_id: uuid.UUID,
        request: OutingCreateRequest,
        actor: Actor,
    ) -> OutingResponse:
        _require_permission(
            "create_outing",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        record = self.repository.create_outing(
            context_id=context_id,
            created_by_id=actor.id,
            title=request.title,
            starts_on=request.starts_on,
            ends_on=request.ends_on,
            headcount=request.headcount,
            budget_per_person_vnd=request.budget_per_person_vnd,
            now=_now(),
        )
        return _wire_outing(record)

    def list_context_outings(
        self, context_id: uuid.UUID, actor: Actor
    ) -> OutingListResponse:
        _require_permission(
            "view_outings",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        return OutingListResponse(
            context_id=context_id,
            outings=[
                _wire_outing(record)
                for record in self.repository.list_outings(context_id)
            ],
        )

    def group_recap(self, context_id: uuid.UUID, actor: Actor) -> GroupRecapResponse:
        """Trips that are over, and -- separately -- the one the group is on.

        Reuses `view_group_memories` rather than minting a permission. This is
        the memory wall's own read -- a different name for the same act would
        make it possible to be a member who can see the photos but not the
        trip they were taken on, which is a distinction nobody asked for.

        The two lists are kept apart rather than merged with a flag, because
        they answer different questions and one of them was already being
        asked. `outings` is the memory wall and has a client reading it today;
        putting a trip nobody has come home from yet into that list would show
        an unfinished trip as a memory and silently change what the field
        means. `in_progress` is budget awareness (F34), which is only worth
        anything while the money is still moving.
        """
        _require_permission(
            "view_group_memories",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        # The server's own wall-clock day in Vietnam, not the caller's. A trip
        # that ended yesterday is a memory for everyone, including a phone whose
        # clock is set wrong.
        today = _now().astimezone(ZoneInfo(WALL_CLOCK_ZONE)).date()
        records = self.repository.group_recap(context_id, today=today)
        outings = [
            _wire_recap_outing(record) for record in records if not record.in_progress
        ]
        return GroupRecapResponse(
            context_id=context_id,
            outings=outings,
            in_progress=[
                _wire_recap_outing(record) for record in records if record.in_progress
            ],
            # Summed here rather than by a sixth query: the per-trip figures on
            # the screen have to add back up to the total above them. Finished
            # trips only, and that is the point -- a memory wall whose total
            # crept upward every time somebody bought lunch on the trip they
            # are still on would stop matching the rows printed beneath it.
            split_total_vnd=sum(outing.split_total_vnd for outing in outings),
        )

    def group_suggestion(
        self,
        context_id: uuid.UUID,
        actor: Actor,
        suggester: Suggester,
    ) -> GroupSuggestionResponse:
        """F32 -- the companion proposes an evening nobody asked it for.

        Built from this group's own past: the trips that are over and what they
        cost (the same recomputed figures the memory wall reads, never a stored
        total), plus the catalogue categories of the places they actually
        checked in at. Both reads are scoped to `context_id` by the repository,
        so there is no path here to a second group's history -- which matters
        more than usual, because this response is the one screen in the product
        that summarises a group in five numbers.

        Every figure the screen shows as *evidence* is computed here.
        `basis` never passes through the model, and the model is not asked to
        restate it: a number written by a model, printed under a number derived
        from the ledger, is the fabrication this whole surface exists to stop.

        The model's only remaining job is to pick place identifiers and say why.
        `ground_suggestion` refuses the entire card if it invented one, and
        every failure lands on the same honest answer: 200, `suggested: false`,
        with the reason it did not speak. There is no hand-written fallback
        card, because a plausible suggestion served while the feature is broken
        is a broken feature that nobody can see is broken.
        """

        _require_permission(
            "view_group_suggestion",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )

        # The server's own wall-clock day in Vietnam, exactly as the memory
        # wall reads it: a trip that ended yesterday is history for everybody,
        # including a phone whose clock is set wrong.
        today = _now().astimezone(ZoneInfo(WALL_CLOCK_ZONE)).date()
        trips = [
            {
                "title": record.outing.title,
                "split_total_vnd": record.split_total_vnd,
                "headcount": record.outing.headcount,
            }
            for record in self.repository.group_recap(context_id, today=today)
        ]

        places = companion_places.load_place_catalogue()
        category_of = {
            place["id"]: place.get("category")
            for place in places
            if isinstance(place.get("id"), str)
        }
        # Check-ins carry a catalogue `place_id`; photographs do not, and a
        # caption is not evidence of a category. Rows whose place is no longer
        # in the catalogue are dropped rather than counted under a stale id.
        visits = [
            {"category": category_of[memory.place_id]}
            for memory in self.repository.list_memories(
                context_id, limit=SUGGESTION_HISTORY_LIMIT, kind="checkin"
            ).memories
            if memory.place_id in category_of
            and category_of[memory.place_id] is not None
        ]

        history = summarise_history(trips, visits)
        basis = SuggestionBasis(**history)

        def _silent(reason: str) -> GroupSuggestionResponse:
            return GroupSuggestionResponse(
                context_id=context_id,
                suggested=False,
                reason=reason,
                title=None,
                when_text=None,
                stops=[],
                basis=basis,
                source="none",
            )

        # Nothing to reason from is not a failure, and inventing a first outing
        # for a group that has never been anywhere would be the product
        # asserting a past that did not happen.
        if history["outing_count"] == 0:
            return _silent("no_history")

        try:
            raw = suggester(history, places)
        except Exception as error:  # noqa: BLE001 - a home screen must not 500
            logger.warning(
                "group suggestion: backend failed (%s)", type(error).__name__
            )
            return _silent("unavailable")
        if raw is None:
            return _silent("unavailable")

        try:
            grounded = ground_suggestion(raw, places)
        except SuggestionError as error:
            # The code, never the card. What provoked the refusal is model
            # output shaped by a private group's own text.
            logger.warning("group suggestion: card refused (%s)", error.code)
            return _silent("ungrounded")

        payload = grounded["payload"]
        return GroupSuggestionResponse(
            context_id=context_id,
            suggested=True,
            reason="ok",
            title=payload["title"],
            when_text=payload["when_text"],
            stops=[SuggestionStop(**stop) for stop in payload["stops"]],
            basis=basis,
            source="ai",
        )

    def replace_outing_timeline(
        self,
        outing_id: uuid.UUID,
        request: OutingTimelineRequest,
        actor: Actor,
    ) -> OutingResponse:
        record = self.repository.get_outing(outing_id)
        if record is None:
            raise ApiProblem(404, "outing_not_found", "Outing does not exist")
        _require_permission(
            "edit_outing_timeline",
            actor,
            {"is_group_member": self.repository.is_member(record.context_id, actor.id)},
        )
        stops = [
            {
                "minute_of_day": _minute_of_day(stop.at),
                "label": stop.label,
                "place_name": stop.place_name,
            }
            for stop in request.stops
        ]
        return _wire_outing(
            self.repository.replace_outing_stops(
                outing_id=outing_id,
                stops=stops,
            )
        )

    def check_in_to_stop(self, stop_id: uuid.UUID, actor: Actor) -> StopCheckinResponse:
        found = self.repository.get_outing_stop(stop_id)
        if found is None:
            raise ApiProblem(404, "stop_not_found", "Stop does not exist")
        _stop, outing = found
        _require_permission(
            "check_in_to_stop",
            actor,
            {"is_group_member": self.repository.is_member(outing.context_id, actor.id)},
        )
        try:
            record = self.repository.create_stop_checkin(
                stop_id=stop_id,
                person_id=actor.id,
                now=_now(),
            )
        except RepositoryConflict as exc:
            if exc.code == "ALREADY_CHECKED_IN":
                raise ApiProblem(
                    409,
                    "already_checked_in",
                    "You have already checked in at this stop",
                ) from exc
            raise
        return self._wire_stop_checkin(record)

    def list_outing_checkins(
        self, outing_id: uuid.UUID, actor: Actor
    ) -> OutingCheckinListResponse:
        outing = self.repository.get_outing(outing_id)
        if outing is None:
            raise ApiProblem(404, "outing_not_found", "Outing does not exist")
        _require_permission(
            "view_stop_checkins",
            actor,
            {"is_group_member": self.repository.is_member(outing.context_id, actor.id)},
        )
        return OutingCheckinListResponse(
            outing_id=outing_id,
            checkins=[
                self._wire_stop_checkin(record)
                for record in self.repository.list_outing_checkins(outing_id)
            ],
        )

    def _wire_stop_checkin(self, record: StopCheckinRecord) -> StopCheckinResponse:
        person = self.repository.get_person(record.person_id)
        return StopCheckinResponse(
            id=record.id,
            stop_id=record.stop_id,
            person_id=record.person_id,
            display_name=None if person is None else person.display_name,
            created_at=record.created_at,
        )

    def create_outing_invite(
        self,
        outing_id: uuid.UUID,
        request: OutingInviteCreateRequest,
        actor: Actor,
    ) -> OutingInviteResponse:
        outing = self.repository.get_outing(outing_id)
        if outing is None:
            raise ApiProblem(404, "outing_not_found", "Outing does not exist")
        _require_permission(
            "invite_to_outing",
            actor,
            {"is_group_member": self.repository.is_member(outing.context_id, actor.id)},
        )

        raw_token: str | None = None
        digest: bytes | None = None
        invited_person_id = request.person_id
        if request.source == "link":
            raw_token = secrets.token_urlsafe(32)
            digest = token_digest(raw_token)
            invited_person_id = None
        else:
            # This friendly pre-check races with a concurrent insert; the
            # partial unique index is the real duplicate guarantee behind it.
            existing = self.repository.find_outing_invite_for_person(
                outing_id, request.person_id
            )
            if existing is not None:
                raise ApiProblem(
                    409,
                    "invite_already_exists",
                    "Person is already invited to this outing",
                )

        now = _now()
        record = self.repository.create_outing_invite(
            outing_id=outing_id,
            source=request.source,
            invited_person_id=invited_person_id,
            invited_by_id=actor.id,
            token_digest=digest,
            expires_at=now + OUTING_INVITE_TTL,
            now=now,
        )
        # The raw token is returned exactly once and never persisted; only its
        # digest crosses the repository boundary.
        return _wire_outing_invite(record, raw_token)

    def accept_outing_invite(
        self, token: str, actor: Actor
    ) -> OutingInviteAcceptResponse:
        """Redeem a bearer link into a request capped at INVITED.

        A forwardable link identifies its holder as the person requesting
        entry, not as an approver. A different person who is already ACTIVE in
        the group must approve the request before group data becomes visible.
        """
        invite = self.repository.get_outing_invite_by_digest(token_digest(token))
        if invite is None:
            raise ApiProblem(404, "invite_not_found", "Invite link is not valid")
        if invite.accepted_at is not None:
            raise ApiProblem(
                409,
                "invite_already_accepted",
                "Invite link was already used",
            )
        now = _now()
        if invite.revoked_at is not None or invite.expires_at <= now:
            raise ApiProblem(404, "invite_not_found", "Invite link is not valid")

        outing = self.repository.get_outing(invite.outing_id)
        if outing is None:
            # Preserve the capability boundary even if referential integrity
            # is broken: the token must not reveal whether an outing existed.
            raise ApiProblem(404, "invite_not_found", "Invite link is not valid")
        try:
            self.repository.accept_outing_invite(
                invite_id=invite.id,
                accepted_by_id=actor.id,
                now=now,
            )
        except RepositoryConflict as exc:
            if exc.code == "OUTING_INVITE_ALREADY_ACCEPTED":
                raise ApiProblem(
                    409,
                    "invite_already_accepted",
                    "Invite link was already used",
                ) from exc
            if exc.code in {
                "OUTING_INVITE_NOT_FOUND",
                "OUTING_INVITE_NOT_REDEEMABLE",
            }:
                raise ApiProblem(
                    404,
                    "invite_not_found",
                    "Invite link is not valid",
                ) from exc
            raise

        membership = self.repository.ensure_invited_membership(
            context_id=outing.context_id,
            person_id=actor.id,
            invited_by_id=invite.invited_by_id,
            now=now,
        )
        return OutingInviteAcceptResponse(
            invite_id=invite.id,
            outing_id=invite.outing_id,
            context_id=outing.context_id,
            membership_id=membership.id,
            membership_state=membership.state,
        )

    def revoke_outing_invite(
        self,
        outing_id: uuid.UUID,
        invite_id: uuid.UUID,
        actor: Actor,
    ) -> OutingInviteResponse:
        outing = self.repository.get_outing(outing_id)
        invite = self.repository.get_outing_invite(invite_id)
        if outing is None or invite is None or invite.outing_id != outing_id:
            raise ApiProblem(404, "invite_not_found", "Invite link is not valid")

        _require_permission(
            "revoke_outing_invite",
            actor,
            {"is_group_member": self.repository.is_member(outing.context_id, actor.id)},
        )
        if invite.accepted_at is not None:
            raise ApiProblem(
                409,
                "invite_already_accepted",
                "Invite link was already used",
            )
        try:
            revoked = self.repository.revoke_outing_invite(
                invite_id=invite.id,
                now=_now(),
            )
        except RepositoryConflict as exc:
            if exc.code == "OUTING_INVITE_ALREADY_ACCEPTED":
                raise ApiProblem(
                    409,
                    "invite_already_accepted",
                    "Invite link was already used",
                ) from exc
            if exc.code == "OUTING_INVITE_NOT_FOUND":
                raise ApiProblem(
                    404,
                    "invite_not_found",
                    "Invite link is not valid",
                ) from exc
            raise
        return _wire_outing_invite(revoked, None)

    def post_context_checkin(
        self,
        context_id: uuid.UUID,
        request: CheckinCreateRequest,
        actor: Actor,
    ) -> MemoryResponse:
        """F46. Mark that the group was at a place, as a row on its own wall.

        Gated on `post_group_memory`, not on a permission of its own. A
        check-in *is* a memory -- same table, same feed, same reader -- and a
        second key would be a second place for the two to drift apart, which
        on a privacy boundary means one of them eventually being the loose one.

        The place is resolved before the write and the refusal names the
        parameter rather than echoing it. `place_id` arrives from a client and
        an error message is the one part of a response that gets pasted into
        chats and bug reports.
        """

        _require_permission(
            "post_group_memory",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        place = find_place(request.place_id)
        if place is None:
            raise ApiProblem(
                422, "place_not_found", "No place in the catalogue has that id"
            )
        record = self.repository.create_checkin(
            context_id=context_id,
            author_id=actor.id,
            place_id=place["id"],
            place_name=place["name"],
            lat=place["lat"],
            lng=place["lng"],
            caption=request.caption,
            now=_now(),
        )
        return _wire_memory(record)

    def list_context_memories(
        self,
        context_id: uuid.UUID,
        query: MemoryQuery,
        actor: Actor,
    ) -> MemoryListResponse:
        _require_permission(
            "view_group_memories",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        try:
            before = decode_cursor(query.before) if query.before is not None else None
        except CursorError as exc:
            raise ApiProblem(422, "invalid_cursor", "Memory cursor is invalid") from exc

        page = self.repository.list_memories(
            context_id,
            limit=query.limit,
            before=before,
            kind=query.kind,
            place_id=query.place_id,
        )
        memories = [_wire_memory(record) for record in page.memories]
        return MemoryListResponse(
            context_id=context_id,
            memories=memories,
            next_cursor=memories[-1].cursor if memories else None,
            has_more=page.has_more,
        )

    def post_context_message(
        self,
        context_id: uuid.UUID,
        request: MessageCreateRequest,
        actor: Actor,
    ) -> MessageResponse:
        _require_permission(
            "post_group_message",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )

        payload_is_valid = (
            (
                request.kind == "text"
                and request.body is not None
                and request.image_url is None
                and request.card is None
            )
            or (
                request.kind == "image"
                and request.image_url is not None
                and request.card is None
            )
            or (
                request.kind == "ai_card"
                and request.card is not None
                and request.image_url is None
                and request.body is None
            )
        )
        if not payload_is_valid:
            raise ApiProblem(
                422,
                "message_payload_invalid",
                "Message payload does not match its kind",
            )

        _require_photo_url_context(context_id, request.image_url)
        record = self.repository.create_message(
            context_id=context_id,
            author_id=actor.id,
            kind=request.kind,
            body=request.body,
            image_url=request.image_url,
            card=request.card,
            now=_now(),
        )
        return _wire_message(record)

    def list_context_messages(
        self,
        context_id: uuid.UUID,
        query: MessageQuery,
        actor: Actor,
    ) -> MessageListResponse:
        _require_permission(
            "view_group_messages",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        if query.before is not None and query.after is not None:
            raise ApiProblem(
                422,
                "cursor_direction_ambiguous",
                "Use either before or after, not both",
            )

        try:
            before = decode_cursor(query.before) if query.before is not None else None
            after = decode_cursor(query.after) if query.after is not None else None
        except CursorError as exc:
            raise ApiProblem(
                422, "invalid_cursor", "Message cursor is invalid"
            ) from exc

        page = self.repository.list_messages(
            context_id,
            limit=query.limit,
            before=before,
            after=after,
        )
        messages = [_wire_message(record) for record in page.messages]
        return MessageListResponse(
            context_id=context_id,
            messages=messages,
            next_cursor=messages[-1].cursor if messages else None,
            has_more=page.has_more,
        )

    def take_companion_turn(
        self,
        context_id: uuid.UUID,
        actor: Actor,
        companion: Companion,
    ) -> CompanionTurnResponse:
        """Let the companion suggest one grounded card, or stay silent.

        The speaking decision receives metadata only, and this workflow has one
        write capability: creating an AI message after grounding succeeds. It
        cannot create expenses or obligations on behalf of a model.
        """

        _require_permission(
            "invoke_group_companion",
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )

        page = self.repository.list_messages(context_id, limit=CONTEXT_WINDOW)
        messages = list(reversed(page.messages))
        metadata = [
            {
                "id": str(message.id),
                "author_kind": "ai" if message.kind == "ai_card" else "human",
                "created_at": message.created_at.isoformat(),
            }
            for message in messages
        ]
        decision = plan_turn({"messages": metadata, "now": _now().isoformat()})
        if not decision["may_speak"]:
            return CompanionTurnResponse(
                context_id=context_id,
                spoke=False,
                reason=decision["reason"],
                message=None,
            )

        model_conversation = [
            {
                "id": str(message.id),
                "author_id": (
                    str(message.author_id) if message.author_id is not None else None
                ),
                "author_kind": "ai" if message.kind == "ai_card" else "human",
                "kind": message.kind,
                "body": message.body,
                "image_url": message.image_url,
                "card": message.card,
                "created_at": message.created_at.isoformat(),
            }
            for message in messages
        ]
        members = []
        for membership in self.repository.list_members(context_id):
            person = self.repository.get_person(membership.person_id)
            if person is not None:
                members.append(
                    {"id": str(person.id), "display_name": person.display_name}
                )
        places = companion_places.load_place_catalogue()

        try:
            raw = companion.reply(
                conversation=model_conversation,
                members=members,
                places=places,
                budget_per_person_vnd=_group_budget_per_person_vnd(),
            )
        except (CompanionError, RuntimeError) as error:
            # The exception type, never the exception text: a backend error
            # carries both the prompt (the group's own words) and the API key
            # often enough that the message itself is the classic leak.
            logger.warning("companion turn: backend failed (%s)", type(error).__name__)
            return CompanionTurnResponse(
                context_id=context_id,
                spoke=False,
                reason="unavailable",
                message=None,
            )

        try:
            grounded = ground_card(raw, places)
        except CompanionError as error:
            # The refusal code is ours and is a closed set. What provoked the
            # refusal is model output shaped by a private group's own text.
            logger.warning("companion turn: card refused (%s)", error.code)
            return CompanionTurnResponse(
                context_id=context_id,
                spoke=False,
                reason="ungrounded",
                message=None,
            )

        record = self.repository.create_message(
            context_id=context_id,
            author_id=None,
            kind="ai_card",
            body=None,
            image_url=None,
            card=grounded,
            now=_now(),
        )
        return CompanionTurnResponse(
            context_id=context_id,
            spoke=True,
            reason="ok",
            message=_wire_message(record),
        )

    def set_context_member_role(
        self,
        context_id: uuid.UUID,
        person_id: uuid.UUID,
        request: MemberRoleRequest,
        actor: Actor,
    ) -> MembershipResponse:
        _require_permission(
            "set_member_role",
            actor,
            {
                "is_group_admin": self.repository.membership_role(context_id, actor.id)
                == "admin"
            },
        )
        membership = self.repository.set_membership_role(
            context_id, person_id, request.role
        )
        if membership is None:
            raise ApiProblem(
                404,
                "membership_not_found",
                "Active membership does not exist",
            )
        return _wire_membership(membership)

    def _bill_for_actor(self, bill_id: uuid.UUID, actor: Actor) -> BillRecord:
        record = self.repository.get_bill(bill_id)
        if record is None:
            raise ApiProblem(404, "bill_not_found", "Bill does not exist")
        _require_permission(
            "confirm_expense_proposal",
            actor,
            {"is_group_member": record.context_id in actor.context_ids},
        )
        return record

    def create_bill(self, request: BillCreateRequest, actor: Actor) -> BillResponse:
        _require_permission(
            "confirm_expense_proposal",
            actor,
            {"is_group_member": request.context_id in actor.context_ids},
        )
        try:
            record = self.repository.create_bill(
                context_id=request.context_id,
                created_by_id=actor.id,
                printed_total_vnd=request.printed_total_vnd,
                items_total_vnd=request.items_total_vnd,
                confidence=request.confidence,
                needs_review=request.needs_review,
                items=[
                    {
                        "item_key": item.item_key,
                        "name": item.name,
                        "quantity": item.quantity,
                        "unit_price_vnd": item.unit_price_vnd,
                        "line_total_vnd": item.line_total_vnd,
                        "position": position,
                        "suggested_participant_ids": list(
                            item.suggested_participant_ids
                        ),
                    }
                    for position, item in enumerate(request.items)
                ],
                surcharges=[
                    {
                        "surcharge_key": surcharge.surcharge_key,
                        "kind": surcharge.kind,
                        "amount_vnd": surcharge.amount_vnd,
                        "mode": surcharge.mode,
                    }
                    for surcharge in request.surcharges
                ],
                discounts=[
                    {
                        "discount_key": discount.discount_key,
                        "amount_vnd": discount.amount_vnd,
                        "scope": discount.scope,
                        "target_item_key": discount.item_key,
                    }
                    for discount in request.discounts
                ],
                now=_now(),
            )
        except RepositoryConflict as exc:
            raise ApiProblem(409, exc.code, "Bill creation conflicted") from exc
        return _wire_bill(record)

    def get_bill(self, bill_id: uuid.UUID, actor: Actor) -> BillResponse:
        return _wire_bill(self._bill_for_actor(bill_id, actor))

    def confirm_bill_assignments(
        self,
        bill_id: uuid.UUID,
        request: BillAssignmentsRequest,
        actor: Actor,
    ) -> BillResponse:
        self._bill_for_actor(bill_id, actor)
        try:
            record = self.repository.confirm_bill_assignments(
                bill_id=bill_id,
                assignments=[
                    {
                        "item_key": assignment.item_key,
                        "participant_ids": list(assignment.participant_ids),
                    }
                    for assignment in request.assignments
                ],
                decided_by_id=actor.id,
                now=_now(),
            )
        except RepositoryConflict as exc:
            if exc.code == "BILL_NOT_FOUND":
                raise ApiProblem(404, "bill_not_found", "Bill does not exist") from exc
            raise ApiProblem(409, exc.code, "Bill assignment conflicted") from exc
        return _wire_bill(record)

    def split_bill(
        self,
        bill_id: uuid.UUID,
        request: BillSplitRequest,
        actor: Actor,
    ) -> BillSplitResponse:
        record = self._bill_for_actor(bill_id, actor)

        list_members = getattr(self.repository, "list_members", None)
        memberships = list_members(record.context_id) if list_members else []
        participant_ids = {
            membership.person_id
            for membership in memberships
            if membership.state == "active"
        }
        if not participant_ids:
            participant_ids = {
                share.participant_id for item in record.items for share in item.shares
            }

        try:
            projection = allocator_input_from_bill(
                {
                    "participants": [
                        str(participant_id)
                        for participant_id in sorted(
                            participant_ids, key=lambda value: value.bytes
                        )
                    ],
                    "printed_total_vnd": record.printed_total_vnd,
                    "items": [
                        {
                            "item_key": item.item_key,
                            "amount_vnd": item.line_total_vnd,
                            "shares": [
                                {
                                    "participant_id": str(share.participant_id),
                                    "source": share.source,
                                }
                                for share in item.shares
                            ],
                        }
                        for item in record.items
                    ],
                    "surcharges": [
                        {
                            "surcharge_id": surcharge.surcharge_key,
                            "kind": surcharge.kind,
                            "amount_vnd": surcharge.amount_vnd,
                            "mode": surcharge.mode,
                        }
                        for surcharge in record.surcharges
                    ],
                    "discounts": [
                        {
                            "discount_id": discount.discount_key,
                            "amount_vnd": discount.amount_vnd,
                            "scope": discount.scope,
                            "item_id": discount.target_item_key,
                        }
                        for discount in record.discounts
                    ],
                    "advancer_id": (
                        str(request.paid_by_id)
                        if request.paid_by_id is not None
                        else None
                    ),
                }
            )
        except BillError as exc:
            raise ApiProblem(422, exc.code, "Bill cannot be projected") from exc

        if request.for_ledger and projection["assignment_state"] != "confirmed":
            raise ApiProblem(
                422,
                "bill_assignments_not_confirmed",
                "Bill assignments must be confirmed before ledger use",
            )

        try:
            allocation_result = allocate(projection["expense"])
        except AllocationError as exc:
            raise ApiProblem(422, exc.code, "Bill cannot be allocated") from exc
        return BillSplitResponse(
            allocation=_wire_allocation(allocation_result),
            assignment_state=projection["assignment_state"],
            suggested_item_keys=projection["suggested_item_keys"],
            total_amount_vnd=projection["expense"]["total_vnd"],
        )

    def propose_expense(self, proposal: ExpenseInput) -> ExpenseProposalResponse:
        try:
            allocation_result = allocate(_allocator_input(proposal))
        except AllocationError as exc:
            raise ApiProblem(422, exc.code, "Expense cannot be allocated") from exc
        identity = self.repository.create_expense(proposal.context_id)
        return ExpenseProposalResponse(
            expense_id=identity.id,
            proposal=proposal,
            allocation=_wire_allocation(allocation_result),
        )

    def confirm_expense(
        self,
        expense_id: uuid.UUID,
        request: ExpenseConfirmationRequest,
        actor: Actor,
    ) -> ExpenseConfirmationResponse:
        identity = self.repository.get_expense(expense_id)
        if identity is None:
            raise ApiProblem(404, "expense_not_found", "Expense does not exist")
        if identity.context_id != request.proposal.context_id:
            raise ApiProblem(
                409,
                "expense_context_mismatch",
                "Proposal context does not match the expense identity",
            )

        _require_permission(
            "confirm_expense_proposal",
            actor,
            {"is_group_member": identity.context_id in actor.context_ids},
        )
        acknowledgement = "pending"
        if request.acknowledge_as_advancer:
            _require_permission(
                "acknowledge_advancer_role",
                actor,
                {"is_named_advancer": actor.id == request.proposal.paid_by_id},
            )
            acknowledgement = "acknowledged"

        domain_expense = _allocator_input(request.proposal)
        try:
            allocation_result = allocate(domain_expense)
        except AllocationError as exc:
            raise ApiProblem(422, exc.code, "Expense cannot be allocated") from exc
        wire = _wire_allocation(allocation_result)
        if wire.allocations != request.expected_allocations:
            raise ApiProblem(
                409,
                "proposal_changed",
                "Confirmed allocations differ from the reviewed proposal",
            )

        try:
            record = self.repository.save_expense_confirmation(
                expense_id=expense_id,
                proposal=request.proposal,
                allocator_expense=allocation_result,
                rollups=component_rollups(domain_expense),
                allocations=request.expected_allocations,
                confirmed_by_id=actor.id,
                payer_acknowledgement=acknowledgement,
                now=_now(),
            )
        except RepositoryConflict as exc:
            raise ApiProblem(
                409, exc.code.lower(), "Expense confirmation conflicted"
            ) from exc
        return ExpenseConfirmationResponse(
            expense_id=expense_id,
            expense_version_id=record.expense_version_id,
            version_number=record.version_number,
            total_amount_vnd=request.proposal.total_amount_vnd,
            payer_acknowledgement=acknowledgement,
            allocations=request.expected_allocations,
        )

    def create_batch(
        self, request: BatchCreateRequest, actor: Actor
    ) -> BatchCreateResponse:
        _require_permission(
            "create_batch",
            actor,
            {"is_group_member": request.context_id in actor.context_ids},
        )
        # The creator becomes the owner before the freeze action is evaluated;
        # the role is resource-derived, not accepted from the request body.
        _require_permission(
            "freeze_batch",
            actor,
            {"owns_batch": True},
            extra_roles={"batch_owner"},
        )
        now = _now()
        if request.due_at <= now:
            raise ApiProblem(422, "due_at_not_future", "due_at must be in the future")

        if request.expense_version_ids is None:
            confirmed = self.repository.load_batch_inputs(request.context_id, None)
            selected = tuple(expense.version_id for expense in confirmed.expenses)
        else:
            selected = tuple(request.expense_version_ids)
        inputs = self.repository.load_batch_inputs(request.context_id, selected)
        if request.expense_version_ids is not None and inputs.unavailable_version_ids:
            raise ApiProblem(
                409,
                "expense_versions_unavailable",
                "A selected version is missing, superseded, or already batched",
            )
        if not inputs.expenses:
            raise ApiProblem(
                409, "no_unbatched_allocations", "No allocations are available"
            )

        raw_obligations: list[dict] = []
        sources_by_pair: dict[tuple[uuid.UUID, uuid.UUID], list] = defaultdict(list)
        try:
            for expense in inputs.expenses:
                allocations = {
                    str(row.participant_id): row.amount_vnd
                    for row in expense.allocations
                }
                raw_obligations.extend(
                    obligations_from_allocations(
                        allocations,
                        str(expense.paid_by_id),
                        str(expense.version_id),
                    )
                )
                for row in expense.allocations:
                    if row.participant_id != expense.paid_by_id and row.amount_vnd > 0:
                        sources_by_pair[
                            (row.participant_id, expense.paid_by_id)
                        ].append(row)
            merged = merge_obligations(raw_obligations)
        except LedgerError as exc:
            raise ApiProblem(
                409, exc.code, "Allocations cannot form obligations"
            ) from exc
        if not merged:
            raise ApiProblem(
                409, "no_obligations", "The selected allocations owe no money"
            )

        recipient_ids = frozenset(uuid.UUID(item["recipient_id"]) for item in merged)
        bank_recipients = self.repository.load_bank_recipients(recipient_ids)
        missing_recipients = recipient_ids - set(bank_recipients)
        freeze_context = {
            "obligations": merged,
            "has_unready_recipient": bool(missing_recipients),
            "unready_recipient_choice": request.unready_recipient_choice,
        }
        try:
            frozen_state = transition("accruing", "freeze", freeze_context)
        except CollectionError as exc:
            raise ApiProblem(409, exc.code, "Batch cannot be frozen") from exc
        if missing_recipients:
            # The current schema requires a snapshot on every obligation and has
            # no blocked-recipient batch type. Do not silently omit a debt.
            raise ApiProblem(
                409,
                "recipient_setup_incomplete",
                "A recipient must finish bank setup before this batch can be created",
            )
        if frozen_state != "frozen":
            raise ApiProblem(
                500, "unexpected_batch_state", "Domain returned an invalid state"
            )

        drafts = tuple(
            ObligationDraft(
                sender_id=uuid.UUID(item["sender_id"]),
                recipient_id=uuid.UUID(item["recipient_id"]),
                amount_vnd=item["amount_vnd"],
                source_expense_version_ids=tuple(
                    uuid.UUID(value) for value in item["source_expense_version_ids"]
                ),
                sources=tuple(
                    sources_by_pair[
                        (uuid.UUID(item["sender_id"]), uuid.UUID(item["recipient_id"]))
                    ]
                ),
            )
            for item in merged
        )
        stored = self.repository.save_frozen_batch(
            context_id=request.context_id,
            owner_id=actor.id,
            due_at=request.due_at,
            obligations=drafts,
            bank_recipients=bank_recipients,
            now=now,
        )
        return BatchCreateResponse(
            batch_id=stored.id,
            batch_version_id=stored.version_id,
            status="frozen",
            obligations=[
                ObligationResponse(
                    obligation_id=item.id,
                    sender_id=item.sender_id,
                    recipient_id=item.recipient_id,
                    amount_vnd=item.amount_vnd,
                    due_at=item.due_at,
                    source_expense_version_ids=list(item.source_expense_version_ids),
                )
                for item in stored.obligations
            ],
        )

    def publish_batch(
        self,
        batch_id: uuid.UUID,
        request: BatchPublishRequest,
        actor: Actor,
    ) -> BatchPublishResponse:
        batch = self.repository.load_batch_for_publish(batch_id)
        if batch is None:
            raise ApiProblem(404, "batch_not_found", "Batch does not exist")
        _require_permission(
            "publish_batch",
            actor,
            {
                "owns_batch": actor.id == batch.owner_id,
                "all_recipients_eligible": batch.all_recipients_eligible,
            },
        )
        now = _now()
        if request.guest_link_expires_at <= now:
            raise ApiProblem(
                422,
                "guest_link_expiry_not_future",
                "guest_link_expires_at must be in the future",
            )
        gate_context = {
            "advancer_acknowledged": batch.advancer_acknowledged,
            "bank_recipient_snapshot_valid": batch.bank_recipient_snapshot_valid,
            "delivery_method_chosen": bool(request.delivery_method),
        }
        unmet = unmet_publish_gates(gate_context)
        if unmet:
            raise ApiProblem(409, unmet[0], "A publish gate is not satisfied")
        try:
            published_state = transition(batch.status, "publish", gate_context)
        except CollectionError as exc:
            raise ApiProblem(409, exc.code, "Batch cannot be published") from exc

        obligations_by_sender: dict[uuid.UUID, list] = defaultdict(list)
        for obligation in batch.obligations:
            obligations_by_sender[obligation.sender_id].append(obligation)

        link_material: list[tuple[uuid.UUID, str, GuestLinkDraft]] = []
        published_links: list[PublishedGuestLink] = []
        try:
            for sender_id in sorted(
                obligations_by_sender, key=lambda value: value.bytes
            ):
                obligations = obligations_by_sender[sender_id]
                capability_scope(
                    {"batch_version_id": batch.version_id, "sender_id": sender_id},
                    [
                        {
                            "obligation_id": item.id,
                            "batch_version_id": item.batch_version_id,
                            "sender_id": item.sender_id,
                        }
                        for item in obligations
                    ],
                )
                raw_token = secrets.token_urlsafe(32)
                link_material.append(
                    (
                        sender_id,
                        raw_token,
                        GuestLinkDraft(
                            sender_id=sender_id,
                            token_digest=token_digest(raw_token),
                            expires_at=request.guest_link_expires_at,
                        ),
                    )
                )
                published_links.append(
                    PublishedGuestLink(
                        sender_id=sender_id,
                        path=f"/g/{raw_token}",
                        expires_at=request.guest_link_expires_at,
                        obligations=[
                            PublishedObligation(
                                obligation_id=item.id,
                                amount_vnd=item.amount_vnd,
                                vietqr_payload=build_payload(
                                    bank_bin=item.bank_bin,
                                    account_number=item.account_number,
                                    amount_vnd=item.amount_vnd,
                                    note=f"TT {item.id.hex[:8]}",
                                ),
                            )
                            for item in obligations
                        ],
                    )
                )
        except (CapabilityScopeError, VietQRError) as exc:
            raise ApiProblem(
                409, exc.code, "A guest capability cannot be built"
            ) from exc

        try:
            stored = self.repository.save_published_batch(
                batch=batch,
                status=published_state,
                links=tuple(item[2] for item in link_material),
                actor_id=actor.id,
                now=now,
            )
        except RepositoryConflict as exc:
            raise ApiProblem(
                409, exc.code.lower(), "Batch publication conflicted"
            ) from exc
        if {item.sender_id for item in stored} != set(obligations_by_sender):
            raise ApiProblem(
                500, "guest_link_write_mismatch", "Guest link write was incomplete"
            )
        return BatchPublishResponse(
            batch_id=batch.id,
            status="published",
            guest_links=published_links,
        )

    def guest_view(self, token: str) -> dict:
        record = self.repository.get_guest_envelope(token_digest(token), _now())
        if record is None:
            raise ApiProblem(404, "guest_link_not_found", "Guest link does not exist")
        _require_permission(
            "view_guest_envelope",
            _guest_actor(token),
            {"is_own_capability": True},
        )
        try:
            return build_guest_view(record.envelope)
        except GuestViewError as exc:
            raise ApiProblem(409, exc.code, "Guest envelope is not renderable") from exc

    def _objection_envelope(self, token: str) -> dict:
        record = self.repository.get_guest_envelope(token_digest(token), _now())
        if record is None:
            raise ApiProblem(404, "guest_link_not_found", "Guest link does not exist")
        _require_permission(
            "view_guest_envelope", _guest_actor(token), {"is_own_capability": True}
        )
        return record.envelope

    def not_me_view(self, token: str) -> dict:
        try:
            return build_not_me_view(self._objection_envelope(token))
        except ObjectionError as exc:
            raise ApiProblem(409, exc.code, "Objection page is not renderable") from exc

    def wrong_amount_view(self, token: str, obligation_id: str) -> dict:
        try:
            return build_wrong_amount_view(
                self._objection_envelope(token), obligation_id
            )
        except ObjectionError as exc:
            raise ApiProblem(409, exc.code, "Objection page is not renderable") from exc

    def list_batch_obligations(
        self, batch_id: uuid.UUID, actor: Actor
    ) -> BatchObligationsResponse:
        """The collection board: what arrived, what is argued about, what was
        claimed.

        Section 8.2 says an objection stops collection on that obligation.
        That is only true if somebody on the collecting side can see it, and
        until now there was nowhere for them to look. The same hole swallowed
        the sender's "I transferred it": the guest page told them to wait for
        a confirmation, and the person expected to give it saw a row identical
        to one nobody had touched. All three facts are reported side by side
        and none of them is merged into another.
        """
        board = self.repository.list_batch_obligations(batch_id)
        if board is None:
            raise ApiProblem(404, "unknown_batch", "No such batch")

        # This check was missing when the endpoint shipped, and QA found it by
        # calling it as a stranger. The parameter was accepted and never read,
        # so any valid actor header let anyone with a batch id read every
        # sender, every recipient, every amount, and the private reason a guest
        # gave for objecting. Section 10: visibility is fail-closed, and an
        # unused `actor` argument is the most convincing way to look otherwise.
        _require_permission(
            "view_collection_board",
            actor,
            {"is_group_member": board.context_id in actor.context_ids},
        )

        rows = board.obligations
        return BatchObligationsResponse(
            batch_id=batch_id,
            obligations=[
                BatchObligationView(
                    obligation_id=row.obligation_id,
                    sender_id=row.sender_id,
                    recipient_id=row.recipient_id,
                    amount_vnd=row.amount_vnd,
                    obligation_status=row.status,
                    disputed=row.disputed,
                    disputed_reason=row.disputed_reason,
                    payment_reported_at=row.payment_reported_at,
                )
                for row in rows
            ],
            disputed_count=sum(1 for row in rows if row.disputed),
            payment_reported_count=sum(
                1 for row in rows if row.payment_reported_at is not None
            ),
        )

    def record_objection(
        self, token: str, kind: str, obligation_id: uuid.UUID | None, reason: str | None
    ) -> None:
        """Spec section 8.6 treats both objections as first-class outcomes.

        They were links to routes that did not exist, so a guest who pressed
        either one got a 404: the page invited an objection and then behaved as
        though objecting had broken something.
        """
        if kind not in OBJECTION_KINDS:
            raise ApiProblem(422, "unknown_objection", "Unknown objection kind")
        if reason is not None and reason not in {
            value for value, _ in OBJECTION_REASONS
        }:
            # A closed list, because free text from a stranger is where the
            # group accidentally learns something, and where a bookkeeping
            # question arrives in a tone that starts an argument.
            raise ApiProblem(422, "unknown_reason", "Unknown objection reason")

        envelope = self._objection_envelope(token)

        # A revoked or expired link is not a channel. GET already refused on
        # both, but POST did not, so submitting the form directly still filed
        # an objection against a link the guest had themselves shut down by
        # pressing "I am not this person". A capability that is over is over
        # in both directions.
        if envelope["link_state"] != "active":
            raise ApiProblem(409, "link_not_active", "This link is no longer open")

        # The token is the capability, and it covers exactly the obligations in
        # this envelope. Without this check a guest holding a valid link could
        # post someone else's obligation_id and file an objection against a
        # debt that was never shown to them. The sibling route report_payment
        # already 404s on the same forgery; this one did not.
        if obligation_id is not None:
            in_scope = any(
                block["obligation_id"] == str(obligation_id)
                for block in envelope["obligations"]
            )
            if not in_scope:
                raise ApiProblem(
                    404, "unknown_obligation", "No such obligation on this link"
                )

        # Indexed, not .get() with a default. The defaults scattered through
        # this codebase said 2 while the repository enforced 3, so the page
        # promised a quota the server did not honour.
        #
        # And the check is gated on the KIND. It used to run for every kind,
        # so someone who had objected three times got 429 for asking how a
        # number was reached -- while the repository, and the comment next to
        # it, both said asking does not spend the quota. The page kept offering
        # the button; only the POST disagreed.
        if kind in QUOTA_CONSUMING_OBJECTIONS:
            # Per obligation. A link can carry debts to two different people,
            # and arguing three times with one of them must not use up the
            # right to say anything about the other.
            block = next(
                (
                    item
                    for item in envelope["obligations"]
                    if item["obligation_id"] == str(obligation_id)
                ),
                None,
            )
            used = block["objections_used"] if block else envelope["objections_used"]
            allowed = (
                block["objections_allowed"] if block else envelope["objections_allowed"]
            )
            if used >= allowed:
                raise ApiProblem(
                    429,
                    "objection_rate_limited",
                    "Too many objections on this obligation",
                )

        self.repository.save_guest_objection(
            token_digest=token_digest(token),
            kind=kind,
            obligation_id=obligation_id,
            reason=reason,
            now=_now(),
        )

    def report_payment(
        self, token: str, request: PaymentReportRequest
    ) -> PaymentReportResponse:
        now = _now()
        target = self.repository.get_payment_report_target(
            token_digest(token), request.obligation_id, now
        )
        if target is None:
            raise ApiProblem(
                404, "guest_obligation_not_found", "Obligation is outside this link"
            )
        _require_permission(
            "report_payment",
            _guest_actor(token),
            {
                "is_own_capability": True,
                "active_capability": target.active_capability,
                "report_budget_available": target.reports_used < 3,
            },
        )
        try:
            record = self.repository.save_payment_report(
                target=target,
                idempotency_key=request.idempotency_key or uuid.uuid4(),
                now=now,
            )
        except RepositoryConflict as exc:
            raise ApiProblem(
                409, exc.code.lower(), "Payment report conflicted"
            ) from exc
        status = obligation_status(
            target.amount_vnd,
            [{"amount_vnd": amount} for amount in record.receipt_amounts_vnd],
        )
        return PaymentReportResponse(
            payment_report_id=record.id,
            obligation_id=record.obligation_id,
            amount_vnd=record.amount_vnd,
            obligation_status=status,
        )

    def set_bank_recipient(
        self, request: BankRecipientRequest, actor: Actor
    ) -> tuple[BankRecipientResponse, bool]:
        """Register where this person's money should land.

        Returns the destination and whether it changed anything, because the
        route answers 201 for a new or replaced destination and 200 for a retry
        that re-sent the same digits.
        """

        # Section 9.2, and one of the few rules in the spec with no exception
        # for an admin: nobody adds or changes another person's bank account.
        # Getting this wrong redirects a whole collection round into whichever
        # account the attacker named. Checked before validation, so a malformed
        # body never tells an outsider anything about somebody else's setup.
        _require_permission(
            "set_bank_recipient",
            actor,
            {
                "is_own_account": actor.id == request.recipient_id,
                # A bearer token is a capability, not an identity. Section 9.2
                # rules out using one for this action by name.
                "is_authenticated_account": "guest" not in actor.roles,
            },
        )
        try:
            destination = normalise_destination(
                {
                    "bank_bin": request.bank_bin,
                    "account_number": request.account_number,
                    "account_name": request.account_name,
                }
            )
        except BankAccountError as exc:
            raise ApiProblem(422, exc.code, "Bank destination is malformed") from exc

        record, created = self.repository.save_bank_recipient(
            recipient_id=request.recipient_id,
            bank_bin=destination["bank_bin"],
            account_number=destination["account_number"],
            account_name=destination["account_name"],
            actor_id=actor.id,
            now=_now(),
        )
        return _bank_recipient_response(record), created

    def get_bank_recipient(
        self, recipient_id: uuid.UUID, actor: Actor
    ) -> BankRecipientResponse:
        _require_permission(
            "view_bank_recipient", actor, {"is_own_account": actor.id == recipient_id}
        )
        record = self.repository.get_active_bank_recipient(recipient_id)
        if record is None:
            raise ApiProblem(
                404,
                "bank_recipient_not_found",
                "No bank destination is registered for this person",
            )
        return _bank_recipient_response(record)

    def confirm_receipt(
        self,
        obligation_id: uuid.UUID,
        request: ReceiptConfirmationRequest,
        actor: Actor,
    ) -> ReceiptConfirmationResponse:
        target = self.repository.get_receipt_target(obligation_id)
        if target is None:
            raise ApiProblem(404, "obligation_not_found", "Obligation does not exist")
        _require_permission(
            "confirm_receipt",
            actor,
            {"is_recipient_of_this_obligation": actor.id == target.recipient_id},
        )
        try:
            record = self.repository.save_receipt_confirmation(
                target=target,
                confirmed_by_id=actor.id,
                amount_vnd=request.amount_vnd,
                payment_report_id=request.payment_report_id,
                idempotency_key=request.idempotency_key,
                now=_now(),
            )
        except RepositoryConflict as exc:
            raise ApiProblem(
                409, exc.code.lower(), "Receipt confirmation conflicted"
            ) from exc
        try:
            status = obligation_status(
                target.amount_vnd,
                [{"amount_vnd": amount} for amount in record.receipt_amounts_vnd],
            )
        except LedgerError as exc:
            raise ApiProblem(409, exc.code, "Receipt events are invalid") from exc
        return ReceiptConfirmationResponse(
            receipt_confirmation_id=record.id,
            obligation_id=record.obligation_id,
            amount_vnd=record.amount_vnd,
            obligation_status=status,
        )

    # --- friend graph (F03, F04) ---------------------------------------

    def send_friend_request(
        self, request: FriendRequestCreate, actor: Actor
    ) -> FriendRequestResponse:
        """Ask. This grants nothing until the other person answers.

        Order matters and is the house rule: permission, then domain, then
        repository. The domain call is not decoration here -- it is what
        refuses a self-edge and what refuses to stack a second request on a
        live one, using the same code for "already asked" and "blocked".
        """
        addressee_id = request.addressee_id
        _require_permission(
            "send_friend_request",
            actor,
            {"is_not_self": actor.id != addressee_id},
        )
        if self.repository.get_person(addressee_id) is None:
            raise ApiProblem(
                404, "person_not_found", "Chưa có ai mang danh tính này."
            )

        existing = self.repository.get_friend_edge(actor.id, addressee_id)
        try:
            open_friendship_request(
                requester_id=str(actor.id),
                addressee_id=str(addressee_id),
                existing=None if existing is None else {"state": existing.state},
            )
        except FriendshipError as refused:
            raise self._friend_refusal(refused) from refused

        try:
            record = self.repository.open_friend_request(
                requester_id=actor.id, addressee_id=addressee_id, now=_now()
            )
        except RepositoryConflict as exc:
            # The race arm of the same refusal. Deliberately the same status
            # and the same code as the read arm above: if these differed, a
            # blocked person could tell a block from a duplicate by timing.
            raise ApiProblem(
                409, BLOCKED_IS_SILENT.lower(), "Chưa gửi được lời mời này."
            ) from exc
        return _wire_friend_edge(record)

    def respond_to_friend_request(
        self, request_id: uuid.UUID, body: FriendRequestDecision, actor: Actor
    ) -> FriendRequestResponse:
        """Answer one. Accepting is the addressee's alone.

        The permission table proves `is_invitee` from the row, and the domain
        proves it again from the same row. Two layers that fail differently:
        one is a data table somebody could edit without reading the domain, the
        other is logic somebody could reach without going through a route.
        """
        edge = self.repository.get_friend_request(request_id, actor.id)
        if edge is None:
            raise ApiProblem(
                404, "friend_request_not_found", "Không có lời mời này."
            )

        answer = Decision(body.decision)
        # Blocking is the one answer either party may give, so the predicate
        # proven for it is "you are a party", not "you were the one asked".
        # Accept and decline keep the narrow `is_invitee`, which is what stops
        # a requester from answering their own request.
        is_invitee = (
            actor.id in (edge.requester_id, edge.addressee_id)
            if answer is Decision.BLOCK
            else actor.id == edge.addressee_id
        )
        _require_permission(
            "respond_to_friend_request", actor, {"is_invitee": is_invitee}
        )

        try:
            decided = decide_friendship(
                edge={
                    "requester_id": str(edge.requester_id),
                    "addressee_id": str(edge.addressee_id),
                    "state": edge.state,
                },
                actor_id=str(actor.id),
                decision=str(answer),
            )
        except FriendshipError as refused:
            raise self._friend_refusal(refused) from refused

        try:
            record = self.repository.decide_friend_request(
                request_id=request_id,
                state=decided["state"],
                decided_by_id=actor.id,
                now=_now(),
            )
        except RepositoryConflict as exc:
            # The write arm of the refusal the domain gives above. The read
            # that fed `decide_friendship` was taken before the row was
            # locked, so by the time the write holds the lock the edge may
            # have moved. Answering with the code the domain would have given
            # on the fresher read is what makes the two orderings of one race
            # indistinguishable from outside: losing a race and never having
            # been allowed must look the same, or timing becomes the channel a
            # silent block leaks through.
            if exc.code == "FRIEND_EDGE_EXISTS":
                # Not a state the row is in -- a state the *pair* is in. The
                # decision would have moved this row into a live state while a
                # different live row already holds the pair, which is the same
                # fact `send_friend_request` answers for, so it gets the same
                # wire code.
                raise ApiProblem(
                    409,
                    BLOCKED_IS_SILENT.lower(),
                    "Chưa trả lời được lời mời này.",
                ) from exc
            raise self._friend_refusal(FriendshipError(exc.code)) from exc
        if record is None:
            raise ApiProblem(
                404, "friend_request_not_found", "Không có lời mời này."
            )
        return _wire_friend_edge(record)

    def list_friend_requests(
        self, person_id: uuid.UUID, direction: str, actor: Actor
    ) -> FriendRequestListResponse:
        _require_permission(
            "view_own_friends", actor, {"is_self": actor.id == person_id}
        )
        return FriendRequestListResponse(
            requests=[
                _wire_friend_edge(record)
                for record in self.repository.list_friend_requests(
                    person_id, direction=direction
                )
            ]
        )

    def list_friends(
        self, person_id: uuid.UUID, actor: Actor
    ) -> FriendListResponse:
        _require_permission(
            "view_own_friends", actor, {"is_self": actor.id == person_id}
        )
        return FriendListResponse(
            friends=[
                FriendSummary(
                    person_id=record.other_person_id,
                    display_name=record.other_display_name,
                    # An accepted row always carries a decision time: the check
                    # constraint `decided_state_matches_timestamp` makes the
                    # alternative unrepresentable, so this cannot be None.
                    friends_since=record.decided_at or record.created_at,
                )
                for record in self.repository.list_friends(person_id)
            ]
        )

    def find_person_by_person_id(
        self, person_id: uuid.UUID, actor: Actor
    ) -> PersonMatchResponse:
        """Resolve an already-derived person id to a name.

        The telephone number never reaches this method. `routes/friends.py`
        turns the number into an id and drops it in the same expression; what
        arrives here is the opaque id, which is why no argument on this
        signature can be logged into a disclosure.
        """
        _require_permission("find_person_by_phone", actor, {})
        person = self.repository.get_person(person_id)
        if person is None:
            # Same sentence whatever the input was. A refusal that varied with
            # the number would be a directory with extra steps.
            raise ApiProblem(
                404, "person_not_found", "Chưa có ai dùng số này trong Rủ Đi."
            )
        return PersonMatchResponse(
            person_id=person.id, display_name=person.display_name
        )

    @staticmethod
    def _friend_refusal(refused: FriendshipError) -> ApiProblem:
        """Map a domain code to an answer that does not narrate the graph."""
        if refused.code == BLOCKED_IS_SILENT:
            return ApiProblem(
                409, refused.code.lower(), "Chưa gửi được lời mời này."
            )
        if refused.code == "SELF_EDGE":
            return ApiProblem(
                422, "self_edge", "Không tự kết bạn với chính mình được."
            )
        if refused.code in ("ONLY_ADDRESSEE_MAY_ANSWER", "NOT_A_PARTY"):
            return ApiProblem(403, "permission_denied", refused.code.lower())
        return ApiProblem(409, refused.code.lower(), "Lời mời không ở trạng thái đó.")


__all__ = ["ApiService", "token_digest"]
