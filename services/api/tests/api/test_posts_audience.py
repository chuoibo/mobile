"""F39/F42 across the HTTP boundary: who reads a post, and how many they read.

Every negative case here asserts a **count**, not only a status code. A feed
that leaks one row still answers 200, so `assertEqual(response.status_code,
200)` is not evidence of anything -- the number of rows in the body is the
whole claim. The one time this suite shipped a privacy gate with status-only
assertions, the gate was a `filter` that had been written as a `map`.

The cast:

    ADVANCER_ID  the author. In CONTEXT_ID.
    SENDER_ID    a groupmate. In CONTEXT_ID, not a friend.
    FRIEND_ID    a friend of the author. In no group.
    OTHER_ID     a stranger. Friend of nobody, member of nothing.

`SENDER_ID` and `FRIEND_ID` exist as separate people on purpose: they are the
two readers that a `friends`/`group` mix-up confuses, and a cast without both
cannot tell a correct implementation from one that treats the two audiences as
a ladder.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from .helpers import ADVANCER_ID, CONTEXT_ID, OTHER_ID, SENDER_ID, actor_headers

FRIEND_ID = uuid.UUID("5ee00000-eeee-4eee-8eee-0000e0000001")
OTHER_CONTEXT_ID = uuid.UUID("6ff00000-ffff-4fff-8fff-0000f0000001")


def befriend(repository, person_a, person_b):
    """An accepted edge, which is what `are_friends` reads."""
    edge_id = uuid.uuid4()
    repository.friend_edges[edge_id] = {
        "id": edge_id,
        "requester_id": person_a,
        "addressee_id": person_b,
        "state": "accepted",
        "decided_by_id": person_b,
        "created_at": datetime(2030, 8, 27, 12, tzinfo=UTC),
        "decided_at": datetime(2030, 8, 27, 12, tzinfo=UTC),
    }
    return edge_id


def post_body(audience, *, context_id=None, body="Tối nay ăn lẩu nhé"):
    payload = {"body": body, "audience": audience}
    if context_id is not None:
        payload["context_id"] = str(context_id)
    return payload


def write_post(client, audience, *, context_id=None, author=ADVANCER_ID, body="Chào"):
    response = client.post(
        "/posts",
        json=post_body(audience, context_id=context_id, body=body),
        headers=actor_headers(author),
    )
    assert response.status_code == 201, response.text
    return response.json()


def feed_ids(client, actor):
    response = client.get("/posts", headers=actor_headers(actor))
    assert response.status_code == 200, response.text
    return [row["id"] for row in response.json()["posts"]]


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def test_the_author_is_the_actor_and_cannot_be_named(client):
    """No `author_id` field exists to be filled in with somebody else."""
    response = client.post(
        "/posts",
        json={
            "body": "Chào",
            "audience": "public",
            "author_id": str(OTHER_ID),
        },
        headers=actor_headers(ADVANCER_ID),
    )
    assert response.status_code == 422, response.text


def test_a_created_post_is_attributed_to_the_caller(client):
    created = write_post(client, "public")
    assert created["author_id"] == str(ADVANCER_ID)


def test_a_group_post_must_name_a_group(client):
    response = client.post(
        "/posts",
        json=post_body("group"),
        headers=actor_headers(ADVANCER_ID),
    )
    assert response.status_code == 422, response.text


def test_a_non_group_post_may_not_name_a_group(client):
    for audience in ("only_me", "friends", "public"):
        response = client.post(
            "/posts",
            json=post_body(audience, context_id=CONTEXT_ID),
            headers=actor_headers(ADVANCER_ID),
        )
        assert response.status_code == 422, (audience, response.text)


def test_an_unknown_audience_is_refused(client):
    response = client.post(
        "/posts",
        json=post_body("everyone_lol"),
        headers=actor_headers(ADVANCER_ID),
    )
    assert response.status_code == 422, response.text


def test_posting_to_a_group_one_is_not_in_is_refused(client):
    """And the refusal does not depend on the group existing."""
    response = client.post(
        "/posts",
        json=post_body("group", context_id=OTHER_CONTEXT_ID),
        headers=actor_headers(ADVANCER_ID),
    )
    assert response.status_code == 403, response.text


def test_the_membership_header_does_not_grant_membership(client, repository):
    """`X-Actor-Contexts` is a claim by the caller. The roster is the fact.

    `helpers.actor_headers` puts CONTEXT_ID in that header for everybody, so
    this is the exact confusion the route has to refuse: OTHER_ID says they are
    in the group, and `repository.is_member` says they are not.
    """
    assert (CONTEXT_ID, OTHER_ID) not in repository.active_memberships
    response = client.post(
        "/posts",
        json=post_body("group", context_id=CONTEXT_ID),
        headers=actor_headers(OTHER_ID),
    )
    assert response.status_code == 403, response.text


# ---------------------------------------------------------------------------
# Reading -- one class of reader per audience, counted
# ---------------------------------------------------------------------------


def test_only_me_reaches_the_author_and_nobody_else(client, repository):
    befriend(repository, ADVANCER_ID, FRIEND_ID)
    created = write_post(client, "only_me")

    assert feed_ids(client, ADVANCER_ID) == [created["id"]]
    for reader in (SENDER_ID, FRIEND_ID, OTHER_ID):
        assert feed_ids(client, reader) == [], reader


def test_only_me_is_not_readable_by_id_by_anyone_else(client, repository):
    """404, not 403: a 403 would confirm the post exists."""
    befriend(repository, ADVANCER_ID, FRIEND_ID)
    created = write_post(client, "only_me")

    for reader in (SENDER_ID, FRIEND_ID, OTHER_ID):
        response = client.get(f"/posts/{created['id']}", headers=actor_headers(reader))
        assert response.status_code == 404, (reader, response.text)

    mine = client.get(f"/posts/{created['id']}", headers=actor_headers(ADVANCER_ID))
    assert mine.status_code == 200, mine.text


def test_reading_by_id_refuses_every_audience_the_reader_is_outside_of(
    client, repository
):
    """`GET /posts/{id}` for each audience, by each reader who may not have it.

    This route is the one read with no SQL narrowing in front of it: the feed
    is filtered twice (once by the query, once by `can_read`), but a lookup by
    id fetches whatever the id names and `can_read` is the *only* thing
    standing between that row and the response.

    Added because a mutation said so. Widening the `friends` branch of
    `app.domain.post_audience.can_read` to `return True` left this whole file
    green -- the feed tests could not see it, because the repository had
    already excluded those rows on its own. The leak it would cause is real
    and it is exactly here.
    """
    befriend(repository, ADVANCER_ID, FRIEND_ID)
    posts = {
        "only_me": write_post(client, "only_me"),
        "friends": write_post(client, "friends"),
        "group": write_post(client, "group", context_id=CONTEXT_ID),
        "public": write_post(client, "public"),
    }
    # Reader -> the audiences that reader is NOT entitled to read.
    outside = {
        SENDER_ID: ("only_me", "friends"),
        FRIEND_ID: ("only_me", "group"),
        OTHER_ID: ("only_me", "friends", "group"),
    }
    for reader, audiences in outside.items():
        for audience in audiences:
            response = client.get(
                f"/posts/{posts[audience]['id']}", headers=actor_headers(reader)
            )
            assert response.status_code == 404, (reader, audience, response.text)
            assert response.json()["code"] == "post_not_found"

    # And the ones they may read still come back, so the assertions above are
    # not passing because the route is simply broken for everybody.
    allowed = {
        SENDER_ID: ("group", "public"),
        FRIEND_ID: ("friends", "public"),
        OTHER_ID: ("public",),
    }
    for reader, audiences in allowed.items():
        for audience in audiences:
            response = client.get(
                f"/posts/{posts[audience]['id']}", headers=actor_headers(reader)
            )
            assert response.status_code == 200, (reader, audience, response.text)


def test_friends_reaches_friends_only(client, repository):
    befriend(repository, ADVANCER_ID, FRIEND_ID)
    created = write_post(client, "friends")

    assert feed_ids(client, FRIEND_ID) == [created["id"]]
    assert feed_ids(client, ADVANCER_ID) == [created["id"]]
    # A groupmate is not a friend, and a stranger is neither.
    assert feed_ids(client, SENDER_ID) == []
    assert feed_ids(client, OTHER_ID) == []


def test_unfriending_takes_the_post_back(client, repository):
    """`friends` resolves at read time, so the edge decides every read.

    Frozen at write time -- the obvious optimisation -- an ex-friend keeps
    reading everything they could read on the day they were added.
    """
    edge_id = befriend(repository, ADVANCER_ID, FRIEND_ID)
    created = write_post(client, "friends")
    assert feed_ids(client, FRIEND_ID) == [created["id"]]

    repository.friend_edges[edge_id]["state"] = "declined"
    assert feed_ids(client, FRIEND_ID) == []


def test_a_pending_request_is_not_friendship(client, repository):
    edge_id = befriend(repository, ADVANCER_ID, FRIEND_ID)
    repository.friend_edges[edge_id]["state"] = "pending"
    write_post(client, "friends")

    assert feed_ids(client, FRIEND_ID) == []


def test_group_reaches_the_group_only(client, repository):
    befriend(repository, ADVANCER_ID, FRIEND_ID)
    created = write_post(client, "group", context_id=CONTEXT_ID)

    assert feed_ids(client, SENDER_ID) == [created["id"]]
    assert feed_ids(client, ADVANCER_ID) == [created["id"]]
    # A friend of the author who is not in the group reads nothing, and the
    # stranger's `X-Actor-Contexts` header claims CONTEXT_ID and buys nothing.
    assert feed_ids(client, FRIEND_ID) == []
    assert feed_ids(client, OTHER_ID) == []


def test_leaving_the_group_takes_the_post_back(client, repository):
    created = write_post(client, "group", context_id=CONTEXT_ID)
    assert feed_ids(client, SENDER_ID) == [created["id"]]

    repository.active_memberships.discard((CONTEXT_ID, SENDER_ID))
    assert feed_ids(client, SENDER_ID) == []


def test_public_reaches_everybody(client):
    created = write_post(client, "public")
    for reader in (ADVANCER_ID, SENDER_ID, FRIEND_ID, OTHER_ID):
        assert feed_ids(client, reader) == [created["id"]], reader


# ---------------------------------------------------------------------------
# The whole wall at once -- the count is the assertion
# ---------------------------------------------------------------------------


def test_each_reader_sees_exactly_their_own_slice(client, repository):
    """Four posts up, and four different answers to "how many".

    Written as one test on purpose: the leak this guards against is a filter
    that is right about each audience alone and wrong about the set, and a
    suite that only ever puts one post on the wall cannot see it.
    """
    befriend(repository, ADVANCER_ID, FRIEND_ID)
    only_me = write_post(client, "only_me", body="ghi cho mình")
    friends = write_post(client, "friends", body="cho bạn bè")
    group = write_post(client, "group", context_id=CONTEXT_ID, body="cho nhóm")
    public = write_post(client, "public", body="cho tất cả")

    expected = {
        ADVANCER_ID: {only_me["id"], friends["id"], group["id"], public["id"]},
        SENDER_ID: {group["id"], public["id"]},
        FRIEND_ID: {friends["id"], public["id"]},
        OTHER_ID: {public["id"]},
    }
    for reader, visible in expected.items():
        got = feed_ids(client, reader)
        assert len(got) == len(visible), (reader, got)
        assert set(got) == visible, reader


def test_a_persons_wall_is_filtered_for_the_reader(client, repository):
    """The profile screen. Same rule, different route, so it is asserted twice.

    A second read path is exactly where the rule gets re-spelled and gets it
    wrong -- the wall was the surface that leaked in the incident this file's
    module docstring refers to.
    """
    befriend(repository, ADVANCER_ID, FRIEND_ID)
    write_post(client, "only_me")
    friends = write_post(client, "friends")
    group = write_post(client, "group", context_id=CONTEXT_ID)
    public = write_post(client, "public")

    expected = {
        ADVANCER_ID: 4,
        SENDER_ID: 2,
        FRIEND_ID: 2,
        OTHER_ID: 1,
    }
    for reader, count in expected.items():
        response = client.get(
            f"/people/{ADVANCER_ID}/posts", headers=actor_headers(reader)
        )
        assert response.status_code == 200, (reader, response.text)
        rows = response.json()["posts"]
        assert len(rows) == count, (reader, rows)
        assert all(row["author_id"] == str(ADVANCER_ID) for row in rows)

    stranger_rows = client.get(
        f"/people/{ADVANCER_ID}/posts", headers=actor_headers(OTHER_ID)
    ).json()["posts"]
    assert [row["id"] for row in stranger_rows] == [public["id"]]
    assert friends["id"] not in {row["id"] for row in stranger_rows}
    assert group["id"] not in {row["id"] for row in stranger_rows}


def test_an_only_me_post_is_absent_from_a_stranger_wall_body_entirely(
    client, repository
):
    """Not in the rows, and not in the serialised bytes either.

    The row could be filtered out of the list and still be reachable through
    some sibling field somebody adds later. Asserting on the raw body is the
    cheap way to keep that honest.
    """
    del repository
    secret = write_post(client, "only_me", body="Số tài khoản của mẹ")
    response = client.get(
        f"/people/{ADVANCER_ID}/posts", headers=actor_headers(OTHER_ID)
    )
    assert response.status_code == 200
    assert response.json()["posts"] == []
    assert secret["id"] not in response.text
    assert "Số tài khoản của mẹ" not in response.text


def test_a_post_in_a_group_the_reader_left_is_gone_from_the_wall(client, repository):
    write_post(client, "group", context_id=CONTEXT_ID)
    repository.active_memberships.discard((CONTEXT_ID, SENDER_ID))

    response = client.get(
        f"/people/{ADVANCER_ID}/posts", headers=actor_headers(SENDER_ID)
    )
    assert response.status_code == 200, response.text
    assert response.json()["posts"] == []
