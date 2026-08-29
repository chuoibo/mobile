"""Synthetic request builders for API endpoint tests."""

from __future__ import annotations

import io
import uuid
from datetime import datetime

from PIL import Image

CONTEXT_ID = uuid.UUID("1aa00000-aaaa-4aaa-8aaa-0000a0000001")
ADVANCER_ID = uuid.UUID("2bb00000-bbbb-4bbb-8bbb-0000b0000001")
SENDER_ID = uuid.UUID("3cc00000-cccc-4ccc-8ccc-0000c0000001")
OTHER_ID = uuid.UUID("4dd00000-dddd-4ddd-8ddd-0000d0000001")


def png_bytes(size: tuple[int, int] = (40, 24)) -> bytes:
    """A PNG with pixels behind the header, for routes that decode uploads.

    Every scan test used to share a 29-byte literal: a signature and an IHDR
    with no IDAT after it. Nothing on the route had ever tried to decode an
    upload, so a header was enough to stand in for a photograph. rd-be-20 put a
    decoder on that path, and the literal stopped being a stand-in for anything
    -- it is not an image, and the route now says so. Building a real one keeps
    those cases testing what they were written to test.
    """

    buffer = io.BytesIO()
    Image.new("RGB", size, (250, 250, 248)).save(buffer, format="PNG")
    return buffer.getvalue()


def expense_payload(*, total=82000, description="Bữa tối", participants=None):
    """`participants` defaults to two people, which yields ONE obligation.

    Pass three to get two obligations and two guest links. Tests about "this
    objection stopped exactly one obligation" need that: with a single
    obligation in the batch there is nothing for a stray dispute to spill
    onto, so the test passes without proving anything.
    """
    people = participants or [SENDER_ID, ADVANCER_ID]
    return {
        "context_id": str(CONTEXT_ID),
        "description": description,
        "recorded_by_id": str(ADVANCER_ID),
        "paid_by_id": str(ADVANCER_ID),
        "verification_scope": "totals_only",
        "occurred_at": "2030-08-27T12:00:00+07:00",
        "participants": [str(person) for person in people],
        "total_amount_vnd": total,
        "items": [],
        "surcharges": [],
        "discounts": [],
    }


def actor_headers(actor_id=ADVANCER_ID, roles="member,advancer,recipient,batch_owner"):
    return {
        "X-Actor-ID": str(actor_id),
        "X-Actor-Roles": roles,
        "X-Actor-Contexts": str(CONTEXT_ID),
    }


def propose_and_confirm(
    client, *, acknowledge=True, total=82000, description="Bữa tối", participants=None
):
    proposal = client.post(
        "/expenses",
        json=expense_payload(
            total=total, description=description, participants=participants
        ),
    )
    assert proposal.status_code == 201, proposal.text
    body = proposal.json()
    confirmation = client.post(
        f"/expenses/{body['expense_id']}/confirm",
        headers=actor_headers(),
        json={
            "proposal": body["proposal"],
            "expected_allocations": body["allocation"]["allocations"],
            "acknowledge_as_advancer": acknowledge,
        },
    )
    assert confirmation.status_code == 201, confirmation.text
    return confirmation.json()


def seed_bank_recipient(repository):
    from app.api.repository import BankRecipientRecord

    repository.bank_recipients[ADVANCER_ID] = BankRecipientRecord(
        id=uuid.uuid4(),
        recipient_id=ADVANCER_ID,
        bank_bin="970415",
        account_number="TESTACCOUNT1133",
        account_name="NGUYEN VAN NAM",
        confirmed_at=datetime.fromisoformat("2029-08-27T00:00:00+00:00"),
    )


def create_batch(client, repository, version_ids=None):
    seed_bank_recipient(repository)
    response = client.post(
        "/batches",
        headers=actor_headers(),
        json={
            "context_id": str(CONTEXT_ID),
            "expense_version_ids": version_ids,
            "due_at": "2030-09-27T12:00:00+07:00",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def publish_batch(client, batch_id):
    response = client.post(
        f"/batches/{batch_id}/publish",
        headers=actor_headers(),
        json={
            "delivery_method": "personal_link",
            "guest_link_expires_at": "2030-10-27T12:00:00+07:00",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()
