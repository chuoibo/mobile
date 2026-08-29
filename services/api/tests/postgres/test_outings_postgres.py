"""Buổi đi chơi (F13/F14/F15) proved against real PostgreSQL over real HTTP.

This is the join between the two halves of the product. Khám phá can pick a
place and chia bill can split what it cost, but until an outing exists there is
nothing for either to hang on -- so the tests here are about the seam, not
about CRUD.

Three things this file is built to catch, none of which a fake repository can
see:

1. **Order is data.** F15 says the timeline keeps the order the person built,
   not the order a clock would impose. A repository that sorts by time reads as
   perfectly correct in a dict-backed fake and quietly rewrites the plan of the
   one person who wanted the bar before the cafe. Only a real ORDER BY proves
   it.
2. **Budget is a number, not a gate.** `budget_per_person_vnd` is đồng, integer,
   and it is a reference figure the group agreed on. Nothing in this product may
   refuse an action because a total went over it. The tests assert the absence
   of enforcement, because an over-eager 409 is the kind of "helpful" rule that
   only shows up when a real group overspends.
3. **A membership boundary the invite link must not widen.** Redeeming a link
   creates an `INVITED` membership, never an `ACTIVE` one -- `is_member` requires
   ACTIVE, so the holder of a link gets no read access to the group's messages,
   memories or balances until a human accepts through the existing route. A
   partial unique index (one open membership per person per group) is what makes
   redeeming twice safe, and that index does not exist in the fake.

Uses `flush`, never `commit`: `postgres_session` rolls back per test and the
schema is shared with row-counting tests in this directory.
"""

from __future__ import annotations

import uuid
from datetime import date

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
    Outing,
    OutingInvite,
    OutingStop,
    Person,
)

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

TITLE = "Đà Lạt cuối tuần"
STARTS_ON = date(2030, 10, 17)
ENDS_ON = date(2030, 10, 19)
HEADCOUNT = 8
BUDGET_VND = 2_500_000

# The PM's own example, in the PM's own order. 21:00 Bar is last because the
# group put it last, not because 21 is the largest number.
PM_TIMELINE = [
    {"at": "08:00", "label": "Cafe", "place_name": "Lưng Chừng Cafe"},
    {"at": "10:00", "label": "Check-in", "place_name": "Homestay Cỏ Hồng"},
    {"at": "12:00", "label": "Lunch", "place_name": "Tiệm Nướng Xóm Lèo"},
    {"at": "14:00", "label": "Sightseeing", "place_name": "Quảng trường"},
    {"at": "18:00", "label": "BBQ", "place_name": None},
    {"at": "21:00", "label": "Bar", "place_name": None},
]


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
    # Both roles on purpose. A header is a claim, not a proof: membership is
    # what decides, never the role string a caller typed.
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


def _join(
    session: Session,
    context: Context,
    person: Person,
    *,
    state: MembershipState = MembershipState.ACTIVE,
    left_at=None,
) -> Membership:
    membership = Membership(
        id=uuid.uuid4(),
        context_id=context.id,
        person_id=person.id,
        state=state,
        role=MembershipRole.MEMBER,
        joined_at=NOW,
        left_at=left_at,
    )
    session.add(membership)
    session.flush()
    return membership


def _group(session: Session) -> tuple[Context, Person, Person]:
    """One group with one member, and one person who is not in it."""
    owner = _person(session, "Minh Anh")
    outsider = _person(session, "Người lạ")
    context = _context(session, owner, "Team Đà Lạt")
    _join(session, context, owner)
    return context, owner, outsider


def _payload(**overrides) -> dict:
    body = {
        "title": TITLE,
        "starts_on": STARTS_ON.isoformat(),
        "ends_on": ENDS_ON.isoformat(),
        "headcount": HEADCOUNT,
        "budget_per_person_vnd": BUDGET_VND,
    }
    body.update(overrides)
    return body


def _make_outing(session: Session, app, owner: Person, context: Context, **overrides):
    async def exchange():
        async with _client(app) as client:
            return await client.post(
                f"/contexts/{context.id}/outings",
                headers=_headers(owner.id),
                json=_payload(**overrides),
            )

    response = anyio.run(exchange)
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------
# F13 -- create an outing
# --------------------------------------------------------------------------


def test_a_member_creates_an_outing_and_reads_it_back(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        async with _client(app) as client:
            created = await client.post(
                f"/contexts/{context.id}/outings",
                headers=_headers(owner.id),
                json=_payload(),
            )
            listed = await client.get(
                f"/contexts/{context.id}/outings", headers=_headers(owner.id)
            )
            return created, listed

    created, listed = anyio.run(exchange)

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["title"] == TITLE
    assert body["starts_on"] == "2030-10-17"
    assert body["ends_on"] == "2030-10-19"
    assert body["headcount"] == HEADCOUNT
    assert body["context_id"] == str(context.id)
    assert body["created_by_id"] == str(owner.id)
    # A fresh outing has no plan yet; the field exists so a client never has to
    # branch on its absence.
    assert body["stops"] == []

    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert [item["title"] for item in page["outings"]] == [TITLE]
    assert page["context_id"] == str(context.id)


def test_the_budget_crosses_the_wire_as_an_integer_of_dong(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Rule 1 of the three money rules, at the only boundary a client sees.

    A float that happens to be exact today is a float that rounds tomorrow, and
    the first place it shows is a screen telling eight people slightly different
    numbers for the same trip.
    """
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    body = _make_outing(postgres_session, app, owner, context)

    assert body["budget_per_person_vnd"] == BUDGET_VND
    assert isinstance(body["budget_per_person_vnd"], int)
    assert not isinstance(body["budget_per_person_vnd"], bool)

    stored = postgres_session.scalar(
        select(Outing.budget_per_person_vnd).where(Outing.id == uuid.UUID(body["id"]))
    )
    assert stored == BUDGET_VND
    assert isinstance(stored, int)


def test_a_float_or_a_string_budget_is_refused_rather_than_coerced(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Coercion is how a rounding error enters a system that has no floats."""
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        async with _client(app) as client:
            floated = await client.post(
                f"/contexts/{context.id}/outings",
                headers=_headers(owner.id),
                json=_payload(budget_per_person_vnd=2_500_000.5),
            )
            whole_float = await client.post(
                f"/contexts/{context.id}/outings",
                headers=_headers(owner.id),
                json=_payload(budget_per_person_vnd=2_500_000.0),
            )
            stringy = await client.post(
                f"/contexts/{context.id}/outings",
                headers=_headers(owner.id),
                json=_payload(budget_per_person_vnd="2500000"),
            )
            negative = await client.post(
                f"/contexts/{context.id}/outings",
                headers=_headers(owner.id),
                json=_payload(budget_per_person_vnd=-1),
            )
            return floated, whole_float, stringy, negative

    floated, whole_float, stringy, negative = anyio.run(exchange)

    assert floated.status_code == 422, floated.text
    # 2500000.0 is the dangerous one: it is exactly representable, so a lenient
    # parser accepts it and the float type spreads from here inward.
    assert whole_float.status_code == 422, whole_float.text
    assert stringy.status_code == 422, stringy.text
    assert negative.status_code == 422, negative.text


def test_the_budget_never_refuses_anything(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Budget is a reference figure, not a limit anybody may be blocked by.

    Zero and an absurdly large figure are both legitimate plans. If either is
    ever rejected, somebody has taught this product to police a group's money.
    """
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        async with _client(app) as client:
            free = await client.post(
                f"/contexts/{context.id}/outings",
                headers=_headers(owner.id),
                json=_payload(title="Đi bộ quanh hồ", budget_per_person_vnd=0),
            )
            lavish = await client.post(
                f"/contexts/{context.id}/outings",
                headers=_headers(owner.id),
                json=_payload(title="Trăng mật", budget_per_person_vnd=900_000_000_000),
            )
            return free, lavish

    free, lavish = anyio.run(exchange)

    assert free.status_code == 201, free.text
    assert free.json()["budget_per_person_vnd"] == 0
    assert lavish.status_code == 201, lavish.text
    assert lavish.json()["budget_per_person_vnd"] == 900_000_000_000


def test_an_outing_that_ends_before_it_starts_is_refused(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        async with _client(app) as client:
            backwards = await client.post(
                f"/contexts/{context.id}/outings",
                headers=_headers(owner.id),
                json=_payload(starts_on="2030-10-19", ends_on="2030-10-17"),
            )
            same_day = await client.post(
                f"/contexts/{context.id}/outings",
                headers=_headers(owner.id),
                json=_payload(starts_on="2030-10-17", ends_on="2030-10-17"),
            )
            blank_title = await client.post(
                f"/contexts/{context.id}/outings",
                headers=_headers(owner.id),
                json=_payload(title="   "),
            )
            no_one = await client.post(
                f"/contexts/{context.id}/outings",
                headers=_headers(owner.id),
                json=_payload(headcount=0),
            )
            return backwards, same_day, blank_title, no_one

    backwards, same_day, blank_title, no_one = anyio.run(exchange)

    assert backwards.status_code == 422, backwards.text
    # A day trip starts and ends on the same day, and that is the common case.
    assert same_day.status_code == 201, same_day.text
    assert blank_title.status_code == 422, blank_title.text
    assert no_one.status_code == 422, no_one.text


def test_a_stranger_can_neither_read_nor_create_outings(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, outsider = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    _make_outing(postgres_session, app, owner, context)

    async def exchange():
        async with _client(app) as client:
            read = await client.get(
                f"/contexts/{context.id}/outings", headers=_headers(outsider.id)
            )
            wrote = await client.post(
                f"/contexts/{context.id}/outings",
                headers=_headers(outsider.id),
                json=_payload(title="Chuyến của người lạ"),
            )
            return read, wrote

    read, wrote = anyio.run(exchange)

    assert read.status_code == 403, read.text
    assert wrote.status_code == 403, wrote.text
    # A refusal is where a plan leaks by accident: neither the trip's name nor
    # its budget may appear in the body that says no.
    assert TITLE not in read.text
    assert "Đà Lạt" not in read.text
    assert "2500000" not in read.text


def test_a_person_who_left_the_group_stops_seeing_its_outings(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Leaving is recorded rather than deleted, so the row still exists.

    A check that asks "is there a row" instead of "is there an open, active
    row" hands the whole trip list to somebody who walked out.
    """
    context, owner, _ = _group(postgres_session)
    former = _person(postgres_session, "Quang Huy")
    _join(postgres_session, context, former, state=MembershipState.LEFT, left_at=NOW)
    app = _http(postgres_session, monkeypatch)
    _make_outing(postgres_session, app, owner, context)

    async def exchange():
        async with _client(app) as client:
            return await client.get(
                f"/contexts/{context.id}/outings", headers=_headers(former.id)
            )

    read = anyio.run(exchange)

    assert read.status_code == 403, read.text
    assert TITLE not in read.text


def test_an_outing_of_another_group_never_appears_in_this_list(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """One person in two groups is the case a missing WHERE clause survives.

    The reader legitimately belongs to both, so no permission check fires. Only
    the query separates the two lists.
    """
    context, owner, _ = _group(postgres_session)
    other = _context(postgres_session, owner, "Team Sa Pa")
    _join(postgres_session, other, owner)
    app = _http(postgres_session, monkeypatch)
    _make_outing(postgres_session, app, owner, context)
    _make_outing(postgres_session, app, owner, other, title="Sa Pa mù sương")

    async def exchange():
        async with _client(app) as client:
            return await client.get(
                f"/contexts/{context.id}/outings", headers=_headers(owner.id)
            )

    read = anyio.run(exchange)

    assert read.status_code == 200, read.text
    assert [item["title"] for item in read.json()["outings"]] == [TITLE]
    assert "Sa Pa" not in read.text


# --------------------------------------------------------------------------
# F15 -- the timeline
# --------------------------------------------------------------------------


def test_the_timeline_keeps_the_order_the_group_built_it_in(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """F15's whole content: "thứ tự giữ nguyên như người dựng".

    The stops go in deliberately out of clock order. A repository that sorts by
    time returns something that looks tidy, passes every fake-backed test, and
    is not the plan the group agreed on.
    """
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    outing = _make_outing(postgres_session, app, owner, context)
    shuffled = [PM_TIMELINE[5], PM_TIMELINE[0], PM_TIMELINE[3]]

    async def exchange():
        async with _client(app) as client:
            put = await client.put(
                f"/outings/{outing['id']}/timeline",
                headers=_headers(owner.id),
                json={"stops": shuffled},
            )
            listed = await client.get(
                f"/contexts/{context.id}/outings", headers=_headers(owner.id)
            )
            return put, listed

    put, listed = anyio.run(exchange)

    assert put.status_code == 200, put.text
    assert [stop["label"] for stop in put.json()["stops"]] == ["Bar", "Cafe", "Sightseeing"]
    assert [stop["at"] for stop in put.json()["stops"]] == ["21:00", "08:00", "14:00"]
    assert [stop["position"] for stop in put.json()["stops"]] == [0, 1, 2]

    # And it survives a round trip through the database, not just the response
    # the writer happened to build in memory.
    assert listed.status_code == 200, listed.text
    reread = listed.json()["outings"][0]["stops"]
    assert [stop["label"] for stop in reread] == ["Bar", "Cafe", "Sightseeing"]


def test_replacing_the_timeline_leaves_no_stops_from_the_previous_plan(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Plans change. A PUT that appends instead of replacing shows a group a
    schedule containing both the cancelled bar and the one that replaced it."""
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    outing = _make_outing(postgres_session, app, owner, context)

    async def exchange():
        async with _client(app) as client:
            await client.put(
                f"/outings/{outing['id']}/timeline",
                headers=_headers(owner.id),
                json={"stops": PM_TIMELINE},
            )
            replaced = await client.put(
                f"/outings/{outing['id']}/timeline",
                headers=_headers(owner.id),
                json={
                    "stops": [
                        {"at": "09:00", "label": "Cafe", "place_name": "Quán mới"}
                    ]
                },
            )
            emptied = await client.put(
                f"/outings/{outing['id']}/timeline",
                headers=_headers(owner.id),
                json={"stops": []},
            )
            return replaced, emptied

    replaced, emptied = anyio.run(exchange)

    assert replaced.status_code == 200, replaced.text
    assert [stop["label"] for stop in replaced.json()["stops"]] == ["Cafe"]
    assert "Xóm Lèo" not in replaced.text

    # Clearing a plan is a thing groups do, and it must actually clear.
    assert emptied.status_code == 200, emptied.text
    assert emptied.json()["stops"] == []
    remaining = postgres_session.scalars(
        select(OutingStop).where(OutingStop.outing_id == uuid.UUID(outing["id"]))
    ).all()
    assert remaining == []


def test_a_malformed_clock_time_is_refused(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Stop times are wall-clock times of day with no timezone at all.

    Storing them as a timestamp is what produces a schedule that shifts by seven
    hours between the phone that wrote it and the server that renders it.
    """
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    outing = _make_outing(postgres_session, app, owner, context)

    async def put(client, stop):
        return await client.put(
            f"/outings/{outing['id']}/timeline",
            headers=_headers(owner.id),
            json={"stops": [stop]},
        )

    async def exchange():
        async with _client(app) as client:
            return (
                await put(client, {"at": "25:00", "label": "Cafe"}),
                await put(client, {"at": "08:70", "label": "Cafe"}),
                await put(client, {"at": "sáng sớm", "label": "Cafe"}),
                await put(client, {"at": "08:00", "label": "  "}),
                await put(client, {"at": "23:59", "label": "Về khách sạn"}),
            )

    hour, minute, words, blank, midnight_edge = anyio.run(exchange)

    assert hour.status_code == 422, hour.text
    assert minute.status_code == 422, minute.text
    assert words.status_code == 422, words.text
    assert blank.status_code == 422, blank.text
    assert midnight_edge.status_code == 200, midnight_edge.text
    assert midnight_edge.json()["stops"][0]["at"] == "23:59"


def test_a_stranger_cannot_rewrite_a_groups_timeline(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, outsider = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    outing = _make_outing(postgres_session, app, owner, context)

    async def exchange():
        async with _client(app) as client:
            forged = await client.put(
                f"/outings/{outing['id']}/timeline",
                headers=_headers(outsider.id),
                json={"stops": [{"at": "08:00", "label": "Của tôi"}]},
            )
            unknown = await client.put(
                f"/outings/{uuid.uuid4()}/timeline",
                headers=_headers(owner.id),
                json={"stops": []},
            )
            return forged, unknown

    forged, unknown = anyio.run(exchange)

    assert forged.status_code == 403, forged.text
    assert TITLE not in forged.text
    assert unknown.status_code == 404, unknown.text


# --------------------------------------------------------------------------
# F14 -- invites
# --------------------------------------------------------------------------


def test_a_member_invites_from_the_group_and_from_their_friends(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Two of F14's three sources. `source` records where the inviter picked
    the person from; it is provenance, and nothing is enforced from it."""
    context, owner, _ = _group(postgres_session)
    inside = _person(postgres_session, "Bảo Trân")
    _join(postgres_session, context, inside)
    friend = _person(postgres_session, "Hải Đăng")
    app = _http(postgres_session, monkeypatch)
    outing = _make_outing(postgres_session, app, owner, context)

    async def exchange():
        async with _client(app) as client:
            from_group = await client.post(
                f"/outings/{outing['id']}/invites",
                headers=_headers(owner.id),
                json={"source": "group", "person_id": str(inside.id)},
            )
            from_friends = await client.post(
                f"/outings/{outing['id']}/invites",
                headers=_headers(owner.id),
                json={"source": "friend", "person_id": str(friend.id)},
            )
            again = await client.post(
                f"/outings/{outing['id']}/invites",
                headers=_headers(owner.id),
                json={"source": "friend", "person_id": str(inside.id)},
            )
            return from_group, from_friends, again

    from_group, from_friends, again = anyio.run(exchange)

    assert from_group.status_code == 201, from_group.text
    assert from_group.json()["source"] == "group"
    assert from_group.json()["invited_person_id"] == str(inside.id)
    assert from_group.json()["invited_by_id"] == str(owner.id)
    # Only a link invite carries a token, and only once.
    assert from_group.json()["invite_token"] is None

    assert from_friends.status_code == 201, from_friends.text
    assert from_friends.json()["source"] == "friend"

    # Inviting the same person twice to the same trip is a duplicate, whichever
    # list the inviter picked them from.
    assert again.status_code == 409, again.text


def test_an_invite_link_stores_only_a_digest_and_shows_the_token_once(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The guest-page token shape, reused: a bearer secret is minted, handed
    back exactly once, and never persisted in a form the database can leak."""
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    outing = _make_outing(postgres_session, app, owner, context)

    async def exchange():
        async with _client(app) as client:
            minted = await client.post(
                f"/outings/{outing['id']}/invites",
                headers=_headers(owner.id),
                json={"source": "link"},
            )
            second = await client.post(
                f"/outings/{outing['id']}/invites",
                headers=_headers(owner.id),
                json={"source": "link"},
            )
            confused = await client.post(
                f"/outings/{outing['id']}/invites",
                headers=_headers(owner.id),
                json={"source": "link", "person_id": str(owner.id)},
            )
            nameless = await client.post(
                f"/outings/{outing['id']}/invites",
                headers=_headers(owner.id),
                json={"source": "group"},
            )
            return minted, second, confused, nameless

    minted, second, confused, nameless = anyio.run(exchange)

    assert minted.status_code == 201, minted.text
    token = minted.json()["invite_token"]
    assert token and len(token) >= 32
    assert minted.json()["invited_person_id"] is None
    assert minted.json()["invite_path"] == f"/outing-invites/{token}"

    # Two links are two different secrets. A constant token would let the first
    # invitee forward a link that keeps working after it is revoked.
    assert second.json()["invite_token"] != token

    stored = postgres_session.scalars(select(OutingInvite.token_digest)).all()
    assert all(digest is None or token.encode() not in digest for digest in stored)
    assert any(digest is not None and len(digest) == 32 for digest in stored)

    # A link invite names nobody; a group invite must name somebody.
    assert confused.status_code == 422, confused.text
    assert nameless.status_code == 422, nameless.text


def test_redeeming_an_invite_link_grants_an_invited_membership_not_an_active_one(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The privacy hinge of this feature.

    A link is a bearer secret that can be forwarded to anyone. If redeeming it
    produced an ACTIVE membership, whoever received the forwarded link would
    immediately be able to read the group's messages, its memory wall and its
    balances -- `is_member` asks for ACTIVE. So redemption lands in INVITED,
    which grants nothing until a human accepts through the existing route.
    """
    context, owner, outsider = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    outing = _make_outing(postgres_session, app, owner, context)

    async def exchange():
        async with _client(app) as client:
            minted = await client.post(
                f"/outings/{outing['id']}/invites",
                headers=_headers(owner.id),
                json={"source": "link"},
            )
            token = minted.json()["invite_token"]
            accepted = await client.post(
                f"/outing-invites/{token}/accept", headers=_headers(outsider.id)
            )
            # Still not a member: the memory wall must stay shut.
            wall = await client.get(
                f"/contexts/{context.id}/memories", headers=_headers(outsider.id)
            )
            trips = await client.get(
                f"/contexts/{context.id}/outings", headers=_headers(outsider.id)
            )
            return accepted, wall, trips

    accepted, wall, trips = anyio.run(exchange)

    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["membership_state"] == "invited"
    assert accepted.json()["outing_id"] == outing["id"]
    # The accepter is not a member yet, so the response may not describe the
    # group it is an invitation to.
    assert TITLE not in accepted.text
    assert "Team Đà Lạt" not in accepted.text

    assert wall.status_code == 403, wall.text
    assert trips.status_code == 403, trips.text

    membership = postgres_session.scalar(
        select(Membership).where(
            Membership.context_id == context.id,
            Membership.person_id == outsider.id,
        )
    )
    assert membership is not None
    assert membership.state == MembershipState.INVITED


def test_a_forged_or_reused_invite_link_is_refused(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Redeeming twice must not attempt a second open membership row: the
    partial unique index would raise, and a 500 is a worse answer than a 409."""
    context, owner, outsider = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    outing = _make_outing(postgres_session, app, owner, context)

    async def exchange():
        async with _client(app) as client:
            minted = await client.post(
                f"/outings/{outing['id']}/invites",
                headers=_headers(owner.id),
                json={"source": "link"},
            )
            token = minted.json()["invite_token"]
            await client.post(
                f"/outing-invites/{token}/accept", headers=_headers(outsider.id)
            )
            reused = await client.post(
                f"/outing-invites/{token}/accept", headers=_headers(outsider.id)
            )
            forged = await client.post(
                "/outing-invites/khong-phai-token-that/accept",
                headers=_headers(outsider.id),
            )
            return reused, forged

    reused, forged = anyio.run(exchange)

    assert reused.status_code == 409, reused.text
    # A wrong token tells the holder nothing about whether the trip exists.
    assert forged.status_code == 404, forged.text
    assert TITLE not in forged.text
    assert "Đà Lạt" not in forged.text


def test_headcount_is_a_plan_and_not_a_door_policy(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """"Participants: 8" is what the group wrote down, not a capacity check.

    A ninth friend turning up is normal. Refusing them is the product deciding
    who may come, which is not its job.
    """
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    outing = _make_outing(postgres_session, app, owner, context, headcount=2)
    guests = [_person(postgres_session, f"Bạn {index}") for index in range(4)]

    async def exchange():
        async with _client(app) as client:
            return [
                await client.post(
                    f"/outings/{outing['id']}/invites",
                    headers=_headers(owner.id),
                    json={"source": "friend", "person_id": str(guest.id)},
                )
                for guest in guests
            ]

    responses = anyio.run(exchange)

    assert [response.status_code for response in responses] == [201, 201, 201, 201]


def test_a_stranger_cannot_invite_anyone_to_a_trip_they_are_not_in(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, outsider = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    outing = _make_outing(postgres_session, app, owner, context)

    async def exchange():
        async with _client(app) as client:
            person_invite = await client.post(
                f"/outings/{outing['id']}/invites",
                headers=_headers(outsider.id),
                json={"source": "friend", "person_id": str(outsider.id)},
            )
            link_invite = await client.post(
                f"/outings/{outing['id']}/invites",
                headers=_headers(outsider.id),
                json={"source": "link"},
            )
            return person_invite, link_invite

    person_invite, link_invite = anyio.run(exchange)

    assert person_invite.status_code == 403, person_invite.text
    assert link_invite.status_code == 403, link_invite.text
    # Minting a link is the highest-value thing an outsider could steal here,
    # so the refusal must not hand one over on the way out.
    assert "invite_token" not in link_invite.text
    assert TITLE not in link_invite.text
