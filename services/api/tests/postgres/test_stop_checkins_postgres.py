"""Check-in theo chặng dừng (F46) trên PostgreSQL thật, qua HTTP thật.

Bốn tính chất, và cả bốn đều vô hình với một fake repository:

1. **Một người một lần cho mỗi chặng, do INDEX giữ.** `uq_outing_stop_checkins_person`
   là chỗ luật sống, không phải một câu `if` trong Python. Một dict-backed fake
   dựng lại luật đó bằng chính đoạn `if` đang cần được chứng minh là thừa. Ca
   `test_the_same_person_cannot_check_in_twice` gỡ index ra là ĐỎ.
2. **Chỉ thành viên ACTIVE.** Người ngoài tự khai `X-Actor-Roles: member` vẫn
   bị chặn, và — quan trọng hơn — người giữ membership `INVITED` cũng bị chặn.
   INVITED là trạng thái mà một link mời tạo ra, nên nếu `is_group_member` bị
   nới thành "có hàng membership" thì người mới bấm link đọc được nhóm đã đi
   những đâu. Ca `test_an_invited_member_cannot_check_in` gỡ yêu cầu ACTIVE ra
   là ĐỎ.
3. **Không có vị trí ở bất kỳ đâu.** Check-in là một cái nút. Ca
   `test_no_response_field_carries_a_location` quét toàn bộ JSON trả về, kể cả
   khoá lồng, tìm mọi tên trường mang nghĩa toạ độ. Nó tồn tại để một lần thêm
   `lat` "cho tiện vẽ bản đồ" sau này phải đi qua một ca đỏ.
4. **Sửa lịch trình KHÔNG xoá check-in của chặng không đổi** (bug-223357), còn
   xoá hẳn một chặng thì check-in của *riêng* nó đi theo qua `ondelete=CASCADE`.
   Hai nửa này phải cùng đúng: trước bản vá, thêm một chặng vào cuối là quét
   sạch "đã tới" của cả nhóm vì `replace_outing_stops` xoá rồi chèn lại toàn bộ
   hàng. Bốn ca ở mục 4 ghim cả hai nửa, kể cả giới hạn còn lại (đổi chữ của
   một chặng vẫn mất check-in của nó, vì request không mang id chặng).

Dùng `flush`, không `commit`: `postgres_session` rollback mỗi ca và schema dùng
chung với các ca đếm hàng trong thư mục này.
"""

from __future__ import annotations

import uuid

import anyio
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import MembershipState, OutingStop, OutingStopCheckin

from .test_outings_postgres import (
    PM_TIMELINE,
    _client,
    _context,
    _group,
    _headers,
    _http,
    _join,
    _make_outing,
    _person,
)
from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres


def _put_timeline(app, owner, outing_id, stops: list[dict]) -> list[dict]:
    """Save `stops` as the outing's timeline and return the stops read back."""

    async def exchange():
        async with _client(app) as client:
            return await client.put(
                f"/outings/{outing_id}/timeline",
                headers=_headers(owner.id),
                json={"stops": stops},
            )

    response = anyio.run(exchange)
    assert response.status_code == 200, response.text
    return response.json()["stops"]


def _with_timeline(app, owner, outing_id) -> list[dict]:
    """Give the outing the PM's own timeline and return its stops."""
    return _put_timeline(app, owner, outing_id, PM_TIMELINE)


def _check_in(app, person_id, stop_id):
    async def exchange():
        async with _client(app) as client:
            return await client.post(
                f"/outing-stops/{stop_id}/checkins",
                headers=_headers(person_id),
            )

    return anyio.run(exchange)


def _read_checkins(app, person_id, outing_id):
    async def exchange():
        async with _client(app) as client:
            return await client.get(
                f"/outings/{outing_id}/checkins",
                headers=_headers(person_id),
            )

    return anyio.run(exchange)


def _scene(session: Session, monkeypatch):
    """A group, its outing, and that outing's timeline."""
    context, owner, outsider = _group(session)
    app = _http(session, monkeypatch)
    outing = _make_outing(session, app, owner, context)
    stops = _with_timeline(app, owner, outing["id"])
    return app, context, owner, outsider, outing, stops


# --------------------------------------------------------------------------
# The stop has an address of its own
# --------------------------------------------------------------------------


def test_every_stop_is_addressable_by_id(postgres_session, monkeypatch):
    """A check-in names a stop, so a stop must have a name to be checked into.

    Before F46 the timeline returned stops identified only by `position`, and
    position is a number that changes meaning the moment the plan is edited.
    """
    _app, _ctx, _owner, _outsider, _outing, stops = _scene(
        postgres_session, monkeypatch
    )

    assert len(stops) == len(PM_TIMELINE)
    ids = [stop["id"] for stop in stops]
    assert all(ids), "every stop needs an id to be checked into"
    assert len(set(ids)) == len(ids), "stop ids must be distinct"


# --------------------------------------------------------------------------
# 1 -- one person, one check-in per stop, held by the unique index
# --------------------------------------------------------------------------


def test_a_member_can_check_in_to_a_stop(postgres_session, monkeypatch):
    app, _ctx, owner, _outsider, _outing, stops = _scene(postgres_session, monkeypatch)

    response = _check_in(app, owner.id, stops[0]["id"])

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["stop_id"] == stops[0]["id"]
    assert body["person_id"] == str(owner.id)
    assert body["display_name"] == "Minh Anh"


def test_the_same_person_cannot_check_in_twice(postgres_session, monkeypatch):
    """Drop `uq_outing_stop_checkins_person` and this test goes red.

    That is the point of it. The service never asks "have you already checked
    in?" -- it writes and lets the index answer, so two phones pressing the
    button in the same instant cannot both win.
    """
    app, _ctx, owner, _outsider, outing, stops = _scene(postgres_session, monkeypatch)

    first = _check_in(app, owner.id, stops[0]["id"])
    second = _check_in(app, owner.id, stops[0]["id"])

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "already_checked_in"

    # And exactly one row survived, not two with one hidden.
    rows = postgres_session.scalars(
        select(OutingStopCheckin).where(
            OutingStopCheckin.stop_id == uuid.UUID(stops[0]["id"])
        )
    ).all()
    assert len(rows) == 1

    listed = _read_checkins(app, owner.id, outing["id"])
    assert len(listed.json()["checkins"]) == 1


def test_the_index_itself_refuses_a_duplicate_row(postgres_session, monkeypatch):
    """The rule is in the schema, proved without going through the API.

    If this passes while `test_the_same_person_cannot_check_in_twice` fails,
    the service is catching something the database never raised.
    """
    _app, _ctx, owner, _outsider, _outing, stops = _scene(
        postgres_session, monkeypatch
    )
    stop_id = uuid.UUID(stops[0]["id"])

    postgres_session.add(OutingStopCheckin(stop_id=stop_id, person_id=owner.id))
    postgres_session.flush()

    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        with postgres_session.begin_nested():
            postgres_session.add(
                OutingStopCheckin(stop_id=stop_id, person_id=owner.id)
            )
            postgres_session.flush()


def test_one_person_may_check_in_to_each_of_several_stops(
    postgres_session, monkeypatch
):
    """The rule is per stop, not per outing -- a group visits every stop."""
    app, _ctx, owner, _outsider, outing, stops = _scene(postgres_session, monkeypatch)

    for stop in stops[:3]:
        assert _check_in(app, owner.id, stop["id"]).status_code == 201

    listed = _read_checkins(app, owner.id, outing["id"]).json()["checkins"]
    assert len(listed) == 3
    assert {row["stop_id"] for row in listed} == {stop["id"] for stop in stops[:3]}


def test_two_members_may_check_in_to_the_same_stop(postgres_session, monkeypatch):
    """The rule is per person -- the whole group arrives at the same place."""
    app, context, owner, _outsider, outing, stops = _scene(
        postgres_session, monkeypatch
    )
    friend = _person(postgres_session, "Quyên")
    _join(postgres_session, context, friend)

    assert _check_in(app, owner.id, stops[0]["id"]).status_code == 201
    assert _check_in(app, friend.id, stops[0]["id"]).status_code == 201

    listed = _read_checkins(app, owner.id, outing["id"]).json()["checkins"]
    assert {row["display_name"] for row in listed} == {"Minh Anh", "Quyên"}


# --------------------------------------------------------------------------
# 2 -- ACTIVE membership, and nothing weaker
# --------------------------------------------------------------------------


def test_an_outsider_cannot_check_in(postgres_session, monkeypatch):
    app, _ctx, _owner, outsider, _outing, stops = _scene(postgres_session, monkeypatch)

    response = _check_in(app, outsider.id, stops[0]["id"])

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "is_group_member"


def test_an_outsider_cannot_read_who_arrived(postgres_session, monkeypatch):
    """Where the group is, is group data. A self-declared role is not a key."""
    app, _ctx, owner, outsider, outing, stops = _scene(postgres_session, monkeypatch)
    assert _check_in(app, owner.id, stops[0]["id"]).status_code == 201

    response = _read_checkins(app, outsider.id, outing["id"])

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "is_group_member"


def test_an_invited_member_cannot_check_in(postgres_session, monkeypatch):
    """Relax the ACTIVE requirement and this test goes red.

    An INVITED row is what redeeming an invite link produces. If
    `is_group_member` were ever loosened to "has a membership row", whoever
    just opened a link would start recording arrivals into a group they have
    not been accepted into.
    """
    app, context, _owner, _outsider, _outing, stops = _scene(
        postgres_session, monkeypatch
    )
    newcomer = _person(postgres_session, "Người vừa bấm link")
    _join(postgres_session, context, newcomer, state=MembershipState.INVITED)

    response = _check_in(app, newcomer.id, stops[0]["id"])

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "is_group_member"


def test_an_invited_member_cannot_read_who_arrived(postgres_session, monkeypatch):
    app, context, owner, _outsider, outing, stops = _scene(
        postgres_session, monkeypatch
    )
    assert _check_in(app, owner.id, stops[0]["id"]).status_code == 201
    newcomer = _person(postgres_session, "Người vừa bấm link")
    _join(postgres_session, context, newcomer, state=MembershipState.INVITED)

    response = _read_checkins(app, newcomer.id, outing["id"])

    assert response.status_code == 403, response.text


def test_a_departed_member_cannot_check_in(postgres_session, monkeypatch):
    """Somebody who left keeps no access to the trip.

    The state and the timestamp move together -- `memberships` carries a check
    constraint saying `(state = 'left') = (left_at IS NOT NULL)`, so "ACTIVE
    but departed" is not a row this schema can hold in the first place.
    """
    app, context, _owner, _outsider, _outing, stops = _scene(
        postgres_session, monkeypatch
    )
    gone = _person(postgres_session, "Đã rời nhóm")
    _join(
        postgres_session,
        context,
        gone,
        state=MembershipState.LEFT,
        left_at=NOW,
    )

    response = _check_in(app, gone.id, stops[0]["id"])

    assert response.status_code == 403, response.text


def test_a_checkin_from_another_group_never_appears(postgres_session, monkeypatch):
    """Two groups, two outings. Reading one must not show the other."""
    app, _ctx, owner, _outsider, outing, stops = _scene(postgres_session, monkeypatch)
    assert _check_in(app, owner.id, stops[0]["id"]).status_code == 201

    other_owner = _person(postgres_session, "Nhóm khác")
    other_context = _context(postgres_session, other_owner, "Team khác")
    _join(postgres_session, other_context, other_owner)
    other_outing = _make_outing(postgres_session, app, other_owner, other_context)
    other_stops = _with_timeline(app, other_owner, other_outing["id"])
    assert _check_in(app, other_owner.id, other_stops[0]["id"]).status_code == 201

    listed = _read_checkins(app, owner.id, outing["id"]).json()["checkins"]

    assert len(listed) == 1
    assert listed[0]["person_id"] == str(owner.id)


# --------------------------------------------------------------------------
# 3 -- no location, anywhere
# --------------------------------------------------------------------------

# Every spelling a coordinate has ever arrived under. Checked against nested
# keys too, so a location cannot hide one level down.
LOCATION_KEYS = {
    "lat",
    "lng",
    "lon",
    "long",
    "latitude",
    "longitude",
    "accuracy",
    "altitude",
    "coords",
    "coordinates",
    "geo",
    "gps",
    "heading",
    "speed",
}


def _keys_anywhere(value) -> set[str]:
    if isinstance(value, dict):
        found = set(value)
        for nested in value.values():
            found |= _keys_anywhere(nested)
        return found
    if isinstance(value, list):
        found = set()
        for nested in value:
            found |= _keys_anywhere(nested)
        return found
    return set()


def test_no_response_field_carries_a_location(postgres_session, monkeypatch):
    """A check-in says who and when. It never says where the phone was.

    Reading the phone's GPS is F47 and is not built. This test is what makes
    adding `lat` "just for the map" a deliberate act rather than a quiet one.
    """
    app, _ctx, owner, _outsider, outing, stops = _scene(postgres_session, monkeypatch)

    created = _check_in(app, owner.id, stops[0]["id"])
    listed = _read_checkins(app, owner.id, outing["id"])

    for payload in (created.json(), listed.json()):
        leaked = _keys_anywhere(payload) & LOCATION_KEYS
        assert not leaked, f"a location reached the wire: {sorted(leaked)}"


def test_the_table_itself_has_no_location_column(postgres_session):
    """Proved against the migrated schema, not against the model file."""
    columns = set(
        postgres_session.scalars(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'outing_stop_checkins'"
            )
        ).all()
    )

    assert columns == {"id", "stop_id", "person_id", "created_at"}
    assert not columns & LOCATION_KEYS


def test_a_body_offering_coordinates_changes_nothing(postgres_session, monkeypatch):
    """The route takes no body, so a coordinate has nowhere to land."""
    app, _ctx, owner, _outsider, outing, stops = _scene(postgres_session, monkeypatch)

    async def exchange():
        async with _client(app) as client:
            return await client.post(
                f"/outing-stops/{stops[0]['id']}/checkins",
                headers=_headers(owner.id),
                json={"lat": 11.9404, "lng": 108.4383},
            )

    response = anyio.run(exchange)

    assert response.status_code == 201, response.text
    assert not _keys_anywhere(response.json()) & LOCATION_KEYS
    row = postgres_session.scalars(select(OutingStopCheckin)).one()
    assert not set(row.__table__.columns.keys()) & LOCATION_KEYS
    listed = _read_checkins(app, owner.id, outing["id"]).json()
    assert not _keys_anywhere(listed) & LOCATION_KEYS


# --------------------------------------------------------------------------
# 4 -- unknown stops, and what a deleted stop takes with it
# --------------------------------------------------------------------------


def test_an_unknown_stop_is_404_and_echoes_nothing(postgres_session, monkeypatch):
    app, _ctx, owner, _outsider, _outing, _stops = _scene(
        postgres_session, monkeypatch
    )

    unknown = uuid.uuid4()

    response = _check_in(app, owner.id, unknown)

    assert response.status_code == 404, response.text
    assert response.json()["code"] == "stop_not_found"
    # The unknown id is not quoted back. A 404 that echoes its input is a
    # probe oracle, and this route is reachable by anyone with a session.
    assert str(unknown) not in response.text


def test_adding_a_stop_keeps_the_checkins_of_the_stops_that_did_not_change(
    postgres_session, monkeypatch
):
    """bug-223357: appending one stop used to erase everybody's "đã tới".

    Measured through the app: check in at the first stop, then type one more
    stop and save. Before the fix every row in `outing_stops` was deleted and
    re-inserted with a fresh id, so the check-in cascaded away while the five
    stops it belonged to were still on the screen, unchanged.
    """
    app, _ctx, owner, _outsider, outing, stops = _scene(postgres_session, monkeypatch)
    assert _check_in(app, owner.id, stops[0]["id"]).status_code == 201

    after = _put_timeline(
        app,
        owner,
        outing["id"],
        [*PM_TIMELINE, {"at": "23:00", "label": "Về", "place_name": None}],
    )

    postgres_session.expire_all()
    assert [stop["id"] for stop in after[: len(PM_TIMELINE)]] == [
        stop["id"] for stop in stops
    ], "a stop the edit did not touch must keep its id"
    listed = _read_checkins(app, owner.id, outing["id"]).json()["checkins"]
    assert [check["stop_id"] for check in listed] == [stops[0]["id"]]


def test_reordering_the_timeline_carries_each_checkin_with_its_stop(
    postgres_session, monkeypatch
):
    """Moving a stop earlier is not deleting it.

    This is the case that `uq_outing_stops_position` makes awkward: the stop
    keeps its row and changes `position`, so two rows want the same position
    part-way through the save. Reusing rows without staging the positions
    makes this test fail on the unique index, not on the assertion.
    """
    app, _ctx, owner, _outsider, outing, stops = _scene(postgres_session, monkeypatch)
    assert _check_in(app, owner.id, stops[4]["id"]).status_code == 201

    reordered = [PM_TIMELINE[4], *PM_TIMELINE[:4], PM_TIMELINE[5]]
    after = _put_timeline(app, owner, outing["id"], reordered)

    postgres_session.expire_all()
    assert after[0]["id"] == stops[4]["id"]
    assert after[0]["position"] == 0
    listed = _read_checkins(app, owner.id, outing["id"]).json()["checkins"]
    assert [check["stop_id"] for check in listed] == [stops[4]["id"]]


def test_a_stop_dropped_from_the_new_plan_takes_only_its_own_checkins(
    postgres_session, monkeypatch
):
    """Pinning the half of the old behaviour that was right.

    A stop that is no longer in the plan is gone, and `ondelete=CASCADE` takes
    its check-ins with it -- there is no arrival to show at a stop nobody is
    going to. What must not happen is the neighbours dying with it.
    """
    app, _ctx, owner, _outsider, outing, stops = _scene(postgres_session, monkeypatch)
    assert _check_in(app, owner.id, stops[0]["id"]).status_code == 201
    assert _check_in(app, owner.id, stops[1]["id"]).status_code == 201

    _put_timeline(app, owner, outing["id"], PM_TIMELINE[1:])

    postgres_session.expire_all()
    survivors = postgres_session.scalars(select(OutingStopCheckin)).all()
    assert len(survivors) == 1
    listed = _read_checkins(app, owner.id, outing["id"]).json()["checkins"]
    assert [check["stop_id"] for check in listed] == [stops[1]["id"]]


def test_editing_a_stop_drops_the_checkins_of_the_stop_it_replaced(
    postgres_session, monkeypatch
):
    """The limit of the fix, written down so it is not mistaken for a bug.

    The client sends no stop ids, so a stop is recognised by what it says --
    time, label, place. Retyping any of those reads as "that stop is gone, this
    other one is new", and the arrivals recorded against the old wording go
    with it. Preserving them across an edit needs the client to echo the stop
    id it is editing, which is a change to a request body this file does not
    own.
    """
    app, _ctx, owner, _outsider, outing, stops = _scene(postgres_session, monkeypatch)
    assert _check_in(app, owner.id, stops[0]["id"]).status_code == 201

    renamed = [{**PM_TIMELINE[0], "label": "Cà phê sáng"}, *PM_TIMELINE[1:]]
    after = _put_timeline(app, owner, outing["id"], renamed)

    postgres_session.expire_all()
    assert after[0]["id"] != stops[0]["id"]
    assert _read_checkins(app, owner.id, outing["id"]).json()["checkins"] == []
    # The stops nobody retyped are untouched, which is the whole point.
    assert [stop["id"] for stop in after[1:]] == [stop["id"] for stop in stops[1:]]


def test_deleting_one_stop_takes_only_its_own_checkins(
    postgres_session, monkeypatch
):
    app, _ctx, owner, _outsider, _outing, stops = _scene(postgres_session, monkeypatch)
    assert _check_in(app, owner.id, stops[0]["id"]).status_code == 201
    assert _check_in(app, owner.id, stops[1]["id"]).status_code == 201

    doomed = postgres_session.get(OutingStop, uuid.UUID(stops[0]["id"]))
    postgres_session.delete(doomed)
    postgres_session.flush()

    remaining = postgres_session.scalars(select(OutingStopCheckin)).all()
    assert len(remaining) == 1
    assert remaining[0].stop_id == uuid.UUID(stops[1]["id"])
