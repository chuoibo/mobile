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


def test_an_admin_may_not_register_for_somebody_else(client, repository):
    """The claim in section 9.2 is that there is *no admin exception*, and a
    test run with default roles never puts that claim under load. This one
    hands the caller the most privileged role the header vocabulary has."""
    response = _register(
        client, actor_id=ADVANCER_ID, recipient_id=OTHER_ID, roles="member,group_admin"
    )

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "permission_denied"
    assert repository.bank_recipients == {}


def test_an_admin_may_not_read_somebody_elses_account(client):
    _register(client, actor_id=OTHER_ID)

    response = client.get(
        f"/bank-recipients/{OTHER_ID}",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member,group_admin"),
    )

    assert response.status_code == 403, response.text
    assert "0000000000TEST" not in response.text


def test_a_request_with_no_actor_at_all_is_refused_as_unauthenticated(client):
    """401, not 403. An anonymous caller has not been denied a thing it asked
    for -- it has not said who it is, and the two answers tell a prober very
    different amounts about who exists."""
    response = client.post(
        "/bank-recipients",
        json={"recipient_id": str(ADVANCER_ID), **DESTINATION},
    )

    assert response.status_code == 401, response.text


def test_an_account_name_may_be_left_out(client):
    """Plenty of people do not know the exact name their bank prints, and the
    transfer works without it. Requiring it would block the registration this
    route exists to unblock."""
    response = client.post(
        "/bank-recipients",
        headers=actor_headers(),
        json={
            "recipient_id": str(ADVANCER_ID),
            "bank_bin": "970418",
            "account_number": "0000000000TEST",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["account_name"] is None


def test_a_client_may_not_stamp_its_own_confirmation_time(client):
    """`confirmed_at` is the server's record that the owner asked for this. A
    timestamp sent by a client is a claim about an event, not the event."""
    response = _register(client, confirmed_at="2020-01-01T00:00:00+00:00")

    assert response.status_code == 422, response.text


def test_a_malformed_recipient_id_is_refused_before_it_reaches_the_database(client):
    """422 naming the field, not a 500 out of the driver."""
    response = client.post(
        "/bank-recipients",
        headers=actor_headers(),
        json={"recipient_id": "khong-phai-uuid", **DESTINATION},
    )

    assert response.status_code == 422, response.text


def test_each_person_keeps_their_own_destination(client, repository):
    _register(client, actor_id=ADVANCER_ID)
    _register(client, actor_id=OTHER_ID, account_number="1111111111TEST")

    active = repository.load_bank_recipients(frozenset({ADVANCER_ID, OTHER_ID}))

    assert active[ADVANCER_ID].account_number == "0000000000TEST"
    assert active[OTHER_ID].account_number == "1111111111TEST"
    assert active[ADVANCER_ID].id != active[OTHER_ID].id


def test_a_person_who_never_registered_does_not_disturb_one_who_did(client, repository):
    """The batch gate asks about everyone in the round at once. A stranger in
    that set must come back absent, not empty-handed for the whole query."""
    _register(client, actor_id=ADVANCER_ID)

    active = repository.load_bank_recipients(frozenset({ADVANCER_ID, uuid.uuid4()}))

    assert set(active) == {ADVANCER_ID}


def test_every_shape_the_database_check_would_reject_is_refused_here_first(client):
    """The API's regexes and the two CHECK constraints have to agree. Anything
    in this list that got through would arrive at PostgreSQL as an
    IntegrityError and reach the caller as a 500 for a plainly malformed body.

    The mirror of this list, asserted against the real constraints, is
    `test_the_database_names_the_constraint_the_api_already_refused` in
    tests/postgres.
    """
    for bad_bin in ("", "   ", "97041", "9704155", "97041a"):
        response = _register(client, bank_bin=bad_bin)
        assert response.status_code == 422, (bad_bin, response.text)
        assert response.json()["code"] == "INVALID_BANK_BIN"

    for bad_account in (
        "",
        # Whitespace is stripped, so a field holding only spaces is empty --
        # and empty must not reach a NOT NULL column as "".
        "   ",
        "0123-4567",
        "1" * 20,
        # Nor may spaces smuggle an over-long number past the column width:
        # this is 20 characters once the padding is gone.
        " ".join("1" * 20),
    ):
        response = _register(client, account_number=bad_account)
        assert response.status_code == 422, (bad_account, response.text)
        assert response.json()["code"] == "INVALID_ACCOUNT_NUMBER"

    # A name of pure whitespace is not silently turned into "no name": an
    # envelope with a blank holder line gives the sender nothing to compare
    # against in their banking app.
    blank_name = _register(client, account_name="   ")
    assert blank_name.status_code == 422, blank_name.text
    assert blank_name.json()["code"] == "INVALID_ACCOUNT_NAME"


def test_an_account_number_spaced_the_way_a_banking_app_shows_it_is_accepted(client):
    """Deliberate, and the opposite of what a stricter reading would do.

    Vietnamese banking apps display the number in groups -- "0000 0000 00TE ST"
    -- and that is exactly what a person copies. Refusing it as malformed makes
    somebody fight the form while the digits they pasted were right all along.
    Pinned here because it looks like a validation hole and is not one.
    """
    response = _register(client, account_number="0123 4567")

    assert response.status_code == 201, response.text
    assert response.json()["account_number"] == "01234567"


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


# --- The person-scoped shape of the same route -------------------------------
#
# `POST /bank-recipients` names its subject in the body, so "change my account"
# and "change yours" are the same request with one field different -- the check
# in the service is the only thing between them. `PUT /people/{id}/bank-recipient`
# puts the subject in the path, where it is part of the address rather than part
# of the payload. That is a narrower surface, not a nicer URL: a body field is
# easy to set by accident, and a path is not.
#
# It is an alias, not a second store. `test_the_two_shapes_are_one_destination`
# is the case that would catch it becoming a second write path into the same
# table, which is the failure this consolidation exists to prevent.


def _put_destination(client, *, person_id=ADVANCER_ID, actor_id=None, roles=None, **fields):
    body = dict(DESTINATION)
    body.update(fields)
    actor_id = actor_id or person_id
    headers = (
        actor_headers(actor_id=actor_id, roles=roles)
        if roles
        else actor_headers(actor_id=actor_id)
    )
    return client.put(
        f"/people/{person_id}/bank-recipient", headers=headers, json=body
    )


def test_the_person_scoped_route_registers_a_destination(client):
    response = _put_destination(client)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["recipient_id"] == str(ADVANCER_ID)
    assert body["account_number"] == "0000000000TEST"
    assert body["bank_name"] == "BIDV"
    assert body["confirmed_at"]


def test_the_person_scoped_route_reads_back(client):
    _put_destination(client)

    response = client.get(
        f"/people/{ADVANCER_ID}/bank-recipient", headers=actor_headers()
    )

    assert response.status_code == 200, response.text
    assert response.json()["account_number"] == "0000000000TEST"


def test_the_two_shapes_are_one_destination(client):
    """The reason both shapes may coexist: they are one row, one store, one
    answer. Two write paths that each kept their own state would show two
    different accounts for the same person depending on which screen asked --
    and one of those screens would be sending somebody's money to the stale one.
    """
    written = _put_destination(client)

    read_the_other_way = client.get(
        f"/bank-recipients/{ADVANCER_ID}", headers=actor_headers()
    )

    assert read_the_other_way.status_code == 200, read_the_other_way.text
    assert read_the_other_way.json()["id"] == written.json()["id"]

    # And back the other way: written through the collection route, read
    # through the person-scoped one.
    replaced = _register(client, account_number="1111111111TEST")
    assert replaced.status_code == 201, replaced.text
    scoped = client.get(
        f"/people/{ADVANCER_ID}/bank-recipient", headers=actor_headers()
    )
    assert scoped.json()["id"] == replaced.json()["id"]
    assert scoped.json()["account_number"] == "1111111111TEST"


def test_the_person_scoped_route_repeated_unchanged_answers_200(client):
    first = _put_destination(client)
    assert first.status_code == 201, first.text

    again = _put_destination(client)

    assert again.status_code == 200, again.text
    assert again.json()["id"] == first.json()["id"]


def test_the_person_scoped_route_refuses_registering_for_somebody_else(
    client, repository
):
    """The same rule as the collection route, asserted on the shape where the
    subject is in the address. Admin role included, because section 9.2 has no
    exception for one."""
    response = client.put(
        f"/people/{OTHER_ID}/bank-recipient",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member,group_admin"),
        json=DESTINATION,
    )

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "permission_denied"
    assert repository.bank_recipients == {}


def test_the_person_scoped_route_refuses_reading_somebody_else(client):
    _put_destination(client, person_id=OTHER_ID)

    response = client.get(
        f"/people/{OTHER_ID}/bank-recipient",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member,group_admin"),
    )

    assert response.status_code == 403, response.text
    assert "0000000000TEST" not in response.text


def test_the_person_scoped_route_refuses_a_guest(client):
    response = _put_destination(client, roles="guest")

    assert response.status_code == 403, response.text


def test_the_person_scoped_route_without_an_actor_is_unauthenticated(client):
    response = client.put(
        f"/people/{ADVANCER_ID}/bank-recipient", json=DESTINATION
    )

    assert response.status_code == 401, response.text


def test_the_person_scoped_body_may_not_name_a_subject(client, repository):
    """The whole point of putting the subject in the path. If the body could
    also carry a `recipient_id`, this shape would inherit exactly the footgun
    it exists to remove -- and worse, two places to look for the answer.
    """
    response = client.put(
        f"/people/{ADVANCER_ID}/bank-recipient",
        headers=actor_headers(),
        json={"recipient_id": str(OTHER_ID), **DESTINATION},
    )

    assert response.status_code == 422, response.text
    assert repository.bank_recipients == {}


def test_a_malformed_person_id_is_refused(client):
    response = client.put(
        "/people/khong-phai-uuid/bank-recipient",
        headers=actor_headers(),
        json=DESTINATION,
    )

    assert response.status_code == 422, response.text


def test_the_person_scoped_route_refuses_a_malformed_destination(client):
    response = _put_destination(client, bank_bin="97041")

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "INVALID_BANK_BIN"


def test_nobody_registered_yet_reads_as_not_found_on_the_person_scoped_route(client):
    response = client.get(
        f"/people/{ADVANCER_ID}/bank-recipient", headers=actor_headers()
    )

    assert response.status_code == 404, response.text
    assert response.json()["code"] == "bank_recipient_not_found"
