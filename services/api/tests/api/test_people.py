"""Wiring for the route that gives a person id a name.

Orchestration only. Whether the foreign keys under `contexts` and `memberships`
are satisfied, and whether the guest envelope joins `people` at all, are
database facts and are proved in
`tests/postgres/test_person_identity_postgres.py`. A dict has no foreign key,
so a green test here says nothing about either.

What it does prove: the path carries the id, the two status codes mean what
they say, and the rename rule is enforced before the repository is touched.
"""

from __future__ import annotations

import uuid

from .helpers import ADVANCER_ID, OTHER_ID, actor_headers

FRIEND_ID = uuid.UUID("5ee00000-eeee-4eee-8eee-0000e0000001")


def _register(client, person_id, display_name, *, actor_id=ADVANCER_ID):
    return client.put(
        f"/people/{person_id}",
        json={"display_name": display_name},
        headers=actor_headers(actor_id=actor_id, roles="member,group_admin"),
    )


def test_naming_an_id_for_the_first_time_answers_201(client):
    response = _register(client, FRIEND_ID, "Quyên")

    assert response.status_code == 201, response.text
    assert response.json()["id"] == str(FRIEND_ID)
    assert response.json()["display_name"] == "Quyên"


def test_re_sending_the_same_name_answers_200(client):
    _register(client, FRIEND_ID, "Quyên")

    response = _register(client, FRIEND_ID, "Quyên", actor_id=OTHER_ID)

    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "Quyên"


def test_somebody_else_cannot_rename_a_person_who_already_has_a_name(client):
    _register(client, FRIEND_ID, "Quyên")

    response = _register(client, FRIEND_ID, "Kẻ giả danh", actor_id=OTHER_ID)

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "permission_denied"
    assert _register(client, FRIEND_ID, "Quyên").status_code == 200


def test_a_person_renames_themselves(client):
    _register(client, FRIEND_ID, "Quyên", actor_id=ADVANCER_ID)

    response = _register(client, FRIEND_ID, "Quyên Nguyễn", actor_id=FRIEND_ID)

    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "Quyên Nguyễn"


def test_an_empty_name_is_refused(client):
    response = _register(client, FRIEND_ID, "")

    assert response.status_code == 422, response.text


def test_a_guest_capability_may_not_name_anybody(client):
    """A bearer token is a capability, not an identity. Section 9.2 keeps one
    out of every action that asserts who somebody is."""
    response = client.put(
        f"/people/{FRIEND_ID}",
        json={"display_name": "Quyên"},
        headers=actor_headers(actor_id=OTHER_ID, roles="guest"),
    )

    assert response.status_code == 403, response.text
