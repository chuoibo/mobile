"""POST /batches and POST /batches/{id}/publish."""

from __future__ import annotations

from .helpers import (
    OTHER_ID,
    actor_headers,
    create_batch,
    propose_and_confirm,
    publish_batch,
)


def test_batch_uses_domain_merge_for_same_sender_recipient_pair(client, repository):
    first = propose_and_confirm(client, total=82000, description="Bữa tối")
    second = propose_and_confirm(client, total=18000, description="Tiền xe")

    batch = create_batch(
        client,
        repository,
        [first["expense_version_id"], second["expense_version_id"]],
    )

    assert batch["status"] == "frozen"
    assert len(batch["obligations"]) == 1
    assert batch["obligations"][0]["amount_vnd"] == 50000
    assert set(batch["obligations"][0]["source_expense_version_ids"]) == {
        first["expense_version_id"],
        second["expense_version_id"],
    }


def test_a_batch_freezes_without_anybody_registering_an_account(client, repository):
    """This used to be 409 UNREADY_RECIPIENT_CHOICE_REQUIRED.

    The organiser had to say out loud what to do about a recipient with no bank
    account registered. There are no bank accounts: the product works out each
    person's share and stops. So the same request that was refused now freezes,
    and the case is kept in that direction rather than deleted -- a state that
    used to block has to be shown not to block any more.
    """

    propose_and_confirm(client)
    response = client.post(
        "/batches",
        headers=actor_headers(),
        json={
            "context_id": str(next(iter(repository.expenses.values())).context_id),
            "due_at": "2030-09-27T12:00:00+07:00",
        },
    )

    assert response.status_code == 201, response.text
    assert len(repository.batches) == 1


def test_publish_checks_ack_gate_separately_from_expense_confirmation(
    client, repository
):
    propose_and_confirm(client, acknowledge=False)
    batch = create_batch(client, repository)

    response = client.post(
        f"/batches/{batch['batch_id']}/publish",
        headers=actor_headers(),
        json={
            "delivery_method": "personal_link",
            "guest_link_expires_at": "2030-10-27T12:00:00+07:00",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "advancer_acknowledgement_required"
    assert repository.links == {}


def test_publish_creates_one_sender_scoped_link_carrying_only_the_amount(
    client, repository
):
    """The link names the debt, not a way to settle it.

    It used to carry a VietQR payload per obligation. The negative half is the
    point now: an envelope that still shipped an account number would be
    handing out a detail the product no longer collects.
    """

    propose_and_confirm(client)
    batch = create_batch(client, repository)
    published = publish_batch(client, batch["batch_id"])

    assert published["status"] == "published"
    assert len(published["guest_links"]) == 1
    link = published["guest_links"][0]
    assert link["path"].startswith("/g/")
    assert len(repository.links) == 1
    obligation = link["obligations"][0]
    assert obligation["amount_vnd"] == batch["obligations"][0]["amount_vnd"]
    for gone in ("vietqr_payload", "bank_bin", "account_number", "transfer_note"):
        assert gone not in obligation, gone


def test_non_owner_cannot_publish_even_with_batch_owner_role(client, repository):
    propose_and_confirm(client)
    batch = create_batch(client, repository)

    response = client.post(
        f"/batches/{batch['batch_id']}/publish",
        headers=actor_headers(
            actor_id=OTHER_ID,
            roles="batch_owner",
        ),
        json={
            "delivery_method": "personal_link",
            "guest_link_expires_at": "2030-10-27T12:00:00+07:00",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "owns_batch"
