"""The guard nobody had: a group's feed must never answer with another group's messages.

`test_group_messages_http_postgres.py` proves a stranger is refused. It does not
prove that a *legitimate* member of group B, asking group B's own endpoint, can
never be handed group A's conversation. Those are different failures, and the
second one survived a full review: deleting the `context_id` filter from the
cursor branches of `SqlAlchemyApiRepository.list_messages` leaves all 24 message
cases green, because every one of them queries a database holding exactly one
group.

    statement = select(Message)
    if before is None and after is None:          # filter only when no cursor
        statement = statement.where(Message.context_id == context_id)

That mutation is a complete cross-group leak, and it needs two groups plus a
cursor to be seen at all. So these cases build both.

THE TRAP, written down so the next person does not fall in it: `before` and
`after` are STRICT inequalities over `(created_at, id)`. A forged cursor aimed
exactly at the victim's message therefore excludes that message from its own
window in both directions -- the case would pass even with the filter deleted,
which is a test that can never go red. The cursors below BRACKET the victim
instead: a future mark for `before`, a past mark for `after`. Both windows
contain the secret, so only the `context_id` filter keeps it out.

Rows here are flushed, never committed; the session fixture rolls back, so the
shared schema keeps the row counts other files assert on.
"""

from __future__ import annotations

import base64
import uuid
from datetime import timedelta

import anyio
import httpx
import pytest
from sqlalchemy.orm import Session

from app.api.cursors import encode_cursor
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

SECRET = "Bí mật nhóm A: 8h tối bất ngờ sinh nhật Hà"
NEIGHBOURLY = "Nhóm B: mai đi cà phê nhé"

# A cursor that sorts after every row in this file, and one that sorts before
# every row. Together they bracket the victim's message from both sides.
FUTURE_MARK = (NOW + timedelta(days=1), uuid.UUID(int=(1 << 128) - 1))
PAST_MARK = (NOW - timedelta(days=1), uuid.UUID(int=0))


def _http(session: Session, monkeypatch: pytest.MonkeyPatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def _headers(person_id: uuid.UUID, *, claims: list[uuid.UUID] | None = None):
    headers = {"X-Actor-ID": str(person_id), "X-Actor-Roles": "member,group_admin"}
    if claims is not None:
        # The gateway is supposed to overwrite this. Pretend it did not.
        headers["X-Actor-Contexts"] = ",".join(str(value) for value in claims)
    return headers


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _context(session: Session, name: str, owner: Person) -> Context:
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
) -> None:
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=person.id,
            state=state,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
            left_at=left_at,
        )
    )
    session.flush()


def _say(session: Session, context: Context, author: Person, body: str, when) -> Message:
    message = Message(
        id=uuid.uuid4(),
        context_id=context.id,
        author_id=author.id,
        kind=MessageKind.TEXT,
        body=body,
        created_at=when,
    )
    session.add(message)
    session.flush()
    return message


def _two_groups(session: Session):
    """Group A holds a secret. The attacker is a real, active member of group B."""
    victim = _person(session, "Nạn nhân")
    attacker = _person(session, "Kẻ tấn công")

    group_a = _context(session, "Nhóm A", victim)
    _join(session, group_a, victim)
    # Newest row in the database, so a leak surfaces at the top of page one.
    secret = _say(session, group_a, victim, SECRET, NOW + timedelta(seconds=10))

    group_b = _context(session, "Nhóm B", attacker)
    _join(session, group_b, attacker)
    _say(session, group_b, attacker, NEIGHBOURLY, NOW)

    return group_a, group_b, victim, attacker, secret


@pytest.mark.parametrize("direction", ["before", "after"])
def test_a_cursor_never_carries_another_groups_messages_into_this_feed(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, direction: str
):
    """A member of B, holding a forged cursor, asks B's endpoint and gets only B.

    The cursor brackets group A's secret rather than pointing at it, so the
    window genuinely contains that row and only the `context_id` filter can
    keep it out.
    """
    group_a, group_b, _, attacker, secret = _two_groups(postgres_session)
    mark = FUTURE_MARK if direction == "before" else PAST_MARK
    forged = encode_cursor(*mark)
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(
                f"/contexts/{group_b.id}/messages",
                # Claim membership of the victim's group in the header too, to
                # check the route trusts the membership row and not the caller.
                headers=_headers(attacker.id, claims=[group_a.id, group_b.id]),
                params={direction: forged, "limit": 50},
            )

    response = anyio.run(exchange)

    assert response.status_code == 200, response.text
    page = response.json()
    bodies = [message["body"] for message in page["messages"]]

    assert SECRET not in response.text, (
        f"CROSS-GROUP LEAK via `{direction}` cursor: group A's private message "
        f"({secret.id}, context {group_a.id}) was served on group B's page "
        f"(context {group_b.id}) to {attacker.id}, who is a member of B only. "
        f"Page returned: {bodies}"
    )
    assert bodies == [NEIGHBOURLY], (
        f"Group B's feed answered with rows that are not group B's: {bodies}"
    )
    # Belt and braces: the ids must all be B's, even if wording ever changes.
    assert {message["context_id"] for message in page["messages"]} == {str(group_b.id)}


def test_someone_who_left_the_group_can_no_longer_read_its_feed(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Leaving is a permission boundary, not a UI state.

    A `left` membership row still exists, so a query that only checks "is there
    a row" would let this person keep reading.
    """
    _, group_b, _, attacker, _ = _two_groups(postgres_session)
    departed = _person(postgres_session, "Người đã rời")
    _join(
        postgres_session,
        group_b,
        departed,
        state=MembershipState.LEFT,
        left_at=NOW + timedelta(days=1),
    )
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            gone = await client.get(
                f"/contexts/{group_b.id}/messages",
                headers=_headers(departed.id, claims=[group_b.id]),
            )
            still_here = await client.get(
                f"/contexts/{group_b.id}/messages",
                headers=_headers(attacker.id),
            )
            return gone, still_here

    gone, still_here = anyio.run(exchange)

    assert gone.status_code == 403, gone.text
    assert NEIGHBOURLY not in gone.text
    # The refusal must not be a blanket outage: an active member still reads.
    assert still_here.status_code == 200, still_here.text
    assert [m["body"] for m in still_here.json()["messages"]] == [NEIGHBOURLY]


def _raw_cursor(payload: str) -> str:
    """Wrap arbitrary bytes the way `encode_cursor` does, without its validation."""

    return base64.urlsafe_b64encode(payload.encode()).decode("ascii").rstrip("=")


@pytest.mark.parametrize(
    ("raw", "why"),
    [
        ("khong-phai-base64!!", "not valid base64"),
        (_raw_cursor("khong-co-dau-gach-dung"), "valid base64, no `|` separator"),
        (
            _raw_cursor(f"9999-12-31T23:59:59.999999+23:59|{uuid.UUID(int=0)}"),
            "year 9999 at offset +23:59",
        ),
        (
            _raw_cursor(f"0001-01-01T00:00:00-23:59|{uuid.UUID(int=0)}"),
            "year 1 at offset -23:59",
        ),
    ],
)
def test_a_poisoned_cursor_is_refused_or_ignored_but_never_crashes(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, raw: str, why: str
):
    """A 500 here hands an attacker a probe and the operator a page of stack.

    Both extremes are real: `datetime.fromisoformat` accepts years 1 and 9999,
    and an offset can push either past what PostgreSQL will bind.
    """
    _, group_b, _, attacker, _ = _two_groups(postgres_session)
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(
                f"/contexts/{group_b.id}/messages",
                headers=_headers(attacker.id),
                params={"before": raw},
            )

    response = anyio.run(exchange)

    assert response.status_code in (200, 422), (
        f"poisoned cursor ({why}) returned {response.status_code}: {response.text}"
    )
    # Whatever the verdict, the neighbouring group stays out of the answer.
    assert SECRET not in response.text
