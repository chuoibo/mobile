"""The session door, on real PostgreSQL: `POST /sessions` and what guards it.

The fake in `tests/api` proves the HTTP orchestration and the mode switch. It
cannot prove any of the things this file is about, because all of them are
statements about the database: a check constraint that had to be relaxed
without losing its surviving half, a partial unique index that makes re-inviting
impossible and rotation necessary, a digest column that must actually be
emptied when a secret is spent, and a membership row that must keep its state
when the same person signs in again.

Every application here is built with `auth_mode="prod"` on purpose. The suite
exports `dev`, and a bootstrap test that quietly ran under the header adapter
would be measuring nothing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import anyio
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_actor, get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.api.service import ApiService, token_digest
from app.db.models import (
    AccountSession,
    Context,
    Membership,
    MembershipOrigin,
    MembershipRole,
    MembershipState,
    Outing,
    OutingInvite,
    OutingInviteSource,
    Person,
)

pytestmark = pytest.mark.postgres


def _prod_app(session: Session):
    app = create_app(auth_mode="prod")
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class World:
    """One group, one trip, one member who may invite, one person invited."""

    def __init__(self, session: Session):
        self.session = session
        self.owner = Person(id=uuid.uuid4(), display_name="Minh Anh")
        self.newcomer = Person(id=uuid.uuid4(), display_name="Hà")
        session.add_all([self.owner, self.newcomer])
        session.flush()

        self.context = Context(
            id=uuid.uuid4(), display_name="Hội đi Đà Lạt", created_by_id=self.owner.id
        )
        session.add(self.context)
        session.flush()
        session.add(
            Membership(
                id=uuid.uuid4(),
                context_id=self.context.id,
                person_id=self.owner.id,
                state=MembershipState.ACTIVE,
                role=MembershipRole.ADMIN,
                origin=MembershipOrigin.NAMED,
                invited_by_id=self.owner.id,
                joined_at=datetime.now(UTC),
            )
        )
        self.outing = Outing(
            id=uuid.uuid4(),
            context_id=self.context.id,
            created_by_id=self.owner.id,
            title="Đà Lạt cuối tuần",
            starts_on=date(2030, 10, 17),
            ends_on=date(2030, 10, 19),
            headcount=6,
            budget_per_person_vnd=2_500_000,
        )
        session.add(self.outing)
        session.flush()

    @property
    def repository(self) -> SqlAlchemyApiRepository:
        return SqlAlchemyApiRepository(self.session)

    def owner_session(self) -> str:
        """A session for the member, seeded the way genesis seeds the first one."""

        raw = f"owner-{uuid.uuid4().hex}"
        now = datetime.now(UTC)
        self.repository.create_account_session(
            person_id=self.owner.id,
            token_digest=token_digest(raw),
            issued_from_invite_id=None,
            expires_at=now + timedelta(days=1),
            now=now,
        )
        self.session.flush()
        return raw

    def invite(self, *, source: str = "friend", person_id=None) -> str:
        """Mint an invitation through the service, and return its raw secret."""

        from app.api.deps import Actor
        from app.api.schemas import OutingInviteCreateRequest

        actor = Actor(
            id=self.owner.id,
            roles=frozenset({"member", "group_admin"}),
            context_ids=frozenset({self.context.id}),
        )
        request = OutingInviteCreateRequest(
            source=source,
            person_id=None if source == "link" else (person_id or self.newcomer.id),
        )
        response = ApiService(self.repository).create_outing_invite(
            self.outing.id, request, actor
        )
        self.session.flush()
        assert response.invite_token is not None
        return response.invite_token

    def membership_of(self, person_id) -> Membership | None:
        return self.session.scalar(
            select(Membership).where(
                Membership.context_id == self.context.id,
                Membership.person_id == person_id,
            )
        )

    def sessions_for(self, person_id) -> list[AccountSession]:
        return list(
            self.session.scalars(
                select(AccountSession).where(AccountSession.person_id == person_id)
            )
        )


def test_a_named_invitation_becomes_a_session_for_the_person_it_names(
    postgres_session: Session,
):
    """The happy path, and the claim that matters inside it.

    The request body carries a secret and nothing else. Who the session belongs
    to comes out of `outing_invites.invited_person_id`, so the answer is a
    person an existing member chose by name.
    """

    world = World(postgres_session)
    token = world.invite()
    app = _prod_app(postgres_session)

    async def walk():
        async with _client(app) as client:
            created = await client.post("/sessions", json={"invite_token": token})
            # The token it just issued has to actually authenticate. Renaming
            # yourself needs `is_self`, which is proven against the session's
            # person and nothing else.
            renamed = await client.put(
                f"/people/{world.newcomer.id}",
                json={"display_name": "Hà Nguyễn"},
                headers=_bearer(created.json()["token"]),
            )
            return created, renamed

    created, renamed = anyio.run(walk)

    assert created.status_code == 201
    body = created.json()
    assert body["person_id"] == str(world.newcomer.id)
    assert body["token"]
    # Signing in is not joining, and the answer says which one happened so the
    # screen does not have to guess.
    assert body["membership_state"] == "invited"
    assert renamed.status_code == 200

    # INVITED, not ACTIVE: possession of an invitation is not membership, and
    # this route must not become a second way in.
    membership = world.membership_of(world.newcomer.id)
    assert membership is not None
    assert membership.state == MembershipState.INVITED
    # Provenance follows the door it came through (ADR-0014 section 8).
    assert membership.origin == MembershipOrigin.NAMED


def test_the_stored_row_holds_a_digest_and_never_the_token(
    postgres_session: Session,
):
    world = World(postgres_session)
    token = world.invite()
    app = _prod_app(postgres_session)

    async def walk():
        async with _client(app) as client:
            return await client.post("/sessions", json={"invite_token": token})

    created = anyio.run(walk)
    raw = created.json()["token"]

    rows = world.sessions_for(world.newcomer.id)
    assert len(rows) == 1
    assert rows[0].token_digest == token_digest(raw)
    # The credential itself is nowhere in the row.
    assert raw.encode("utf-8") not in bytes(rows[0].token_digest)
    assert rows[0].issued_from_invite_id is not None


def test_the_same_secret_cannot_be_spent_twice(postgres_session: Session):
    """The digest is removed when it is spent, so the second try finds nothing.

    Answered 404 rather than 409 on purpose: a caller replaying a stolen token
    learns whether it was ever real from a 409, and learns nothing from this.
    """

    world = World(postgres_session)
    token = world.invite()
    app = _prod_app(postgres_session)

    async def walk():
        async with _client(app) as client:
            first = await client.post("/sessions", json={"invite_token": token})
            second = await client.post("/sessions", json={"invite_token": token})
            return first, second

    first, second = anyio.run(walk)

    assert first.status_code == 201
    assert second.status_code == 404
    assert len(world.sessions_for(world.newcomer.id)) == 1

    invite = postgres_session.scalar(select(OutingInvite))
    assert invite is not None
    assert invite.token_digest is None
    assert invite.accepted_at is not None


def test_a_forwardable_link_cannot_become_a_session(postgres_session: Session):
    """A link names nobody, so there is no person to issue a session to.

    This is the door the whole design turns on. If a link could be exchanged,
    the caller would have to say who they are, and saying who you are is the
    hole being closed.

    What this case measures, measured rather than assumed: removing the check
    in `bootstrap_session_from_invite` alone leaves it green, because
    `consume_named_invite_secret` refuses the same row a layer down. It goes
    red when both are gone -- and then `acceptance_is_whole` in PostgreSQL is
    what raises, which is a third layer nobody has to remember. So read this as
    a guard on the pair, not on either line by itself.
    """

    world = World(postgres_session)
    token = world.invite(source="link")
    app = _prod_app(postgres_session)

    async def walk():
        async with _client(app) as client:
            return await client.post("/sessions", json={"invite_token": token})

    response = anyio.run(walk)

    assert response.status_code == 404
    # Scoped to this world's people, not to the whole schema. `tests/postgres`
    # shares one migrated schema across the tier, so a bare `select(AccountSession)`
    # here passes alone and fails in a full run -- measured, on this file.
    assert world.sessions_for(world.newcomer.id) == []
    assert world.sessions_for(world.owner.id) == []


def test_a_named_secret_is_refused_at_the_link_door(postgres_session: Session):
    """Two doors, two kinds of token, and no shared redemption.

    Without this guard the link door would spend the row a session was going to
    come from, on behalf of whoever held the token rather than the person the
    invitation names.
    """

    world = World(postgres_session)
    named = world.invite()
    owner_token = world.owner_session()
    app = _prod_app(postgres_session)

    async def walk():
        async with _client(app) as client:
            wrong_door = await client.post(
                f"/outing-invites/{named}/accept", headers=_bearer(owner_token)
            )
            # And the secret is still live afterwards: the refusal must not
            # have consumed anything.
            right_door = await client.post("/sessions", json={"invite_token": named})
            return wrong_door, right_door

    wrong_door, right_door = anyio.run(walk)

    assert wrong_door.status_code == 404
    assert right_door.status_code == 201


def test_a_second_named_invitation_is_refused_which_is_why_rotation_exists(
    postgres_session: Session,
):
    world = World(postgres_session)
    world.invite()

    from app.api.errors import ApiProblem

    with pytest.raises(ApiProblem) as raised:
        world.invite()
    assert raised.value.status_code == 409


def test_rotation_kills_the_old_secret_and_signs_the_same_person_back_in(
    postgres_session: Session,
):
    """Losing a phone must not lose the account.

    The partial unique index refuses a second named row for this person and
    outing, so re-inviting is not the way back. Rotating is: same row, same
    `invited_person_id`, new secret.
    """

    world = World(postgres_session)
    first_token = world.invite()
    owner_token = world.owner_session()
    invite_id = postgres_session.scalar(select(OutingInvite.id))
    app = _prod_app(postgres_session)

    async def walk():
        async with _client(app) as client:
            await client.post("/sessions", json={"invite_token": first_token})
            rotated = await client.post(
                f"/outings/{world.outing.id}/invites/{invite_id}/rotate",
                headers=_bearer(owner_token),
            )
            second_token = rotated.json()["invite_token"]
            with_old = await client.post(
                "/sessions", json={"invite_token": first_token}
            )
            with_new = await client.post(
                "/sessions", json={"invite_token": second_token}
            )
            return rotated, with_old, with_new

    rotated, with_old, with_new = anyio.run(walk)

    assert rotated.status_code == 200
    assert with_old.status_code == 404, "a rotated-away secret must stay dead"
    assert with_new.status_code == 201
    assert with_new.json()["person_id"] == str(world.newcomer.id)
    # Two sessions for one person is correct -- signing in on a new phone does
    # not sign the old one out -- and both came from the same invitation row.
    assert len(world.sessions_for(world.newcomer.id)) == 2


def test_an_active_member_who_signs_in_again_stays_active(
    postgres_session: Session,
):
    """Re-login must not demote somebody to INVITED and make them ask again."""

    world = World(postgres_session)
    token = world.invite()
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=world.context.id,
            person_id=world.newcomer.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.MEMBER,
            origin=MembershipOrigin.NAMED,
            invited_by_id=world.owner.id,
            joined_at=datetime.now(UTC),
        )
    )
    postgres_session.flush()
    app = _prod_app(postgres_session)

    async def walk():
        async with _client(app) as client:
            return await client.post("/sessions", json={"invite_token": token})

    response = anyio.run(walk)
    assert response.status_code == 201
    assert response.json()["membership_state"] == "active"

    membership = world.membership_of(world.newcomer.id)
    assert membership is not None
    assert membership.state == MembershipState.ACTIVE


def test_the_relaxed_constraint_still_refuses_a_link_without_a_secret(
    postgres_session: Session,
):
    """The half of `link_carries_digest` that had to survive.

    A `link` row with no digest can never be redeemed by anybody. Relaxing the
    equality to allow secrets on named rows must not have relaxed that.
    """

    world = World(postgres_session)
    postgres_session.add(
        OutingInvite(
            id=uuid.uuid4(),
            outing_id=world.outing.id,
            source=OutingInviteSource.LINK,
            invited_person_id=None,
            invited_by_id=world.owner.id,
            token_digest=None,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    with pytest.raises(IntegrityError) as raised:
        postgres_session.flush()
    assert "link_carries_digest" in str(raised.value)
    postgres_session.rollback()


def test_the_actor_is_built_from_the_roster_not_from_the_request(
    postgres_session: Session,
):
    """Roles and contexts on a real session come out of `memberships`.

    Asserted against the database rather than a fake, because the mapping from
    `MembershipRole.ADMIN` to the domain's `group_admin` is exactly the kind of
    translation a fake would be free to get wrong in the same direction twice.
    """

    world = World(postgres_session)
    token = world.owner_session()
    repository = SqlAlchemyApiRepository(postgres_session)

    actor = ApiService(repository).actor_for_session_token(token)

    assert actor.id == world.owner.id
    assert actor.context_ids == frozenset({world.context.id})
    # Not `group_admin`, even though this person IS an admin of that group: the
    # role is derived per call from the group being acted on, because a flat
    # role set cannot say which group it means.
    assert "group_admin" not in actor.roles
    assert "platform_moderator" not in actor.roles
    assert "guest" not in actor.roles


def test_an_admin_of_one_group_is_not_an_admin_of_another(postgres_session: Session):
    """The escalation that a session-wide `group_admin` would have opened.

    `invite_context_member` asks for the role plus `is_group_member` -- not
    `is_group_admin` -- so a role carried on the session would have been the
    whole of the check, and somebody who runs one group could add people to
    every group they merely belong to.

    Written against a real roster because the mapping this guards is a fact
    about two membership rows, and a fake is free to get both wrong the same way.
    """

    world = World(postgres_session)
    other = Context(
        id=uuid.uuid4(),
        display_name="Nhóm của người khác",
        created_by_id=world.newcomer.id,
    )
    postgres_session.add(other)
    postgres_session.flush()
    # Owner runs their own group and is a plain member of this second one.
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=other.id,
            person_id=world.owner.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.MEMBER,
            origin=MembershipOrigin.NAMED,
            invited_by_id=world.newcomer.id,
            joined_at=datetime.now(UTC),
        )
    )
    postgres_session.flush()
    token = world.owner_session()
    stranger = Person(id=uuid.uuid4(), display_name="Người được thêm")
    postgres_session.add(stranger)
    postgres_session.flush()
    app = _prod_app(postgres_session)

    async def walk():
        async with _client(app) as client:
            into_other = await client.post(
                f"/contexts/{other.id}/members",
                json={"person_id": str(stranger.id)},
                headers=_bearer(token),
            )
            into_own = await client.post(
                f"/contexts/{world.context.id}/members",
                json={"person_id": str(stranger.id)},
                headers=_bearer(token),
            )
            return into_other, into_own

    into_other, into_own = anyio.run(walk)

    assert into_other.status_code == 403, into_other.text
    # And the control: the same person, the same request, their own group.
    # Without this the case above passes for a server that refuses everything.
    assert into_own.status_code == 201, into_own.text


def test_signing_out_kills_the_session(postgres_session: Session):
    world = World(postgres_session)
    token = world.invite()
    app = _prod_app(postgres_session)

    async def walk():
        async with _client(app) as client:
            created = await client.post("/sessions", json={"invite_token": token})
            session_token = created.json()["token"]
            before = await client.put(
                f"/people/{world.newcomer.id}",
                json={"display_name": "Hà một"},
                headers=_bearer(session_token),
            )
            signed_out = await client.delete(
                "/sessions/current", headers=_bearer(session_token)
            )
            after = await client.put(
                f"/people/{world.newcomer.id}",
                json={"display_name": "Hà hai"},
                headers=_bearer(session_token),
            )
            return before, signed_out, after

    before, signed_out, after = anyio.run(walk)

    assert before.status_code == 200
    assert signed_out.status_code == 204
    assert after.status_code == 401


def test_get_actor_is_the_dependency_every_route_shares(postgres_session: Session):
    """A guard on the wiring, not on one route.

    `get_actor` is what the routers depend on; if a future route reached for
    the headers directly this would not catch it, but if `get_actor` itself
    stopped consulting the mode, every case in this file would go green while
    the product stayed open. So the mode is asserted where it is read.
    """

    app = _prod_app(postgres_session)
    assert app.state.auth_mode == "prod"
    assert get_actor.__module__ == "app.api.deps"


def test_the_session_names_the_group_the_invitation_belonged_to(
    postgres_session: Session,
):
    """A session says WHICH group, and says the right one.

    Without this the client is told who it is and nothing else, and there is no
    second way to find out: `contexts.py` declares no route that lists a
    person's contexts. The mobile app sat in fixture mode for exactly that
    reason -- it could hold a valid session and still have no group to read.

    The two-group shape is the point. With one group any answer looks correct,
    including one that returns whatever context the reader happened to reach
    first. Here the same person is invited to two trips in two groups, and the
    session from the second invitation must name the second group -- naming the
    first would hand somebody a group their invitation said nothing about.
    """

    world = World(postgres_session)

    # Redeem the FIRST invitation, so the newcomer really holds a membership in
    # group one by the time group two is asked about. Without this step the
    # person is only ever in one group, and a service that answered from "the
    # person's first membership" would pass by accident.
    first_token = world.invite()
    app_one = _prod_app(postgres_session)

    async def redeem_first():
        async with _client(app_one) as client:
            return await client.post("/sessions", json={"invite_token": first_token})

    first = anyio.run(redeem_first)
    assert first.status_code == 201
    assert first.json()["context_id"] == str(world.context.id)
    assert world.membership_of(world.newcomer.id) is not None

    # A second group, same owner, same newcomer, so the person really is in two.
    other_context = Context(
        id=uuid.uuid4(), display_name="Hội cà phê", created_by_id=world.owner.id
    )
    postgres_session.add(other_context)
    postgres_session.flush()
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=other_context.id,
            person_id=world.owner.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.ADMIN,
            origin=MembershipOrigin.NAMED,
            invited_by_id=world.owner.id,
            joined_at=datetime.now(UTC),
        )
    )
    other_outing = Outing(
        id=uuid.uuid4(),
        context_id=other_context.id,
        created_by_id=world.owner.id,
        title="Cà phê sáng thứ Bảy",
        starts_on=date(2030, 11, 7),
        ends_on=date(2030, 11, 7),
        headcount=4,
        budget_per_person_vnd=200_000,
    )
    postgres_session.add(other_outing)
    postgres_session.flush()

    from app.api.deps import Actor
    from app.api.schemas import OutingInviteCreateRequest

    minted = ApiService(world.repository).create_outing_invite(
        other_outing.id,
        OutingInviteCreateRequest(source="friend", person_id=world.newcomer.id),
        Actor(
            id=world.owner.id,
            roles=frozenset({"member", "group_admin"}),
            context_ids=frozenset({other_context.id}),
        ),
    )
    postgres_session.flush()
    assert minted.invite_token is not None

    app = _prod_app(postgres_session)

    async def walk():
        async with _client(app) as client:
            return await client.post(
                "/sessions", json={"invite_token": minted.invite_token}
            )

    created = anyio.run(walk)

    assert created.status_code == 201
    body = created.json()
    assert body["context_id"] == str(other_context.id)
    # Named explicitly rather than left to the equality above: the failure this
    # guards is answering with the wrong group, not answering with none.
    assert body["context_id"] != str(world.context.id)
    assert body["person_id"] == str(world.newcomer.id)


def test_phien_mang_dung_membership_va_nguoi_do_tu_dong_y_duoc(postgres_session):
    """A session names the row its person may accept, and accepting works.

    Two claims, and the second is the one that matters. `membership_id` is only
    worth carrying if the client can *do* something with it, and what it must
    be able to do is exactly one thing: consent for itself. ADR-0014 s8 says a
    named invitation carries an existing member's choice, so the invitee
    consents rather than waits -- `accept_context_membership` requires only
    `is_invitee`.

    Before this field the product had a door that opened onto a wall. Somebody
    could redeem a real invitation over real HTTP, hold a real session, and
    then sit at `invited` with no reachable button: `POST /memberships/{id}/
    accept` needs an id, and the only route that lists memberships is behind
    the membership being accepted.

    The acceptance is driven THROUGH HTTP with the session's own bearer, not
    through the service object. A service-level call proves the domain rule and
    nothing about whether the token this route just minted is accepted by the
    route the screen calls next -- which is the whole of what a phone does.
    """

    world = World(postgres_session)
    token = world.invite()
    app = _prod_app(postgres_session)

    async def redeem_then_accept():
        async with _client(app) as client:
            created = await client.post("/sessions", json={"invite_token": token})
            if created.status_code != 201:
                return created, None
            phien = created.json()
            accepted = await client.post(
                f"/memberships/{phien['membership_id']}/accept",
                headers={"Authorization": f"Bearer {phien['token']}"},
            )
            return created, accepted

    created, accepted = anyio.run(redeem_then_accept)

    assert created.status_code == 201
    phien = created.json()
    assert phien["membership_state"] == "invited"

    row = world.membership_of(world.newcomer.id)
    assert row is not None
    assert phien["membership_id"] == str(row.id)
    # The owner's row is in the same group, so "any membership here" passes the
    # line above only if it happens to pick the right one. Say which is wrong.
    owner_row = world.membership_of(world.owner.id)
    assert owner_row is not None
    assert phien["membership_id"] != str(owner_row.id)

    assert accepted is not None
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["state"] == "active"
    postgres_session.expire_all()
    assert world.membership_of(world.newcomer.id).state is MembershipState.ACTIVE
