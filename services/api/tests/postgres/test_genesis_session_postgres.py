"""`scripts/genesis_session.py` against a real schema.

The script is the only way into a fresh `prod` host, so "it probably works" is
not good enough: if it is broken, the product is unenterable and the failure
shows up on the day of a deployment rather than in CI.

It runs against the isolated schema this layer already migrates, by being
handed that schema's own URL. Nothing here touches a shared database.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api.repository import SqlAlchemyApiRepository
from app.api.service import ApiService, token_digest
from app.db.models import (
    AccountSession,
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    Person,
)

pytestmark = pytest.mark.postgres

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "genesis_session.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("genesis_session", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _token_from(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    marker = next(index for index, line in enumerate(lines) if "Bearer token" in line)
    return lines[marker + 1]


def _run(engine: Engine, capsys, **overrides) -> str:
    module = _load_script()
    argv = [
        "--display-name",
        overrides.get("display_name", "Minh Anh"),
        "--group",
        overrides.get("group", "Nhóm đầu tiên"),
        "--database-url",
        engine.url.render_as_string(hide_password=False),
    ]
    if "person_id" in overrides:
        argv += ["--person-id", str(overrides["person_id"])]
    assert module.main(argv) == 0
    return _token_from(capsys.readouterr().out)


def test_the_first_session_can_be_minted_without_http(
    postgres_engine: Engine, postgres_session: Session, capsys
):
    person_id = uuid.uuid4()

    token = _run(postgres_engine, capsys, person_id=person_id, group="Hội Đà Lạt")

    person = postgres_session.get(Person, person_id)
    assert person is not None
    assert person.display_name == "Minh Anh"

    context = postgres_session.scalar(
        select(Context).where(Context.display_name == "Hội Đà Lạt")
    )
    assert context is not None

    membership = postgres_session.scalar(
        select(Membership).where(
            Membership.context_id == context.id, Membership.person_id == person_id
        )
    )
    assert membership is not None
    # ACTIVE and admin, because this person has to be able to invite the next
    # one -- `invite_to_outing` proves `is_group_member` against exactly this.
    assert membership.state == MembershipState.ACTIVE
    assert membership.role == MembershipRole.ADMIN

    # And what was stored is a digest, not the credential printed to stdout.
    stored = postgres_session.scalar(
        select(AccountSession).where(AccountSession.person_id == person_id)
    )
    assert stored is not None
    assert stored.token_digest == token_digest(token)
    assert stored.issued_from_invite_id is None


def test_the_printed_token_authenticates_as_that_person(
    postgres_engine: Engine, postgres_session: Session, capsys
):
    person_id = uuid.uuid4()
    token = _run(postgres_engine, capsys, person_id=person_id, group="Hội Nha Trang")

    repository = SqlAlchemyApiRepository(postgres_session)
    actor = ApiService(repository).actor_for_session_token(token)

    assert actor.id == person_id
    assert actor.context_ids
    # Not on the session: `group_admin` is a fact about one group, derived per
    # call. What genesis has to leave behind is the row it is derived FROM --
    # without that, the first person cannot invite the second and the host is
    # still unenterable.
    assert "group_admin" not in actor.roles
    context_id = next(iter(actor.context_ids))
    assert repository.membership_role(context_id, person_id) == "admin"


def test_running_it_twice_adds_a_session_and_nothing_else(
    postgres_engine: Engine, postgres_session: Session, capsys
):
    """Signing in on a second device is not a second person.

    The person, the group and the membership are looked up before they are
    created, so an operator who runs this again on a half-seeded host does not
    end up with two groups of the same name and a member of neither.
    """

    person_id = uuid.uuid4()
    first = _run(postgres_engine, capsys, person_id=person_id, group="Hội Đà Nẵng")
    second = _run(postgres_engine, capsys, person_id=person_id, group="Hội Đà Nẵng")

    assert first != second

    people = list(
        postgres_session.scalars(select(Person).where(Person.id == person_id))
    )
    assert len(people) == 1
    contexts = list(
        postgres_session.scalars(
            select(Context).where(Context.display_name == "Hội Đà Nẵng")
        )
    )
    assert len(contexts) == 1
    memberships = list(
        postgres_session.scalars(
            select(Membership).where(Membership.person_id == person_id)
        )
    )
    assert len(memberships) == 1
    sessions = list(
        postgres_session.scalars(
            select(AccountSession).where(AccountSession.person_id == person_id)
        )
    )
    assert len(sessions) == 2

    repository = SqlAlchemyApiRepository(postgres_session)
    service = ApiService(repository)
    # Both devices stay signed in; the second run does not evict the first.
    assert service.actor_for_session_token(first).id == person_id
    assert service.actor_for_session_token(second).id == person_id
