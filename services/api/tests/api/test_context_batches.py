"""`GET /contexts/{context_id}/batches`: the group's collection rounds.

`POST /batches` returns the id once. Without a list, a phone that restarted
or a member who did not open the round could not reach the board at all, and
the settlement screen had nowhere to send anyone. The list is a fold of the
board: the counts here are the board's own rows counted, never a second
derivation of who paid.
"""

from __future__ import annotations

import uuid

from .helpers import (
    CONTEXT_ID,
    actor_headers,
    create_batch,
    propose_and_confirm,
    publish_batch,
)


def _headers_for(context_id):
    headers = actor_headers()
    headers["X-Actor-Contexts"] = str(context_id)
    return headers


class TestTheListIsAFoldOfTheBoard:
    def test_a_frozen_round_is_listed_before_it_is_published(self, client, repository):
        propose_and_confirm(client)
        batch = create_batch(client, repository)

        response = client.get(
            f"/contexts/{CONTEXT_ID}/batches", headers=actor_headers()
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["context_id"] == str(CONTEXT_ID)
        assert [row["batch_id"] for row in body["batches"]] == [batch["batch_id"]]
        row = body["batches"][0]
        assert row["status"] == "frozen"
        assert row["published_at"] is None
        assert row["obligation_count"] == len(batch["obligations"])
        assert row["confirmed_count"] == 0
        assert row["disputed_count"] == 0
        # The obligations' amounts added on the server, no share invented here.
        assert row["total_vnd"] == sum(o["amount_vnd"] for o in batch["obligations"])

    def test_publishing_and_a_confirmed_receipt_move_the_counts(
        self, client, repository
    ):
        propose_and_confirm(client)
        batch = create_batch(client, repository)
        publish_batch(client, batch["batch_id"])
        target = batch["obligations"][0]
        confirmed = client.post(
            f"/obligations/{target['obligation_id']}/confirm-receipt",
            json={
                "amount_vnd": target["amount_vnd"],
                "idempotency_key": str(uuid.uuid4()),
            },
            headers=actor_headers(),
        )
        assert confirmed.status_code == 201, confirmed.text

        row = client.get(
            f"/contexts/{CONTEXT_ID}/batches", headers=actor_headers()
        ).json()["batches"][0]
        assert row["status"] == "published"
        assert row["published_at"] is not None
        assert row["confirmed_count"] == 1
        assert row["obligation_count"] == len(batch["obligations"])

    def test_a_group_with_no_round_gets_an_empty_list_not_an_error(self, client):
        response = client.get(
            f"/contexts/{CONTEXT_ID}/batches", headers=actor_headers()
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"context_id": str(CONTEXT_ID), "batches": []}


class TestTheListIsNotPublic:
    """Same rule as the board: membership, checked before anything is read."""

    def test_somebody_from_another_group_cannot_read_it(self, client, repository):
        propose_and_confirm(client)
        batch = create_batch(client, repository)
        publish_batch(client, batch["batch_id"])
        outsider = {
            "X-Actor-ID": str(uuid.uuid4()),
            "X-Actor-Roles": "member",
            "X-Actor-Contexts": str(uuid.uuid4()),
        }
        response = client.get(f"/contexts/{CONTEXT_ID}/batches", headers=outsider)
        assert response.status_code == 403, response.text
        for leaked in ("total_vnd", "batch_id", "obligation_count"):
            assert leaked not in response.text

    def test_an_unknown_group_refuses_the_same_way(self, client):
        """A 404 here would say which group ids exist. Fail closed, same code."""
        stranger_to_nothing = _headers_for(uuid.uuid4())
        response = client.get(
            f"/contexts/{uuid.uuid4()}/batches", headers=stranger_to_nothing
        )
        assert response.status_code == 403, response.text
