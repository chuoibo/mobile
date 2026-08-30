"""F46 -- group check-in, proved against real PostgreSQL over real HTTP.

A check-in is where a group of people physically were, and at what time. The
brief puts that at the same rank as a phone number, so the interesting tests
here are not "can a member check in": they are what a person standing outside
the group gets back, and whether the coordinates can be reached by any request
that is not gated on membership.

Why PostgreSQL rather than the fake repository, in one sentence: the boundary
being tested is a WHERE clause. `list_memories` filters by `context_id`, and a
dict-backed fake round-trips a missing predicate exactly as cleanly as a
present one -- so cross-group leakage is invisible to a fake by construction.
`test_a_checkin_from_another_group_never_appears` is written so that deleting
that predicate turns it red; that is the mutation the brief asks for.

Two things this file deliberately does NOT prove:

  * that the coordinates are where the group actually was. They come from the
    seed catalogue, not from a phone -- reading GPS is F47 and is not built.
  * that a check-in is honest. Anybody in the group can claim to have been
    anywhere in the catalogue, and nothing here disputes it.

Uses `flush`, never `commit`: `postgres_session` rolls back per test, and the
schema is shared with row-counting tests in this directory that go red if rows
from here survive.
"""

from __future__ import annotations

import uuid

import anyio
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import (
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    Memory,
    Person,
)
from app.places.catalog import PLACES

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

# Taken from the catalogue rather than written out, so a rename in the seed
# file fails here loudly instead of leaving this suite asserting a place that
# no longer exists.
PLACE = PLACES[0]
PLACE_ID = PLACE["id"]
OTHER_PLACE_ID = PLACES[1]["id"]


def _photo_url(context_id: uuid.UUID) -> str:
    """A url shaped like the one `POST /contexts/{id}/photos` hands back.

    `image_url` only accepts a pointer into this group's own photo storage --
    an off-site url is refused at the schema, because the poster picking the
    host is how a memory wall turns into a tracking pixel.
    """

    return f"/contexts/{context_id}/photos/{uuid.uuid4()}"


def _http(session: Session, monkeypatch: pytest.MonkeyPatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def _headers(person_id: uuid.UUID) -> dict[str, str]:
    # Both roles on purpose. A header is a claim, not a proof: what decides
    # here is membership, not the role string a client chose to send.
    return {"X-Actor-ID": str(person_id), "X-Actor-Roles": "member,group_admin"}


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _context(session: Session, owner: Person, name: str) -> Context:
    context = Context(id=uuid.uuid4(), display_name=name, created_by_id=owner.id)
    session.add(context)
    session.flush()
    return context


def _join(session: Session, context: Context, person: Person) -> Membership:
    membership = Membership(
        id=uuid.uuid4(),
        context_id=context.id,
        person_id=person.id,
        state=MembershipState.ACTIVE,
        role=MembershipRole.MEMBER,
        joined_at=NOW,
    )
    session.add(membership)
    session.flush()
    return membership


def _group(session: Session, name: str = "Team Đà Lạt") -> tuple[Context, Person]:
    owner = _person(session, "Minh Anh")
    context = _context(session, owner, name)
    _join(session, context, owner)
    return context, owner


def _run(app, exchange):
    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await exchange(client)

    return anyio.run(go)


def test_a_member_checks_in_and_the_place_comes_from_the_catalogue(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The happy path, and the fact that the server named the place.

    The request carries an id and nothing else. If the name or the coordinates
    on the response came from anywhere but `catalog.py`, this fails -- which is
    what stops a client writing "the group was at 0,0" into a permanent record.
    """

    context, owner = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    async def exchange(client):
        posted = await client.post(
            f"/contexts/{context.id}/checkins",
            headers=_headers(owner.id),
            json={"place_id": PLACE_ID, "caption": "Tới rồi nha"},
        )
        listed = await client.get(
            f"/contexts/{context.id}/memories", headers=_headers(owner.id)
        )
        return posted, listed

    posted, listed = _run(app, exchange)

    assert posted.status_code == 201, posted.text
    body = posted.json()
    assert body["kind"] == "checkin"
    assert body["place_id"] == PLACE_ID
    assert body["place_name"] == PLACE["name"]
    assert body["lat"] == PLACE["lat"]
    assert body["lng"] == PLACE["lng"]
    assert body["caption"] == "Tới rồi nha"
    assert body["author_id"] == str(owner.id)
    # A check-in has no photograph, and says so rather than carrying an empty
    # string that a client would render as a broken image.
    assert body["image_url"] is None
    # The moment is the record's own, not something the client asserted.
    assert body["created_at"]

    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert [item["kind"] for item in page["memories"]] == ["checkin"]
    assert page["memories"][0]["cursor"]


def test_the_request_body_cannot_move_the_place(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Extra fields in the body are refused, not quietly obeyed.

    Without this, a caller could try `{"place_id": ..., "lat": 0, "lng": 0}`
    and find out by experiment whether the server took it. `ApiModel` forbids
    unknown fields, so the answer is a 422 -- and this test is what keeps that
    true if somebody ever relaxes the model.
    """

    context, owner = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    async def exchange(client):
        return await client.post(
            f"/contexts/{context.id}/checkins",
            headers=_headers(owner.id),
            json={"place_id": PLACE_ID, "lat": 0.0, "lng": 0.0},
        )

    response = _run(app, exchange)

    assert response.status_code == 422, response.text
    assert postgres_session.scalars(select(Memory)).all() == []


def test_a_place_the_catalogue_never_heard_of_is_refused(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """And the refusal does not echo the id back.

    An error message is the part of a response that ends up pasted into a
    group chat. `place_id` arrives from a client, so it stays out of the
    sentence -- the same rule the guest page follows about not reflecting
    input.
    """

    context, owner = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    invented = "p-nha-toi-khong-co-that"

    async def exchange(client):
        return await client.post(
            f"/contexts/{context.id}/checkins",
            headers=_headers(owner.id),
            json={"place_id": invented},
        )

    response = _run(app, exchange)

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "place_not_found"
    assert invented not in response.text
    assert postgres_session.scalars(select(Memory)).all() == []


def test_a_stranger_can_neither_read_nor_write_a_groups_checkins(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The acceptance criterion, at the boundary a real client uses.

    The read is checked *after* a real check-in exists. Refusing an empty wall
    proves nothing: the question is whether coordinates that are actually in
    the table can be reached by somebody outside the group.
    """

    context, owner = _group(postgres_session)
    outsider = _person(postgres_session, "Người lạ")
    app = _http(postgres_session, monkeypatch)

    async def exchange(client):
        await client.post(
            f"/contexts/{context.id}/checkins",
            headers=_headers(owner.id),
            json={"place_id": PLACE_ID},
        )
        posted = await client.post(
            f"/contexts/{context.id}/checkins",
            headers=_headers(outsider.id),
            json={"place_id": OTHER_PLACE_ID},
        )
        listed = await client.get(
            f"/contexts/{context.id}/memories", headers=_headers(outsider.id)
        )
        filtered = await client.get(
            f"/contexts/{context.id}/memories?kind=checkin",
            headers=_headers(outsider.id),
        )
        return posted, listed, filtered

    posted, listed, filtered = _run(app, exchange)

    assert posted.status_code == 403, posted.text
    assert listed.status_code == 403, listed.text
    # A filter is not a way in. `kind=checkin` runs the same permission check.
    assert filtered.status_code == 403, filtered.text

    # The refusal must not leak what it is refusing. A 403 that carries the
    # venue's name or its coordinates has already disclosed the thing the
    # status code claims to be withholding.
    for response in (listed, filtered):
        assert PLACE["name"] not in response.text
        assert str(PLACE["lat"]) not in response.text
        assert str(PLACE["lng"]) not in response.text
        assert PLACE_ID not in response.text

    # And nothing the outsider sent was written.
    kept = postgres_session.scalars(select(Memory)).all()
    assert [row.author_id for row in kept] == [owner.id]


def test_a_checkin_from_another_group_never_appears(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The mutation target.

    One person is in both groups, so membership cannot be what separates the
    two feeds -- only the `context_id` predicate in `list_memories` can be.
    Delete that predicate and this test goes red; that is the whole reason the
    same person is joined to both.
    """

    ours, owner = _group(postgres_session, "Team Đà Lạt")
    theirs, _ = _group(postgres_session, "Hội Quận 1")
    _join(postgres_session, theirs, owner)
    app = _http(postgres_session, monkeypatch)

    async def exchange(client):
        await client.post(
            f"/contexts/{ours.id}/checkins",
            headers=_headers(owner.id),
            json={"place_id": PLACE_ID},
        )
        await client.post(
            f"/contexts/{theirs.id}/checkins",
            headers=_headers(owner.id),
            json={"place_id": OTHER_PLACE_ID},
        )
        return await client.get(
            f"/contexts/{ours.id}/memories", headers=_headers(owner.id)
        )

    listed = _run(app, exchange)

    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert [item["place_id"] for item in page["memories"]] == [PLACE_ID]
    assert OTHER_PLACE_ID not in listed.text


def test_photos_and_checkins_share_one_wall_and_can_be_narrowed(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """One feed, newest first, with `kind` and `place_id` as filters over it.

    The unfiltered read is asserted first. A `kind` filter that worked while
    the shared feed had quietly stopped returning check-ins would still look
    correct on the screen that uses the filter.
    """

    context, owner = _group(postgres_session)
    photo = _photo_url(context.id)
    app = _http(postgres_session, monkeypatch)

    async def exchange(client):
        await client.post(
            f"/contexts/{context.id}/memories",
            headers=_headers(owner.id),
            json={"image_url": photo, "caption": "Ảnh cả nhóm"},
        )
        await client.post(
            f"/contexts/{context.id}/checkins",
            headers=_headers(owner.id),
            json={"place_id": PLACE_ID},
        )
        await client.post(
            f"/contexts/{context.id}/checkins",
            headers=_headers(owner.id),
            json={"place_id": OTHER_PLACE_ID},
        )
        return (
            await client.get(
                f"/contexts/{context.id}/memories", headers=_headers(owner.id)
            ),
            await client.get(
                f"/contexts/{context.id}/memories?kind=checkin",
                headers=_headers(owner.id),
            ),
            await client.get(
                f"/contexts/{context.id}/memories?kind=photo",
                headers=_headers(owner.id),
            ),
            await client.get(
                f"/contexts/{context.id}/memories?kind=checkin&place_id={PLACE_ID}",
                headers=_headers(owner.id),
            ),
        )

    everything, checkins, photos, here = _run(app, exchange)

    assert sorted(item["kind"] for item in everything.json()["memories"]) == [
        "checkin",
        "checkin",
        "photo",
    ]
    assert [item["kind"] for item in checkins.json()["memories"]] == [
        "checkin",
        "checkin",
    ]
    assert [item["image_url"] for item in photos.json()["memories"]] == [photo]
    assert [item["place_id"] for item in here.json()["memories"]] == [PLACE_ID]


def test_the_database_refuses_a_row_that_is_both_kinds_at_once(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The constraint, not the route.

    Every write today goes through a repository method that cannot produce
    this shape. The constraint is what will still be standing when a later
    writer can -- a seed script, a backfill, a psql session at 2am -- and a
    constraint nobody has ever seen refuse anything is a constraint nobody
    knows is switched on.
    """

    del monkeypatch
    context, owner = _group(postgres_session)

    postgres_session.add(
        Memory(
            id=uuid.uuid4(),
            context_id=context.id,
            author_id=owner.id,
            kind="checkin",
            image_url=_photo_url(context.id),
            place_id=PLACE_ID,
            place_name=PLACE["name"],
            lat=PLACE["lat"],
            lng=PLACE["lng"],
            created_at=NOW,
        )
    )
    with pytest.raises(Exception) as caught:
        postgres_session.flush()
    assert "payload_matches_kind" in str(caught.value)
    postgres_session.rollback()
