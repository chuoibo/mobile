"""F37 trip reels over real HTTP and real PostgreSQL.

The model backend is fixed so these cases measure the door and its SQL rather
than a model's taste. Everything behind that seam is production wiring:
``SqlAlchemyApiRepository`` reads the Alembic-migrated schema, the application
owns the real reel limiter, and FastAPI serves the real route.

The positive case seeds two controls alongside the trip's real rows: a memory
from another context on the same dates, and a memory from this context outside
the trip dates. If either SQL scope predicate disappears, the model is offered
the control and the exact-id assertion goes red.

Uses ``flush``, never ``commit``: ``postgres_session`` rolls back each test and
the PostgreSQL files share one schema with row-counting tests.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import anyio
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_reeler, get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import (
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    Memory,
    MemoryKind,
    Outing,
    Person,
)

pytestmark = pytest.mark.postgres

VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")


class RecordingReeler:
    """Copy every offered id while recording exactly what the route offered."""

    def __init__(self) -> None:
        self.calls: list[tuple[dict, list[dict]]] = []

    def __call__(self, trip: dict, memories: list[dict]) -> dict:
        self.calls.append((dict(trip), [dict(memory) for memory in memories]))
        return {
            "title": "PostgreSQL reel",
            "picks": [
                {
                    "memory_id": memory["id"],
                    "note": f"Offered row {position}",
                }
                for position, memory in enumerate(memories, start=1)
            ],
        }


@dataclass(frozen=True)
class Scene:
    own_context: Context
    own_member: Person
    own_outing: Outing
    own_memories: tuple[Memory, Memory]
    out_of_window_memory: Memory
    empty_outing: Outing
    foreign_context: Context
    foreign_member: Person
    foreign_outing: Outing
    foreign_memory: Memory


@pytest.fixture
def reeler() -> RecordingReeler:
    return RecordingReeler()


@pytest.fixture
def app(
    postgres_session: Session,
    reeler: RecordingReeler,
    monkeypatch: pytest.MonkeyPatch,
):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    # The test Session is intentionally shared with the synchronous route.
    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    application = create_app()
    application.dependency_overrides[get_repository] = lambda: (
        SqlAlchemyApiRepository(postgres_session)
    )
    application.dependency_overrides[get_reeler] = lambda: reeler
    return application


def _request(app, path: str, *, headers: dict[str, str]) -> httpx.Response:
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(path, headers=headers)

    return anyio.run(send)


def _headers(person: Person, claimed_context: Context) -> dict[str, str]:
    # The context header is deliberately over-claimed. PostgreSQL membership,
    # not this caller-controlled claim, must decide whether the route opens.
    return {
        "X-Actor-ID": str(person.id),
        "X-Actor-Roles": "member,group_admin",
        "X-Actor-Contexts": str(claimed_context.id),
    }


def _reel_path(context: Context, outing_id: uuid.UUID) -> str:
    return f"/contexts/{context.id}/albums/{outing_id}/reel"


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _group(session: Session, name: str) -> tuple[Context, Person]:
    member = _person(session, f"Synthetic member of {name}")
    context = Context(
        id=uuid.uuid4(),
        display_name=name,
        created_by_id=member.id,
    )
    session.add(context)
    session.flush()
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=member.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.MEMBER,
            joined_at=datetime.now(UTC),
        )
    )
    session.flush()
    return context, member


def _outing(
    session: Session,
    context: Context,
    member: Person,
    *,
    title: str,
    starts_on: date,
    ends_on: date,
) -> Outing:
    outing = Outing(
        id=uuid.uuid4(),
        context_id=context.id,
        created_by_id=member.id,
        title=title,
        starts_on=starts_on,
        ends_on=ends_on,
        headcount=3,
        budget_per_person_vnd=500_000,
        created_at=datetime.now(UTC),
    )
    session.add(outing)
    session.flush()
    return outing


def _moment(day: date, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=VIETNAM)


def _memory(
    session: Session,
    context: Context,
    member: Person,
    *,
    caption: str,
    created_at: datetime,
) -> Memory:
    memory_id = uuid.uuid4()
    memory = Memory(
        id=memory_id,
        context_id=context.id,
        author_id=member.id,
        kind=MemoryKind.PHOTO,
        image_url=f"/contexts/{context.id}/photos/{memory_id}",
        caption=caption,
        created_at=created_at,
    )
    session.add(memory)
    session.flush()
    return memory


@pytest.fixture
def scene(postgres_session: Session) -> Scene:
    today = datetime.now(VIETNAM).date()
    trip_start = today - timedelta(days=4)
    trip_end = today - timedelta(days=3)
    empty_start = today - timedelta(days=10)
    empty_end = today - timedelta(days=9)

    own_context, own_member = _group(postgres_session, "F37 synthetic group A")
    own_outing = _outing(
        postgres_session,
        own_context,
        own_member,
        title="F37 own trip",
        starts_on=trip_start,
        ends_on=trip_end,
    )
    own_memories = (
        _memory(
            postgres_session,
            own_context,
            own_member,
            caption="F37 own memory one",
            created_at=_moment(trip_start, 8),
        ),
        _memory(
            postgres_session,
            own_context,
            own_member,
            caption="F37 own memory two",
            created_at=_moment(trip_end, 18),
        ),
    )
    out_of_window_memory = _memory(
        postgres_session,
        own_context,
        own_member,
        caption="F37 same group but outside the trip",
        created_at=_moment(today - timedelta(days=1), 12),
    )
    empty_outing = _outing(
        postgres_session,
        own_context,
        own_member,
        title="F37 empty trip",
        starts_on=empty_start,
        ends_on=empty_end,
    )

    foreign_context, foreign_member = _group(postgres_session, "F37 synthetic group B")
    foreign_outing = _outing(
        postgres_session,
        foreign_context,
        foreign_member,
        title="F37 foreign trip",
        starts_on=trip_start,
        ends_on=trip_end,
    )
    foreign_memory = _memory(
        postgres_session,
        foreign_context,
        foreign_member,
        caption="F37 foreign memory on the same day",
        created_at=_moment(trip_start, 10),
    )

    return Scene(
        own_context=own_context,
        own_member=own_member,
        own_outing=own_outing,
        own_memories=own_memories,
        out_of_window_memory=out_of_window_memory,
        empty_outing=empty_outing,
        foreign_context=foreign_context,
        foreign_member=foreign_member,
        foreign_outing=foreign_outing,
        foreign_memory=foreign_memory,
    )


def test_a_member_gets_only_real_rows_of_their_own_trip(
    app,
    scene: Scene,
    reeler: RecordingReeler,
    postgres_session: Session,
):
    response = _request(
        app,
        _reel_path(scene.own_context, scene.own_outing.id),
        headers=_headers(scene.own_member, scene.own_context),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    expected_ids = {memory.id for memory in scene.own_memories}
    picked_ids = {uuid.UUID(pick["memory_id"]) for pick in body["picks"]}
    assert body["reeled"] is True
    assert body["reason"] == "ok"
    assert body["source"] == "ai"
    assert body["title"] == "PostgreSQL reel"
    assert body["considered_count"] == len(expected_ids) == 2
    assert picked_ids == expected_ids
    assert scene.foreign_memory.id not in picked_ids
    assert scene.out_of_window_memory.id not in picked_ids

    assert len(reeler.calls) == 1
    trip, offered = reeler.calls[0]
    assert trip["title"] == scene.own_outing.title
    assert {uuid.UUID(memory["id"]) for memory in offered} == expected_ids

    stored = postgres_session.execute(
        select(Memory.id, Memory.context_id, Memory.created_at).where(
            Memory.id.in_(picked_ids)
        )
    ).all()
    assert {row.id for row in stored} == expected_ids
    for row in stored:
        assert row.context_id == scene.own_context.id
        wall_date = row.created_at.astimezone(VIETNAM).date()
        assert scene.own_outing.starts_on <= wall_date <= scene.own_outing.ends_on


def test_a_member_of_a_different_group_gets_a_constant_403(
    app,
    scene: Scene,
    reeler: RecordingReeler,
):
    headers = _headers(scene.foreign_member, scene.own_context)
    existing = _request(
        app,
        _reel_path(scene.own_context, scene.own_outing.id),
        headers=headers,
    )
    invented = _request(
        app,
        _reel_path(scene.own_context, uuid.uuid4()),
        headers=headers,
    )

    expected = {"code": "permission_denied", "detail": "is_group_member"}
    assert existing.status_code == invented.status_code == 403
    assert existing.json() == invented.json() == expected
    assert reeler.calls == []


def test_an_outing_from_another_context_is_404_after_real_scope_lookup(
    app,
    scene: Scene,
    reeler: RecordingReeler,
    postgres_session: Session,
):
    stored_context_id = postgres_session.scalar(
        select(Outing.context_id).where(Outing.id == scene.foreign_outing.id)
    )
    assert stored_context_id == scene.foreign_context.id

    response = _request(
        app,
        _reel_path(scene.own_context, scene.foreign_outing.id),
        headers=_headers(scene.own_member, scene.own_context),
    )

    assert response.status_code == 404
    assert response.json() == {
        "code": "album_not_found",
        "detail": "Chuyến đi này không có ở đây.",
    }
    assert reeler.calls == []


def test_a_trip_with_no_memories_has_the_tidy_empty_state(
    app,
    scene: Scene,
    reeler: RecordingReeler,
):
    response = _request(
        app,
        _reel_path(scene.own_context, scene.empty_outing.id),
        headers=_headers(scene.own_member, scene.own_context),
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "context_id": str(scene.own_context.id),
        "outing_id": str(scene.empty_outing.id),
        "reeled": False,
        "reason": "no_memories",
        "source": "none",
        "title": None,
        "picks": [],
        "considered_count": 0,
    }
    assert reeler.calls == []
