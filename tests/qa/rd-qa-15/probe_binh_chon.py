"""QA probe for F17 group voting (PR #135), against the real route and real Postgres.

#135 counts votes ON THE CLIENT. Its whole correctness rests on one server fact,
which `binh-chon.ts` names in its own header comment:

    `post_context_message` sets author_id=actor.id from the trusted actor header
    and gates the call on is_group_member. A CLIENT CANNOT SAY WHO VOTED.

The author asserts that fact. This probe attacks it. Six cases, none of which is
in `tests/binh-chon.test.mjs` (that file is a pure fold over a hand-written array
and never touches a server):

  A  control        an ACTIVE member opens a poll and votes
  B  forged field   a member posts a ballot with author_id in the REQUEST BODY,
                    claiming to be someone else
  C  forged card    a member hides voter/author_id INSIDE the free-form `card`
                    dict, which the server does not validate at all
  D  non-member     a total outsider casts a ballot
  E  other group    an ACTIVE member of a DIFFERENT group reads this thread
  F  double vote    the same person votes twice

It prints the stored author_id for every accepted message rather than comparing
status codes, because a 201 that records the WRONG voter and a 201 that records
the right one look identical to `assert status == 201`.

The tally itself is deliberately NOT recomputed here. Re-implementing the count
in the probe would just compare two implementations of the same idea. Instead
this dumps the real server rows to JSON and `dem_lai.mjs` folds them with the
shipped `tongHopBinhChon`.

Run against a QA-owned database, never the shared one:
  MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile_qa15'
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, UTC

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
POLL_ID = "poll-qa15"
QUESTION = "Toi nay an o dau?"
OPTIONS = [
    {"option_id": "o1", "label": "Tiem nuong Xom Leo"},
    {"option_id": "o2", "label": "Lau ga la e Tao Ngo"},
    {"option_id": "o3", "label": "Banh can Nha Chung"},
]


def _app(session):
    import app.api.service as service_mod
    service_mod._now = lambda: NOW
    application = create_app()
    application.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return application


def _call(application, method, path, *, headers, json=None):
    async def run():
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, headers=headers, json=json)
    return anyio.run(run)


def _headers(person, context):
    # Deliberately claims every role. A header is a claim, not a proof.
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
    session.add(Membership(
        id=uuid.uuid4(), context_id=context.id, person_id=person.id,
        state=state, role=MembershipRole.MEMBER, joined_at=NOW,
    ))
    session.flush()


def main() -> int:
    url = os.environ["MOBILE_TEST_DATABASE_URL"]
    engine = create_engine(url)
    session = Session(engine)
    application = _app(session)
    verdicts = []

    an = _person(session, "An")
    trang = _person(session, "Trang")
    minh = _person(session, "Minh")
    nguoi_la = _person(session, "Nguoi la")
    nhom_khac = _person(session, "Thanh vien nhom khac")

    ctx = Context(id=uuid.uuid4(), display_name="Nhom QA15", created_by_id=an.id)
    other = Context(id=uuid.uuid4(), display_name="Nhom khac QA15", created_by_id=nhom_khac.id)
    session.add_all([ctx, other])
    session.flush()

    for p in (an, trang, minh):
        _membership(session, ctx, p, MembershipState.ACTIVE)
    _membership(session, other, nhom_khac, MembershipState.ACTIVE)
    session.commit()

    msg_path = f"/contexts/{ctx.id}/messages"

    def post(actor, card, *, extra=None, context=ctx):
        payload = {"kind": "ai_card", "card": card}
        if extra:
            payload.update(extra)
        return _call(application, "POST", f"/contexts/{context.id}/messages",
                     headers=_headers(actor, context), json=payload)

    print("=" * 72)
    print("A  CONTROL — thanh vien ACTIVE mo binh chon roi bo phieu")
    r = post(an, {"kind": "poll", "payload": {
        "poll_id": POLL_ID, "question": QUESTION, "options": OPTIONS}})
    print(f"   mo poll (An)            HTTP {r.status_code}  author_id={r.json().get('author_id') if r.status_code < 300 else '-'}")
    verdicts.append(("A mo poll", r.status_code == 201))

    r = post(trang, {"kind": "poll_vote", "payload": {"poll_id": POLL_ID, "option_id": "o1"}})
    ok = r.status_code == 201 and r.json().get("author_id") == str(trang.id)
    print(f"   phieu Trang -> o1       HTTP {r.status_code}  author_id khop Trang={ok}")
    verdicts.append(("A phieu that", ok))

    print()
    print("B  GIA MAO author_id NGAY TRONG THAN YEU CAU")
    print("   Minh gui phieu, kem author_id=Trang. Neu may chu nhan, Minh bo")
    print("   phieu ho Trang va 'mot nguoi mot phieu' vo nghia.")
    r = post(minh, {"kind": "poll_vote", "payload": {"poll_id": POLL_ID, "option_id": "o3"}},
             extra={"author_id": str(trang.id)})
    body = r.text[:120].replace("\n", " ")
    ok = r.status_code == 422
    print(f"   HTTP {r.status_code}   tu choi truong la={ok}")
    print(f"   than tra ve: {body}")
    verdicts.append(("B tu choi author_id gia", ok))

    print()
    print("C  GIA MAO NGUOI BO PHIEU BEN TRONG `card` (may chu KHONG kiem card)")
    print("   card la dict tu do. Minh nhet author_id/voter_id=Trang vao payload.")
    r = post(minh, {"kind": "poll_vote", "payload": {
        "poll_id": POLL_ID, "option_id": "o3",
        "author_id": str(trang.id), "voter_id": str(trang.id), "nguoi_bo": str(trang.id)}})
    stored = r.json().get("author_id") if r.status_code < 300 else None
    ok = r.status_code == 201 and stored == str(minh.id)
    print(f"   HTTP {r.status_code}   may chu chap nhan card (dung, card tu do)")
    print(f"   author_id LUU = {stored}")
    print(f"   = Minh (nguoi gui THAT)? {stored == str(minh.id)}   = Trang (nguoi bi mao danh)? {stored == str(trang.id)}")
    verdicts.append(("C card gia khong doi duoc author_id", ok))

    print()
    print("D  NGUOI LA (khong phai thanh vien) bo phieu")
    r = post(nguoi_la, {"kind": "poll_vote", "payload": {"poll_id": POLL_ID, "option_id": "o2"}})
    ok = r.status_code == 403
    print(f"   HTTP {r.status_code}   bi chan={ok}")
    verdicts.append(("D nguoi la bi chan", ok))

    print()
    print("E  THANH VIEN ACTIVE CUA NHOM KHAC doc luong tin nay")
    r = _call(application, "GET", msg_path, headers=_headers(nhom_khac, ctx))
    leaked = [s for s in (QUESTION, "Tiem nuong Xom Leo", "Lau ga la e Tao Ngo") if s in r.text]
    ok = r.status_code == 403 and not leaked
    print(f"   HTTP {r.status_code}   ro ri noi dung: {leaked or 'KHONG'}")
    verdicts.append(("E nhom khac khong doc duoc", ok))

    print()
    print("F  BO PHIEU HAI LAN — Minh da bo o3 o ca C, gio bo lai o2")
    r = post(minh, {"kind": "poll_vote", "payload": {"poll_id": POLL_ID, "option_id": "o2"}})
    ok = r.status_code == 201 and r.json().get("author_id") == str(minh.id)
    print(f"   HTTP {r.status_code}   may chu ghi ca hai la phieu (dung — chot o tang dem)")
    verdicts.append(("F phieu thu hai duoc ghi", ok))

    # Dump the real rows so the shipped counter folds them, not a copy of it.
    r = _call(application, "GET", msg_path, headers=_headers(an, ctx))
    rows = r.json()["messages"]
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tin-nhan-that.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({
            "messages": rows,
            "ids": {"an": str(an.id), "trang": str(trang.id), "minh": str(minh.id)},
            "poll_id": POLL_ID,
        }, fh, ensure_ascii=False, indent=2)
    print()
    print(f"   da ghi {len(rows)} tin nhan THAT tu may chu -> {os.path.basename(out)}")

    print()
    print("=" * 72)
    failed = [name for name, ok in verdicts if not ok]
    for name, ok in verdicts:
        print(f"   {'dat ' if ok else 'HONG'}  {name}")
    if failed:
        print(f"KET QUA: FAIL — {len(failed)}/{len(verdicts)} ca hong")
        return 1
    print(f"KET QUA: PASS — {len(verdicts)}/{len(verdicts)} ca dat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
