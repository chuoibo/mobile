"""Seed one real poll with real ballots into the demo group, over HTTP.

Only so the vote card has something to render for the screenshot and axe pass.
Every write goes through `POST /contexts/{id}/messages` exactly as the app does
-- no direct row insert for the poll or the ballots -- so what the screen draws
is what the real route stored.

The extra members are inserted directly, because there is no HTTP route that
adds a member to a group without an invite handshake, and the handshake is not
what this run is measuring.
"""

from __future__ import annotations

import os
import sys
import uuid

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Context, Membership, MembershipRole, MembershipState, Person

API = os.environ.get("QA_API", "http://127.0.0.1:8500")
GROUP = "Team Đà Lạt"

# The seven demo people are stable uuid5 rows; these three are enough for a tie.
MINH = "46b55e67-932b-5415-a5ee-08fb2641a4ff"
TRANG = "49871dab-3bf9-5140-acf3-6c9736b31e8f"
HAI = "be2389f9-62cb-5b28-8e5f-874768e9fb75"

POLL_ID = "poll-man-qa15"
OPTIONS = [
    {"option_id": "o1", "label": "Tiệm nướng Xóm Lèo"},
    {"option_id": "o2", "label": "Lẩu gà lá é Tao Ngộ"},
    {"option_id": "o3", "label": "Bánh căn Nhà Chung"},
]


def headers(person_id, ctx_id):
    return {
        "X-Actor-ID": person_id,
        "X-Actor-Roles": "member",
        "X-Actor-Contexts": str(ctx_id),
    }


def main() -> int:
    engine = create_engine(os.environ["MOBILE_TEST_DATABASE_URL"])
    session = Session(engine)

    ctx = session.scalars(
        select(Context).where(Context.display_name == GROUP)
    ).first()
    if ctx is None:
        print(f"khong tim thay nhom {GROUP!r} — app chua bootstrap?")
        return 1
    print(f"nhom: {ctx.display_name}  context_id={ctx.id}")

    for pid, name in ((TRANG, "Trang"), (HAI, "Hải")):
        p = session.get(Person, uuid.UUID(pid))
        if p is None:
            session.add(Person(id=uuid.UUID(pid), display_name=name))
            session.flush()
        has = session.scalars(
            select(Membership).where(
                Membership.context_id == ctx.id,
                Membership.person_id == uuid.UUID(pid),
            )
        ).first()
        if has is None:
            session.add(Membership(
                id=uuid.uuid4(), context_id=ctx.id, person_id=uuid.UUID(pid),
                state=MembershipState.ACTIVE, role=MembershipRole.MEMBER,
            ))
    session.commit()
    print("thanh vien ACTIVE: Minh, Trang, Hải")

    def post(actor, card):
        r = httpx.post(f"{API}/contexts/{ctx.id}/messages",
                       headers=headers(actor, ctx.id),
                       json={"kind": "ai_card", "card": card}, timeout=30)
        return r

    r = post(MINH, {"kind": "poll", "payload": {
        "poll_id": POLL_ID, "question": "Tối nay ăn ở đâu?", "options": OPTIONS}})
    print(f"mo binh chon (Minh)   HTTP {r.status_code}")
    if r.status_code != 201:
        print(r.text[:300])
        return 1

    # Two ballots on o2, one on o1 -> a clear winner, so the crown path renders.
    for who, name, opt in ((TRANG, "Trang", "o2"), (HAI, "Hải", "o2"), (MINH, "Minh", "o1")):
        r = post(who, {"kind": "poll_vote", "payload": {"poll_id": POLL_ID, "option_id": opt}})
        got = r.json().get("author_id") if r.status_code < 300 else "-"
        print(f"phieu {name:6} -> {opt}   HTTP {r.status_code}  author_id khop={got == who}")

    print("da seed xong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
