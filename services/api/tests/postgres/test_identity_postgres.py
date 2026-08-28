"""Identity repository and HTTP authorization on real PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import anyio
import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import Context, Membership, MembershipState, Person

pytestmark = pytest.mark.postgres

NOW = datetime(2030, 8, 28, 9, 0, tzinfo=UTC)


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name, created_at=NOW)
    session.add(person)
    session.flush()
    return person


def _open_membership(
    repository: SqlAlchemyApiRepository,
    context_id: uuid.UUID,
    person_id: uuid.UUID,
    invited_by_id: uuid.UUID,
):
    invitation = repository.add_member(context_id, person_id, invited_by_id)
    return repository.accept_membership(invitation.id, NOW)


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


def _actor_headers(
    actor_id: uuid.UUID,
    *,
    roles: str = "member",
    claimed_context_id: uuid.UUID | None = None,
) -> dict[str, str]:
    headers = {
        "X-Actor-ID": str(actor_id),
        "X-Actor-Roles": roles,
    }
    if claimed_context_id is not None:
        headers["X-Actor-Contexts"] = str(claimed_context_id)
    return headers


def test_repository_membership_lifecycle_creates_a_new_row_on_rejoin(
    postgres_session: Session,
):
    owner = _person(postgres_session, "Synthetic owner")
    friend = _person(postgres_session, "Synthetic friend")
    repository = SqlAlchemyApiRepository(postgres_session)

    context = repository.create_context("Synthetic context", owner.id)
    owner_membership = _open_membership(repository, context.id, owner.id, owner.id)
    invitation = repository.add_member(context.id, friend.id, owner.id)

    assert invitation.state == "invited"
    assert invitation.joined_at is None
    assert repository.is_member(context.id, friend.id) is False
    assert [row.id for row in repository.list_members(context.id)] == [
        owner_membership.id,
        invitation.id,
    ]

    accepted = repository.accept_membership(invitation.id, NOW)
    assert accepted.state == "active"
    assert accepted.joined_at == NOW
    assert repository.is_member(context.id, friend.id) is True

    left_at = NOW + timedelta(hours=1)
    closed = repository.leave_context(context.id, friend.id, left_at)
    assert closed.state == "left"
    assert closed.left_at == left_at
    assert repository.is_member(context.id, friend.id) is False
    assert [row.id for row in repository.list_members(context.id)] == [
        owner_membership.id
    ]

    rejoined = repository.add_member(context.id, friend.id, owner.id)
    assert rejoined.id != invitation.id
    assert rejoined.state == "invited"
    historical_ids = tuple(
        postgres_session.scalars(
            select(Membership.id)
            .where(
                Membership.context_id == context.id,
                Membership.person_id == friend.id,
            )
            .order_by(Membership.created_at, Membership.id)
        )
    )
    assert historical_ids == (invitation.id, rejoined.id)


def test_partial_unique_index_refuses_two_open_memberships(
    postgres_session: Session,
):
    owner = _person(postgres_session, "Synthetic owner")
    friend = _person(postgres_session, "Synthetic friend")
    repository = SqlAlchemyApiRepository(postgres_session)
    context = repository.create_context("Synthetic context", owner.id)
    repository.add_member(context.id, friend.id, owner.id)

    with pytest.raises(IntegrityError) as caught:
        with postgres_session.begin_nested():
            repository.add_member(context.id, friend.id, owner.id)

    assert _constraint_name(caught.value) == "uq_memberships_open_per_person"


@pytest.mark.parametrize("column", ["state", "left_at"])
def test_check_constraint_refuses_half_of_the_leave_transition(
    postgres_session: Session,
    column: str,
):
    owner = _person(postgres_session, "Synthetic owner")
    repository = SqlAlchemyApiRepository(postgres_session)
    context = repository.create_context("Synthetic context", owner.id)
    membership = _open_membership(repository, context.id, owner.id, owner.id)
    value = MembershipState.LEFT if column == "state" else NOW + timedelta(hours=1)

    with pytest.raises(IntegrityError) as caught:
        with postgres_session.begin_nested():
            postgres_session.execute(
                update(Membership)
                .where(Membership.id == membership.id)
                .values({column: value})
            )

    assert (
        _constraint_name(caught.value) == "ck_memberships_left_state_matches_timestamp"
    )


def test_identity_routes_enforce_actor_membership_on_real_rows(
    postgres_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    owner = _person(postgres_session, "Synthetic owner")
    friend = _person(postgres_session, "Synthetic friend")
    outsider = _person(postgres_session, "Synthetic outsider")
    repository = SqlAlchemyApiRepository(postgres_session)

    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repository

    async def exercise_routes() -> tuple[uuid.UUID, uuid.UUID]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            created = await client.post(
                "/contexts",
                headers=_actor_headers(owner.id),
                json={"display_name": "Synthetic context"},
            )
            assert created.status_code == 201, created.text
            context_id = uuid.UUID(created.json()["id"])
            assert repository.is_member(context_id, owner.id) is True

            other = await client.post(
                "/contexts",
                headers=_actor_headers(outsider.id),
                json={"display_name": "Other synthetic context"},
            )
            assert other.status_code == 201, other.text

            invited = await client.post(
                f"/contexts/{context_id}/members",
                headers=_actor_headers(owner.id),
                json={"person_id": str(friend.id)},
            )
            assert invited.status_code == 201, invited.text
            membership_id = uuid.UUID(invited.json()["id"])
            assert invited.json()["state"] == "invited"

            # A claimed context header is not database membership. This actor
            # belongs to another context and must not read the target roster.
            outsider_list = await client.get(
                f"/contexts/{context_id}/members",
                headers=_actor_headers(outsider.id, claimed_context_id=context_id),
            )
            assert outsider_list.status_code == 403, outsider_list.text

            wrong_accept = await client.post(
                f"/memberships/{membership_id}/accept",
                headers=_actor_headers(outsider.id),
            )
            assert wrong_accept.status_code == 403, wrong_accept.text
            assert postgres_session.get(Membership, membership_id).state == (
                MembershipState.INVITED
            )

            accepted = await client.post(
                f"/memberships/{membership_id}/accept",
                headers=_actor_headers(friend.id),
            )
            assert accepted.status_code == 200, accepted.text
            assert accepted.json()["state"] == "active"

            visible = await client.get(
                f"/contexts/{context_id}/members",
                headers=_actor_headers(friend.id),
            )
            assert visible.status_code == 200, visible.text
            assert {row["person_id"] for row in visible.json()} == {
                str(owner.id),
                str(friend.id),
            }

            left = await client.delete(
                f"/contexts/{context_id}/members/{friend.id}",
                headers=_actor_headers(friend.id),
            )
            assert left.status_code == 204, left.text

            # Leaving closes current roster authorization even if a stale
            # upstream header still claims the context.
            former_list = await client.get(
                f"/contexts/{context_id}/members",
                headers=_actor_headers(friend.id, claimed_context_id=context_id),
            )
            assert former_list.status_code == 403, former_list.text

            owner_view = await client.get(
                f"/contexts/{context_id}/members",
                headers=_actor_headers(owner.id),
            )
            assert owner_view.status_code == 200, owner_view.text
            assert [row["person_id"] for row in owner_view.json()] == [str(owner.id)]

            reinvited = await client.post(
                f"/contexts/{context_id}/members",
                headers=_actor_headers(owner.id),
                json={"person_id": str(friend.id)},
            )
            assert reinvited.status_code == 201, reinvited.text
            assert reinvited.json()["id"] != str(membership_id)
            return context_id, membership_id

    context_id, membership_id = anyio.run(exercise_routes)

    membership = postgres_session.get(Membership, membership_id)
    assert membership is not None
    assert membership.state == MembershipState.LEFT
    assert membership.left_at == NOW
    assert postgres_session.get(Context, context_id) is not None
