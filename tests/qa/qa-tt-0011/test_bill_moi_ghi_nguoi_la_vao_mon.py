"""The third path that writes a name into a bill. Closed now; this holds it shut.

`#235` closed this hole on `POST /expenses/{id}/confirm`. `#247` closed it on
`PUT /bills/{id}/assignments` and said so in its own docstring: the guard "is
called in exactly one place", so it added the second. Counting the call sites
against the paths that write a `participant_id` is what this directory does,
and the count does not come out even:

    app/api/service.py   confirm_bill_assignments   guarded  (#247)
    app/api/service.py   confirm_expense            guarded  (#235)
    app/api/service.py   create_bill                NOT guarded  <- was

`create_bill` proved the *actor* belongs to the context and then passed
`item.suggested_participant_ids` -- straight out of the request body, never
checked against the roster -- down to the repository, which writes one
`BillItemShare` row per id (`repository.py:2083`). A share is not a draft: it
comes back out of `GET /bills/{id}` as somebody's dish and is what the person
tapping "đúng rồi" is agreeing to.

Measured on main @ 431dd7c, before this file existed:

    PUT  /bills/{id}/assignments   stranger -> 422 participant_not_in_context
    POST /bills                    stranger -> 201, share stored and readable

Same stranger, same bill, same group, two answers. The refusal exists; it is
simply not on this door.

The two cases that carried `xfail(strict=True)` are now plain assertions. That
was the point of `strict`: when the guard reached `create_bill` they turned
XPASS, a strict XPASS is a FAILURE, and so removing the marker became the
second half of the fix rather than a note somebody forgets. They are kept
because the measurement above is only worth having if something holds it.
"""

from __future__ import annotations

import uuid

import pytest

from tests.api.helpers import ADVANCER_ID, SENDER_ID, actor_headers
from tests.api.test_bills import bill_payload

# Well-formed and deliberately unknown. A valid UUID is not evidence of a
# person, and a person is not evidence of a member.
STRANGER_ID = uuid.UUID("9ee00000-eeee-4eee-8eee-0000e000000f")


def _create(client, first_item_owners):
    payload = bill_payload()
    payload["items"][0]["suggested_participant_ids"] = [
        str(person) for person in first_item_owners
    ]
    return client.post("/bills", headers=actor_headers(), json=payload)


def _shares_of(client, bill_id):
    stored = client.get(f"/bills/{bill_id}", headers=actor_headers()).json()
    return {
        share["participant_id"] for item in stored["items"] for share in item["shares"]
    }


def test_the_confirm_door_refuses_the_stranger(client):
    """Positive control for the guard itself.

    Without this, every case below is satisfied by a service that has no
    membership rule at all -- and the point being made is not "there is no
    guard", it is "the guard is not on every door".
    """

    bill = _create(client, [SENDER_ID]).json()

    response = client.put(
        f"/bills/{bill['id']}/assignments",
        headers=actor_headers(),
        json={
            "assignments": [
                {"item_key": "i1", "participant_ids": [str(STRANGER_ID)]},
                {"item_key": "i2", "participant_ids": [str(ADVANCER_ID)]},
            ]
        },
    )

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "participant_not_in_context"


def test_creating_a_bill_naming_only_members_is_still_accepted(client):
    """The ordinary case must keep working, or the gate above is just noise."""

    response = _create(client, [SENDER_ID])

    assert response.status_code == 201, response.text
    assert str(SENDER_ID) in _shares_of(client, response.json()["id"])


def test_creating_a_bill_refuses_a_participant_the_group_does_not_contain(client):
    """Same rule as the other two write paths, on the door nobody gated."""

    response = _create(client, [STRANGER_ID])

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "participant_not_in_context"


def test_a_refused_name_is_not_readable_as_somebodys_dish(client):
    """Refusing later at `split` would still leave this screen wrong.

    `GET /bills/{id}` is what a person reads while deciding whether the split
    is right. A stranger shown as the owner of a dish there is a decision the
    product has already drawn, whatever happens afterwards.
    """

    response = _create(client, [STRANGER_ID])
    if response.status_code != 201:
        return

    assert str(STRANGER_ID) not in _shares_of(client, response.json()["id"])


def test_every_stranger_is_named_at_once_not_just_the_first(client):
    """Whatever the answer becomes, it must not leak the roster by enumeration.

    Not marked xfail: today `create_bill` accepts both ids, so "no single
    stranger is singled out" holds vacuously. It is asserted anyway because the
    shape of the eventual refusal is the thing worth pinning -- `#247` had to
    make the same promise on its own path, and a fix that answers one id per
    round trip turns the group roster into something a caller can enumerate.
    """

    second_stranger = uuid.UUID("9ee00000-eeee-4eee-8eee-0000e000001f")
    response = _create(client, [STRANGER_ID, second_stranger])

    if response.status_code == 422:
        detail = response.json()["detail"]
        assert str(STRANGER_ID) in detail
        assert str(second_stranger) in detail
    else:
        stored = _shares_of(client, response.json()["id"])
        assert (str(STRANGER_ID) in stored) == (str(second_stranger) in stored)
