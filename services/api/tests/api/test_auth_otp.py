"""The OTP doors against the fake repository, in `prod` auth mode.

`prod` on purpose: these routes are the way a phone gets its first bearer, and
a suite running in `dev` would let `X-Actor-*` stand in for what this proves.
The sender is a recording fake so a test can read the code the way a phone
would -- from the message -- rather than from the store.

No telephone number is spelled out whole anywhere here; the repo guard refuses
digit runs shaped like one, and it is right to.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.person_identity import (
    KEY_ENV_VAR,
    canonical_mobile,
    derive_code_digest,
    derive_person_id,
    derive_phone_digest,
)
from app.api.repository import PersonRecord
from app.api.sms import (
    DEBUG_CODE_ENV,
    GATEWAY_TOKEN_ENV,
    GATEWAY_URL_ENV,
    HttpJsonSmsSender,
    LogSmsSender,
    OtpConfigInvalid,
    SmsDeliveryError,
    build_sms_sender,
    resolve_otp_debug_code,
)

from .conftest import ASGITestClient

KEY = "otp-route-test-key-for-person-id-derivation"
PHONE = "0912" + "345678"
OTHER_PHONE = "0987" + "654321"
DIGITS = re.compile(r"\d{6,}")


class RecordingSender:
    def __init__(self, fail: bool = False):
        self.sent: list[tuple[str, str, uuid.UUID]] = []
        self.fail = fail

    def send_otp(self, *, canonical_phone, code, challenge_id):
        if self.fail:
            raise SmsDeliveryError("URLError")
        self.sent.append((canonical_phone, code, challenge_id))


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv(KEY_ENV_VAR, KEY)


@pytest.fixture
def sender():
    return RecordingSender()


@pytest.fixture
def prod_client(repository, sender, monkeypatch):
    import anyio

    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    app = create_app(auth_mode="prod")
    app.dependency_overrides[get_repository] = lambda: repository
    app.state.sms_sender = sender
    app.state.otp_debug_code = None
    return ASGITestClient(app)


def _request(client, phone=PHONE):
    return client.post("/auth/otp/request", json={"phone": phone})


def _verify(client, challenge_id, code, phone=PHONE):
    return client.post(
        "/auth/otp/verify",
        json={"challenge_id": str(challenge_id), "phone": phone, "code": code},
    )


def _login(client, sender, phone=PHONE):
    requested = _request(client, phone)
    assert requested.status_code == 202, requested.text
    _, code, challenge_id = sender.sent[-1]
    verified = _verify(client, challenge_id, code, phone)
    assert verified.status_code == 201, verified.text
    return verified.json()


def test_a_code_sent_to_the_phone_buys_a_session_the_server_accepts(
    prod_client, sender
):
    body = _login(prod_client, sender)
    assert body["issued_via"] == "otp"
    assert body["is_new_person"] is True
    assert body["profile"]["display_name"] == "Thành viên mới"
    assert body["contexts"] == []
    assert body["context_id"] is None and body["membership_id"] is None
    # The bearer is real: a route behind `get_actor` answers as this person.
    mine = prod_client.get(
        "/people/me/contexts", headers={"Authorization": f"Bearer {body['token']}"}
    )
    assert mine.status_code == 200, mine.text


def _let_the_cooldown_pass(repository):
    """Backdate every challenge so the next request is not a resend."""
    from dataclasses import replace

    for challenge_id, record in list(repository.otp_challenges.items()):
        repository.otp_challenges[challenge_id] = replace(
            record, created_at=record.created_at - timedelta(minutes=2)
        )


def test_the_same_number_signs_the_same_person_back_in(prod_client, sender, repository):
    first = _login(prod_client, sender)
    _let_the_cooldown_pass(repository)
    second = _login(prod_client, sender)
    assert first["person_id"] == second["person_id"]
    assert second["is_new_person"] is False
    assert len(repository.account_identities) == 1


def test_a_person_a_friend_named_by_phone_lands_in_their_own_row(
    prod_client, sender, repository
):
    canonical = canonical_mobile(PHONE)
    person_id = derive_person_id(canonical, KEY.encode())
    repository.people[person_id] = PersonRecord(
        id=person_id, display_name="Hà", created_at=datetime(2030, 8, 27, tzinfo=UTC)
    )
    body = _login(prod_client, sender)
    assert body["person_id"] == str(person_id)
    assert body["is_new_person"] is False
    assert body["profile"]["display_name"] == "Hà", "tên bạn đã đặt phải được giữ"


def test_no_response_ever_carries_the_number_or_the_code(prod_client, sender):
    requested = _request(prod_client)
    _, code, challenge_id = sender.sent[-1]
    wrong = _verify(
        prod_client, challenge_id, "000000" if code != "000000" else "111111"
    )
    verified = _verify(prod_client, challenge_id, code)
    canonical = canonical_mobile(PHONE)
    for response in (requested, wrong, verified):
        assert PHONE[1:] not in response.text and canonical not in response.text
    # The code is a secret between the phone and the server: the two answers
    # that precede a successful login must not repeat it.
    assert code not in requested.text and code not in wrong.text


def test_a_wrong_code_counts_down_and_the_fifth_burns_the_challenge(
    prod_client, sender
):
    _request(prod_client)
    _, code, challenge_id = sender.sent[-1]
    bad = "000000" if code != "000000" else "111111"
    statuses = [_verify(prod_client, challenge_id, bad) for _ in range(4)]
    assert [r.status_code for r in statuses] == [422, 422, 422, 422]
    assert "4" in statuses[0].json()["detail"] and "1" in statuses[3].json()["detail"]
    fifth = _verify(prod_client, challenge_id, bad)
    assert fifth.status_code == 429
    assert fifth.json()["code"] == "otp_too_many_attempts"
    # Even the right code is nothing now, and the answer is the same 404 as never.
    after = _verify(prod_client, challenge_id, code)
    assert after.status_code == 404
    assert after.json()["code"] == "otp_challenge_not_found"


def test_an_expired_challenge_is_not_found(prod_client, sender, repository):
    _request(prod_client)
    _, code, challenge_id = sender.sent[-1]
    record = repository.otp_challenges[challenge_id]
    from dataclasses import replace

    repository.otp_challenges[challenge_id] = replace(
        record, expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )
    assert _verify(prod_client, challenge_id, code).status_code == 404


def test_a_challenge_belongs_to_one_number(prod_client, sender):
    _request(prod_client)
    _, code, challenge_id = sender.sent[-1]
    response = _verify(prod_client, challenge_id, code, phone=OTHER_PHONE)
    assert response.status_code == 404, (
        "mã của số khác không được tồn tại với người này"
    )


def test_a_spent_code_cannot_be_spent_twice(prod_client, sender):
    _request(prod_client)
    _, code, challenge_id = sender.sent[-1]
    assert _verify(prod_client, challenge_id, code).status_code == 201
    assert _verify(prod_client, challenge_id, code).status_code == 404


def test_resend_inside_the_cooldown_is_refused_with_a_wait(prod_client, sender):
    assert _request(prod_client).status_code == 202
    again = _request(prod_client)
    assert again.status_code == 429
    assert again.json()["code"] == "otp_resend_too_soon"
    assert len(sender.sent) == 1, "không gửi thêm tin nhắn nào"


def test_a_phone_posted_as_a_number_is_refused_without_echo(prod_client):
    response = prod_client.post("/auth/otp/request", json={"phone": 912_345_678})
    assert response.status_code == 422
    assert response.json()["code"] == "phone_required"
    assert not DIGITS.search(response.text)


def test_without_the_identity_key_the_door_is_closed_not_open(prod_client, monkeypatch):
    monkeypatch.delenv(KEY_ENV_VAR)
    response = _request(prod_client)
    assert response.status_code == 503
    assert response.json()["code"] == "identity_key_missing"


def test_a_failed_delivery_burns_the_challenge_and_says_so(repository, monkeypatch):
    import anyio

    monkeypatch.setattr(anyio.to_thread, "run_sync", lambda f, *a, **k: _sync(f, *a))
    app = create_app(auth_mode="prod")
    app.dependency_overrides[get_repository] = lambda: repository
    app.state.sms_sender = RecordingSender(fail=True)
    app.state.otp_debug_code = None
    client = ASGITestClient(app)
    response = _request(client)
    assert response.status_code == 503
    assert response.json()["code"] == "sms_unavailable"
    assert all(r.consumed_at is not None for r in repository.otp_challenges.values())


async def _sync(function, *args):
    return function(*args)


def test_the_debug_code_is_what_every_challenge_carries(prod_client, sender):
    prod_client.app.state.otp_debug_code = "000000"
    _request(prod_client)
    assert sender.sent[-1][1] == "000000"
    _, _, challenge_id = sender.sent[-1]
    assert _verify(prod_client, challenge_id, "000000").status_code == 201


def test_the_stored_code_digest_is_salted_by_the_challenge(
    prod_client, sender, repository
):
    prod_client.app.state.otp_debug_code = "000000"
    _request(prod_client)
    _request(prod_client, OTHER_PHONE)
    (_, _, first), (_, _, second) = sender.sent[-2:]
    assert (
        repository.otp_challenges[first].code_digest
        != repository.otp_challenges[second].code_digest
    )
    assert repository.otp_challenges[first].code_digest == derive_code_digest(
        first, "000000", KEY.encode()
    )
    assert repository.otp_challenges[first].phone_digest == derive_phone_digest(
        canonical_mobile(PHONE), KEY.encode()
    )


def test_ten_requests_from_one_address_hit_the_per_caller_ceiling(prod_client, sender):
    seen = []
    for i in range(12):
        phone = "09" + f"{10 + i:02d}" + "000" + f"{i:03d}"
        seen.append(_request(prod_client, phone).status_code)
    assert seen.count(202) == 10 and seen[-1] == 429


def test_debug_code_beside_a_real_gateway_refuses_to_start():
    env = {
        GATEWAY_URL_ENV: "https://sms.example.test/send",
        GATEWAY_TOKEN_ENV: "t",
        DEBUG_CODE_ENV: "000000",
    }
    sender = build_sms_sender(env)
    assert isinstance(sender, HttpJsonSmsSender)
    with pytest.raises(OtpConfigInvalid):
        resolve_otp_debug_code(env, sender)


def test_debug_code_must_be_six_digits_and_is_none_when_unset():
    assert resolve_otp_debug_code({}, LogSmsSender()) is None
    with pytest.raises(OtpConfigInvalid):
        resolve_otp_debug_code({DEBUG_CODE_ENV: "abc"}, LogSmsSender())
    assert (
        resolve_otp_debug_code({DEBUG_CODE_ENV: "000000"}, LogSmsSender()) == "000000"
    )


def test_create_app_itself_refuses_the_dangerous_pairing(monkeypatch):
    monkeypatch.setenv(GATEWAY_URL_ENV, "https://sms.example.test/send")
    monkeypatch.setenv(GATEWAY_TOKEN_ENV, "t")
    monkeypatch.setenv(DEBUG_CODE_ENV, "000000")
    with pytest.raises(OtpConfigInvalid):
        create_app(auth_mode="prod")


def test_a_gateway_url_without_a_token_is_a_configuration_error():
    with pytest.raises(OtpConfigInvalid):
        build_sms_sender({GATEWAY_URL_ENV: "https://sms.example.test/send"})
