"""Group messages against real PostgreSQL: who may read them, and how a client
walks them.

Two things are being proved here and neither survives a dict-backed fake.

Privacy first. A group conversation is the most sensitive thing this product
stores after bank destinations -- it names who is going where, with whom, and
what they spent. Membership is `state = 'active' AND left_at IS NULL`, a fact
that only the database holds. The outsider in these tests arrives with an
`X-Actor-Contexts` header that CLAIMS the group, because that header is written
by a gateway and a gateway is not an authority on membership. If the check ever
gets rewritten to read the claim instead of the row, these tests go red.

Paging second. `created_at` is not a position: PostgreSQL's `now()` is the
transaction timestamp, so every message written in one transaction shares it to
the microsecond. Ordering by timestamp alone would make the boundary between
two pages arbitrary and re-serve or skip whatever sits on it. The cursor is
therefore `(created_at, id)`, and the tie test below writes several messages at
one instant on purpose.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import Actor
from app.api.errors import ApiProblem
from app.api.repository import SqlAlchemyApiRepository
from app.api.schemas import MessageCreateRequest, MessageQuery
from app.api.service import ApiService
from app.db.models import (
    Context,
    Membership,
    MembershipState,
    Message,
    MessageKind,
    Person,
)

NOW = datetime(2030, 8, 29, 9, 0, tzinfo=UTC)
ROLES = frozenset({"member", "group_admin"})


def _actor(person_id: uuid.UUID, context_id: uuid.UUID | None = None) -> Actor:
    return Actor(
        id=person_id,
        roles=ROLES,
        context_ids=frozenset({context_id} if context_id else set()),
    )


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _group(session: Session) -> tuple[Context, Person, Person]:
    """A group with one active member, plus a stranger who is not in it."""
    owner = _person(session, "Nam")
    outsider = _person(session, "Người lạ")
    context = Context(id=uuid.uuid4(), display_name="Nhóm ăn tối", created_by_id=owner.id)
    session.add(context)
    session.flush()
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=owner.id,
            state=MembershipState.ACTIVE,
            joined_at=NOW,
        )
    )
    session.flush()
    return context, owner, outsider


def _write(
    session: Session,
    context: Context,
    author: Person | None,
    text: str,
    at: datetime,
) -> Message:
    message = Message(
        id=uuid.uuid4(),
        context_id=context.id,
        author_id=None if author is None else author.id,
        kind=MessageKind.TEXT,
        body=text,
        created_at=at,
    )
    session.add(message)
    session.flush()
    return message


def _service(session: Session) -> ApiService:
    return ApiService(SqlAlchemyApiRepository(session))


# --- privacy ----------------------------------------------------------------


def test_a_member_reads_the_messages_of_their_own_group(postgres_session: Session):
    context, owner, _ = _group(postgres_session)
    _write(postgres_session, context, owner, "Tối nay ăn gì?", NOW)

    page = _service(postgres_session).list_context_messages(
        context.id, MessageQuery(), _actor(owner.id, context.id)
    )

    assert [message.body for message in page.messages] == ["Tối nay ăn gì?"]


def test_somebody_outside_the_group_cannot_read_its_messages(
    postgres_session: Session,
):
    """The outsider's actor header claims this very group. Membership is a row
    in `memberships`, never a claim carried in a request."""
    context, owner, outsider = _group(postgres_session)
    _write(postgres_session, context, owner, "Quán cũ 7h nhé", NOW)

    with pytest.raises(ApiProblem) as caught:
        _service(postgres_session).list_context_messages(
            context.id, MessageQuery(), _actor(outsider.id, context.id)
        )

    assert caught.value.status_code == 403
    # And the refusal leaks neither the conversation nor who is in it.
    assert "Quán cũ" not in str(caught.value.detail)
    assert "Nam" not in str(caught.value.detail)


def test_somebody_outside_the_group_cannot_post_into_it(postgres_session: Session):
    context, _, outsider = _group(postgres_session)

    with pytest.raises(ApiProblem) as caught:
        _service(postgres_session).post_context_message(
            context.id,
            MessageCreateRequest(kind="text", body="cho tôi vào với"),
            _actor(outsider.id, context.id),
        )

    assert caught.value.status_code == 403


def test_an_invited_person_cannot_read_before_they_accept(postgres_session: Session):
    """Being added to a group is something that happens to you. An invite that
    already showed the conversation would make accepting it decorative."""
    context, owner, invitee = _group(postgres_session)
    _write(postgres_session, context, owner, "chốt quán", NOW)
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=invitee.id,
            state=MembershipState.INVITED,
        )
    )
    postgres_session.flush()

    with pytest.raises(ApiProblem) as caught:
        _service(postgres_session).list_context_messages(
            context.id, MessageQuery(), _actor(invitee.id, context.id)
        )

    assert caught.value.status_code == 403


def test_a_member_who_left_stops_reading_new_messages(postgres_session: Session):
    """Leaving is recorded rather than deleted, which makes it easy to keep
    reading a row that has ended."""
    context, owner, friend = _group(postgres_session)
    membership = Membership(
        id=uuid.uuid4(),
        context_id=context.id,
        person_id=friend.id,
        state=MembershipState.ACTIVE,
        joined_at=NOW,
    )
    postgres_session.add(membership)
    _write(postgres_session, context, owner, "đi chưa", NOW)
    postgres_session.flush()

    service = _service(postgres_session)
    assert service.list_context_messages(
        context.id, MessageQuery(), _actor(friend.id, context.id)
    ).messages

    membership.state = MembershipState.LEFT
    membership.left_at = NOW
    postgres_session.flush()

    with pytest.raises(ApiProblem) as caught:
        service.list_context_messages(
            context.id, MessageQuery(), _actor(friend.id, context.id)
        )
    assert caught.value.status_code == 403


def test_a_member_of_one_group_does_not_see_another_group(postgres_session: Session):
    """Two groups, one reader. The query is scoped by `context_id`; a missing
    WHERE clause here merges every conversation on the platform into one."""
    mine, owner, _ = _group(postgres_session)
    theirs, stranger, _ = _group(postgres_session)
    _write(postgres_session, mine, owner, "của tôi", NOW)
    _write(postgres_session, theirs, stranger, "của họ", NOW)

    page = _service(postgres_session).list_context_messages(
        mine.id, MessageQuery(), _actor(owner.id, mine.id)
    )

    assert [message.body for message in page.messages] == ["của tôi"]


# --- paging -----------------------------------------------------------------


def _walk_backwards(service: ApiService, context_id, actor, limit: int) -> list[str]:
    """Every message a client would see scrolling up, in the order it sees them."""
    seen: list[str] = []
    cursor: str | None = None
    for _ in range(50):  # a bound, so a broken cursor loops finitely
        page = service.list_context_messages(
            context_id, MessageQuery(limit=limit, before=cursor), actor
        )
        seen.extend(message.body for message in page.messages)
        if not page.has_more:
            return seen
        assert page.next_cursor is not None
        cursor = page.next_cursor
    raise AssertionError("paging did not terminate")


def test_scrolling_up_sees_every_message_exactly_once(postgres_session: Session):
    context, owner, _ = _group(postgres_session)
    bodies = [f"tin {index}" for index in range(7)]
    for index, body in enumerate(bodies):
        _write(postgres_session, context, owner, body, NOW + timedelta(minutes=index))

    seen = _walk_backwards(
        _service(postgres_session), context.id, _actor(owner.id, context.id), limit=3
    )

    # Newest first: that is the order a chat screen fills from the bottom.
    assert seen == list(reversed(bodies))


def test_paging_is_total_even_when_messages_share_one_timestamp(
    postgres_session: Session,
):
    """`now()` is the transaction timestamp. Five messages sent in one burst
    share it exactly, and a cursor built on time alone cannot tell them apart:
    the boundary row is either served twice or skipped."""
    context, owner, _ = _group(postgres_session)
    bodies = [f"burst {index}" for index in range(5)]
    for body in bodies:
        _write(postgres_session, context, owner, body, NOW)

    seen = _walk_backwards(
        _service(postgres_session), context.id, _actor(owner.id, context.id), limit=2
    )

    assert sorted(seen) == sorted(bodies)
    assert len(seen) == len(set(seen))


def test_a_message_sent_mid_scroll_does_not_shift_the_page_underneath(
    postgres_session: Session,
):
    """The reason this is a cursor and not an offset. With `OFFSET 2` the new
    message pushes everything down one row and the reader sees `tin 4` twice."""
    context, owner, _ = _group(postgres_session)
    for index in range(5):
        _write(
            postgres_session, context, owner, f"tin {index}", NOW + timedelta(minutes=index)
        )

    service = _service(postgres_session)
    actor = _actor(owner.id, context.id)
    first = service.list_context_messages(context.id, MessageQuery(limit=2), actor)
    assert [message.body for message in first.messages] == ["tin 4", "tin 3"]

    _write(postgres_session, context, owner, "tin mới", NOW + timedelta(hours=1))

    second = service.list_context_messages(
        context.id, MessageQuery(limit=2, before=first.next_cursor), actor
    )
    assert [message.body for message in second.messages] == ["tin 2", "tin 1"]


def test_asking_for_what_is_new_returns_only_newer_messages_oldest_first(
    postgres_session: Session,
):
    """The polling direction. A client holds the cursor of the newest message
    it has and asks forward; it must never be handed its own tail again."""
    context, owner, _ = _group(postgres_session)
    for index in range(3):
        _write(
            postgres_session, context, owner, f"cũ {index}", NOW + timedelta(minutes=index)
        )

    service = _service(postgres_session)
    actor = _actor(owner.id, context.id)
    latest = service.list_context_messages(context.id, MessageQuery(limit=1), actor)
    watermark = latest.messages[0].cursor

    assert (
        service.list_context_messages(
            context.id, MessageQuery(after=watermark), actor
        ).messages
        == []
    )

    for index in range(2):
        _write(
            postgres_session, context, owner, f"mới {index}", NOW + timedelta(hours=index + 1)
        )

    fresh = service.list_context_messages(
        context.id, MessageQuery(after=watermark), actor
    )
    assert [message.body for message in fresh.messages] == ["mới 0", "mới 1"]


def test_each_message_carries_the_cursor_that_resumes_from_it(
    postgres_session: Session,
):
    """A client must never have to build a cursor itself; the moment it does,
    the encoding stops being ours to change."""
    context, owner, _ = _group(postgres_session)
    for index in range(3):
        _write(
            postgres_session, context, owner, f"tin {index}", NOW + timedelta(minutes=index)
        )

    service = _service(postgres_session)
    actor = _actor(owner.id, context.id)
    page = service.list_context_messages(context.id, MessageQuery(), actor)
    middle = page.messages[1]

    older = service.list_context_messages(
        context.id, MessageQuery(before=middle.cursor), actor
    )
    assert [message.body for message in older.messages] == ["tin 0"]


def test_an_empty_group_pages_without_a_cursor_to_nowhere(postgres_session: Session):
    context, owner, _ = _group(postgres_session)

    page = _service(postgres_session).list_context_messages(
        context.id, MessageQuery(), _actor(owner.id, context.id)
    )

    assert page.messages == []
    assert page.has_more is False
    assert page.next_cursor is None


def test_a_forged_cursor_is_refused_rather_than_ignored(postgres_session: Session):
    """Ignoring an unparseable cursor silently restarts the history from the
    top, which reads exactly like a working page."""
    context, owner, _ = _group(postgres_session)
    _write(postgres_session, context, owner, "tin", NOW)

    with pytest.raises(ApiProblem) as caught:
        _service(postgres_session).list_context_messages(
            context.id, MessageQuery(before="khong-phai-cursor"), _actor(owner.id, context.id)
        )

    assert caught.value.status_code == 422


def test_asking_in_both_directions_at_once_is_refused(postgres_session: Session):
    context, owner, _ = _group(postgres_session)
    message = _write(postgres_session, context, owner, "tin", NOW)
    service = _service(postgres_session)
    actor = _actor(owner.id, context.id)
    cursor = service.list_context_messages(
        context.id, MessageQuery(), actor
    ).messages[0].cursor
    assert message.id is not None

    with pytest.raises(ApiProblem) as caught:
        service.list_context_messages(
            context.id, MessageQuery(before=cursor, after=cursor), actor
        )

    assert caught.value.status_code == 422


# --- what a message may be --------------------------------------------------


def test_a_member_posts_text_and_gets_it_back_with_their_name_on_it(
    postgres_session: Session,
):
    context, owner, _ = _group(postgres_session)

    posted = _service(postgres_session).post_context_message(
        context.id,
        MessageCreateRequest(kind="text", body="7h quán cũ nhé"),
        _actor(owner.id, context.id),
    )

    assert posted.kind == "text"
    assert posted.body == "7h quán cũ nhé"
    # Authorship comes from the actor, never from the request body: otherwise
    # one member can put words in another member's mouth.
    assert posted.author_id == owner.id


def test_an_ai_card_keeps_its_payload_and_needs_no_human_author(
    postgres_session: Session,
):
    """The card the AI produces is structured, not a paragraph. Flattening it
    to text now means re-parsing prose later to render a button."""
    context, _, _ = _group(postgres_session)
    repository = SqlAlchemyApiRepository(postgres_session)
    card = {
        "type": "place_suggestion",
        "places": [{"name": "Bún chả Hương Liên", "price_vnd": 60000}],
    }

    record = repository.create_message(
        context_id=context.id,
        author_id=None,
        kind="ai_card",
        body=None,
        image_url=None,
        card=card,
        now=NOW,
    )
    postgres_session.expire_all()
    stored = postgres_session.get(Message, record.id)

    assert stored.card == card
    assert stored.author_id is None


def test_the_database_refuses_a_text_message_with_no_text(postgres_session: Session):
    context, owner, _ = _group(postgres_session)

    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(
                Message(
                    id=uuid.uuid4(),
                    context_id=context.id,
                    author_id=owner.id,
                    kind=MessageKind.TEXT,
                    created_at=NOW,
                )
            )
            postgres_session.flush()


def test_the_database_refuses_an_image_message_with_no_image(
    postgres_session: Session,
):
    context, owner, _ = _group(postgres_session)

    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(
                Message(
                    id=uuid.uuid4(),
                    context_id=context.id,
                    author_id=owner.id,
                    kind=MessageKind.IMAGE,
                    body="ảnh bill",
                    created_at=NOW,
                )
            )
            postgres_session.flush()


def test_the_database_refuses_a_human_message_with_no_author(
    postgres_session: Session,
):
    """Only a card the system produced may be unsigned. An anonymous human
    message is an attribution hole in a screen people read as a conversation."""
    context, _, _ = _group(postgres_session)

    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(
                Message(
                    id=uuid.uuid4(),
                    context_id=context.id,
                    author_id=None,
                    kind=MessageKind.TEXT,
                    body="ai gửi cái này?",
                    created_at=NOW,
                )
            )
            postgres_session.flush()


def test_the_database_refuses_a_message_in_a_group_that_does_not_exist(
    postgres_session: Session,
):
    """`context_id` columns in this schema used to be plain UUIDs pointing at
    nothing, so any random id was a valid group."""
    owner = _person(postgres_session, "Nam")

    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(
                Message(
                    id=uuid.uuid4(),
                    context_id=uuid.uuid4(),
                    author_id=owner.id,
                    kind=MessageKind.TEXT,
                    body="gửi vào hư không",
                    created_at=NOW,
                )
            )
            postgres_session.flush()
