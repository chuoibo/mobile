"""F39/F42 against real PostgreSQL: the WHERE clause, not the Python loop.

`tests/api/test_posts_audience.py` proves `ApiService` applies
`app.domain.post_audience.can_read`. It cannot prove anything about
`SqlAlchemyApiRepository._readable_by`, because it runs against a dict-backed
fake whose visibility predicate is a re-implementation written by the same
hand -- a fake agrees with a wrong query exactly as readily as with a right
one.

Two things here need a real database and get one:

* **The predicate is in the SELECT.** `test_only_me_never_leaves_the_database`
  calls the repository directly, with no service in front of it, so a row that
  the query returns has genuinely left storage even if a later loop would have
  dropped it. That is the difference between "filtered out of the response"
  and "never fetched", and only the second one survives somebody adding a
  second reader of the same method.
* **`audience_matches_target` is a CHECK constraint.** A dict cannot refuse a
  row. `test_the_database_refuses...` writes the bad shapes straight through
  the ORM, past every layer that would otherwise have caught them.

Uses `flush`, never `commit`: `postgres_session` rolls back per test, and this
schema is shared with row-counting tests in this directory that go red if rows
from here survive.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import anyio
import httpx
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import (
    Context,
    FriendRequest,
    FriendRequestState,
    Membership,
    MembershipRole,
    MembershipState,
    Person,
    Post,
    PostAudience,
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


def _headers(person_id: uuid.UUID, *, contexts: str | None = None) -> dict[str, str]:
    headers = {"X-Actor-ID": str(person_id), "X-Actor-Roles": "member,group_admin"}
    if contexts is not None:
        # A claim the caller types. Present in some tests precisely so the
        # refusal has to come from the roster instead.
        headers["X-Actor-Contexts"] = contexts
    return headers


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


def _join(session: Session, context: Context, person: Person, *, left_at=None) -> None:
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=person.id,
            state=(MembershipState.ACTIVE if left_at is None else MembershipState.LEFT),
            role=MembershipRole.MEMBER,
            joined_at=NOW,
            left_at=left_at,
        )
    )
    session.flush()


def _befriend(
    session: Session,
    a: Person,
    b: Person,
    *,
    state: FriendRequestState = FriendRequestState.ACCEPTED,
) -> FriendRequest:
    edge = FriendRequest(
        id=uuid.uuid4(),
        requester_id=a.id,
        addressee_id=b.id,
        state=state,
        decided_by_id=b.id if state is not FriendRequestState.PENDING else None,
        created_at=NOW,
        decided_at=NOW if state is not FriendRequestState.PENDING else None,
    )
    session.add(edge)
    session.flush()
    return edge


def _write(
    session: Session,
    author: Person,
    audience: PostAudience,
    *,
    context: Context | None = None,
    body: str = "Tối nay ăn lẩu nhé",
    minutes: int = 0,
) -> Post:
    post = Post(
        id=uuid.uuid4(),
        author_id=author.id,
        audience=audience,
        context_id=None if context is None else context.id,
        body=body,
        image_url=None,
        created_at=NOW + timedelta(minutes=minutes),
    )
    session.add(post)
    session.flush()
    return post


@pytest.fixture
def cast(postgres_session: Session):
    """Author, groupmate, friend, stranger -- and one post per audience.

    The friend is deliberately not in the group and the groupmate is
    deliberately not a friend. A cast where one person is both cannot tell a
    correct implementation from one that treats `friends` and `group` as a
    ladder, which is the mistake this feature is most likely to make.
    """
    session = postgres_session
    author = _person(session, "Minh Anh")
    groupmate = _person(session, "Bảo")
    friend = _person(session, "Chi")
    stranger = _person(session, "Người lạ")

    context = _context(session, author, "Team Đà Lạt")
    _join(session, context, author)
    _join(session, context, groupmate)
    _befriend(session, author, friend)

    posts = {
        "only_me": _write(session, author, PostAudience.ONLY_ME, minutes=0),
        "friends": _write(session, author, PostAudience.FRIENDS, minutes=1),
        "group": _write(
            session, author, PostAudience.GROUP, context=context, minutes=2
        ),
        "public": _write(session, author, PostAudience.PUBLIC, minutes=3),
    }
    return {
        "session": session,
        "repository": SqlAlchemyApiRepository(session),
        "author": author,
        "groupmate": groupmate,
        "friend": friend,
        "stranger": stranger,
        "context": context,
        "posts": posts,
    }


# ---------------------------------------------------------------------------
# The query itself
# ---------------------------------------------------------------------------


def test_the_query_returns_exactly_the_reader_slice(cast):
    """Four readers, four different answers, straight out of the repository."""
    repository = cast["repository"]
    posts = cast["posts"]
    expected = {
        "author": {posts[k].id for k in ("only_me", "friends", "group", "public")},
        "groupmate": {posts["group"].id, posts["public"].id},
        "friend": {posts["friends"].id, posts["public"].id},
        "stranger": {posts["public"].id},
    }
    for who, visible in expected.items():
        rows = repository.list_posts_visible_to(cast[who].id, limit=50)
        assert {row.id for row in rows} == visible, who
        assert len(rows) == len(visible), who


def test_only_me_never_leaves_the_database(cast):
    """No service in front of it. If the row comes back, it has escaped.

    This is the claim the fake cannot make: there, a Python loop drops the row
    after the store handed it over, and the two are indistinguishable from the
    outside until somebody adds a second caller of the same method.
    """
    repository = cast["repository"]
    secret = cast["posts"]["only_me"].id
    for who in ("groupmate", "friend", "stranger"):
        rows = repository.list_posts_visible_to(cast[who].id, limit=50)
        assert secret not in {row.id for row in rows}, who
        wall = repository.list_person_posts_visible_to(
            cast["author"].id, cast[who].id, limit=50
        )
        assert secret not in {row.id for row in wall}, who


def test_a_pending_friend_request_does_not_open_the_friends_audience(
    postgres_session: Session, cast
):
    """`state = 'accepted'` and nothing else. An unanswered ask is a question."""
    repository = cast["repository"]
    hopeful = _person(postgres_session, "Người vừa gửi lời mời")
    _befriend(
        postgres_session, hopeful, cast["author"], state=FriendRequestState.PENDING
    )
    rows = repository.list_posts_visible_to(hopeful.id, limit=50)
    assert {row.id for row in rows} == {cast["posts"]["public"].id}


def test_a_departed_member_stops_reading_the_group(postgres_session: Session, cast):
    """`left_at` decides at read time, so the row goes when the person does."""
    repository = cast["repository"]
    leaver = _person(postgres_session, "Người đã rời nhóm")
    _join(postgres_session, cast["context"], leaver, left_at=NOW)

    rows = repository.list_posts_visible_to(leaver.id, limit=50)
    assert {row.id for row in rows} == {cast["posts"]["public"].id}


def test_a_group_post_does_not_reach_another_group(postgres_session: Session, cast):
    """Membership is of *this* context, not of any context.

    A predicate that joined memberships without correlating on the post's own
    `context_id` passes every single-group test ever written.
    """
    repository = cast["repository"]
    elsewhere_member = _person(postgres_session, "Thành viên nhóm khác")
    other_context = _context(postgres_session, elsewhere_member, "Nhóm khác")
    _join(postgres_session, other_context, elsewhere_member)

    rows = repository.list_posts_visible_to(elsewhere_member.id, limit=50)
    assert {row.id for row in rows} == {cast["posts"]["public"].id}


# ---------------------------------------------------------------------------
# The constraint
# ---------------------------------------------------------------------------


def test_the_database_refuses_a_group_post_with_no_group(postgres_session: Session):
    author = _person(postgres_session, "Minh Anh")
    postgres_session.add(
        Post(
            id=uuid.uuid4(),
            author_id=author.id,
            audience=PostAudience.GROUP,
            context_id=None,
            body="cho nhóm nào?",
            created_at=NOW,
        )
    )
    with pytest.raises(IntegrityError):
        postgres_session.flush()
    postgres_session.rollback()


@pytest.mark.parametrize(
    "audience",
    [PostAudience.ONLY_ME, PostAudience.FRIENDS, PostAudience.PUBLIC],
)
def test_the_database_refuses_a_non_group_post_that_names_a_group(
    postgres_session: Session, audience
):
    """The row that would make `only_me` reachable through a context join."""
    author = _person(postgres_session, "Minh Anh")
    context = _context(postgres_session, author, "Team Đà Lạt")
    postgres_session.add(
        Post(
            id=uuid.uuid4(),
            author_id=author.id,
            audience=audience,
            context_id=context.id,
            body="ghi cho mình",
            created_at=NOW,
        )
    )
    with pytest.raises(IntegrityError):
        postgres_session.flush()
    postgres_session.rollback()


def test_the_database_refuses_an_empty_body(postgres_session: Session):
    author = _person(postgres_session, "Minh Anh")
    postgres_session.add(
        Post(
            id=uuid.uuid4(),
            author_id=author.id,
            audience=PostAudience.PUBLIC,
            context_id=None,
            body="",
            created_at=NOW,
        )
    )
    with pytest.raises(IntegrityError):
        postgres_session.flush()
    postgres_session.rollback()


# ---------------------------------------------------------------------------
# Over HTTP, against the same rows
# ---------------------------------------------------------------------------


def test_the_membership_header_buys_nothing_over_http(
    postgres_session: Session, cast, monkeypatch: pytest.MonkeyPatch
):
    """A stranger naming the group in `X-Actor-Contexts` still reads nothing.

    The one claim the header format makes it easy to believe, refused against
    a real roster rather than against a set literal in a fake.
    """
    app = _http(postgres_session, monkeypatch)
    stranger = cast["stranger"]

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            feed = await client.get(
                "/posts",
                headers=_headers(stranger.id, contexts=str(cast["context"].id)),
            )
            assert feed.status_code == 200, feed.text
            rows = feed.json()["posts"]
            assert [row["id"] for row in rows] == [str(cast["posts"]["public"].id)]

            refused = await client.post(
                "/posts",
                json={
                    "body": "chen vào nhóm",
                    "audience": "group",
                    "context_id": str(cast["context"].id),
                },
                headers=_headers(stranger.id, contexts=str(cast["context"].id)),
            )
            assert refused.status_code == 403, refused.text

    anyio.run(scenario)


def test_reading_someone_elses_only_me_post_by_id_is_404(
    postgres_session: Session, cast, monkeypatch: pytest.MonkeyPatch
):
    """404 and not 403: the status may not confirm that the id is real."""
    app = _http(postgres_session, monkeypatch)
    secret = cast["posts"]["only_me"].id

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            for who in ("groupmate", "friend", "stranger"):
                response = await client.get(
                    f"/posts/{secret}", headers=_headers(cast[who].id)
                )
                assert response.status_code == 404, (who, response.text)

            invented = await client.get(
                f"/posts/{uuid.uuid4()}", headers=_headers(cast["stranger"].id)
            )
            # Identical to the refusal above, which is the point: a real id and
            # an imaginary one are indistinguishable to somebody probing.
            assert invented.status_code == 404
            assert invented.json()["code"] == "post_not_found"

            mine = await client.get(
                f"/posts/{secret}", headers=_headers(cast["author"].id)
            )
            assert mine.status_code == 200, mine.text

    anyio.run(scenario)


def test_reading_by_id_refuses_every_audience_the_reader_is_outside_of(
    postgres_session: Session, cast, monkeypatch: pytest.MonkeyPatch
):
    """The by-id read for all four audiences, against real rows.

    `list_posts_visible_to` is guarded twice -- by the SQL predicate and then
    by `can_read`. This route is guarded once, so it is where a widening of
    `can_read` alone becomes a leak. A mutation that made the `friends` branch
    return True left every other test in this file green.
    """
    app = _http(postgres_session, monkeypatch)
    posts = cast["posts"]
    outside = {
        "groupmate": ("only_me", "friends"),
        "friend": ("only_me", "group"),
        "stranger": ("only_me", "friends", "group"),
    }
    allowed = {
        "groupmate": ("group", "public"),
        "friend": ("friends", "public"),
        "stranger": ("public",),
    }

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            for who, audiences in outside.items():
                for audience in audiences:
                    response = await client.get(
                        f"/posts/{posts[audience].id}",
                        headers=_headers(cast[who].id),
                    )
                    assert response.status_code == 404, (who, audience, response.text)
                    assert response.json()["code"] == "post_not_found"
            for who, audiences in allowed.items():
                for audience in audiences:
                    response = await client.get(
                        f"/posts/{posts[audience].id}",
                        headers=_headers(cast[who].id),
                    )
                    assert response.status_code == 200, (who, audience, response.text)

    anyio.run(scenario)


def test_the_written_post_is_attributed_to_the_caller(
    postgres_session: Session, cast, monkeypatch: pytest.MonkeyPatch
):
    """An `author_id` in the body is refused, not quietly ignored."""
    app = _http(postgres_session, monkeypatch)
    author = cast["author"]
    stranger = cast["stranger"]

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            impersonation = await client.post(
                "/posts",
                json={
                    "body": "giả danh",
                    "audience": "public",
                    "author_id": str(author.id),
                },
                headers=_headers(stranger.id),
            )
            assert impersonation.status_code == 422, impersonation.text

            honest = await client.post(
                "/posts",
                json={"body": "chào cả nhà", "audience": "public"},
                headers=_headers(stranger.id),
            )
            assert honest.status_code == 201, honest.text
            assert honest.json()["author_id"] == str(stranger.id)

    anyio.run(scenario)
