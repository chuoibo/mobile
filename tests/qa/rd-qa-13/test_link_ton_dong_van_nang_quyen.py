"""bug-141903 counter-check: does turning off minting actually shut the door?

PR #124 ("bước 1") made `POST /outings/{id}/invites` with `source="link"`
return 422, and skipped the three tests that covered the link path. Its own
commit message defers the real defect -- the self-circular predicate behind
`/memberships/{id}/accept` -- to "bước 2".

That leaves a question the skipped tests can no longer ask: a link is a bearer
token that lives in somebody's chat history. Refusing to mint *new* ones does
nothing to the ones already minted. Every deployment that ran the pre-#124 code
has rows in `outing_invites`, and both routes that consume them are still
mounted:

    POST /outing-invites/{token}/accept     -> INVITED membership for the bearer
    POST /memberships/{membership_id}/accept -> is_invitee == the row just written

`accept_outing_invite` checks `accepted_at` (single use) but never an expiry, so
an outstanding link stays valid forever.

This test builds that state the only way it can now exist -- an `OutingInvite`
row written directly, exactly as a pre-#124 mint would have left it -- and then
walks a stranger through both live routes. It asserts the behaviour the file's
own docstring in `tests/postgres/test_outings_postgres.py` promises:

    "the holder of a link gets no read access to the group's messages,
     memories or balances until a human accepts through the existing route"

Red on 42228d6 means the promise is not kept. Green means bước 2 landed.

Run:
    cd services/api && MOBILE_TEST_DATABASE_URL=... MOBILE_REQUIRE_POSTGRES_TESTS=1 \
      python3 -m pytest ../../tests/qa/rd-qa-13 -q
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import anyio
import httpx
import pytest
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.api.service import token_digest
from app.db.models import (
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    OutingInvite,
    OutingInviteSource,
    Person,
)

pytestmark = pytest.mark.postgres

# Declared here rather than imported from `tests.postgres.test_repository_postgres`:
# two directories in this repo are named `tests`, so that import resolves
# differently depending on which directory pytest was invoked from.
NOW = datetime(2030, 8, 27, 12, tzinfo=UTC)

# A token that was handed out before #124 landed. Its plaintext survives in a
# chat message; only the digest was ever stored.
LEAKED_TOKEN = "rd-qa-13-mot-link-da-gui-truoc-khi-tat"
SECRET_MESSAGE = "Số tài khoản của mình là 000-bí-mật, chuyển khoản nhé"


def _http(session: Session, monkeypatch: pytest.MonkeyPatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def _client(app):
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def _headers(person_id: uuid.UUID) -> dict[str, str]:
    return {"X-Actor-ID": str(person_id), "X-Actor-Roles": "member,group_admin"}


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _scene(session: Session):
    """One group, one member inside it, one stranger outside it."""
    owner = _person(session, "Minh Anh")
    stranger = _person(session, "Người cầm link")
    context = Context(
        id=uuid.uuid4(), display_name="Team Đà Lạt", created_by_id=owner.id
    )
    session.add(context)
    session.flush()
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=owner.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
            left_at=None,
        )
    )
    session.flush()
    return context, owner, stranger


def _outing(app, owner: Person, context: Context) -> dict:
    async def exchange():
        async with _client(app) as client:
            return await client.post(
                f"/contexts/{context.id}/outings",
                headers=_headers(owner.id),
                json={
                    "title": "Đà Lạt cuối tuần",
                    "starts_on": date(2030, 10, 17).isoformat(),
                    "ends_on": date(2030, 10, 19).isoformat(),
                    "headcount": 8,
                    "budget_per_person_vnd": 2_500_000,
                },
            )

    response = anyio.run(exchange)
    assert response.status_code == 201, response.text
    return response.json()


def _outstanding_link(session: Session, outing_id: str, owner: Person) -> OutingInvite:
    """The row a pre-#124 mint left behind. Nothing revokes it."""
    invite = OutingInvite(
        id=uuid.uuid4(),
        outing_id=uuid.UUID(outing_id),
        source=OutingInviteSource.LINK,
        invited_person_id=None,
        invited_by_id=owner.id,
        token_digest=token_digest(LEAKED_TOKEN),
        accepted_at=None,
        accepted_by_id=None,
        created_at=NOW,
    )
    session.add(invite)
    session.flush()
    return invite


def _walk(postgres_session: Session, monkeypatch: pytest.MonkeyPatch):
    """Redeem an outstanding link as a stranger, then try to self-promote.

    Returns every response the two steps produced so each claim can be asserted
    in its own test -- a single test would stop at the first violation and hide
    whether the promotion actually bought any data.
    """
    context, owner, stranger = _scene(postgres_session)
    app = _http(postgres_session, monkeypatch)
    outing = _outing(app, owner, context)
    _outstanding_link(postgres_session, outing["id"], owner)

    async def exchange():
        async with _client(app) as client:
            # The group says something it expects to stay in the group.
            posted = await client.post(
                f"/contexts/{context.id}/messages",
                headers=_headers(owner.id),
                json={"kind": "text", "body": SECRET_MESSAGE},
            )
            # Before redeeming, the stranger is a stranger.
            before = await client.get(
                f"/contexts/{context.id}/messages", headers=_headers(stranger.id)
            )
            # Step 1 -- the mint is off, but redeeming is not.
            redeemed = await client.post(
                f"/outing-invites/{LEAKED_TOKEN}/accept",
                headers=_headers(stranger.id),
            )
            return posted, before, redeemed

    posted, before, redeemed = anyio.run(exchange)

    assert posted.status_code == 201, posted.text
    # Assert the door was shut first: a leak test that only checks the negative
    # passes just as happily on a blank page.
    assert before.status_code == 403, before.text

    assert redeemed.status_code == 200, (
        "PR #124 refuses to MINT a link; it does not refuse to redeem one that "
        f"already exists. Got {redeemed.status_code}: {redeemed.text}"
    )
    membership_id = redeemed.json()["membership_id"]
    assert redeemed.json()["membership_state"].upper() == "INVITED"

    async def escalate():
        async with _client(app) as client:
            accepted = await client.post(
                f"/memberships/{membership_id}/accept",
                headers=_headers(stranger.id),
            )
            after = await client.get(
                f"/contexts/{context.id}/messages", headers=_headers(stranger.id)
            )
            balances = await client.get(
                f"/contexts/{context.id}/balances", headers=_headers(stranger.id)
            )
            return accepted, after, balances

    accepted, after, balances = anyio.run(escalate)
    return redeemed, accepted, after, balances


def test_a_link_bearer_cannot_promote_themselves_to_active(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """`accept_context_membership` proves only `membership.person_id == actor.id`.

    The redeem step wrote that row one call earlier, so the predicate is
    self-circular: it asks a question the attacker just supplied the answer to.
    Nobody in the group ever chose this person.
    """
    _, accepted, _, _ = _walk(postgres_session, monkeypatch)

    assert accepted.status_code == 403, (
        "A link bearer promoted THEMSELVES from INVITED to ACTIVE. "
        f"Got {accepted.status_code}: {accepted.text}"
    )


def test_a_link_bearer_never_reads_the_groups_messages_or_balances(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The consequence, asserted apart from the status code that enables it.

    Stated separately so a fix that only changes a status code cannot satisfy
    the escalation test while the data stays readable.
    """
    _, _, after, balances = _walk(postgres_session, monkeypatch)

    assert after.status_code == 403, (
        "The link bearer is reading the group's messages. "
        f"Got {after.status_code}: {after.text}"
    )
    assert SECRET_MESSAGE not in after.text, "Group message leaked to a link bearer"
    assert balances.status_code == 403, (
        f"The link bearer is reading the group's balances. Got {balances.status_code}"
    )
