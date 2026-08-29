"""VAT and service charge against the real database and over real HTTP.

`tests/api/test_bills_surcharges.py` proves the orchestration with a fake
repository, which can be taught to return anything and therefore proves nothing
about storage. Two claims need PostgreSQL:

  * the surcharge and discount rows actually survive a commit, read back on a
    SEPARATE connection -- a writer session happily reads its own uncommitted
    rows, so asserting through the writing session would prove the object graph
    in memory and nothing about what persists;
  * the four routes a bill screen calls reach that storage over HTTP, with the
    real repository behind them, and land on the printed total.

Note for whoever adds cases here: `tests/postgres` shares one schema for the
whole session, so never assert "this table has exactly N rows".
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import anyio
import httpx
import pytest
from sqlalchemy.engine import Engine
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

pytestmark = pytest.mark.postgres

NOW = datetime(2030, 8, 29, 9, 0, tzinfo=UTC)

LAU_BO_VND = 420000
BIA_VND = 300000
ITEMS_TOTAL_VND = LAU_BO_VND + BIA_VND  # 720.000
SERVICE_CHARGE_VND = 36000  # 5% of the food
VAT_VND = 60480  # 8% of food + service
PRINTED_TOTAL_VND = ITEMS_TOTAL_VND + SERVICE_CHARGE_VND + VAT_VND  # 816.480


def _items(an: uuid.UUID, binh: uuid.UUID) -> list[dict]:
    return [
        {
            "item_key": "lau-bo",
            "name": "Lẩu bò",
            "quantity": 1,
            "unit_price_vnd": LAU_BO_VND,
            "line_total_vnd": LAU_BO_VND,
            "position": 0,
            "suggested_participant_ids": [an, binh],
        },
        {
            "item_key": "bia-sai-gon",
            "name": "Bia Sài Gòn",
            "quantity": 6,
            "unit_price_vnd": 50000,
            "line_total_vnd": BIA_VND,
            "position": 1,
            "suggested_participant_ids": [binh],
        },
    ]


def _surcharges() -> list[dict]:
    return [
        {
            "surcharge_key": "phi-phuc-vu",
            "kind": "service",
            "amount_vnd": SERVICE_CHARGE_VND,
            "mode": "proportional",
        },
        {
            "surcharge_key": "vat",
            "kind": "vat",
            "amount_vnd": VAT_VND,
            "mode": "proportional",
        },
    ]


def _committed(postgres_engine: Engine, session: Session):
    session.commit()
    return Session(postgres_engine, expire_on_commit=False)


class TestWhatSurvivesACommit:
    def test_the_surcharge_lines_read_back_with_their_kind_and_mode(
        self, postgres_engine: Engine, postgres_session: Session
    ):
        """Kind and mode are money facts, not labels.

        Golden G10 shows the same amount allocating differently under
        `proportional` and `even`; storing a surcharge without its mode would
        turn one of those two answers into the other on the next read.
        """

        an, binh = uuid.uuid4(), uuid.uuid4()
        bill = SqlAlchemyApiRepository(postgres_session).create_bill(
            context_id=uuid.uuid4(),
            created_by_id=an,
            printed_total_vnd=PRINTED_TOTAL_VND,
            items_total_vnd=ITEMS_TOTAL_VND,
            confidence=91,
            needs_review=False,
            items=_items(an, binh),
            surcharges=_surcharges(),
            discounts=[],
            now=NOW,
        )

        with _committed(postgres_engine, postgres_session) as reader:
            stored = SqlAlchemyApiRepository(reader).get_bill(bill.id)

        assert [
            (line.surcharge_key, line.kind, line.amount_vnd, line.mode)
            for line in stored.surcharges
        ] == [
            ("phi-phuc-vu", "service", SERVICE_CHARGE_VND, "proportional"),
            ("vat", "vat", VAT_VND, "proportional"),
        ]

    def test_an_item_scoped_discount_keeps_the_item_it_points_at(
        self, postgres_engine: Engine, postgres_session: Session
    ):
        """A discount that forgets its target becomes a different discount:
        ADR-0004 subtracts an item-scoped one from that item before splitting,
        and a global one proportionally from everybody."""

        an, binh = uuid.uuid4(), uuid.uuid4()
        bill = SqlAlchemyApiRepository(postgres_session).create_bill(
            context_id=uuid.uuid4(),
            created_by_id=an,
            printed_total_vnd=PRINTED_TOTAL_VND - 30000,
            items_total_vnd=ITEMS_TOTAL_VND,
            confidence=91,
            needs_review=False,
            items=_items(an, binh),
            surcharges=_surcharges(),
            discounts=[
                {
                    "discount_key": "giam-bia",
                    "amount_vnd": 30000,
                    "scope": "item",
                    "target_item_key": "bia-sai-gon",
                }
            ],
            now=NOW,
        )

        with _committed(postgres_engine, postgres_session) as reader:
            stored = SqlAlchemyApiRepository(reader).get_bill(bill.id)

        assert [
            (line.discount_key, line.amount_vnd, line.scope, line.target_item_key)
            for line in stored.discounts
        ] == [("giam-bia", 30000, "item", "bia-sai-gon")]


def _http(session: Session, monkeypatch: pytest.MonkeyPatch):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    return app


def _group(session: Session) -> tuple[Context, Person, Person]:
    an = Person(id=uuid.uuid4(), display_name="An")
    binh = Person(id=uuid.uuid4(), display_name="Bình")
    session.add_all([an, binh])
    session.flush()
    context = Context(
        id=uuid.uuid4(), display_name="Nhóm ăn tối", created_by_id=an.id
    )
    session.add(context)
    session.flush()
    session.add_all(
        [
            Membership(
                id=uuid.uuid4(),
                context_id=context.id,
                person_id=person.id,
                state=MembershipState.ACTIVE,
                role=MembershipRole.MEMBER,
                joined_at=NOW,
            )
            for person in (an, binh)
        ]
    )
    session.flush()
    return context, an, binh


def _headers(person: Person, context: Context) -> dict[str, str]:
    return {
        "X-Actor-ID": str(person.id),
        "X-Actor-Roles": "member,advancer,recipient,batch_owner",
        "X-Actor-Contexts": str(context.id),
    }


def test_the_four_routes_split_a_vat_bill_to_the_printed_total_over_http(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The whole hero seam: scan result in, per-person amounts out.

    Nothing here is stubbed except the clock. If the wire schema drops the
    surcharges, or no column stores them, or the projection is fed empty lists
    again, this lands on 720.000 or on RECONCILIATION_MISMATCH -- the two
    failures that made a real quan an bill unsplittable.
    """

    context, an, binh = _group(postgres_session)
    app = _http(postgres_session, monkeypatch)
    headers = _headers(an, context)

    async def walk():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            created = await client.post(
                "/bills",
                headers=headers,
                json={
                    "context_id": str(context.id),
                    "printed_total_vnd": PRINTED_TOTAL_VND,
                    "items_total_vnd": ITEMS_TOTAL_VND,
                    "confidence": 91,
                    "needs_review": False,
                    "items": [
                        {
                            "item_key": "lau-bo",
                            "name": "Lẩu bò",
                            "quantity": 1,
                            "unit_price_vnd": LAU_BO_VND,
                            "line_total_vnd": LAU_BO_VND,
                            "suggested_participant_ids": [str(an.id), str(binh.id)],
                        },
                        {
                            "item_key": "bia-sai-gon",
                            "name": "Bia Sài Gòn",
                            "quantity": 6,
                            "unit_price_vnd": 50000,
                            "line_total_vnd": BIA_VND,
                            "suggested_participant_ids": [str(binh.id)],
                        },
                    ],
                    "surcharges": [
                        {
                            "surcharge_key": "phi-phuc-vu",
                            "kind": "service",
                            "amount_vnd": SERVICE_CHARGE_VND,
                            "mode": "proportional",
                        },
                        {
                            "surcharge_key": "vat",
                            "kind": "vat",
                            "amount_vnd": VAT_VND,
                            "mode": "proportional",
                        },
                    ],
                    "discounts": [],
                },
            )
            assert created.status_code == 201, created.text
            bill_id = created.json()["id"]
            # POST answers from `_bill_record` on the writing session, before
            # any commit; GET below answers from a fresh read. Asserting only
            # the second would leave the first free to return a shape the
            # client never gets to see.
            assert [
                line["surcharge_key"] for line in created.json()["surcharges"]
            ] == ["phi-phuc-vu", "vat"]

            fetched = await client.get(f"/bills/{bill_id}", headers=headers)
            assert fetched.status_code == 200, fetched.text

            confirmed = await client.put(
                f"/bills/{bill_id}/assignments",
                headers=headers,
                json={
                    "assignments": [
                        {
                            "item_key": "lau-bo",
                            "participant_ids": [str(an.id), str(binh.id)],
                        },
                        {
                            "item_key": "bia-sai-gon",
                            "participant_ids": [str(binh.id)],
                        },
                    ]
                },
            )
            assert confirmed.status_code == 200, confirmed.text

            split = await client.post(
                f"/bills/{bill_id}/split",
                headers=headers,
                json={"for_ledger": True, "paid_by_id": str(binh.id)},
            )
            assert split.status_code == 200, split.text
            return fetched.json(), split.json()

    fetched, split = anyio.run(walk)

    assert [line["amount_vnd"] for line in fetched["surcharges"]] == [
        SERVICE_CHARGE_VND,
        VAT_VND,
    ]
    assert split["total_amount_vnd"] == PRINTED_TOTAL_VND
    # 210.000 + 10.500 + 17.640 for An; 510.000 + 25.500 + 42.840 for Bình.
    assert split["allocation"]["allocations"] == {
        str(an.id): 238140,
        str(binh.id): 578340,
    }
    assert sum(split["allocation"]["allocations"].values()) == PRINTED_TOTAL_VND
