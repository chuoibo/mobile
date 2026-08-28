"""Application workflows that connect HTTP validation, domain, and storage."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from app.api.deps import Actor
from app.api.errors import ApiProblem, RepositoryConflict
from app.api.limits import OBJECTION_KINDS, QUOTA_CONSUMING_OBJECTIONS
from app.api.repository import (
    ApiRepository,
    GuestLinkDraft,
    ObligationDraft,
)
from app.api.schemas import (
    AllocationProposal,
    BatchCreateRequest,
    BatchObligationsResponse,
    BatchObligationView,
    BatchCreateResponse,
    BatchPublishRequest,
    BatchPublishResponse,
    ExpenseConfirmationRequest,
    ExpenseConfirmationResponse,
    ExpenseInput,
    ExpenseProposalResponse,
    ObligationResponse,
    PaymentReportRequest,
    PaymentReportResponse,
    PublishedGuestLink,
    PublishedObligation,
    ReceiptConfirmationRequest,
    ReceiptConfirmationResponse,
)
from app.domain import permissions
from app.domain.allocator import allocate
from app.domain.capability import CapabilityScopeError, capability_scope
from app.domain.collection import CollectionError, transition, unmet_publish_gates
from app.domain.contract import AllocationError
from app.domain.expense import component_rollups
from app.domain.ledger import (
    LedgerError,
    merge_obligations,
    obligation_status,
    obligations_from_allocations,
)
from app.payments.vietqr import VietQRError, build_payload
from app.web.guest_view import GuestViewError, build_guest_view
from app.web.objection_view import (
    OBJECTION_REASONS,
    ObjectionError,
    build_not_me_view,
    build_wrong_amount_view,
)


def _now() -> datetime:
    return datetime.now(UTC)


def token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def _guest_actor(token: str) -> Actor:
    """A guest has no account, and the product deliberately keeps it that way:
    spec section 8.6 rules out OTP for guests in v1 because it would break the
    spread that makes the collection loop work at all.

    So the subject of a guest action is the capability itself. The token digest
    names the bearer without pretending to know which person is holding it,
    which is exactly the claim the guest page is careful never to make.
    """
    return Actor(id=f"capability:{token_digest(token).hex()[:16]}", roles=frozenset({"guest"}), context_ids=frozenset())


def _require_permission(
    action: str, actor: Actor, context: dict, *, extra_roles: frozenset[str] | set[str] = frozenset()
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


class ApiService:
    def __init__(self, repository: ApiRepository):
        self.repository = repository

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

        selected = (
            tuple(request.expense_version_ids)
            if request.expense_version_ids is not None
            else None
        )
        inputs = self.repository.load_batch_inputs(request.context_id, selected)
        if inputs.unavailable_version_ids:
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
            return build_wrong_amount_view(self._objection_envelope(token), obligation_id)
        except ObjectionError as exc:
            raise ApiProblem(409, exc.code, "Objection page is not renderable") from exc

    def list_batch_obligations(
        self, batch_id: uuid.UUID, actor: Actor
    ) -> BatchObligationsResponse:
        """The collection board, disputes and all.

        Section 8.2 says an objection stops collection on that obligation.
        That is only true if somebody on the collecting side can see it, and
        until now there was nowhere for them to look.
        """
        rows = self.repository.list_batch_obligations(batch_id)
        if rows is None:
            raise ApiProblem(404, "unknown_batch", "No such batch")
        return BatchObligationsResponse(
            batch_id=batch_id,
            obligations=[
                BatchObligationView(
                    obligation_id=row.obligation_id,
                    sender_id=row.sender_id,
                    recipient_id=row.recipient_id,
                    amount_vnd=row.amount_vnd,
                    obligation_status=row.status,
                    disputed_reason=row.disputed_reason,
                )
                for row in rows
            ],
            disputed_count=sum(1 for row in rows if row.status == "disputed"),
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
        if reason is not None and reason not in {value for value, _ in OBJECTION_REASONS}:
            # A closed list, because free text from a stranger is where the
            # group accidentally learns something, and where a bookkeeping
            # question arrives in a tone that starts an argument.
            raise ApiProblem(422, "unknown_reason", "Unknown objection reason")

        envelope = self._objection_envelope(token)

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
                raise ApiProblem(404, "unknown_obligation", "No such obligation on this link")

        # Indexed, not .get() with a default. The defaults scattered through
        # this codebase said 2 while the repository enforced 3, so the page
        # promised a quota the server did not honour.
        #
        # And the check is gated on the KIND. It used to run for every kind,
        # so someone who had objected three times got 429 for asking how a
        # number was reached -- while the repository, and the comment next to
        # it, both said asking does not spend the quota. The page kept offering
        # the button; only the POST disagreed.
        if (
            kind in QUOTA_CONSUMING_OBJECTIONS
            and envelope["objections_used"] >= envelope["objections_allowed"]
        ):
            raise ApiProblem(429, "objection_rate_limited", "Too many objections on this link")

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


__all__ = ["ApiService", "token_digest"]
