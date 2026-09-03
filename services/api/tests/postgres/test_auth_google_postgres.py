"""The Google door on the real repository, real HTTP, `prod` auth mode.

What only PostgreSQL can show: one `people` row plus one `account_identities`
row plus one `account_sessions` row with `issued_via = 'google'` per first
login; a second login on the same `sub` refreshes the binding instead of
duplicating it; the unique index refuses a second binding of one `sub`; and a
phone-born person and a Google-born person stay two people even when the
display names match -- the schema has nothing to merge them by.
"""

from __future__ import annotations

import uuid

import anyio
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.google_identity import GoogleClaims, GoogleTokenInvalid
from app.api.main import create_app
from app.api.person_identity import KEY_ENV_VAR
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import AccountIdentity, AccountSession, Person

pytestmark = pytest.mark.postgres

KEY = "google-postgres-test-key-for-person-id-derivation"
PHONE = "0912" + "345678"


class TableVerifier:
    def __init__(self, table):
        self.table = table

    def verify(self, id_token):
        try:
            return self.table[id_token]
        except KeyError as missing:
            raise GoogleTokenInvalid("not issued by this test") from missing


class RecordingSender:
    def __init__(self):
        self.sent = []

    def send_otp(self, *, canonical_phone, code, challenge_id):
        del canonical_phone
        self.sent.append((code, challenge_id))


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv(KEY_ENV_VAR, KEY)


def _app(session: Session, verifier, sender=None):
    app = create_app(auth_mode="prod")
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    app.state.google_verifier = verifier
    app.state.sms_sender = sender or RecordingSender()
    app.state.otp_debug_code = None
    return app


def _call(app, method, path, *, json=None, token=None):
    async def go():
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.request(method, path, json=json, headers=headers)

    return anyio.run(go)


def _verifier():
    return TableVerifier(
        {
            "tok-an": GoogleClaims(subject="sub-an", display_name="An Nguyen"),
            "tok-an-2": GoogleClaims(subject="sub-an", display_name="An Nguyen"),
            "tok-an-dien-thoai": GoogleClaims(
                subject="sub-an-google", display_name="Thành viên mới"
            ),
        }
    )


def test_a_first_login_writes_one_person_one_binding_one_google_session(
    postgres_session,
):
    app = _app(postgres_session, _verifier())
    response = _call(app, "POST", "/auth/google", json={"id_token": "tok-an"})
    assert response.status_code == 201, response.text
    body = response.json()
    person_id = uuid.UUID(body["person_id"])

    person = postgres_session.get(Person, person_id)
    assert person is not None and person.display_name == "An Nguyen"
    bindings = postgres_session.scalars(
        select(AccountIdentity).where(AccountIdentity.provider == "google")
    ).all()
    assert [(b.person_id, b.subject) for b in bindings] == [(person_id, "sub-an")]
    sessions = postgres_session.scalars(
        select(AccountSession).where(AccountSession.person_id == person_id)
    ).all()
    assert [s.issued_via for s in sessions] == ["google"]
    assert all(s.issued_from_invite_id is None for s in sessions)
    # The bearer is real on the real repository too.
    mine = _call(app, "GET", "/people/me/contexts", token=body["token"])
    assert mine.status_code == 200 and mine.json()["contexts"] == []


def test_a_second_login_on_the_same_sub_refreshes_the_binding_not_the_person(
    postgres_session,
):
    app = _app(postgres_session, _verifier())
    first = _call(app, "POST", "/auth/google", json={"id_token": "tok-an"}).json()
    binding_before = postgres_session.scalar(
        select(AccountIdentity).where(AccountIdentity.subject == "sub-an")
    )
    seen_first = binding_before.last_login_at

    second = _call(app, "POST", "/auth/google", json={"id_token": "tok-an-2"}).json()
    assert second["person_id"] == first["person_id"]
    assert second["is_new_person"] is False
    postgres_session.expire_all()
    bindings = postgres_session.scalars(
        select(AccountIdentity).where(AccountIdentity.subject == "sub-an")
    ).all()
    assert len(bindings) == 1
    assert bindings[0].last_login_at >= seen_first
    sessions = postgres_session.scalars(
        select(AccountSession).where(
            AccountSession.person_id == uuid.UUID(first["person_id"])
        )
    ).all()
    assert len(sessions) == 2 and {s.issued_via for s in sessions} == {"google"}


def test_the_database_refuses_binding_one_sub_to_a_second_person(postgres_session):
    app = _app(postgres_session, _verifier())
    _call(app, "POST", "/auth/google", json={"id_token": "tok-an"})
    other = Person(id=uuid.uuid4(), display_name="Ke gia")
    postgres_session.add(other)
    postgres_session.flush()
    postgres_session.add(
        AccountIdentity(
            person_id=other.id,
            provider="google",
            subject="sub-an",
            last_login_at=postgres_session.scalar(
                select(AccountIdentity.last_login_at).where(
                    AccountIdentity.subject == "sub-an"
                )
            ),
        )
    )
    with pytest.raises(IntegrityError):
        postgres_session.flush()
    postgres_session.rollback()


def test_a_phone_person_and_a_google_person_stay_two_people(postgres_session):
    sender = RecordingSender()
    app = _app(postgres_session, _verifier(), sender)
    requested = _call(app, "POST", "/auth/otp/request", json={"phone": PHONE})
    assert requested.status_code == 202, requested.text
    code, challenge_id = sender.sent[-1]
    by_phone = _call(
        app,
        "POST",
        "/auth/otp/verify",
        json={"challenge_id": str(challenge_id), "phone": PHONE, "code": code},
    ).json()
    by_google = _call(
        app, "POST", "/auth/google", json={"id_token": "tok-an-dien-thoai"}
    ).json()

    # Same display name, different doors: two rows. Linking them is a consented
    # flow ADR-0016 leaves for later, not something a matching name may do.
    assert by_phone["profile"]["display_name"] == by_google["profile"]["display_name"]
    assert by_phone["person_id"] != by_google["person_id"]
    providers = sorted(postgres_session.scalars(select(AccountIdentity.provider)).all())
    assert providers == ["google", "phone"]
