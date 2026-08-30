#!/usr/bin/env python3
"""Build the one dataset that can tell F42's four audiences apart.

An audience matrix needs readers that differ in exactly one fact each. Seven
people who are all friends and all in the same group cannot distinguish
`friends` from `group`: every reader passes both checks, so a `can_read` that
ignored the audience entirely would still answer correctly on every row. That
is the shape `scripts/seed_demo_data.py` builds, and it is the wrong fixture
for this question.

So this builds four people chosen so that each pair of audiences is separated
by at least one reader:

    Minh    author of every post
    Trang   friend of Minh, NOT in Minh's group
    Hai     in Minh's group, NOT a friend of Minh
    Ngoc    neither

`friends` and `group` are the pair worth the trouble. `app/domain/post_audience.py`
says in its own docstring that they reach disjoint sets and that a rank
comparison would be the wrong implementation. Trang and Hai are the two readers
that make that claim falsifiable: if the levels were secretly a ladder, Hai
reads the `friends` post, and no other reader in the fixture would show it.

## Why these are the demo seven and not four people invented here

`src/navigation/lien-ket.ts` enters the app as one of `DEMO_PEOPLE`, and that
list is hard-coded. A fixture that invents its own person ids builds a matrix
the API can answer and the app can never reach, so the browser half of the
measurement would be walking a different dataset than the HTTP half.

`scripts/seed_demo_data.py` is deliberately NOT used: it puts all seven people
in one group, which makes every reader both a friend-candidate and a groupmate
and collapses the exact distinction this fixture exists to draw.

Every write goes through HTTP. Nothing here INSERTs, because a fixture that
writes rows the API would have refused proves the database can hold a shape the
product cannot produce.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid

API = os.environ.get("MOBILE_QA_API", "http://127.0.0.1:8352")

# Copied from `src/navigation/nhom-demo.ts`. Not re-derived here: that file is
# what the app enters as, so a value computed a second way could drift from it
# and the drift would look like a permission bug.
MINH = uuid.UUID("46b55e67-932b-5415-a5ee-08fb2641a4ff")
TRANG = uuid.UUID("49871dab-3bf9-5140-acf3-6c9736b31e8f")
HAI = uuid.UUID("be2389f9-62cb-5b28-8e5f-874768e9fb75")
NGOC = uuid.UUID("e3a44e25-4547-508a-8f4d-9b2495c3325f")

PEOPLE = [(MINH, "Minh"), (TRANG, "Trang"), (HAI, "Hải"), (NGOC, "Ngọc")]
NAME_OF = dict(PEOPLE)

# The same strings `scripts/seed_demo_data.py` uses. The gateway is trusted to
# write these headers, so a fixture that omits them gets 403 on writes that the
# product performs routinely.
ROLES = "group_admin,member,advancer,recipient,batch_owner"


def call(
    method: str,
    path: str,
    *,
    actor: uuid.UUID,
    body: dict | None = None,
    context_id: uuid.UUID | None = None,
    write_key: str | None = None,
    expect: tuple[int, ...] = (200, 201),
) -> dict:
    """One HTTP call as one actor. Raises on any status outside `expect`."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"{API}{path}", data=data, method=method)
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Actor-ID", str(actor))
    request.add_header("X-Actor-Roles", ROLES)
    if context_id is not None:
        request.add_header("X-Actor-Contexts", str(context_id))
    if write_key is not None:
        request.add_header("Idempotency-Key", write_key)
    try:
        with urllib.request.urlopen(request) as response:
            payload = response.read().decode()
            status = response.status
    except urllib.error.HTTPError as error:
        payload = error.read().decode()
        status = error.code
    if status not in expect:
        raise SystemExit(
            f"{method} {path} as {NAME_OF.get(actor, actor)} -> {status} {payload[:300]}"
        )
    return json.loads(payload) if payload else {}


def main() -> int:
    for person_id, name in PEOPLE:
        call(
            "PUT", f"/people/{person_id}", actor=person_id, body={"display_name": name}
        )
    print(f"nguoi: {len(PEOPLE)}")

    # Minh's group. Hai joins; Trang and Ngoc are deliberately left out.
    group = call(
        "POST",
        "/contexts",
        actor=MINH,
        body={"display_name": "Nhóm của Minh"},
        write_key=f"qa3-0035-group-{MINH}",
    )
    group_id = uuid.UUID(group["id"])
    invite = call(
        "POST",
        f"/contexts/{group_id}/members",
        actor=MINH,
        body={"person_id": str(HAI)},
        context_id=group_id,
        write_key=f"qa3-0035-invite-{HAI}",
    )
    call(
        "POST",
        f"/memberships/{invite['id']}/accept",
        actor=HAI,
        context_id=group_id,
        write_key=f"qa3-0035-accept-{HAI}",
    )
    print(f"nhom: {group_id} (Minh + Hai)")

    # Minh <-> Trang are friends. Minh and Hai are not, which is the whole point.
    friend_request = call(
        "POST",
        "/friends/requests",
        actor=MINH,
        body={"addressee_id": str(TRANG)},
        write_key=f"qa3-0035-friend-{TRANG}",
        expect=(200, 201),
    )
    call(
        "POST",
        f"/friends/requests/{friend_request['id']}/respond",
        actor=TRANG,
        body={"decision": "accept"},
        write_key=f"qa3-0035-friend-accept-{TRANG}",
    )
    print("ket ban: Minh <-> Trang (Minh va Hai KHONG ket ban)")

    print(
        json.dumps(
            {
                "api": API,
                "group_id": str(group_id),
                "minh": str(MINH),
                "trang": str(TRANG),
                "hai": str(HAI),
                "ngoc": str(NGOC),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
