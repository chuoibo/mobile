"""`items_total_vnd` on a stored bill must be the sum of that bill's lines.

`POST /bills` takes `items_total_vnd` from the request body and writes it
through untouched. Nothing recomputes it, and the only rule the database
carries is `items_total_nonnegative`. So the figure is a caller assertion that
the server stores as if it were a fact, and `GET /bills/{id}` hands it back
beside the very lines it is supposed to be the sum of.

Why that matters here rather than in general. `items_total_vnd` is the one
number in this payload the client never authors: `read_receipt` computes it as
`sum(item["line_total_vnd"] for item in items)` and `ReceiptScanResponse`
returns it. The realistic way it goes wrong is not malice but editing -- a
person deletes a misread line on the review screen and the client re-posts the
scanner's original total beside the shortened list. The bill is then internally
inconsistent from its first write, and stays that way.

The consequence is two numbers for one meal, which is the specific failure this
product is built to avoid. `GET /bills/{id}` shows `items_total_vnd`;
`POST /bills/{id}/split` shows `total_amount_vnd`, which
`allocator_input_from_bill` derives from the stored lines. When the declared
total disagrees with the lines, those two screens disagree, and the split
screen is the one telling the truth.

What this gate does NOT claim:

- It is not a money-law-2 fix. The allocator never reads `items_total_vnd`, so
  a wrong value here has never made `Σ` allocations differ from the total that
  was split. This is about the figure a person reads, not the one they owe.
- It says nothing about `printed_total_vnd`. That number is allowed to disagree
  with the lines -- it is what the paper said, and the disagreement is
  information the scan reports as `total_difference_vnd`. Only the *sum of the
  lines* is being pinned, because only it is arithmetic rather than evidence.
- Surcharges and discounts are deliberately outside the sum, matching
  `read_receipt`. A fix that folded them in would be a different rule wearing
  this one's name, so a case below pins that they stay out.
"""

from __future__ import annotations

from tests.api.helpers import ADVANCER_ID, SENDER_ID, actor_headers

from .test_bills import bill_payload, create_bill

# The two lines in `bill_payload` are 65.000 and 70.000.
LINES_SUM_VND = 135000


class TestDeclaredItemsTotalMustMatchTheLines:
    def test_a_bill_whose_declared_total_exceeds_its_lines_is_refused(self, client):
        """The shape a review screen produces when a line is deleted.

        The scanner read three dishes, the person removed the one it misread,
        and the client re-sent the total from before the edit. Every field is
        individually well formed, so nothing but this rule can catch it.
        """
        payload = bill_payload()
        payload["items_total_vnd"] = LINES_SUM_VND + 40000

        response = client.post("/bills", headers=actor_headers(), json=payload)

        assert response.status_code == 422, response.text
        assert response.json()["code"] == "bill_items_total_mismatch"

    def test_a_bill_whose_declared_total_falls_short_of_its_lines_is_refused(
        self, client
    ):
        """The other direction, which no reader would notice.

        A total that is too low looks like a cheaper meal rather than like a
        broken payload, so it is the direction that survives being looked at.
        """
        payload = bill_payload()
        payload["items_total_vnd"] = LINES_SUM_VND - 1

        response = client.post("/bills", headers=actor_headers(), json=payload)

        assert response.status_code == 422, response.text
        assert response.json()["code"] == "bill_items_total_mismatch"

    def test_the_refusal_names_both_numbers(self, client):
        """A 422 that does not say which two figures disagree cannot be acted on.

        The client has both numbers already, so printing them leaks nothing it
        did not send; what it buys is a report that reads as an arithmetic
        error rather than as a rejected request.
        """
        payload = bill_payload()
        payload["items_total_vnd"] = LINES_SUM_VND + 40000

        response = client.post("/bills", headers=actor_headers(), json=payload)

        detail = response.json()["detail"]
        assert str(LINES_SUM_VND + 40000) in detail, detail
        assert str(LINES_SUM_VND) in detail, detail

    def test_a_consistent_bill_is_still_accepted(self, client):
        """The fix must refuse disagreement, not refuse bills.

        Without this case the rule above is satisfiable by rejecting
        everything, and the suite would still be green.
        """
        body = create_bill(client)

        assert body["items_total_vnd"] == LINES_SUM_VND

    def test_surcharges_and_discounts_stay_outside_the_sum(self, client):
        """`items_total_vnd` is the lines, matching `read_receipt`.

        A service charge is not an item, and a fix that required the declared
        total to include one would refuse every bill the scanner can actually
        produce. This case fails if the rule is written against the wrong sum.
        """
        payload = bill_payload()
        payload["surcharges"] = [
            {
                "surcharge_key": "s1",
                "kind": "service",
                "amount_vnd": 13500,
                "mode": "proportional",
            }
        ]
        payload["discounts"] = [
            {
                "discount_key": "d1",
                "amount_vnd": 5000,
                "scope": "global_proportional",
                "item_key": None,
            }
        ]

        response = client.post("/bills", headers=actor_headers(), json=payload)

        assert response.status_code == 201, response.text
        assert response.json()["items_total_vnd"] == LINES_SUM_VND

    def test_a_single_line_bill_must_still_add_up(self, client):
        """One item, so the sum is the line -- and the rule still applies.

        Written because a rule implemented as "compare against the first item"
        or as "only check when there are several" passes every case above.
        """
        payload = bill_payload(
            items=[
                {
                    "item_key": "i1",
                    "name": "Cơm tấm",
                    "quantity": 2,
                    "unit_price_vnd": 45000,
                    "line_total_vnd": 90000,
                    "suggested_participant_ids": [str(SENDER_ID), str(ADVANCER_ID)],
                }
            ]
        )
        payload["items_total_vnd"] = 45000

        response = client.post("/bills", headers=actor_headers(), json=payload)

        assert response.status_code == 422, response.text
        assert response.json()["code"] == "bill_items_total_mismatch"


class TestWhatTheClientReadsBackAddsUp:
    def test_the_stored_total_is_the_sum_of_the_stored_lines(self, client):
        """The invariant stated on the response rather than on the request.

        The cases above pin the door. This one pins the property a reader
        actually depends on, and it is written to be re-runnable against any
        bill: whatever `GET /bills/{id}` reports as `items_total_vnd` is the
        sum of the `line_total_vnd` values it reports beside it. A future write
        path that reaches storage without passing the door fails here.
        """
        created = create_bill(client)

        body = client.get(f"/bills/{created['id']}", headers=actor_headers()).json()

        assert body["items_total_vnd"] == sum(
            item["line_total_vnd"] for item in body["items"]
        )

    def test_the_split_screen_and_the_bill_screen_report_the_same_meal(self, client):
        """The two figures a person sees, compared to each other.

        `total_amount_vnd` comes from `allocator_input_from_bill` reading the
        stored lines; `items_total_vnd` comes from the request body. With no
        printed total to override it, agreement between them is exactly the
        property whose absence this file was written for.
        """
        created = create_bill(client, printed_total_vnd=None)
        bill_id = created["id"]
        client.put(
            f"/bills/{bill_id}/assignments",
            headers=actor_headers(),
            json={
                "assignments": [
                    {"item_key": "i1", "participant_ids": [str(SENDER_ID)]},
                    {"item_key": "i2", "participant_ids": [str(ADVANCER_ID)]},
                ]
            },
        )

        split = client.post(
            f"/bills/{bill_id}/split",
            headers=actor_headers(),
            json={"for_ledger": False, "paid_by_id": str(ADVANCER_ID)},
        )

        assert split.status_code == 200, split.text
        assert split.json()["total_amount_vnd"] == created["items_total_vnd"]
