"""The HTTP surface that writes ``bank_recipients``.

Before this endpoint existed the vertical slice had a dead end: an advancer
could record and confirm an expense, then ``POST /batches`` answered 409
``advancer_bank_recipient_missing`` forever, because nothing in the HTTP
surface could ever write the row that clears the gate. The end-to-end test hid
the hole by inserting the row with raw SQL, so the suite was green precisely
where a real user was stuck.

``test_luong_day_du_khong_can_seed_sql`` is the reproduction: it walks the flow
with nothing but HTTP calls. It fails on any build where the write route is
missing.
"""

from __future__ import annotations

import uuid

from .helpers import (
    ADVANCER_ID,
    CONTEXT_ID,
    OTHER_ID,
    actor_headers,
    propose_and_confirm,
)

VALID_ACCOUNT = {
    # Synthetic. Not a real bank, not a real account.
    "bank_bin": "970415",
    "account_number": "0000000000TEST",
    "account_name": "NGUYEN VAN NAM",
}


def set_account(client, person_id=ADVANCER_ID, actor_id=None, **overrides):
    payload = {**VALID_ACCOUNT, **overrides}
    return client.put(
        f"/people/{person_id}/bank-recipient",
        headers=actor_headers(actor_id=actor_id or person_id),
        json=payload,
    )


def test_luong_day_du_khong_can_seed_sql(client):
    """Repro: expense -> confirm -> set account -> batch, over HTTP only.

    No fixture touches ``repository.bank_recipients``. If the route that writes
    the row is missing, ``PUT`` is 405/404 and ``POST /batches`` is 409.
    """
    confirmed = propose_and_confirm(client)

    saved = set_account(client)
    assert saved.status_code == 200, saved.text

    batch = client.post(
        "/batches",
        headers=actor_headers(),
        json={
            "context_id": str(CONTEXT_ID),
            "expense_version_ids": [confirmed["expense_version_id"]],
            "due_at": "2030-09-27T12:00:00+07:00",
        },
    )
    assert batch.status_code == 201, batch.text
    assert batch.json()["obligations"], batch.text


def test_luu_xong_doc_lai_duoc(client):
    assert set_account(client).status_code == 200

    read = client.get(
        f"/people/{ADVANCER_ID}/bank-recipient",
        headers=actor_headers(),
    )
    assert read.status_code == 200, read.text
    body = read.json()
    assert body["recipient_id"] == str(ADVANCER_ID)
    assert body["bank_bin"] == VALID_ACCOUNT["bank_bin"]
    assert body["account_number"] == VALID_ACCOUNT["account_number"]
    assert body["account_name"] == VALID_ACCOUNT["account_name"]
    assert body["confirmed_at"]


def test_chua_khai_thi_404(client):
    read = client.get(
        f"/people/{ADVANCER_ID}/bank-recipient",
        headers=actor_headers(),
    )
    assert read.status_code == 404, read.text
    assert read.json()["code"] == "bank_recipient_not_found"


def test_khai_lai_thay_tai_khoan_cu(client, repository):
    first = set_account(client)
    assert first.status_code == 200, first.text
    first_id = first.json()["id"]

    second = set_account(client, account_number="9999999999TEST")
    assert second.status_code == 200, second.text
    assert second.json()["id"] != first_id
    assert second.json()["account_number"] == "9999999999TEST"

    read = client.get(
        f"/people/{ADVANCER_ID}/bank-recipient", headers=actor_headers()
    )
    assert read.json()["account_number"] == "9999999999TEST"

    # A replacement is a new row, not an overwrite: the batch gate must see
    # exactly one active destination for this person.
    active = repository.load_bank_recipients(frozenset({ADVANCER_ID}))
    assert len(active) == 1
    assert active[ADVANCER_ID].account_number == "9999999999TEST"


def test_khong_ai_khai_ho_nguoi_khac(client):
    """Spec 9.2: an admin may not add or change someone else's bank account."""
    response = client.put(
        f"/people/{OTHER_ID}/bank-recipient",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member,group_admin"),
        json=VALID_ACCOUNT,
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "permission_denied"


def test_khong_doc_tai_khoan_nguoi_khac(client):
    response = client.get(
        f"/people/{OTHER_ID}/bank-recipient",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="member,group_admin"),
    )
    assert response.status_code == 403, response.text


def test_capability_khach_khong_khai_duoc(client):
    """A guest capability is a bearer token, not an authenticated account."""
    response = client.put(
        f"/people/{ADVANCER_ID}/bank-recipient",
        headers=actor_headers(actor_id=ADVANCER_ID, roles="guest"),
        json=VALID_ACCOUNT,
    )
    assert response.status_code == 403, response.text


def test_khong_co_actor_thi_401(client):
    response = client.put(
        f"/people/{ADVANCER_ID}/bank-recipient", json=VALID_ACCOUNT
    )
    assert response.status_code == 401, response.text


def test_bank_bin_sai_dinh_dang_bi_chan_truoc_khi_toi_db(client):
    for bad in ("97041", "9704155", "97041a", ""):
        response = set_account(client, bank_bin=bad)
        assert response.status_code == 422, (bad, response.text)


def test_so_tai_khoan_sai_dinh_dang_bi_chan_truoc_khi_toi_db(client):
    for bad in ("", "A" * 20, "0123 4567", "0123-4567"):
        response = set_account(client, account_number=bad)
        assert response.status_code == 422, (bad, response.text)


def test_ten_chu_tai_khoan_co_the_bo_trong(client):
    response = client.put(
        f"/people/{ADVANCER_ID}/bank-recipient",
        headers=actor_headers(),
        json={"bank_bin": "970415", "account_number": "0000000000TEST"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["account_name"] is None


def test_person_id_khong_phai_uuid_thi_422(client):
    response = client.put(
        "/people/khong-phai-uuid/bank-recipient",
        headers=actor_headers(),
        json=VALID_ACCOUNT,
    )
    assert response.status_code == 422, response.text


def test_khong_nhan_truong_la(client):
    response = client.put(
        f"/people/{ADVANCER_ID}/bank-recipient",
        headers=actor_headers(),
        json={**VALID_ACCOUNT, "confirmed_at": "2020-01-01T00:00:00+00:00"},
    )
    assert response.status_code == 422, response.text


def test_moi_nguoi_giu_tai_khoan_rieng(client, repository):
    assert set_account(client, person_id=ADVANCER_ID).status_code == 200
    assert (
        set_account(
            client, person_id=OTHER_ID, account_number="1111111111TEST"
        ).status_code
        == 200
    )

    active = repository.load_bank_recipients(frozenset({ADVANCER_ID, OTHER_ID}))
    assert active[ADVANCER_ID].account_number == VALID_ACCOUNT["account_number"]
    assert active[OTHER_ID].account_number == "1111111111TEST"
    assert active[ADVANCER_ID].id != active[OTHER_ID].id


def test_nguoi_chua_khai_khong_lam_hong_nguoi_da_khai(client, repository):
    assert set_account(client).status_code == 200
    active = repository.load_bank_recipients(frozenset({ADVANCER_ID, uuid.uuid4()}))
    assert set(active) == {ADVANCER_ID}
