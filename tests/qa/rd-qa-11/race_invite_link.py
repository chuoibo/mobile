"""Two people redeem ONE outing invite link at the same instant.

The link is documented as single use: `accept_outing_invite` refuses a second
redemption with 409 "Invite link was already used", and the sequential case is
covered by `test_a_forged_or_reused_invite_link_is_refused`.

This probe asks the question that test cannot: does the guard survive two
redemptions that overlap in time? The service reads the invite WITHOUT a lock
(`get_outing_invite_by_digest` is a plain SELECT), decides in Python whether
`accepted_at` is None, and only then takes `FOR UPDATE` -- where it stamps
`accepted_at` unconditionally, never re-reading the guard it already passed.

Run against a REAL server and a REAL PostgreSQL. The routes are sync `def`, so
FastAPI dispatches them to a threadpool and each request gets its own session
and its own connection -- which is the only configuration where this can be
observed at all. A shared TestClient session cannot see it.

Usage:
    MOBILE_API=http://localhost:8811 \
    MOBILE_DB='postgresql://mobile:mobile-dev-only@localhost:5811/mobile' \
    python3 race_invite_link.py [rounds]
"""

from __future__ import annotations

import os
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx
import psycopg

API = os.environ.get("MOBILE_API", "http://localhost:8811")
DB = os.environ.get("MOBILE_DB", "postgresql://mobile:mobile-dev-only@localhost:5811/mobile")


def headers(person_id: str) -> dict[str, str]:
    return {"X-Actor-ID": person_id, "X-Actor-Roles": "member"}


def make_person(client: httpx.Client, name: str) -> str:
    person_id = str(uuid.uuid4())
    response = client.put(
        f"/people/{person_id}",
        json={"display_name": name},
        headers=headers(person_id),
    )
    response.raise_for_status()
    return person_id


def build_outing(client: httpx.Client) -> tuple[str, str, str, str]:
    """Owner creates a group and a trip. Returns (context, owner, and two outsiders)."""
    owner = make_person(client, "Chu nhom")
    first = make_person(client, "Nguoi la mot")
    second = make_person(client, "Nguoi la hai")

    context = client.post(
        "/contexts", json={"display_name": "Team QA11"}, headers=headers(owner)
    )
    context.raise_for_status()
    context_id = context.json()["id"]

    outing = client.post(
        f"/contexts/{context_id}/outings",
        json={
            "title": "Da Lat 2 ngay",
            "starts_on": "2026-09-05",
            "ends_on": "2026-09-06",
            "headcount": 4,
            "budget_per_person_vnd": 2_500_000,
        },
        headers=headers(owner),
    )
    outing.raise_for_status()
    return context_id, outing.json()["id"], first, second


def mint_link(client: httpx.Client, outing_id: str, owner_actor: str) -> str:
    response = client.post(
        f"/outings/{outing_id}/invites",
        json={"source": "link"},
        headers=headers(owner_actor),
    )
    response.raise_for_status()
    return response.json()["invite_token"]


def count_open_memberships(context_id: str) -> list[tuple[str, str]]:
    """Read back on a SEPARATE connection -- the API's own session would lie."""
    with psycopg.connect(DB) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT person_id::text, state FROM memberships "
            "WHERE context_id = %s AND left_at IS NULL ORDER BY created_at",
            (context_id,),
        )
        return [(row[0], str(row[1])) for row in cursor.fetchall()]


def one_round(index: int) -> dict:
    with httpx.Client(base_url=API, timeout=30.0) as client:
        context_id, outing_id, first, second = build_outing(client)
        owner = count_open_memberships(context_id)[0][0]
        token = mint_link(client, outing_id, owner)

    gate = threading.Barrier(2)

    def redeem(actor: str) -> tuple[int, str]:
        # A fresh client per thread: separate TCP connection, separate session.
        with httpx.Client(base_url=API, timeout=30.0) as client:
            gate.wait()
            response = client.post(
                f"/outing-invites/{token}/accept", headers=headers(actor)
            )
            return response.status_code, response.text[:120]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result() for f in [pool.submit(redeem, first), pool.submit(redeem, second)]]

    rows = count_open_memberships(context_id)
    invited = [row for row in rows if row[1].lower().endswith("invited")]
    accepted = sum(1 for status, _ in results if status == 200)

    return {
        "round": index,
        "statuses": sorted(status for status, _ in results),
        "accepted_200": accepted,
        "invited_rows": len(invited),
        "context": context_id,
        "bodies": [body for _, body in results],
    }


def main() -> int:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    bad = []
    for index in range(1, rounds + 1):
        outcome = one_round(index)
        # The contract: one link, one redemption, one invited person.
        broken = outcome["accepted_200"] != 1 or outcome["invited_rows"] != 1
        flag = "VI PHAM" if broken else "ok"
        print(
            f"[{index:>2}] statuses={outcome['statuses']} "
            f"200s={outcome['accepted_200']} invited_rows={outcome['invited_rows']} {flag}"
        )
        if broken:
            bad.append(outcome)

    print()
    print(f"rounds={rounds} vi_pham={len(bad)}")
    if bad:
        sample = bad[0]
        print(f"vi du: context={sample['context']}")
        for body in sample["bodies"]:
            print(f"  body: {body}")
        print("KET LUAN: mot link dung mot lan da nhan HAI nguoi vao nhom.")
        return 1
    print("KET LUAN: khong quan sat duoc vi pham trong so vong da chay.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
