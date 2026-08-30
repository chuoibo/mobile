"""F42 visibility enforcement at every memory-wall HTTP read surface."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from .helpers import ADVANCER_ID, CONTEXT_ID, OTHER_ID, SENDER_ID, actor_headers

PHOTO_URL = f"/contexts/{CONTEXT_ID}/photos/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _request_social_route(client, method, memory_id, *, actor_id):
    path = f"/contexts/{CONTEXT_ID}/memories/{memory_id}"
    headers = actor_headers(actor_id=actor_id, roles="member")
    if method == "GET comments":
        return client.get(f"{path}/comments", headers=headers)
    if method == "POST comments":
        return client.post(
            f"{path}/comments", headers=headers, json={"body": "Một bình luận"}
        )
    if method == "POST reactions":
        return client.post(f"{path}/reactions", headers=headers)
    if method == "DELETE reactions":
        return client.request("DELETE", f"{path}/reactions", headers=headers)
    raise AssertionError(f"Unknown method case: {method}")


def _accept_friendship(repository, person_a, person_b):
    edge_id = repository.open_friend_request(
        requester_id=person_a,
        addressee_id=person_b,
        now=datetime(2030, 8, 27, 10, tzinfo=UTC),
    ).id
    repository.decide_friend_request(
        request_id=edge_id,
        state="accepted",
        decided_by_id=person_b,
        now=datetime(2030, 8, 27, 11, tzinfo=UTC),
    )


def test_feed_omits_a_hidden_memory_from_another_member(client, repository):
    hidden = repository.seed_memory(author_id=SENDER_ID, visibility="only_me")

    response = client.get(
        f"/contexts/{CONTEXT_ID}/memories",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member"),
    )

    assert response.status_code == 200, response.text
    assert str(hidden.id) not in {row["id"] for row in response.json()["memories"]}


@pytest.mark.parametrize(
    "method",
    ["GET comments", "POST comments", "POST reactions", "DELETE reactions"],
)
def test_hidden_memory_is_404_on_every_social_route(
    client, repository, method
):
    hidden = repository.seed_memory(author_id=SENDER_ID, visibility="only_me")
    if method == "DELETE reactions":
        repository.add_memory_reaction(
            memory_id=hidden.id,
            person_id=ADVANCER_ID,
            now=datetime(2030, 8, 27, 13, tzinfo=UTC),
        )

    response = _request_social_route(
        client, method, hidden.id, actor_id=ADVANCER_ID
    )

    assert response.status_code == 404, response.text
    assert response.json()["code"] == "memory_not_found"


@pytest.mark.parametrize("visibility", ["only_me", "friends", "group", "public"])
@pytest.mark.parametrize(
    "route",
    ["feed", "GET comments", "POST comments", "POST reactions", "DELETE reactions"],
)
def test_non_member_still_gets_403_at_every_visibility_and_route(
    client, repository, visibility, route
):
    memory = repository.seed_memory(author_id=SENDER_ID, visibility=visibility)
    if route == "DELETE reactions":
        repository.add_memory_reaction(
            memory_id=memory.id,
            person_id=OTHER_ID,
            now=datetime(2030, 8, 27, 13, tzinfo=UTC),
        )

    if route == "feed":
        response = client.get(
            f"/contexts/{CONTEXT_ID}/memories",
            headers=actor_headers(actor_id=OTHER_ID, roles="member"),
        )
    else:
        response = _request_social_route(
            client, route, memory.id, actor_id=OTHER_ID
        )

    assert response.status_code == 403, response.text


@pytest.mark.parametrize(
    ("visibility", "viewer_id", "accepted_friend"),
    [
        ("only_me", SENDER_ID, False),
        ("friends", ADVANCER_ID, True),
        ("group", ADVANCER_ID, False),
        ("public", ADVANCER_ID, False),
    ],
)
def test_feed_keeps_rows_visible_to_the_viewer(
    client, repository, visibility, viewer_id, accepted_friend
):
    memory = repository.seed_memory(author_id=SENDER_ID, visibility=visibility)
    if accepted_friend:
        _accept_friendship(repository, SENDER_ID, viewer_id)

    response = client.get(
        f"/contexts/{CONTEXT_ID}/memories",
        headers=actor_headers(actor_id=viewer_id, roles="member"),
    )

    assert response.status_code == 200, response.text
    assert str(memory.id) in {row["id"] for row in response.json()["memories"]}


def test_an_accepted_friend_can_read_comments(client, repository):
    memory = repository.seed_memory(author_id=SENDER_ID, visibility="friends")
    _accept_friendship(repository, SENDER_ID, ADVANCER_ID)

    response = _request_social_route(
        client, "GET comments", memory.id, actor_id=ADVANCER_ID
    )

    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            f"/contexts/{CONTEXT_ID}/memories",
            {"image_url": PHOTO_URL, "caption": "Ảnh nhóm"},
        ),
        (
            f"/contexts/{CONTEXT_ID}/checkins",
            {"place_id": "p-tiem-nuong-xom-lao", "caption": "Đã tới"},
        ),
    ],
)
def test_memory_writes_default_visibility_to_group(client, path, payload):
    response = client.post(path, headers=actor_headers(), json=payload)

    assert response.status_code == 201, response.text
    assert response.json().get("visibility") == "group"


@pytest.mark.parametrize(
    ("path", "payload", "visibility"),
    [
        (
            f"/contexts/{CONTEXT_ID}/memories",
            {"image_url": PHOTO_URL, "caption": "Ảnh riêng"},
            "only_me",
        ),
        (
            f"/contexts/{CONTEXT_ID}/checkins",
            {"place_id": "p-tiem-nuong-xom-lao", "caption": "Bạn bè"},
            "friends",
        ),
    ],
)
def test_memory_writes_store_and_return_explicit_visibility(
    client, path, payload, visibility
):
    response = client.post(
        path,
        headers=actor_headers(),
        json={**payload, "visibility": visibility},
    )

    assert response.status_code == 201, response.text
    assert response.json()["visibility"] == visibility
