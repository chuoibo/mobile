"""What the person tapping "chặn" actually receives when the write is refused.

`test_friend_consent_races_postgres.py` (rd-qa-36) proves the repository layer:
`decide_friend_request` must raise `RepositoryConflict` instead of letting
`uq_friend_edge_live` escape as an `IntegrityError`. That is necessary and it is
not sufficient. A repository that raises a named conflict nobody catches is the
same 500 with a nicer traceback -- `respond_to_friend_request` had no
`except RepositoryConflict` at all, so the named refusal would have travelled
straight through the service, past every user middleware, and out of
`ServerErrorMiddleware` as `text/plain`.

So this file asks the question one layer further out, over the real ASGI stack
against the real schema: **what status code and what body**. It is deliberately
the only friend test that goes through HTTP with a live database, because it is
the only claim here that HTTP can decide.

The route driven is the ordinary one a user walks, not a contrived one:

    A asks B  ->  B declines  ->  A asks again  ->  A blocks the old notice

The last tap is a stale row from A's own notification list, and the pair now
holds a live `pending` row, so the partial unique index refuses the update. The
product answer to that is "no", not "the server broke".
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import FriendRequest, Person

#: Ids of every person this module creates, so teardown deletes exactly those.
#: The postgres tier shares one schema and one row too many turns a row-counting
#: test in another file red -- see `test_friend_requests_postgres.py`, which
#: asserts `count(*) == 2` over the whole table.
_CREATED: list[uuid.UUID] = []


@pytest.fixture
def live_client(postgres_engine: Engine) -> Iterator[TestClient]:
    """The real app, the real schema, one committing session per request.

    Each request gets its own session, exactly as `get_repository` gives it in
    production. A single shared session would hide the whole point: the failed
    flush has to be survivable across a request boundary, and a session reused
    from a previous request would already be poisoned or already be rolled back
    by something other than the code under test.

    `raise_server_exceptions=False` so an unhandled exception is observed as the
    500 a user would receive rather than re-raised into the test. Before the
    fix this file guards, that is exactly what happened, and a test that dies on
    a traceback reads like a broken test rather than a broken product.
    """

    def repository_dependency():
        with Session(postgres_engine, expire_on_commit=False) as session:
            with session.begin():
                yield SqlAlchemyApiRepository(session)

    app = create_app()
    app.dependency_overrides[get_repository] = repository_dependency
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        # This test commits for real. Delete the rows it made, and only those.
        with Session(postgres_engine) as cleanup:
            cleanup.execute(
                delete(FriendRequest).where(FriendRequest.requester_id.in_(_CREATED))
            )
            cleanup.execute(delete(Person).where(Person.id.in_(_CREATED)))
            cleanup.commit()
        _CREATED.clear()


def _headers(actor_id: uuid.UUID) -> dict[str, str]:
    return {"X-Actor-ID": str(actor_id), "X-Actor-Roles": "member"}


def _two_people(engine: Engine) -> tuple[uuid.UUID, uuid.UUID]:
    dung = Person(id=uuid.uuid4(), display_name="Dũng")
    em = Person(id=uuid.uuid4(), display_name="Em")
    with Session(engine) as session:
        session.add_all([dung, em])
        session.commit()
        _CREATED.extend([dung.id, em.id])
        return dung.id, em.id


def test_blocking_a_stale_declined_notice_answers_409_not_500(
    live_client: TestClient, postgres_engine: Engine
):
    """The whole walk, over HTTP. The last tap must be a refusal, not a crash.

    Blocking is the only door a requester has -- PR #196 ships no "withdraw
    request" -- so a 500 here is not a cosmetic status code. It is the product
    telling somebody who is trying to cut a tie that the attempt failed for no
    reason they can act on, on a body (`text/plain`, no code) their client
    cannot even parse into a message.
    """
    dung, em = _two_people(postgres_engine)

    asked = live_client.post(
        "/friends/requests",
        json={"addressee_id": str(em)},
        headers=_headers(dung),
    )
    assert asked.status_code == 201, asked.text
    stale_id = asked.json()["id"]

    declined = live_client.post(
        f"/friends/requests/{stale_id}/respond",
        json={"decision": "decline"},
        headers=_headers(em),
    )
    assert declined.status_code == 200, declined.text
    assert declined.json()["state"] == "declined"

    # Being turned down once is not a life sentence: the pair is free again.
    asked_again = live_client.post(
        "/friends/requests",
        json={"addressee_id": str(em)},
        headers=_headers(dung),
    )
    assert asked_again.status_code == 201, asked_again.text

    # Dũng now blocks the notification still sitting in his own list, which
    # points at the declined row rather than the live one.
    blocked = live_client.post(
        f"/friends/requests/{stale_id}/respond",
        json={"decision": "block"},
        headers=_headers(dung),
    )

    assert blocked.status_code == 409, (
        "chặn một thông báo cũ phải là lời từ chối có tên, không phải 500: "
        f"{blocked.status_code} {blocked.text[:200]}"
    )
    assert blocked.headers["content-type"].startswith("application/json")
    body = blocked.json()
    assert isinstance(body.get("code"), str) and body["code"], body
    # A refusal must not narrate the database. `uq_friend_edge_live`, the SQL
    # text and the two person ids are all in the exception this replaces.
    rendered = blocked.text.lower()
    for leaked in ("uq_friend_edge_live", "traceback", "update friend_requests"):
        assert leaked not in rendered, f"refusal leaked {leaked!r}: {blocked.text[:300]}"


def test_the_live_edge_is_untouched_after_that_refusal(
    live_client: TestClient, postgres_engine: Engine
):
    """A refused write must leave the pair exactly as it found it.

    The failed flush aborts a PostgreSQL transaction, so "the refusal was
    handled" and "nothing half-written was committed" are two different claims.
    This is the second one, read back on a fresh connection.
    """
    dung, em = _two_people(postgres_engine)

    stale_id = live_client.post(
        "/friends/requests",
        json={"addressee_id": str(em)},
        headers=_headers(dung),
    ).json()["id"]
    live_client.post(
        f"/friends/requests/{stale_id}/respond",
        json={"decision": "decline"},
        headers=_headers(em),
    )
    live_id = live_client.post(
        "/friends/requests",
        json={"addressee_id": str(em)},
        headers=_headers(dung),
    ).json()["id"]

    live_client.post(
        f"/friends/requests/{stale_id}/respond",
        json={"decision": "block"},
        headers=_headers(dung),
    )

    with Session(postgres_engine, expire_on_commit=False) as reader:
        repository = SqlAlchemyApiRepository(reader)
        assert repository.get_friend_request(uuid.UUID(stale_id), dung).state == (
            "declined"
        ), "hàng cũ đã bị ghi một nửa"
        assert repository.get_friend_request(uuid.UUID(live_id), dung).state == (
            "pending"
        ), "lời mời đang sống bị lượt chặn hỏng làm hỏng theo"
        assert repository.list_friends(dung) == []

    # And the door still works where it is meant to work: blocking the row that
    # actually holds the pair succeeds.
    on_the_live_row = live_client.post(
        f"/friends/requests/{live_id}/respond",
        json={"decision": "block"},
        headers=_headers(dung),
    )
    assert on_the_live_row.status_code == 200, on_the_live_row.text
    assert on_the_live_row.json()["state"] == "blocked"
