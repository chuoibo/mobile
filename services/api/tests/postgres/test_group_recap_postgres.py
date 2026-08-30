"""Tường kỷ niệm (F30/F35): what a finished trip cost, read back from the ledger.

The memory wall does not store anything. It answers "which trips are over,
where did they go, how much did we split" by recomputing from `expense_versions`
and `confirmed_allocations` on the request that asks -- invariant 3 pointed at a
screen whose entire job is to look backwards.

There is no `expenses.outing_id`, so a trip claims the spending that happened on
its days. That is a *rule*, and rules picked out of thin air are exactly what
this file exists to pin down. Four things it is built to catch, none of which a
fake repository can see:

1. **The timezone fold.** `outings.starts_on` is a wall-clock Vietnamese day;
   `expense_versions.occurred_at` is an instant. Folding the instant with
   whatever timezone the session carries puts a 01:00 supper on the previous
   day, and under a UTC server that drops it out of its own trip. CI runs UTC
   and a developer's machine runs +07, so this is the one bug that passes at
   home and fails in the pipeline -- see PR #96.
2. **Corrections must not double the trip.** An edit writes a new version rather
   than overwriting. A sum that forgets to take only the newest version reports
   a corrected 520k dinner as 1.04m, and a wrong total still looks like a total.
3. **`Decimal` escaping as money.** PostgreSQL sums a bigint as `numeric`, which
   psycopg returns as `Decimal` and JSON renders as `520000.0`. Law 1 is integer
   đồng end to end, and only a real driver can prove it.
4. **Another group's trip and another group's money.** The wall is private. A
   sum keyed on dates alone would happily add the neighbours' dinner.

Uses `flush`, never `commit`: `postgres_session` rolls back per test and the
schema is shared with row-counting tests in this directory.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

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
    Outing,
    OutingStop,
    Person,
)

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

# NOW is 2030-08-27T12:00Z, which is 2030-08-27T19:00 in Vietnam. Every trip
# below ends before that day, so every trip below is a memory.
TRIP_STARTS_ON = date(2030, 8, 21)
TRIP_ENDS_ON = date(2030, 8, 23)
DINNER_VND = 520_000

# The trip the group is on right now: started before today, ends after it. The
# server's Vietnamese day is 2030-08-27, so `today` falls strictly inside.
ONGOING_STARTS_ON = date(2030, 8, 26)
ONGOING_ENDS_ON = date(2030, 8, 29)
LUNCH_VND = 340_000


def _app(session: Session, monkeypatch: pytest.MonkeyPatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def _call(app, method: str, path: str, *, headers: dict, json: dict | None = None):
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, path, headers=headers, json=json)

    return anyio.run(run)


def _headers(person: Person, context: Context) -> dict[str, str]:
    # Both roles on purpose. A header is a claim, not a proof: membership is what
    # decides, never the role string a caller typed.
    return {
        "X-Actor-ID": str(person.id),
        "X-Actor-Roles": "member,group_admin,advancer",
        "X-Actor-Contexts": str(context.id),
    }


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _group(session: Session, name: str = "Team Đà Lạt") -> tuple[Context, Person]:
    owner = _person(session, "Minh Anh")
    context = Context(id=uuid.uuid4(), display_name=name, created_by_id=owner.id)
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
    return context, owner


def _outing(
    session: Session,
    context: Context,
    owner: Person,
    *,
    title: str = "Đà Lạt 2030",
    starts_on: date = TRIP_STARTS_ON,
    ends_on: date = TRIP_ENDS_ON,
    stops: tuple[tuple[int, str, str | None], ...] = (),
) -> Outing:
    outing = Outing(
        id=uuid.uuid4(),
        context_id=context.id,
        created_by_id=owner.id,
        title=title,
        starts_on=starts_on,
        ends_on=ends_on,
        headcount=4,
        budget_per_person_vnd=1_500_000,
        created_at=NOW,
    )
    session.add(outing)
    session.flush()
    for position, (minute, label, place) in enumerate(stops):
        session.add(
            OutingStop(
                id=uuid.uuid4(),
                outing_id=outing.id,
                position=position,
                minute_of_day=minute,
                label=label,
                place_name=place,
            )
        )
    session.flush()
    return outing


def _split(
    app,
    context: Context,
    payer: Person,
    others: list[Person],
    *,
    occurred_at: str,
    total: int = DINNER_VND,
    expense_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Split a bill the way the app does it: propose, then confirm.

    Deliberately not hand-written `ExpenseVersion` rows. The point of this file
    is that the recap reads what the product actually writes, and a fixture that
    builds its own ledger proves only that the query agrees with the fixture.
    """
    participants = [str(payer.id)] + [str(person.id) for person in others]
    proposal = {
        "context_id": str(context.id),
        "description": "Bữa tối",
        "recorded_by_id": str(payer.id),
        "paid_by_id": str(payer.id),
        "verification_scope": "totals_only",
        "occurred_at": occurred_at,
        "participants": participants,
        "total_amount_vnd": total,
        "items": [],
        "surcharges": [],
        "discounts": [],
    }
    headers = _headers(payer, context)
    if expense_id is None:
        proposed = _call(app, "POST", "/expenses", headers=headers, json=proposal)
        assert proposed.status_code == 201, proposed.text
        body = proposed.json()
        expense_id = uuid.UUID(body["expense_id"])
        allocations = body["allocation"]["allocations"]
        sent = body["proposal"]
    else:
        preview = _call(app, "POST", "/expenses", headers=headers, json=proposal)
        assert preview.status_code == 201, preview.text
        allocations = preview.json()["allocation"]["allocations"]
        sent = preview.json()["proposal"]

    confirmed = _call(
        app,
        "POST",
        f"/expenses/{expense_id}/confirm",
        headers=headers,
        json={
            "proposal": sent,
            "expected_allocations": allocations,
            "acknowledge_as_advancer": True,
        },
    )
    assert confirmed.status_code == 201, confirmed.text
    return expense_id


def _recap(app, context: Context, person: Person):
    return _call(
        app, "GET", f"/contexts/{context.id}/recap", headers=_headers(person, context)
    )


def test_a_finished_trip_reports_where_it_went_and_what_it_cost(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The whole feature in one case: trip, stops, money, all read back."""

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    friend = _person(postgres_session, "Quang Huy")
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=friend.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
        )
    )
    postgres_session.flush()
    _outing(
        postgres_session,
        context,
        owner,
        stops=((8 * 60, "Cafe", "Lưng Chừng Cafe"), (12 * 60, "Lunch", None)),
    )
    _split(app, context, owner, [friend], occurred_at="2030-08-22T19:00:00+07:00")

    response = _recap(app, context, owner)

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["outings"]) == 1
    trip = body["outings"][0]
    assert trip["title"] == "Đà Lạt 2030"
    assert [stop["label"] for stop in trip["stops"]] == ["Cafe", "Lunch"]
    assert [stop["place_name"] for stop in trip["stops"]] == ["Lưng Chừng Cafe", None]
    assert trip["split_total_vnd"] == DINNER_VND
    assert trip["expense_count"] == 1
    assert body["split_total_vnd"] == DINNER_VND
    # The wire shape, and only the wire shape. These two cannot catch a
    # `Decimal` leaving the driver: `split_total_vnd` is declared `int` on the
    # response model, so pydantic has already coerced it by the time there is a
    # body to read. Law 1 is proved against the repository instead, in
    # `test_every_recap_money_figure_arrives_as_a_python_int` below.
    assert isinstance(trip["split_total_vnd"], int)
    assert isinstance(body["split_total_vnd"], int)


def test_every_recap_money_figure_arrives_as_a_python_int(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Law 1, asserted at the boundary that actually breaks it.

    Item 3 of this module's docstring says only a real driver can prove the
    `Decimal` case. Until this case existed, this file did not prove it. Every
    other Law 1 assertion here reads `split_total_vnd` out of the HTTP body,
    and the response model declares that field `int`, so pydantic coerces
    `Decimal("520000")` to `520000` before any assertion runs. Deleting the
    `int(...)` cast in `SqlAlchemyApiRepository.group_recap` left all sixteen
    cases in this file green; the only thing that went red was a *different*
    feature's test, raising `suggestion_history_not_integer_dong` from the
    domain guard that the recap basis feeds.

    So this reads the repository return value, which nothing has laundered.
    `type(...) is int` and not `isinstance`: the value stays right while the
    type goes wrong -- `Decimal("520000") == 520000` is true, which is exactly
    why every value assertion in this file survives the bug.
    """

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    friend = _person(postgres_session, "Quang Huy")
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=friend.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
        )
    )
    postgres_session.flush()
    _outing(postgres_session, context, owner)
    _split(app, context, owner, [friend], occurred_at="2030-08-22T19:00:00+07:00")

    # NOW is 2030-08-27T12:00Z, i.e. the Vietnamese day the route would compute.
    (trip,) = SqlAlchemyApiRepository(postgres_session).group_recap(
        context.id, today=date(2030, 8, 27)
    )

    assert trip.split_total_vnd == DINNER_VND
    assert type(trip.split_total_vnd) is int, (
        f"split_total_vnd came back as {type(trip.split_total_vnd).__name__}: "
        f"{trip.split_total_vnd!r}"
    )
    assert type(trip.expense_count) is int, (
        f"expense_count came back as {type(trip.expense_count).__name__}: "
        f"{trip.expense_count!r}"
    )


def test_a_supper_after_midnight_stays_on_its_vietnamese_day(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """01:00 on the first night of the trip is still the first day of the trip.

    In UTC that instant is 18:00 the day *before* the trip starts. Fold the
    timestamp with the session timezone instead of naming Vietnam's, and this
    supper falls out of the trip that ate it -- on CI only, because a developer
    machine at +07 folds it back to the right day and stays green.
    """

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    friend = _person(postgres_session, "Quang Huy")
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=friend.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
        )
    )
    postgres_session.flush()
    _outing(postgres_session, context, owner, starts_on=TRIP_STARTS_ON)
    # 2030-08-21T01:00+07 is 2030-08-20T18:00Z -- the day before the trip starts.
    _split(app, context, owner, [friend], occurred_at="2030-08-21T01:00:00+07:00")

    trip = _recap(app, context, owner).json()["outings"][0]

    assert trip["split_total_vnd"] == DINNER_VND
    assert trip["expense_count"] == 1


def test_spending_after_everyone_went_home_is_not_claimed_by_the_trip(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The date rule cuts both ways, and the screen says so out loud."""

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    friend = _person(postgres_session, "Quang Huy")
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=friend.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
        )
    )
    postgres_session.flush()
    _outing(postgres_session, context, owner)
    _split(app, context, owner, [friend], occurred_at="2030-08-25T19:00:00+07:00")

    body = _recap(app, context, owner).json()

    assert body["outings"][0]["split_total_vnd"] == 0
    assert body["outings"][0]["expense_count"] == 0
    assert body["split_total_vnd"] == 0


def test_correcting_a_bill_does_not_double_the_trip_total(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """An edit writes version 2. Only version 2 is the trip's money."""

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    friend = _person(postgres_session, "Quang Huy")
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=friend.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
        )
    )
    postgres_session.flush()
    _outing(postgres_session, context, owner)
    expense_id = _split(
        app, context, owner, [friend], occurred_at="2030-08-22T19:00:00+07:00"
    )
    _split(
        app,
        context,
        owner,
        [friend],
        occurred_at="2030-08-22T19:00:00+07:00",
        total=600_000,
        expense_id=expense_id,
    )

    trip = _recap(app, context, owner).json()["outings"][0]

    assert trip["split_total_vnd"] == 600_000
    assert trip["expense_count"] == 1


def test_a_trip_the_group_is_still_on_reports_what_it_has_cost_so_far(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """rd-be-15. Budget awareness is worth something only while money is moving.

    `group_recap` used to select `ends_on < today` and nothing else, so a trip
    in progress was absent from every answer this route gave. The screen that
    warns about overspending could therefore only warn after everyone had gone
    home -- the one moment the warning cannot change anything.

    The figure is read the same way a finished trip's is: summed from
    `confirmed_allocations` on the request that asks. No new column, no running
    total kept on `outings`. Invariant 3 does not get an exception for being
    early.
    """

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    _outing(
        postgres_session,
        context,
        owner,
        title="Đang ở Đà Lạt",
        starts_on=ONGOING_STARTS_ON,
        ends_on=ONGOING_ENDS_ON,
    )
    _split(
        app,
        context,
        owner,
        [],
        occurred_at="2030-08-26T19:00:00+07:00",
        total=LUNCH_VND,
    )

    body = _recap(app, context, owner).json()

    assert [trip["title"] for trip in body["in_progress"]] == ["Đang ở Đà Lạt"]
    trip = body["in_progress"][0]
    assert trip["split_total_vnd"] == LUNCH_VND
    assert trip["expense_count"] == 1
    # Law 1 end to end. PostgreSQL sums a bigint as `numeric`, psycopg hands
    # that back as `Decimal`, and a Decimal that escapes reaches JSON as
    # `340000.0`. Only a real driver can catch this, which is why the case
    # lives here and not against the fake repository.
    assert isinstance(trip["split_total_vnd"], int)


def test_a_finished_trip_reads_exactly_as_it_did_before_in_progress_existed(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The control. Without it, "fixed the live trip" and "broke the memory
    wall" are the same shade of green.

    `outings` stays what it has always been -- trips that are over -- and the
    top-level `split_total_vnd` stays the sum of exactly those. A trip the group
    is still on must not sneak into either, or the memory wall starts showing a
    trip that has not happened yet and its total stops adding up to the figures
    printed under it.
    """

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    _outing(postgres_session, context, owner, title="Đã về")
    _outing(
        postgres_session,
        context,
        owner,
        title="Đang đi",
        starts_on=ONGOING_STARTS_ON,
        ends_on=ONGOING_ENDS_ON,
    )
    _split(app, context, owner, [], occurred_at="2030-08-22T19:00:00+07:00")
    _split(
        app,
        context,
        owner,
        [],
        occurred_at="2030-08-26T19:00:00+07:00",
        total=LUNCH_VND,
    )

    body = _recap(app, context, owner).json()

    assert [trip["title"] for trip in body["outings"]] == ["Đã về"]
    assert body["outings"][0]["split_total_vnd"] == DINNER_VND
    # The memory wall's own total: finished trips only, still adding up to the
    # rows printed beneath it. The live trip's lunch is not part of it.
    assert body["split_total_vnd"] == DINNER_VND
    assert [trip["title"] for trip in body["in_progress"]] == ["Đang đi"]
    assert body["in_progress"][0]["split_total_vnd"] == LUNCH_VND


def test_the_last_day_of_a_trip_still_counts_as_being_on_it(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The boundary the old filter got wrong, and the cheapest one to get wrong
    again.

    `ends_on < today` put a trip ending *today* on the memory wall while the
    group was still at the table. Today is the last day, not the first day
    afterwards: it belongs to the trip in progress.
    """

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    _outing(
        postgres_session,
        context,
        owner,
        title="Về tối nay",
        starts_on=date(2030, 8, 25),
        ends_on=date(2030, 8, 27),
    )

    body = _recap(app, context, owner).json()

    assert [trip["title"] for trip in body["in_progress"]] == ["Về tối nay"]
    assert body["outings"] == []


def test_a_dinner_before_the_live_trip_began_is_not_charged_to_it(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """A trip claims the spending on its own days, in progress or not.

    The live trip inherits the date rule rather than a looser one. Summing
    everything up to today would hand the group a warning built from a dinner
    they ate the week before, and a wrong number that arrives early is worse
    than a right one that arrives late.
    """

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    _outing(
        postgres_session,
        context,
        owner,
        title="Đang đi",
        starts_on=ONGOING_STARTS_ON,
        ends_on=ONGOING_ENDS_ON,
    )
    # Two days before this trip started, and on no trip at all.
    _split(app, context, owner, [], occurred_at="2030-08-24T19:00:00+07:00")

    body = _recap(app, context, owner).json()

    trip = body["in_progress"][0]
    assert trip["split_total_vnd"] == 0
    assert trip["expense_count"] == 0


@pytest.mark.parametrize(
    ("state", "left_at", "joined_at"),
    [
        (MembershipState.LEFT, NOW, NOW),
        (MembershipState.INVITED, None, None),
    ],
)
def test_only_an_active_member_sees_what_the_live_trip_has_cost(
    postgres_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    state: MembershipState,
    left_at,
    joined_at,
):
    """The new payload is behind the same gate as the old one, proven and not
    assumed.

    A field added to a response is a field that has to be refused too. Somebody
    who left and somebody who never accepted both hold a `memberships` row, so
    neither is refused by "no row exists" -- what refuses them is
    `state = 'active'`, and this is the case that goes red if the live trip's
    money is ever read on a looser check than the memory wall's.
    """

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    _outing(
        postgres_session,
        context,
        owner,
        title="Đang đi",
        starts_on=ONGOING_STARTS_ON,
        ends_on=ONGOING_ENDS_ON,
    )
    _split(
        app,
        context,
        owner,
        [],
        occurred_at="2030-08-26T19:00:00+07:00",
        total=LUNCH_VND,
    )
    stranger = _person(postgres_session, "Không còn quyền")
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=stranger.id,
            state=state,
            role=MembershipRole.MEMBER,
            joined_at=joined_at,
            left_at=left_at,
            invited_by_id=owner.id if state is MembershipState.INVITED else None,
        )
    )
    postgres_session.flush()

    response = _recap(app, context, stranger)

    assert response.status_code == 403, response.text
    assert "Đang đi" not in response.text
    assert str(LUNCH_VND) not in response.text


def test_a_trip_still_ahead_is_not_a_memory_yet(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The wall is for what happened, not for what is planned."""

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    _outing(
        postgres_session,
        context,
        owner,
        title="Sắp đi",
        starts_on=date(2030, 9, 10),
        ends_on=date(2030, 9, 12),
    )
    _outing(postgres_session, context, owner, title="Đã đi")

    body = _recap(app, context, owner).json()

    assert [trip["title"] for trip in body["outings"]] == ["Đã đi"]
    # Nor is it under way. "In progress" has to mean started-and-not-finished;
    # a filter that decayed into "not finished" would collect the whole
    # calendar and warn the group about a budget they have not opened yet.
    assert body["in_progress"] == []


def test_another_groups_dinner_never_lands_on_this_wall(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Same dates, different group. A sum keyed on dates alone adds both."""

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    other_context, other_owner = _group(postgres_session, name="Hội khác")
    other_friend = _person(postgres_session, "Người lạ")
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=other_context.id,
            person_id=other_friend.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
        )
    )
    postgres_session.flush()
    _outing(postgres_session, context, owner)
    _split(
        app,
        other_context,
        other_owner,
        [other_friend],
        occurred_at="2030-08-22T19:00:00+07:00",
    )

    trip = _recap(app, context, owner).json()["outings"][0]

    assert trip["split_total_vnd"] == 0
    assert trip["expense_count"] == 0


def test_photos_posted_during_the_trip_are_counted_on_it(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Memories have no outing column either, so they follow the same day rule."""

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    _outing(postgres_session, context, owner)
    for day, hour in ((22, 20), (23, 9), (26, 20)):
        postgres_session.add(
            Memory(
                id=uuid.uuid4(),
                context_id=context.id,
                author_id=owner.id,
                image_url=f"https://example.invalid/{day}.jpg",
                caption=None,
                created_at=datetime.fromisoformat(
                    f"2030-08-{day:02d}T{hour:02d}:00:00+07:00"
                ),
            )
        )
    postgres_session.flush()

    trip = _recap(app, context, owner).json()["outings"][0]

    # Two inside the trip's days, one taken three days after everyone got home.
    assert trip["memory_count"] == 2


def test_a_non_member_cannot_read_the_wall(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Private to the group, and the role string in the header does not decide."""

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    _outing(postgres_session, context, owner)
    outsider = _person(postgres_session, "Người lạ")

    response = _recap(app, context, outsider)

    assert response.status_code == 403, response.text
    body = response.text
    # A refusal must not leak what it is refusing access to.
    assert "Đà Lạt" not in body


def test_a_member_who_left_can_no_longer_read_the_wall(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Leaving takes the history with it, not just the next trip.

    The stranger case above cannot catch this. A stranger has no `memberships`
    row at all, so every clause in `is_member` refuses them and none of them is
    load-bearing. Somebody who left has a row, and only the row's own columns
    stand between them and the group's whole travel and spending history.

    `state` and `left_at` move together here -- `memberships` carries a check
    constraint saying `(state = 'left') = (left_at IS NOT NULL)`, so a departed
    row that still looks open is not a row this schema can hold. Which means a
    departed row fails *both* clauses of `is_member` at once, and this case
    survives dropping either one on its own. Measured, not assumed: it stays
    green under either single mutation and goes red only when both clauses go,
    i.e. when `is_member` decays into "a row exists". That is the refactor it
    is here to catch. The invited case below is the one that pins
    `state = 'active'` by itself.
    """

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    _outing(postgres_session, context, owner)
    _split(app, context, owner, [], occurred_at="2030-08-22T19:00:00+07:00")
    gone = _person(postgres_session, "Đã rời nhóm")
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=gone.id,
            state=MembershipState.LEFT,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
            left_at=NOW,
        )
    )
    postgres_session.flush()

    response = _recap(app, context, gone)

    assert response.status_code == 403, response.text
    body = response.text
    # Not just "no trips": the refusal must not name the trip, and must not
    # carry the total the group split on it.
    assert "Đà Lạt" not in body
    assert str(DINNER_VND) not in body


def test_an_invited_member_cannot_read_the_wall_yet(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Being added to a group is not the same as being in it.

    `INVITED` exists because membership is something that happens to you, and a
    boundary somebody was placed inside without agreeing is not one. The row is
    open -- `left_at` is NULL, as the check constraint requires for any state
    that is not `left` -- so `state = 'active'` is the only clause refusing this
    read. Drop it from `is_member` and this case is the one that goes red.
    """

    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    _outing(postgres_session, context, owner)
    _split(app, context, owner, [], occurred_at="2030-08-22T19:00:00+07:00")
    pending = _person(postgres_session, "Chưa nhận lời")
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=pending.id,
            state=MembershipState.INVITED,
            role=MembershipRole.MEMBER,
            invited_by_id=owner.id,
            joined_at=None,
        )
    )
    postgres_session.flush()

    response = _recap(app, context, pending)

    assert response.status_code == 403, response.text
    body = response.text
    assert "Đà Lạt" not in body
    assert str(DINNER_VND) not in body
