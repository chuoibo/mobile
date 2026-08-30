"""F43/F44/F45 against real PostgreSQL over real HTTP -- who may read what.

The brief for this work put one requirement above the others: **never return a
person's location to somebody who does not share an ACTIVE group with them**,
and never let a group heatmap be walked back to "who was where, and when".

That requirement cannot be tested by a pure function, and it cannot be tested
by the fake repository either. The boundary is a WHERE clause: `list_memories`
filters by `context_id`, and a dict-backed fake round-trips a missing predicate
exactly as cleanly as a present one, so cross-group leakage is invisible to a
fake by construction. The same argument `test_group_checkins_postgres.py` makes.

## Why every refusal here has a matching positive control

A test that only proves an outsider is refused is green on an endpoint that is
broken for *everybody* -- a 500, a typo in the path, a route that was never
registered all satisfy "the outsider did not get the data". So each refusal
below is paired with a member making the same request and getting the data.
The pair is the evidence; either half alone is not.

Uses `flush`, never `commit`: `postgres_session` rolls back per test, and this
directory's schema is shared with row-counting tests that go red if rows from
here survive.
"""

from __future__ import annotations

import uuid

import anyio
import httpx
import pytest
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
    MemoryKind,
    Person,
)
from app.places.catalog import PLACES

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

DA_LAT = PLACES[0]
CAFE = PLACES[1]
SAIGON = next(place for place in PLACES if "Quận 4" in place["address"])


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
    # Both roles on purpose. A header is a claim, not a proof: membership
    # decides, not the role string a client chose to send.
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
    state: MembershipState = MembershipState.ACTIVE,
) -> Membership:
    membership = Membership(
        id=uuid.uuid4(),
        context_id=context.id,
        person_id=person.id,
        state=state,
        role=MembershipRole.MEMBER,
        joined_at=NOW,
        # `ck_memberships_left_state_matches_timestamp` refuses a LEFT row with
        # no departure time. The constraint is doing real work here: "left" and
        # "left at some unknown moment" are not the same fact, and a test
        # fixture that could write the second one would be building a state the
        # product cannot reach.
        left_at=NOW if state is MembershipState.LEFT else None,
    )
    session.add(membership)
    session.flush()
    return membership


def _group(session: Session, name: str = "Team Đà Lạt") -> tuple[Context, Person]:
    owner = _person(session, "Minh Anh")
    context = _context(session, owner, name)
    _join(session, context, owner)
    return context, owner


def _checkin(session: Session, context: Context, author: Person, place: dict) -> Memory:
    memory = Memory(
        id=uuid.uuid4(),
        context_id=context.id,
        author_id=author.id,
        kind=MemoryKind.CHECKIN,
        place_id=place["id"],
        place_name=place["name"],
        lat=place["lat"],
        lng=place["lng"],
        created_at=NOW,
    )
    session.add(memory)
    session.flush()
    return memory


def _run(app, exchange):
    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await exchange(client)

    return anyio.run(go)


def _get(app, path: str, person_id: uuid.UUID):
    async def exchange(client):
        return await client.get(path, headers=_headers(person_id))

    return _run(app, exchange)


def _post(app, path: str, person_id: uuid.UUID, payload: dict):
    async def exchange(client):
        return await client.post(path, headers=_headers(person_id), json=payload)

    return _run(app, exchange)


# ---------------------------------------------------------------------------
# The refusal, and its positive control
# ---------------------------------------------------------------------------


def test_an_outsider_cannot_read_the_map_and_a_member_can(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The pair. Without the second half the first is green on a dead route."""

    context, owner = _group(postgres_session)
    _checkin(postgres_session, context, owner, DA_LAT)
    outsider = _person(postgres_session, "Người lạ")
    app = _http(postgres_session, monkeypatch)

    refused = _get(app, f"/contexts/{context.id}/map", outsider.id)
    allowed = _get(app, f"/contexts/{context.id}/map", owner.id)

    assert refused.status_code == 403, refused.text
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["visited"], "positive control read no visits"
    assert allowed.json()["visited"][0]["place_id"] == DA_LAT["id"]


def test_an_outsider_cannot_read_the_heatmap_and_a_member_can(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner = _group(postgres_session)
    _checkin(postgres_session, context, owner, DA_LAT)
    outsider = _person(postgres_session, "Người lạ")
    app = _http(postgres_session, monkeypatch)

    refused = _get(app, f"/contexts/{context.id}/heatmap", outsider.id)
    allowed = _get(app, f"/contexts/{context.id}/heatmap", owner.id)

    assert refused.status_code == 403, refused.text
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["areas"], "positive control read no areas"
    assert allowed.json()["areas"][0]["id"] == "da-lat"


def test_an_outsider_cannot_ask_for_a_meeting_point_and_a_member_can(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner = _group(postgres_session)
    outsider = _person(postgres_session, "Người lạ")
    app = _http(postgres_session, monkeypatch)
    payload = {"from_areas": ["hcm-quan-1", "hcm-thu-duc"]}

    refused = _post(app, f"/contexts/{context.id}/meet", outsider.id, payload)
    allowed = _post(app, f"/contexts/{context.id}/meet", owner.id, payload)

    assert refused.status_code == 403, refused.text
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["candidates"], "positive control got no candidates"


def test_an_invited_member_is_not_yet_a_member(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """`is_group_member` is satisfied only by an ACTIVE row.

    Being added to a group is something that happens to you; a boundary
    somebody was placed inside without agreeing is not one.
    """

    context, owner = _group(postgres_session)
    _checkin(postgres_session, context, owner, DA_LAT)
    invitee = _person(postgres_session, "Chưa đồng ý")
    _join(postgres_session, context, invitee, MembershipState.INVITED)
    app = _http(postgres_session, monkeypatch)

    refused = _get(app, f"/contexts/{context.id}/map", invitee.id)
    allowed = _get(app, f"/contexts/{context.id}/map", owner.id)

    assert refused.status_code == 403, refused.text
    assert allowed.status_code == 200, allowed.text


def test_someone_who_left_stops_reading_the_map(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """History does not follow a person out of the group."""

    context, owner = _group(postgres_session)
    _checkin(postgres_session, context, owner, DA_LAT)
    gone = _person(postgres_session, "Đã rời nhóm")
    _join(postgres_session, context, gone, MembershipState.LEFT)
    app = _http(postgres_session, monkeypatch)

    refused = _get(app, f"/contexts/{context.id}/heatmap", gone.id)
    allowed = _get(app, f"/contexts/{context.id}/heatmap", owner.id)

    assert refused.status_code == 403, refused.text
    assert allowed.status_code == 200, allowed.text


# ---------------------------------------------------------------------------
# Cross-group isolation -- the WHERE clause a fake cannot test
# ---------------------------------------------------------------------------


def test_another_groups_visits_never_appear_on_this_map(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Deleting the `context_id` predicate in `list_memories` turns this red.

    Both groups exist, both have check-ins, and the places are different so a
    leak is visible rather than coincidentally identical.
    """

    mine, me = _group(postgres_session, "Nhóm mình")
    theirs, them = _group(postgres_session, "Nhóm khác")
    _checkin(postgres_session, mine, me, DA_LAT)
    _checkin(postgres_session, theirs, them, SAIGON)
    app = _http(postgres_session, monkeypatch)

    body = _get(app, f"/contexts/{mine.id}/map", me.id).json()

    seen = {row["place_id"] for row in body["visited"]}
    assert seen == {DA_LAT["id"]}
    assert SAIGON["id"] not in seen
    assert body["scanned_checkins"] == 1


def test_another_groups_visits_never_appear_on_this_heatmap(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    mine, me = _group(postgres_session, "Nhóm mình")
    theirs, them = _group(postgres_session, "Nhóm khác")
    _checkin(postgres_session, mine, me, DA_LAT)
    _checkin(postgres_session, theirs, them, SAIGON)
    app = _http(postgres_session, monkeypatch)

    body = _get(app, f"/contexts/{mine.id}/heatmap", me.id).json()

    assert [area["id"] for area in body["areas"]] == ["da-lat"]
    assert body["resolved_checkins"] == 1


# ---------------------------------------------------------------------------
# What the answers must never contain
# ---------------------------------------------------------------------------


def test_the_map_answer_names_nobody(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Two members check in to the same place. The answer is "2 visits"."""

    context, owner = _group(postgres_session)
    friend = _person(postgres_session, "Bạn thân")
    _join(postgres_session, context, friend)
    _checkin(postgres_session, context, owner, DA_LAT)
    _checkin(postgres_session, context, friend, DA_LAT)
    app = _http(postgres_session, monkeypatch)

    raw = _get(app, f"/contexts/{context.id}/map", owner.id).text
    body = _get(app, f"/contexts/{context.id}/map", owner.id).json()

    assert body["visited"][0]["visit_count"] == 2
    assert str(owner.id) not in raw
    assert str(friend.id) not in raw
    assert "author" not in raw
    assert "created_at" not in raw


def test_the_heatmap_answer_carries_no_person_and_no_time(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """F44's stated requirement, at the wire.

    A district and a count cannot be walked back to an evening. A coordinate
    and a timestamp can, which is why neither is here.
    """

    context, owner = _group(postgres_session)
    friend = _person(postgres_session, "Bạn thân")
    _join(postgres_session, context, friend)
    _checkin(postgres_session, context, owner, DA_LAT)
    _checkin(postgres_session, context, friend, SAIGON)
    app = _http(postgres_session, monkeypatch)

    raw = _get(app, f"/contexts/{context.id}/heatmap", owner.id).text

    assert str(owner.id) not in raw
    assert str(friend.id) not in raw
    assert "author" not in raw
    assert "created_at" not in raw
    assert str(NOW.year) not in raw


def test_the_heatmap_reports_a_centroid_not_the_venue(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Even one visit resolves only to a district, never to the place itself."""

    context, owner = _group(postgres_session)
    _checkin(postgres_session, context, owner, SAIGON)
    app = _http(postgres_session, monkeypatch)

    area = _get(app, f"/contexts/{context.id}/heatmap", owner.id).json()["areas"][0]

    assert area["id"] == "hcm-quan-4"
    assert area["lat"] != SAIGON["lat"]
    assert area["lng"] != SAIGON["lng"]


def test_a_group_with_no_history_gets_an_empty_map_not_an_error(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """A new group is the common case on demo day."""

    context, owner = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    body = _get(app, f"/contexts/{context.id}/map", owner.id).json()

    assert body["visited"] == []
    assert body["scanned_checkins"] == 0
    assert body["truncated"] is False
    # Trending and recommended come from the catalogue, so they are populated
    # even for a group that has been nowhere.
    assert body["recommended"]


def test_the_saved_layer_is_declared_missing_rather_than_empty(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """F43 lists four layers and this product has three. An empty `saved`
    array would read as "you have saved nothing", which is a claim about the
    group; "not built" is a claim about the product, and it is the true one."""

    context, owner = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    body = _get(app, f"/contexts/{context.id}/map", owner.id).json()

    declared = {row["layer"] for row in body["unavailable"]}
    assert "saved" in declared
    assert "saved" not in body


def test_recommended_excludes_places_the_group_has_already_been(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner = _group(postgres_session)
    _checkin(postgres_session, context, owner, DA_LAT)
    app = _http(postgres_session, monkeypatch)

    body = _get(app, f"/contexts/{context.id}/map", owner.id).json()

    assert DA_LAT["id"] not in {row["place_id"] for row in body["recommended"]}
    assert DA_LAT["id"] in {row["place_id"] for row in body["visited"]}


# ---------------------------------------------------------------------------
# F45 input handling
# ---------------------------------------------------------------------------


def test_one_area_is_refused_because_it_is_not_a_meeting(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    response = _post(
        app, f"/contexts/{context.id}/meet", owner.id, {"from_areas": ["hcm-quan-1"]}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_origin_count"


def test_an_unknown_area_is_refused_rather_than_silently_dropped(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Dropping it would compute a "fair" point for four friends from three of
    them and present it as the answer for four."""

    context, owner = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    response = _post(
        app,
        f"/contexts/{context.id}/meet",
        owner.id,
        {"from_areas": ["hcm-quan-1", "sao-hoa"]},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "unknown_area"


def test_the_two_origin_inversion_is_disclosed(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """With two origins the midpoint is invertible. That discloses nothing
    here -- both came from this caller -- but a screen showing the result to
    both members has told each of them where the other is, so it is flagged."""

    context, owner = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    two = _post(
        app,
        f"/contexts/{context.id}/meet",
        owner.id,
        {"from_areas": ["hcm-quan-1", "hcm-thu-duc"]},
    ).json()
    three = _post(
        app,
        f"/contexts/{context.id}/meet",
        owner.id,
        {"from_areas": ["hcm-quan-1", "hcm-thu-duc", "hcm-quan-7"]},
    ).json()

    assert two["two_origin_inversion"] is True
    assert three["two_origin_inversion"] is False


def test_the_meeting_answer_names_no_member(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The structural guarantee at the wire: no person was supplied, so none
    can be returned."""

    context, owner = _group(postgres_session)
    friend = _person(postgres_session, "Bạn thân")
    _join(postgres_session, context, friend)
    app = _http(postgres_session, monkeypatch)

    raw = _post(
        app,
        f"/contexts/{context.id}/meet",
        owner.id,
        {"from_areas": ["hcm-quan-1", "hcm-thu-duc"]},
    ).text

    assert str(owner.id) not in raw
    assert str(friend.id) not in raw
    assert "person_id" not in raw


def test_the_meeting_request_has_no_field_for_naming_a_person(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """`MeetingPointRequest` forbids extra fields, so an attempt to attach a
    member to an origin is refused at the schema rather than ignored.

    This is the "no identity from the request body" rule the money routes
    learned the hard way, applied before there is anything to lose.
    """

    context, owner = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    response = _post(
        app,
        f"/contexts/{context.id}/meet",
        owner.id,
        {
            "from_areas": ["hcm-quan-1", "hcm-thu-duc"],
            "person_id": str(owner.id),
        },
    )

    assert response.status_code == 422, response.text
