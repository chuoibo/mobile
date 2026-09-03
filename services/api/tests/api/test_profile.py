"""`GET/PATCH /people/me`, `GET /people/{id}` and saved places against the fake.

What this layer proves: the service assembles the profile from five sources and
never from the request; a partial update touches only the fields sent; the
public view is gated by relation (self, friend, groupmate) and an id nobody may
see answers the SAME 403 whether or not it exists; bookmarks are idempotent and
refuse a key the catalogue does not know. What it does not prove: the COUNT
queries, the unique index and the row lock -- `tests/postgres/test_profile_postgres.py`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.api.repository import (
    AccountIdentityRecord,
    ContextRecord,
    MemoryRecord,
    PersonRecord,
)
from app.places.catalog import PLACES

from .helpers import actor_headers

# Letters interleaved on purpose: the repo guard reads nine consecutive digits
# (hyphens allowed) as an account number and blocks the commit.
ME = uuid.UUID("aa00aa00-0a0a-4a0a-8a0a-0a0a0a0a0aa0")
FRIEND = uuid.UUID("bb00bb00-0b0b-4b0b-8b0b-0b0b0b0b0bb0")
MATE = uuid.UUID("cc00cc00-0c0c-4c0c-8c0c-0c0c0c0c0cc0")
STRANGER = uuid.UUID("dd00dd00-0d0d-4d0d-8d0d-0d0d0d0d0dd0")
A = uuid.UUID("a1a1a1a1-0a0a-4a0a-8a0a-0a0a0a0a0a01")
LEFT = uuid.UUID("c3c3c3c3-0c0c-4c0c-8c0c-0c0c0c0c0c03")
T0 = datetime(2030, 8, 27, 12, tzinfo=UTC)
PLACE = PLACES[0]["id"]
PLACE_2 = PLACES[1]["id"]


def _seed(repository):
    for pid, name in (
        (ME, "Tôi"),
        (FRIEND, "Bạn thân"),
        (MATE, "Đồng nhóm"),
        (STRANGER, "Người lạ"),
    ):
        repository.people[pid] = PersonRecord(id=pid, display_name=name, created_at=T0)
    repository.contexts[A] = ContextRecord(
        id=A, display_name="Hội A", created_by_id=MATE, created_at=T0
    )
    repository.contexts[LEFT] = ContextRecord(
        id=LEFT, display_name="Nhóm cũ", created_by_id=MATE, created_at=T0
    )
    repository.active_memberships |= {(A, ME), (A, MATE)}
    repository.left_memberships.add((LEFT, ME))
    repository.active_memberships.add((LEFT, STRANGER))
    # One accepted edge with FRIEND (who shares no group), one pending with STRANGER.
    repository.friend_edges[uuid.uuid4()] = {
        "requester_id": FRIEND,
        "addressee_id": ME,
        "state": "accepted",
        "created_at": T0,
        "decided_at": T0,
    }
    repository.friend_edges[uuid.uuid4()] = {
        "requester_id": ME,
        "addressee_id": STRANGER,
        "state": "pending",
        "created_at": T0,
        "decided_at": None,
    }
    repository.outings_by_context[uuid.uuid4()] = A
    repository.outings_by_context[uuid.uuid4()] = LEFT
    stop_1, stop_2 = uuid.uuid4(), uuid.uuid4()
    repository.stop_checkins |= {
        (ME, stop_1),
        (ME, stop_2),
        (ME, stop_1),
        (MATE, stop_1),
    }
    for _ in range(2):
        mid = uuid.uuid4()
        repository.memories[mid] = MemoryRecord(
            id=mid,
            context_id=A,
            author_id=ME,
            kind="photo",
            image_url=None,
            caption=None,
            place_id=None,
            place_name=None,
            lat=None,
            lng=None,
            created_at=T0,
        )
    repository.account_identities[("phone", "digest-me")] = AccountIdentityRecord(
        id=uuid.uuid4(),
        person_id=ME,
        provider="phone",
        subject="digest-me",
        created_at=T0,
        last_login_at=T0,
    )


def _as(pid):
    return actor_headers(actor_id=pid)


def test_my_profile_counts_come_from_the_five_sources(client, repository):
    _seed(repository)
    response = client.get("/people/me", headers=_as(ME))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(ME) and body["display_name"] == "Tôi"
    assert body["bio"] is None and body["city"] is None
    assert body["counts"] == {
        "friends": 1,  # the pending edge is not a friend
        "contexts": 1,  # the left group is not a context
        "outings": 1,  # only outings of active contexts
        "places_checked_in": 2,  # distinct stops, not check-in rows
        "memories": 2,
    }
    assert body["login_methods"] == ["phone"]


def test_patch_touches_only_the_fields_sent_and_clears_with_empty(client, repository):
    _seed(repository)
    first = client.patch(
        "/people/me", json={"bio": "  Thích cafe sáng  "}, headers=_as(ME)
    )
    assert first.status_code == 200, first.text
    assert first.json()["bio"] == "Thích cafe sáng"
    assert first.json()["display_name"] == "Tôi", "tên không được đụng khi chỉ sửa bio"

    second = client.patch(
        "/people/me",
        json={"display_name": " Tôi Mới ", "city": "Đà Lạt"},
        headers=_as(ME),
    )
    assert second.status_code == 200, second.text
    assert second.json()["display_name"] == "Tôi Mới"
    assert second.json()["city"] == "Đà Lạt"
    assert second.json()["bio"] == "Thích cafe sáng"

    cleared = client.patch("/people/me", json={"bio": ""}, headers=_as(ME))
    assert cleared.status_code == 200
    assert cleared.json()["bio"] is None
    assert repository.people[ME].display_name == "Tôi Mới"


def test_patch_refuses_nothing_unknown_fields_and_a_blank_name(client, repository):
    _seed(repository)
    for body in ({}, {"phone": "x"}, {"display_name": "   "}, {"bio": "x" * 501}):
        response = client.patch("/people/me", json=body, headers=_as(ME))
        assert response.status_code == 422, (body, response.text)
    assert repository.people[ME].display_name == "Tôi"


def test_a_friend_and_a_groupmate_see_the_public_view_with_their_relation(
    client, repository
):
    _seed(repository)
    client.patch("/people/me", json={"bio": "Xin chào", "city": "Huế"}, headers=_as(ME))

    as_friend = client.get(f"/people/{ME}", headers=_as(FRIEND))
    assert as_friend.status_code == 200, as_friend.text
    assert as_friend.json()["relation"] == "friend"
    assert as_friend.json()["bio"] == "Xin chào" and as_friend.json()["city"] == "Huế"
    assert "counts" not in as_friend.json() and "login_methods" not in as_friend.json()

    as_mate = client.get(f"/people/{ME}", headers=_as(MATE))
    assert as_mate.status_code == 200 and as_mate.json()["relation"] == "groupmate"

    me = client.get(f"/people/{ME}", headers=_as(ME))
    assert me.status_code == 200 and me.json()["relation"] == "self"


def test_a_stranger_and_a_nonexistent_id_get_the_same_403(client, repository):
    _seed(repository)
    # A pending request is not a friendship, and a group the reader LEFT does
    # not make them a groupmate of who is still in it.
    stranger = client.get(f"/people/{ME}", headers=_as(STRANGER))
    nobody = client.get(f"/people/{uuid.uuid4()}", headers=_as(STRANGER))
    assert stranger.status_code == 403 and nobody.status_code == 403
    assert stranger.json()["code"] == "person_not_visible"
    assert stranger.json() == nobody.json(), (
        "403 phải giống nhau: route không được là oracle về id nào tồn tại"
    )


def test_saved_places_are_idempotent_and_named_from_the_catalogue(client, repository):
    _seed(repository)
    first = client.put(f"/people/me/saved-places/{PLACE}", headers=_as(ME))
    assert first.status_code == 201, first.text
    assert first.json()["name"] == PLACES[0]["name"]
    again = client.put(f"/people/me/saved-places/{PLACE}", headers=_as(ME))
    assert again.status_code == 200, "lưu lần hai là cùng một bookmark, không phải 409"
    client.put(f"/people/me/saved-places/{PLACE_2}", headers=_as(ME))

    listed = client.get("/people/me/saved-places", headers=_as(ME))
    assert listed.status_code == 200
    assert {row["place_id"] for row in listed.json()["saved"]} == {PLACE, PLACE_2}
    assert all(
        row["name"] and row["category"] and row["saved_at"]
        for row in listed.json()["saved"]
    )

    gone = client.delete(f"/people/me/saved-places/{PLACE}", headers=_as(ME))
    assert gone.status_code == 204
    gone_again = client.delete(f"/people/me/saved-places/{PLACE}", headers=_as(ME))
    assert gone_again.status_code == 204, "xoá cái không còn vẫn là «không còn»"
    assert [
        row["place_id"]
        for row in client.get("/people/me/saved-places", headers=_as(ME)).json()[
            "saved"
        ]
    ] == [PLACE_2]
    # Somebody else's bookmarks are not mine.
    assert (
        client.get("/people/me/saved-places", headers=_as(FRIEND)).json()["saved"] == []
    )


def test_a_key_the_catalogue_does_not_know_is_refused_on_put_and_delete(
    client, repository
):
    _seed(repository)
    for method in (client.put, client.delete):
        response = method("/people/me/saved-places/p-khong-co-that", headers=_as(ME))
        assert response.status_code == 404, response.text
        assert response.json()["code"] == "place_not_found"
    assert repository.saved_places == {}


def test_profile_routes_need_a_signed_in_person(client, repository):
    _seed(repository)
    assert client.get("/people/me").status_code in (401, 403)
    assert client.get(f"/people/{ME}").status_code in (401, 403)
    assert client.get("/people/me/saved-places").status_code in (401, 403)
