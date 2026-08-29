"""A real Vietnamese restaurant bill carries VAT and a service charge.

The rd-be-03 contract declared `surcharges` and `discounts`, and
`app/domain/bill.py` already honours them -- it passes both straight through to
the frozen allocator. What was missing is any way to reach that code: the wire
schema had no such fields, no column stored them, and `service.split_bill` fed
the projection two hardcoded empty lists. So the half of the contract that
handles the 96.480d of VAT and service charge on a 816.480d bill was written,
tested at the domain layer, and unreachable.

The failure mode this pins is not "a feature is missing". It is that the two
available answers are both wrong in a money product:

  * keep `printed_total_vnd` = 816.480 and the allocator refuses the bill with
    RECONCILIATION_MISMATCH, because the lines only reach 720.000;
  * drop `printed_total_vnd` and the split succeeds at 720.000 -- collecting
    96.480d less than the paper the group just paid.

Amounts here are the ordinary ones off a quan an bill: 5% service on the food,
then 8% VAT on food-plus-service. They are chosen so the proportional split
lands on whole dong, so a wrong per-person number cannot hide behind rounding.
The discount case below is the opposite on purpose: it does not divide evenly,
so it also pins which participant absorbs the leftover dong.
"""

from __future__ import annotations

from tests.api.helpers import ADVANCER_ID, CONTEXT_ID, SENDER_ID, actor_headers

# 420.000 shared by two + 300.000 eaten by one = 720.000 of food.
LAU_BO_VND = 420000
BIA_VND = 300000
ITEMS_TOTAL_VND = LAU_BO_VND + BIA_VND

# 5% service on the food, then 8% VAT on food + service.
SERVICE_CHARGE_VND = 36000
VAT_VND = 60480
PRINTED_TOTAL_VND = ITEMS_TOTAL_VND + SERVICE_CHARGE_VND + VAT_VND  # 816.480


def bill_payload(*, surcharges=None, discounts=None, printed_total_vnd=None):
    return {
        "context_id": str(CONTEXT_ID),
        "printed_total_vnd": (
            PRINTED_TOTAL_VND if printed_total_vnd is None else printed_total_vnd
        ),
        "items_total_vnd": ITEMS_TOTAL_VND,
        "confidence": 91,
        "needs_review": False,
        "items": [
            {
                "item_key": "lau-bo",
                "name": "Lẩu bò",
                "quantity": 1,
                "unit_price_vnd": LAU_BO_VND,
                "line_total_vnd": LAU_BO_VND,
                "suggested_participant_ids": [str(SENDER_ID), str(ADVANCER_ID)],
            },
            {
                "item_key": "bia-sai-gon",
                "name": "Bia Sài Gòn",
                "quantity": 6,
                "unit_price_vnd": 50000,
                "line_total_vnd": BIA_VND,
                "suggested_participant_ids": [str(ADVANCER_ID)],
            },
        ],
        "surcharges": (
            [
                {
                    "surcharge_key": "phi-phuc-vu",
                    "kind": "service",
                    "amount_vnd": SERVICE_CHARGE_VND,
                    "mode": "proportional",
                },
                {
                    "surcharge_key": "vat",
                    "kind": "vat",
                    "amount_vnd": VAT_VND,
                    "mode": "proportional",
                },
            ]
            if surcharges is None
            else surcharges
        ),
        "discounts": [] if discounts is None else discounts,
    }


def create_bill(client, **kwargs):
    response = client.post(
        "/bills", headers=actor_headers(), json=bill_payload(**kwargs)
    )
    assert response.status_code == 201, response.text
    return response.json()


def confirm_all(client, bill_id):
    response = client.put(
        f"/bills/{bill_id}/assignments",
        headers=actor_headers(),
        json={
            "assignments": [
                {
                    "item_key": "lau-bo",
                    "participant_ids": [str(SENDER_ID), str(ADVANCER_ID)],
                },
                {"item_key": "bia-sai-gon", "participant_ids": [str(ADVANCER_ID)]},
            ]
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def split(client, bill_id, *, for_ledger=True):
    return client.post(
        f"/bills/{bill_id}/split",
        headers=actor_headers(),
        json={"for_ledger": for_ledger, "paid_by_id": str(ADVANCER_ID)},
    )


class TestBillWithServiceChargeAndVat:
    def test_the_four_routes_split_the_bill_the_customer_actually_paid(self, client):
        """Create, confirm, split -- and land on the number on the paper.

        The walk goes through every route the bill screen uses, because the
        break was at the seam between them: the domain projection was correct
        and the wire dropped its input on the way in.
        """

        bill = create_bill(client)
        confirm_all(client, bill["id"])

        response = split(client, bill["id"])

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total_amount_vnd"] == PRINTED_TOTAL_VND
        # 210.000 + 10.500 service + 17.640 VAT, and 510.000 + 25.500 + 42.840.
        assert body["allocation"]["allocations"] == {
            str(SENDER_ID): 238140,
            str(ADVANCER_ID): 578340,
        }

    def test_the_split_sums_to_the_printed_total_exactly(self, client):
        """Money rule 2, restated at the seam that used to lose 96.480d."""

        bill = create_bill(client)
        confirm_all(client, bill["id"])

        allocations = split(client, bill["id"]).json()["allocation"]["allocations"]

        assert sum(allocations.values()) == PRINTED_TOTAL_VND

    def test_dropping_the_surcharges_would_lose_the_vat(self, client):
        """The old behaviour, kept as a control.

        Without the surcharge lines the same items only reach 720.000, so this
        is exactly the 96.480d that used to go uncollected. If this ever starts
        returning the printed total, the surcharges are being invented
        somewhere instead of carried.
        """

        bill = create_bill(
            client, surcharges=[], printed_total_vnd=ITEMS_TOTAL_VND
        )
        confirm_all(client, bill["id"])

        body = split(client, bill["id"]).json()

        assert body["total_amount_vnd"] == ITEMS_TOTAL_VND

    def test_a_bill_that_kept_its_surcharges_can_be_read_back(self, client):
        """GET must echo them, or the bill screen cannot show the VAT line."""

        bill = create_bill(client)

        response = client.get(f"/bills/{bill['id']}", headers=actor_headers())

        assert response.status_code == 200, response.text
        body = response.json()
        assert [
            (surcharge["surcharge_key"], surcharge["kind"], surcharge["amount_vnd"])
            for surcharge in body["surcharges"]
        ] == [
            ("phi-phuc-vu", "service", SERVICE_CHARGE_VND),
            ("vat", "vat", VAT_VND),
        ]


class TestBillWithDiscount:
    """A voucher is the same seam read backwards, and it does not divide.

    16.480d off 720.000d of food leaves each exact share a third of a dong away
    from an integer, so this case also pins the single rounding point: the
    largest remainder wins, and the sum is still the printed total.
    """

    DISCOUNT_VND = 16480
    DISCOUNTED_TOTAL_VND = ITEMS_TOTAL_VND - DISCOUNT_VND  # 703.520 + 96.480 = 800.000

    def _discounted_bill(self, client):
        return create_bill(
            client,
            discounts=[
                {
                    "discount_key": "voucher",
                    "amount_vnd": self.DISCOUNT_VND,
                    "scope": "global_proportional",
                }
            ],
            printed_total_vnd=PRINTED_TOTAL_VND - self.DISCOUNT_VND,
        )

    def test_a_voucher_lowers_every_share_and_still_sums_to_the_paper(self, client):
        bill = self._discounted_bill(client)
        confirm_all(client, bill["id"])

        body = split(client, bill["id"]).json()

        assert body["total_amount_vnd"] == 800000
        assert body["allocation"]["allocations"] == {
            str(SENDER_ID): 233333,
            str(ADVANCER_ID): 566667,
        }
        assert sum(body["allocation"]["allocations"].values()) == 800000

    def test_the_leftover_dong_goes_to_the_larger_remainder(self, client):
        """Not to the advancer by default -- remainder is the primary key."""

        bill = self._discounted_bill(client)
        confirm_all(client, bill["id"])

        body = split(client, bill["id"]).json()

        assert body["allocation"]["rounding_gainers"] == [str(ADVANCER_ID)]
