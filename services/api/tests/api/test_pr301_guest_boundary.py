"""PR #301 -- a guest link is not a key to F31/F33/F36.

`/g/{token}` is the one place in this product where a stranger is handed a
working URL. The three routes this branch adds are the three most concentrated
reads it owns: what a group eats, what a group is saying right now, and every
photograph they took on a trip. Nothing wires them together, and this file is
what makes "nothing" checkable rather than believed.

The positive control is the whole test. Each case below first fetches the
guest page and asserts it renders -- so the token in hand is live, valid, and
unexpired -- and only then shows that the same token opens none of the four
new endpoints. Without that first half, every refusal here is equally
satisfied by a token that was already broken, which is the failure mode a
"guest cannot reach X" test falls into by default.

`X-Actor-ID` is a claim rather than a credential in this slice (see
`app/api/deps.py`), so a guest can put anything in it. That is why the cases
below try the token *as* an actor id, and try a well-formed random one: the
question is not whether the product trusts guests, it is what the product does
when a guest simply asserts they are somebody.
"""

from __future__ import annotations

import uuid

import pytest

from .helpers import CONTEXT_ID, create_batch, propose_and_confirm, publish_batch

#: The four endpoints this branch adds. Written out because the point is
#: coverage of all of them: three of the four were reachable through one
#: service method, and the fourth (`/albums/{outing_id}`) through another.
NEW_ROUTES = pytest.mark.parametrize(
    "path",
    [
        f"/contexts/{CONTEXT_ID}/preference-profile",
        f"/contexts/{CONTEXT_ID}/contextual-suggestion",
        f"/contexts/{CONTEXT_ID}/albums",
        f"/contexts/{CONTEXT_ID}/albums/{uuid.uuid4()}",
    ],
)


def _live_guest_token(client, repository) -> str:
    """A real, published, working guest link -- and proof that it works.

    The assertion inside this helper is not decoration. Every test in this
    file argues "this token opens the guest page and nothing else", and the
    first half of that sentence has to be established before the second half
    means anything.
    """

    propose_and_confirm(client)
    batch = create_batch(client, repository)
    published = publish_batch(client, batch["batch_id"])
    path = published["guest_links"][0]["path"]

    page = client.get(path)
    assert page.status_code == 200, page.text
    assert "Chỉ hiển thị phần của bạn" in page.text

    return path.rsplit("/", 1)[-1]


def _carries_no_records(response) -> None:
    """A refusal is an error and nothing else."""

    body = response.json()
    assert set(body) == {"code", "detail"}, body
    assert not any(isinstance(value, list | dict) for value in body.values()), body


@NEW_ROUTES
def test_a_guest_with_a_live_token_has_no_actor_and_is_turned_away(
    client, repository, path
):
    """The ordinary case: a guest sends no `X-Actor-ID`, because they have none.

    401 rather than 403 is the correct answer and worth pinning: the caller is
    not a member who is refused, they are nobody at all, and collapsing the two
    would tell an unauthenticated caller that the group exists.
    """

    _live_guest_token(client, repository)

    response = client.get(path)

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"
    _carries_no_records(response)


@NEW_ROUTES
def test_the_guest_token_is_not_an_actor_id(client, repository, path):
    """The obvious thing a holder of a bearer token tries next.

    The token is the only credential a guest has, so presenting it as identity
    is the first move available to them. It must not resolve to a person.
    """

    token = _live_guest_token(client, repository)

    response = client.get(path, headers={"X-Actor-ID": token})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_actor_id"
    _carries_no_records(response)


@NEW_ROUTES
def test_a_guest_who_invents_an_actor_id_and_claims_the_group_is_refused(
    client, repository, path
):
    """The attack the missing gateway actually leaves open.

    A guest who reads their own page learns a real `context_id` is involved in
    their obligation. Inventing an actor id costs nothing and naming the group
    in `X-Actor-Contexts` costs nothing, so the only thing standing here is
    that the service asks the repository for a membership row instead of
    reading the header back. This asserts that it does.
    """

    _live_guest_token(client, repository)

    response = client.get(
        path,
        headers={
            "X-Actor-ID": str(uuid.uuid4()),
            "X-Actor-Roles": "member,group_admin",
            "X-Actor-Contexts": str(CONTEXT_ID),
        },
    )

    assert response.status_code == 403
    _carries_no_records(response)


def test_the_guest_page_carries_no_door_to_any_of_the_three_features(
    client, repository
):
    """The rendered page, not the route table.

    A link a guest can see is a link a guest can follow, and the guest view
    model is the one boundary that decides what reaches the template. This
    reads the delivered HTML rather than the source, because the question is
    what a stranger's browser receives.
    """

    propose_and_confirm(client)
    batch = create_batch(client, repository)
    published = publish_batch(client, batch["batch_id"])
    path = published["guest_links"][0]["path"]

    page = client.get(path)

    assert page.status_code == 200
    for fragment in (
        "preference-profile",
        "contextual-suggestion",
        "/albums",
        # The response field names the three routes mint. Present in the page
        # would mean the guest template grew a second data source.
        "photo_count",
        "checkin_count",
        "has_profile",
    ):
        assert fragment not in page.text, fragment
