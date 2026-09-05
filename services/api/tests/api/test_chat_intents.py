"""Slash commands and mentions in `POST /contexts/{id}/messages` (M3).

What this layer proves: the message is stored before anything else happens;
`/plan` and `@Rủ Đi` ask the companion for a turn and a full window is
reported in the body rather than as 429; `/vote` creates a poll and a poll card
in the caller's name that the cadence does not read as an AI turn; a malformed
vote and `/chia-bill` answer honestly; a client card is grounded by the same
whitelist as the model's, so `poll` cannot be forged; and a forward poll that
finds nothing echoes its cursor.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import anyio
import pytest

from app.api import companion_places
from app.api.cursors import decode_cursor
from app.api.deps import get_chat_expense_reader, get_companion, get_repository
from app.api.main import create_app
from app.api.repository import (
    MembershipRecord,
    MessagePage,
    MessageRecord,
    ReactionRecord,
    VoteOptionRecord,
    VoteRecord,
)
from app.api.routes.messages import get_message_intent_limiter
from app.api.search_rate_limit import FixedWindowLimiter
from app.domain.chat_expense import ChatExpenseError

from .conftest import SeedCatalogueReads, ASGITestClient
from .helpers import actor_headers

NOW = datetime(2030, 8, 27, 12, 0, tzinfo=UTC)
CONTEXT_ID = uuid.UUID("3cc00000-cccc-4ccc-8ccc-0000c0000009")
MEMBER_ID = uuid.UUID("4dd00000-dddd-4ddd-8ddd-0000d0000009")
CATALOGUE = [
    {
        "id": "p-quan-a",
        "name": "Quán A",
        "category": "food",
        "price_band": "mid",
        "lat": 11.94,
        "lng": 108.44,
    }
]
TEXT_CARD = {"kind": "text", "payload": {"text": "Tối mai đi ăn rồi cà phê nhé."}}


class ChatRepository(SeedCatalogueReads):
    """One group, one member, a growing feed, and the votes it created."""

    def __init__(self) -> None:
        self.messages: list[MessageRecord] = []
        self.votes: dict[uuid.UUID, VoteRecord] = {}
        self.reactions: dict[tuple[uuid.UUID, uuid.UUID, str], datetime] = {}
        self.clock = NOW

    def is_member(self, context_id, person_id):
        del person_id
        return context_id == CONTEXT_ID

    def list_members(self, context_id):
        del context_id
        return [
            MembershipRecord(
                id=uuid.uuid4(),
                context_id=CONTEXT_ID,
                person_id=MEMBER_ID,
                display_name="Hà",
                state="active",
                role="member",
                origin="founder",
                invited_by_id=None,
                joined_at=NOW,
                left_at=None,
                created_at=NOW,
            )
        ]

    def get_person(self, person_id):
        from app.api.repository import PersonRecord

        return PersonRecord(id=person_id, display_name="Hà", created_at=NOW)

    def list_messages(self, context_id, limit, before=None, after=None):
        rows = [m for m in self.messages if m.context_id == context_id]
        if after is not None:
            rows = [m for m in rows if (m.created_at, m.id) > after]
        if before is not None:
            rows = [m for m in rows if (m.created_at, m.id) < before]
        rows.sort(key=lambda m: (m.created_at, m.id), reverse=True)
        page = rows[:limit]
        if after is not None:
            page = sorted(page, key=lambda m: (m.created_at, m.id))
        return MessagePage(messages=tuple(page), has_more=len(rows) > limit)

    def create_message(self, **fields):
        self.clock += timedelta(seconds=1)
        record = MessageRecord(
            id=uuid.uuid4(),
            context_id=fields["context_id"],
            author_id=fields["author_id"],
            kind=fields["kind"],
            body=fields["body"],
            image_url=fields["image_url"],
            card=fields["card"],
            created_at=self.clock,
        )
        self.messages.append(record)
        return record

    def get_message(self, message_id):
        return next((m for m in self.messages if m.id == message_id), None)

    def add_reaction(self, *, message_id, person_id, kind, now):
        key = (message_id, person_id, kind)
        if key in self.reactions:
            return False
        self.reactions[key] = now
        return True

    def remove_reaction(self, *, message_id, person_id, kind):
        return self.reactions.pop((message_id, person_id, kind), None) is not None

    def list_reactions(self, message_ids):
        wanted = set(message_ids)
        return [
            ReactionRecord(message_id=m, person_id=p, kind=k)
            for (m, p, k), _ in sorted(self.reactions.items(), key=lambda kv: kv[1])
            if m in wanted
        ]

    def create_vote(
        self, *, context_id, outing_id, created_by_id, question, options, now
    ):
        vote_id = uuid.uuid4()
        record = VoteRecord(
            id=vote_id,
            context_id=context_id,
            outing_id=outing_id,
            created_by_id=created_by_id,
            question=question,
            created_at=now,
            closed_at=None,
            closed_by_id=None,
            options=tuple(
                VoteOptionRecord(
                    id=uuid.uuid4(),
                    vote_id=vote_id,
                    position=i,
                    label=o["label"],
                    place_name=o["place_name"],
                )
                for i, o in enumerate(options)
            ),
            ballots=(),
        )
        self.votes[vote_id] = record
        return record


class CountingCompanion:
    def __init__(self) -> None:
        self.calls = 0

    def reply(self, **kwargs) -> dict:
        del kwargs
        self.calls += 1
        return TEXT_CARD


@pytest.fixture
def repository():
    return ChatRepository()


@pytest.fixture
def companion():
    return CountingCompanion()


class TableReader:
    """Answers from a table keyed by message text; unknown text is «not an expense»."""

    def __init__(self, table=None, *, fail=None):
        self.table = table or {}
        self.fail = fail
        self.texts: list[str] = []

    def read(self, text: str) -> dict:
        if self.fail is not None:
            raise self.fail
        self.texts.append(text)
        return self.table.get(text, {"is_expense": False})


def _client(repository, companion, monkeypatch, *, limiter=None, reader=None):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr(
        companion_places, "load_place_catalogue", lambda *_: list(CATALOGUE)
    )
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_companion] = lambda: companion
    if limiter is not None:
        app.dependency_overrides[get_message_intent_limiter] = lambda: limiter
    app.dependency_overrides[get_chat_expense_reader] = lambda: reader or TableReader(
        fail=ChatExpenseError("CHAT_READER_NOT_CONFIGURED")
    )
    return ASGITestClient(app)


@pytest.fixture
def client(repository, companion, monkeypatch):
    return _client(repository, companion, monkeypatch)


def _post(client, body):
    return client.post(
        f"/contexts/{CONTEXT_ID}/messages",
        json={"kind": "text", "body": body},
        headers=actor_headers(actor_id=MEMBER_ID),
    )


def test_an_ordinary_message_is_stored_and_asks_nobody_anything(
    client, repository, companion
):
    response = _post(client, "tối nay ăn gì")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["intent"] is None and body["companion"] is None and body["vote"] is None
    assert body["intent_error"] is None
    assert [m.body for m in repository.messages] == ["tối nay ăn gì"]
    assert companion.calls == 0


@pytest.mark.parametrize("text", ["/plan tối mai đi đâu", "@Rủ Đi gợi ý quán đi"])
def test_plan_and_mention_ask_the_companion_after_the_message_is_stored(
    client, repository, companion, text
):
    response = _post(client, text)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["intent"] == ("plan" if text.startswith("/") else "mention")
    assert body["companion"]["spoke"] is True
    assert body["companion"]["message"]["card"] == TEXT_CARD
    assert companion.calls == 1
    kinds = [(m.kind, m.author_id) for m in repository.messages]
    assert kinds == [("text", MEMBER_ID), ("ai_card", None)]


def test_a_full_companion_window_is_reported_in_the_body_not_as_429(
    repository, companion, monkeypatch
):
    client = _client(
        repository,
        companion,
        monkeypatch,
        limiter=FixedWindowLimiter(
            limit=0,
            window_seconds=60,
            code="rate_limited",
            message="Thử lại sau một phút.",
        ),
    )
    response = _post(client, "/plan đi đâu")
    assert response.status_code == 201, response.text
    assert response.json()["intent"] == "plan"
    assert response.json()["intent_error"] == "companion_rate_limited"
    assert response.json()["companion"] is None
    assert companion.calls == 0
    assert [m.body for m in repository.messages] == ["/plan đi đâu"], (
        "tin nhắn phải được giữ"
    )


def test_vote_creates_a_poll_and_a_poll_card_in_the_callers_name(
    client, repository, companion
):
    response = _post(client, "/vote Ăn gì tối nay? Bún bò | Phở | Cơm tấm")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["intent"] == "vote" and body["intent_error"] is None
    assert body["vote"]["question"] == "Ăn gì tối nay?"
    assert [o["label"] for o in body["vote"]["options"]] == ["Bún bò", "Phở", "Cơm tấm"]
    assert len(repository.votes) == 1
    card = repository.messages[-1]
    assert card.kind == "ai_card" and card.author_id == MEMBER_ID, (
        "thẻ poll là của người, không phải của AI"
    )
    assert card.card["kind"] == "poll"
    assert card.card["payload"]["vote_id"] == body["vote"]["id"]
    assert companion.calls == 0, "một cuộc bình chọn không tốn lượt AI"


def test_a_poll_card_does_not_count_as_the_companion_speaking_last(
    client, repository, companion
):
    _post(client, "/vote Đi đâu? Đà Lạt | Vũng Tàu")
    # The last message is the poll card. An unrequested turn is refused only
    # while the COMPANION spoke last; a person's poll card is not that.
    turn = client.post(
        f"/contexts/{CONTEXT_ID}/ai-turn", headers=actor_headers(actor_id=MEMBER_ID)
    )
    assert turn.status_code == 200, turn.text
    assert turn.json()["spoke"] is True, turn.json()
    # Control: after the companion itself spoke, the same unrequested turn is refused.
    again = client.post(
        f"/contexts/{CONTEXT_ID}/ai-turn", headers=actor_headers(actor_id=MEMBER_ID)
    )
    assert again.json()["spoke"] is False
    assert again.json()["reason"] == "already_spoke_last"


def test_a_malformed_vote_is_named_not_guessed(client, repository):
    response = _post(client, "/vote Ăn gì?")
    assert response.status_code == 201
    assert response.json()["intent"] == "vote"
    assert response.json()["intent_error"] == "vote_malformed"
    assert response.json()["vote"] is None
    assert repository.votes == {}
    assert len(repository.messages) == 1


def test_chia_bill_without_a_configured_reader_says_so(client, repository):
    _post(client, "tối qua tôi trả 180k tiền ăn")
    response = _post(client, "/chia-bill")
    assert response.status_code == 201
    assert response.json()["intent"] == "chia_bill"
    assert response.json()["intent_error"] == "chia_bill_not_available"
    assert response.json()["expense_card"] is None
    assert len(repository.messages) == 2, "hai tin người vẫn được giữ, không có thẻ"


def test_chia_bill_reads_recent_human_text_into_one_draft_card(
    repository, companion, monkeypatch
):
    reader = TableReader(
        {
            "tối qua tôi trả 180k tiền ăn": {
                "is_expense": True,
                "title": "Tiền ăn",
                "amount_text": "180k",
            },
            "mình ứng 1 triệu tiền phòng": {
                "is_expense": True,
                "title": "Tiền phòng",
                "amount_text": "1 triệu",
            },
        }
    )
    client = _client(repository, companion, monkeypatch, reader=reader)
    _post(client, "tối qua tôi trả 180k tiền ăn")
    _post(client, "haha ok")
    _post(client, "mình ứng 1 triệu tiền phòng")
    response = _post(client, "/chia-bill")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["intent"] == "chia_bill" and body["intent_error"] is None
    card = body["expense_card"]
    assert card["kind"] == "ai_card" and card["author_id"] is None
    drafts = card["card"]["payload"]["drafts"]
    assert [d["title"] for d in drafts] == ["Tiền ăn", "Tiền phòng"], (
        "cũ trước, đúng thứ tự đã tiêu"
    )
    assert [d["amount_vnd"] for d in drafts] == [180000, 1000000]
    assert all(d["paid_by_id"] == str(MEMBER_ID) for d in drafts), (
        "người trả = tác giả tin, không phải mô hình nói"
    )
    assert all(d["shared_by"] == [str(MEMBER_ID)] for d in drafts)
    assert all(d["needs_review"] is True for d in drafts)
    assert all(isinstance(d["amount_vnd"], int) for d in drafts)
    # The command itself was not read, and no expense exists: only messages.
    assert "/chia-bill" not in reader.texts
    assert repository.messages[-1].kind == "ai_card"
    assert repository.messages[-1].card["kind"] == "expense_draft"


def test_chia_bill_with_nothing_to_split_posts_no_card(
    repository, companion, monkeypatch
):
    client = _client(repository, companion, monkeypatch, reader=TableReader())
    _post(client, "haha ok")
    response = _post(client, "/chia-bill")
    assert response.json()["intent_error"] == "chia_bill_no_expenses"
    assert response.json()["expense_card"] is None
    assert all(m.kind == "text" for m in repository.messages)


def test_a_reader_that_names_a_person_sinks_the_whole_batch(
    repository, companion, monkeypatch
):
    reader = TableReader(
        {
            "tôi trả 180k": {
                "is_expense": True,
                "title": "x",
                "amount_text": "180k",
                "paid_by": "Nam",
            }
        }
    )
    client = _client(repository, companion, monkeypatch, reader=reader)
    _post(client, "tôi trả 180k")
    response = _post(client, "/chia-bill")
    assert response.json()["intent_error"] == "chia_bill_refused"
    assert response.json()["expense_card"] is None


def test_chia_bill_reads_at_most_eight_messages(repository, companion, monkeypatch):
    reader = TableReader()
    client = _client(repository, companion, monkeypatch, reader=reader)
    for i in range(12):
        _post(client, f"tin {i}")
    _post(client, "/chia-bill")
    assert len(reader.texts) == 8
    assert reader.texts[0] == "tin 11", "đọc từ tin mới nhất"


def test_a_client_card_is_grounded_and_a_poll_cannot_be_forged(client, repository):
    forged = client.post(
        f"/contexts/{CONTEXT_ID}/messages",
        json={"kind": "ai_card", "card": {"kind": "poll", "payload": {"vote_id": "x"}}},
        headers=actor_headers(actor_id=MEMBER_ID),
    )
    assert forged.status_code == 422 and forged.json()["code"] == "card_ungrounded"
    unknown_place = client.post(
        f"/contexts/{CONTEXT_ID}/messages",
        json={
            "kind": "ai_card",
            "card": {
                "kind": "places",
                "payload": {"title": "x", "items": [{"place_id": "p-khong-co"}]},
            },
        },
        headers=actor_headers(actor_id=MEMBER_ID),
    )
    assert unknown_place.status_code == 422
    assert repository.messages == []
    honest = client.post(
        f"/contexts/{CONTEXT_ID}/messages",
        json={
            "kind": "ai_card",
            "card": {"kind": "text", "payload": {"text": "Đi thôi", "extra": 1}},
        },
        headers=actor_headers(actor_id=MEMBER_ID),
    )
    assert honest.status_code == 201, honest.text
    assert honest.json()["card"] == {"kind": "text", "payload": {"text": "Đi thôi"}}, (
        "khoá lạ không được chép"
    )


def test_a_forward_poll_that_finds_nothing_echoes_its_cursor(client, repository):
    _post(client, "một")
    last = _post(client, "hai").json()["cursor"]
    empty = client.get(
        f"/contexts/{CONTEXT_ID}/messages?after={last}",
        headers=actor_headers(actor_id=MEMBER_ID),
    )
    assert empty.status_code == 200, empty.text
    assert empty.json()["messages"] == []
    assert empty.json()["next_cursor"] == last, (
        "trang rỗng phải trả lại cursor để client giữ chỗ"
    )
    decode_cursor(empty.json()["next_cursor"])
    first_page = client.get(
        f"/contexts/{CONTEXT_ID}/messages", headers=actor_headers(actor_id=MEMBER_ID)
    )
    assert first_page.json()["next_cursor"] is not None


# ---- reactions (M3) -------------------------------------------------------

OTHER_ID = uuid.UUID("5ee00000-eeee-4eee-8eee-0000e0000009")


def _react(client, message_id, kind, who=MEMBER_ID):
    return client.post(
        f"/contexts/{CONTEXT_ID}/messages/{message_id}/reactions",
        json={"kind": kind},
        headers=actor_headers(actor_id=who),
    )


def test_a_reaction_is_idempotent_and_the_list_is_reader_aware(client, repository):
    posted = _post(client, "đi thôi").json()
    first = _react(client, posted["id"], "heart")
    again = _react(client, posted["id"], "heart")
    assert first.status_code == 201 and again.status_code == 201, (
        first.text,
        again.text,
    )
    assert again.json()["reactions"] == [{"kind": "heart", "count": 1, "mine": True}], (
        "hai lần bấm là một tim"
    )
    theirs = _react(client, posted["id"], "heart", who=OTHER_ID).json()
    assert theirs["reactions"] == [{"kind": "heart", "count": 2, "mine": True}]
    page = client.get(
        f"/contexts/{CONTEXT_ID}/messages", headers=actor_headers(actor_id=MEMBER_ID)
    ).json()
    assert page["messages"][0]["reactions"] == [
        {"kind": "heart", "count": 2, "mine": True}
    ]
    stranger = uuid.uuid4()
    page = client.get(
        f"/contexts/{CONTEXT_ID}/messages", headers=actor_headers(actor_id=stranger)
    ).json()
    assert page["messages"][0]["reactions"] == [
        {"kind": "heart", "count": 2, "mine": False}
    ]
    assert "person" not in str(page["messages"][0]["reactions"]), (
        "danh sách là số đếm, không phải tên"
    )


def test_taking_a_reaction_back_returns_the_remaining_list(client, repository):
    posted = _post(client, "đi thôi").json()
    _react(client, posted["id"], "heart")
    _react(client, posted["id"], "fire", who=OTHER_ID)
    gone = client.delete(
        f"/contexts/{CONTEXT_ID}/messages/{posted['id']}/reactions/heart",
        headers=actor_headers(actor_id=MEMBER_ID),
    )
    assert gone.status_code == 200, gone.text
    assert gone.json()["reactions"] == [{"kind": "fire", "count": 1, "mine": False}]
    twice = client.delete(
        f"/contexts/{CONTEXT_ID}/messages/{posted['id']}/reactions/heart",
        headers=actor_headers(actor_id=MEMBER_ID),
    )
    assert twice.status_code == 200, "bỏ cái không còn vẫn là «không còn»"


def test_unknown_kinds_and_foreign_messages_are_refused(client, repository):
    posted = _post(client, "đi thôi").json()
    assert _react(client, posted["id"], "poop").status_code == 422
    missing = _react(client, uuid.uuid4(), "heart")
    assert missing.status_code == 404 and missing.json()["code"] == "message_not_found"
    other_context = client.post(
        f"/contexts/{uuid.uuid4()}/messages/{posted['id']}/reactions",
        json={"kind": "heart"},
        headers=actor_headers(actor_id=MEMBER_ID),
    )
    assert other_context.status_code in (403, 404), (
        "một nhóm khác không mượn được tin của nhóm này"
    )
    assert repository.reactions == {}
