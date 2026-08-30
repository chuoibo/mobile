"""F38 across the HTTP boundary: who may read a group's newest photograph.

Every case here asserts a **record count**, never only a status code. That is
not style. A 403 whose body is empty and a 403 whose body carries the photo
are the same assertion under `assertEqual(response.status_code, 403)`, and the
widget's whole risk is a body: it renders unattended, on a lock screen, beside
whatever else the phone is showing. `widget_records()` below returns the list
of photo payloads a response actually contains -- length 1 or length 0 -- so a
refusal that leaked would fail on the number rather than pass on the code.

The cast, deliberately the same shape `test_posts_audience.py` uses:

    ADVANCER_ID  a member of CONTEXT_ID. Author of the photograph.
    SENDER_ID    a second member of CONTEXT_ID. Reads what they did not write.
    OTHER_ID     a stranger. In no group -- `conftest.repository` refuses to
                 seed them, on purpose.

`OTHER_ID` matters more here than anywhere else in this suite, because
`helpers.actor_headers` sends `X-Actor-Contexts: CONTEXT_ID` for *every*
caller. So the stranger's request arrives already claiming membership of the
group it is asking about. An implementation that read the header instead of
asking the database would answer that request with the photograph, and would
pass a probe that only looked at status codes on a caller who told the truth.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.api.repository import MemoryRecord, PersonRecord

from .helpers import ADVANCER_ID, CONTEXT_ID, OTHER_ID, SENDER_ID, actor_headers

#: The one string this whole file exists to keep away from a stranger. Distinct
#: enough that a substring search over the raw response text means something.
PHOTO_URL = f"/contexts/{CONTEXT_ID}/photos/7f0a1b2c-3d4e-4f5a-8b6c-7d8e9f0a1b2c"
CAPTION = "Lẩu ở Nguyễn Thị Minh Khai"
AUTHOR_NAME = "Nam"

FIRST = datetime(2030, 8, 27, 12, 0, tzinfo=UTC)
LATER = datetime(2030, 8, 27, 19, 30, tzinfo=UTC)


def name_people(repository):
    """The wall stores an `author_id`; a widget draws a name."""

    for person_id, name in (
        (ADVANCER_ID, AUTHOR_NAME),
        (SENDER_ID, "Hà"),
        (OTHER_ID, "Người lạ"),
    ):
        repository.people[person_id] = PersonRecord(
            id=person_id, display_name=name, created_at=FIRST
        )


def put_photo(
    repository,
    *,
    context_id=CONTEXT_ID,
    author=ADVANCER_ID,
    image_url=PHOTO_URL,
    caption=CAPTION,
    created_at=FIRST,
):
    memory_id = uuid.uuid4()
    repository.memories[memory_id] = MemoryRecord(
        id=memory_id,
        context_id=context_id,
        author_id=author,
        kind="photo",
        image_url=image_url,
        caption=caption,
        place_id=None,
        place_name=None,
        lat=None,
        lng=None,
        created_at=created_at,
    )
    return memory_id


def put_checkin(repository, *, context_id=CONTEXT_ID, author=ADVANCER_ID, created_at):
    memory_id = uuid.uuid4()
    repository.memories[memory_id] = MemoryRecord(
        id=memory_id,
        context_id=context_id,
        author_id=author,
        kind="checkin",
        image_url=None,
        caption=None,
        place_id="quan-lau-1",
        place_name="Quán lẩu",
        lat=10.78,
        lng=106.69,
        created_at=created_at,
    )
    return memory_id


def read_widget(client, actor, *, context_id=CONTEXT_ID, roles="member"):
    return client.get(
        f"/contexts/{context_id}/widget",
        headers=actor_headers(actor, roles=roles),
    )


def widget_records(response):
    """Every photo payload in this body, as a list. Zero or one.

    Written to return a list and not a bool so that a caller writes
    `len(...) == 0` -- the number is the claim. A response that is not JSON at
    all (a 500 page, an HTML error) counts as zero rather than raising, so a
    crashed route cannot be mistaken for a defended one by this function; the
    status assertion beside every call is what separates those two.
    """

    try:
        body = response.json()
    except Exception:
        return []
    if not isinstance(body, dict):
        return []
    photo = body.get("photo")
    return [photo] if isinstance(photo, dict) else []


# ---------------------------------------------------------------------------
# The positive direction first. Every refusal below is worthless until this
# passes: a widget that answers nobody is not a widget that keeps a secret.
# ---------------------------------------------------------------------------


def test_a_member_sees_the_groups_newest_photograph(client, repository):
    name_people(repository)
    memory_id = put_photo(repository)

    response = read_widget(client, ADVANCER_ID)

    assert response.status_code == 200, response.text
    records = widget_records(response)
    assert len(records) == 1
    photo = records[0]
    assert photo["memory_id"] == str(memory_id)
    assert photo["image_url"] == PHOTO_URL
    assert photo["caption"] == CAPTION
    assert photo["author_id"] == str(ADVANCER_ID)
    assert photo["author_name"] == AUTHOR_NAME
    assert photo["created_at"].startswith("2030-08-27T12:00:00")


def test_a_second_member_sees_a_photograph_they_did_not_take(client, repository):
    """The widget is the group's, not the author's."""

    name_people(repository)
    put_photo(repository, author=ADVANCER_ID)

    response = read_widget(client, SENDER_ID)

    assert response.status_code == 200, response.text
    records = widget_records(response)
    assert len(records) == 1
    assert records[0]["author_name"] == AUTHOR_NAME


def test_the_widget_shows_the_newest_of_several(client, repository):
    name_people(repository)
    put_photo(repository, created_at=FIRST, image_url=PHOTO_URL, caption="Cũ")
    newest = put_photo(
        repository,
        author=SENDER_ID,
        created_at=LATER,
        image_url=PHOTO_URL + "-moi",
        caption="Mới",
    )

    records = widget_records(read_widget(client, ADVANCER_ID))

    assert len(records) == 1
    assert records[0]["memory_id"] == str(newest)
    assert records[0]["caption"] == "Mới"
    assert records[0]["author_name"] == "Hà"


def test_a_newer_checkin_does_not_blank_the_widget(client, repository):
    """F46 shares the wall. A check-in has no image, so it is not the answer.

    Without the `kind="photo"` filter the newest row here is the check-in, its
    `image_url` is null, and the widget answers "nothing to draw" for a group
    that has a photograph -- reading as broken rather than as empty.
    """

    name_people(repository)
    photo_id = put_photo(repository, created_at=FIRST)
    put_checkin(repository, created_at=LATER)

    records = widget_records(read_widget(client, ADVANCER_ID))

    assert len(records) == 1
    assert records[0]["memory_id"] == str(photo_id)


# ---------------------------------------------------------------------------
# The leak probe. Counts, not codes.
# ---------------------------------------------------------------------------


def test_a_stranger_gets_no_records_and_no_photo_url(client, repository):
    """`OTHER_ID` is in no group, and says otherwise in the header.

    `actor_headers` sets `X-Actor-Contexts: CONTEXT_ID` for everybody, so this
    request asserts the membership it does not have. The roster is asked
    instead, and the roster says no.
    """

    name_people(repository)
    put_photo(repository)

    response = read_widget(client, OTHER_ID)

    assert response.status_code == 403, response.text
    assert len(widget_records(response)) == 0
    assert PHOTO_URL not in response.text
    assert CAPTION not in response.text
    assert AUTHOR_NAME not in response.text
    assert str(ADVANCER_ID) not in response.text


def test_a_stranger_claiming_every_role_still_gets_no_records(client, repository):
    """Under-credentialling is not what is refusing this caller.

    If the widget ever opens to `OTHER_ID`, it must not be because the probe
    forgot a role. This request carries every role the product grants.
    """

    name_people(repository)
    put_photo(repository)

    response = read_widget(
        client,
        OTHER_ID,
        roles="member,group_admin,batch_owner,advancer,recipient,sender,creditor",
    )

    assert response.status_code == 403, response.text
    assert len(widget_records(response)) == 0
    assert PHOTO_URL not in response.text


def test_a_guest_gets_no_records(client, repository):
    """The guest page never reaches this route.

    A guest holds a `/g/{token}` link and no membership. `view_group_memories`
    is a member action, so the role alone refuses this before the roster is
    even consulted -- and the body carries nothing either way.
    """

    name_people(repository)
    put_photo(repository)

    response = read_widget(client, OTHER_ID, roles="guest")

    assert response.status_code == 403, response.text
    assert len(widget_records(response)) == 0
    assert PHOTO_URL not in response.text


def test_a_member_of_one_group_gets_no_records_from_another(client, repository):
    """Membership is per group, not a flag on a person.

    `ADVANCER_ID` is a real member of a real group. That does not make them a
    member of this one, and a check that only asked "is this actor in *any*
    group" would answer with somebody else's dinner.
    """

    other_context = uuid.UUID("8bb00000-bbbb-4bbb-8bbb-0000b0000009")
    name_people(repository)
    put_photo(repository, context_id=other_context)

    response = read_widget(client, ADVANCER_ID, context_id=other_context)

    assert response.status_code == 403, response.text
    assert len(widget_records(response)) == 0
    assert PHOTO_URL not in response.text


def test_a_stranger_cannot_tell_an_empty_group_from_a_full_one(client, repository):
    """Two groups, one photograph between them, one refusal for both.

    The status code and the record count are identical whether the group the
    stranger names holds a photograph or nothing at all, so the route is not an
    oracle for what a group contains.
    """

    empty_context = uuid.UUID("9cc00000-cccc-4ccc-8ccc-0000c0000009")
    name_people(repository)
    put_photo(repository)

    full = read_widget(client, OTHER_ID, context_id=CONTEXT_ID)
    empty = read_widget(client, OTHER_ID, context_id=empty_context)

    assert full.status_code == empty.status_code == 403
    assert len(widget_records(full)) == len(widget_records(empty)) == 0
    assert full.json() == empty.json()


# ---------------------------------------------------------------------------
# The empty state, which is a 200 and says nothing about the group.
# ---------------------------------------------------------------------------


def test_a_group_with_no_photographs_answers_two_hundred_and_null(client, repository):
    name_people(repository)

    response = read_widget(client, ADVANCER_ID)

    assert response.status_code == 200, response.text
    assert len(widget_records(response)) == 0
    assert response.json() == {"context_id": str(CONTEXT_ID), "photo": None}


def test_a_group_holding_only_checkins_answers_null(client, repository):
    """Check-ins are on the wall and are not photographs."""

    name_people(repository)
    put_checkin(repository, created_at=LATER)

    response = read_widget(client, ADVANCER_ID)

    assert response.status_code == 200, response.text
    assert len(widget_records(response)) == 0


def test_the_empty_body_carries_nothing_about_the_group(client, repository):
    """Two fields, both of them things the caller already held.

    An empty widget is the state a stranger who *has* just been added to a
    group sees first, so it is the state most likely to be read by somebody the
    group is still deciding about. It must not carry a member count, a group
    name, a creation date or a roster -- and the way to keep it from carrying
    them is to assert the exact set of keys rather than the absence of the ones
    that happen to be on today's mind.
    """

    from app.api.repository import ContextRecord

    repository.contexts[CONTEXT_ID] = ContextRecord(
        id=CONTEXT_ID,
        display_name="Nhóm Lẩu Thứ Bảy",
        created_by_id=ADVANCER_ID,
        created_at=FIRST,
    )
    name_people(repository)

    response = read_widget(client, SENDER_ID)

    assert response.status_code == 200, response.text
    assert set(response.json()) == {"context_id", "photo"}
    assert "Nhóm Lẩu Thứ Bảy" not in response.text
    assert "Hà" not in response.text


# ---------------------------------------------------------------------------
# The request shape itself
# ---------------------------------------------------------------------------


def test_the_widget_route_takes_no_identity_field(client, repository):
    """There is no body and no query parameter naming a person or a group.

    A widget refreshes on a timer with no user in front of it, so the request
    it sends is the smallest thing that can be spelled. `extra="forbid"` is on
    every request model in this app; the point here is that there is no request
    model at all to put a field into. Sending a body changes nothing.
    """

    name_people(repository)
    put_photo(repository)

    sneaky = client.get(
        f"/contexts/{CONTEXT_ID}/widget?person_id={ADVANCER_ID}",
        headers=actor_headers(OTHER_ID, roles="member"),
    )

    assert sneaky.status_code == 403, sneaky.text
    assert len(widget_records(sneaky)) == 0
    assert PHOTO_URL not in sneaky.text
