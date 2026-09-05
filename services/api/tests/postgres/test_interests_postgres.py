"""Personal tastes on the real repository, real HTTP, `prod` auth mode.

What only PostgreSQL can show: `uq_person_interests_person_tag` refuses a
second row for one taste, so every count computed from this table is over
distinct claims; replacing the set deletes only what left and leaves the
survivors' rows -- including their `created_at` -- alone; the foreign key
refuses a taste for a person who is not there; and the band lands in the
`people` row rather than in a session.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import anyio
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.api.service import token_digest
from app.db.models import Person, PersonInterest

pytestmark = pytest.mark.postgres


def _prod_app(session: Session):
    app = create_app(auth_mode="prod")
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def _call(app, method: str, path: str, *, token: str | None = None, json=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    async def go():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.request(method, path, json=json, headers=headers)

    return anyio.run(go)


def _person(session: Session, name: str = "Tôi") -> Person:
    row = Person(id=uuid.uuid4(), display_name=name)
    session.add(row)
    session.flush()
    return row


def _token(session: Session, person: Person) -> str:
    raw = f"tok-{uuid.uuid4().hex}"
    now = datetime.now(UTC)
    SqlAlchemyApiRepository(session).create_account_session(
        person_id=person.id,
        token_digest=token_digest(raw),
        issued_from_invite_id=None,
        expires_at=now + timedelta(days=1),
        now=now,
        issued_via="otp",
    )
    session.flush()
    return raw


def test_the_answers_persist_in_their_own_rows(postgres_session):
    person = _person(postgres_session)
    app = _prod_app(postgres_session)
    token = _token(postgres_session, person)

    written = _call(
        app,
        "PUT",
        "/people/me/interests",
        token=token,
        json={"interests": ["cafe", "an-uong"], "budget_band": "vua-phai"},
    )
    assert written.status_code == 200, written.text

    tags = set(
        postgres_session.scalars(
            select(PersonInterest.tag).where(PersonInterest.person_id == person.id)
        )
    )
    assert tags == {"an-uong", "cafe"}
    postgres_session.refresh(person)
    assert person.budget_band == "vua-phai"


def test_the_same_taste_cannot_be_claimed_twice(postgres_session):
    """The uniqueness rule is the part that has to be in the database: every
    count over this table -- «how many of us like cafés» -- is wrong the moment
    one person can appear twice."""

    person = _person(postgres_session)
    postgres_session.add(
        PersonInterest(id=uuid.uuid4(), person_id=person.id, tag="cafe")
    )
    postgres_session.flush()
    postgres_session.add(
        PersonInterest(id=uuid.uuid4(), person_id=person.id, tag="cafe")
    )
    with pytest.raises(IntegrityError):
        postgres_session.flush()
    postgres_session.rollback()


def test_replacing_the_set_leaves_the_survivors_alone(postgres_session):
    """A taste that stays keeps its row and its `created_at`. Delete-all then
    insert-all would be simpler and would rewrite the date somebody first said
    it -- which is the only thing these rows could ever be asked about."""

    person = _person(postgres_session)
    app = _prod_app(postgres_session)
    token = _token(postgres_session, person)
    _call(
        app,
        "PUT",
        "/people/me/interests",
        token=token,
        json={"interests": ["cafe", "an-uong", "game"]},
    )
    before = {
        tag: created
        for tag, created in postgres_session.execute(
            select(PersonInterest.tag, PersonInterest.created_at).where(
                PersonInterest.person_id == person.id
            )
        )
    }
    assert set(before) == {"an-uong", "cafe", "game"}

    _call(
        app,
        "PUT",
        "/people/me/interests",
        token=token,
        json={"interests": ["cafe", "nightlife"]},
    )
    after = {
        tag: created
        for tag, created in postgres_session.execute(
            select(PersonInterest.tag, PersonInterest.created_at).where(
                PersonInterest.person_id == person.id
            )
        )
    }
    assert set(after) == {"cafe", "nightlife"}
    assert after["cafe"] == before["cafe"]


def test_a_taste_needs_a_person(postgres_session):
    postgres_session.add(
        PersonInterest(id=uuid.uuid4(), person_id=uuid.uuid4(), tag="cafe")
    )
    with pytest.raises(IntegrityError):
        postgres_session.flush()
    postgres_session.rollback()


def test_a_blank_tag_is_refused_by_the_check(postgres_session):
    person = _person(postgres_session)
    postgres_session.add(
        PersonInterest(id=uuid.uuid4(), person_id=person.id, tag="   ")
    )
    with pytest.raises(IntegrityError):
        postgres_session.flush()
    postgres_session.rollback()


def test_two_people_keep_their_own_answers(postgres_session):
    """The table is keyed by person, and the read is scoped by the session --
    not by anything the caller sends."""

    mine = _person(postgres_session, "Tôi")
    theirs = _person(postgres_session, "Người kia")
    app = _prod_app(postgres_session)
    _call(
        app,
        "PUT",
        "/people/me/interests",
        token=_token(postgres_session, mine),
        json={"interests": ["cafe"], "budget_band": "tiet-kiem"},
    )
    _call(
        app,
        "PUT",
        "/people/me/interests",
        token=_token(postgres_session, theirs),
        json={"interests": ["nightlife", "game"], "budget_band": "thoai-mai"},
    )

    first = _call(app, "GET", "/people/me", token=_token(postgres_session, mine)).json()
    second = _call(
        app, "GET", "/people/me", token=_token(postgres_session, theirs)
    ).json()
    assert first["interests"] == ["cafe"] and first["budget_band"] == "tiet-kiem"
    assert second["interests"] == ["nightlife", "game"]
    assert second["budget_band"] == "thoai-mai"


def test_the_vocabulary_route_needs_no_session(postgres_session):
    app = _prod_app(postgres_session)
    response = _call(app, "GET", "/interests")
    assert response.status_code == 200, response.text
    assert response.json()["interests"][0]["id"] == "an-uong"
