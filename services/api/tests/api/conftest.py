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
from datetime import UTC, datetime
from functools import lru_cache

import anyio
import httpx
import pytest

from app.api.deps import get_repository
from app.api.errors import RepositoryConflict
from app.api.limits import OBJECTION_LIMIT, REPORT_LIMIT
from app.api.main import create_app
from app.api.repository import (
    AccountIdentityRecord,
    AccountSessionRecord,
    ActorGrants,
    AllocationRow,
    BatchBoard,
    BatchForPublish,
    BatchInputs,
    BatchObligationRow,
    BillDiscountRecord,
    BillItemRecord,
    BillRecord,
    BillShareRecord,
    BillSurchargeRecord,
    ConfirmationRecord,
    ConfirmedExpense,
    ContextBatchRow,
    ContextRecord,
    DestinationRecord,
    ExpenseIdentity,
    FriendEdgeRecord,
    FrozenBatch,
    FrozenObligation,
    GuestEnvelopeRecord,
    GuestLinkDraft,
    LastMessageRecord,
    MembershipRecord,
    MemoryPage,
    MemoryRecord,
    MessageRecord,
    ObligationDraft,
    OtpChallengeRecord,
    OutingInviteRecord,
    PaymentReportRecord,
    PaymentReportTarget,
    PersonContextSummaryRecord,
    PersonFinanceSummary,
    PersonRecord,
    PlaceRecord,
    PostRecord,
    ProfileCounts,
    PublishObligation,
    ReadMarkRecord,
    ReceiptRecord,
    ReceiptTarget,
    SavedPlaceRecord,
    StoredGuestLink,
)
from app.domain.capability import capability_scope
from app.domain.ledger import obligation_status

from .helpers import ADVANCER_ID, CONTEXT_ID, SENDER_ID

FAKE_BATCH_INSTANT = datetime(2026, 1, 1, tzinfo=UTC)


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
    #: When the sender said it. Kept because the collection board shows the
    #: claim beside the payment status, so a fake that dropped the timestamp
    #: could not tell "reported at 9:04" from "never reported".
    reported_at: datetime


@dataclass(slots=True)
class FakeReceipt:
    id: uuid.UUID
    obligation_id: uuid.UUID
    confirmed_by_id: uuid.UUID
    amount_vnd: int
    payment_report_id: uuid.UUID | None
    idempotency_key: uuid.UUID


@lru_cache(maxsize=1)
def _seed_place_records() -> tuple[PlaceRecord, ...]:
    """The seed catalogue as repository records, built once per process."""
    from app.places.catalog import PLACES
    from app.places.details import find_detail
    from app.places.seed_catalog import _destination_for

    out = []
    for place in PLACES:
        prose = find_detail(place["id"])
        out.append(
            PlaceRecord(
                id=place["id"],
                destination_id=_destination_for(place),
                name=place["name"],
                category=place["category"],
                kinds=list(place["kinds"]),
                address=place["address"],
                lat=place["lat"],
                lng=place["lng"],
                rating=place["rating"],
                rating_count=place["rating_count"],
                price_min_vnd=place["price_min_vnd"],
                price_max_vnd=place["price_max_vnd"],
                open_hours=place["open_hours"],
                open_now=place["open_now"],
                travel_minutes=place["travel_minutes"],
                distance_km=place["distance_km"],
                photo_count=place["photo_count"],
                traits=list(place["traits"]),
                group_fit=dict(place["group_fit"]),
                flag=place["flag"],
                description=None if prose is None else prose["description"],
                reviews=None if prose is None else list(prose["reviews"]),
                source="seed",
                source_ref=None,
                license=None,
            )
        )
    return tuple(out)


@lru_cache(maxsize=1)
def _seed_destination_records() -> tuple[DestinationRecord, ...]:
    from app.places.seed_catalog import SEED_DESTINATIONS

    return tuple(DestinationRecord(**row) for row in SEED_DESTINATIONS)


class SeedCatalogueReads:
    """The four catalogue reads, for a test double that is not `FakeRepository`.

    Since M9 the catalogue is a table, so every repository the service is handed
    has to be able to answer for it -- including the small hand-written doubles
    in individual test modules, which exist to make one path fail in a specific
    way and should not have to grow a catalogue to do it.
    """

    def list_places(self, *, destination_id=None, category=None):
        rows = [
            record
            for record in _seed_place_records()
            if (destination_id is None or record.destination_id == destination_id)
            and (category is None or record.category == category)
        ]
        return sorted(rows, key=lambda record: record.id)

    def get_place(self, place_id):
        for record in _seed_place_records():
            if record.id == place_id:
                return record
        return None

    def list_destinations(self):
        return list(_seed_destination_records())

    def get_destination(self, destination_id):
        for record in _seed_destination_records():
            if record.id == destination_id:
                return record
        return None


class FakeRepository(SeedCatalogueReads):
    def __init__(self):
        self.expenses: dict[uuid.UUID, ExpenseIdentity] = {}
        self.confirmed: dict[uuid.UUID, ConfirmedExpense] = {}
        self.version_to_expense: dict[uuid.UUID, uuid.UUID] = {}
        self.version_numbers: dict[uuid.UUID, int] = {}
        self.batched_versions: set[uuid.UUID] = set()
        self.batches: dict[uuid.UUID, BatchForPublish] = {}
        self.obligations: dict[uuid.UUID, PublishObligation] = {}
        self.links: dict[bytes, FakeLink] = {}
        self.reports: dict[uuid.UUID, FakeReport] = {}
        self.objections: list[dict] = []
        self.receipts: dict[uuid.UUID, FakeReceipt] = {}
        self.people: dict[uuid.UUID, PersonRecord] = {}
        self.contexts: dict[uuid.UUID, ContextRecord] = {}
        self.messages: dict[uuid.UUID, MessageRecord] = {}
        self.bills: dict[uuid.UUID, BillRecord] = {}
        self.finances: dict[uuid.UUID, PersonFinanceSummary] = {}
        self.active_memberships: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.outing_invites: dict[uuid.UUID, OutingInviteRecord] = {}
        self.outing_invite_ids_by_digest: dict[bytes, uuid.UUID] = {}
        self.friend_edges: dict[uuid.UUID, dict] = {}
        self.posts: dict[uuid.UUID, PostRecord] = {}
        self.memories: dict[uuid.UUID, MemoryRecord] = {}
        self.account_sessions: dict[uuid.UUID, AccountSessionRecord] = {}
        self.invited_memberships: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.read_marks: dict[tuple[uuid.UUID, uuid.UUID], ReadMarkRecord] = {}
        self.otp_challenges: dict[uuid.UUID, OtpChallengeRecord] = {}
        self.account_identities: dict[tuple[str, str], AccountIdentityRecord] = {}
        # M2 profile: bookmarks, and the two sources the counts read that this
        # fake did not model before (outing -> context, and check-ins).
        self.saved_places: dict[tuple[uuid.UUID, str], SavedPlaceRecord] = {}
        self.person_interests: dict[uuid.UUID, set[str]] = {}
        self.outings_by_context: dict[uuid.UUID, uuid.UUID] = {}
        self.stop_checkins: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.account_session_ids_by_digest: dict[bytes, uuid.UUID] = {}
        self.left_memberships: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.admin_memberships: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.leak_guest_input = False

    @staticmethod
    def _ordered_bill(bill: BillRecord) -> BillRecord:
        return replace(
            bill,
            items=[
                replace(
                    item,
                    shares=sorted(
                        item.shares,
                        key=lambda share: share.participant_id.bytes,
                    ),
                )
                for item in sorted(
                    bill.items,
                    key=lambda item: (item.position, item.item_key),
                )
            ],
            surcharges=sorted(
                bill.surcharges,
                key=lambda surcharge: surcharge.surcharge_key.encode("utf-8"),
            ),
            discounts=sorted(
                bill.discounts,
                key=lambda discount: discount.discount_key.encode("utf-8"),
            ),
        )

    def get_person(self, person_id):
        return self.people.get(person_id)

    def create_person(self, person_id, display_name):
        # No primary key here, so the double-insert conflict the real table
        # raises cannot happen. That case is covered in tests/postgres.
        record = PersonRecord(
            id=person_id,
            display_name=display_name,
            created_at=datetime(2030, 8, 27, 12, tzinfo=UTC),
        )
        self.people[person_id] = record
        return record

    def rename_person(self, person_id, display_name):
        existing = self.people.get(person_id)
        if existing is None:
            return None
        renamed = PersonRecord(
            id=existing.id,
            display_name=display_name,
            created_at=existing.created_at,
        )
        self.people[person_id] = renamed
        return renamed

    # --- friend graph (F03, F04) ---------------------------------------
    #
    # A dict cannot express `uq_friend_edge_live`, the functional partial
    # unique index that makes (A,B) and (B,A) one edge under concurrency. This
    # fake is blind to that race BY CONSTRUCTION, which is why
    # tests/postgres/test_friend_requests_postgres.py exists. Widening this
    # fake until the race "passes" here would be the lie CLAUDE.md names.

    def _friend_record(self, edge, reader_id):
        other = (
            edge["addressee_id"]
            if edge["requester_id"] == reader_id
            else edge["requester_id"]
        )
        person = self.people.get(other)
        return FriendEdgeRecord(
            id=edge["id"],
            requester_id=edge["requester_id"],
            addressee_id=edge["addressee_id"],
            other_person_id=other,
            other_display_name=(
                person.display_name if person is not None else str(other)
            ),
            state=edge["state"],
            decided_by_id=edge["decided_by_id"],
            created_at=edge["created_at"],
            decided_at=edge["decided_at"],
        )

    def get_friend_edge(self, person_a, person_b):
        pair = frozenset((person_a, person_b))
        for edge in self.friend_edges.values():
            same_pair = frozenset((edge["requester_id"], edge["addressee_id"]))
            if same_pair == pair and edge["state"] != "declined":
                return self._friend_record(edge, person_a)
        return None

    def get_friend_request(self, request_id, reader_id):
        edge = self.friend_edges.get(request_id)
        if edge is None:
            return None
        if reader_id not in (edge["requester_id"], edge["addressee_id"]):
            return None
        return self._friend_record(edge, reader_id)

    def open_friend_request(self, *, requester_id, addressee_id, now):
        edge = {
            "id": uuid.uuid4(),
            "requester_id": requester_id,
            "addressee_id": addressee_id,
            "state": "pending",
            "decided_by_id": None,
            "created_at": now,
            "decided_at": None,
        }
        self.friend_edges[edge["id"]] = edge
        return self._friend_record(edge, requester_id)

    def decide_friend_request(self, *, request_id, state, decided_by_id, now):
        edge = self.friend_edges.get(request_id)
        if edge is None:
            return None
        edge["state"] = state
        edge["decided_by_id"] = decided_by_id
        edge["decided_at"] = now
        return self._friend_record(edge, decided_by_id)

    def list_friend_requests(self, person_id, *, direction):
        side = "addressee_id" if direction == "incoming" else "requester_id"
        return [
            self._friend_record(edge, person_id)
            for edge in self.friend_edges.values()
            if edge[side] == person_id and edge["state"] == "pending"
        ]

    def list_friends(self, person_id):
        return [
            self._friend_record(edge, person_id)
            for edge in self.friend_edges.values()
            if edge["state"] == "accepted"
            and person_id in (edge["requester_id"], edge["addressee_id"])
        ]

    # --- F39 posts, F42 audiences ---------------------------------------
    #
    # This fake re-implements the visibility predicate that
    # `SqlAlchemyApiRepository._readable_by` writes in SQL, so `tests/api` is
    # proving the *service*, not the query. The query has its own live cases in
    # tests/postgres/test_posts_postgres.py, and it has to: a dict cannot show
    # that `only_me` rows are excluded by the SELECT rather than by a Python
    # loop that runs after them, and "excluded by the SELECT" is the claim.

    def create_post(self, *, author_id, audience, context_id, body, image_url, now):
        record = PostRecord(
            id=uuid.uuid4(),
            author_id=author_id,
            audience=audience,
            context_id=context_id,
            body=body,
            image_url=image_url,
            created_at=now,
        )
        self.posts[record.id] = record
        return record

    def get_post(self, post_id):
        return self.posts.get(post_id)

    def _post_visible_to(self, record, reader_id):
        if record.author_id == reader_id:
            return True
        if record.audience == "public":
            return True
        if record.audience == "friends":
            edge = self.get_friend_edge(reader_id, record.author_id)
            return edge is not None and edge.state == "accepted"
        if record.audience == "group":
            return record.context_id is not None and self.is_member(
                record.context_id, reader_id
            )
        return False

    def _posts_newest_first(self):
        return sorted(
            self.posts.values(),
            key=lambda record: (record.created_at, record.id.bytes),
            reverse=True,
        )

    def list_posts_visible_to(self, reader_id, *, limit):
        return tuple(
            record
            for record in self._posts_newest_first()
            if self._post_visible_to(record, reader_id)
        )[:limit]

    def list_person_posts_visible_to(self, person_id, reader_id, *, limit):
        return tuple(
            record
            for record in self._posts_newest_first()
            if record.author_id == person_id
            and self._post_visible_to(record, reader_id)
        )[:limit]

    def list_memories(
        self,
        context_id,
        *,
        limit,
        before=None,
        kind=None,
        place_id=None,
        viewer_id=None,
    ):
        """Enough of the wall for F38's widget probe to count rows.

        Added for one reason: the leak probe has to be able to see the leak.
        Without a wall in this fake, an outsider whose membership check had
        been broken would receive an *empty* widget, and "no photo because the
        group has none" and "no photo because the gate held" are the same body.
        A probe that cannot tell those apart proves nothing, so the fake has to
        hold at least one photograph for the gate to withhold.

        Ordering, `kind` and the `has_more` flag match
        `SqlAlchemyApiRepository.list_memories`. `before`, `place_id` and
        `viewer_id` are accepted and unused: the widget passes none of them,
        and a fake that pretended to page or to count hearts would be a second
        implementation of behaviour `tests/postgres` already proves.
        """

        rows = sorted(
            (
                record
                for record in self.memories.values()
                if record.context_id == context_id
                and (kind is None or record.kind == kind)
            ),
            key=lambda record: (record.created_at, record.id.bytes),
            reverse=True,
        )
        return MemoryPage(memories=tuple(rows[:limit]), has_more=len(rows) > limit)

    def membership_role(self, context_id, person_id):
        if (context_id, person_id) in self.admin_memberships:
            return "admin"
        if (context_id, person_id) in self.active_memberships:
            return "member"
        return None

    def is_member(self, context_id, person_id):
        return (context_id, person_id) in self.active_memberships

    def list_members(self, context_id):
        """`ApiRepository` has always declared this; the fake never had it.

        `ApiService.split_bill` reads it through `getattr(..., None)` and falls
        back to "the participants are whoever the shares name" when it is
        missing -- which, against this fake, was always. That fallback makes
        the allocator's `UNKNOWN_PARTICIPANT` check unreachable by
        construction, so the whole `tests/api` layer was proving a membership
        rule it could not have broken.
        """

        return [
            MembershipRecord(
                id=uuid.uuid5(uuid.NAMESPACE_URL, f"{context}/{person}"),
                context_id=context,
                person_id=person,
                display_name=(
                    self.people[person].display_name
                    if person in self.people
                    else f"Thành viên {str(person)[:8]}"
                ),
                state="active",
                role="member",
                origin="named",
                invited_by_id=None,
                joined_at=datetime(2030, 8, 27, 12, tzinfo=UTC),
                left_at=None,
                created_at=datetime(2030, 8, 27, 12, tzinfo=UTC),
            )
            for context, person in sorted(
                self.active_memberships, key=lambda pair: pair[1].bytes
            )
            if context == context_id
        ]

    def get_context(self, context_id):
        return self.contexts.get(context_id)

    def get_message(self, message_id):
        return self.messages.get(message_id)

    def create_outing_invite(
        self,
        *,
        outing_id,
        source,
        invited_person_id,
        invited_by_id,
        token_digest,
        expires_at,
        now,
    ):
        record = OutingInviteRecord(
            id=uuid.uuid4(),
            outing_id=outing_id,
            source=source,
            invited_person_id=invited_person_id,
            invited_by_id=invited_by_id,
            accepted_at=None,
            accepted_by_id=None,
            created_at=now,
            expires_at=expires_at,
            revoked_at=None,
        )
        self.outing_invites[record.id] = record
        if token_digest is not None:
            self.outing_invite_ids_by_digest[token_digest] = record.id
        return record

    def find_outing_invite_for_person(self, outing_id, person_id):
        return next(
            (
                invite
                for invite in self.outing_invites.values()
                if invite.outing_id == outing_id
                and invite.invited_person_id == person_id
            ),
            None,
        )

    def get_outing_invite(self, invite_id):
        return self.outing_invites.get(invite_id)

    def get_outing_invite_by_digest(self, token_digest):
        invite_id = self.outing_invite_ids_by_digest.get(token_digest)
        if invite_id is None:
            return None
        return self.outing_invites.get(invite_id)

    def accept_outing_invite(self, *, invite_id, accepted_by_id, now):
        invite = self.outing_invites.get(invite_id)
        if invite is None:
            raise RepositoryConflict("OUTING_INVITE_NOT_FOUND")
        if invite.accepted_at is not None:
            raise RepositoryConflict("OUTING_INVITE_ALREADY_ACCEPTED")
        if invite.revoked_at is not None or invite.expires_at <= now:
            raise RepositoryConflict("OUTING_INVITE_NOT_REDEEMABLE")
        accepted = replace(
            invite,
            accepted_at=now,
            accepted_by_id=accepted_by_id,
        )
        self.outing_invites[invite_id] = accepted
        return accepted

    def revoke_outing_invite(self, *, invite_id, now):
        invite = self.outing_invites.get(invite_id)
        if invite is None:
            raise RepositoryConflict("OUTING_INVITE_NOT_FOUND")
        if invite.accepted_at is not None:
            raise RepositoryConflict("OUTING_INVITE_ALREADY_ACCEPTED")
        if invite.revoked_at is not None:
            return invite
        revoked = replace(invite, revoked_at=now)
        self.outing_invites[invite_id] = revoked
        return revoked

    def rotate_outing_invite_digest(self, *, invite_id, token_digest, expires_at, now):
        del now
        invite = self.outing_invites.get(invite_id)
        if invite is None:
            raise RepositoryConflict("OUTING_INVITE_NOT_FOUND")
        if invite.invited_person_id is None:
            raise RepositoryConflict("OUTING_INVITE_NOT_NAMED")
        if invite.revoked_at is not None:
            raise RepositoryConflict("OUTING_INVITE_NOT_REDEEMABLE")
        self.outing_invite_ids_by_digest = {
            digest: held
            for digest, held in self.outing_invite_ids_by_digest.items()
            if held != invite_id
        }
        self.outing_invite_ids_by_digest[token_digest] = invite_id
        rotated = replace(invite, expires_at=expires_at)
        self.outing_invites[invite_id] = rotated
        return rotated

    def consume_named_invite_secret(
        self, *, invite_id, token_digest, accepted_by_id, now
    ):
        invite = self.outing_invites.get(invite_id)
        if invite is None:
            raise RepositoryConflict("OUTING_INVITE_NOT_FOUND")
        if invite.invited_person_id is None:
            raise RepositoryConflict("OUTING_INVITE_NOT_NAMED")
        if self.outing_invite_ids_by_digest.get(token_digest) != invite_id:
            raise RepositoryConflict("OUTING_INVITE_NOT_REDEEMABLE")
        if invite.revoked_at is not None or invite.expires_at <= now:
            raise RepositoryConflict("OUTING_INVITE_NOT_REDEEMABLE")
        # The digest leaves the table entirely, exactly as the real adapter
        # nulls the column: a spent secret has nothing left to match against.
        del self.outing_invite_ids_by_digest[token_digest]
        if invite.accepted_at is None:
            invite = replace(invite, accepted_at=now, accepted_by_id=accepted_by_id)
            self.outing_invites[invite_id] = invite
        return invite

    def create_account_session(
        self,
        *,
        person_id,
        token_digest,
        issued_from_invite_id,
        expires_at,
        now,
        issued_via=None,
    ):
        if issued_via is None:
            issued_via = "invite" if issued_from_invite_id is not None else "genesis"
        record = AccountSessionRecord(
            id=uuid.uuid4(),
            person_id=person_id,
            issued_from_invite_id=issued_from_invite_id,
            issued_via=issued_via,
            created_at=now,
            expires_at=expires_at,
            revoked_at=None,
        )
        self.account_sessions[record.id] = record
        self.account_session_ids_by_digest[token_digest] = record.id
        return record

    def get_account_session_by_digest(self, token_digest):
        session_id = self.account_session_ids_by_digest.get(token_digest)
        if session_id is None:
            return None
        return self.account_sessions.get(session_id)

    def revoke_account_session(self, *, session_id, now):
        record = self.account_sessions.get(session_id)
        if record is None:
            return None
        if record.revoked_at is None:
            record = replace(record, revoked_at=now)
            self.account_sessions[session_id] = record
        return record

    def actor_grants(self, person_id):
        """The fake's copy of the roster rule, kept deliberately literal.

        It mirrors `SqlAlchemyApiRepository.actor_grants` rather than being
        clever: the four capability roles are granted to any known person
        because every action that names them also proves a predicate, and
        `platform_moderator` is never granted because nothing says who holds it.
        """

        if person_id not in self.people:
            return ActorGrants(
                person_exists=False, roles=frozenset(), context_ids=frozenset()
            )
        # No `group_admin` here on purpose, mirroring the real adapter: it is a
        # fact about one group, and the service derives it per call.
        roles = {"member", "advancer", "recipient", "sender", "creditor"}
        context_ids = {
            context_id
            for context_id, held in self.active_memberships
            if held == person_id
        }
        if any(held == person_id for _, held in self.left_memberships):
            roles.add("former_member")
        return ActorGrants(
            person_exists=True,
            roles=frozenset(roles),
            context_ids=frozenset(context_ids),
        )

    def _membership_id_for(self, context_id, person_id):
        return uuid.uuid5(uuid.NAMESPACE_URL, f"{context_id}/{person_id}")

    def _messages_in(self, context_id):
        return sorted(
            (m for m in self.messages.values() if m.context_id == context_id),
            key=lambda m: (m.created_at, m.id.bytes),
        )

    def count_unread_messages(self, context_id, person_id):
        mark = self.read_marks.get((context_id, person_id))
        total = 0
        for m in self._messages_in(context_id):
            if m.author_id == person_id:
                continue
            if mark is not None and (m.created_at, m.id.bytes) <= (
                mark.last_read_at,
                mark.last_read_message_id.bytes,
            ):
                continue
            total += 1
        return total

    def list_person_context_summaries(self, person_id):
        pairs = {
            (c, p)
            for c, p in self.active_memberships | self.invited_memberships
            if p == person_id and (c, p) not in self.left_memberships
        }
        out = []
        for context_id, _ in pairs:
            context = self.contexts.get(context_id)
            if context is None:
                continue
            state = (
                "active"
                if (context_id, person_id) in self.active_memberships
                else "invited"
            )
            role = self.membership_role(context_id, person_id) or "member"
            newest = self._messages_in(context_id)
            last = None
            if newest:
                m = newest[-1]
                author = self.people.get(m.author_id) if m.author_id else None
                last = LastMessageRecord(
                    id=m.id,
                    kind=m.kind,
                    preview=(m.body or "")[:80]
                    if m.kind == "text"
                    else ("[Ảnh]" if m.kind == "image" else "[Rủ Đi AI]"),
                    author_id=m.author_id,
                    author_display_name=author.display_name if author else None,
                    created_at=m.created_at,
                )
            out.append(
                PersonContextSummaryRecord(
                    id=context_id,
                    display_name=context.display_name,
                    member_count=sum(
                        1 for c, _ in self.active_memberships if c == context_id
                    ),
                    my_role=role,
                    my_state=state,
                    membership_id=self._membership_id_for(context_id, person_id),
                    joined_at=datetime(2030, 8, 27, 12, tzinfo=UTC)
                    if state == "active"
                    else None,
                    last_message=last,
                    unread_count=self.count_unread_messages(context_id, person_id),
                )
            )
        out.sort(
            key=lambda r: (
                r.last_message is None,
                -(r.last_message.created_at.timestamp()) if r.last_message else 0,
                r.display_name,
            )
        )
        return out

    def get_read_mark(self, context_id, person_id):
        return self.read_marks.get((context_id, person_id))

    def set_read_mark(self, *, context_id, person_id, message, now):
        del now
        current = self.read_marks.get((context_id, person_id))
        if current is None or (message.created_at, message.id.bytes) > (
            current.last_read_at,
            current.last_read_message_id.bytes,
        ):
            current = ReadMarkRecord(
                context_id=context_id,
                person_id=person_id,
                last_read_message_id=message.id,
                last_read_at=message.created_at,
            )
            self.read_marks[(context_id, person_id)] = current
        return current

    def create_otp_challenge(
        self, *, challenge_id, phone_digest, code_digest, expires_at, now
    ):
        record = OtpChallengeRecord(
            id=challenge_id,
            phone_digest=phone_digest,
            code_digest=code_digest,
            created_at=now,
            expires_at=expires_at,
            attempts=0,
            consumed_at=None,
        )
        self.otp_challenges[challenge_id] = record
        return record

    def recent_otp_challenges(self, phone_digest, since):
        return sorted(
            (
                r
                for r in self.otp_challenges.values()
                if r.phone_digest == phone_digest and r.created_at > since
            ),
            key=lambda r: r.created_at,
            reverse=True,
        )

    def get_otp_challenge(self, challenge_id):
        return self.otp_challenges.get(challenge_id)

    def record_otp_attempt(self, *, challenge_id, attempts, consumed, now):
        record = self.otp_challenges.get(challenge_id)
        if record is None:
            return None
        record = replace(
            record,
            attempts=attempts,
            consumed_at=(record.consumed_at or now) if consumed else record.consumed_at,
        )
        self.otp_challenges[challenge_id] = record
        return record

    def get_account_identity(self, provider, subject):
        return self.account_identities.get((provider, subject))

    def create_person_with_identity(
        self, *, person_id, display_name, provider, subject, now
    ):
        if (provider, subject) in self.account_identities:
            raise RepositoryConflict("IDENTITY_ALREADY_BOUND")
        self.create_person(person_id, display_name)
        return self.upsert_account_identity(
            person_id=person_id, provider=provider, subject=subject, now=now
        )

    # --- M2 profile and bookmarks -----------------------------------------

    def update_person_profile(self, person_id, *, changes):
        record = self.people.get(person_id)
        if record is None:
            return None
        record = replace(record, **changes)
        self.people[person_id] = record
        return record

    def profile_counts(self, person_id):
        friends = sum(
            1
            for edge in self.friend_edges.values()
            if edge["state"] == "accepted"
            and person_id in (edge["requester_id"], edge["addressee_id"])
        )
        my_contexts = {
            cid for (cid, pid) in self.active_memberships if pid == person_id
        }
        outings = sum(
            1 for cid in self.outings_by_context.values() if cid in my_contexts
        )
        places = len({stop for (pid, stop) in self.stop_checkins if pid == person_id})
        memories = sum(1 for m in self.memories.values() if m.author_id == person_id)
        return ProfileCounts(
            friends=friends,
            contexts=len(my_contexts),
            outings=outings,
            places_checked_in=places,
            memories=memories,
        )

    def list_person_interests(self, person_id):
        return sorted(self.person_interests.get(person_id, set()))

    def set_person_interests(self, person_id, tags, now):
        self.person_interests[person_id] = set(tags)
        return self.list_person_interests(person_id)

    def interests_by_person(self, person_ids):
        return {
            pid: sorted(self.person_interests[pid])
            for pid in person_ids
            if self.person_interests.get(pid)
        }

    def list_login_providers(self, person_id):
        return sorted(
            {
                identity.provider
                for identity in self.account_identities.values()
                if identity.person_id == person_id
            }
        )

    def are_friends(self, a, b):
        return any(
            edge["state"] == "accepted"
            and {edge["requester_id"], edge["addressee_id"]} == {a, b}
            for edge in self.friend_edges.values()
        )

    def share_active_context(self, a, b):
        mine = {cid for (cid, pid) in self.active_memberships if pid == a}
        return any(cid in mine for (cid, pid) in self.active_memberships if pid == b)

    def list_saved_places(self, person_id):
        rows = [r for (pid, _), r in self.saved_places.items() if pid == person_id]
        return sorted(rows, key=lambda r: (r.created_at, r.id), reverse=True)

    def save_place(self, person_id, place_id, now):
        existing = self.saved_places.get((person_id, place_id))
        if existing is not None:
            return existing, False
        record = SavedPlaceRecord(
            id=uuid.uuid4(), person_id=person_id, place_id=place_id, created_at=now
        )
        self.saved_places[(person_id, place_id)] = record
        return record, True

    def unsave_place(self, person_id, place_id):
        return self.saved_places.pop((person_id, place_id), None) is not None

    def upsert_account_identity(self, *, person_id, provider, subject, now):
        existing = self.account_identities.get((provider, subject))
        if existing is None:
            existing = AccountIdentityRecord(
                id=uuid.uuid4(),
                person_id=person_id,
                provider=provider,
                subject=subject,
                created_at=now,
                last_login_at=now,
            )
        else:
            existing = replace(existing, last_login_at=now)
        self.account_identities[(provider, subject)] = existing
        return existing

    def ensure_invited_membership(
        self, *, context_id, person_id, invited_by_id, origin, now
    ):
        del now
        # The real adapter returns an existing row untouched, which is what
        # keeps an ACTIVE member from being demoted by signing in again.
        state = (
            "active"
            if (context_id, person_id) in self.active_memberships
            else "invited"
        )
        if state == "invited":
            self.invited_memberships.add((context_id, person_id))
        person = self.people.get(person_id)
        return MembershipRecord(
            id=uuid.uuid4(),
            context_id=context_id,
            person_id=person_id,
            display_name="" if person is None else person.display_name,
            state=state,
            role="member",
            origin=origin,
            invited_by_id=invited_by_id,
            joined_at=None,
            left_at=None,
            created_at=datetime(2030, 8, 27, 12, tzinfo=UTC),
        )

    def create_bill(
        self,
        *,
        context_id,
        created_by_id,
        printed_total_vnd,
        items_total_vnd,
        confidence,
        needs_review,
        items,
        surcharges,
        discounts,
        now,
    ):
        # Mirrors the three unique constraints on the bill draft tables so the
        # route's 409 can be exercised without a database. Being taught to
        # refuse is not the same as being unable to accept: what PostgreSQL
        # actually does with these rows is proved in
        # tests/postgres/test_bill_duplicate_item_key_postgres.py.
        for lines, key, code in (
            (items, "item_key", "DUPLICATE_BILL_ITEM_KEY"),
            (surcharges, "surcharge_key", "DUPLICATE_BILL_SURCHARGE_KEY"),
            (discounts, "discount_key", "DUPLICATE_BILL_DISCOUNT_KEY"),
        ):
            keys = [line[key] for line in lines]
            if len(keys) != len(set(keys)):
                raise RepositoryConflict(code)

        bill = BillRecord(
            id=uuid.uuid4(),
            context_id=context_id,
            printed_total_vnd=printed_total_vnd,
            items_total_vnd=items_total_vnd,
            confidence=confidence,
            needs_review=needs_review,
            created_by_id=created_by_id,
            created_at=now,
            items=[
                BillItemRecord(
                    item_key=item["item_key"],
                    name=item["name"],
                    quantity=item["quantity"],
                    unit_price_vnd=item["unit_price_vnd"],
                    line_total_vnd=item["line_total_vnd"],
                    position=item["position"],
                    shares=[
                        BillShareRecord(
                            participant_id=participant_id,
                            source="ai_suggested",
                            decided_by_id=None,
                            decided_at=None,
                        )
                        for participant_id in item["suggested_participant_ids"]
                    ],
                )
                for item in items
            ],
            surcharges=[
                BillSurchargeRecord(
                    surcharge_key=surcharge["surcharge_key"],
                    kind=surcharge["kind"],
                    amount_vnd=surcharge["amount_vnd"],
                    mode=surcharge["mode"],
                )
                for surcharge in surcharges
            ],
            discounts=[
                BillDiscountRecord(
                    discount_key=discount["discount_key"],
                    amount_vnd=discount["amount_vnd"],
                    scope=discount["scope"],
                    target_item_key=discount["target_item_key"],
                )
                for discount in discounts
            ],
        )
        self.bills[bill.id] = bill
        return self._ordered_bill(bill)

    def get_bill(self, bill_id):
        bill = self.bills.get(bill_id)
        return None if bill is None else self._ordered_bill(bill)

    def confirm_bill_assignments(
        self,
        *,
        bill_id,
        assignments,
        decided_by_id,
        now,
    ):
        bill = self.bills.get(bill_id)
        if bill is None:
            raise RepositoryConflict("BILL_NOT_FOUND")

        assignments_by_key = {
            assignment["item_key"]: assignment for assignment in assignments
        }
        item_keys = {item.item_key for item in bill.items}
        if set(assignments_by_key) - item_keys:
            raise RepositoryConflict("UNKNOWN_BILL_ITEM")

        updated_items = []
        for item in bill.items:
            assignment = assignments_by_key.get(item.item_key)
            if assignment is None:
                updated_items.append(item)
                continue
            updated_items.append(
                replace(
                    item,
                    shares=[
                        BillShareRecord(
                            participant_id=participant_id,
                            source="confirmed",
                            decided_by_id=decided_by_id,
                            decided_at=now,
                        )
                        for participant_id in assignment["participant_ids"]
                    ],
                )
            )

        updated = replace(bill, items=updated_items)
        self.bills[bill_id] = updated
        return self._ordered_bill(updated)

    def claim_bill_items(self, *, bill_id, participant_id, item_keys, now):
        """Mirror of the SQL version: this participant's claims, bill-wide.

        Written to the same contract rather than to whatever made the cases
        pass. The one that matters is scope -- shares belonging to other people
        are never touched -- because a fake that dropped them would let the
        route's most damaging bug through the whole API tier.
        """

        bill = self.bills.get(bill_id)
        if bill is None:
            raise RepositoryConflict("BILL_NOT_FOUND")

        requested = dict.fromkeys(item_keys)
        item_keys_present = {item.item_key for item in bill.items}
        if set(requested) - item_keys_present:
            raise RepositoryConflict("UNKNOWN_BILL_ITEM")

        updated_items = []
        for item in bill.items:
            others = [
                share for share in item.shares if share.participant_id != participant_id
            ]
            if item.item_key in requested:
                others.append(
                    BillShareRecord(
                        participant_id=participant_id,
                        source="confirmed",
                        decided_by_id=participant_id,
                        decided_at=now,
                    )
                )
            updated_items.append(replace(item, shares=others))

        updated = replace(bill, items=updated_items)
        self.bills[bill_id] = updated
        return self._ordered_bill(updated)

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
            and (selected is None or version_id not in self.batched_versions)
            and (selected is None or version_id in selected)
        )
        unavailable = (
            tuple(sorted(selected - {record.version_id for record in records}, key=str))
            if selected is not None
            else ()
        )
        return BatchInputs(expenses=records, unavailable_version_ids=unavailable)

    def load_confirmed_receipts(self, context_id):
        batch_version_ids = {
            batch.version_id
            for batch in self.batches.values()
            if batch.context_id == context_id
        }
        totals = {}
        for receipt in self.receipts.values():
            obligation = self.obligations.get(receipt.obligation_id)
            if (
                obligation is None
                or obligation.batch_version_id not in batch_version_ids
                or receipt.confirmed_by_id != obligation.recipient_id
            ):
                continue
            pair = (obligation.sender_id, obligation.recipient_id)
            totals[pair] = totals.get(pair, 0) + receipt.amount_vnd
        return dict(
            sorted(
                totals.items(),
                key=lambda item: (item[0][0].bytes, item[0][1].bytes),
            )
        )

    def save_frozen_batch(
        self,
        *,
        context_id,
        owner_id,
        due_at,
        obligations: tuple[ObligationDraft, ...],
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
            record = PublishObligation(
                id=obligation_id,
                batch_version_id=version_id,
                sender_id=draft.sender_id,
                recipient_id=draft.recipient_id,
                amount_vnd=draft.amount_vnd,
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
        # Counted per obligation, same as SqlAlchemyApiRepository: three
        # objections about one debt must not use up the right to say anything
        # about a different debt on the same link.
        objection_counts: dict[str, int] = {}
        for objection in self.objections:
            if objection["kind"] not in ("not_me", "wrong_amount"):
                continue
            key = str(objection["obligation_id"]) if objection["obligation_id"] else "*"
            objection_counts[key] = objection_counts.get(key, 0) + 1

        # Same derivation as SqlAlchemyApiRepository: a wrong-amount objection
        # naming an obligation makes that obligation disputed, and nothing else.
        disputed_ids = {
            str(objection["obligation_id"])
            for objection in self.objections
            if objection["kind"] == "wrong_amount" and objection["obligation_id"]
        }
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
            blocks.append(
                {
                    "obligation_id": str(item.id),
                    "disputed": str(item.id) in disputed_ids,
                    "objections_used": objection_counts.get(str(item.id), 0),
                    "objections_allowed": OBJECTION_LIMIT,
                    "occasion_label": "bữa tối",
                    "amount_vnd": item.amount_vnd,
                    "recipient_display_name": "Nam",
                    "evidence_requested": any(
                        objection["kind"] == "evidence_request"
                        and objection["obligation_id"] == item.id
                        for objection in self.objections
                    ),
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
            "reports_allowed": REPORT_LIMIT,
            # Counted, not assumed. This double said zero forever, so a test
            # could not have caught the quota never being reached.
            "objections_used": sum(
                objection["token_digest"] == token_digest
                and objection["kind"] in ("not_me", "wrong_amount")
                for objection in self.objections
            ),
            "objections_allowed": OBJECTION_LIMIT,
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

    def save_guest_objection(self, *, token_digest, kind, obligation_id, reason, now):
        del now
        self.objections.append(
            {
                "token_digest": token_digest,
                "kind": kind,
                "obligation_id": obligation_id,
                "reason": reason,
            }
        )
        if kind == "not_me":
            link = self.links.get(token_digest)
            if link is not None:
                link.status = "revoked"

    def save_payment_report(self, *, target, idempotency_key, now):
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
                reported_at=now,
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

    def person_finance_summary(self, person_id, *, movement_limit):
        """Whatever a test put there, handed back.

        Deliberately not a reimplementation of the SQL. A fake that recomputed
        these totals would be a second answer to the money question, and the
        suite would then be checking the fake against itself. What the totals
        should be is settled in `tests/postgres/test_person_finance_postgres.py`
        against the real ledger; what this supports is the layer above -- who is
        allowed to ask, and what the route does with the answer.
        """
        summary = self.finances.get(person_id)
        if summary is None:
            return PersonFinanceSummary(
                person_id=person_id,
                display_name=None,
                spend_vnd=0,
                settled_vnd=0,
                outstanding_vnd=0,
                receivable_vnd=0,
                expense_count=0,
                group_count=0,
                movements=(),
            )
        return replace(summary, movements=summary.movements[:movement_limit])

    def list_batch_obligations(self, batch_id):
        obligations = list(self.obligations.values())
        if not obligations:
            return None
        disputes: dict[str, str | None] = {}
        for objection in self.objections:
            if objection["kind"] == "wrong_amount" and objection["obligation_id"]:
                disputes.setdefault(
                    str(objection["obligation_id"]), objection.get("reason")
                )
        rows = []
        for item in sorted(obligations, key=lambda o: str(o.sender_id)):
            receipts = [
                receipt.amount_vnd
                for receipt in self.receipts.values()
                if receipt.obligation_id == item.id
            ]
            # Earliest, matching the SQL: a repeat report is the same claim
            # said again, not a later one.
            claims = [
                report.reported_at
                for report in self.reports.values()
                if report.obligation_id == item.id
            ]
            key = str(item.id)
            rows.append(
                BatchObligationRow(
                    obligation_id=item.id,
                    sender_id=item.sender_id,
                    recipient_id=getattr(item, "recipient_id", item.sender_id),
                    amount_vnd=item.amount_vnd,
                    status=obligation_status(
                        item.amount_vnd, [{"amount_vnd": amount} for amount in receipts]
                    ),
                    disputed=key in disputes,
                    disputed_reason=disputes.get(key),
                    payment_reported_at=min(claims) if claims else None,
                )
            )
        return BatchBoard(context_id=CONTEXT_ID, obligations=tuple(rows))

    def list_context_batches(self, context_id):
        # The fake keeps no clock on a batch; a fixed instant stands in, and
        # `published_at` follows the status the way the SQL row's column does.
        rows = []
        for batch in self.batches.values():
            if batch.context_id != context_id:
                continue
            ids = {obligation.id for obligation in batch.obligations}
            board = self.list_batch_obligations(batch.id)
            obligations = tuple(
                row
                for row in (() if board is None else board.obligations)
                if row.obligation_id in ids
            )
            rows.append(
                ContextBatchRow(
                    batch_id=batch.id,
                    status=batch.status,
                    created_at=FAKE_BATCH_INSTANT,
                    published_at=(
                        FAKE_BATCH_INSTANT
                        if batch.status in ("published", "collecting")
                        else None
                    ),
                    obligation_count=len(obligations),
                    confirmed_count=sum(
                        1
                        for row in obligations
                        if row.status in ("confirmed", "over_confirmed")
                    ),
                    disputed_count=sum(1 for row in obligations if row.disputed),
                    total_vnd=sum(row.amount_vnd for row in obligations),
                )
            )
        return tuple(rows)

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

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)

    def patch(self, path, **kwargs):
        return self.request("PATCH", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request("DELETE", path, **kwargs)


@pytest.fixture
def repository():
    """The standard cast starts out inside the standard group.

    Every test here that spends money uses `helpers.expense_payload`, whose
    default people are `SENDER_ID` and `ADVANCER_ID` in `CONTEXT_ID`. That they
    belong to that group was always the intent -- it just was not written down
    anywhere, because nothing had ever asked. Now the ledger asks, so the fake
    has to state it.

    `OTHER_ID` is deliberately **not** here. Across this suite it is the person
    standing outside: `test_context_read` and `test_context_balances` both use
    it to prove that holding a group id is not membership. Seeding it turns
    those two green for the wrong reason -- measured, not guessed: adding it
    here flips both from 403 to 200. The three tests that do want it spending
    money say so themselves via `helpers.join_group`.

    That is the rule for anything added here later: seed the id only if every
    test in the suite agrees it is an insider. A fixture that seeds every id a
    test mentions would silence the membership gate entirely -- see
    `test_expense_participants_must_be_members.py`.
    """

    repository = FakeRepository()
    for person_id in (SENDER_ID, ADVANCER_ID):
        repository.active_memberships.add((CONTEXT_ID, person_id))
    return repository


@pytest.fixture
def client(repository, monkeypatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    # This runner's Python 3.13 thread executor deadlocks even for
    # ``asyncio.to_thread(lambda: 1)``. Execute Starlette's sync adapters inline
    # for the fake-only tests; production routes remain conventional sync routes.
    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    # Dev, explicitly. This suite asserts the header adapter, which is the
    # mode that trusts `X-Actor-*`; `create_app()` with no argument is prod
    # now, and a suite that quietly kept the old default would have been
    # testing an adapter the product no longer ships.
    app = create_app(auth_mode="dev")
    app.dependency_overrides[get_repository] = lambda: repository
    return ASGITestClient(app)
