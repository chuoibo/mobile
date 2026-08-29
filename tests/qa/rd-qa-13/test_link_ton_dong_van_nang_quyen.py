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

WHAT THIS FILE DELIBERATELY DOES NOT ASSERT (bug-153233)

There is more than one way to keep that promise, and a build is free to pick
either. #128 lets the stale token through to an INVITED membership (200) and
then refuses the self-promotion; #132 refuses the stale token outright (404) so
the membership is never written at all. Both keep the bearer out of the group's
messages and balances -- which is the whole claim.

An earlier revision of `_walk` hard-coded `assert redeemed.status_code == 200`
before reading `membership_id`. That made the helper pick one of the two, so a
build that shut the door *earlier* failed here, at the helper, in every case in
the file -- including the two that say nothing about how the redeem is answered.
The probe could not go green even when the product was right. The redeem status
is now recorded, not judged, and each case asserts the end state instead.

AND THE COST OF THAT, WHICH IS WHY THERE IS A THIRD CASE (rd-qa-20)

Recording rather than judging bought tolerance and paid for it in reach. Once
#132 landed, the legacy row is refused at redeem, `membership_id` stays None,
the escalation call is skipped -- and the two cases above still pass, having
never touched `/memberships/{id}/accept` at all. Measured, not reasoned: on
32c02e0 rebased onto main e2736ad the redeem answers 404 in both cases and the
file reports `2 passed`. Green by not running.

So the two cases above now describe expiry (the door shuts earlier), and
`test_a_live_link_bearer_cannot_promote_themselves_to_active` carries the
original claim on a link that is still inside its window. `_walk(con_han=True)`
asserts it reached the escalation call, so that case cannot go quiet the way
these two did.

Run:
    cd services/api && MOBILE_TEST_DATABASE_URL=... MOBILE_REQUIRE_POSTGRES_TESTS=1 \
      python3 -m pytest ../../tests/qa/rd-qa-13 -q
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import anyio
import httpx
import pytest
from sqlalchemy import select
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


def _outstanding_link(
    session: Session, outing_id: str, owner: Person, *, con_han: bool = False
) -> OutingInvite:
    """The row a pre-#124 mint left behind. Nothing revokes it.

    `con_han=False` is the legacy row: expiry equal to `created_at`, which is
    what #132's backfill wrote for every link minted before the column existed.

    `con_han=True` is a link that is still inside its window. That distinction
    is the whole reason this helper takes an argument: after #132 the legacy row
    is refused at the door, so a file that only ever built legacy rows stops
    reaching the self-promotion route it exists to test. See `_walk`.
    """
    columns = dict(
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
    # `expires_at` arrives NOT NULL with migration d4a2e7b91c30 (#132), which
    # backfills every row that predates the column to `created_at` -- dead on
    # arrival. Writing that same value keeps this row describing the same legacy
    # link on both sides of the migration. Naming the column unconditionally
    # would make the file uncollectable on any build before it; leaving it out
    # makes the INSERT fail with NotNullViolation on any build after it.
    if hasattr(OutingInvite, "expires_at"):
        columns["expires_at"] = NOW + timedelta(days=7) if con_han else NOW
    invite = OutingInvite(**columns)
    session.add(invite)
    session.flush()
    return invite


@dataclass
class Walk:
    """What the two live routes produced, with no verdict attached.

    `accepted` is None on a build that refuses the stale token, because there is
    then no membership id to promote -- the door shut one step earlier. Cases
    that would otherwise have nothing left to check in that branch assert
    `stranger_states` instead, which is read back from the table and is a real
    claim on either path.
    """

    redeemed: httpx.Response
    accepted: httpx.Response | None
    after: httpx.Response
    balances: httpx.Response
    stranger_states: list[str]


def _walk(
    postgres_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    *,
    con_han: bool = False,
) -> Walk:
    """Redeem an outstanding link as a stranger, then try to self-promote.

    Returns every response the two steps produced so each claim can be asserted
    in its own test -- a single test would stop at the first violation and hide
    whether the promotion actually bought any data.

    `con_han=True` demands that the redeem actually succeed. That is not a
    second opinion about how a redeem should be answered -- it is the guard that
    keeps this file honest. Measured on 32c02e0 rebased onto main e2736ad: with
    the legacy row the redeem answers 404, `membership_id` stays None, the
    escalation call is skipped, and BOTH cases below still pass while never
    touching `/memberships/{id}/accept`. The file went green by not running.
    """
    context, owner, stranger = _scene(postgres_session)
    app = _http(postgres_session, monkeypatch)
    outing = _outing(app, owner, context)
    _outstanding_link(postgres_session, outing["id"], owner, con_han=con_han)

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

    # Record which of the two shapes this build answered with; do not grade it.
    # Whichever it is, the walk continues to the reads below, because the claim
    # every case here makes is about what the bearer ends up able to see.
    membership_id: str | None = None
    if redeemed.status_code == 200:
        body = redeemed.json()
        assert body["membership_state"].upper() == "INVITED", (
            "A redeemed link handed out something other than INVITED: "
            f"{body['membership_state']}"
        )
        membership_id = body["membership_id"]
    else:
        # A refusal is fine; a crash is not, and a 5xx would let a broken route
        # masquerade as a closed door for the rest of this file.
        assert 400 <= redeemed.status_code < 500, (
            "Redeeming an outstanding link neither succeeded nor was refused. "
            f"Got {redeemed.status_code}: {redeemed.text}"
        )

    if con_han:
        # The path assertion. A link inside its window MUST reach an INVITED
        # membership, because that membership id is the only input the
        # self-promotion route takes -- without it the interesting call is
        # simply not made, and every assertion downstream becomes a statement
        # about a request that never happened.
        assert membership_id is not None, (
            "A link still inside its window was refused at redeem "
            f"({redeemed.status_code}), so this walk never reached "
            "/memberships/{id}/accept and proves nothing about self-promotion. "
            "Either the expiry window moved or the redeem route changed; fix "
            f"the fixture rather than letting the case pass. Body: {redeemed.text}"
        )

    async def escalate():
        async with _client(app) as client:
            accepted = None
            if membership_id is not None:
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

    # Read the membership rows back from the table rather than trusting the
    # identity map the routes just wrote through.
    postgres_session.expire_all()
    stranger_states = [
        getattr(membership.state, "name", str(membership.state)).upper()
        for membership in postgres_session.execute(
            select(Membership).where(
                Membership.context_id == context.id,
                Membership.person_id == stranger.id,
            )
        ).scalars()
    ]
    return Walk(redeemed, accepted, after, balances, stranger_states)


def test_a_link_bearer_cannot_promote_themselves_to_active(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """`accept_context_membership` proves only `membership.person_id == actor.id`.

    The redeem step wrote that row one call earlier, so the predicate is
    self-circular: it asks a question the attacker just supplied the answer to.
    Nobody in the group ever chose this person.
    """
    walk = _walk(postgres_session, monkeypatch)

    if walk.accepted is not None:
        assert walk.accepted.status_code == 403, (
            "A link bearer promoted THEMSELVES from INVITED to ACTIVE. "
            f"Got {walk.accepted.status_code}: {walk.accepted.text}"
        )

    # The end state, asserted from the table. A build that refuses the redeem
    # never reaches the branch above, and a case that only checked the branch
    # above would pass there by having nothing left to look at. This line makes
    # the same claim on both paths: nobody in the group chose this person, so no
    # ACTIVE row may exist for them.
    assert "ACTIVE" not in walk.stranger_states, (
        "A link bearer holds an ACTIVE membership nobody in the group chose. "
        f"Rows for the bearer: {walk.stranger_states}"
    )


def test_a_link_bearer_never_reads_the_groups_messages_or_balances(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The consequence, asserted apart from the status code that enables it.

    Stated separately so a fix that only changes a status code cannot satisfy
    the escalation test while the data stays readable.
    """
    walk = _walk(postgres_session, monkeypatch)

    assert walk.after.status_code == 403, (
        "The link bearer is reading the group's messages. "
        f"Got {walk.after.status_code}: {walk.after.text}"
    )
    assert SECRET_MESSAGE not in walk.after.text, (
        "Group message leaked to a link bearer"
    )
    assert walk.balances.status_code == 403, (
        "The link bearer is reading the group's balances. "
        f"Got {walk.balances.status_code}"
    )


def test_a_live_link_bearer_cannot_promote_themselves_to_active(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The same claim, on a link the door actually opens for.

    The two cases above are about a *legacy* row, and after #132 that row is
    refused at redeem. Their protection against self-promotion therefore rests
    on a call that is never made: expiry closed the door one step earlier, which
    is a real fix but a different one.

    This case holds a link that is still inside its window, so the redeem
    succeeds, an INVITED membership exists, and `/memberships/{id}/accept` is
    genuinely exercised with the id the attacker was just handed. That is the
    self-circular predicate from the module docstring, and this is the only case
    in the file that can still go red if it comes back.
    """
    walk = _walk(postgres_session, monkeypatch, con_han=True)

    # `con_han=True` already asserted the walk reached the escalation call, so
    # this is a real response and not a skipped step wearing a green tick.
    assert walk.accepted is not None
    assert walk.accepted.status_code == 403, (
        "A bearer of a LIVE link promoted THEMSELVES from INVITED to ACTIVE. "
        f"Got {walk.accepted.status_code}: {walk.accepted.text}"
    )
    assert "ACTIVE" not in walk.stranger_states, (
        "A live-link bearer holds an ACTIVE membership nobody in the group "
        f"chose. Rows for the bearer: {walk.stranger_states}"
    )
    # And the consequence, so a fix that only changes the status code cannot
    # satisfy this case while the data stays readable.
    assert walk.after.status_code == 403, (
        "The live-link bearer is reading the group's messages. "
        f"Got {walk.after.status_code}: {walk.after.text}"
    )
    assert SECRET_MESSAGE not in walk.after.text, (
        "Group message leaked to a live-link bearer"
    )
