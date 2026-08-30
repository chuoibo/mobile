"""F38 over real HTTP against real PostgreSQL: the widget and the roster.

`tests/api/test_widget_leak.py` proves the same rules against a fake whose
`is_member` is a `set` lookup. That fake cannot be wrong about membership in
any of the ways the database can: it has no `invited` state, no `left_at`, no
`Membership.state` column to forget. So the interesting refusals -- the person
holding a live-looking membership row that is not active -- can only be proved
here, against the schema Alembic actually migrates.

Two things this file adds that the fake layer cannot:

1. **`invited` and `left` are refused.** Both have a real `Membership` row with
   the group in it. An `is_member` narrowed to "a row exists" answers yes to
   both, and the fake would never notice because it has no rows.
2. **The route is registered.** A service-level test passes with the router
   never included in the app; these go through `create_app()` and httpx.

Every negative assertion counts records. `widget_records()` returns the photo
payloads in the body, so a refusal that answered 403 *with* a photograph fails
on the number. Status-only assertions were how a `filter` written as a `map`
shipped once already (`test_posts_audience.py` header).
"""

from __future__ import annotations

import uuid
from datetime import timedelta

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

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

#: A relative url of the shape `POST /contexts/{id}/photos` mints. The bytes it
#: names were stripped of EXIF on that route; nothing in F38 re-reads an image.
PHOTO_URL = "/contexts/{context_id}/photos/7f0a1b2c-3d4e-4f5a-8b6c-7d8e9f0a1b2c"
CAPTION = "Lẩu tối thứ bảy"
GROUP_NAME = "Nhóm Lẩu Thứ Bảy"


def _http(session: Session, monkeypatch: pytest.MonkeyPatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def _headers(person_id: uuid.UUID, context_id: uuid.UUID) -> dict[str, str]:
    """Generous on purpose, and lying on purpose.

    Every role the product grants, plus `X-Actor-Contexts` naming the very
    group being asked about -- which for the outsiders below is a claim the
    caller has no right to make. If the widget ever opens to one of them it
    must not be because the probe under-credentialled them, and if it opens to
    a stranger, `X-Actor-Contexts` is the first place to look.
    """

    return {
        "X-Actor-ID": str(person_id),
        "X-Actor-Roles": "member,group_admin,batch_owner,advancer,recipient",
        "X-Actor-Contexts": str(context_id),
    }


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _context(session: Session, owner: Person, name: str = GROUP_NAME) -> Context:
    context = Context(id=uuid.uuid4(), display_name=name, created_by_id=owner.id)
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
    return context


def _membership(
    session: Session,
    context: Context,
    person: Person,
    state: MembershipState,
    *,
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


def _photo(
    session: Session,
    context: Context,
    author: Person,
    *,
    caption: str = CAPTION,
    at=NOW,
    suffix: str = "",
) -> Memory:
    memory = Memory(
        id=uuid.uuid4(),
        context_id=context.id,
        author_id=author.id,
        kind=MemoryKind.PHOTO,
        image_url=PHOTO_URL.format(context_id=context.id) + suffix,
        caption=caption,
        created_at=at,
    )
    session.add(memory)
    session.flush()
    return memory


def _checkin(session: Session, context: Context, author: Person, *, at) -> Memory:
    memory = Memory(
        id=uuid.uuid4(),
        context_id=context.id,
        author_id=author.id,
        kind=MemoryKind.CHECKIN,
        place_id="quan-lau-1",
        place_name="Quán lẩu",
        lat=10.78,
        lng=106.69,
        created_at=at,
    )
    session.add(memory)
    session.flush()
    return memory


def _get_widget(app, context_id: uuid.UUID, actor_id: uuid.UUID):
    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(
                f"/contexts/{context_id}/widget",
                headers=_headers(actor_id, context_id),
            )

    return anyio.run(exchange)


def widget_records(response) -> list:
    """The photo payloads this body contains. Zero or one. Never a bool."""

    try:
        body = response.json()
    except Exception:
        return []
    if not isinstance(body, dict):
        return []
    photo = body.get("photo")
    return [photo] if isinstance(photo, dict) else []


# ---------------------------------------------------------------------------
# The positive direction, asserted before any refusal is believed
# ---------------------------------------------------------------------------


def test_a_member_sees_the_newest_photograph_with_a_name_and_a_moment(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    owner = _person(postgres_session, "Nam")
    reader = _person(postgres_session, "Hà")
    context = _context(postgres_session, owner)
    _membership(postgres_session, context, reader, MembershipState.ACTIVE)
    memory = _photo(postgres_session, context, owner)

    response = _get_widget(_http(postgres_session, monkeypatch), context.id, reader.id)

    assert response.status_code == 200, response.text
    records = widget_records(response)
    assert len(records) == 1
    photo = records[0]
    assert photo["memory_id"] == str(memory.id)
    assert photo["image_url"] == memory.image_url
    assert photo["caption"] == CAPTION
    assert photo["author_id"] == str(owner.id)
    assert photo["author_name"] == "Nam"
    assert photo["created_at"].startswith(NOW.date().isoformat())


def test_the_widget_answers_with_the_newest_of_three(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    owner = _person(postgres_session, "Nam")
    context = _context(postgres_session, owner)
    _photo(postgres_session, context, owner, caption="Cũ nhất", at=NOW, suffix="-a")
    _photo(
        postgres_session,
        context,
        owner,
        caption="Giữa",
        at=NOW + timedelta(hours=1),
        suffix="-b",
    )
    newest = _photo(
        postgres_session,
        context,
        owner,
        caption="Mới nhất",
        at=NOW + timedelta(hours=2),
        suffix="-c",
    )

    records = widget_records(
        _get_widget(_http(postgres_session, monkeypatch), context.id, owner.id)
    )

    assert len(records) == 1
    assert records[0]["memory_id"] == str(newest.id)
    assert records[0]["caption"] == "Mới nhất"


def test_a_newer_checkin_does_not_blank_the_widget(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """F46 shares `memories`. A check-in has no image and is not the answer."""

    owner = _person(postgres_session, "Nam")
    context = _context(postgres_session, owner)
    photo = _photo(postgres_session, context, owner)
    _checkin(postgres_session, context, owner, at=NOW + timedelta(hours=3))

    records = widget_records(
        _get_widget(_http(postgres_session, monkeypatch), context.id, owner.id)
    )

    assert len(records) == 1
    assert records[0]["memory_id"] == str(photo.id)


def test_the_author_keeps_their_name_after_they_leave(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """A memory belongs to the group, so the name comes from `people`.

    Reading the name off the roster instead would blank the caption line the
    day somebody left, and `models.Memory` says in its own docstring that the
    group -- not one person's continuing membership -- owns the history.
    """

    owner = _person(postgres_session, "Nam")
    leaver = _person(postgres_session, "Người đã rời")
    context = _context(postgres_session, owner)
    _membership(
        postgres_session,
        context,
        leaver,
        MembershipState.LEFT,
        left_at=NOW + timedelta(days=1),
    )
    _photo(postgres_session, context, leaver)

    records = widget_records(
        _get_widget(_http(postgres_session, monkeypatch), context.id, owner.id)
    )

    assert len(records) == 1
    assert records[0]["author_name"] == "Người đã rời"


# ---------------------------------------------------------------------------
# The refusals. Counts, not codes.
# ---------------------------------------------------------------------------


def test_a_stranger_gets_no_records(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    owner = _person(postgres_session, "Nam")
    stranger = _person(postgres_session, "Người lạ")
    context = _context(postgres_session, owner)
    memory = _photo(postgres_session, context, owner)

    response = _get_widget(
        _http(postgres_session, monkeypatch), context.id, stranger.id
    )

    assert response.status_code == 403, response.text
    assert len(widget_records(response)) == 0
    assert memory.image_url not in response.text
    assert CAPTION not in response.text
    assert "Nam" not in response.text
    assert GROUP_NAME not in response.text


def test_an_invited_person_gets_no_records_before_they_accept(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The row exists and looks live. Only `state` disqualifies it.

    This is the case the fake layer structurally cannot reach, and the one an
    `is_member` written as "SELECT 1 FROM memberships WHERE ..." would get
    wrong while every other membership test stayed green.
    """

    owner = _person(postgres_session, "Nam")
    invitee = _person(postgres_session, "Người được mời")
    context = _context(postgres_session, owner)
    memory = _photo(postgres_session, context, owner)
    _membership(postgres_session, context, invitee, MembershipState.INVITED)

    response = _get_widget(_http(postgres_session, monkeypatch), context.id, invitee.id)

    assert response.status_code == 403, response.text
    assert len(widget_records(response)) == 0
    assert memory.image_url not in response.text
    assert CAPTION not in response.text


def test_a_person_who_left_gets_no_records(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """A widget outlives the app being open. Leaving has to switch it off."""

    owner = _person(postgres_session, "Nam")
    leaver = _person(postgres_session, "Người đã rời")
    context = _context(postgres_session, owner)
    memory = _photo(postgres_session, context, owner)
    _membership(
        postgres_session,
        context,
        leaver,
        MembershipState.LEFT,
        left_at=NOW + timedelta(days=1),
    )

    response = _get_widget(_http(postgres_session, monkeypatch), context.id, leaver.id)

    assert response.status_code == 403, response.text
    assert len(widget_records(response)) == 0
    assert memory.image_url not in response.text


def test_a_member_of_one_group_gets_no_records_from_another(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    owner_a = _person(postgres_session, "Nam")
    owner_b = _person(postgres_session, "Bình")
    context_a = _context(postgres_session, owner_a, "Nhóm A")
    context_b = _context(postgres_session, owner_b, "Nhóm B")
    memory_b = _photo(postgres_session, context_b, owner_b, caption="Bí mật nhóm B")
    _photo(postgres_session, context_a, owner_a, caption="Của nhóm A", suffix="-a")

    response = _get_widget(
        _http(postgres_session, monkeypatch), context_b.id, owner_a.id
    )

    assert response.status_code == 403, response.text
    assert len(widget_records(response)) == 0
    assert memory_b.image_url not in response.text
    assert "Bí mật nhóm B" not in response.text


def test_a_guest_gets_no_records(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Nobody arriving from `/g/{token}` reaches this route.

    A guest is not a member and carries the `guest` role; `view_group_memories`
    admits `member` and `group_admin` only. The request below spells the guest
    out explicitly so that the day somebody widens that role set, this fails.
    """

    owner = _person(postgres_session, "Nam")
    outsider = _person(postgres_session, "Khách")
    context = _context(postgres_session, owner)
    memory = _photo(postgres_session, context, owner)

    async def exchange():
        transport = httpx.ASGITransport(app=_http(postgres_session, monkeypatch))
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(
                f"/contexts/{context.id}/widget",
                headers={
                    "X-Actor-ID": str(outsider.id),
                    "X-Actor-Roles": "guest",
                    "X-Actor-Contexts": str(context.id),
                },
            )

    response = anyio.run(exchange)

    assert response.status_code == 403, response.text
    assert len(widget_records(response)) == 0
    assert memory.image_url not in response.text


def test_the_refusal_is_the_same_whether_the_group_exists(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """No status code and no body distinguishes a real group from a made-up one.

    A widget id is guessable in a way a session token is not, so a route that
    answered 404 for "no such group" and 403 for "not yours" would let anybody
    holding one valid actor header enumerate which group ids are real.
    """

    owner = _person(postgres_session, "Nam")
    stranger = _person(postgres_session, "Người lạ")
    context = _context(postgres_session, owner)
    _photo(postgres_session, context, owner)
    app = _http(postgres_session, monkeypatch)

    real = _get_widget(app, context.id, stranger.id)
    imaginary = _get_widget(app, uuid.uuid4(), stranger.id)

    assert real.status_code == imaginary.status_code == 403
    assert len(widget_records(real)) == len(widget_records(imaginary)) == 0
    assert real.json() == imaginary.json()


# ---------------------------------------------------------------------------
# The empty state
# ---------------------------------------------------------------------------


def test_a_group_with_no_photographs_answers_two_hundred_and_says_nothing(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Empty is 200, and the body carries no fact about the group.

    404 would be wrong twice: the question was valid, and the second status
    code would be exactly the signal a stranger is fishing for above.
    """

    owner = _person(postgres_session, "Nam")
    context = _context(postgres_session, owner)

    response = _get_widget(_http(postgres_session, monkeypatch), context.id, owner.id)

    assert response.status_code == 200, response.text
    assert len(widget_records(response)) == 0
    assert response.json() == {"context_id": str(context.id), "photo": None}
    assert GROUP_NAME not in response.text
    assert "Nam" not in response.text


def test_a_group_holding_only_checkins_answers_null(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    owner = _person(postgres_session, "Nam")
    context = _context(postgres_session, owner)
    _checkin(postgres_session, context, owner, at=NOW)

    response = _get_widget(_http(postgres_session, monkeypatch), context.id, owner.id)

    assert response.status_code == 200, response.text
    assert len(widget_records(response)) == 0
    assert "Quán lẩu" not in response.text
