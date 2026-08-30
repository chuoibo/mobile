"""Who may read a person's money, and what the route does with the answer.

Runs on the fake repository, so it proves nothing about the totals themselves
-- those are settled against real PostgreSQL in
`tests/postgres/test_person_finance_postgres.py`. What it does prove is the
layer the fake actually stands for: the self-only rule, and the fact that the
route hands the ledger's own numbers through without reshaping them.

The self-only rule is worth a test rather than a comment because the header
auth it rests on is a trusted-gateway stand-in. A missing check here would look
identical to a present one in every other test in this directory.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.api.repository import FinanceMovement, PersonFinanceSummary

from .helpers import ADVANCER_ID, CONTEXT_ID, OTHER_ID, actor_headers

CONFIRMED_AT = datetime(2030, 8, 29, 12, 30, tzinfo=UTC)


def _summary(person_id=ADVANCER_ID, *, movements=()):
    return PersonFinanceSummary(
        person_id=person_id,
        display_name="Minh",
        spend_vnd=860_000,
        settled_vnd=610_000,
        outstanding_vnd=250_000,
        receivable_vnd=530_000,
        expense_count=4,
        group_count=2,
        movements=movements,
    )


def _movement(direction="out", amount_vnd=250_000):
    return FinanceMovement(
        obligation_id=uuid.uuid4(),
        direction=direction,
        amount_vnd=amount_vnd,
        counterparty_id=OTHER_ID,
        counterparty_name="Trang",
        context_id=CONTEXT_ID,
        context_name="Team Đà Lạt",
        occasion="Lẩu nấm",
        occurred_at=CONFIRMED_AT,
    )


def test_a_person_reads_their_own_finances(client, repository):
    repository.finances[ADVANCER_ID] = _summary(movements=(_movement(),))

    response = client.get(
        f"/people/{ADVANCER_ID}/finance", headers=actor_headers(ADVANCER_ID)
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["spend_vnd"] == 860_000
    assert body["settled_vnd"] == 610_000
    assert body["outstanding_vnd"] == 250_000
    assert body["receivable_vnd"] == 530_000
    assert body["expense_count"] == 4
    assert body["group_count"] == 2
    assert len(body["movements"]) == 1


def test_nobody_reads_somebody_elses_finances(client, repository):
    """The whole privacy rule for this screen, in one refusal.

    A finance summary carries what somebody spent, what they still owe, and the
    names of everyone they have settled with. There is deliberately no
    group-admin exception: running a collection round is a different question
    from what a member has spent all year.
    """
    repository.finances[OTHER_ID] = _summary(person_id=OTHER_ID)

    response = client.get(
        f"/people/{OTHER_ID}/finance",
        headers=actor_headers(ADVANCER_ID, roles="member,group_admin,batch_owner"),
    )

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "not_your_finances"
    # The refusal must not leak the figures it is refusing.
    assert "860000" not in response.text
    assert "530000" not in response.text, "what they are owed is theirs too"
    assert "Trang" not in response.text


def test_a_person_who_has_split_nothing_reads_zero_rather_than_404(client):
    """A new account is a real state with a real answer, and it is zero.

    404 would make an account that has not split anything indistinguishable
    from a mistyped id, and the screen would have to guess which it was
    looking at.
    """
    newcomer = uuid.uuid4()

    response = client.get(
        f"/people/{newcomer}/finance", headers=actor_headers(newcomer)
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["spend_vnd"] == 0
    assert body["outstanding_vnd"] == 0
    assert body["receivable_vnd"] == 0
    assert body["movements"] == []


def test_the_direction_of_money_survives_the_response(client, repository):
    """`direction` is carried as a word, never as the sign of a number.

    A signed amount loses its sign the first time a client formats it with an
    absolute value -- which is precisely how a repayment renders as income on
    somebody's screen.
    """
    repository.finances[ADVANCER_ID] = _summary(
        movements=(_movement("in", 420_000), _movement("out", 120_000))
    )

    response = client.get(
        f"/people/{ADVANCER_ID}/finance", headers=actor_headers(ADVANCER_ID)
    )

    movements = response.json()["movements"]
    assert [m["direction"] for m in movements] == ["in", "out"]
    assert all(m["amount_vnd"] > 0 for m in movements), "sign lives in direction"
    assert movements[0]["counterparty_name"] == "Trang"
    assert movements[0]["occasion"] == "Lẩu nấm"


def test_the_route_never_recomputes_what_the_ledger_answered(client, repository):
    """Passed through, not re-derived.

    The route is handed figures that already satisfy
    `settled + outstanding == spend` and must not "helpfully" recompute one of
    them. Fed a deliberately inconsistent summary it reports exactly what it
    was given, which is what makes the ledger the only place this arithmetic
    happens.
    """
    repository.finances[ADVANCER_ID] = PersonFinanceSummary(
        person_id=ADVANCER_ID,
        display_name="Minh",
        spend_vnd=100,
        settled_vnd=7,
        outstanding_vnd=11,
        receivable_vnd=13,
        expense_count=1,
        group_count=1,
        movements=(),
    )

    body = client.get(
        f"/people/{ADVANCER_ID}/finance", headers=actor_headers(ADVANCER_ID)
    ).json()

    assert (body["spend_vnd"], body["settled_vnd"], body["outstanding_vnd"]) == (
        100,
        7,
        11,
    )
    # Outside that identity on purpose: 13 is neither 100 - 7 nor 100 - 11, and
    # a route that "helpfully" reconciled the row would have to change it.
    assert body["receivable_vnd"] == 13
