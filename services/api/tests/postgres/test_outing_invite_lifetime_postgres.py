"""bug-151046: an invite link that was already handed out must be killable.

`#128` (bước 2) closed the escalation: a link holder can no longer promote
themselves past INVITED. What it did not touch is the *lifetime* of the link
itself. `accept_outing_invite` proves exactly one thing about a redeemed token
-- `accepted_at IS NULL`, i.e. single use -- and nothing at all about how old it
is or whether anybody wanted it back.

That leaves a bearer token with unbounded life sitting in somebody's chat
history. Turning the mint off (`#124`) never reached those rows; neither did
`#128`, which only changed what a redeemed link *buys*. Both routes that
consume a link stayed mounted the whole time.

So the rows this file cares about are the ones already in the table:

    minted long ago -> never accepted -> still redeemable today, forever

Two ways to end a link, and this file asserts both plus the schema invariant
underneath them:

    expires_at   NOT NULL -- the database, not a code path, guarantees that no
                            link has unbounded life. Rows minted before the
                            column existed are backfilled to `created_at`, i.e.
                            dead on arrival. Handing them a fresh TTL would give
                            every leaked link a new lease, which is the whole
                            defect.
    revoked_at   somebody inside the group takes a link back by hand.

Refusals answer 404, the same shape a forged token gets: a token holder must
not learn from the status code whether the link ever existed.

Run:
    cd services/api && MOBILE_TEST_DATABASE_URL='postgresql+psycopg://...' \
      MOBILE_REQUIRE_POSTGRES_TESTS=1 python3 -m pytest \
      tests/postgres/test_outing_invite_lifetime_postgres.py -q
"""

from __future__ import annotations

import os
import uuid
from datetime import timedelta

import anyio
import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.deps import get_repository
from app.api.errors import RepositoryConflict
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.api.service import OUTING_INVITE_TTL, token_digest
from app.db.models import (
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    OutingInvite,
    OutingInviteSource,
    Person,
)

from .conftest import API_ROOT, DATABASE_URL_ENV, _schema_url
from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

# The revision that introduces expires_at/revoked_at. The backfill test walks up
# to the one before it, plants a row the old way, then upgrades onto it.
LIFETIME_REVISION = "d4a2e7b91c30"
PREVIOUS_REVISION = "c5f141903a2b"


def _headers(person_id: uuid.UUID) -> dict[str, str]:
    return {"X-Actor-ID": str(person_id), "X-Actor-Roles": "member"}


def _http(session: Session):
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )


def _scene(session: Session) -> tuple[Context, Person, Person]:
    """One group with one ACTIVE member, and one stranger outside it."""
    owner = Person(id=uuid.uuid4(), display_name="Minh Anh")
    outsider = Person(id=uuid.uuid4(), display_name="Người cầm link")
    session.add_all([owner, outsider])
    session.flush()
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
        )
    )
    session.flush()
    return context, owner, outsider


async def _make_outing(client: httpx.AsyncClient, context: Context, owner: Person):
    return await client.post(
        f"/contexts/{context.id}/outings",
        json={
            "title": "Đà Lạt 2 ngày",
            "starts_on": "2026-09-05",
            "ends_on": "2026-09-06",
            "headcount": 4,
            "budget_per_person_vnd": 2_500_000,
        },
        headers=_headers(owner.id),
    )


def _membership_of(session: Session, context: Context, person: Person):
    return session.scalar(
        select(Membership).where(
            Membership.context_id == context.id,
            Membership.person_id == person.id,
        )
    )


def test_the_schema_refuses_a_link_with_no_end_of_life(postgres_session: Session):
    """The invariant lives in the column, not in everyone remembering it.

    `expires_at` NOT NULL is what makes "no link lives forever" true of rows
    that already exist, including rows written by code that predates this fix.
    An app-level convention (say, NULL means expired) would put the guarantee
    back where bug-141903 already found it too weak: in a predicate every future
    caller has to read the same way.
    """
    context, owner, _ = _scene(postgres_session)
    outing_id = uuid.uuid4()
    postgres_session.execute(
        text(
            "INSERT INTO outings (id, context_id, title, starts_on, ends_on,"
            " headcount, budget_per_person_vnd, created_by_id, created_at)"
            " VALUES (:id, :context_id, 'Đà Lạt', DATE '2026-09-05',"
            " DATE '2026-09-06', 4, 2500000, :owner, now())"
        ),
        {"id": outing_id, "context_id": context.id, "owner": owner.id},
    )

    postgres_session.add(
        OutingInvite(
            id=uuid.uuid4(),
            outing_id=outing_id,
            source=OutingInviteSource.LINK,
            invited_person_id=None,
            invited_by_id=owner.id,
            token_digest=token_digest("mot-link-khong-co-han"),
            accepted_at=None,
            accepted_by_id=None,
            created_at=NOW,
        )
    )
    with pytest.raises(IntegrityError):
        postgres_session.flush()
    postgres_session.rollback()


def test_a_mint_says_out_loud_when_the_link_dies(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """A caller cannot honour a deadline it is never told about.

    The token is shown once; the expiry has to travel with it, or the UI has no
    way to say "link này hết hạn sau 7 ngày" without guessing the rule.
    """
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    context, owner, _ = _scene(postgres_session)
    app = _http(postgres_session)

    async def mint():
        async with _client(app) as client:
            outing = await _make_outing(client, context, owner)
            return await client.post(
                f"/outings/{outing.json()['id']}/invites",
                json={"source": "link"},
                headers=_headers(owner.id),
            )

    minted = anyio.run(mint)

    assert minted.status_code == 201, minted.text
    body = minted.json()
    assert body["revoked_at"] is None
    assert body["expires_at"] is not None
    assert body["expires_at"].startswith(
        (NOW + OUTING_INVITE_TTL).isoformat()[:19]
    ), f"expires_at không phải NOW + TTL: {body['expires_at']}"


def test_an_outstanding_link_stops_working_once_it_expires(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The case the ticket is about: nobody revoked it, time did.

    A link nobody ever redeemed is the dangerous kind -- `accepted_at` is still
    NULL, so the single-use check waves it straight through no matter how old
    the row is.
    """
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    context, owner, outsider = _scene(postgres_session)
    app = _http(postgres_session)

    async def mint():
        async with _client(app) as client:
            outing = await _make_outing(client, context, owner)
            return await client.post(
                f"/outings/{outing.json()['id']}/invites",
                json={"source": "link"},
                headers=_headers(owner.id),
            )

    minted = anyio.run(mint)
    assert minted.status_code == 201, minted.text
    token = minted.json()["invite_token"]

    # One second past the deadline is enough; nothing here depends on how long
    # the TTL happens to be.
    monkeypatch.setattr(
        "app.api.service._now", lambda: NOW + OUTING_INVITE_TTL + timedelta(seconds=1)
    )

    async def redeem():
        async with _client(app) as client:
            return await client.post(
                f"/outing-invites/{token}/accept", headers=_headers(outsider.id)
            )

    redeemed = anyio.run(redeem)

    assert redeemed.status_code == 404, (
        "Một link đã quá hạn vẫn đổi được. "
        f"HTTP {redeemed.status_code}: {redeemed.text}"
    )
    # A refusal that still writes the row would be a refusal in name only.
    assert _membership_of(postgres_session, context, outsider) is None, (
        "Link quá hạn bị từ chối nhưng vẫn tạo membership"
    )


def test_a_link_still_inside_its_window_redeems(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The control the expiry cases are worthless without.

    Every other case here asserts a refusal, and refusals all pass at once if
    the deadline comparison is simply always true. This is the case that goes
    red when the fix stops distinguishing links and starts rejecting the lot --
    which is the shape a too-eager expiry bug actually has in production.

    One second short of the deadline on purpose: an in-date link at the very
    edge is the one a `<=`/`<` slip would get wrong.
    """
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    context, owner, outsider = _scene(postgres_session)
    app = _http(postgres_session)

    async def mint():
        async with _client(app) as client:
            outing = await _make_outing(client, context, owner)
            return await client.post(
                f"/outings/{outing.json()['id']}/invites",
                json={"source": "link"},
                headers=_headers(owner.id),
            )

    minted = anyio.run(mint)
    assert minted.status_code == 201, minted.text
    token = minted.json()["invite_token"]

    monkeypatch.setattr(
        "app.api.service._now",
        lambda: NOW + OUTING_INVITE_TTL - timedelta(seconds=1),
    )

    async def redeem():
        async with _client(app) as client:
            return await client.post(
                f"/outing-invites/{token}/accept", headers=_headers(outsider.id)
            )

    redeemed = anyio.run(redeem)

    assert redeemed.status_code == 200, (
        "Link CHƯA hết hạn bị từ chối -- hạn dùng đang chặn nhầm tất cả. "
        f"HTTP {redeemed.status_code}: {redeemed.text}"
    )
    # A 200 that wrote nothing would pass a status-code-only assertion.
    membership = _membership_of(postgres_session, context, outsider)
    assert membership is not None, "Redeem trả 200 nhưng không có membership nào"
    # Still INVITED, not ACTIVE: the link buys a request, not entry (bug-141903).
    assert membership.state == MembershipState.INVITED, membership.state


def test_the_repository_refuses_an_expired_link_even_when_nothing_checked_first(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The repository copy of the deadline, pinned on its own.

    `ApiService` reads the invite WITHOUT a lock and checks it there; the
    repository then re-checks while holding `FOR UPDATE`. Going through HTTP
    can never tell those two apart -- the service refuses first, so the
    repository's copy is never reached and deleting it leaves the suite green.

    This calls the adapter directly with a clock past the deadline, which is
    also the real TOCTOU story: the row can expire between the unlocked read
    and the write.
    """
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    context, owner, outsider = _scene(postgres_session)
    app = _http(postgres_session)

    async def mint():
        async with _client(app) as client:
            outing = await _make_outing(client, context, owner)
            return await client.post(
                f"/outings/{outing.json()['id']}/invites",
                json={"source": "link"},
                headers=_headers(owner.id),
            )

    minted = anyio.run(mint)
    assert minted.status_code == 201, minted.text
    invite_id = uuid.UUID(minted.json()["id"])

    repository = SqlAlchemyApiRepository(postgres_session)

    # A real person on purpose: with a made-up id, dropping the deadline check
    # would blow up on the accepter foreign key, and the test would still go red
    # while proving nothing about the deadline.
    with pytest.raises(RepositoryConflict) as raised:
        repository.accept_outing_invite(
            invite_id=invite_id,
            accepted_by_id=outsider.id,
            now=NOW + OUTING_INVITE_TTL + timedelta(seconds=1),
        )

    assert raised.value.code == "OUTING_INVITE_NOT_REDEEMABLE", raised.value.code
    invite = postgres_session.get(OutingInvite, invite_id)
    assert invite is not None and invite.accepted_at is None, (
        "Repository ném lỗi nhưng vẫn đóng dấu accepted_at"
    )


def test_the_repository_still_redeems_a_link_inside_its_window(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Same control, one layer down: the adapter must not refuse everything."""
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    context, owner, outsider = _scene(postgres_session)
    app = _http(postgres_session)

    async def mint():
        async with _client(app) as client:
            outing = await _make_outing(client, context, owner)
            return await client.post(
                f"/outings/{outing.json()['id']}/invites",
                json={"source": "link"},
                headers=_headers(owner.id),
            )

    minted = anyio.run(mint)
    assert minted.status_code == 201, minted.text
    invite_id = uuid.UUID(minted.json()["id"])

    repository = SqlAlchemyApiRepository(postgres_session)

    accepted = repository.accept_outing_invite(
        invite_id=invite_id,
        accepted_by_id=outsider.id,
        now=NOW + OUTING_INVITE_TTL - timedelta(seconds=1),
    )

    assert accepted.accepted_by_id == outsider.id
    assert accepted.accepted_at is not None


def test_a_revoked_link_stops_working_immediately(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Taking a link back is the answer to "it leaked", and it cannot wait a week.

    Expiry alone means an owner who knows a link leaked can only sit and watch
    the clock. Revocation is the route that turns knowing into doing.
    """
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    context, owner, outsider = _scene(postgres_session)
    app = _http(postgres_session)

    async def walk():
        async with _client(app) as client:
            outing = await _make_outing(client, context, owner)
            minted = await client.post(
                f"/outings/{outing.json()['id']}/invites",
                json={"source": "link"},
                headers=_headers(owner.id),
            )
            revoked = await client.post(
                f"/outings/{outing.json()['id']}/invites/"
                f"{minted.json()['id']}/revoke",
                headers=_headers(owner.id),
            )
            redeemed = await client.post(
                f"/outing-invites/{minted.json()['invite_token']}/accept",
                headers=_headers(outsider.id),
            )
            return minted, revoked, redeemed

    minted, revoked, redeemed = anyio.run(walk)

    assert minted.status_code == 201, minted.text
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["revoked_at"] is not None
    # Revoking must never echo the secret back; the token was shown once.
    assert revoked.json()["invite_token"] is None

    assert redeemed.status_code == 404, (
        f"Link đã thu hồi vẫn đổi được. HTTP {redeemed.status_code}: {redeemed.text}"
    )
    assert _membership_of(postgres_session, context, outsider) is None


def test_only_someone_inside_the_group_can_take_a_link_back(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Revocation is a group decision, so it needs a group member.

    Asserted together with the link still working afterwards: a 403 that quietly
    revoked anyway would pass a status-code-only check while doing the damage.
    """
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    context, owner, outsider = _scene(postgres_session)
    app = _http(postgres_session)

    async def walk():
        async with _client(app) as client:
            outing = await _make_outing(client, context, owner)
            minted = await client.post(
                f"/outings/{outing.json()['id']}/invites",
                json={"source": "link"},
                headers=_headers(owner.id),
            )
            refused = await client.post(
                f"/outings/{outing.json()['id']}/invites/"
                f"{minted.json()['id']}/revoke",
                headers=_headers(outsider.id),
            )
            redeemed = await client.post(
                f"/outing-invites/{minted.json()['invite_token']}/accept",
                headers=_headers(outsider.id),
            )
            return refused, redeemed

    refused, redeemed = anyio.run(walk)

    assert refused.status_code == 403, (
        f"Người ngoài nhóm thu hồi được link. HTTP {refused.status_code}: {refused.text}"
    )
    assert redeemed.status_code == 200, (
        "403 nhưng link vẫn bị thu hồi -- lời từ chối chỉ nằm ở status code. "
        f"HTTP {redeemed.status_code}: {redeemed.text}"
    )


def test_the_backfill_kills_every_link_minted_before_the_column_existed(
    postgres_engine: Engine,
):
    """The row this ticket is actually about, migrated forward with data in it.

    Asserting the *consequence* of the backfill on a hand-written row would
    prove only that the enforcement reads the column. This runs Alembic across
    the boundary with a legacy row already present, which is the one thing that
    says something about deployments that already ran the old code.

    Its own schema on purpose: downgrading the session schema would pull the
    table out from under every other test in this layer.
    """
    database_url = make_url(os.environ[DATABASE_URL_ENV])
    schema_name = "invite_backfill_" + uuid.uuid4().hex
    admin_engine = create_engine(database_url, pool_pre_ping=True, hide_parameters=True)
    scoped_url = _schema_url(database_url, schema_name)
    previous = os.environ.get("MOBILE_DATABASE_URL")
    engine: Engine | None = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(CreateSchema(schema_name))
        os.environ["MOBILE_DATABASE_URL"] = scoped_url.render_as_string(
            hide_password=False
        )
        config = Config(str(API_ROOT / "alembic.ini"))
        # Stop one revision short: this is the world every pre-fix deployment
        # is in right now.
        command.upgrade(config, PREVIOUS_REVISION)

        engine = create_engine(scoped_url, pool_pre_ping=True, hide_parameters=True)
        invite_id = uuid.uuid4()
        with engine.begin() as connection:
            person_id, context_id, outing_id = (uuid.uuid4() for _ in range(3))
            connection.execute(
                text(
                    "INSERT INTO people (id, display_name, created_at)"
                    " VALUES (:id, 'Minh Anh', now())"
                ),
                {"id": person_id},
            )
            connection.execute(
                text(
                    "INSERT INTO contexts (id, display_name, created_by_id, created_at)"
                    " VALUES (:id, 'Team Đà Lạt', :owner, now())"
                ),
                {"id": context_id, "owner": person_id},
            )
            connection.execute(
                text(
                    "INSERT INTO outings (id, context_id, title, starts_on, ends_on,"
                    " headcount, budget_per_person_vnd, created_by_id, created_at)"
                    " VALUES (:id, :context_id, 'Đà Lạt', DATE '2026-09-05',"
                    " DATE '2026-09-06', 4, 2500000, :owner, now())"
                ),
                {"id": outing_id, "context_id": context_id, "owner": person_id},
            )
            # A link handed out a year ago and never redeemed.
            connection.execute(
                text(
                    "INSERT INTO outing_invites (id, outing_id, source,"
                    " invited_person_id, invited_by_id, token_digest, accepted_at,"
                    " accepted_by_id, created_at)"
                    " VALUES (:id, :outing_id, 'link', NULL, :owner, :digest, NULL,"
                    " NULL, now() - interval '365 days')"
                ),
                {
                    "id": invite_id,
                    "outing_id": outing_id,
                    "owner": person_id,
                    "digest": token_digest("link-phat-truoc-khi-co-cot"),
                },
            )

        command.upgrade(config, LIFETIME_REVISION)

        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT created_at, expires_at, expires_at <= now() AS is_dead"
                    " FROM outing_invites WHERE id = :id"
                ),
                {"id": invite_id},
            ).one()

        assert row.expires_at == row.created_at, (
            "Backfill cho link cũ một hạn dùng MỚI thay vì khai tử nó: "
            f"created_at={row.created_at} expires_at={row.expires_at}"
        )
        assert row.is_dead, "Link phát trước khi có cột vẫn còn sống sau migration"
    finally:
        if engine is not None:
            engine.dispose()
        if previous is None:
            os.environ.pop("MOBILE_DATABASE_URL", None)
        else:
            os.environ["MOBILE_DATABASE_URL"] = previous
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema_name, cascade=True, if_exists=True))
        admin_engine.dispose()
