"""`POST /bills/{id}/split` names its participants -- against real PostgreSQL.

The fake in `tests/api/conftest.py` hardcodes `state="active"` for every row
`list_members` returns, so the case that matters most here is unreachable
there: the sibling file has to hand `split_bill` a hand-built roster to make
an invitation exist at all. That proves the partition in Python and nothing
about the query, and the query is the claim -- `excluded_member_ids` is only
ever non-empty because `list_members` filters on `left_at IS NULL` rather
than on `state`, and so returns invitations alongside members.

So this file writes a real `memberships` row with `state = 'invited'`, asks
the real route over HTTP, and reads the answer. What it proves that the fake
cannot: the roster SQL really does hand the service a row the split will not
pay, and the response really does name that person instead of leaving the
client to wonder whether the server has never heard of them.
"""

from __future__ import annotations

import uuid

import anyio
import httpx
import pytest
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

PHO = 120_000
NEM = 80_000
TOTAL = PHO + NEM


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


def _member(session: Session, context_id: uuid.UUID, person: Person, state) -> None:
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context_id,
            person_id=person.id,
            state=state,
            role=MembershipRole.MEMBER,
            # An invitation records that somebody was asked, not that they
            # arrived, so it carries no `joined_at`.
            joined_at=NOW if state is MembershipState.ACTIVE else None,
        )
    )
    session.flush()


@pytest.fixture
def table(postgres_session, monkeypatch):
    """Two people eating, one person invited and not yet arrived."""

    app = _app(postgres_session, monkeypatch)
    an = _person(postgres_session, "An")
    binh = _person(postgres_session, "Bình")
    chi = _person(postgres_session, "Chi")
    context = Context(
        id=uuid.uuid4(), display_name="Bữa tối thứ bảy", created_by_id=an.id
    )
    postgres_session.add(context)
    postgres_session.flush()
    _member(postgres_session, context.id, an, MembershipState.ACTIVE)
    _member(postgres_session, context.id, binh, MembershipState.ACTIVE)
    _member(postgres_session, context.id, chi, MembershipState.INVITED)

    created = _request(
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
                    "suggested_participant_ids": [str(an.id)],
                },
                {
                    "item_key": "nem",
                    "name": "Nem rán",
                    "quantity": 1,
                    "unit_price_vnd": NEM,
                    "line_total_vnd": NEM,
                    "suggested_participant_ids": [str(binh.id)],
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    return {
        "app": app,
        "an": an,
        "binh": binh,
        "chi": chi,
        "bill_id": uuid.UUID(created.json()["id"]),
    }


def _split(table) -> dict:
    response = _request(
        table["app"],
        "POST",
        f"/bills/{table['bill_id']}/split",
        headers=_headers(table["an"].id),
        json={"for_ledger": False},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_the_route_names_the_two_people_it_divided_the_bill_between(table):
    body = _split(table)

    assert set(body["participant_ids"]) == {
        str(table["an"].id),
        str(table["binh"].id),
    }
    assert set(body["participant_ids"]) == set(body["allocation"]["allocations"])
    assert sum(body["allocation"]["allocations"].values()) == TOTAL


def test_the_route_names_the_invited_row_the_roster_query_returned(table):
    """The case the fake cannot reach: `state = 'invited'`, written to the DB.

    A `list_members` that filtered on `state` instead of `left_at` would never
    hand the service this row, `excluded_member_ids` would come back empty,
    and the client would be back to guessing why Chi has no line.
    """

    body = _split(table)

    assert body["excluded_member_ids"] == [str(table["chi"].id)]
    assert str(table["chi"].id) not in body["allocation"]["allocations"]


def test_an_invited_person_is_not_charged_a_dong(table):
    """Negative control: naming somebody must not be a step towards paying them.

    Reporting the excluded row is a statement about the roster. If it ever
    became a statement about the split -- one `participant_ids | excluded`
    away -- the printed total would be divided three ways and the two who ate
    would each be undercharged.
    """

    body = _split(table)
    allocations = body["allocation"]["allocations"]

    assert allocations[str(table["an"].id)] == PHO
    assert allocations[str(table["binh"].id)] == NEM
    assert len(allocations) == 2
