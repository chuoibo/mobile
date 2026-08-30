"""`POST /bills/{id}/my-items`: the write path, against real PostgreSQL.

The half of F22 that touches money. Detection produces rectangles; this is what
happens when somebody taps one and says "that is me, and these were my dishes".

Three properties, and the second is the one a fake could never have proved:

1. The person charged comes from `X-Actor-ID`. The body has no field for a
   name, so there is nothing to forge -- but "there is no field" is a claim
   about a schema, and this file checks the row that actually lands in
   `bill_item_shares`.
2. Claiming a dish does not disturb anybody else's claim on it. The obvious
   implementation reuses `confirm_bill_assignments`, which clears every share
   on the keys it is handed; that bug is invisible in a single-diner test and
   silently deletes the rest of the table in a real one.
3. Nothing here reaches the ledger. A bill is a draft: re-tagging before the
   split changes no recorded money, and after a split it is `confirm_expense`
   that writes a new version. This file asserts the draft path writes no
   allocation rows, and that the split of a re-tagged bill still sums to the
   printed total.
"""

from __future__ import annotations

import uuid

import anyio
import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_repository
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import (
    BillItemShare,
    ConfirmedAllocation,
    Context,
    ExpenseVersion,
    Membership,
    MembershipRole,
    MembershipState,
    Person,
)

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

PHO = 120_000
NEM = 80_000
BIA = 100_000
TOTAL = PHO + NEM + BIA


def _app(session: Session, monkeypatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    application = create_app()
    application.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(
        session
    )
    return application


def _request(app, method: str, path: str, **kwargs) -> httpx.Response:
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, path, **kwargs)

    return anyio.run(send)


def _headers(person_id: uuid.UUID) -> dict[str, str]:
    return {"X-Actor-ID": str(person_id), "X-Actor-Roles": "member,group_admin"}


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _join(session: Session, context_id: uuid.UUID, person: Person, role) -> None:
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context_id,
            person_id=person.id,
            state=MembershipState.ACTIVE,
            role=role,
            joined_at=NOW,
        )
    )
    session.flush()


@pytest.fixture
def app(postgres_session, monkeypatch):
    return _app(postgres_session, monkeypatch)


@pytest.fixture
def table(app, postgres_session):
    """Three people at one table, one bill with three lines, no claims yet."""

    an = _person(postgres_session, "An")
    binh = _person(postgres_session, "Bình")
    chi = _person(postgres_session, "Chi")
    context = Context(
        id=uuid.uuid4(), display_name="Bữa tối thứ bảy", created_by_id=an.id
    )
    postgres_session.add(context)
    postgres_session.flush()
    _join(postgres_session, context.id, an, MembershipRole.ADMIN)
    _join(postgres_session, context.id, binh, MembershipRole.MEMBER)
    _join(postgres_session, context.id, chi, MembershipRole.MEMBER)

    response = _request(
        app,
        "POST",
        "/bills",
        headers=_headers(an.id),
        json={
            "context_id": str(context.id),
            "printed_total_vnd": TOTAL,
            "items_total_vnd": TOTAL,
            "confidence": 90,
            "needs_review": False,
            "items": [
                {
                    "item_key": "pho",
                    "name": "Phở bò",
                    "quantity": 1,
                    "unit_price_vnd": PHO,
                    "line_total_vnd": PHO,
                    "suggested_participant_ids": [],
                },
                {
                    "item_key": "nem",
                    "name": "Nem rán",
                    "quantity": 1,
                    "unit_price_vnd": NEM,
                    "line_total_vnd": NEM,
                    "suggested_participant_ids": [],
                },
                {
                    "item_key": "bia",
                    "name": "Bia",
                    "quantity": 1,
                    "unit_price_vnd": BIA,
                    "line_total_vnd": BIA,
                    "suggested_participant_ids": [],
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    return {
        "an": an,
        "binh": binh,
        "chi": chi,
        "context": context,
        "bill_id": uuid.UUID(response.json()["id"]),
    }


def _claim(app, bill_id, person, item_keys) -> httpx.Response:
    return _request(
        app,
        "POST",
        f"/bills/{bill_id}/my-items",
        headers=_headers(person.id),
        json={"item_keys": item_keys},
    )


def _shares(session: Session, bill_id: uuid.UUID) -> list[BillItemShare]:
    from app.db.models import BillItem

    return list(
        session.scalars(
            select(BillItemShare)
            .join(BillItem, BillItem.id == BillItemShare.bill_item_id)
            .where(BillItem.bill_id == bill_id)
        )
    )


def test_the_row_that_lands_names_the_caller(app, table, postgres_session):
    response = _claim(app, table["bill_id"], table["binh"], ["nem"])

    assert response.status_code == 200, response.text
    rows = _shares(postgres_session, table["bill_id"])
    assert len(rows) == 1
    assert rows[0].participant_id == table["binh"].id
    # The decision is the same person, necessarily. A self-claim is the one
    # assignment where "who decided" and "who is charged" cannot differ.
    assert rows[0].decided_by_id == table["binh"].id
    assert rows[0].source == "confirmed"


def test_claiming_a_shared_dish_does_not_evict_the_other_claimant(
    app, table, postgres_session
):
    """The bug the obvious implementation has.

    Reusing `confirm_bill_assignments` clears every share on the keys handed
    to it. With one diner nothing looks wrong; with two, Bình's tap deletes
    An's beer and the split silently charges one person for both.
    """

    assert _claim(app, table["bill_id"], table["an"], ["bia"]).status_code == 200
    assert _claim(app, table["bill_id"], table["binh"], ["bia"]).status_code == 200

    rows = _shares(postgres_session, table["bill_id"])
    assert {row.participant_id for row in rows} == {
        table["an"].id,
        table["binh"].id,
    }
    assert len(rows) == 2


def test_the_list_is_the_whole_claim_so_a_mistap_can_be_undone(
    app, table, postgres_session
):
    assert (
        _claim(app, table["bill_id"], table["chi"], ["pho", "nem"]).status_code == 200
    )
    assert _claim(app, table["bill_id"], table["chi"], ["pho"]).status_code == 200

    mine = [
        row
        for row in _shares(postgres_session, table["bill_id"])
        if row.participant_id == table["chi"].id
    ]
    assert len(mine) == 1


def test_releasing_everything_leaves_the_others_alone(app, table, postgres_session):
    assert _claim(app, table["bill_id"], table["an"], ["pho"]).status_code == 200
    assert _claim(app, table["bill_id"], table["binh"], ["nem"]).status_code == 200
    assert _claim(app, table["bill_id"], table["binh"], []).status_code == 200

    rows = _shares(postgres_session, table["bill_id"])
    assert [row.participant_id for row in rows] == [table["an"].id]


def test_repeating_the_same_claim_is_idempotent(app, table, postgres_session):
    for _ in range(3):
        assert (
            _claim(app, table["bill_id"], table["an"], ["pho", "bia"]).status_code
            == 200
        )

    rows = _shares(postgres_session, table["bill_id"])
    assert len(rows) == 2


def test_the_body_cannot_name_anybody(app, table, postgres_session):
    """`extra="forbid"` is the gate; this is the measurement of it.

    Every shape somebody would reach for to charge a dish to another person.
    Each is refused before the handler runs, and no row is written.
    """

    for body in (
        {"item_keys": ["pho"], "participant_id": str(table["chi"].id)},
        {"item_keys": ["pho"], "person_id": str(table["chi"].id)},
        {"item_keys": ["pho"], "on_behalf_of": str(table["chi"].id)},
        {"item_keys": ["pho"], "participant_ids": [str(table["chi"].id)]},
        {"item_keys": ["pho"], "decided_by_id": str(table["chi"].id)},
    ):
        response = _request(
            app,
            "POST",
            f"/bills/{table['bill_id']}/my-items",
            headers=_headers(table["an"].id),
            json=body,
        )
        assert response.status_code == 422, (body, response.text)

    assert _shares(postgres_session, table["bill_id"]) == []


def test_a_stranger_cannot_claim_a_dish_on_a_group_they_are_not_in(
    app, table, postgres_session
):
    stranger = _person(postgres_session, "Người ngoài")

    response = _claim(app, table["bill_id"], stranger, ["pho"])

    assert response.status_code == 403
    assert _shares(postgres_session, table["bill_id"]) == []


def test_an_item_that_is_not_on_this_bill_is_refused(app, table, postgres_session):
    response = _claim(app, table["bill_id"], table["an"], ["pho", "khong-co-mon-nay"])

    assert response.status_code == 422
    assert response.json()["code"] == "unknown_bill_item"
    # And the valid half of the request did not land either.
    assert _shares(postgres_session, table["bill_id"]) == []


# --- the money boundary ---------------------------------------------------


def test_self_tagging_writes_nothing_to_the_ledger(app, table, postgres_session):
    """A bill is a draft. Tapping "that was mine" records no money."""

    before_allocations = postgres_session.scalar(
        select(func.count()).select_from(ConfirmedAllocation)
    )
    before_versions = postgres_session.scalar(
        select(func.count()).select_from(ExpenseVersion)
    )

    assert _claim(app, table["bill_id"], table["an"], ["pho"]).status_code == 200
    assert _claim(app, table["bill_id"], table["binh"], ["nem"]).status_code == 200
    assert _claim(app, table["bill_id"], table["chi"], ["bia"]).status_code == 200
    postgres_session.flush()

    assert (
        postgres_session.scalar(select(func.count()).select_from(ConfirmedAllocation))
        == before_allocations
    )
    assert (
        postgres_session.scalar(select(func.count()).select_from(ExpenseVersion))
        == before_versions
    )


def test_the_split_of_a_self_tagged_bill_still_sums_to_the_total(app, table):
    """Law 2, on the path F22 opens. Not assumed from the allocator's own tests.

    The allocator is proved by 41 hand-computed vectors. What those cannot say
    is whether *this* route hands it a projection that still adds up -- a claim
    written with the wrong scope produces a perfectly valid allocation of the
    wrong bill.
    """

    assert _claim(app, table["bill_id"], table["an"], ["pho"]).status_code == 200
    assert _claim(app, table["bill_id"], table["binh"], ["nem"]).status_code == 200
    assert _claim(app, table["bill_id"], table["chi"], ["bia"]).status_code == 200

    response = _request(
        app,
        "POST",
        f"/bills/{table['bill_id']}/split",
        headers=_headers(table["an"].id),
        json={"for_ledger": True, "paid_by_id": str(table["an"].id)},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assignment_state"] == "confirmed"
    assert body["total_amount_vnd"] == TOTAL

    by_person = body["allocation"]["allocations"]
    assert sum(by_person.values()) == TOTAL
    # Every diner paid for exactly what they claimed, in whole dong.
    assert by_person[str(table["an"].id)] == PHO
    assert by_person[str(table["binh"].id)] == NEM
    assert by_person[str(table["chi"].id)] == BIA


def test_retagging_changes_the_split_and_still_sums_to_the_total(app, table):
    """The invariant holds across a correction, not only on a first pass."""

    assert _claim(app, table["bill_id"], table["an"], ["pho", "bia"]).status_code == 200
    assert _claim(app, table["bill_id"], table["binh"], ["nem"]).status_code == 200
    # An looks again: the beer was Chi's.
    assert _claim(app, table["bill_id"], table["an"], ["pho"]).status_code == 200
    assert _claim(app, table["bill_id"], table["chi"], ["bia"]).status_code == 200

    response = _request(
        app,
        "POST",
        f"/bills/{table['bill_id']}/split",
        headers=_headers(table["an"].id),
        json={"for_ledger": True, "paid_by_id": str(table["an"].id)},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    by_person = body["allocation"]["allocations"]
    assert sum(by_person.values()) == TOTAL
    assert by_person[str(table["an"].id)] == PHO
    assert by_person[str(table["chi"].id)] == BIA


def test_every_amount_is_a_whole_number_of_dong(app, table):
    """Law 1 on this path: no float reaches the wire, not even at 1/3 of a beer."""

    # Every line needs an assignee before the bill projects at all, so the
    # other two dishes go to An. The beer is the interesting one: three ways.
    assert (
        _claim(app, table["bill_id"], table["an"], ["pho", "nem", "bia"]).status_code
        == 200
    )
    assert _claim(app, table["bill_id"], table["binh"], ["bia"]).status_code == 200
    assert _claim(app, table["bill_id"], table["chi"], ["bia"]).status_code == 200

    response = _request(
        app,
        "POST",
        f"/bills/{table['bill_id']}/split",
        headers=_headers(table["an"].id),
        json={"for_ledger": False, "paid_by_id": str(table["an"].id)},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    for amount in body["allocation"]["allocations"].values():
        assert isinstance(amount, int)
    # 100_000 over three people does not divide evenly, and the remainder must
    # still be inside the total rather than rounded away.
    assert sum(body["allocation"]["allocations"].values()) == TOTAL
    # The exact rational shares are kept as strings, so the third that does
    # not terminate in base ten is never smuggled through a float.
    assert body["allocation"]["exact_shares"]
    for share in body["allocation"]["exact_shares"].values():
        assert isinstance(share, str)
