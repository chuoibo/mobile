"""The guest's "I transferred it" has to reach the person collecting.

The guest page says "waiting for NAM to confirm". Until this existed the
recipient's board had nowhere to read that from: `obligation_status` is derived
from `ReceiptConfirmation` only, so a guest who had done everything asked of
them looked identical to one who had done nothing.

What the board carries is the CLAIM, next to -- never inside -- the payment
status. Three different facts, kept apart on purpose:

  * `payment_reported_at` -- one person said they transferred, at this time.
  * `obligation_status`   -- somebody on the receiving side confirmed arrival.
  * neither one is evidence from a bank.
"""

from __future__ import annotations

import uuid

from .helpers import (
    ADVANCER_ID,
    OTHER_ID,
    SENDER_ID,
    actor_headers,
    create_batch,
    join_group,
    propose_and_confirm,
    publish_batch,
)


def _board(client, batch_id):
    response = client.get(f"/batches/{batch_id}/obligations", headers=actor_headers())
    assert response.status_code == 200, response.text
    return response.json()


def _rows(client, batch_id):
    board = _board(client, batch_id)
    return {row["obligation_id"]: row for row in board["obligations"]}


def _published(client, repository, **kwargs):
    propose_and_confirm(client, **kwargs)
    batch = create_batch(client, repository)
    published = publish_batch(client, batch["batch_id"])
    return batch, published["guest_links"]


class TestTheClaimReachesTheBoard:
    def test_a_board_with_no_report_says_so_rather_than_staying_silent(
        self, client, repository
    ):
        """`None` is the answer to "when did they say it", not a missing key.

        A key that only appears once somebody reports makes "nobody reported"
        and "this build is older than the field" the same thing on the wire.
        """
        batch, _ = _published(client, repository)

        board = _board(client, batch["batch_id"])

        assert board["payment_reported_count"] == 0
        for row in board["obligations"]:
            assert row["payment_reported_at"] is None

    def test_the_next_read_of_the_board_carries_the_guest_claim(
        self, client, repository
    ):
        """The acceptance case: guest presses the button, the recipient's next
        refresh is different from the one before it."""
        batch, links = _published(client, repository)
        path = links[0]["path"]
        obligation_id = batch["obligations"][0]["obligation_id"]

        report = client.post(path + "/da-chuyen", data={"obligation_id": obligation_id})
        assert report.status_code == 201, report.text

        board = _board(client, batch["batch_id"])
        rows = {row["obligation_id"]: row for row in board["obligations"]}
        assert rows[obligation_id]["payment_reported_at"] is not None
        assert board["payment_reported_count"] == 1

    def test_the_claim_does_not_move_the_payment_status(self, client, repository):
        """Invariant 3 in one assertion. Status stays derived from receipts;
        a self-report is displayed data, not a fourth state."""
        batch, links = _published(client, repository)
        path = links[0]["path"]
        obligation_id = batch["obligations"][0]["obligation_id"]

        client.post(path + "/da-chuyen", data={"obligation_id": obligation_id})

        row = _rows(client, batch["batch_id"])[obligation_id]
        assert row["obligation_status"] == "outstanding"
        assert row["payment_reported_at"] is not None

    def test_one_persons_claim_does_not_appear_on_another_persons_row(
        self, client, repository
    ):
        """Three participants, so two senders each hold their own link. A claim
        that spilled would tell the advancer somebody paid who never said so."""
        join_group(repository, OTHER_ID)
        batch, links = _published(
            client,
            repository,
            total=90_000,
            participants=[SENDER_ID, OTHER_ID, ADVANCER_ID],
        )
        assert len(links) >= 2, "fixture stopped producing two guest links"

        before = _board(client, batch["batch_id"])
        assert len(before["obligations"]) >= 2
        # Report from the link that actually holds the obligation. A link is a
        # capability over its own sender's rows, so picking the wrong one gets
        # a 404 rather than a claim.
        reporter = links[0]
        target = reporter["obligations"][0]["obligation_id"]
        others = [
            row["obligation_id"]
            for row in before["obligations"]
            if row["obligation_id"] != target
        ]
        assert others, "fixture stopped producing a second obligation"

        report = client.post(
            reporter["path"] + "/da-chuyen", data={"obligation_id": target}
        )
        assert report.status_code == 201, report.text

        rows = _rows(client, batch["batch_id"])
        assert rows[target]["payment_reported_at"] is not None
        for other in others:
            assert rows[other]["payment_reported_at"] is None, (
                "one guest's claim showed up on somebody else's obligation"
            )

    def test_confirming_receipt_does_not_erase_the_claim(self, client, repository):
        """Both facts survive together. The recipient confirming is a second,
        separate event by a different person -- it does not rewrite the first
        one, and a board that dropped the claim on confirmation would lose the
        only record that the sender ever spoke."""
        batch, links = _published(client, repository)
        path = links[0]["path"]
        obligation = batch["obligations"][0]
        obligation_id = obligation["obligation_id"]

        client.post(path + "/da-chuyen", data={"obligation_id": obligation_id})
        claimed_at = _rows(client, batch["batch_id"])[obligation_id][
            "payment_reported_at"
        ]

        confirm = client.post(
            f"/obligations/{obligation_id}/confirm-receipt",
            headers=actor_headers(),
            json={
                "amount_vnd": obligation["amount_vnd"],
                "idempotency_key": str(uuid.uuid4()),
            },
        )
        assert confirm.status_code == 201, confirm.text

        row = _rows(client, batch["batch_id"])[obligation_id]
        assert row["obligation_status"] == "confirmed"
        assert row["payment_reported_at"] == claimed_at

    def test_saying_it_twice_keeps_the_time_they_first_said_it(
        self, client, repository
    ):
        """A guest gets three reports. Showing the latest would make the board
        move without the claim changing -- the same reason the dispute reason
        beside it is "first one wins"."""
        batch, links = _published(client, repository)
        path = links[0]["path"]
        obligation_id = batch["obligations"][0]["obligation_id"]

        client.post(
            path + "/da-chuyen",
            data={"obligation_id": obligation_id, "idempotency_key": str(uuid.uuid4())},
        )
        first = _rows(client, batch["batch_id"])[obligation_id]["payment_reported_at"]
        client.post(
            path + "/da-chuyen",
            data={"obligation_id": obligation_id, "idempotency_key": str(uuid.uuid4())},
        )

        assert len(repository.reports) == 2, "fixture stopped recording two reports"
        again = _rows(client, batch["batch_id"])[obligation_id]["payment_reported_at"]
        assert again == first
