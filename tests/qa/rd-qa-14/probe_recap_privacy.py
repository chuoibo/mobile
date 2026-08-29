"""QA probe for the new private surface GET /contexts/{id}/recap (PR #131).

Independent of the author's own test file. The author covers the total
outsider; this asks the three cases they did not:

  - a member who LEFT the group (state='left', left_at set)
  - a person invited but not yet ACTIVE (state='invited')
  - an ACTIVE member of a DIFFERENT group

It prints the whole response body for every actor rather than comparing status
codes, because a 200 that leaks and a 403 that leaks in its error text look the
same to `assert status == 403`.

Run against a QA-owned database, never the shared one:
  MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile_qa14'
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date, datetime, UTC

import anyio
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import (
    Context, Membership, MembershipRole, MembershipState, Memory,
    Outing, OutingStop, Person,
)

NOW = datetime(2030, 8, 27, 12, 0, tzinfo=UTC)
TRIP_STARTS_ON = date(2030, 8, 21)
TRIP_ENDS_ON = date(2030, 8, 23)
DINNER_VND = 520_000

# Distinctive strings. If any of these turns up in a body an actor should not
# see, that is the leak -- not the status code.
SECRET_TITLE = "Da Lat 2030 QA14"
SECRET_PLACE = "Quan Nuong Ba Nam"
SECRET_STOP = "An toi"


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


def _membership(session, context, person, state, *, left_at=None):
    session.add(Membership(
        id=uuid.uuid4(), context_id=context.id, person_id=person.id,
        state=state, role=MembershipRole.MEMBER, joined_at=NOW, left_at=left_at,
    ))
    session.flush()


def main() -> int:
    url = os.environ["MOBILE_TEST_DATABASE_URL"]
    engine = create_engine(url)
    session = Session(engine)
    application = _app(session)
    verdicts = []

    try:
        # ---- the group whose wall is private -------------------------------
        owner = _person(session, "Minh Anh")
        context = Context(id=uuid.uuid4(), display_name="Team QA14", created_by_id=owner.id)
        session.add(context)
        session.flush()
        _membership(session, context, owner, MembershipState.ACTIVE)

        left_member = _person(session, "Nguoi da roi nhom")
        _membership(session, context, left_member, MembershipState.LEFT, left_at=NOW)

        pending = _person(session, "Nguoi moi duoc moi")
        _membership(session, context, pending, MembershipState.INVITED)

        outsider = _person(session, "Nguoi la")

        # an ACTIVE member of a completely different group
        other_owner = _person(session, "Chu nhom khac")
        other_ctx = Context(id=uuid.uuid4(), display_name="Nhom khac", created_by_id=other_owner.id)
        session.add(other_ctx)
        session.flush()
        _membership(session, other_ctx, other_owner, MembershipState.ACTIVE)

        # ---- the private content -------------------------------------------
        outing = Outing(
            id=uuid.uuid4(), context_id=context.id, created_by_id=owner.id,
            title=SECRET_TITLE, starts_on=TRIP_STARTS_ON, ends_on=TRIP_ENDS_ON,
            headcount=4, budget_per_person_vnd=1_500_000, created_at=NOW,
        )
        session.add(outing)
        session.flush()
        session.add(OutingStop(
            id=uuid.uuid4(), outing_id=outing.id, position=0,
            minute_of_day=19 * 60, label=SECRET_STOP, place_name=SECRET_PLACE,
        ))
        session.add(Memory(
            id=uuid.uuid4(), context_id=context.id, author_id=owner.id,
            image_url="https://example.invalid/qa14.jpg", caption="anh chuyen di",
            created_at=datetime(2030, 8, 22, 5, 0, tzinfo=UTC),
        ))
        session.flush()

        # real money, written the way the product writes it
        participants = [str(owner.id), str(left_member.id)]
        proposal = {
            "context_id": str(context.id), "description": "Bua toi",
            "recorded_by_id": str(owner.id), "paid_by_id": str(owner.id),
            "verification_scope": "totals_only",
            "occurred_at": "2030-08-22T12:00:00+00:00",
            "participants": participants, "total_amount_vnd": DINNER_VND,
            "items": [], "surcharges": [], "discounts": [],
        }
        h = _headers(owner, context)
        proposed = _call(application, "POST", "/expenses", headers=h, json=proposal)
        assert proposed.status_code == 201, proposed.text
        pb = proposed.json()
        confirmed = _call(
            application, "POST", f"/expenses/{pb['expense_id']}/confirm", headers=h,
            json={"proposal": pb["proposal"],
                  "expected_allocations": pb["allocation"]["allocations"],
                  "acknowledge_as_advancer": True},
        )
        assert confirmed.status_code == 201, confirmed.text
        session.flush()

        secrets = [SECRET_TITLE, SECRET_PLACE, SECRET_STOP, str(DINNER_VND), "520000"]

        cases = [
            ("A  ACTIVE member (chung: PHAI thay)", owner, True),
            ("B  da ROI nhom  (state=left)",        left_member, False),
            ("C  moi duoc MOI (state=invited)",     pending, False),
            ("D  nguoi la hoan toan",               outsider, False),
            ("E  ACTIVE cua NHOM KHAC",             other_owner, False),
        ]

        for label, actor, should_see in cases:
            r = _call(application, "GET", f"/contexts/{context.id}/recap",
                      headers=_headers(actor, context))
            body = r.text
            leaked = [s for s in secrets if s in body]
            print("=" * 72)
            print(f"ACTOR {label}")
            print(f"  HTTP {r.status_code}")
            print(f"  BODY {body[:600]}")
            if should_see:
                ok = r.status_code == 200 and SECRET_TITLE in body and str(DINNER_VND) in body
                print(f"  -> chung: thay duoc noi dung rieng = {ok}")
                verdicts.append(("CONTROL", label, ok))
            else:
                ok = r.status_code == 403 and not leaked
                print(f"  -> ro ri: {leaked if leaked else 'KHONG'}   dat={ok}")
                verdicts.append(("PRIVACY", label, ok))
    finally:
        session.rollback()
        session.close()

    print("=" * 72)
    failed = [v for v in verdicts if not v[2]]
    for kind, label, ok in verdicts:
        print(f"  [{'OK  ' if ok else 'FAIL'}] {kind:8} {label}")
    print("=" * 72)
    if failed:
        print(f"KET QUA: FAIL - {len(failed)}/{len(verdicts)} ca hong")
        return 1
    print(f"KET QUA: PASS - {len(verdicts)}/{len(verdicts)} ca dat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
