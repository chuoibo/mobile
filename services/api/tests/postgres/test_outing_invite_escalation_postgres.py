"""Red-first regression test for the forwarded-link privilege escalation.

DROP-IN, NOT COLLECTED HERE ON PURPOSE. This file is named `regression_*.py`
so the repo gate (`pytest services/api/tests tests`) does not pick it up and
main does not go red on a defect QA only reported. When the fix lands, move it
to its home and let the gate own it:

    git mv tests/qa/rd-qa-11/regression_outing_invite_escalation.py \
           services/api/tests/postgres/test_outing_invite_escalation_postgres.py

Run it red, today, against real PostgreSQL:

    cd services/api && MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5811/mobile' \
      MOBILE_REQUIRE_POSTGRES_TESTS=1 python3 -m pytest \
      ../../tests/qa/rd-qa-11/regression_outing_invite_escalation.py -q

WHAT IT GUARDS

`test_outings_postgres.py` already asserts that redeeming a link yields an
INVITED membership and that the memory wall answers 403 immediately after. Both
assertions pass. The bug lives one call later: the redeem response hands back
`membership_id`, and `accept_context_membership` proves only `is_invitee`
(`membership.person_id == actor.id`). The invitee is the accepter, so the
holder of a forwarded link promotes themselves to ACTIVE and `is_member` opens
messages, memories and balances.

The existing test stops at the door and checks it is shut. This one turns the
handle.
"""

from __future__ import annotations

import uuid

import anyio
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import (
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    Person,
)

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

SECRET_CAPTION = "Ảnh riêng của nhóm — người ngoài không được thấy"


def _headers(person_id: uuid.UUID) -> dict[str, str]:
    return {"X-Actor-ID": str(person_id), "X-Actor-Roles": "member"}


def _http(session: Session, monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )


def test_a_forwarded_invite_link_cannot_promote_itself_to_active(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """A link holder nobody named must not reach ACTIVE on their own say-so.

    INVITED is only a safe ceiling while somebody already in the group decides
    who clears it. `is_invitee` was that decision when the sole route to INVITED
    was `invite_context_member`, which requires a group_admin naming a person.
    rd-be-08 added a second route -- a bearer token, forwardable to anyone --
    and the predicate did not change with it.
    """
    owner = Person(id=uuid.uuid4(), display_name="Minh Anh")
    outsider = Person(id=uuid.uuid4(), display_name="Người lạ cầm link")
    postgres_session.add_all([owner, outsider])
    postgres_session.flush()
    context = Context(id=uuid.uuid4(), display_name="Team Đà Lạt", created_by_id=owner.id)
    postgres_session.add(context)
    postgres_session.flush()
    postgres_session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=owner.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
        )
    )
    postgres_session.flush()

    app = _http(postgres_session, monkeypatch)

    async def walk():
        async with _client(app) as client:
            await client.post(
                f"/contexts/{context.id}/memories",
                json={"image_url": "https://example.invalid/a.jpg", "caption": SECRET_CAPTION},
                headers=_headers(owner.id),
            )
            outing = await client.post(
                f"/contexts/{context.id}/outings",
                json={
                    "title": "Đà Lạt 2 ngày",
                    "starts_on": "2026-09-05",
                    "ends_on": "2026-09-06",
                    "headcount": 4,
                    "budget_per_person_vnd": 2_500_000,
                },
                headers=_headers(owner.id),
            )
            minted = await client.post(
                f"/outings/{outing.json()['id']}/invites",
                json={"source": "link"},
                headers=_headers(owner.id),
            )
            token = minted.json()["invite_token"]

            redeemed = await client.post(
                f"/outing-invites/{token}/accept", headers=_headers(outsider.id)
            )
            # The response itself hands over the id needed for the next call.
            membership_id = redeemed.json()["membership_id"]
            promoted = await client.post(
                f"/memberships/{membership_id}/accept", headers=_headers(outsider.id)
            )
            wall = await client.get(
                f"/contexts/{context.id}/memories", headers=_headers(outsider.id)
            )
            return redeemed, promoted, wall

    redeemed, promoted, wall = anyio.run(walk)

    assert redeemed.status_code == 200, redeemed.text
    assert redeemed.json()["membership_state"] == "invited"

    # The self-promotion must be refused. Somebody already inside the group has
    # to clear a bearer-token holder; the holder may not clear themselves.
    assert promoted.status_code == 403, (
        "Người cầm link chuyển tiếp tự nâng mình lên ACTIVE được: "
        f"HTTP {promoted.status_code} {promoted.text}"
    )

    # And the wall stays shut, which is the consequence anyone actually cares about.
    assert wall.status_code == 403, wall.text
    assert SECRET_CAPTION not in wall.text

    membership = postgres_session.scalar(
        select(Membership).where(
            Membership.context_id == context.id,
            Membership.person_id == outsider.id,
        )
    )
    assert membership is not None
    assert membership.state == MembershipState.INVITED, (
        f"membership đã thành {membership.state} mà không ai trong nhóm đồng ý"
    )
