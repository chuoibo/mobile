"""The predicate that replaced `is_invitee` for link-born memberships.

bug-141903 was one predicate answering a question it had just written down.
`accept_context_membership` proved `membership.person_id == actor.id` and
nothing else, which was sound while `invite_context_member` -- a group_admin
naming one person -- was the only road to INVITED. rd-be-08 opened a second
road, a forwardable bearer token, on which the redeeming call *creates* the row
it is then asked about. The answer was therefore always yes.

QA's `test_outing_invite_escalation_postgres.py` proves the escalation is shut.
This file proves the two things shutting it must not cost:

1. The feature still works. A fix that only ever answers 403 closes the hole by
   deleting F14, and a dead route looks identical to a safe one in a suite that
   only tests refusals.
2. The refusal does not depend on the attacker being polite about roles.
   `X-Actor-Roles` is a claim the caller types; membership is what decides.

Plus the race QA found on the same route: a one-use link that admitted two
people because the `accepted_at IS NULL` check ran in Python, outside the lock
that the stamping statement later took.

Uses `flush`, never `commit`: `postgres_session` rolls back per test and the
schema is shared with row-counting tests in this directory.
"""

from __future__ import annotations

import uuid

import anyio
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.errors import RepositoryConflict
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import (
    Context,
    Membership,
    MembershipOrigin,
    MembershipRole,
    MembershipState,
    OutingInvite,
    Person,
)

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

SECRET_CAPTION = "Ảnh riêng của nhóm — người ngoài không được thấy"


def _headers(person_id: uuid.UUID, roles: str = "member") -> dict[str, str]:
    return {"X-Actor-ID": str(person_id), "X-Actor-Roles": roles}


def _app(session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _group(session: Session) -> tuple[Context, Person, Person, Person]:
    """A group with two ACTIVE members, plus one person who is not in it."""
    owner = _person(session, "Minh Anh")
    second = _person(session, "Bảo Trân")
    outsider = _person(session, "Người lạ cầm link")
    context = Context(id=uuid.uuid4(), display_name="Team Đà Lạt", created_by_id=owner.id)
    session.add(context)
    session.flush()
    for member in (owner, second):
        session.add(
            Membership(
                id=uuid.uuid4(),
                context_id=context.id,
                person_id=member.id,
                state=MembershipState.ACTIVE,
                role=MembershipRole.MEMBER,
                joined_at=NOW,
            )
        )
    session.flush()
    return context, owner, second, outsider


async def _mint_and_redeem(client, context: Context, owner: Person, holder: Person):
    outing = await client.post(
        f"/contexts/{context.id}/outings",
        json={
            "title": "Đà Lạt 2 ngày",
            "starts_on": "2030-09-05",
            "ends_on": "2030-09-06",
            "headcount": 4,
            "budget_per_person_vnd": 2_500_000,
        },
        headers=_headers(owner.id),
    )
    minted = await client.post(
        f"/outings/{outing.json()['id']}/invites",
        json={"source": "link"},
        headers=_headers(owner.id),
    )
    token = minted.json()["invite_token"]
    redeemed = await client.post(
        f"/outing-invites/{token}/accept", headers=_headers(holder.id)
    )
    return token, redeemed


def test_an_active_member_can_approve_a_link_request_and_that_opens_the_group(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The half of the fix that keeps F14 alive.

    Refusing every accept would also have made QA's escalation test green, and
    it would have been the wrong fix: a link nobody can ever approve is a
    feature that does not exist. Somebody already inside the group has to be
    able to clear the request, and once they do the newcomer is a real member.
    """
    context, owner, second, outsider = _group(postgres_session)
    app = _app(postgres_session, monkeypatch)

    async def walk():
        async with _client(app) as client:
            await client.post(
                f"/contexts/{context.id}/memories",
                json={
                    "image_url": "https://example.invalid/a.jpg",
                    "caption": SECRET_CAPTION,
                },
                headers=_headers(owner.id),
            )
            _, redeemed = await _mint_and_redeem(client, context, owner, outsider)
            membership_id = redeemed.json()["membership_id"]

            before = await client.get(
                f"/contexts/{context.id}/memories", headers=_headers(outsider.id)
            )
            # A member who is not the requester clears the request.
            approved = await client.post(
                f"/memberships/{membership_id}/accept", headers=_headers(second.id)
            )
            after = await client.get(
                f"/contexts/{context.id}/memories", headers=_headers(outsider.id)
            )
            return before, approved, after

    before, approved, after = anyio.run(walk)

    # Before approval the wall is shut -- that is QA's invariant, restated here
    # so this test fails loudly if the ordering ever inverts.
    assert before.status_code == 403, before.text
    assert SECRET_CAPTION not in before.text

    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "active"

    # And the approval actually means something: the newcomer now reads the
    # group, which is the whole point of joining it.
    assert after.status_code == 200, after.text
    assert SECRET_CAPTION in after.text


def test_the_requester_cannot_approve_themselves_whatever_roles_they_claim(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """`X-Actor-Roles` is a claim the caller types on their own phone.

    QA's regression test sends `member`. If the new predicate leaned on the
    role string rather than on an ACTIVE membership row, sending
    `group_admin` would walk straight through it and the suite would still
    look green.
    """
    context, owner, _second, outsider = _group(postgres_session)
    app = _app(postgres_session, monkeypatch)

    async def walk():
        async with _client(app) as client:
            _, redeemed = await _mint_and_redeem(client, context, owner, outsider)
            membership_id = redeemed.json()["membership_id"]
            return await client.post(
                f"/memberships/{membership_id}/accept",
                headers=_headers(outsider.id, roles="member,group_admin"),
            )

    promoted = anyio.run(walk)

    assert promoted.status_code == 403, promoted.text

    membership = postgres_session.scalar(
        select(Membership).where(
            Membership.context_id == context.id,
            Membership.person_id == outsider.id,
        )
    )
    assert membership is not None
    assert membership.state == MembershipState.INVITED
    # And the row remembers why it may not clear itself.
    assert membership.origin == MembershipOrigin.LINK


def test_a_named_invitee_still_accepts_their_own_invitation(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The predicate that was always correct must survive the fix.

    When a group_admin names a person, that person consenting IS the decision
    the product wants -- nobody else should have to countersign. Losing this
    would trade one broken route for another.
    """
    context, owner, _second, invitee = _group(postgres_session)
    app = _app(postgres_session, monkeypatch)

    async def walk():
        async with _client(app) as client:
            invited = await client.post(
                f"/contexts/{context.id}/members",
                json={"person_id": str(invitee.id)},
                headers=_headers(owner.id, roles="member,group_admin"),
            )
            membership_id = invited.json()["id"]
            accepted = await client.post(
                f"/memberships/{membership_id}/accept", headers=_headers(invitee.id)
            )
            return invited, accepted

    invited, accepted = anyio.run(walk)

    assert invited.status_code in (200, 201), invited.text
    assert invited.json()["state"] == "invited"
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["state"] == "active"

    membership = postgres_session.scalar(
        select(Membership).where(Membership.id == uuid.UUID(invited.json()["id"]))
    )
    assert membership is not None
    assert membership.origin == MembershipOrigin.NAMED


def test_a_one_use_link_is_stamped_once_even_when_the_check_already_passed(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """QA's second finding: the guard ran outside the lock that mattered.

    `accept_outing_invite` used to take `FOR UPDATE` and then stamp
    `accepted_at` unconditionally, trusting a Python-level
    `accepted_at is None` the service had evaluated on an unlocked read some
    time earlier. Two redeemers both passed that check and both were stamped,
    so one link admitted two people and `accepted_by_id` remembered only the
    second.

    Driven at the repository seam on purpose. The HTTP layer here shares one
    session, so it cannot interleave two transactions -- the very reason the
    defect survived the existing suite. What is provable without a second
    connection is that the stamping step no longer trusts a decision made
    before the lock: it re-reads the condition while holding it.
    """
    context, owner, _second, outsider = _group(postgres_session)
    app = _app(postgres_session, monkeypatch)
    repository = SqlAlchemyApiRepository(postgres_session)

    async def walk():
        async with _client(app) as client:
            return await _mint_and_redeem(client, context, owner, outsider)

    _token, redeemed = anyio.run(walk)
    assert redeemed.status_code == 200, redeemed.text
    invite_id = uuid.UUID(redeemed.json()["invite_id"])

    # Replay the second half of a lost race: the caller believed the invite was
    # free, and is now asking to stamp it. It must be refused, not overwritten.
    with pytest.raises(RepositoryConflict) as refused:
        repository.accept_outing_invite(
            invite_id=invite_id,
            accepted_by_id=_person(postgres_session, "Người thứ hai").id,
            now=NOW,
        )

    assert refused.value.code == "OUTING_INVITE_ALREADY_ACCEPTED"

    # The ledger still names the person who actually won.
    invite = postgres_session.scalar(
        select(OutingInvite).where(OutingInvite.id == invite_id)
    )
    assert invite is not None
    assert invite.accepted_by_id == outsider.id
