"""The friend graph against a real PostgreSQL server.

Three guarantees here cannot exist in the dict-backed fake, and the API tests
are blind to all three by construction:

* `uq_friend_edge_live` -- a UNIQUE index over
  `least(requester_id, addressee_id), greatest(...)` restricted to live states.
  This is what makes (A asks B) and (B asks A) one edge. A dict keyed by
  request id cannot express it, so the fake happily stores two pending rows for
  one pair, and both could be accepted into two friendships between the same
  two people.
* `ck_friend_requests_decided_state_matches_timestamp` -- an answered row must
  carry a decision time and a pending one must not. The fake sets whatever the
  code sets.
* `ck_friend_requests_no_self_friendship` -- the domain refuses a self-edge;
  this makes the refusal true of the DATA, for any future writer that skips the
  domain.

The last test drives real HTTP into this database, because the API layer proves
the wiring against a fake and the repository tests prove the SQL, and neither
proves that the route and the schema agree.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import anyio
import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.errors import RepositoryConflict
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import FriendRequest, FriendRequestState, Person

NOW = datetime(2030, 8, 29, 12, tzinfo=UTC)


def _person(session: Session, name: str) -> uuid.UUID:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person.id


def _row(session: Session, request_id: uuid.UUID) -> FriendRequest:
    return session.scalar(select(FriendRequest).where(FriendRequest.id == request_id))


# --- the index that makes one pair one edge ---------------------------------


def test_two_people_asking_each_other_at_once_produce_one_edge(
    postgres_session: Session,
):
    """The race the fake cannot see.

    Anh taps "add Binh" and Binh taps "add Anh" in the same second. Without
    `uq_friend_edge_live` both rows land, both get accepted, and the product
    holds two friendships between two people -- one screen counts 2, another
    counts 1, and there is no non-arbitrary way to repair it afterwards.
    """
    repository = SqlAlchemyApiRepository(postgres_session)
    anh = _person(postgres_session, "Anh")
    binh = _person(postgres_session, "Bình")

    repository.open_friend_request(requester_id=anh, addressee_id=binh, now=NOW)

    with pytest.raises(RepositoryConflict) as collided:
        repository.open_friend_request(
            requester_id=binh, addressee_id=anh, now=NOW
        )
    # Named, not a blind `Exception`: this must fail because the DATABASE
    # refused, not because the call signature drifted. `FRIEND_EDGE_EXISTS` is
    # the code the repository raises only when `uq_friend_edge_live` fires.
    assert collided.value.code == "FRIEND_EDGE_EXISTS"


def test_the_index_also_refuses_a_duplicate_in_the_same_direction(
    postgres_session: Session,
):
    repository = SqlAlchemyApiRepository(postgres_session)
    anh = _person(postgres_session, "Anh")
    binh = _person(postgres_session, "Bình")

    repository.open_friend_request(requester_id=anh, addressee_id=binh, now=NOW)

    with pytest.raises(RepositoryConflict) as collided:
        repository.open_friend_request(requester_id=anh, addressee_id=binh, now=NOW)
    assert collided.value.code == "FRIEND_EDGE_EXISTS"


def test_a_declined_edge_frees_the_pair_for_a_new_request(postgres_session: Session):
    """`declined` is deliberately absent from the index predicate.

    Being turned down once must not be permanent. If this fails, the index
    predicate has been widened and a single mistaken tap removes somebody from
    your reachable set forever.
    """
    repository = SqlAlchemyApiRepository(postgres_session)
    anh = _person(postgres_session, "Anh")
    binh = _person(postgres_session, "Bình")

    first = repository.open_friend_request(
        requester_id=anh, addressee_id=binh, now=NOW
    )
    repository.decide_friend_request(
        request_id=first.id, state="declined", decided_by_id=binh, now=NOW
    )

    second = repository.open_friend_request(
        requester_id=anh, addressee_id=binh, now=NOW
    )

    assert second.state == "pending"
    assert (
        postgres_session.scalar(select(func.count()).select_from(FriendRequest)) == 2
    )


def test_a_blocked_edge_keeps_holding_the_pair(postgres_session: Session):
    """`blocked` IS in the index predicate. Blocking is meant to be durable."""
    repository = SqlAlchemyApiRepository(postgres_session)
    anh = _person(postgres_session, "Anh")
    binh = _person(postgres_session, "Bình")

    edge = repository.open_friend_request(requester_id=anh, addressee_id=binh, now=NOW)
    repository.decide_friend_request(
        request_id=edge.id, state="blocked", decided_by_id=binh, now=NOW
    )

    with pytest.raises(RepositoryConflict) as collided:
        repository.open_friend_request(requester_id=anh, addressee_id=binh, now=NOW)
    assert collided.value.code == "FRIEND_EDGE_EXISTS"


# --- constraints the domain also enforces, made true of the data ------------


def test_the_database_refuses_a_self_friendship(postgres_session: Session):
    anh = _person(postgres_session, "Anh")
    postgres_session.add(
        FriendRequest(
            id=uuid.uuid4(),
            requester_id=anh,
            addressee_id=anh,
            state=FriendRequestState.PENDING,
            created_at=NOW,
        )
    )
    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_an_answered_row_must_carry_a_decision_time(postgres_session: Session):
    """Otherwise "when did Binh accept" has no answer for some accepted rows."""
    anh = _person(postgres_session, "Anh")
    binh = _person(postgres_session, "Bình")
    postgres_session.add(
        FriendRequest(
            id=uuid.uuid4(),
            requester_id=anh,
            addressee_id=binh,
            state=FriendRequestState.ACCEPTED,
            created_at=NOW,
            decided_at=None,
        )
    )
    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_a_pending_row_must_not_carry_a_decision_time(postgres_session: Session):
    anh = _person(postgres_session, "Anh")
    binh = _person(postgres_session, "Bình")
    postgres_session.add(
        FriendRequest(
            id=uuid.uuid4(),
            requester_id=anh,
            addressee_id=binh,
            state=FriendRequestState.PENDING,
            created_at=NOW,
            decided_at=NOW,
        )
    )
    with pytest.raises(IntegrityError):
        postgres_session.flush()


# --- reading friendship back from the events --------------------------------


def test_friendship_is_read_back_from_the_accepted_row(postgres_session: Session):
    """There is no `friends` table to drift from this query.

    Both directions: whoever asked, both people see one friend.
    """
    repository = SqlAlchemyApiRepository(postgres_session)
    anh = _person(postgres_session, "Anh")
    binh = _person(postgres_session, "Bình")

    edge = repository.open_friend_request(requester_id=anh, addressee_id=binh, now=NOW)
    assert repository.list_friends(anh) == []

    repository.decide_friend_request(
        request_id=edge.id, state="accepted", decided_by_id=binh, now=NOW
    )

    for reader, expected in ((anh, "Bình"), (binh, "Anh")):
        friends = repository.list_friends(reader)
        assert [friend.other_display_name for friend in friends] == [expected]


def test_the_accepting_party_is_recorded_on_the_row(postgres_session: Session):
    """The audit trail for the consent rule.

    An accepted row whose `decided_by_id` equals `requester_id` is evidence of
    the bug this whole feature is built to make impossible, so the column has
    to actually be written.
    """
    repository = SqlAlchemyApiRepository(postgres_session)
    anh = _person(postgres_session, "Anh")
    binh = _person(postgres_session, "Bình")

    edge = repository.open_friend_request(requester_id=anh, addressee_id=binh, now=NOW)
    repository.decide_friend_request(
        request_id=edge.id, state="accepted", decided_by_id=binh, now=NOW
    )

    row = _row(postgres_session, edge.id)
    assert row.decided_by_id == binh
    assert row.decided_by_id != row.requester_id


def test_a_stranger_reading_a_request_by_id_gets_nothing(postgres_session: Session):
    repository = SqlAlchemyApiRepository(postgres_session)
    anh = _person(postgres_session, "Anh")
    binh = _person(postgres_session, "Bình")
    cuong = _person(postgres_session, "Cường")

    edge = repository.open_friend_request(requester_id=anh, addressee_id=binh, now=NOW)

    assert repository.get_friend_request(edge.id, cuong) is None
    assert repository.get_friend_request(edge.id, binh) is not None


# --- route and schema agree -------------------------------------------------


def test_consent_is_required_over_real_http_against_this_database(
    postgres_engine, postgres_session: Session
):
    """The whole feature, end to end, on the real schema.

    The API tests prove this against a fake and the tests above prove the SQL.
    Neither proves the route and the schema agree -- which is the failure mode
    where every layer is individually green and the product is broken.
    """
    anh = _person(postgres_session, "Anh")
    binh = _person(postgres_session, "Bình")
    postgres_session.commit()

    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(
        postgres_session
    )

    def headers(actor: uuid.UUID) -> dict[str, str]:
        return {"X-Actor-ID": str(actor), "X-Actor-Roles": "member"}

    async def drive() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            asked = await client.post(
                "/friends/requests",
                headers=headers(anh),
                json={"addressee_id": str(binh)},
            )
            assert asked.status_code == 201, asked.text
            request_id = asked.json()["id"]

            forged = await client.post(
                f"/friends/requests/{request_id}/respond",
                headers=headers(anh),
                json={"decision": "accept"},
            )
            assert forged.status_code == 403, forged.text

            still_none = await client.get(
                f"/people/{anh}/friends", headers=headers(anh)
            )
            assert still_none.json()["friends"] == []

            accepted = await client.post(
                f"/friends/requests/{request_id}/respond",
                headers=headers(binh),
                json={"decision": "accept"},
            )
            assert accepted.status_code == 200, accepted.text

            listed = await client.get(f"/people/{anh}/friends", headers=headers(anh))
            assert [
                friend["display_name"] for friend in listed.json()["friends"]
            ] == ["Bình"]

    anyio.run(drive)
