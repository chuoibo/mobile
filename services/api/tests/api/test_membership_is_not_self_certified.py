"""Membership on the money path must be read from the roster, not from the caller.

`X-Actor-Contexts` is a header the caller writes. `CLAUDE.md` says so plainly,
and says not to build on the assumption it is safe. This file is not a report
that the header is untrusted -- that is already written down. It is about a
narrower thing that is a bug even *under the trust model the header assumes*:

the codebase answers "is this actor in this group?" two different ways, and the
routes that move money picked the weaker one.

    thirty-odd call sites   `self.repository.is_member(context_id, actor.id)`
    five call sites         `context_id in actor.context_ids`

The five are `_bill_for_actor`, `create_bill`, `confirm_expense`, `create_batch`
and the collection board -- exactly the hero path, and nothing else. The first
form asks the database. The second asks the request that is trying to get in,
so `<group> in {<group>}` is true for whatever group the caller typed.

Even a perfect gateway does not close this. A gateway can overwrite `X-Actor-ID`
because it knows who authenticated; it cannot correctly fill `X-Actor-Contexts`
because group membership lives in a table it does not own. So the header cannot
be made right by the boundary it was designed for. Membership is a fact about
`memberships`, and only `memberships` can be asked.

`#235` closed the neighbouring half of this: it stopped a confirmed expense from
charging a *participant* the group does not contain, by reading the roster. The
gate on the *actor* kept reading the header, so today a person who is in no
group at all can write a confirmed expense into someone else's ledger, charging
that group's real members, and then open a collection batch that mails those
members a demand for the money.

There is already a `TestGroupBoundary` in `test_bills.py`, and it is green, and
one of its cases is named `test_an_outsider_cannot_create_a_bill_in_someone_
elses_group`. It passes because its outsider sends `X-Actor-Contexts` naming a
*different* group, so the set membership honestly fails. That is the intruder
who fills the form in truthfully. Nobody attacking this writes their real group
in the box; they write the victim's. Those cases can only go red if the check is
deleted outright, never if it is asking the wrong source -- so the suite reads
as though ownership were gated here while the door stands open. Every case below
sends the victim's context id, which is the only version an attacker would send.

The three money rules stay green throughout. Integer dong, allocations summing
to the total, a balance that replays from the ledger -- an intruder's expense
satisfies all three, exactly as a stranger participant did. Ownership is a
separate invariant, and this is its second door.
"""

from __future__ import annotations

import uuid

from .helpers import (
    ADVANCER_ID,
    CONTEXT_ID,
    OTHER_ID,
    SENDER_ID,
    actor_headers,
    expense_payload,
    propose_and_confirm,
)

# `OTHER_ID` is seeded into no context by `conftest.repository`; helpers.py
# calls it "the outsider that the context-read and balance tests need". The
# outsider claims the group anyway, which is the whole point: the header is
# the caller's own sentence about themselves.
OUTSIDER_HEADERS = {
    "X-Actor-ID": str(OTHER_ID),
    "X-Actor-Roles": "member,advancer,recipient,batch_owner",
    "X-Actor-Contexts": str(CONTEXT_ID),
}


def _propose(client, participants=None):
    response = client.post("/expenses", json=expense_payload(participants=participants))
    assert response.status_code == 201, response.text
    return response.json()


def _bill_payload():
    """One line, priced so the printed total and the item total agree."""

    return {
        "context_id": str(CONTEXT_ID),
        "printed_total_vnd": 135000,
        "items_total_vnd": 135000,
        "confidence": 88,
        "needs_review": False,
        "items": [
            {
                "item_key": "i1",
                "name": "Phở bò",
                "quantity": 1,
                "unit_price_vnd": 135000,
                "line_total_vnd": 135000,
                "suggested_participant_ids": [],
            }
        ],
        "surcharges": [],
        "discounts": [],
    }


def test_an_outsider_cannot_confirm_an_expense_into_someone_elses_ledger(
    client, repository
):
    """The money write. An intruder charges two real members of a real group."""

    proposed = _propose(client)

    response = client.post(
        f"/expenses/{proposed['expense_id']}/confirm",
        headers=OUTSIDER_HEADERS,
        json={
            "proposal": proposed["proposal"],
            "expected_allocations": proposed["allocation"]["allocations"],
            "acknowledge_as_advancer": False,
        },
    )

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "permission_denied"
    # Refused before the write, not reconciled after it. A ledger that has to
    # be cleaned up has already been wrong to everyone who read it meanwhile.
    assert repository.confirmed == {}


def test_a_member_can_still_confirm(client, repository):
    """The negative case above proves nothing if the positive case cannot pass.

    Answering 403 to every confirmation would leave the assertions above green
    while deleting the feature.
    """

    proposed = _propose(client)

    response = client.post(
        f"/expenses/{proposed['expense_id']}/confirm",
        headers=actor_headers(),
        json={
            "proposal": proposed["proposal"],
            "expected_allocations": proposed["allocation"]["allocations"],
            "acknowledge_as_advancer": True,
        },
    )

    assert response.status_code == 201, response.text
    stored = repository.confirmed[uuid.UUID(response.json()["expense_version_id"])]
    assert sum(row.amount_vnd for row in stored.allocations) == 82000


def test_an_outsider_cannot_open_a_collection_batch_on_someone_elses_group(
    client, repository
):
    """The second money write, and the one that reaches people.

    A batch is not an internal record: publishing it mints a guest envelope per
    obligation and sends each member a link asking them to transfer money.

    The group's own debt is created first, by a real member. Without it the
    route answers `no_unbatched_allocations` and the case would go green on an
    empty group rather than on a refusal -- passing for want of anything to
    steal instead of because the door held.
    """

    propose_and_confirm(client)

    response = client.post(
        "/batches",
        headers=OUTSIDER_HEADERS,
        json={
            "context_id": str(CONTEXT_ID),
            "expense_version_ids": None,
            "due_at": "2030-09-27T12:00:00+07:00",
        },
    )

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "permission_denied"


def test_an_outsider_cannot_create_a_bill_in_someone_elses_group(client):
    """A bill is the head of the hero path: scan, assign items, split.

    Left open, an intruder seeds the screen every member of that group opens.
    """

    response = client.post("/bills", headers=OUTSIDER_HEADERS, json=_bill_payload())

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "permission_denied"


def test_an_outsider_cannot_read_a_bill_belonging_to_someone_elses_group(client):
    """Reading is not the harmless half.

    A bill carries the line items of a real meal and the ids they are assigned
    to. `_bill_for_actor` guards every read and write that names a bill id, so
    one weak answer here exposes all of them.
    """

    created = client.post("/bills", headers=actor_headers(), json=_bill_payload())
    assert created.status_code == 201, created.text

    response = client.get(f"/bills/{created.json()['id']}", headers=OUTSIDER_HEADERS)

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "permission_denied"
    # The dish name is the payload of the leak, not just the status code.
    assert "Phở bò" not in response.text


def test_a_member_can_still_read_a_bill(client):
    """Positive control for the read gate, for the same reason as above."""

    created = client.post("/bills", headers=actor_headers(), json=_bill_payload())
    assert created.status_code == 201, created.text

    response = client.get(f"/bills/{created.json()['id']}", headers=actor_headers())

    assert response.status_code == 200, response.text
    assert "Phở bò" in response.text


def test_a_former_member_cannot_confirm_after_leaving(client, repository):
    """`state=left` is the case the header cannot represent at all.

    The roster keeps the row and flips its state; the header is a list of ids
    with no state in it. So a link, a bookmarked client, or a stale token that
    still names the group reads as membership forever. `repository.is_member`
    requires `ACTIVE`, which is the only reason this can be told apart.
    """

    repository.active_memberships.add((CONTEXT_ID, OTHER_ID))
    proposed = _propose(client, participants=[ADVANCER_ID, SENDER_ID])
    repository.active_memberships.discard((CONTEXT_ID, OTHER_ID))

    response = client.post(
        f"/expenses/{proposed['expense_id']}/confirm",
        headers=OUTSIDER_HEADERS,
        json={
            "proposal": proposed["proposal"],
            "expected_allocations": proposed["allocation"]["allocations"],
            "acknowledge_as_advancer": False,
        },
    )

    assert response.status_code == 403, response.text
    assert repository.confirmed == {}
