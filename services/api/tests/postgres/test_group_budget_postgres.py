"""F34 reads current and historical spend from the real PostgreSQL ledger.

This test uses ``flush`` through the shared helpers and never commits. The
``postgres_session`` rollback therefore leaves no rows for neighbouring files
whose assertions count the shared schema.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.db.models import Membership, MembershipRole, MembershipState

from .test_group_recap_postgres import (
    NOW,
    _app,
    _call,
    _group,
    _headers,
    _outing,
    _person,
    _split,
)

pytestmark = pytest.mark.postgres


def test_group_budget_reloads_the_latest_ledger_version_on_each_request(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _app(postgres_session, monkeypatch)
    context, owner = _group(postgres_session)
    friend = _person(postgres_session, "Bạn đồng hành")
    postgres_session.add(
        Membership(
            context_id=context.id,
            person_id=friend.id,
            state=MembershipState.ACTIVE,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
        )
    )
    postgres_session.flush()
    _outing(postgres_session, context, owner)
    _outing(
        postgres_session,
        context,
        owner,
        title="Đang đi",
        starts_on=date(2030, 8, 26),
        ends_on=date(2030, 8, 29),
    )
    _split(
        app,
        context,
        owner,
        [friend],
        occurred_at="2030-08-22T19:00:00+07:00",
        total=520_000,
    )
    live_expense_id = _split(
        app,
        context,
        owner,
        [friend],
        occurred_at="2030-08-27T19:00:00+07:00",
        total=340_000,
    )

    path = f"/contexts/{context.id}/budget?candidate_per_person_vnd=180000"
    first = _call(app, "GET", path, headers=_headers(owner, context))

    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["active_member_count"] == 2
    assert first_body["outing_count"] == 1
    assert first_body["avg_per_person_vnd"] == 130_000
    assert first_body["in_progress"][0]["spent_per_person_vnd"] == 85_000
    assert first_body["comparison"] == {
        "candidate_per_person_vnd": 180_000,
        "delta_vnd": 50_000,
        "verdict": "cao-hon",
    }

    # A correction appends version 2. The next GET must replace 340k with the
    # latest 400003, not read a cached per-outing total and not add both.
    _split(
        app,
        context,
        owner,
        [friend],
        occurred_at="2030-08-27T19:00:00+07:00",
        total=400_003,
        expense_id=live_expense_id,
    )

    second = _call(app, "GET", path, headers=_headers(owner, context))

    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["in_progress"][0]["spent_per_person_vnd"] == 100_000
    assert second_body["in_progress"][0]["spent_per_person_vnd"] != 185_000
    assert type(second_body["in_progress"][0]["spent_per_person_vnd"]) is int
