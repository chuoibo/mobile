"""Thả tim (F40) và bình luận (F41) trên tường kỷ niệm, PostgreSQL thật, HTTP thật.

Mockup `product/features/05-ky-niem-cua-nhom.png` vẽ dưới mỗi bài một hàng
"❤️ 18 · 💬 6", một bình luận hiện sẵn, và ô "Viết bình luận…". Bốn tính chất
đứng sau hàng đó, và **cả bốn đều vô hình với fake repository**:

1. **Người viết là người GỌI, không phải thân request.** Route thả tim không
   nhận body nào cả, và body bình luận có đúng một field `body`. Một request
   khai `author_id`/`person_id` bị `extra="forbid"` chặn ở 422 — nghĩa là cái
   sai đó *không đánh vần được*, chứ không phải "được nhận rồi bỏ qua".
2. **Chỉ thành viên ACTIVE**, hỏi DATABASE qua `repository.is_member`, không
   đọc `actor.context_ids` (lỗ #253). Người đã rời (LEFT) và người mới được
   mời (INVITED) đều có hàng membership, và không ai trong hai người có hàng
   ACTIVE. Cả hai bị chặn ở 403.
3. **Một người một tim, do INDEX giữ.** `uq_memory_reactions_person` là chỗ
   luật sống. Gỡ index ra thì `test_the_same_person_cannot_react_twice` ĐỎ, và
   `test_the_index_itself_refuses_a_duplicate_row` chứng minh luật nằm trong
   schema chứ không phải trong một câu `if` của service.
4. **Nội dung bình luận là dữ liệu riêng tư của nhóm.** Nó không lên trang
   khách — và trang khách là bearer capability nằm trong tay người NGOÀI nhóm,
   đúng đường mà lỗ B của #254 đã rò tên đi. `test_a_group_comment_never_reaches
   _the_guest_page` dựng cả vòng đời tiền thật rồi mở `/g/{token}` bằng chính
   route đó, và tìm chuỗi bình luận trong HTML trả về.

Còn một tính chất thứ năm không nằm trong nghiệm thu nhưng đã suýt là bug thật:
đếm tim và đếm bình luận bằng HAI câu group-by riêng, không bằng hai outer join
lên cùng một cha. Hai join nhân hàng với nhau — 3 tim × 2 bình luận ra 6 của cả
hai — và con số 6 đọc như một con số hợp lý chứ không như một tai nạn.
`test_hearts_and_comments_do_not_multiply_each_other` ghim chỗ đó.

Dùng `flush`, không `commit`: `postgres_session` rollback mỗi ca và schema dùng
chung với các ca đếm hàng trong thư mục này.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import anyio
import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import (
    Context,
    MembershipState,
    Memory,
    MemoryComment,
    MemoryReaction,
    Person,
)

from .test_group_memories_postgres import (
    _context,
    _group,
    _headers,
    _http,
    _join,
    _person,
    _remember,
)
from .test_repository_postgres import GUEST_TOKEN, NOW, _persist_lifecycle

pytestmark = pytest.mark.postgres

COMMENT = "Ảnh này đẹp quá, hôm đó trời trong ghê"


# --------------------------------------------------------------------------
# Exchanges
# --------------------------------------------------------------------------


def _call(app, method: str, path: str, person_id: uuid.UUID, json=None):
    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(
                method, path, headers=_headers(person_id), json=json
            )

    return anyio.run(exchange)


def _react(app, context_id, memory_id, person_id):
    return _call(
        app,
        "POST",
        f"/contexts/{context_id}/memories/{memory_id}/reactions",
        person_id,
    )


def _unreact(app, context_id, memory_id, person_id):
    return _call(
        app,
        "DELETE",
        f"/contexts/{context_id}/memories/{memory_id}/reactions",
        person_id,
    )


def _comment(app, context_id, memory_id, person_id, body=COMMENT, payload=None):
    return _call(
        app,
        "POST",
        f"/contexts/{context_id}/memories/{memory_id}/comments",
        person_id,
        json={"body": body} if payload is None else payload,
    )


def _read_comments(app, context_id, memory_id, person_id):
    return _call(
        app,
        "GET",
        f"/contexts/{context_id}/memories/{memory_id}/comments",
        person_id,
    )


def _feed(app, context_id, person_id):
    return _call(app, "GET", f"/contexts/{context_id}/memories", person_id)


def _scene(session: Session, monkeypatch):
    """A group, one member, one outsider, and one photograph on the wall."""
    context, owner, outsider = _group(session)
    app = _http(session, monkeypatch)
    memory = _remember(session, context, owner)
    return app, context, owner, outsider, memory


# --------------------------------------------------------------------------
# 1 -- the writer is the caller
# --------------------------------------------------------------------------


def test_a_member_leaves_a_heart_and_it_is_their_own(postgres_session, monkeypatch):
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)

    response = _react(app, context.id, memory.id, owner.id)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["memory_id"] == str(memory.id)
    assert body["person_id"] == str(owner.id)
    assert body["reaction_count"] == 1

    row = postgres_session.scalars(select(MemoryReaction)).one()
    assert row.person_id == owner.id


def test_a_body_naming_another_person_changes_nothing(postgres_session, monkeypatch):
    """The route declares no body, so a named person has nowhere to land.

    Six money routes leaked because "the caller has permission" was allowed to
    stand in for "the caller may write about the person the body names". Here
    the whole class is unreachable by construction rather than by a check: the
    handler takes no request model, so `person_id` is not a field that is read
    and then ignored -- it is a field that does not exist. The row can only
    ever carry the actor's id.

    Written the same way `test_a_body_offering_coordinates_changes_nothing`
    is: send the dangerous body, then look at what landed in the table.
    """
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    victim = _person(postgres_session, "Người bị mượn tên")
    _join(postgres_session, context, victim)

    response = _call(
        app,
        "POST",
        f"/contexts/{context.id}/memories/{memory.id}/reactions",
        owner.id,
        json={"person_id": str(victim.id)},
    )

    assert response.status_code == 201, response.text
    assert response.json()["person_id"] == str(owner.id)
    row = postgres_session.scalars(select(MemoryReaction)).one()
    assert row.person_id == owner.id, "the body named the writer"
    assert row.person_id != victim.id


def test_a_comment_cannot_name_its_own_author(postgres_session, monkeypatch):
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    victim = _person(postgres_session, "Người bị mượn tên")
    _join(postgres_session, context, victim)

    response = _comment(
        app,
        context.id,
        memory.id,
        owner.id,
        payload={"body": COMMENT, "author_id": str(victim.id)},
    )

    assert response.status_code == 422, response.text
    assert postgres_session.scalars(select(MemoryComment)).all() == []


def test_a_comment_is_written_under_the_callers_name(postgres_session, monkeypatch):
    """The commenter is deliberately NOT the person who posted the photograph.

    Written the obvious way -- the owner commenting on the owner's own memory
    -- this test passes just as happily against a service that takes the
    author from `memory.author_id`. The two ids are the same, so the bug and
    the fix are the same colour. The mutation table caught exactly that: row 7
    went red somewhere else while this test stayed green.

    So `friend` comments on `owner`'s photograph, and the two ids differ.
    """
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    friend = _person(postgres_session, "Quyên")
    _join(postgres_session, context, friend)
    assert memory.author_id == owner.id
    assert friend.id != owner.id

    response = _comment(app, context.id, memory.id, friend.id)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["author_id"] == str(friend.id), "the comment took the photo's author"
    assert body["display_name"] == "Quyên"
    assert body["body"] == COMMENT

    row = postgres_session.scalars(select(MemoryComment)).one()
    assert row.author_id == friend.id
    assert row.author_id != memory.author_id


def test_a_blank_comment_is_refused(postgres_session, monkeypatch):
    """An empty sentence is not a comment, and the database says so too."""
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)

    response = _comment(app, context.id, memory.id, owner.id, body="")

    assert response.status_code == 422, response.text
    assert postgres_session.scalars(select(MemoryComment)).all() == []


def test_the_check_constraint_itself_refuses_a_blank_body(
    postgres_session, monkeypatch
):
    """Proved against the migrated schema, not against the pydantic model."""
    _app, _ctx, _owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    author = postgres_session.scalars(select(Person)).first()

    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(
                MemoryComment(memory_id=memory.id, author_id=author.id, body="")
            )
            postgres_session.flush()


# --------------------------------------------------------------------------
# 2 -- ACTIVE membership, asked of the database
# --------------------------------------------------------------------------


def test_an_outsider_cannot_leave_a_heart(postgres_session, monkeypatch):
    app, context, _owner, outsider, memory = _scene(postgres_session, monkeypatch)

    response = _react(app, context.id, memory.id, outsider.id)

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "is_group_member"
    assert postgres_session.scalars(select(MemoryReaction)).all() == []


def test_an_outsider_cannot_comment(postgres_session, monkeypatch):
    app, context, _owner, outsider, memory = _scene(postgres_session, monkeypatch)

    response = _comment(app, context.id, memory.id, outsider.id)

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "is_group_member"
    assert postgres_session.scalars(select(MemoryComment)).all() == []


def test_an_outsider_cannot_read_the_comments(postgres_session, monkeypatch):
    app, context, owner, outsider, memory = _scene(postgres_session, monkeypatch)
    assert _comment(app, context.id, memory.id, owner.id).status_code == 201

    response = _read_comments(app, context.id, memory.id, outsider.id)

    assert response.status_code == 403, response.text
    assert COMMENT not in response.text


def test_an_invited_member_cannot_react_or_comment(postgres_session, monkeypatch):
    """Relax the ACTIVE requirement and this test goes red.

    An INVITED row is what redeeming an invite link produces. `is_group_member`
    is satisfied only by an ACTIVE row -- if it were ever loosened to "has a
    membership row", whoever just opened a link would be writing onto the
    group's permanent wall before anybody accepted them.
    """
    app, context, _owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    newcomer = _person(postgres_session, "Người vừa bấm link")
    _join(postgres_session, context, newcomer, state=MembershipState.INVITED)

    heart = _react(app, context.id, memory.id, newcomer.id)
    said = _comment(app, context.id, memory.id, newcomer.id)
    read = _read_comments(app, context.id, memory.id, newcomer.id)

    assert heart.status_code == 403, heart.text
    assert said.status_code == 403, said.text
    assert read.status_code == 403, read.text
    assert postgres_session.scalars(select(MemoryReaction)).all() == []
    assert postgres_session.scalars(select(MemoryComment)).all() == []


def test_a_departed_member_cannot_react_or_comment(postgres_session, monkeypatch):
    """Somebody who left keeps no way to write onto the wall they left."""
    app, context, _owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    gone = _person(postgres_session, "Đã rời nhóm")
    _join(
        postgres_session,
        context,
        gone,
        state=MembershipState.LEFT,
        left_at=NOW,
    )

    heart = _react(app, context.id, memory.id, gone.id)
    said = _comment(app, context.id, memory.id, gone.id)
    read = _read_comments(app, context.id, memory.id, gone.id)

    assert heart.status_code == 403, heart.text
    assert said.status_code == 403, said.text
    assert read.status_code == 403, read.text
    assert postgres_session.scalars(select(MemoryReaction)).all() == []
    assert postgres_session.scalars(select(MemoryComment)).all() == []


def test_a_declared_role_is_not_a_key(postgres_session, monkeypatch):
    """`_headers` sends `member,group_admin` for everyone, including outsiders.

    So every 403 above is already proof that the role string is not what
    decides. This test says it in one place so the reason cannot be lost if
    `_headers` is ever changed.
    """
    app, context, _owner, outsider, memory = _scene(postgres_session, monkeypatch)
    assert "group_admin" in _headers(outsider.id)["X-Actor-Roles"]

    assert _react(app, context.id, memory.id, outsider.id).status_code == 403


def test_membership_is_read_from_the_database_not_from_the_header(
    postgres_session, monkeypatch
):
    """An `X-Actor-Contexts` claim naming the group changes nothing.

    This is lỗ #253 written as a test: reading `actor.context_ids` instead of
    asking the repository turns a header into a membership card.
    """
    app, context, _owner, outsider, memory = _scene(postgres_session, monkeypatch)

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.post(
                f"/contexts/{context.id}/memories/{memory.id}/reactions",
                headers={
                    "X-Actor-ID": str(outsider.id),
                    "X-Actor-Roles": "member,group_admin",
                    "X-Actor-Contexts": str(context.id),
                },
            )

    response = anyio.run(exchange)

    assert response.status_code == 403, response.text
    assert postgres_session.scalars(select(MemoryReaction)).all() == []


# --------------------------------------------------------------------------
# 3 -- one person, one heart, held by the index
# --------------------------------------------------------------------------


def test_the_same_person_cannot_react_twice(postgres_session, monkeypatch):
    """Drop `uq_memory_reactions_person` and this test goes red.

    That is the point of it. The service never asks "have you already liked
    this?" -- it writes and lets the index answer, so two taps in the same
    instant cannot both win.
    """
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)

    first = _react(app, context.id, memory.id, owner.id)
    second = _react(app, context.id, memory.id, owner.id)

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "already_reacted"

    rows = postgres_session.scalars(
        select(MemoryReaction).where(MemoryReaction.memory_id == memory.id)
    ).all()
    assert len(rows) == 1

    feed = _feed(app, context.id, owner.id).json()["memories"]
    assert feed[0]["reaction_count"] == 1


def test_the_index_itself_refuses_a_duplicate_row(postgres_session, monkeypatch):
    """The rule is in the schema, proved without going through the API.

    If this passes while `test_the_same_person_cannot_react_twice` fails, the
    service is catching something the database never raised.
    """
    _app, _ctx, owner, _outsider, memory = _scene(postgres_session, monkeypatch)

    postgres_session.add(MemoryReaction(memory_id=memory.id, person_id=owner.id))
    postgres_session.flush()

    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(
                MemoryReaction(memory_id=memory.id, person_id=owner.id)
            )
            postgres_session.flush()


def test_two_members_may_each_leave_their_own_heart(postgres_session, monkeypatch):
    """The rule is per person, not per memory -- a whole group can like a photo."""
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    friend = _person(postgres_session, "Quyên")
    _join(postgres_session, context, friend)

    assert _react(app, context.id, memory.id, owner.id).status_code == 201
    second = _react(app, context.id, memory.id, friend.id)

    assert second.status_code == 201, second.text
    assert second.json()["reaction_count"] == 2


def test_one_person_may_like_several_memories(postgres_session, monkeypatch):
    """The rule is per memory, not per person -- a wall has many photographs."""
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    other = _remember(postgres_session, context, owner, created_at=NOW)

    assert _react(app, context.id, memory.id, owner.id).status_code == 201
    assert _react(app, context.id, other.id, owner.id).status_code == 201


def test_a_member_can_take_their_heart_back(postgres_session, monkeypatch):
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    assert _react(app, context.id, memory.id, owner.id).status_code == 201

    removed = _unreact(app, context.id, memory.id, owner.id)

    assert removed.status_code == 204, removed.text
    assert postgres_session.scalars(select(MemoryReaction)).all() == []
    # And the heart can be left again afterwards -- taking it back is not a
    # one-way door.
    assert _react(app, context.id, memory.id, owner.id).status_code == 201


def test_taking_back_a_heart_that_was_never_left_is_a_404(
    postgres_session, monkeypatch
):
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)

    response = _unreact(app, context.id, memory.id, owner.id)

    assert response.status_code == 404, response.text
    assert response.json()["code"] == "reaction_not_found"


def test_one_member_cannot_remove_another_members_heart(postgres_session, monkeypatch):
    """`DELETE` names no person, so it can only ever reach the actor's own row."""
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    friend = _person(postgres_session, "Quyên")
    _join(postgres_session, context, friend)
    assert _react(app, context.id, memory.id, owner.id).status_code == 201

    response = _unreact(app, context.id, memory.id, friend.id)

    assert response.status_code == 404, response.text
    surviving = postgres_session.scalars(select(MemoryReaction)).one()
    assert surviving.person_id == owner.id


# --------------------------------------------------------------------------
# The counts the mockup draws
# --------------------------------------------------------------------------


def test_the_feed_carries_both_totals(postgres_session, monkeypatch):
    """ "❤️ 18 · 💬 6" has to come from somewhere, and it is not an N+1."""
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    friend = _person(postgres_session, "Quyên")
    _join(postgres_session, context, friend)

    assert _react(app, context.id, memory.id, owner.id).status_code == 201
    assert _react(app, context.id, memory.id, friend.id).status_code == 201
    assert _comment(app, context.id, memory.id, owner.id).status_code == 201

    row = _feed(app, context.id, owner.id).json()["memories"][0]

    assert row["reaction_count"] == 2
    assert row["comment_count"] == 1


def test_hearts_and_comments_do_not_multiply_each_other(postgres_session, monkeypatch):
    """Two outer joins onto one parent multiply the children together.

    Three hearts and two comments would both be reported as six, and six is a
    plausible-looking number rather than an obvious crash. Counting each side
    with its own grouped query cannot produce it. Distinct totals on purpose:
    equal ones would pass under the bug.
    """
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    people = [owner]
    for name in ("Quyên", "Nam"):
        friend = _person(postgres_session, name)
        _join(postgres_session, context, friend)
        people.append(friend)

    for person in people:
        assert _react(app, context.id, memory.id, person.id).status_code == 201
    for person in people[:2]:
        assert _comment(app, context.id, memory.id, person.id).status_code == 201

    row = _feed(app, context.id, owner.id).json()["memories"][0]

    assert row["reaction_count"] == 3
    assert row["comment_count"] == 2


def test_viewer_has_reacted_is_a_fact_about_the_reader(postgres_session, monkeypatch):
    """Two members read the same wall and get two different answers."""
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    friend = _person(postgres_session, "Quyên")
    _join(postgres_session, context, friend)
    assert _react(app, context.id, memory.id, owner.id).status_code == 201

    mine = _feed(app, context.id, owner.id).json()["memories"][0]
    theirs = _feed(app, context.id, friend.id).json()["memories"][0]

    assert mine["viewer_has_reacted"] is True
    assert theirs["viewer_has_reacted"] is False
    # Same underlying row, so the total is the same for both readers. Only the
    # "did I" answer moves.
    assert mine["reaction_count"] == theirs["reaction_count"] == 1


def test_a_fresh_memory_reports_zero_and_not_null(postgres_session, monkeypatch):
    app, context, owner, _outsider, _memory = _scene(postgres_session, monkeypatch)

    row = _feed(app, context.id, owner.id).json()["memories"][0]

    assert row["reaction_count"] == 0
    assert row["comment_count"] == 0
    assert row["viewer_has_reacted"] is False


def test_the_comments_come_back_oldest_first(postgres_session, monkeypatch):
    """A conversation under a photograph runs forward, unlike the feed above it."""
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    friend = _person(postgres_session, "Quyên")
    _join(postgres_session, context, friend)

    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    assert (
        _comment(app, context.id, memory.id, owner.id, body="Đi lần nữa đi").status_code
        == 201
    )
    monkeypatch.setattr("app.api.service._now", lambda: NOW + timedelta(minutes=5))
    assert (
        _comment(app, context.id, memory.id, friend.id, body="Ừ, cuối tuần").status_code
        == 201
    )

    comments = _read_comments(app, context.id, memory.id, owner.id).json()["comments"]

    assert [row["body"] for row in comments] == ["Đi lần nữa đi", "Ừ, cuối tuần"]
    assert [row["display_name"] for row in comments] == ["Minh Anh", "Quyên"]


# --------------------------------------------------------------------------
# Cross-group, and the id oracle
# --------------------------------------------------------------------------


def test_another_groups_memory_is_not_reachable_through_this_context(
    postgres_session, monkeypatch
):
    """A member of A naming B's memory under A's context id gets nothing.

    `get_context_memory` filters on both ids. Dropping the `context_id`
    predicate makes this test red, and would make every memory in the product
    writable by any member of any group who learned its id.
    """
    app, context, owner, _outsider, _memory = _scene(postgres_session, monkeypatch)
    stranger = _person(postgres_session, "Nhóm khác")
    other_context = _context(postgres_session, stranger, "Team khác")
    _join(postgres_session, other_context, stranger)
    theirs = _remember(postgres_session, other_context, stranger)

    heart = _react(app, context.id, theirs.id, owner.id)
    said = _comment(app, context.id, theirs.id, owner.id)

    assert heart.status_code == 404, heart.text
    assert said.status_code == 404, said.text
    assert postgres_session.scalars(select(MemoryReaction)).all() == []
    assert postgres_session.scalars(select(MemoryComment)).all() == []


def test_an_outsider_learns_nothing_about_which_ids_exist(
    postgres_session, monkeypatch
):
    """403 for a real memory and 403 for an invented one -- the same answer.

    Swap the two lines of `_memory_of_member` so the lookup runs before the
    permission check and this goes red: the pair of status codes would become
    an oracle for walking memory ids inside groups the caller is not in.
    """
    app, context, _owner, outsider, memory = _scene(postgres_session, monkeypatch)
    invented = uuid.uuid4()

    real = _react(app, context.id, memory.id, outsider.id)
    fake = _react(app, context.id, invented, outsider.id)

    assert real.status_code == fake.status_code == 403
    assert real.json() == fake.json()


def test_a_member_asking_for_an_unknown_memory_gets_404_without_an_echo(
    postgres_session, monkeypatch
):
    app, context, owner, _outsider, _memory = _scene(postgres_session, monkeypatch)
    unknown = uuid.uuid4()

    response = _react(app, context.id, unknown, owner.id)

    assert response.status_code == 404, response.text
    assert response.json()["code"] == "memory_not_found"
    assert str(unknown) not in response.text


def test_a_comment_from_another_group_never_appears(postgres_session, monkeypatch):
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    stranger = _person(postgres_session, "Nhóm khác")
    other_context = _context(postgres_session, stranger, "Team khác")
    _join(postgres_session, other_context, stranger)
    theirs = _remember(postgres_session, other_context, stranger)
    assert (
        _comment(
            app, other_context.id, theirs.id, stranger.id, body="Bí mật của nhóm khác"
        ).status_code
        == 201
    )
    assert _comment(app, context.id, memory.id, owner.id).status_code == 201

    mine = _read_comments(app, context.id, memory.id, owner.id)

    assert [row["body"] for row in mine.json()["comments"]] == [COMMENT]
    assert "Bí mật của nhóm khác" not in mine.text


# --------------------------------------------------------------------------
# 4 -- the comment body is group-private, and the guest page is the boundary
# --------------------------------------------------------------------------


def test_a_group_comment_never_reaches_the_guest_page(
    postgres_session, monkeypatch: pytest.MonkeyPatch
):
    """The whole money lifecycle, a comment on the same group's wall, and `/g/`.

    The guest link is a bearer capability held by somebody standing outside
    the group -- that is exactly the door lỗ B of #254 leaked a name through.
    So this does not assert on a view model: it asks the real route for the
    real page and looks for the sentence in the HTML that comes back.

    `build_guest_view` is a whitelist and has no slot for a comment, which is
    why this passes. Adding "recent group activity" to that envelope, however
    reasonable it looked in a ticket, turns it red.
    """
    secret = "Bình luận riêng của nhóm — không được lên trang khách"
    state = _persist_lifecycle(postgres_session)

    # `_persist_lifecycle` writes no `people` or `contexts` rows -- it does not
    # need them, because `expenses.context_id` has no foreign key. `memories`
    # does, so the group behind that lifecycle gets built here.
    author = Person(id=state.sender_id, display_name="Thành viên nhóm")
    postgres_session.add(author)
    postgres_session.flush()
    postgres_session.add(
        Context(
            id=state.context_id,
            display_name="Nhóm đi ăn",
            created_by_id=state.sender_id,
        )
    )
    postgres_session.flush()
    memory = Memory(
        id=uuid.uuid4(),
        context_id=state.context_id,
        author_id=state.sender_id,
        image_url=f"/contexts/{state.context_id}/photos/{uuid.uuid4()}",
        caption="Bữa đó",
        created_at=NOW,
    )
    postgres_session.add(memory)
    postgres_session.flush()
    postgres_session.add(
        MemoryComment(
            memory_id=memory.id,
            author_id=state.sender_id,
            body=secret,
            created_at=NOW,
        )
    )
    postgres_session.add(
        MemoryReaction(memory_id=memory.id, person_id=state.sender_id, created_at=NOW)
    )
    postgres_session.flush()

    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW + timedelta(minutes=10))
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(
        postgres_session
    )

    async def get_page():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(f"/g/{GUEST_TOKEN}")

    response = anyio.run(get_page)

    # The page has to have rendered for its silence to mean anything. A 500
    # contains no comment either.
    assert response.status_code == 200, response.text
    assert "Techcombank" in response.text, "guest page did not render its envelope"

    assert secret not in response.text
    assert "Bữa đó" not in response.text
    assert str(memory.id) not in response.text
    for word in ("comment", "reaction", "bình luận", "Bình luận"):
        assert word not in response.text, f"guest page mentions {word!r}"


def test_the_comment_body_is_not_quoted_back_in_any_refusal(
    postgres_session, monkeypatch
):
    """A refusal is the part of a response that gets pasted into chats.

    Every way this write can fail must fail without repeating the sentence:
    an unknown memory, a group the caller is not in, a body too long.
    """
    app, context, _owner, outsider, memory = _scene(postgres_session, monkeypatch)
    secret = "Chuyện chỉ nhóm mới được biết"

    refusals = [
        _comment(app, context.id, memory.id, outsider.id, body=secret),
        _comment(app, context.id, uuid.uuid4(), outsider.id, body=secret),
        _comment(app, context.id, memory.id, outsider.id, body=secret * 200),
    ]

    for response in refusals:
        assert response.status_code in {403, 404, 422}, response.text
        assert secret not in response.text, response.text


def test_the_comment_body_never_reaches_the_logs(postgres_session, monkeypatch, caplog):
    """Group-private text at the rank of a phone number stays out of the log."""
    import logging

    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    secret = "Câu này không được xuất hiện trong log"

    with caplog.at_level(logging.DEBUG):
        assert (
            _comment(app, context.id, memory.id, owner.id, body=secret).status_code
            == 201
        )
        assert _read_comments(app, context.id, memory.id, owner.id).status_code == 200

    assert secret not in caplog.text


# --------------------------------------------------------------------------
# What a deleted memory takes with it
# --------------------------------------------------------------------------


def test_deleting_a_memory_takes_its_hearts_and_comments(postgres_session, monkeypatch):
    """`ON DELETE CASCADE`, pinned so it cannot change in silence.

    A heart on a photograph that no longer exists is a count attached to
    nothing, and a comment under it is group-private text with no owner left.
    """
    app, context, owner, _outsider, memory = _scene(postgres_session, monkeypatch)
    survivor = _remember(postgres_session, context, owner)
    assert _react(app, context.id, memory.id, owner.id).status_code == 201
    assert _comment(app, context.id, memory.id, owner.id).status_code == 201
    assert _react(app, context.id, survivor.id, owner.id).status_code == 201

    postgres_session.delete(postgres_session.get(Memory, memory.id))
    postgres_session.flush()

    reactions = postgres_session.scalars(select(MemoryReaction)).all()
    assert len(reactions) == 1
    assert reactions[0].memory_id == survivor.id
    assert postgres_session.scalars(select(MemoryComment)).all() == []


def test_the_schema_holds_the_cascade_and_the_unique_index(postgres_session):
    """Read off the migrated database, not off the model file."""
    cascades = set(
        postgres_session.execute(
            text(
                "SELECT c.conname, c.confdeltype FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "WHERE t.relname IN ('memory_reactions', 'memory_comments') "
                "AND c.contype = 'f'"
            )
        ).all()
    )
    by_name = dict(cascades)
    assert by_name["fk_memory_reactions_memory"] == "c", "memory FK must cascade"
    assert by_name["fk_memory_comments_memory"] == "c", "memory FK must cascade"
    # The person FKs deliberately do not cascade: a person leaving is not a
    # reason to rewrite what a group remembers.
    assert by_name["fk_memory_reactions_person"] == "a"
    assert by_name["fk_memory_comments_author"] == "a"

    unique = postgres_session.scalars(
        text(
            "SELECT conname FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "WHERE t.relname = 'memory_reactions' AND c.contype = 'u'"
        )
    ).all()
    assert "uq_memory_reactions_person" in unique
