"""Re-run the reported reproduction against a live server, end to end.

Not part of the pytest suite: it needs uvicorn and a migrated database, which
is exactly why it is the check the report asked for. Everything here goes over
HTTP; nothing reaches past the API into the tables.

    docker compose up -d postgres
    cd services/api && alembic upgrade head
    MOBILE_DATABASE_URL=... uvicorn app.api.main:app --port 8791
    python3 tests/live/repro_bug_013305.py http://localhost:8791
"""

from __future__ import annotations

import re
import sys
import uuid

import httpx

UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I
)

NAM = (uuid.uuid4(), "Nam")
HA = (uuid.uuid4(), "Hà")
QUYEN = (uuid.uuid4(), "Quyên")
CONTEXT_ID = uuid.uuid4()


def headers(actor_id: uuid.UUID, roles: str) -> dict[str, str]:
    return {
        "X-Actor-ID": str(actor_id),
        "X-Actor-Roles": roles,
        "X-Actor-Contexts": str(CONTEXT_ID),
    }


def visible_text(html: str) -> str:
    """What a reader actually sees: script and style bodies are not read."""
    stripped = re.sub(
        r"<(script|style)\b[^>]*>[\s\S]*?</\1>", " ", html, flags=re.I
    )
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", stripped))


def main(base_url: str) -> int:
    client = httpx.Client(base_url=base_url, timeout=30.0)
    member = "member,group_admin,advancer,recipient,batch_owner"

    for person_id, name in (NAM, HA, QUYEN):
        response = client.put(
            f"/people/{person_id}",
            json={"display_name": name},
            headers=headers(person_id, member),
        )
        print(f"PUT /people/{person_id} -> {response.status_code} {response.text}")
        assert response.status_code == 201, response.text

    opened = client.post(
        "/contexts",
        json={"display_name": "Hội bạn thân"},
        headers=headers(NAM[0], member),
    )
    print(f"POST /contexts -> {opened.status_code} {opened.text}")
    assert opened.status_code == 201, opened.text
    context_id = opened.json()["id"]

    proposal_body = {
        "context_id": context_id,
        "description": "bữa lẩu tối thứ bảy",
        "recorded_by_id": str(NAM[0]),
        "paid_by_id": str(NAM[0]),
        "verification_scope": "totals_only",
        "occurred_at": "2030-08-27T12:00:00+07:00",
        "participants": [str(NAM[0]), str(HA[0]), str(QUYEN[0])],
        "total_amount_vnd": 300_000,
        "items": [],
        "surcharges": [],
        "discounts": [],
    }
    headers_nam = {
        **headers(NAM[0], member),
        "X-Actor-Contexts": context_id,
    }
    proposed = client.post("/expenses", json=proposal_body, headers=headers_nam)
    print(f"POST /expenses -> {proposed.status_code}")
    assert proposed.status_code == 201, proposed.text
    allocations = proposed.json()["allocation"]["allocations"]
    assert sum(allocations.values()) == 300_000, allocations
    print(f"  allocations={allocations} sum={sum(allocations.values())}")

    confirmed = client.post(
        f"/expenses/{proposed.json()['expense_id']}/confirm",
        json={
            "proposal": proposal_body,
            "expected_allocations": allocations,
            "acknowledge_as_advancer": True,
        },
        headers=headers_nam,
    )
    print(f"POST /expenses/{{id}}/confirm -> {confirmed.status_code}")
    assert confirmed.status_code == 201, confirmed.text

    seeded = client.post(
        "/bank-recipients",
        json={
            "recipient_id": str(NAM[0]),
            "bank_bin": "970418",
            "account_number": "0000000000TEST",
            "account_name": "NGUYEN VAN NAM",
        },
        headers=headers_nam,
    )
    print(f"POST /bank-recipients -> {seeded.status_code}")
    assert seeded.status_code in (200, 201), seeded.text

    batch = client.post(
        "/batches",
        json={
            "context_id": context_id,
            "expense_version_ids": [confirmed.json()["expense_version_id"]],
            "due_at": "2030-09-27T12:00:00+07:00",
        },
        headers=headers_nam,
    )
    print(f"POST /batches -> {batch.status_code}")
    assert batch.status_code == 201, batch.text

    published = client.post(
        f"/batches/{batch.json()['batch_id']}/publish",
        json={
            "delivery_method": "personal_link",
            "guest_link_expires_at": "2030-10-27T12:00:00+07:00",
        },
        headers=headers_nam,
    )
    print(f"POST /batches/{{id}}/publish -> {published.status_code}")
    assert published.status_code == 200, published.text

    failures = []
    for link in published.json()["guest_links"]:
        page = client.get(link["path"])
        assert page.status_code == 200, page.status_code
        text = visible_text(page.text)
        strays = UUID_RE.findall(text)
        expected_name = next(
            name for person_id, name in (NAM, HA, QUYEN) if str(person_id) == link["sender_id"]
        )
        print(f"\nGET {link['path']} -> {page.status_code}")
        print(f"  UUIDs in VISIBLE TEXT: {len(strays)}")
        for stray in strays:
            print(f"    {stray}")
        for phrase in (f"Phần của {expected_name}", f"{NAM[1]} đã ghi"):
            present = phrase in text
            print(f"  {'ok ' if present else 'MISSING'} — {phrase!r}")
            if not present:
                failures.append(f"{link['path']}: thiếu {phrase!r}")
        if strays:
            failures.append(f"{link['path']}: còn {len(strays)} UUID trong chữ thấy được")

    print()
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS — không còn UUID nào trong chữ nhìn thấy được, và trang gọi đúng tên")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8791"))
