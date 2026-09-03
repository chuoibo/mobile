"""What `prod` refuses, and where the identity comes from instead.

The suite everywhere else runs in `dev`, where `X-Actor-*` still works. These
cases build their applications with `auth_mode="prod"` explicitly, so nothing
here can pass because of the environment the rest of the suite exports.

The sharp case is `test_a_session_beats_a_forged_header`: the request carries a
valid session for one person **and** headers naming a different person with
better roles. Under the adapter this replaces, the headers won.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import anyio
import pytest

from app.api.deps import get_actor, get_repository
from app.api.errors import ApiProblem
from app.api.main import create_app
from app.api.repository import ContextRecord, PersonRecord
from app.api.service import token_digest

from .conftest import ASGITestClient
from .helpers import ADVANCER_ID, CONTEXT_ID, OTHER_ID, actor_headers

CREATED_AT = datetime(2030, 8, 27, 12, tzinfo=UTC)


def _seed_person(repository, person_id, display_name="Minh Anh"):
    repository.people[person_id] = PersonRecord(
        id=person_id, display_name=display_name, created_at=CREATED_AT
    )


def _seed_context(repository):
    repository.contexts[CONTEXT_ID] = ContextRecord(
        id=CONTEXT_ID,
        display_name="Hội đi Đà Lạt",
        created_by_id=ADVANCER_ID,
        created_at=CREATED_AT,
    )


def _grant_session(repository, person_id, *, lifetime=timedelta(days=1), revoked=False):
    """Put a live session in the fake and hand back its raw token.

    Real clock, not a frozen one: the service compares against
    `datetime.now(UTC)`, and a fixture dated 2030 would make every session in
    this file expired for reasons that have nothing to do with what is being
    measured.
    """

    raw = f"session-{uuid.uuid4().hex}"
    now = datetime.now(UTC)
    record = repository.create_account_session(
        person_id=person_id,
        token_digest=token_digest(raw),
        issued_from_invite_id=None,
        expires_at=now + lifetime,
        now=now,
    )
    if revoked:
        repository.revoke_account_session(session_id=record.id, now=now)
    return raw


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def prod_client(repository, monkeypatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    app = create_app(auth_mode="prod")
    app.dependency_overrides[get_repository] = lambda: repository
    return ASGITestClient(app)


def _request(repository, *, mode, authorization=None, **headers):
    """Call the dependency itself, with an application that is only a mode.

    Going through the dependency rather than a route is what makes the role
    assertions possible: no route in the product reaches an action that needs
    `platform_moderator`, so the only way to show the header cannot grant it is
    to look at the `Actor` that comes out.
    """

    return get_actor(
        request=SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(auth_mode=mode))
        ),
        repository=repository,
        authorization=authorization,
        **headers,
    )


class TestProdRefusesWhatItCannotVerify:
    def test_a_forged_header_alone_is_401(self, prod_client, repository):
        _seed_context(repository)
        repository.active_memberships.add((CONTEXT_ID, ADVANCER_ID))

        response = prod_client.get(f"/contexts/{CONTEXT_ID}", headers=actor_headers())

        assert response.status_code == 401
        assert response.json()["code"] == "authentication_required"

    def test_a_request_with_nothing_at_all_is_401(self, prod_client, repository):
        _seed_context(repository)

        assert prod_client.get(f"/contexts/{CONTEXT_ID}").status_code == 401

    def test_an_unknown_bearer_is_401(self, prod_client, repository):
        _seed_context(repository)

        response = prod_client.get(
            f"/contexts/{CONTEXT_ID}", headers=_bearer("not-a-session")
        )

        assert response.status_code == 401

    def test_a_malformed_authorization_header_is_401(self, prod_client, repository):
        _seed_context(repository)
        token = _grant_session(repository, ADVANCER_ID)
        _seed_person(repository, ADVANCER_ID)

        for value in ("", "Bearer", "Bearer ", token, f"Basic {token}"):
            response = prod_client.get(
                f"/contexts/{CONTEXT_ID}", headers={"Authorization": value}
            )
            assert response.status_code == 401, value

    def test_an_expired_session_is_401(self, prod_client, repository):
        _seed_context(repository)
        _seed_person(repository, ADVANCER_ID)
        repository.active_memberships.add((CONTEXT_ID, ADVANCER_ID))
        token = _grant_session(repository, ADVANCER_ID, lifetime=-timedelta(seconds=1))

        response = prod_client.get(f"/contexts/{CONTEXT_ID}", headers=_bearer(token))

        assert response.status_code == 401

    def test_a_revoked_session_is_401(self, prod_client, repository):
        _seed_context(repository)
        _seed_person(repository, ADVANCER_ID)
        repository.active_memberships.add((CONTEXT_ID, ADVANCER_ID))
        token = _grant_session(repository, ADVANCER_ID, revoked=True)

        response = prod_client.get(f"/contexts/{CONTEXT_ID}", headers=_bearer(token))

        assert response.status_code == 401

    def test_a_session_whose_person_is_gone_is_401(self, prod_client, repository):
        # The row in `people` is what `actor_grants` reads. A session pointing
        # at nobody must not become an actor with no roles; it must not
        # authenticate at all.
        _seed_context(repository)
        token = _grant_session(repository, ADVANCER_ID)

        response = prod_client.get(f"/contexts/{CONTEXT_ID}", headers=_bearer(token))

        assert response.status_code == 401


class TestProdAnswersAValidSession:
    def test_a_member_with_a_session_and_no_headers_is_served(
        self, prod_client, repository
    ):
        _seed_context(repository)
        _seed_person(repository, ADVANCER_ID)
        repository.active_memberships.add((CONTEXT_ID, ADVANCER_ID))
        token = _grant_session(repository, ADVANCER_ID)

        response = prod_client.get(f"/contexts/{CONTEXT_ID}", headers=_bearer(token))

        assert response.status_code == 200
        assert response.json()["id"] == str(CONTEXT_ID)

    def test_a_session_beats_a_forged_header(self, prod_client, repository):
        """The case the whole change exists for.

        `OTHER_ID` is the outsider this suite uses everywhere. Their session is
        real; the headers claim to be a member. If the headers were still read,
        this would be 200.
        """

        _seed_context(repository)
        _seed_person(repository, OTHER_ID, display_name="Người lạ")
        repository.active_memberships.add((CONTEXT_ID, ADVANCER_ID))
        token = _grant_session(repository, OTHER_ID)

        response = prod_client.get(
            f"/contexts/{CONTEXT_ID}",
            headers={**actor_headers(), **_bearer(token)},
        )

        assert response.status_code == 403


class TestWhereRolesComeFrom:
    def test_headers_cannot_add_a_role(self, repository):
        _seed_person(repository, ADVANCER_ID)
        repository.active_memberships.add((CONTEXT_ID, ADVANCER_ID))
        token = _grant_session(repository, ADVANCER_ID)

        actor = _request(
            repository,
            mode="prod",
            authorization=f"Bearer {token}",
            actor_id=str(OTHER_ID),
            actor_roles="platform_moderator,group_admin,guest",
            actor_contexts=str(uuid.uuid4()),
        )

        assert actor.id == ADVANCER_ID
        # Not granted by any session: its three actions carry no predicate at
        # all, and nothing says who holds it.
        assert "platform_moderator" not in actor.roles
        # Not an admin of anything in the fake's roster, whatever the header says.
        assert "group_admin" not in actor.roles
        # A person is not a guest. That subject is a capability digest.
        assert "guest" not in actor.roles
        # And the contexts are the roster's, not the header's.
        assert actor.context_ids == frozenset({CONTEXT_ID})

    def test_the_capability_roles_are_granted_so_the_product_still_works(
        self, repository
    ):
        # Every action naming these also proves a predicate from the resource
        # (`is_recipient_of_this_obligation` and friends), so carrying them is
        # worth no more than the right to be asked the real question -- and
        # withholding them would 403 every receipt confirmation in the product.
        _seed_person(repository, ADVANCER_ID)
        token = _grant_session(repository, ADVANCER_ID)

        actor = _request(repository, mode="prod", authorization=f"Bearer {token}")

        assert {"member", "advancer", "recipient", "sender", "creditor"} <= actor.roles

    def test_a_session_never_carries_group_admin(self, repository):
        """Being an admin is a fact about one group, so it cannot ride along.

        A flat set of roles has nowhere to say *which* group it means. The
        version that granted it here let an admin of one group act as an admin
        in every group they belonged to -- `invite_context_member` asks for
        `is_group_member`, not `is_group_admin`, so the role was the whole of
        the check. `ApiService._group_admin_role` derives it per call instead.
        """

        _seed_person(repository, ADVANCER_ID)
        repository.active_memberships.add((CONTEXT_ID, ADVANCER_ID))
        repository.admin_memberships.add((CONTEXT_ID, ADVANCER_ID))
        token = _grant_session(repository, ADVANCER_ID)

        actor = _request(repository, mode="prod", authorization=f"Bearer {token}")

        assert "group_admin" not in actor.roles

    def test_dev_still_reads_the_headers(self, repository):
        # The contrast that makes the cases above mean something: same call,
        # same fake, other mode.
        actor = _request(
            repository,
            mode="dev",
            actor_id=str(OTHER_ID),
            actor_roles="group_admin",
            actor_contexts=str(CONTEXT_ID),
        )

        assert actor.id == OTHER_ID
        assert actor.roles == frozenset({"group_admin"})

    def test_prod_refuses_even_when_the_headers_are_well_formed(self, repository):
        with pytest.raises(ApiProblem) as raised:
            _request(
                repository,
                mode="prod",
                actor_id=str(ADVANCER_ID),
                actor_roles="member",
                actor_contexts=str(CONTEXT_ID),
            )
        assert raised.value.status_code == 401
