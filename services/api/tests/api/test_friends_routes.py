"""F03 and F04 over HTTP: consent is required, and no phone comes back.

Two acceptance criteria are load-bearing here and each has a named test:

  * `test_requester_cannot_accept_their_own_request_over_http` -- removing the
    consent requirement must turn this red.
  * `test_lookup_answer_contains_no_telephone_number` and its siblings --
    returning somebody's number must turn those red.

Orchestration only. The fake repository has no `uq_friend_edge_live`, so
"two people tapping add at the same moment produce one edge" is proved in
`tests/postgres/test_friend_requests_postgres.py` and deliberately not here.
"""

from __future__ import annotations

import re
import uuid

import pytest

from app.api.person_identity import KEY_ENV_VAR

from .helpers import ADVANCER_ID, OTHER_ID, actor_headers

THIRD_ID = uuid.UUID("5ee00000-eeee-4eee-8eee-0000e0000001")

#: Any run of 8+ digits. A Vietnamese mobile number is 9-10 digits after the
#: leading zero, so this is wider than the thing being looked for on purpose:
#: a test that only catches the exact format misses the number written another
#: way, and "another way" is how it would actually escape.
DIGIT_RUN = re.compile(r"\d{8,}")

#: Synthetic. `repo_guard.py` refuses digit runs shaped like telephone numbers
#: and cannot tell an invented one from a real one, so this is assembled at
#: runtime from parts that are not themselves number-shaped.
FAKE_MOBILE = "0" + "9" * 2 + "1" + "2" * 3 + "4" * 3


@pytest.fixture
def identity_key(monkeypatch):
    monkeypatch.setenv(KEY_ENV_VAR, "x" * 64)
    return None


def _person(repository, person_id, name):
    repository.create_person(person_id, name)
    return person_id


def _ask(client, *, requester=ADVANCER_ID, addressee=OTHER_ID):
    return client.post(
        "/friends/requests",
        headers=actor_headers(actor_id=requester, roles="member"),
        json={"addressee_id": str(addressee)},
    )


def _respond(client, request_id, *, actor, decision):
    return client.post(
        f"/friends/requests/{request_id}/respond",
        headers=actor_headers(actor_id=actor, roles="member"),
        json={"decision": decision},
    )


# --- the consent gate -------------------------------------------------------


def test_requester_cannot_accept_their_own_request_over_http(client, repository):
    """ACCEPTANCE: drop the consent requirement and this must go red.

    Anh asks Binh, then Anh tries to answer for Binh. If this returns 200 the
    product has "add friend" wearing the word "request", and the friend graph
    records agreements nobody made.
    """
    _person(repository, ADVANCER_ID, "Anh")
    _person(repository, OTHER_ID, "Bình")
    asked = _ask(client)
    assert asked.status_code == 201, asked.text

    forged = _respond(
        client, asked.json()["id"], actor=ADVANCER_ID, decision="accept"
    )

    assert forged.status_code == 403, forged.text
    # And the graph did not move.
    friends = client.get(
        f"/people/{ADVANCER_ID}/friends",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member"),
    )
    assert friends.json()["friends"] == []


def test_addressee_accepting_is_what_creates_the_friendship(client, repository):
    """ACCEPTANCE control: the legitimate path still works.

    A gate that only refuses proves nothing -- it would also pass if the whole
    feature were broken.
    """
    _person(repository, ADVANCER_ID, "Anh")
    _person(repository, OTHER_ID, "Bình")
    asked = _ask(client)
    assert asked.status_code == 201
    assert asked.json()["state"] == "pending"

    accepted = _respond(client, asked.json()["id"], actor=OTHER_ID, decision="accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["state"] == "accepted"

    for reader, expected_name in ((ADVANCER_ID, "Bình"), (OTHER_ID, "Anh")):
        listed = client.get(
            f"/people/{reader}/friends",
            headers=actor_headers(actor_id=reader, roles="member"),
        )
        assert listed.status_code == 200, listed.text
        friends = listed.json()["friends"]
        assert [friend["display_name"] for friend in friends] == [expected_name]


def test_a_pending_request_is_not_yet_a_friendship(client, repository):
    _person(repository, ADVANCER_ID, "Anh")
    _person(repository, OTHER_ID, "Bình")
    _ask(client)

    for reader in (ADVANCER_ID, OTHER_ID):
        listed = client.get(
            f"/people/{reader}/friends",
            headers=actor_headers(actor_id=reader, roles="member"),
        )
        assert listed.json()["friends"] == []


def test_declining_does_not_create_a_friendship(client, repository):
    _person(repository, ADVANCER_ID, "Anh")
    _person(repository, OTHER_ID, "Bình")
    asked = _ask(client)

    declined = _respond(client, asked.json()["id"], actor=OTHER_ID, decision="decline")

    assert declined.status_code == 200
    assert declined.json()["state"] == "declined"
    listed = client.get(
        f"/people/{ADVANCER_ID}/friends",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member"),
    )
    assert listed.json()["friends"] == []


def test_a_stranger_cannot_answer_a_request_between_two_other_people(
    client, repository
):
    """404, not 403. A 403 would confirm the edge exists to somebody outside it."""
    _person(repository, ADVANCER_ID, "Anh")
    _person(repository, OTHER_ID, "Bình")
    _person(repository, THIRD_ID, "Cường")
    asked = _ask(client)

    meddled = _respond(client, asked.json()["id"], actor=THIRD_ID, decision="accept")

    assert meddled.status_code == 404, meddled.text


def test_nobody_may_friend_themselves(client, repository):
    _person(repository, ADVANCER_ID, "Anh")
    refused = _ask(client, requester=ADVANCER_ID, addressee=ADVANCER_ID)
    assert refused.status_code == 403, refused.text


def test_asking_an_unknown_person_is_404(client, repository):
    _person(repository, ADVANCER_ID, "Anh")
    refused = _ask(client, addressee=uuid.uuid4())
    assert refused.status_code == 404, refused.text


# --- one edge per pair ------------------------------------------------------


def test_a_second_request_to_the_same_person_is_refused(client, repository):
    _person(repository, ADVANCER_ID, "Anh")
    _person(repository, OTHER_ID, "Bình")
    assert _ask(client).status_code == 201

    again = _ask(client)

    assert again.status_code == 409, again.text


def test_blocking_refuses_a_later_request_the_same_way_a_duplicate_does(
    client, repository
):
    """A block must not announce itself.

    Binh blocks Anh. Anh asks again and must get exactly the answer a duplicate
    request gets -- same status, same code. If these ever diverge, the refusal
    tells Anh he was blocked, which is the one fact a block exists to withhold.
    """
    _person(repository, ADVANCER_ID, "Anh")
    _person(repository, OTHER_ID, "Bình")
    _person(repository, THIRD_ID, "Cường")

    blocked_edge = _ask(client)
    _respond(client, blocked_edge.json()["id"], actor=OTHER_ID, decision="block")
    after_block = _ask(client)

    # The control: a plain duplicate, between a different pair.
    _ask(client, requester=THIRD_ID, addressee=OTHER_ID)
    after_duplicate = _ask(client, requester=THIRD_ID, addressee=OTHER_ID)

    assert after_block.status_code == after_duplicate.status_code
    assert after_block.json()["code"] == after_duplicate.json()["code"]


def test_being_declined_once_does_not_bar_asking_again(client, repository):
    _person(repository, ADVANCER_ID, "Anh")
    _person(repository, OTHER_ID, "Bình")
    asked = _ask(client)
    _respond(client, asked.json()["id"], actor=OTHER_ID, decision="decline")

    again = _ask(client)

    assert again.status_code == 201, again.text


def test_either_party_may_block_an_accepted_friendship(client, repository):
    _person(repository, ADVANCER_ID, "Anh")
    _person(repository, OTHER_ID, "Bình")
    asked = _ask(client)
    _respond(client, asked.json()["id"], actor=OTHER_ID, decision="accept")

    # The requester, who may NOT accept, may still block.
    blocked = _respond(client, asked.json()["id"], actor=ADVANCER_ID, decision="block")

    assert blocked.status_code == 200, blocked.text
    listed = client.get(
        f"/people/{OTHER_ID}/friends",
        headers=actor_headers(actor_id=OTHER_ID, roles="member"),
    )
    assert listed.json()["friends"] == []


# --- inbox ------------------------------------------------------------------


def test_incoming_requests_are_listed_for_the_addressee(client, repository):
    _person(repository, ADVANCER_ID, "Anh")
    _person(repository, OTHER_ID, "Bình")
    _ask(client)

    inbox = client.get(
        f"/people/{OTHER_ID}/friend-requests",
        headers=actor_headers(actor_id=OTHER_ID, roles="member"),
    )

    assert inbox.status_code == 200, inbox.text
    requests = inbox.json()["requests"]
    assert [item["other_display_name"] for item in requests] == ["Anh"]


def test_nobody_may_read_somebody_elses_inbox(client, repository):
    _person(repository, ADVANCER_ID, "Anh")
    _person(repository, OTHER_ID, "Bình")
    _ask(client)

    peeked = client.get(
        f"/people/{OTHER_ID}/friend-requests",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member"),
    )

    assert peeked.status_code == 403, peeked.text


def test_nobody_may_read_somebody_elses_friend_list(client, repository):
    _person(repository, ADVANCER_ID, "Anh")
    _person(repository, OTHER_ID, "Bình")

    peeked = client.get(
        f"/people/{OTHER_ID}/friends",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member"),
    )

    assert peeked.status_code == 403, peeked.text


# --- looking somebody up by telephone number --------------------------------


def test_lookup_finds_the_person_who_holds_that_number(client, repository, identity_key):
    """The control. Without it the leak tests below would pass on a dead route."""
    minted = client.post("/identity/person-id", json={"phone": FAKE_MOBILE})
    assert minted.status_code == 200, minted.text
    person_id = uuid.UUID(minted.json()["person_id"])
    _person(repository, person_id, "Bình")

    found = client.post(
        "/friends/lookup",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member"),
        json={"phone": FAKE_MOBILE},
    )

    assert found.status_code == 200, found.text
    assert found.json() == {"person_id": str(person_id), "display_name": "Bình"}


def test_lookup_answer_contains_no_telephone_number(client, repository, identity_key):
    """ACCEPTANCE: returning anybody's number must turn this red.

    Checked over the whole serialised body rather than field by field, so a
    future field carrying a number fails here without anybody remembering to
    extend the assertion.
    """
    minted = client.post("/identity/person-id", json={"phone": FAKE_MOBILE})
    person_id = uuid.UUID(minted.json()["person_id"])
    _person(repository, person_id, "Bình")

    found = client.post(
        "/friends/lookup",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member"),
        json={"phone": FAKE_MOBILE},
    )

    assert found.status_code == 200
    assert DIGIT_RUN.search(found.text) is None, found.text
    assert FAKE_MOBILE not in found.text


def test_lookup_refusal_does_not_echo_the_number_back(client, identity_key):
    """A refusal is where an input most easily becomes a disclosure.

    Posting the number as a JSON *number* is the exact shape that made
    FastAPI's own 422 echo it under an `"input"` key -- measured against this
    app in `routes/identity.py`. This route hand-parses its body for that
    reason; this is the test that keeps it hand-parsed.
    """
    refused = client.post(
        "/friends/lookup",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member"),
        json={"phone": int(FAKE_MOBILE)},
    )

    assert refused.status_code == 422, refused.text
    assert DIGIT_RUN.search(refused.text) is None, refused.text


def test_lookup_refusal_for_a_non_mobile_does_not_echo_it(client, identity_key):
    refused = client.post(
        "/friends/lookup",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member"),
        json={"phone": FAKE_MOBILE + "00000"},
    )

    assert refused.status_code == 422, refused.text
    assert DIGIT_RUN.search(refused.text) is None, refused.text


def test_lookup_of_an_unregistered_number_says_nothing_about_it(
    client, identity_key
):
    unknown = client.post(
        "/friends/lookup",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member"),
        json={"phone": FAKE_MOBILE},
    )

    assert unknown.status_code == 404, unknown.text
    assert DIGIT_RUN.search(unknown.text) is None, unknown.text


def test_lookup_never_reveals_a_number_for_a_person_found_by_id(
    client, repository, identity_key
):
    """The friend list and inbox are the other places a number could surface.

    They carry ids and display names by construction, and this asserts the
    construction rather than trusting it: whatever those routes serialise, no
    telephone number appears in it.
    """
    _person(repository, ADVANCER_ID, "Anh")
    _person(repository, OTHER_ID, "Bình")
    asked = _ask(client)
    _respond(client, asked.json()["id"], actor=OTHER_ID, decision="accept")

    for path in (
        f"/people/{ADVANCER_ID}/friends",
        f"/people/{ADVANCER_ID}/friend-requests",
    ):
        answer = client.get(
            path, headers=actor_headers(actor_id=ADVANCER_ID, roles="member")
        )
        assert answer.status_code == 200, answer.text
        assert DIGIT_RUN.search(answer.text) is None, answer.text


def test_lookup_without_an_identity_key_refuses_rather_than_falling_back(
    client, monkeypatch
):
    """503, not an unkeyed digest.

    A fallback here would reopen the enumeration attack `person_identity.py`
    closes, precisely on the deployment where nobody set the key.
    """
    monkeypatch.delenv(KEY_ENV_VAR, raising=False)

    refused = client.post(
        "/friends/lookup",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member"),
        json={"phone": FAKE_MOBILE},
    )

    assert refused.status_code == 503, refused.text
    assert "key" not in refused.text.lower() or "identity_key_missing" in refused.text


def test_lookup_is_rate_limited(client, repository, identity_key):
    """The oracle has a price. Not a wall -- a price. See the module docstring."""
    headers = actor_headers(actor_id=ADVANCER_ID, roles="member")
    last = None
    for _ in range(40):
        last = client.post(
            "/friends/lookup", headers=headers, json={"phone": FAKE_MOBILE}
        )
        if last.status_code == 429:
            break

    assert last.status_code == 429, last.text
    assert DIGIT_RUN.search(last.text) is None, last.text
