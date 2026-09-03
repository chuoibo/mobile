"""Profile and saved places on the real repository, real HTTP, `prod` auth mode.

What only PostgreSQL can show: the five COUNT queries read the right tables
(an accepted edge counted once whichever direction it was asked in, a LEFT
membership not a context, an outing of a left group not an outing, stops
counted per stop not per row); the public view's relation comes from the
friend graph and the roster; `saved_places` refuses a second row for one
bookmark and the route turns that into 200, not 409; a PATCH persists.
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

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.api.service import token_digest
from app.db.models import (
    AccountIdentity,
    Context,
    FriendRequest,
    FriendRequestState,
    Membership,
    MembershipOrigin,
    MembershipRole,
    MembershipState,
    Memory,
    MemoryKind,
    Outing,
    OutingStop,
    OutingStopCheckin,
    Person,
    SavedPlace,
)
from app.places.catalog import PLACES

pytestmark = pytest.mark.postgres

PLACE = PLACES[0]["id"]


def _prod_app(session: Session):
    app = create_app(auth_mode="prod")
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def _call(app, method: str, path: str, *, token: str, json=None):
    async def go():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.request(
                method, path, json=json, headers={"Authorization": f"Bearer {token}"}
            )

    return anyio.run(go)


class World:
    """Me, a friend who shares no group, a groupmate, a stranger; one active
    group, one I left; an outing in each; check-ins at two stops; two memories."""

    def __init__(self, session: Session):
        self.session = session
        self.now = datetime.now(UTC)
        self.me = Person(id=uuid.uuid4(), display_name="Tôi")
        self.friend = Person(id=uuid.uuid4(), display_name="Bạn thân")
        self.mate = Person(id=uuid.uuid4(), display_name="Đồng nhóm")
        self.stranger = Person(id=uuid.uuid4(), display_name="Người lạ")
        session.add_all([self.me, self.friend, self.mate, self.stranger])
        session.flush()
        self.a = self._context("Hội A")
        self.left = self._context("Nhóm cũ")
        self._member(self.a, self.me, MembershipState.ACTIVE, MembershipRole.ADMIN)
        self._member(self.a, self.mate, MembershipState.ACTIVE)
        self._member(self.left, self.me, MembershipState.LEFT)
        self._member(self.left, self.stranger, MembershipState.ACTIVE)
        # Friendship asked by the FRIEND, so the count is checked against the
        # direction the reader did not initiate.
        session.add(
            FriendRequest(
                id=uuid.uuid4(),
                requester_id=self.friend.id,
                addressee_id=self.me.id,
                state=FriendRequestState.ACCEPTED,
                decided_by_id=self.me.id,
                created_at=self.now,
                decided_at=self.now,
            )
        )
        session.add(
            FriendRequest(
                id=uuid.uuid4(),
                requester_id=self.me.id,
                addressee_id=self.stranger.id,
                state=FriendRequestState.PENDING,
                created_at=self.now,
            )
        )
        outing_a = self._outing(self.a)
        self._outing(self.left)
        stop_1 = self._stop(outing_a, 0)
        stop_2 = self._stop(outing_a, 1)
        # One row per (stop, person): `uq_outing_stop_checkins_person` forbids a
        # second arrival at one stop, so «distinct stops» is two stops for me and
        # one of them shared with the groupmate.
        for stop in (stop_1, stop_2):
            session.add(
                OutingStopCheckin(
                    id=uuid.uuid4(), stop_id=stop.id, person_id=self.me.id
                )
            )
        session.add(
            OutingStopCheckin(
                id=uuid.uuid4(), stop_id=stop_1.id, person_id=self.mate.id
            )
        )
        for _ in range(2):
            session.add(
                Memory(
                    id=uuid.uuid4(),
                    context_id=self.a.id,
                    author_id=self.me.id,
                    kind=MemoryKind("photo"),
                    image_url="memories/x.jpg",
                )
            )
        session.add(
            AccountIdentity(
                person_id=self.me.id,
                provider="phone",
                subject="digest-me",
                last_login_at=self.now,
            )
        )
        session.flush()

    def _context(self, name: str) -> Context:
        context = Context(id=uuid.uuid4(), display_name=name, created_by_id=self.me.id)
        self.session.add(context)
        self.session.flush()
        return context

    def _member(self, context, person, state, role=MembershipRole.MEMBER) -> Membership:
        row = Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=person.id,
            state=state,
            role=role,
            origin=MembershipOrigin.NAMED,
            invited_by_id=self.me.id,
            joined_at=self.now if state == MembershipState.ACTIVE else None,
            left_at=self.now if state == MembershipState.LEFT else None,
        )
        self.session.add(row)
        return row

    def _outing(self, context) -> Outing:
        row = Outing(
            id=uuid.uuid4(),
            context_id=context.id,
            created_by_id=self.me.id,
            title="Đi chơi",
            starts_on=date(2030, 10, 17),
            ends_on=date(2030, 10, 18),
            headcount=2,
            budget_per_person_vnd=0,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def _stop(self, outing, position: int) -> OutingStop:
        row = OutingStop(
            id=uuid.uuid4(),
            outing_id=outing.id,
            position=position,
            minute_of_day=600 + position,
            label=f"Chặng {position}",
        )
        self.session.add(row)
        self.session.flush()
        return row

    def session_for(self, person) -> str:
        raw = f"tok-{uuid.uuid4().hex}"
        SqlAlchemyApiRepository(self.session).create_account_session(
            person_id=person.id,
            token_digest=token_digest(raw),
            issued_from_invite_id=None,
            expires_at=self.now + timedelta(days=1),
            now=self.now,
            issued_via="otp",
        )
        self.session.flush()
        return raw


def test_the_counts_read_the_right_rows(postgres_session):
    world = World(postgres_session)
    app = _prod_app(postgres_session)
    response = _call(app, "GET", "/people/me", token=world.session_for(world.me))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["counts"] == {
        "friends": 1,
        "contexts": 1,
        "outings": 1,
        "places_checked_in": 2,
        "memories": 2,
    }
    assert body["login_methods"] == ["phone"]
    # The friend sees one friend too, from the other side of the same row.
    theirs = _call(app, "GET", "/people/me", token=world.session_for(world.friend))
    assert theirs.json()["counts"]["friends"] == 1
    assert theirs.json()["counts"]["contexts"] == 0
    assert theirs.json()["login_methods"] == []


def test_a_patch_persists_and_the_public_view_follows_the_relation(postgres_session):
    world = World(postgres_session)
    app = _prod_app(postgres_session)
    mine = world.session_for(world.me)
    patched = _call(
        app, "PATCH", "/people/me", token=mine, json={"bio": "Cafe sáng", "city": "Huế"}
    )
    assert patched.status_code == 200, patched.text
    postgres_session.expire_all()
    row = postgres_session.get(Person, world.me.id)
    assert (row.bio, row.city, row.display_name) == ("Cafe sáng", "Huế", "Tôi")

    path = f"/people/{world.me.id}"
    as_friend = _call(app, "GET", path, token=world.session_for(world.friend))
    as_mate = _call(app, "GET", path, token=world.session_for(world.mate))
    as_stranger = _call(app, "GET", path, token=world.session_for(world.stranger))
    nobody = _call(
        app, "GET", f"/people/{uuid.uuid4()}", token=world.session_for(world.stranger)
    )
    assert as_friend.status_code == 200 and as_friend.json()["relation"] == "friend"
    assert as_friend.json()["bio"] == "Cafe sáng"
    assert as_mate.status_code == 200 and as_mate.json()["relation"] == "groupmate"
    # A pending request is not a friendship; a group the reader is still in
    # but I LEFT does not make us groupmates. And an unknown id looks the same.
    assert (
        as_stranger.status_code == 403
        and as_stranger.json()["code"] == "person_not_visible"
    )
    assert nobody.status_code == 403 and nobody.json() == as_stranger.json()


def test_one_bookmark_per_person_and_place_in_the_database_and_over_http(
    postgres_session,
):
    world = World(postgres_session)
    app = _prod_app(postgres_session)
    mine = world.session_for(world.me)
    first = _call(app, "PUT", f"/people/me/saved-places/{PLACE}", token=mine)
    again = _call(app, "PUT", f"/people/me/saved-places/{PLACE}", token=mine)
    assert (first.status_code, again.status_code) == (201, 200), (
        first.text,
        again.text,
    )
    rows = postgres_session.scalars(
        select(SavedPlace).where(SavedPlace.person_id == world.me.id)
    ).all()
    assert [r.place_id for r in rows] == [PLACE]

    # The unique index is the last line of defence, not the route. Inside a
    # savepoint: a plain rollback would also discard the sessions minted above
    # and turn the next request into a 401 that reads like a bookmark bug.
    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(SavedPlace(person_id=world.me.id, place_id=PLACE))
            postgres_session.flush()

    listed = _call(app, "GET", "/people/me/saved-places", token=mine)
    assert [row["place_id"] for row in listed.json()["saved"]] == [PLACE]
    assert listed.json()["saved"][0]["name"] == PLACES[0]["name"]
    unknown = _call(app, "PUT", "/people/me/saved-places/p-khong-co", token=mine)
    assert unknown.status_code == 404 and unknown.json()["code"] == "place_not_found"
    removed = _call(app, "DELETE", f"/people/me/saved-places/{PLACE}", token=mine)
    assert removed.status_code == 204
    assert postgres_session.scalars(select(SavedPlace)).all() == []
