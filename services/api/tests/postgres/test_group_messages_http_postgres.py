"""The message routes reached over real HTTP, against real PostgreSQL.

The service-level tests in `test_group_messages_postgres.py` prove the rules.
They do not prove a client can reach them. Those are different failures: this
repo has already shipped a route whose `actor` argument was accepted and never
read, and a pair of buttons that were dead before they 404ed. A router that is
never registered, a query parameter that never binds, a response model that
drops a field -- each of those leaves every service test green.

So this file asserts the boundary an app actually touches: status codes, the
JSON shape, and the cursor surviving a round trip through a query string.
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
    Message,
    MessageKind,
    Person,
)

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres


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
    return {"X-Actor-ID": str(person_id), "X-Actor-Roles": "member,group_admin"}


def _group(session: Session) -> tuple[Context, Person, Person]:
    owner = Person(id=uuid.uuid4(), display_name="Nam")
    outsider = Person(id=uuid.uuid4(), display_name="Người lạ")
    session.add_all([owner, outsider])
    session.flush()
    context = Context(id=uuid.uuid4(), display_name="Nhóm ăn tối", created_by_id=owner.id)
    session.add(context)
    session.flush()
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=owner.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.ADMIN,
            joined_at=NOW,
        )
    )
    session.flush()
    return context, owner, outsider


def test_a_member_posts_and_reads_messages_over_http(
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
                f"/contexts/{context.id}/messages",
                headers=_headers(owner.id),
                json={"kind": "text", "body": "7h quán cũ nhé"},
            )
            listed = await client.get(
                f"/contexts/{context.id}/messages",
                headers=_headers(owner.id),
            )
            return posted, listed

    posted, listed = anyio.run(exchange)

    assert posted.status_code == 201, posted.text
    assert posted.json()["body"] == "7h quán cũ nhé"
    assert posted.json()["author_id"] == str(owner.id)

    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert [message["body"] for message in page["messages"]] == ["7h quán cũ nhé"]
    assert page["has_more"] is False
    # Every message carries its own cursor, so a client never builds one.
    assert page["messages"][0]["cursor"]


def test_the_route_refuses_a_stranger_rather_than_answering_them(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The acceptance criterion, at the boundary a real client uses."""
    context, owner, outsider = _group(postgres_session)
    postgres_session.add(
        Message(
            id=uuid.uuid4(),
            context_id=context.id,
            author_id=owner.id,
            kind=MessageKind.TEXT,
            body="Quán cũ 7h nhé",
            created_at=NOW,
        )
    )
    postgres_session.flush()
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            read = await client.get(
                f"/contexts/{context.id}/messages", headers=_headers(outsider.id)
            )
            wrote = await client.post(
                f"/contexts/{context.id}/messages",
                headers=_headers(outsider.id),
                json={"kind": "text", "body": "cho tôi vào với"},
            )
            return read, wrote

    read, wrote = anyio.run(exchange)

    assert read.status_code == 403, read.text
    assert wrote.status_code == 403, wrote.text
    # The body of a refusal is a place a conversation leaks by accident.
    assert "Quán cũ" not in read.text
    assert "Nam" not in read.text


def test_the_cursor_survives_a_round_trip_through_the_query_string(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """A cursor that needs escaping is a cursor that silently truncates. This
    is why the codec refuses `+`, `/` and `=`."""
    context, owner, _ = _group(postgres_session)
    for index in range(5):
        postgres_session.add(
            Message(
                id=uuid.uuid4(),
                context_id=context.id,
                author_id=owner.id,
                kind=MessageKind.TEXT,
                body=f"tin {index}",
                created_at=NOW.replace(microsecond=index * 1000),
            )
        )
    postgres_session.flush()
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            first = await client.get(
                f"/contexts/{context.id}/messages",
                headers=_headers(owner.id),
                params={"limit": 2},
            )
            second = await client.get(
                f"/contexts/{context.id}/messages",
                headers=_headers(owner.id),
                params={"limit": 2, "before": first.json()["next_cursor"]},
            )
            forged = await client.get(
                f"/contexts/{context.id}/messages",
                headers=_headers(owner.id),
                params={"before": "khong-phai-cursor"},
            )
            return first, second, forged

    first, second, forged = anyio.run(exchange)

    assert first.status_code == 200, first.text
    assert [m["body"] for m in first.json()["messages"]] == ["tin 4", "tin 3"]
    assert first.json()["has_more"] is True

    assert second.status_code == 200, second.text
    assert [m["body"] for m in second.json()["messages"]] == ["tin 2", "tin 1"]

    assert forged.status_code == 422, forged.text


def test_promoting_a_member_works_over_http(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    context, owner, outsider = _group(postgres_session)
    friend = Person(id=uuid.uuid4(), display_name="Hà")
    postgres_session.add(friend)
    postgres_session.flush()
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
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            promoted = await client.put(
                f"/contexts/{context.id}/members/{friend.id}/role",
                headers=_headers(owner.id),
                json={"role": "admin"},
            )
            refused = await client.put(
                f"/contexts/{context.id}/members/{friend.id}/role",
                headers=_headers(outsider.id),
                json={"role": "member"},
            )
            return promoted, refused

    promoted, refused = anyio.run(exchange)

    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["role"] == "admin"
    # A stranger asking about somebody else's group is refused, not told
    # whether that membership exists.
    assert refused.status_code == 403, refused.text
