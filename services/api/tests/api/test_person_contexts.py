"""`GET /people/me/contexts` and `PUT /contexts/{id}/read-mark` against the fake.

What this layer proves: the service assembles a conversation list from the
roster and the feed, excludes groups the person left, keeps invitations with
their `membership_id`, counts only other people's messages as unread, and never
moves a read mark backwards. What it does not prove: the four SQL queries behind
the real adapter -- `tests/postgres/test_person_contexts_postgres.py` does.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.api.repository import ContextRecord, MessageRecord, PersonRecord

from .helpers import actor_headers

# Letters interleaved on purpose: the repo guard reads nine consecutive digits
# (hyphens allowed) as an account number and blocks the commit.
ME = uuid.UUID("aa00aa00-0a0a-4a0a-8a0a-0a0a0a0a0aa0")
OTHER = uuid.UUID("bb00bb00-0b0b-4b0b-8b0b-0b0b0b0b0bb0")
STRANGER = uuid.UUID("cc00cc00-0c0c-4c0c-8c0c-0c0c0c0c0cc0")
A = uuid.UUID("a1a1a1a1-0a0a-4a0a-8a0a-0a0a0a0a0a01")
B = uuid.UUID("b2b2b2b2-0b0b-4b0b-8b0b-0b0b0b0b0b02")
C = uuid.UUID("c3c3c3c3-0c0c-4c0c-8c0c-0c0c0c0c0c03")
T0 = datetime(2030, 8, 27, 12, tzinfo=UTC)


def _seed_world(repository):
    for pid, name in ((ME, "Tôi"), (OTHER, "Bình"), (STRANGER, "Người lạ")):
        repository.people[pid] = PersonRecord(id=pid, display_name=name, created_at=T0)
    for cid, name in ((A, "Hội đi Đà Lạt"), (B, "Nhà 4 người"), (C, "Nhóm cũ")):
        repository.contexts[cid] = ContextRecord(
            id=cid, display_name=name, created_by_id=OTHER, created_at=T0
        )
    repository.active_memberships |= {(A, ME), (A, OTHER), (B, OTHER), (C, OTHER)}
    repository.invited_memberships.add((B, ME))
    repository.left_memberships.add((C, ME))


def _say(repository, context_id, author_id, body, minutes):
    record = MessageRecord(
        id=uuid.uuid4(),
        context_id=context_id,
        author_id=author_id,
        kind="text",
        body=body,
        image_url=None,
        card=None,
        created_at=T0 + timedelta(minutes=minutes),
    )
    repository.messages[record.id] = record
    return record


def test_lists_active_and_invited_groups_but_not_the_one_left(client, repository):
    _seed_world(repository)

    response = client.get("/people/me/contexts", headers=actor_headers(actor_id=ME))

    assert response.status_code == 200, response.text
    rows = {row["id"]: row for row in response.json()["contexts"]}
    assert set(rows) == {str(A), str(B)}, "nhóm đã rời không phải một hội thoại"
    assert rows[str(A)]["my_state"] == "active"
    assert rows[str(A)]["member_count"] == 2
    assert rows[str(B)]["my_state"] == "invited"
    assert rows[str(B)]["member_count"] == 1, "người được mời chưa đếm là thành viên"
    assert uuid.UUID(rows[str(B)]["membership_id"]), "invitee phải biết id để tự đồng ý"
    assert rows[str(A)]["last_message"] is None
    assert rows[str(A)]["unread_count"] == 0


def test_unread_counts_only_other_peoples_messages_and_the_mark_never_goes_back(
    client, repository
):
    _seed_world(repository)
    first = _say(repository, A, OTHER, "Cuối tuần đi Đà Lạt nhé", 1)
    _say(repository, A, ME, "Ok!", 2)
    newest = _say(repository, A, OTHER, "Mình có quán bánh căn view đẹp", 3)

    listed = client.get("/people/me/contexts", headers=actor_headers(actor_id=ME))
    row = listed.json()["contexts"][0]
    assert row["id"] == str(A)
    assert row["unread_count"] == 2, "tin của chính mình không bao giờ là chưa đọc"
    assert row["last_message"]["preview"] == "Mình có quán bánh căn view đẹp"
    assert row["last_message"]["author_display_name"] == "Bình"

    marked = client.put(
        f"/contexts/{A}/read-mark",
        json={"message_id": str(newest.id)},
        headers=actor_headers(actor_id=ME),
    )
    assert marked.status_code == 200, marked.text
    assert marked.json()["unread_count"] == 0
    assert marked.json()["last_read_message_id"] == str(newest.id)

    # A stale client replays an older position: nothing un-reads.
    older = client.put(
        f"/contexts/{A}/read-mark",
        json={"message_id": str(first.id)},
        headers=actor_headers(actor_id=ME),
    )
    assert older.status_code == 200, older.text
    assert older.json()["last_read_message_id"] == str(newest.id)
    assert older.json()["unread_count"] == 0

    relisted = client.get("/people/me/contexts", headers=actor_headers(actor_id=ME))
    assert relisted.json()["contexts"][0]["unread_count"] == 0


def test_a_message_from_another_group_cannot_mark_this_one(client, repository):
    _seed_world(repository)
    elsewhere = _say(repository, B, OTHER, "tin của nhóm khác", 1)

    response = client.put(
        f"/contexts/{A}/read-mark",
        json={"message_id": str(elsewhere.id)},
        headers=actor_headers(actor_id=ME),
    )
    # 404, not 403: this door must not confirm the id exists somewhere else.
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "message_not_found"


def test_a_stranger_cannot_mark_a_group_they_are_not_in(client, repository):
    _seed_world(repository)
    message = _say(repository, A, OTHER, "riêng tư", 1)

    response = client.put(
        f"/contexts/{A}/read-mark",
        json={"message_id": str(message.id)},
        headers=actor_headers(actor_id=STRANGER),
    )
    assert response.status_code == 403, response.text


def test_the_conversation_list_orders_by_newest_message_then_name(client, repository):
    _seed_world(repository)
    repository.active_memberships.add((B, ME))
    repository.invited_memberships.discard((B, ME))
    _say(repository, B, OTHER, "mới hơn", 5)
    _say(repository, A, OTHER, "cũ hơn", 1)

    ids = [
        row["id"]
        for row in client.get(
            "/people/me/contexts", headers=actor_headers(actor_id=ME)
        ).json()["contexts"]
    ]
    assert ids == [str(B), str(A)]
