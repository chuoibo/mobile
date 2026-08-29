"""The group memory wall, proved against real PostgreSQL over real HTTP.

The mockup calls this screen "Tường nhóm riêng tư -- chỉ thành viên nhóm mới
xem". That sentence is a permission boundary, and a boundary is only worth the
test that tries to cross it. So the centre of this file is not "can a member
post a photo": it is what a person standing outside the group receives when
they ask, and what the refusal itself gives away.

Why PostgreSQL and not the fake repository: a feed is a query. `list_memories`
filters by `context_id` and orders by a composite key, and the fake stores
whatever it is handed -- a missing WHERE clause round-trips through a dict
exactly as cleanly as a correct one. Cross-group leakage is invisible to a fake
by construction, which is precisely the failure this file exists to catch.

Uses `flush`, never `commit`: `postgres_session` rolls back per test, and the
schema is shared with row-counting tests in this directory that go red if rows
from here survive.
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
    Person,
)

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

PHOTO = "https://cdn.example/kyniem/da-lat-01.jpg"
CAPTION = "Một chiều chill thật chill ở Đà Lạt"


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
    # Both roles on purpose. A header is a claim, not a proof: the point of
    # these tests is that membership -- not the role string -- is what decides.
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


def _remember(
    session: Session,
    context: Context,
    author: Person,
    *,
    caption: str | None = CAPTION,
    image_url: str = PHOTO,
    created_at=NOW,
) -> Memory:
    memory = Memory(
        id=uuid.uuid4(),
        context_id=context.id,
        author_id=author.id,
        image_url=image_url,
        caption=caption,
        created_at=created_at,
    )
    session.add(memory)
    session.flush()
    return memory


def test_a_member_posts_a_memory_and_reads_it_back(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            posted = await client.post(
                f"/contexts/{context.id}/memories",
                headers=_headers(owner.id),
                json={"image_url": PHOTO, "caption": CAPTION},
            )
            listed = await client.get(
                f"/contexts/{context.id}/memories", headers=_headers(owner.id)
            )
            return posted, listed

    posted, listed = anyio.run(exchange)

    assert posted.status_code == 201, posted.text
    body = posted.json()
    assert body["image_url"] == PHOTO
    assert body["caption"] == CAPTION
    assert body["author_id"] == str(owner.id)
    assert body["context_id"] == str(context.id)

    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert [item["caption"] for item in page["memories"]] == [CAPTION]
    assert page["has_more"] is False
    # Every entry carries its own cursor, so a client never builds one.
    assert page["memories"][0]["cursor"]


def test_a_stranger_can_neither_read_nor_post_group_memories(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The acceptance criterion, at the boundary a real client uses."""
    context, owner, outsider = _group(postgres_session)
    _remember(postgres_session, context, owner)
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            read = await client.get(
                f"/contexts/{context.id}/memories", headers=_headers(outsider.id)
            )
            wrote = await client.post(
                f"/contexts/{context.id}/memories",
                headers=_headers(outsider.id),
                json={"image_url": "https://cdn.example/khong-phai-cua-toi.jpg"},
            )
            return read, wrote

    read, wrote = anyio.run(exchange)

    assert read.status_code == 403, read.text
    assert wrote.status_code == 403, wrote.text
    # A refusal is a place private data leaks by accident: the photo URL, the
    # caption and the poster's name must all be absent from the body.
    assert PHOTO not in read.text
    assert "Đà Lạt" not in read.text
    assert "Minh Anh" not in read.text


def test_a_person_who_left_the_group_stops_seeing_its_memories(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Leaving is recorded rather than deleted, so the row still exists.

    A membership check that asks "is there a row" instead of "is there an open
    row" reads as green everywhere else and hands the whole wall to somebody
    who walked out of the group.
    """
    context, owner, _ = _group(postgres_session)
    former = _person(postgres_session, "Quang Huy")
    _join(
        postgres_session,
        context,
        former,
        state=MembershipState.LEFT,
        left_at=NOW,
    )
    _remember(postgres_session, context, owner)
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(
                f"/contexts/{context.id}/memories", headers=_headers(former.id)
            )

    read = anyio.run(exchange)

    assert read.status_code == 403, read.text
    assert PHOTO not in read.text


def test_a_memory_belonging_to_another_group_never_appears_in_this_feed(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """One person in two groups is the case a missing WHERE clause survives.

    The reader is a legitimate member of both, so no permission check fires.
    Only the query itself separates the two walls.
    """
    context, owner, _ = _group(postgres_session)
    other = _context(postgres_session, owner, "Team Sa Pa")
    _join(postgres_session, other, owner)
    _remember(postgres_session, context, owner, caption="Đà Lạt hôm ấy")
    _remember(
        postgres_session,
        other,
        owner,
        caption="Sa Pa mù sương",
        image_url="https://cdn.example/kyniem/sa-pa-01.jpg",
    )
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(
                f"/contexts/{context.id}/memories", headers=_headers(owner.id)
            )

    read = anyio.run(exchange)

    assert read.status_code == 200, read.text
    assert [item["caption"] for item in read.json()["memories"]] == ["Đà Lạt hôm ấy"]
    assert "Sa Pa" not in read.text


def test_the_caption_is_optional_but_the_photo_is_not(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The mockup labels the caption "nếu muốn"; the photo is the memory."""
    context, owner, _ = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            silent = await client.post(
                f"/contexts/{context.id}/memories",
                headers=_headers(owner.id),
                json={"image_url": PHOTO},
            )
            blank = await client.post(
                f"/contexts/{context.id}/memories",
                headers=_headers(owner.id),
                json={"image_url": "", "caption": CAPTION},
            )
            missing = await client.post(
                f"/contexts/{context.id}/memories",
                headers=_headers(owner.id),
                json={"caption": CAPTION},
            )
            return silent, blank, missing

    silent, blank, missing = anyio.run(exchange)

    assert silent.status_code == 201, silent.text
    assert silent.json()["caption"] is None

    assert blank.status_code == 422, blank.text
    assert missing.status_code == 422, missing.text


def test_the_wall_is_newest_first_and_pages_backwards(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """A wall is read from the top down, and a cursor that needs escaping is a
    cursor that silently truncates in a query string."""
    context, owner, _ = _group(postgres_session)
    for index in range(5):
        _remember(
            postgres_session,
            context,
            owner,
            caption=f"ảnh {index}",
            created_at=NOW.replace(microsecond=index * 1000),
        )
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            first = await client.get(
                f"/contexts/{context.id}/memories",
                headers=_headers(owner.id),
                params={"limit": 2},
            )
            second = await client.get(
                f"/contexts/{context.id}/memories",
                headers=_headers(owner.id),
                params={"limit": 2, "before": first.json()["next_cursor"]},
            )
            forged = await client.get(
                f"/contexts/{context.id}/memories",
                headers=_headers(owner.id),
                params={"before": "khong-phai-cursor"},
            )
            return first, second, forged

    first, second, forged = anyio.run(exchange)

    assert first.status_code == 200, first.text
    assert [item["caption"] for item in first.json()["memories"]] == ["ảnh 4", "ảnh 3"]
    assert first.json()["has_more"] is True

    assert second.status_code == 200, second.text
    assert [item["caption"] for item in second.json()["memories"]] == ["ảnh 2", "ảnh 1"]

    assert forged.status_code == 422, forged.text
