"""The same dish twice is an ordinary receipt, not a malformed one.

`uq_bill_items_bill_item_key` is right to refuse a second row for one key. What
was wrong is the shape of the refusal: `create_bill` was the only write path in
this feature that did not translate `IntegrityError` into `RepositoryConflict`,
so the violation escaped as a raw psycopg error and FastAPI answered 500 -- a
status `routes/bills.py` does not declare in its `responses` map. Its sibling
`confirm_bill_assignments` already translated and already answered 409.

Why it is not an exotic case: a Vietnamese bill repeats dish names constantly.
"Bia Sài Gòn" printed on two lines is a normal receipt. Whoever builds the bill
screen must mint `item_key` themselves, and any key derived from the dish name
collides on the second line.

This file proves the ROUTE's half only: given a repository that reports the
conflict, the answer is 409 and not 500. That the real table produces that
conflict at all is a claim about PostgreSQL, and it is proved against
PostgreSQL in `tests/postgres/test_bill_duplicate_item_key_postgres.py`. The
fake here is taught to mirror the constraint, and a fake that has been taught
something is not evidence about the database.
"""

from __future__ import annotations

from tests.api.helpers import ADVANCER_ID, CONTEXT_ID, actor_headers


def repeated_line_payload():
    return {
        "context_id": str(CONTEXT_ID),
        "printed_total_vnd": 60000,
        "items_total_vnd": 60000,
        "confidence": 88,
        "needs_review": False,
        "items": [
            {
                "item_key": "bia-sai-gon",
                "name": "Bia Sài Gòn",
                "quantity": 1,
                "unit_price_vnd": 30000,
                "line_total_vnd": 30000,
                "suggested_participant_ids": [str(ADVANCER_ID)],
            },
            {
                "item_key": "bia-sai-gon",
                "name": "Bia Sài Gòn",
                "quantity": 1,
                "unit_price_vnd": 30000,
                "line_total_vnd": 30000,
                "suggested_participant_ids": [str(ADVANCER_ID)],
            },
        ],
    }


def test_a_repeated_item_key_is_refused_with_409_not_500(client):
    response = client.post(
        "/bills", headers=actor_headers(), json=repeated_line_payload()
    )

    assert response.status_code == 409, response.text


def test_the_refusal_names_the_duplicate_key_rather_than_leaking_the_constraint(
    client,
):
    """A caller has to be able to act on this, and a psycopg DETAIL line
    carries the bill id and the raw constraint name into the client."""

    response = client.post(
        "/bills", headers=actor_headers(), json=repeated_line_payload()
    )

    assert response.json()["code"] == "DUPLICATE_BILL_ITEM_KEY"
    assert "uq_bill_items" not in response.text
