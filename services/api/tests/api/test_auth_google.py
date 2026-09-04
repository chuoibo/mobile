"""The Google door against the fake repository, in `prod` auth mode (ADR-0016).

The verifier is a table: a token is either a row of claims or invalid. That is
the seam the real `GoogleAuthLibraryVerifier` fills with cryptography, and it
lets these cases say exactly what the ROUTE and SERVICE guarantee -- which is
the part that would silently rot if the library were mocked deeper down.

Nothing here spells an e-mail address into a claim the service can read: the
claims type has no such field, and the test that proves two `sub`s are two
people is the test that keeps it that way.
"""

from __future__ import annotations

import uuid

import pytest

from app.api.deps import get_repository
from app.api.google_identity import (
    CLIENT_IDS_ENV,
    GoogleAuthLibraryVerifier,
    GoogleClaims,
    GoogleTokenInvalid,
    build_google_verifier,
    claims_from,
)
from app.api.main import create_app
from app.api.person_identity import KEY_ENV_VAR

from .conftest import ASGITestClient

KEY = "google-route-test-key-for-person-id-derivation"
IDS = frozenset({"web-client-id.apps.googleusercontent.com", "android-client-id"})


class TableVerifier:
    def __init__(self, table: dict[str, GoogleClaims]):
        self.table = table
        self.calls = 0

    def verify(self, id_token: str) -> GoogleClaims:
        self.calls += 1
        try:
            return self.table[id_token]
        except KeyError as missing:
            raise GoogleTokenInvalid("not a token this test issued") from missing


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv(KEY_ENV_VAR, KEY)


@pytest.fixture
def verifier():
    return TableVerifier(
        {
            "tok-an": GoogleClaims(subject="sub-an", display_name="An Nguyen"),
            "tok-an-lai": GoogleClaims(subject="sub-an", display_name="An Nguyen"),
            "tok-binh": GoogleClaims(subject="sub-binh", display_name=None),
        }
    )


def _client(repository, verifier):
    app = create_app(auth_mode="prod")
    app.dependency_overrides[get_repository] = lambda: repository
    app.state.google_verifier = verifier
    return ASGITestClient(app)


@pytest.fixture
def prod_client(repository, verifier):
    return _client(repository, verifier)


def _login(client, token):
    return client.post("/auth/google", json={"id_token": token})


def test_a_vouched_token_buys_a_session_for_a_new_person(prod_client, repository):
    response = _login(prod_client, "tok-an")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["issued_via"] == "google"
    assert body["is_new_person"] is True
    assert body["profile"]["display_name"] == "An Nguyen"
    assert body["contexts"] == []
    assert body["context_id"] is None and body["membership_id"] is None
    # The bearer is real: a route behind `get_actor` answers as this person.
    mine = prod_client.get(
        "/people/me/contexts", headers={"Authorization": f"Bearer {body['token']}"}
    )
    assert mine.status_code == 200, mine.text
    # And the proof is bound once, to that person.
    bound = repository.account_identities[("google", "sub-an")]
    assert bound.person_id == uuid.UUID(body["person_id"])


def test_the_same_sub_signs_in_to_the_same_person_and_is_not_new_twice(
    prod_client, repository
):
    first = _login(prod_client, "tok-an").json()
    second = _login(prod_client, "tok-an-lai").json()
    assert second["person_id"] == first["person_id"]
    assert second["is_new_person"] is False
    assert second["token"] != first["token"]
    assert len([k for k in repository.account_identities if k[0] == "google"]) == 1


def test_two_subs_are_two_people_whatever_google_says_about_their_mail(prod_client):
    an = _login(prod_client, "tok-an").json()
    binh = _login(prod_client, "tok-binh").json()
    assert an["person_id"] != binh["person_id"]
    # A token without a name still makes a person, named the neutral way.
    assert binh["profile"]["display_name"] == "Thành viên mới"


def test_claims_carry_no_email_so_the_service_cannot_merge_by_it():
    payload = {
        "aud": "android-client-id",
        "iss": "https://accounts.google.com",
        "sub": "sub-x",
        "email": "khong-bao-gio-duoc-doc",
        "email_verified": True,
        "name": "  X  ",
    }
    claims = claims_from(payload, IDS)
    assert claims == GoogleClaims(subject="sub-x", display_name="X")
    assert not hasattr(claims, "email")


def test_an_unvouched_token_is_one_401_and_creates_nothing(prod_client, repository):
    response = _login(prod_client, "tok-gia")
    assert response.status_code == 401
    assert response.json()["code"] == "google_token_invalid"
    assert repository.account_identities == {}
    assert repository.account_sessions == {}
    assert "tok-gia" not in response.text


def test_a_host_without_client_ids_refuses_before_looking_at_the_token(
    repository, verifier
):
    client = _client(repository, None)
    response = _login(client, "tok-an")
    assert response.status_code == 503
    assert response.json()["code"] == "google_not_configured"
    assert verifier.calls == 0
    assert repository.account_sessions == {}


def test_a_missing_or_blank_token_is_422_without_an_echo(prod_client, verifier):
    for body in ({}, {"id_token": "   "}, {"id_token": 5}):
        response = prod_client.post("/auth/google", json=body)
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "id_token_required"
    assert verifier.calls == 0


def test_the_response_never_carries_the_token_or_the_subject(prod_client):
    response = _login(prod_client, "tok-an")
    assert "tok-an" not in response.text
    assert "sub-an" not in response.text
    assert "sub" not in response.json()


def test_the_door_is_rate_limited_per_caller(prod_client):
    codes = [_login(prod_client, "tok-gia").status_code for _ in range(11)]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


def test_claims_from_refuses_the_wrong_audience_issuer_or_no_subject():
    good = {"aud": "android-client-id", "iss": "accounts.google.com", "sub": "s"}
    assert claims_from(good, IDS).subject == "s"
    with pytest.raises(GoogleTokenInvalid):
        claims_from({**good, "aud": "somebody-elses-client"}, IDS)
    with pytest.raises(GoogleTokenInvalid):
        claims_from({**good, "iss": "https://evil.example"}, IDS)
    with pytest.raises(GoogleTokenInvalid):
        claims_from({**good, "sub": ""}, IDS)
    with pytest.raises(GoogleTokenInvalid):
        claims_from({k: v for k, v in good.items() if k != "sub"}, IDS)
    # Either spelling of Google's issuer is Google.
    assert (
        claims_from({**good, "iss": "https://accounts.google.com"}, IDS).subject == "s"
    )


def test_build_google_verifier_is_none_without_ids_and_a_set_with_them(monkeypatch):
    assert build_google_verifier({}) is None
    assert build_google_verifier({CLIENT_IDS_ENV: "  , "}) is None
    built = build_google_verifier({CLIENT_IDS_ENV: " a.apps , b "})
    assert isinstance(built, GoogleAuthLibraryVerifier)
    assert built.client_ids == frozenset({"a.apps", "b"})
    with pytest.raises(ValueError):
        GoogleAuthLibraryVerifier(frozenset())


def test_the_real_verifier_refuses_a_malformed_token_without_the_network():
    # `google-auth` rejects a token that is not three segments before it fetches
    # any certificate, so this runs offline -- and it is the shape the route
    # sees when a client sends garbage.
    with pytest.raises(GoogleTokenInvalid):
        GoogleAuthLibraryVerifier(IDS).verify("khong-phai-token")


def test_create_app_reads_the_client_ids_from_the_environment(monkeypatch):
    monkeypatch.delenv(CLIENT_IDS_ENV, raising=False)
    assert create_app(auth_mode="prod").state.google_verifier is None
    monkeypatch.setenv(CLIENT_IDS_ENV, "android-client-id")
    configured = create_app(auth_mode="prod").state.google_verifier
    assert isinstance(configured, GoogleAuthLibraryVerifier)
