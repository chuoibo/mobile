"""The seam where a scanned bill meets the frozen allocator.

Two things are being pinned here, and only one of them is about HTTP.

The first is that no second division exists. `POST /bills/{id}/split` must reach
`app.domain.allocator.allocate`; a hand-rolled per-person number computed in the
service layer would pass a naive assertion about response shape while quietly
becoming the second answer to "what does Bình owe", and the two answers would
drift the first time somebody touched rounding. One test therefore watches the
allocator itself get called rather than trusting the number that comes back.

The second is that a guess is not a decision. An AI assignment arrives as
`ai_suggested` and is allowed to be previewed; it is not allowed to reach the
ledger. `for_ledger=True` is the gate where that distinction gets teeth, and a
test that only ever checked the happy preview would never notice the gate
falling open.
"""

from __future__ import annotations

import unittest.mock
import uuid

import pytest

from app.api.repository import BillItemRecord, BillRecord, BillShareRecord
from tests.api.helpers import ADVANCER_ID, CONTEXT_ID, OTHER_ID, SENDER_ID, actor_headers

OUTSIDER_ID = uuid.UUID("5ee00000-eeee-4eee-8eee-0000e0000001")
OTHER_CONTEXT_ID = uuid.UUID("6ff00000-ffff-4fff-8fff-0000f0000001")


def bill_payload(*, context_id=CONTEXT_ID, printed_total_vnd=135000, items=None):
    """Two lines, two people, one dish each -- the smallest bill that can be
    got wrong. An even split and a per-item split return the same numbers when
    both people ate the same amount, so the amounts here differ on purpose."""

    return {
        "context_id": str(context_id),
        "printed_total_vnd": printed_total_vnd,
        "items_total_vnd": 135000,
        "confidence": 88,
        "needs_review": False,
        "items": items
        if items is not None
        else [
            {
                "item_key": "i1",
                "name": "Phở bò",
                "quantity": 1,
                "unit_price_vnd": 65000,
                "line_total_vnd": 65000,
                "suggested_participant_ids": [str(SENDER_ID)],
            },
            {
                "item_key": "i2",
                "name": "Bún chả",
                "quantity": 1,
                "unit_price_vnd": 70000,
                "line_total_vnd": 70000,
                "suggested_participant_ids": [str(ADVANCER_ID)],
            },
        ],
    }


def create_bill(client, **kwargs):
    response = client.post(
        "/bills", headers=actor_headers(), json=bill_payload(**kwargs)
    )
    assert response.status_code == 201, response.text
    return response.json()


def confirm_all(client, bill_id):
    """Confirm the AI's guesses unchanged -- the ordinary case where a person
    read the suggestion and agreed with it. Agreeing is still a decision."""

    return client.put(
        f"/bills/{bill_id}/assignments",
        headers=actor_headers(),
        json={
            "assignments": [
                {"item_key": "i1", "participant_ids": [str(SENDER_ID)]},
                {"item_key": "i2", "participant_ids": [str(ADVANCER_ID)]},
            ]
        },
    )


def sources(body):
    return {
        item["item_key"]: [share["source"] for share in item["shares"]]
        for item in body["items"]
    }


class TestBillDraftCreation:
    def test_an_ai_assignment_is_stored_as_a_suggestion_not_a_decision(self, client):
        body = create_bill(client)

        assert sources(body) == {"i1": ["ai_suggested"], "i2": ["ai_suggested"]}
        for item in body["items"]:
            for share in item["shares"]:
                # Nobody decided this, so nobody is recorded as having decided
                # it. A `decided_by_id` filled in by the scanner would make a
                # guess indistinguishable from a person's agreement.
                assert share["decided_by_id"] is None
                assert share["decided_at"] is None

    def test_a_fresh_draft_reports_itself_as_unconfirmed(self, client):
        assert create_bill(client)["assignment_state"] == "ai_suggested"

    def test_a_draft_creates_no_obligation(self, client, repository):
        """Scanning a bill is not spending money. The ledger only accepts an
        expense version, and nothing on this path writes one."""

        create_bill(client)

        assert repository.confirmations == {}


class TestAssignmentConfirmation:
    def test_confirming_marks_the_shares_as_decided_and_names_the_decider(
        self, client
    ):
        bill = create_bill(client)

        response = confirm_all(client, bill["id"])

        assert response.status_code == 200, response.text
        body = response.json()
        assert sources(body) == {"i1": ["confirmed"], "i2": ["confirmed"]}
        for item in body["items"]:
            for share in item["shares"]:
                assert share["decided_by_id"] == str(ADVANCER_ID)
                assert share["decided_at"] is not None
        assert body["assignment_state"] == "confirmed"

    def test_a_person_may_overrule_the_ai_about_who_ate_what(self, client):
        """The suggestion said Sender ate i1. A correction has to actually
        replace the guess, not sit alongside it -- two shares on one line would
        halve the amount that line charges."""

        bill = create_bill(client)

        response = client.put(
            f"/bills/{bill['id']}/assignments",
            headers=actor_headers(),
            json={
                "assignments": [
                    {"item_key": "i1", "participant_ids": [str(ADVANCER_ID)]}
                ]
            },
        )

        assert response.status_code == 200, response.text
        items = {item["item_key"]: item for item in response.json()["items"]}
        assert [share["participant_id"] for share in items["i1"]["shares"]] == [
            str(ADVANCER_ID)
        ]
        # i2 was not mentioned, so it keeps the standing it already had.
        assert [share["source"] for share in items["i2"]["shares"]] == ["ai_suggested"]

    def test_an_unmentioned_item_leaves_the_bill_unconfirmed(self, client):
        bill = create_bill(client)

        response = client.put(
            f"/bills/{bill['id']}/assignments",
            headers=actor_headers(),
            json={
                "assignments": [
                    {"item_key": "i1", "participant_ids": [str(SENDER_ID)]}
                ]
            },
        )

        assert response.json()["assignment_state"] == "ai_suggested"
        assert response.json()["suggested_item_keys"] == ["i2"]

    def test_an_unknown_item_key_is_refused_rather_than_ignored(self, client):
        """Silently dropping an assignment for a line that does not exist means
        the caller believes it assigned a dish that nobody now owns."""

        bill = create_bill(client)

        response = client.put(
            f"/bills/{bill['id']}/assignments",
            headers=actor_headers(),
            json={
                "assignments": [
                    {"item_key": "khong-ton-tai", "participant_ids": [str(SENDER_ID)]}
                ]
            },
        )

        assert response.status_code == 409, response.text
        assert response.json()["code"] == "UNKNOWN_BILL_ITEM"


class TestSplitReusesTheAllocator:
    def test_split_calls_the_frozen_allocator(self, client):
        """The acceptance criterion "reuse the allocator, do not write a second
        division" is not observable from the response body: a hand-rolled split
        of this bill returns the same two numbers. So watch the call.

        Patched where the service looks it up, not where it is defined, and the
        real function still runs -- this proves the path, it does not stub the
        money.
        """

        bill = create_bill(client)
        confirm_all(client, bill["id"])

        from app.api import service as service_module

        with unittest.mock.patch.object(
            service_module, "allocate", wraps=service_module.allocate
        ) as spy:
            response = client.post(
                f"/bills/{bill['id']}/split", headers=actor_headers(), json={}
            )

        assert response.status_code == 200, response.text
        assert spy.call_count == 1, "split must reach app.domain.allocator.allocate"

    def test_split_charges_each_person_for_the_dish_they_ate(self, client):
        bill = create_bill(client)
        confirm_all(client, bill["id"])

        response = client.post(
            f"/bills/{bill['id']}/split", headers=actor_headers(), json={}
        )

        allocations = response.json()["allocation"]["allocations"]
        assert allocations[str(SENDER_ID)] == 65000
        assert allocations[str(ADVANCER_ID)] == 70000

    def test_the_split_sums_to_the_printed_total(self, client):
        """Money law 2, checked at this seam rather than assumed from the
        allocator's own tests: the projection could drop a line on the way in
        and every allocator test would still pass."""

        bill = create_bill(client)
        confirm_all(client, bill["id"])

        body = client.post(
            f"/bills/{bill['id']}/split", headers=actor_headers(), json={}
        ).json()

        assert sum(body["allocation"]["allocations"].values()) == 135000
        assert body["total_amount_vnd"] == 135000

    def test_a_preview_still_reports_which_lines_are_only_guesses(self, client):
        bill = create_bill(client)

        body = client.post(
            f"/bills/{bill['id']}/split", headers=actor_headers(), json={}
        ).json()

        assert body["assignment_state"] == "ai_suggested"
        assert body["suggested_item_keys"] == ["i1", "i2"]

    def test_a_bill_whose_lines_miss_the_printed_total_is_refused(self, client):
        """The paper said 200.000 and the lines add to 135.000. One of the two
        is wrong and this layer does not get to pick, so the allocator's
        RECONCILIATION_MISMATCH has to come out intact rather than the service
        quietly stretching a line to make the sum work."""

        bill = create_bill(client, printed_total_vnd=200000)
        confirm_all(client, bill["id"])

        response = client.post(
            f"/bills/{bill['id']}/split", headers=actor_headers(), json={}
        )

        assert response.status_code == 422, response.text
        assert response.json()["code"] == "RECONCILIATION_MISMATCH"

    def test_a_bill_with_no_lines_is_not_quietly_split_evenly(self, client):
        bill = create_bill(client, items=[])

        response = client.post(
            f"/bills/{bill['id']}/split", headers=actor_headers(), json={}
        )

        assert response.status_code == 422, response.text
        assert response.json()["code"] == "BILL_HAS_NO_ITEMS"


class TestTheLedgerGate:
    def test_a_suggested_assignment_may_not_be_taken_to_the_ledger(self, client):
        """This is where the suggested/confirmed distinction has a consequence.
        Preview freely; charging somebody needs a person to have said so."""

        bill = create_bill(client)

        response = client.post(
            f"/bills/{bill['id']}/split",
            headers=actor_headers(),
            json={"for_ledger": True},
        )

        assert response.status_code == 422, response.text
        assert response.json()["code"] == "bill_assignments_not_confirmed"

    def test_one_unconfirmed_line_is_enough_to_hold_the_whole_bill_back(self, client):
        bill = create_bill(client)
        client.put(
            f"/bills/{bill['id']}/assignments",
            headers=actor_headers(),
            json={
                "assignments": [
                    {"item_key": "i1", "participant_ids": [str(SENDER_ID)]}
                ]
            },
        )

        response = client.post(
            f"/bills/{bill['id']}/split",
            headers=actor_headers(),
            json={"for_ledger": True},
        )

        assert response.status_code == 422, response.text
        assert response.json()["code"] == "bill_assignments_not_confirmed"

    def test_a_confirmed_bill_passes_the_gate(self, client):
        bill = create_bill(client)
        confirm_all(client, bill["id"])

        response = client.post(
            f"/bills/{bill['id']}/split",
            headers=actor_headers(),
            json={"for_ledger": True},
        )

        assert response.status_code == 200, response.text
        assert response.json()["assignment_state"] == "confirmed"


class TestGroupBoundary:
    """A bill names what people ate and how much they owe. Someone who is not
    in the group has no reading of it -- not a redacted one, none."""

    def _outsider_headers(self):
        return {
            "X-Actor-ID": str(OUTSIDER_ID),
            "X-Actor-Roles": "member",
            "X-Actor-Contexts": str(OTHER_CONTEXT_ID),
        }

    def test_an_outsider_cannot_create_a_bill_in_someone_elses_group(self, client):
        response = client.post(
            "/bills", headers=self._outsider_headers(), json=bill_payload()
        )

        assert response.status_code in (403, 404), response.text

    def test_an_outsider_cannot_read_the_dishes_of_another_group(self, client):
        bill = create_bill(client)

        response = client.get(
            f"/bills/{bill['id']}", headers=self._outsider_headers()
        )

        assert response.status_code in (403, 404), response.text
        assert "Phở bò" not in response.text

    def test_an_outsider_cannot_reassign_who_ate_what(self, client):
        bill = create_bill(client)

        response = client.put(
            f"/bills/{bill['id']}/assignments",
            headers=self._outsider_headers(),
            json={
                "assignments": [
                    {"item_key": "i1", "participant_ids": [str(OUTSIDER_ID)]}
                ]
            },
        )

        assert response.status_code in (403, 404), response.text

    def test_an_outsider_cannot_split_another_groups_bill(self, client):
        bill = create_bill(client)

        response = client.post(
            f"/bills/{bill['id']}/split", headers=self._outsider_headers(), json={}
        )

        assert response.status_code in (403, 404), response.text
        assert "65000" not in response.text


class TestMissingBill:
    def test_a_bill_that_does_not_exist_is_a_404(self, client):
        response = client.get(f"/bills/{uuid.uuid4()}", headers=actor_headers())

        assert response.status_code == 404, response.text
