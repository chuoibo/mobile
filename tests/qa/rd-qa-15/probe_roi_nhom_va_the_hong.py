"""Two cases `probe_binh_chon.py` left open, both asked for by the lead.

G  DEPARTED MEMBER. A poll is a group message. Someone who has LEFT the group
   (membership.state='left') must not keep reading the thread they walked out
   of. A non-member being blocked (case D) does NOT prove this: `left` rows
   still exist in `memberships`, so a membership check written as "a row
   exists" passes for them while a check written as "an ACTIVE row exists"
   does not. Only this case separates the two.

   It prints any leaked body rather than comparing status codes, because a 200
   carrying the thread and a 200 carrying an empty page are the same number.

H  MALFORMED BALLOT CARDS. `card` is a free-form dict the server does not
   validate (proved in case C). So the client will meet shapes no author had
   in mind. If one bad card throws, `tongHopBinhChon` is called once for the
   WHOLE thread (TinNhan.tsx:89) -- so a single junk row does not lose one
   bubble, it takes down the entire chat screen and every surface downstream.
   That is the loss the lead named: "trang chat ma trang man vi mot the xau
   la mat ca tinh nang chat".

Run against a QA-owned database, never the shared one.
"""

from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, UTC

import anyio
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import (
    Context, Membership, MembershipRole, MembershipState, Person,
)

NOW = datetime(2030, 8, 27, 12, 0, tzinfo=UTC)
_ticks = itertools.count()


def _tick():
    return NOW + timedelta(seconds=next(_ticks))


def _app(session):
    import app.api.service as service_mod
    service_mod._now = _tick
    application = create_app()
    application.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return application


def _call(application, method, path, *, headers, json=None):
    async def run():
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, headers=headers, json=json)
    return anyio.run(run)


def _hd(person, context):
    return {
        "X-Actor-ID": str(person.id),
        "X-Actor-Roles": "member,group_admin,advancer,platform_moderator",
        "X-Actor-Contexts": str(context.id),
    }


def _person(session, name):
    p = Person(id=uuid.uuid4(), display_name=name)
    session.add(p)
    session.flush()
    return p


def _membership(session, context, person, state):
    # `ck_memberships_left_state_matches_timestamp` requires left_at exactly
    # when state='left'. A schema-level invariant, so it only exists on real
    # Postgres -- the fake repository would have accepted the bad row.
    session.add(Membership(
        id=uuid.uuid4(), context_id=context.id, person_id=person.id,
        state=state, role=MembershipRole.MEMBER, joined_at=NOW,
        left_at=NOW + timedelta(minutes=5) if state is MembershipState.LEFT else None,
    ))
    session.flush()


def main() -> int:
    url = os.environ["MOBILE_TEST_DATABASE_URL"]
    engine = create_engine(url)
    ket = []

    with Session(engine) as session:
        an = _person(session, "An")
        roi = _person(session, "Ro'i Nhom")
        ctx = Context(id=uuid.uuid4(), display_name="Nhom QA15", created_by_id=an.id)
        session.add(ctx)
        session.flush()
        _membership(session, ctx, an, MembershipState.ACTIVE)
        # Was a real member, then left. The row REMAINS in `memberships`.
        _membership(session, ctx, roi, MembershipState.LEFT)
        session.commit()

        app_ = _app(session)
        SECRET = "Toi nay an o dau"

        # An opens a poll containing a distinctive string we can grep for.
        r = _call(app_, "POST", f"/contexts/{ctx.id}/messages", headers=_hd(an, ctx), json={
            "kind": "ai_card",
            "card": {"kind": "poll", "payload": {
                "poll_id": "p-left", "question": SECRET,
                "options": [{"option_id": "o1", "label": "Tiem nuong"},
                            {"option_id": "o2", "label": "Lau ga"}],
            }},
        })
        session.commit()
        print("=" * 72)
        print("G  NGUOI DA ROI NHOM (state='left') doc luong co cuoc binh chon")
        print(f"   An mo poll: HTTP {r.status_code}")
        assert r.status_code == 201, r.text

        # The departed member tries to READ the thread.
        rr = _call(app_, "GET", f"/contexts/{ctx.id}/messages", headers=_hd(roi, ctx))
        body = rr.text
        leaked = SECRET.lower() in body.lower()
        print(f"   nguoi da roi GET messages -> HTTP {rr.status_code}")
        print(f"   ro ri cau hoi binh chon trong than tra ve? {'CO' if leaked else 'KHONG'}")
        if leaked:
            print(f"   THAN TRA VE (ro ri): {body[:400]}")
        ok_g_read = (rr.status_code == 403) or not leaked
        ket.append(("G nguoi da roi nhom khong doc duoc luong", ok_g_read))

        # And tries to VOTE.
        rv = _call(app_, "POST", f"/contexts/{ctx.id}/messages", headers=_hd(roi, ctx), json={
            "kind": "ai_card",
            "card": {"kind": "poll_vote", "payload": {"poll_id": "p-left", "option_id": "o1"}},
        })
        session.commit()
        print(f"   nguoi da roi BO PHIEU -> HTTP {rv.status_code}  bi chan={rv.status_code == 403}")
        ket.append(("G nguoi da roi nhom khong bo phieu duoc", rv.status_code == 403))

    print()
    print("H  THE PHIEU HONG / LA TRONG LUONG CHAT")
    payload = json.dumps({"ok": True})
    proc = subprocess.run(
        ["node", os.path.join(os.path.dirname(os.path.abspath(__file__)), "the_hong.mjs")],
        capture_output=True, text=True, timeout=180,
    )
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stdout.write(proc.stderr[-2000:])
    ket.append(("H the hong khong lam vo man chat", proc.returncode == 0))

    print()
    print("=" * 72)
    hong = 0
    for ten, ok in ket:
        print(f"   {'dat ' if ok else 'HONG'}  {ten}")
        hong += 0 if ok else 1
    print(f"KET QUA: {'PASS' if hong == 0 else 'FAIL'} — {len(ket) - hong}/{len(ket)} ca dat")
    return 1 if hong else 0


if __name__ == "__main__":
    raise SystemExit(main())
