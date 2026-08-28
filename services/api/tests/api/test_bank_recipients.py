"""The route that gives the money somewhere to land.

Nothing in the HTTP surface wrote `bank_recipients`, so no batch could ever
freeze: `POST /batches` answered `recipient_setup_incomplete` forever, and the
mobile end-to-end test had to reach past the API and INSERT the row itself with
a Python script. Every green test above this line was green about a product
that could not take a single dong off anybody.

These cover orchestration only -- the fake repository has no partial unique
index, so "changing an account leaves exactly one active row" is proved in
`tests/postgres/test_bank_recipient_routes_postgres.py` and not here.
"""

from __future__ import annotations

import uuid

from .helpers import (
    ADVANCER_ID,
    CONTEXT_ID,
    OTHER_ID,
    actor_headers,
    propose_and_confirm,
)

# Synthetic: a real Napas BIN (BIDV) with an account number that is not a real
# account. Nothing in this repository may carry a real one.
DESTINATION = {
    "bank_bin": "970418",
    "account_number": "0000000000TEST",
    "account_name": "NGUYEN VAN NAM",
}


def _register(client, *, actor_id=ADVANCER_ID, recipient_id=None, roles=None, **fields):
    body = {"recipient_id": str(recipient_id or actor_id), **DESTINATION}
    body.update(fields)
    headers = (
        actor_headers(actor_id=actor_id, roles=roles)
        if roles
        else actor_headers(actor_id=actor_id)
    )
    return client.post("/bank-recipients", headers=headers, json=body)


def test_a_person_registers_where_their_money_should_land(client):
    response = _register(client)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["recipient_id"] == str(ADVANCER_ID)
    assert body["bank_bin"] == "970418"
    assert body["account_number"] == "0000000000TEST"
    assert body["account_name"] == "NGUYEN VAN NAM"
    assert uuid.UUID(body["id"])
    assert body["confirmed_at"]


def test_the_registration_reads_back(client):
    """The acceptance criterion, stated as a test: written over HTTP, read over
    HTTP. A write nobody can read back is indistinguishable from a write that
    did not happen."""
    _register(client)

    response = client.get(f"/bank-recipients/{ADVANCER_ID}", headers=actor_headers())

    assert response.status_code == 200, response.text
    assert response.json()["account_number"] == "0000000000TEST"


def test_a_bank_code_becomes_a_name_a_person_can_act_on(client):
    """A BIN is a routing code. Somebody has to pick the right bank inside
    their banking app, so the answer has to say BIDV."""
    body = _register(client).json()

    assert body["bank_name"] == "BIDV"
    assert body["bank_recognised"] is True


def test_an_unfamiliar_bank_code_is_labelled_as_a_code_rather_than_refused(client):
    """The BIN table is deliberately not exhaustive. Refusing an unlisted code
    would lock out anyone whose bank we simply have not listed, and inventing a
    name for it would send them confidently into the wrong app. So: accept it,
    say it is a code, and let the caller warn."""
    body = _register(client, bank_bin="999999").json()

    assert body["bank_recognised"] is False
    assert body["bank_name"] == "Mã ngân hàng 999999"


def test_nobody_has_registered_yet_reads_as_not_found(client):
    response = client.get(f"/bank-recipients/{ADVANCER_ID}", headers=actor_headers())

    assert response.status_code == 404, response.text
    assert response.json()["code"] == "bank_recipient_not_found"


def test_registering_an_account_for_somebody_else_is_refused(client, repository):
    """Section 9.2, and one of the few rules in the spec with no exception for
    an admin: nobody adds or changes another person's bank account. Getting
    this wrong redirects a whole collection round into the attacker's account."""
    response = _register(client, actor_id=ADVANCER_ID, recipient_id=OTHER_ID)

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "permission_denied"
    assert repository.bank_recipients == {}


def test_reading_somebody_elses_account_is_refused(client):
    _register(client, actor_id=OTHER_ID)

    response = client.get(f"/bank-recipients/{OTHER_ID}", headers=actor_headers())

    assert response.status_code == 403, response.text
    # And the refusal does not leak what it refused.
    assert "0000000000TEST" not in response.text


def test_a_guest_may_not_register_an_account(client):
    """A bearer token is a capability, not an identity. Section 9.2 rules out
    using one for this specific action by name."""
    response = _register(client, roles="guest")

    assert response.status_code == 403, response.text


def test_a_bank_code_that_is_not_six_digits_is_refused(client):
    response = _register(client, bank_bin="97041")

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "INVALID_BANK_BIN"


def test_an_account_number_with_punctuation_is_refused(client):
    # repo-guard: allow=long-number reason=synthetic-test-fixture-never-real-participant-data
    response = _register(client, account_number="0000-0000-00")

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "INVALID_ACCOUNT_NUMBER"


def test_an_account_number_wider_than_the_column_is_refused(client):
    response = _register(client, account_number="1" * 20)

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "INVALID_ACCOUNT_NUMBER"


def test_changing_the_account_replaces_what_the_next_batch_will_use(client):
    first = _register(client).json()

    second = _register(client, account_number="1111111111TEST")

    assert second.status_code == 201, second.text
    assert second.json()["id"] != first["id"], "a change must be a new row"
    read_back = client.get(f"/bank-recipients/{ADVANCER_ID}", headers=actor_headers())
    assert read_back.json()["account_number"] == "1111111111TEST"


def test_registering_the_same_account_twice_changes_nothing(client):
    """Adding or changing a destination is a material event: section 8.5 says
    it must be audited and the affected parties told. A retry that re-sends the
    same digits changed nothing, and must not fire that."""
    first = _register(client).json()

    second = _register(client)

    assert second.status_code == 200, second.text
    assert second.json()["id"] == first["id"]
    assert second.json()["confirmed_at"] == first["confirmed_at"]


def test_the_same_account_with_stray_spaces_is_still_the_same_account(client):
    first = _register(client).json()

    second = _register(client, account_number=" 0000 0000 00TEST ")

    assert second.status_code == 200, second.text
    assert second.json()["id"] == first["id"]


def test_an_account_registered_over_http_lets_a_batch_freeze(client):
    """The reason this route exists, asserted end to end through the API.

    The refusal is asserted first. Without it this test would pass on a server
    that had simply stopped checking whether the money has anywhere to go --
    which is the failure the check exists to prevent, not the one being fixed.
    """
    confirmed = propose_and_confirm(client)
    batch_body = {
        "context_id": str(CONTEXT_ID),
        "expense_version_ids": [confirmed["expense_version_id"]],
        "due_at": "2030-09-27T12:00:00+07:00",
    }

    refused = client.post("/batches", headers=actor_headers(), json=batch_body)
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] in {
        "UNREADY_RECIPIENT_CHOICE_REQUIRED",
        "recipient_setup_incomplete",
    }

    assert _register(client).status_code == 201

    frozen = client.post("/batches", headers=actor_headers(), json=batch_body)
    assert frozen.status_code == 201, frozen.text
    assert frozen.json()["obligations"]
