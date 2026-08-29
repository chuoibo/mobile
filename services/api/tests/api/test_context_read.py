"""GET /contexts/{context_id} -- the route that gives a group id a name.

`POST /contexts` mints an id and hands it back once. Every later surface that
identifies a group by that id -- a share link carrying `nhom=<uuid>`, a check-in
card that has to say *which* group arrived somewhere -- gets the key without the
name, and the server offered no request that would trade one for the other.
`/contexts/{id}/members` and `/contexts/{id}/balances` both existed; the group
itself could not be read.

The consequence was not cosmetic. The F46 check-in card refused to render from a
cold URL, because writing "nhóm <uuid> đã tới đây" onto a group's permanent
timeline is worse than refusing, and inventing a name is worse than both.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.api.repository import ContextRecord

from .helpers import ADVANCER_ID, CONTEXT_ID, OTHER_ID, actor_headers

CREATED_AT = datetime(2030, 8, 27, 12, tzinfo=UTC)


def _seed_context(repository, *, display_name="Hội đi Đà Lạt"):
    repository.contexts[CONTEXT_ID] = ContextRecord(
        id=CONTEXT_ID,
        display_name=display_name,
        created_by_id=ADVANCER_ID,
        created_at=CREATED_AT,
    )


def test_a_member_can_read_the_group_name_from_its_id_alone(client, repository):
    """The whole point: a uuid arrives from a link, a name has to come back."""
    _seed_context(repository)
    repository.active_memberships.add((CONTEXT_ID, ADVANCER_ID))

    response = client.get(f"/contexts/{CONTEXT_ID}", headers=actor_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(CONTEXT_ID)
    assert body["display_name"] == "Hội đi Đà Lạt"
    assert body["created_by_id"] == str(ADVANCER_ID)


def test_a_stranger_holding_the_id_is_refused_the_name(client, repository):
    """A group id travels in links, so holding one must not be membership.

    Without this half, the route above is satisfied by returning the row to
    anybody who can type a uuid -- and group names are group data.
    """
    _seed_context(repository)

    response = client.get(
        f"/contexts/{CONTEXT_ID}", headers=actor_headers(actor_id=OTHER_ID)
    )

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_a_stranger_is_refused_before_the_row_is_read(client, repository):
    """A non-member must not learn whether a group id exists.

    Answering 404 for an unknown id and 403 for a known one turns the route into
    an oracle for guessing which groups are real.
    """
    unknown = uuid.uuid4()

    response = client.get(
        f"/contexts/{unknown}", headers=actor_headers(actor_id=OTHER_ID)
    )

    assert response.status_code == 403


def test_a_member_of_a_group_with_no_row_gets_404_not_500(client, repository):
    """Membership is recorded per group id; the row it points at may be gone.

    The service reads an optional record, so the branch where it is `None` has
    to be a stated answer rather than an attribute error on the way out.
    """
    repository.active_memberships.add((CONTEXT_ID, ADVANCER_ID))

    response = client.get(f"/contexts/{CONTEXT_ID}", headers=actor_headers())

    assert response.status_code == 404
    assert response.json()["code"] == "context_not_found"
