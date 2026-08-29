"""Two devices, one poll — the lead's first question about F17.

"May A mo binh chon, may B bo phieu, may A doc lai duoc khong?"

`tests/binh-chon.test.mjs` cannot answer this. It folds a hand-written array
inside one process: there is no second device, no write, and no read-back. The
only thing that makes F17 usable is that a ballot cast on B becomes visible on
A, and that is a round trip through the server.

Each device gets its OWN HTTP client and its OWN actor headers -- nothing is
shared between them but the database. A reads the thread back with a fresh GET
and folds it with the SHIPPED counter, through `tinHienThiLanDau` exactly as
`TinNhan.tsx:280` does, so what is asserted is what A's screen would draw.
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
POLL = "poll-hai-may"
_ticks = itertools.count()


def _tick():
    return NOW + timedelta(seconds=next(_ticks))


def _app(session):
    import app.api.service as service_mod
    service_mod._now = _tick
    application = create_app()
    application.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return application


def _hd(person, context):
    return {
        "X-Actor-ID": str(person.id),
        "X-Actor-Roles": "member",
        "X-Actor-Contexts": str(context.id),
    }


def main() -> int:
    engine = create_engine(os.environ["MOBILE_TEST_DATABASE_URL"])
    ket = []

    with Session(engine) as session:
        an = Person(id=uuid.uuid4(), display_name="An (may A)")
        trang = Person(id=uuid.uuid4(), display_name="Trang (may B)")
        session.add_all([an, trang])
        session.flush()
        ctx = Context(id=uuid.uuid4(), display_name="Nhom hai may", created_by_id=an.id)
        session.add(ctx)
        session.flush()
        for p in (an, trang):
            session.add(Membership(
                id=uuid.uuid4(), context_id=ctx.id, person_id=p.id,
                state=MembershipState.ACTIVE, role=MembershipRole.MEMBER, joined_at=NOW,
            ))
        session.commit()

        application = _app(session)

        def device(actor, method, path, payload=None):
            """One call from ONE device. Separate client per call: two devices
            never share a connection or any client-side state."""
            async def run():
                transport = httpx.ASGITransport(app=application)
                async with httpx.AsyncClient(transport=transport, base_url="http://a") as c:
                    return await c.request(method, path, headers=_hd(actor, ctx), json=payload)
            return anyio.run(run)

        print("=" * 72)
        print("MAY A (An) mo cuoc binh chon")
        r = device(an, "POST", f"/contexts/{ctx.id}/messages", {
            "kind": "ai_card",
            "card": {"kind": "poll", "payload": {
                "poll_id": POLL, "question": "Toi nay an o dau?",
                "options": [{"option_id": "o1", "label": "Tiem nuong Xom Leo"},
                            {"option_id": "o2", "label": "Lau ga la e Tao Ngo"}]}},
        })
        session.commit()
        print(f"   HTTP {r.status_code}")
        ket.append(("A mo duoc binh chon", r.status_code == 201))

        print("MAY B (Trang) bo phieu cho o2 — chua tung thay may A")
        rb = device(trang, "POST", f"/contexts/{ctx.id}/messages", {
            "kind": "ai_card",
            "card": {"kind": "poll_vote", "payload": {"poll_id": POLL, "option_id": "o2"}},
        })
        session.commit()
        print(f"   HTTP {rb.status_code}")
        ket.append(("B bo phieu duoc", rb.status_code == 201))

        print("MAY A doc lai luong (GET moi, khong dung cache cua A)")
        ra = device(an, "GET", f"/contexts/{ctx.id}/messages")
        print(f"   HTTP {ra.status_code}")
        rows = ra.json().get("messages", [])
        print(f"   A nhan {len(rows)} tin")
        thay_phieu = any(
            (m.get("card") or {}).get("payload", {}).get("option_id") == "o2"
            and str(m.get("author_id")) == str(trang.id)
            for m in rows
        )
        print(f"   A CO thay la phieu cua B khong? {'CO' if thay_phieu else 'KHONG'}")
        ket.append(("A doc lai thay phieu cua B", thay_phieu))

        payload = {"messages": rows, "poll_id": POLL,
                   "ids": {"an": str(an.id), "trang": str(trang.id)}}
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hai-may-rows.json")
        with open(out, "w") as f:
            json.dump(payload, f, indent=1)

    print()
    print("Gap chinh nhung hang A nhan duoc, bang counter DA SHIP,")
    print("qua tinHienThiLanDau dung nhu TinNhan.tsx:280.")
    proc = subprocess.run(
        ["node", os.path.join(os.path.dirname(os.path.abspath(__file__)), "hai_may.mjs")],
        capture_output=True, text=True, timeout=180,
    )
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stdout.write(proc.stderr[-1500:])
    ket.append(("man hinh cua A dem dung la phieu cua B", proc.returncode == 0))

    print()
    print("=" * 72)
    hong = sum(0 if ok else 1 for _, ok in ket)
    for ten, ok in ket:
        print(f"   {'dat ' if ok else 'HONG'}  {ten}")
    print(f"KET QUA: {'PASS' if hong == 0 else 'FAIL'} — {len(ket) - hong}/{len(ket)} ca dat")
    return 1 if hong else 0


if __name__ == "__main__":
    raise SystemExit(main())
