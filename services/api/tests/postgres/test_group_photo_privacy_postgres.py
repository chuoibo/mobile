"""Who can reach a group's photographs, over real HTTP against real PostgreSQL.

rd-qa-33. The memory wall is the one surface in this product that holds a
picture of real people, so it is the surface where a membership bug stops being
an access-control abstraction and becomes a stranger looking at somebody's
dinner.

`tests/postgres/test_group_memories_postgres.py` already proves the service
rules for a stranger and for a person who **left**. Two things it does not
prove, and this file does:

1. An **invited** person -- one who has a `Membership` row, in state `invited`,
   with `left_at` NULL -- cannot read the wall. That state is the dangerous one
   precisely because the row exists and looks live: an `is_member` that asked
   only "is there a membership row" would answer yes. The `left` tests cannot
   catch that mistake, because a left row is disqualified by `left_at` alone.
2. The rules are reachable **over HTTP**, on the photo routes specifically. A
   service test passes even when the router is never registered.

Measured with a mutation, not by reading the code: dropping
`Membership.state == ACTIVE` from `SqlAlchemyApiRepository.is_member` leaves
every photo-wall assertion in this repo green except the ones below.
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

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

# A stand-in for the one thing this wall exists to hold. The bytes live at
# whatever host this string names -- this product stores the string, never the
# photograph -- which is itself the finding recorded in the QA report.
PHOTO_URL = "https://anh.example/nhom-a/toi-thu-bay.jpg"
#: Một id địa điểm để gắn ảnh vào (M12). Không có FK từ `memories` sang
#: `places`, giống `expenses.context_id` ngày trước: id ở đây là nhãn của
#: một hàng danh mục, và danh mục thì nhập lại được.
PLACE_ID = "p-quan-thu"


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
    # Deliberately generous: every role this product grants. If the wall ever
    # opens, it must not be because the caller was under-credentialled.
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


def _photo(
    session: Session,
    context: Context,
    author: Person,
    *,
    place_id: str | None = None,
    place_name: str | None = None,
) -> Memory:
    memory = Memory(
        id=uuid.uuid4(),
        context_id=context.id,
        author_id=author.id,
        kind=MemoryKind.PHOTO,
        image_url=PHOTO_URL,
        caption="Tối thứ bảy",
        place_id=place_id,
        place_name=place_name,
        created_at=NOW,
    )
    session.add(memory)
    session.flush()
    return memory


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


def _get_wall(app, context_id: uuid.UUID, actor_id: uuid.UUID):
    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(
                f"/contexts/{context_id}/memories", headers=_headers(actor_id)
            )

    return anyio.run(exchange)


def test_the_wall_answers_its_own_member_first(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The positive direction, asserted before any refusal is believed.

    Without this, every assertion below could pass against a route that
    answers nobody -- a wall that is broken for everyone is not a wall that is
    private.
    """
    owner = _person(postgres_session, "Nam")
    context = _context(postgres_session, owner, "Nhóm A")
    _photo(postgres_session, context, owner)

    response = _get_wall(_http(postgres_session, monkeypatch), context.id, owner.id)

    assert response.status_code == 200, response.text
    photos = response.json()["memories"]
    assert [photo["image_url"] for photo in photos] == [PHOTO_URL]


def test_an_invited_person_cannot_see_the_photos_before_they_accept(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The gap this file was written for.

    An invite creates a real `Membership` row (`ensure_invited_membership`),
    state `invited`, `left_at` NULL. Nothing about the row's existence or its
    `left_at` disqualifies it -- only the state does. So this is the one case
    that catches an `is_member` narrowed to "a row exists".
    """
    owner = _person(postgres_session, "Nam")
    invitee = _person(postgres_session, "Người được mời")
    context = _context(postgres_session, owner, "Nhóm A")
    _photo(postgres_session, context, owner)
    _membership(postgres_session, context, invitee, MembershipState.INVITED)

    response = _get_wall(_http(postgres_session, monkeypatch), context.id, invitee.id)

    assert response.status_code in {403, 404}, response.text
    assert PHOTO_URL not in response.text


def test_an_invited_person_cannot_put_a_photo_on_a_wall_they_have_not_joined(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Reading is the leak; writing is the other half of the same gate."""
    owner = _person(postgres_session, "Nam")
    invitee = _person(postgres_session, "Người được mời")
    context = _context(postgres_session, owner, "Nhóm A")
    _membership(postgres_session, context, invitee, MembershipState.INVITED)
    app = _http(postgres_session, monkeypatch)

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.post(
                f"/contexts/{context.id}/memories",
                headers=_headers(invitee.id),
                # Well formed on purpose: a malformed url dies at the schema
                # with a 422 and stops proving that membership is the gate.
                json={
                    "image_url": f"/contexts/{context.id}/photos/{uuid.uuid4()}",
                    "caption": "Chen vào",
                },
            )

    response = anyio.run(exchange)

    assert response.status_code in {403, 404}, response.text


def test_a_member_of_one_group_cannot_open_another_groups_photos(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Being active *somewhere* must not be being active *here*.

    The neighbour is a fully active admin of their own group, so the only
    thing standing between them and these photographs is the `context_id`
    predicate.
    """
    owner = _person(postgres_session, "Nam")
    neighbour = _person(postgres_session, "Chủ nhóm B")
    group_a = _context(postgres_session, owner, "Nhóm A")
    _context(postgres_session, neighbour, "Nhóm B")
    _photo(postgres_session, group_a, owner)

    response = _get_wall(_http(postgres_session, monkeypatch), group_a.id, neighbour.id)

    assert response.status_code in {403, 404}, response.text
    assert PHOTO_URL not in response.text


def test_someone_who_left_stops_seeing_the_photos_over_http(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The service layer proves the rule; this proves a client meets it."""
    owner = _person(postgres_session, "Nam")
    departed = _person(postgres_session, "Người đã rời")
    context = _context(postgres_session, owner, "Nhóm A")
    _photo(postgres_session, context, owner)
    _membership(postgres_session, context, departed, MembershipState.LEFT, left_at=NOW)

    response = _get_wall(_http(postgres_session, monkeypatch), context.id, departed.id)

    assert response.status_code in {403, 404}, response.text
    assert PHOTO_URL not in response.text


def test_guessing_group_ids_never_returns_a_photo_and_never_says_which_id_exists(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Path-guessing, and the enumeration oracle underneath it.

    Two claims. The obvious one: a stranger walking group ids gets no
    photograph. The quieter one: the refusal for a group that **exists** must
    not be distinguishable from the refusal for one that does not. If real ids
    answered 403 and fictional ids answered 404, the endpoint would confirm
    which groups exist to anybody willing to spend a loop -- turning an opaque
    id into an oracle, and a later leak into a targeted one.
    """
    owner = _person(postgres_session, "Nam")
    stranger = _person(postgres_session, "Người lạ")
    real = _context(postgres_session, owner, "Nhóm A")
    _photo(postgres_session, real, owner)
    app = _http(postgres_session, monkeypatch)

    real_reply = _get_wall(app, real.id, stranger.id)
    invented = [_get_wall(app, uuid.uuid4(), stranger.id) for _ in range(30)]

    assert real_reply.status_code in {403, 404}, real_reply.text
    assert PHOTO_URL not in real_reply.text
    for reply in invented:
        assert reply.status_code in {403, 404}, reply.text
        assert PHOTO_URL not in reply.text

    # The oracle check: an id that exists answers exactly like one that does not.
    assert {reply.status_code for reply in invented} == {real_reply.status_code}


# --- ảnh của nhóm gắn địa điểm (M12, ADR-0017 §2.4) ------------------------


def _get_group_photos(app, place_id: str, actor_id: uuid.UUID):
    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(
                f"/places/{place_id}/group-photos", headers=_headers(actor_id)
            )

    return anyio.run(exchange)


def test_a_place_shows_my_groups_photographs_and_nobody_elses(
    postgres_session, monkeypatch
):
    """The one live case ADR-0017 §5 asks for by name: «người ngoài nhóm KHÔNG
    nhận được ảnh ấy trong gallery của địa điểm».

    Two groups, one place, one photograph each. Each reader must see exactly
    their own. The dangerous failure is not an error -- it is a 200 with one
    extra row in it, which no status code notices.
    """

    app = _http(postgres_session, monkeypatch)
    toi = _person(postgres_session, "Tôi")
    ho = _person(postgres_session, "Người khác")
    nhom_toi = _context(postgres_session, toi, "Nhóm tôi")
    nhom_ho = _context(postgres_session, ho, "Nhóm họ")
    # `_context` đã cho chủ nhóm một hàng ACTIVE; thêm nữa là vi phạm
    # `uq_memberships_open_per_person`.

    cua_toi = _photo(
        postgres_session, nhom_toi, toi, place_id=PLACE_ID, place_name="Quán thử"
    )
    cua_ho = _photo(
        postgres_session, nhom_ho, ho, place_id=PLACE_ID, place_name="Quán thử"
    )
    postgres_session.flush()

    ra_toi = _get_group_photos(app, PLACE_ID, toi.id)
    assert ra_toi.status_code == 200
    assert [row["id"] for row in ra_toi.json()["photos"]] == [str(cua_toi.id)]

    ra_ho = _get_group_photos(app, PLACE_ID, ho.id)
    assert [row["id"] for row in ra_ho.json()["photos"]] == [str(cua_ho.id)]


def test_an_invited_person_does_not_get_the_places_group_photographs(
    postgres_session, monkeypatch
):
    """`invited` is the state that looks live: the row exists, `left_at` is
    NULL, and a gate that asked «is there a membership row» would say yes."""

    app = _http(postgres_session, monkeypatch)
    chu = _person(postgres_session, "Chủ nhóm")
    khach = _person(postgres_session, "Được mời")
    nhom = _context(postgres_session, chu, "Nhóm")
    _membership(postgres_session, nhom, khach, MembershipState.INVITED)
    _photo(postgres_session, nhom, chu, place_id=PLACE_ID, place_name="Quán thử")
    postgres_session.flush()

    assert _get_group_photos(app, PLACE_ID, khach.id).json()["photos"] == []
    assert len(_get_group_photos(app, PLACE_ID, chu.id).json()["photos"]) == 1


def test_someone_who_left_stops_getting_the_places_group_photographs(
    postgres_session, monkeypatch
):
    app = _http(postgres_session, monkeypatch)
    chu = _person(postgres_session, "Chủ nhóm")
    di = _person(postgres_session, "Đã rời")
    nhom = _context(postgres_session, chu, "Nhóm")
    _membership(postgres_session, nhom, di, MembershipState.LEFT, left_at=NOW)
    _photo(postgres_session, nhom, chu, place_id=PLACE_ID, place_name="Quán thử")
    postgres_session.flush()

    assert _get_group_photos(app, PLACE_ID, di.id).json()["photos"] == []


def test_a_photograph_with_no_place_is_not_pulled_into_any_place(
    postgres_session, monkeypatch
):
    """Không gắn địa điểm thì không thuộc địa điểm nào. Một truy vấn quên mệnh
    đề `place_id` sẽ đổ cả tường của nhóm vào màn chi tiết một cái quán."""

    app = _http(postgres_session, monkeypatch)
    toi = _person(postgres_session, "Tôi")
    nhom = _context(postgres_session, toi, "Nhóm")
    _photo(postgres_session, nhom, toi)
    postgres_session.flush()

    assert _get_group_photos(app, PLACE_ID, toi.id).json()["photos"] == []
