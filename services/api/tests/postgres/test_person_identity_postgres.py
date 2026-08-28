"""The identity table, reached over HTTP, against a real PostgreSQL server.

Two failures live here, and they are the same failure seen from both ends.

`contexts.created_by_id` and `memberships.person_id` are foreign keys into
`people`, and no route ever wrote that table. So `POST /contexts` answered HTTP
500 -- `ForeignKeyViolation` on `fk_contexts_created_by` -- for every caller,
including a correct one. There was no request an app could send that would have
worked, because the row the constraint wants had no way in.

From the other end: `get_guest_envelope` never read `people` either, so the
guest page said "Phần của a5b2c277-9b99-4699-a875-ed324e886237". The two things
that page exists to say are who is asking and which debt this is, and a machine
id says neither.

These run against PostgreSQL because both halves are database facts. The fake
repository has no foreign keys, so it cannot produce the 500; and a join it
does not perform cannot be proved by a dictionary lookup it does.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import anyio
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_repository
from app.api.errors import ApiProblem
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.api.schemas import ContextCreateRequest, MembershipInviteRequest
from app.api.service import ApiService
from app.db.models import Context, Person

from .test_repository_postgres import NOW, _persist_lifecycle

pytestmark = pytest.mark.postgres


def _actor(person_id: uuid.UUID) -> Actor:
    return Actor(
        id=person_id,
        roles=frozenset({"member", "group_admin"}),
        context_ids=frozenset(),
    )


def _service(session: Session) -> ApiService:
    return ApiService(SqlAlchemyApiRepository(session))


def _http(session: Session, monkeypatch: pytest.MonkeyPatch):
    """Drive real HTTP into this session's transaction.

    Copied in shape from the bank-recipient route tests: the API layer proves
    wiring against a fake and the repository tests prove the SQL, and neither
    proves that a route and this schema agree.
    """

    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def test_registering_a_name_then_opening_a_group_works_over_http(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The acceptance criterion: an app with nothing but an actor id can now
    reach a created group. Before this route the same two requests were a 500,
    and no third request existed that would have helped."""
    person_id = uuid.uuid4()
    app = _http(postgres_session, monkeypatch)
    headers = {"X-Actor-ID": str(person_id), "X-Actor-Roles": "member,group_admin"}

    async def exchange():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            registered = await client.put(
                f"/people/{person_id}",
                headers=headers,
                json={"display_name": "Nam"},
            )
            opened = await client.post(
                "/contexts",
                headers=headers,
                json={"display_name": "Hội bạn thân"},
            )
            return registered, opened

    registered, opened = anyio.run(exchange)

    assert registered.status_code == 201, registered.text
    assert registered.json()["display_name"] == "Nam"
    assert registered.json()["id"] == str(person_id)
    assert opened.status_code == 201, opened.text

    # In the table, not only in the response body.
    stored = postgres_session.get(Person, person_id)
    assert stored is not None and stored.display_name == "Nam"
    context = postgres_session.scalar(
        select(Context).where(Context.created_by_id == person_id)
    )
    assert context is not None and context.display_name == "Hội bạn thân"


def test_opening_a_group_without_an_identity_is_refused_not_a_crash(
    postgres_session: Session,
):
    """The reported 500. A foreign key rejecting a row is the database doing
    its job; letting that reach the caller as a stack trace is not. The answer
    has to name what is missing, because the caller can fix it."""
    service = _service(postgres_session)
    stranger = uuid.uuid4()

    with pytest.raises(ApiProblem) as raised:
        service.create_context(
            ContextCreateRequest(display_name="Hội bạn thân"), _actor(stranger)
        )

    assert raised.value.status_code == 409
    assert raised.value.code == "person_not_registered"
    # Nothing half-written: a refused group leaves no row behind.
    assert postgres_session.scalar(
        select(Context).where(Context.created_by_id == stranger)
    ) is None


def test_inviting_somebody_who_was_never_named_is_refused_not_a_crash(
    postgres_session: Session,
):
    """`memberships.person_id` is the same foreign key one table over, so it
    was the same 500 waiting behind `POST /contexts/{id}/members`."""
    owner = uuid.uuid4()
    service = _service(postgres_session)
    service.register_person(owner, "Nam", _actor(owner))
    context = service.create_context(
        ContextCreateRequest(display_name="Hội bạn thân"), _actor(owner)
    )

    with pytest.raises(ApiProblem) as raised:
        service.invite_context_member(
            context.id,
            MembershipInviteRequest(person_id=uuid.uuid4()),
            _actor(owner),
        )

    assert raised.value.status_code == 409
    assert raised.value.code == "person_not_registered"


def test_one_member_may_name_a_friend_who_has_no_row_yet(postgres_session: Session):
    """This is how a name enters the system at all. Nobody in this product
    signs up before their friend adds them to a dinner; the organiser types
    "Quyên" on their own phone, and that has to be allowed or the group can
    never be built."""
    organiser = uuid.uuid4()
    friend = uuid.uuid4()
    service = _service(postgres_session)

    record, created = service.register_person(friend, "Quyên", _actor(organiser))

    assert created is True
    assert record.display_name == "Quyên"
    assert postgres_session.get(Person, friend).display_name == "Quyên"


def test_a_second_member_may_not_rename_somebody_who_already_has_a_name(
    postgres_session: Session,
):
    """A display name is what a stranger reads on a guest page while deciding
    whether to send money. Letting any member overwrite another person's name
    would let one member change who the page appears to be from."""
    friend = uuid.uuid4()
    service = _service(postgres_session)
    service.register_person(friend, "Quyên", _actor(uuid.uuid4()))

    with pytest.raises(ApiProblem) as raised:
        service.register_person(friend, "Kẻ giả danh", _actor(uuid.uuid4()))

    assert raised.value.status_code == 403
    assert postgres_session.get(Person, friend).display_name == "Quyên"


def test_a_person_may_rename_themselves(postgres_session: Session):
    person = uuid.uuid4()
    service = _service(postgres_session)
    service.register_person(person, "Quyên", _actor(uuid.uuid4()))

    record, created = service.register_person(person, "Quyên Nguyễn", _actor(person))

    assert created is False
    assert record.display_name == "Quyên Nguyễn"


def test_re_sending_the_same_name_is_not_a_rename(postgres_session: Session):
    """A retried request is not an attempt to change anything, and answering
    403 to a retry would make the client's own retry look like an attack."""
    friend = uuid.uuid4()
    service = _service(postgres_session)
    service.register_person(friend, "Quyên", _actor(uuid.uuid4()))

    record, created = service.register_person(friend, "Quyên", _actor(uuid.uuid4()))

    assert created is False
    assert record.id == friend
    assert record.display_name == "Quyên"


def test_guest_envelope_names_the_people_instead_of_printing_their_ids(
    postgres_session: Session,
):
    """The reported symptom, at the layer that produced it.

    `app/web/guest_view.py` is a pure function and the template may not query;
    whatever the repository puts in these two fields is what the reader sees.
    It was putting `str(uuid)` in both."""
    state = _persist_lifecycle(postgres_session)
    postgres_session.add_all(
        [
            Person(id=state.owner_id, display_name="Nam"),
            Person(id=state.sender_id, display_name="Quyên"),
        ]
    )
    postgres_session.flush()

    repository = SqlAlchemyApiRepository(postgres_session)
    envelope = repository.get_guest_envelope(
        state.token_digest, NOW + timedelta(minutes=10)
    )

    assert envelope is not None
    assert envelope.envelope["recorded_by_display_name"] == "Nam"
    assert envelope.envelope["claimed_person_display_name"] == "Quyên"


def test_guest_envelope_falls_back_to_the_id_when_nobody_named_the_person(
    postgres_session: Session,
):
    """Deliberately still an id, and deliberately not a friendly placeholder.

    Hiding a missing name behind "Thành viên" makes two different people read
    as one, on the one screen whose whole job is telling them apart."""
    state = _persist_lifecycle(postgres_session)

    repository = SqlAlchemyApiRepository(postgres_session)
    envelope = repository.get_guest_envelope(
        state.token_digest, NOW + timedelta(minutes=10)
    )

    assert envelope is not None
    assert envelope.envelope["recorded_by_display_name"] == str(state.owner_id)
    assert envelope.envelope["claimed_person_display_name"] == str(state.sender_id)
