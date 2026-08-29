"""`GET /contexts/{id}/suggestion` over real HTTP, against real PostgreSQL.

F32 is the one screen in this product that summarises a whole group in five
numbers, and every one of those numbers is a database read. A fake repository
would answer them from a dict it was handed, which proves the route can add up
a fixture. What has to be true is narrower and only a real database can show
it: that the trips, the money and the check-ins all came from *this* group,
that they were recomputed from the ledger rather than read off a stored total,
and that an INVITED link holder gets none of it.

The Gemini backend IS faked here, deliberately -- the same split
`test_companion_postgres.py` makes. What this file proves holds whichever model
is plugged in: that a refused card serves nothing, that no field the contract
did not name survives to the wire, that no coordinate does, and that a private
group's own words never reach a log line. Whether a real model stays inside the
catalogue is a different claim, needs a real call, and belongs in `tests/live`.

Rows here are flushed, never committed; the session fixture rolls back, so the
shared schema keeps the row counts other files assert on.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

import anyio
import httpx
import pytest
from sqlalchemy.orm import Session

from app.api.deps import get_repository, get_suggester
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import (
    Context,
    Membership,
    MembershipRole,
    MembershipState,
    Memory,
    MemoryKind,
    Outing,
    Person,
)
from app.domain.suggestion import SUGGESTION_KIND

from .test_repository_postgres import NOW

pytestmark = pytest.mark.postgres

# NOW is 2030-08-27T12:00Z. Every trip below ends before that Vietnamese day,
# so every trip below is history the suggestion is allowed to reason from.
TRIP_STARTS_ON = date(2030, 8, 21)
TRIP_ENDS_ON = date(2030, 8, 23)
DINNER_VND = 520_000

# Real catalogue identifiers. A test that invented its own would prove the
# route agrees with the test rather than with the catalogue the model is shown.
NUONG = "p-tiem-nuong-xom-lao"
CAFE = "p-lung-chung-cafe"

# A string nobody would produce by accident, planted where a group's own words
# live, so the privacy case can look for it everywhere output goes.
SECRET = "SENTINEL-ten-chuyen-rieng-tu-cua-nhom"


def _card(*place_ids: str, **payload_extra) -> dict:
    return {
        "kind": SUGGESTION_KIND,
        "payload": {
            "title": "Tối thứ Bảy: nướng rồi cà phê",
            "when_text": "Tối thứ Bảy tuần này",
            "stops": [
                {
                    "place_id": place_id,
                    "time_text": "18:00",
                    "note": "Đi sớm cho kịp chỗ ngoài trời",
                    "reason": "Nhóm hay ăn quán local, mức giá vừa ngân sách",
                    "verdict": "hop",
                }
                for place_id in place_ids
            ],
            **payload_extra,
        },
    }


class FakeSuggester:
    """Records what it was handed; returns a canned card."""

    def __init__(self, card: dict | None = None, error: Exception | None = None):
        self.card = card if card is not None else _card(NUONG, CAFE)
        self.error = error
        self.calls: list[dict] = []

    def __call__(self, history: dict, places: list[dict]) -> dict | None:
        self.calls.append({"history": history, "places": places})
        if self.error is not None:
            raise self.error
        return self.card


def _app(session: Session, monkeypatch: pytest.MonkeyPatch, suggester=None):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(session)
    if suggester is not None:
        app.dependency_overrides[get_suggester] = lambda: suggester
    return app


def _call(app, method: str, path: str, *, headers: dict, json: dict | None = None):
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, path, headers=headers, json=json)

    return anyio.run(run)


def _headers(person: Person, context: Context) -> dict[str, str]:
    # Both roles on purpose. A header is a claim, not a proof: membership is
    # what decides, never the role string a caller typed.
    return {
        "X-Actor-ID": str(person.id),
        "X-Actor-Roles": "member,group_admin,advancer",
        "X-Actor-Contexts": str(context.id),
    }


def _person(session: Session, name: str) -> Person:
    person = Person(id=uuid.uuid4(), display_name=name)
    session.add(person)
    session.flush()
    return person


def _member(
    session: Session,
    context: Context,
    person: Person,
    state: MembershipState = MembershipState.ACTIVE,
) -> None:
    session.add(
        Membership(
            id=uuid.uuid4(),
            context_id=context.id,
            person_id=person.id,
            state=state,
            role=MembershipRole.MEMBER,
            joined_at=NOW,
        )
    )
    session.flush()


def _group(session: Session, name: str = "Team Đà Lạt") -> tuple[Context, Person]:
    owner = _person(session, "Minh Anh")
    context = Context(id=uuid.uuid4(), display_name=name, created_by_id=owner.id)
    session.add(context)
    session.flush()
    _member(session, context, owner)
    return context, owner


def _outing(
    session: Session,
    context: Context,
    owner: Person,
    *,
    title: str = "Đà Lạt 2030",
    headcount: int = 4,
) -> Outing:
    outing = Outing(
        id=uuid.uuid4(),
        context_id=context.id,
        created_by_id=owner.id,
        title=title,
        starts_on=TRIP_STARTS_ON,
        ends_on=TRIP_ENDS_ON,
        headcount=headcount,
        budget_per_person_vnd=1_500_000,
        created_at=NOW,
    )
    session.add(outing)
    session.flush()
    return outing


def _checkin(
    session: Session,
    context: Context,
    author: Person,
    place_id: str,
    place_name: str = "Tiệm Nướng Xóm Lào",
) -> None:
    session.add(
        Memory(
            id=uuid.uuid4(),
            context_id=context.id,
            author_id=author.id,
            kind=MemoryKind.CHECKIN,
            image_url=None,
            caption=None,
            place_id=place_id,
            place_name=place_name,
            lat=11.9404,
            lng=108.4583,
            created_at=NOW,
        )
    )
    session.flush()


def _split(
    app,
    context: Context,
    payer: Person,
    others: list[Person],
    *,
    occurred_at: str = "2030-08-22T19:00:00+07:00",
    total: int = DINNER_VND,
) -> None:
    """Split a bill the way the app does it: propose, then confirm.

    Deliberately not hand-written ledger rows. The basis figures have to be the
    ones the product actually writes; a fixture that builds its own ledger
    proves only that the query agrees with the fixture.
    """

    participants = [str(payer.id)] + [str(person.id) for person in others]
    proposal = {
        "context_id": str(context.id),
        "description": "Bữa tối",
        "recorded_by_id": str(payer.id),
        "paid_by_id": str(payer.id),
        "verification_scope": "totals_only",
        "occurred_at": occurred_at,
        "participants": participants,
        "total_amount_vnd": total,
        "items": [],
        "surcharges": [],
        "discounts": [],
    }
    headers = _headers(payer, context)
    proposed = _call(app, "POST", "/expenses", headers=headers, json=proposal)
    assert proposed.status_code == 201, proposed.text
    body = proposed.json()
    confirmed = _call(
        app,
        "POST",
        f"/expenses/{body['expense_id']}/confirm",
        headers=headers,
        json={
            "proposal": body["proposal"],
            "expected_allocations": body["allocation"]["allocations"],
            "acknowledge_as_advancer": True,
        },
    )
    assert confirmed.status_code == 201, confirmed.text


def _suggestion(app, context: Context, person: Person):
    return _call(
        app,
        "GET",
        f"/contexts/{context.id}/suggestion",
        headers=_headers(person, context),
    )


def _group_with_history(session: Session, app, *, title: str = "Đà Lạt 2030"):
    context, owner = _group(session)
    friend = _person(session, "Quang Huy")
    _member(session, context, friend)
    _outing(session, context, owner, title=title)
    _checkin(session, context, owner, NUONG)
    _split(app, context, owner, [friend])
    return context, owner


# ---------------------------------------------------------------------------
# The feature, end to end
# ---------------------------------------------------------------------------


def test_a_group_with_a_past_gets_a_grounded_suggestion(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    suggester = FakeSuggester()
    app = _app(postgres_session, monkeypatch, suggester)
    context, owner = _group_with_history(postgres_session, app)

    response = _suggestion(app, context, owner)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["suggested"] is True
    assert body["source"] == "ai"
    assert [stop["place"]["id"] for stop in body["stops"]] == [NUONG, CAFE]
    # Names, prices and addresses come from the catalogue, never from the model.
    assert body["stops"][0]["place"]["name"] == "Tiệm Nướng Xóm Lào"


def test_the_basis_is_recomputed_from_the_ledger_not_from_the_model(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Invariant 3 pointed at the one screen that argues from the past."""

    suggester = FakeSuggester()
    app = _app(postgres_session, monkeypatch, suggester)
    context, owner = _group_with_history(postgres_session, app)

    body = _suggestion(app, context, owner).json()

    assert body["basis"]["outing_count"] == 1
    assert body["basis"]["split_total_vnd"] == DINNER_VND
    # Integer đồng out of a `numeric` sum. A `Decimal` escaping the driver
    # renders as 520000.0, which only a real database can show.
    assert isinstance(body["basis"]["split_total_vnd"], int)
    assert body["basis"]["avg_per_person_vnd"] == DINNER_VND // 4
    assert body["basis"]["top_categories"] == ["quan-an-local"]


def test_a_group_that_has_never_been_anywhere_is_told_so_without_a_model_call(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """No history is an answer. Inventing a past is not."""

    suggester = FakeSuggester()
    app = _app(postgres_session, monkeypatch, suggester)
    context, owner = _group(postgres_session)

    body = _suggestion(app, context, owner).json()

    assert body["suggested"] is False
    assert body["reason"] == "no_history"
    assert body["stops"] == []
    assert body["source"] == "none"
    assert suggester.calls == []


# ---------------------------------------------------------------------------
# Only this group, and only its ACTIVE members
# ---------------------------------------------------------------------------


def test_a_second_group_history_reaches_neither_the_basis_nor_the_model(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The neighbours' dinner is not this group's evidence.

    Both groups have a finished trip and a check-in on the same days, so a read
    keyed on dates alone -- or on nothing at all -- would fold one into the
    other, in the totals *and* in the prompt.
    """

    suggester = FakeSuggester()
    app = _app(postgres_session, monkeypatch, suggester)
    mine, owner = _group_with_history(postgres_session, app, title="Chuyến của tôi")

    theirs, their_owner = _group(postgres_session, name="Nhóm hàng xóm")
    their_friend = _person(postgres_session, "Người lạ")
    _member(postgres_session, theirs, their_friend)
    _outing(postgres_session, theirs, their_owner, title="Chuyến hàng xóm")
    _checkin(postgres_session, theirs, their_owner, CAFE, "Lưng Chừng Cafe")
    _split(app, theirs, their_owner, [their_friend], total=999_000)

    body = _suggestion(app, mine, owner).json()

    assert body["basis"]["outing_count"] == 1
    assert body["basis"]["split_total_vnd"] == DINNER_VND
    assert body["basis"]["recent_titles"] == ["Chuyến của tôi"]
    assert body["basis"]["top_categories"] == ["quan-an-local"]

    handed = suggester.calls[-1]["history"]
    assert handed["recent_titles"] == ["Chuyến của tôi"]
    assert handed["split_total_vnd"] == DINNER_VND
    assert "Chuyến hàng xóm" not in repr(suggester.calls)


def test_an_invited_link_holder_is_refused(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """INVITED is not ACTIVE, and a suggestion is a read of the group's past."""

    suggester = FakeSuggester()
    app = _app(postgres_session, monkeypatch, suggester)
    context, _owner = _group_with_history(postgres_session, app)
    outsider = _person(postgres_session, "Người vừa bấm link")
    _member(postgres_session, context, outsider, MembershipState.INVITED)

    response = _suggestion(app, context, outsider)

    assert response.status_code == 403, response.text
    assert suggester.calls == []


def test_a_stranger_with_a_context_header_is_refused(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    suggester = FakeSuggester()
    app = _app(postgres_session, monkeypatch, suggester)
    context, _owner = _group_with_history(postgres_session, app)
    stranger = _person(postgres_session, "Không quen ai")

    response = _suggestion(app, context, stranger)

    assert response.status_code == 403, response.text
    assert suggester.calls == []


# ---------------------------------------------------------------------------
# What the model may and may not put on a screen
# ---------------------------------------------------------------------------


def test_an_invented_place_costs_the_whole_card_over_the_wire(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    suggester = FakeSuggester(_card(NUONG, "p-quan-model-tu-nghi-ra"))
    app = _app(postgres_session, monkeypatch, suggester)
    context, owner = _group_with_history(postgres_session, app)

    body = _suggestion(app, context, owner).json()

    assert body["suggested"] is False
    assert body["reason"] == "ungrounded"
    assert body["stops"] == []
    # And the honest basis is still served: the group's past is not the part
    # that went wrong.
    assert body["basis"]["split_total_vnd"] == DINNER_VND


def test_a_key_the_contract_never_named_does_not_reach_the_wire(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    card = _card(NUONG, cta="Đặt bàn ngay", budget_per_person_vnd=999_999)
    card["payload"]["stops"][0]["booking_url"] = "https://khong-phai-cua-san-pham"
    card["payload"]["stops"][0]["name"] = "Tên do model tự đặt"
    suggester = FakeSuggester(card)
    app = _app(postgres_session, monkeypatch, suggester)
    context, owner = _group_with_history(postgres_session, app)

    response = _suggestion(app, context, owner)

    assert response.status_code == 200, response.text
    raw = response.text
    for leaked in ("cta", "booking_url", "Tên do model tự đặt", "999999"):
        assert leaked not in raw
    assert set(response.json()["stops"][0]) == {
        "time_text",
        "note",
        "reason",
        "verdict",
        "place",
    }


def test_no_coordinate_reaches_the_model_or_the_screen(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Check-ins store lat/lng. A suggestion is about where to go, not where
    anybody is, so neither the prompt data nor the response carries a pair."""

    suggester = FakeSuggester()
    app = _app(postgres_session, monkeypatch, suggester)
    context, owner = _group_with_history(postgres_session, app)

    response = _suggestion(app, context, owner)

    assert '"lat"' not in response.text
    assert '"lng"' not in response.text
    assert "11.9404" not in response.text
    handed = repr(suggester.calls)
    assert "11.9404" not in handed
    assert "108.4583" not in handed


def test_a_half_pair_arrives_as_neither_half(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    card = _card(NUONG)
    card["payload"]["stops"][0]["verdict"] = None
    suggester = FakeSuggester(card)
    app = _app(postgres_session, monkeypatch, suggester)
    context, owner = _group_with_history(postgres_session, app)

    stop = _suggestion(app, context, owner).json()["stops"][0]

    assert stop["reason"] is None
    assert stop["verdict"] is None


def test_a_backend_that_raises_is_silence_not_a_five_hundred(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch
):
    suggester = FakeSuggester(error=RuntimeError("boom"))
    app = _app(postgres_session, monkeypatch, suggester)
    context, owner = _group_with_history(postgres_session, app)

    response = _suggestion(app, context, owner)

    assert response.status_code == 200, response.text
    assert response.json()["reason"] == "unavailable"


def test_the_group_own_words_never_reach_a_log_line(
    postgres_session: Session, monkeypatch: pytest.MonkeyPatch, caplog
):
    """A refused card is logged by code. The trip title is the group's, not ours."""

    suggester = FakeSuggester(_card("p-khong-co-that"))
    app = _app(postgres_session, monkeypatch, suggester)
    context, owner = _group_with_history(postgres_session, app, title=SECRET)

    with caplog.at_level(logging.DEBUG):
        response = _suggestion(app, context, owner)

    assert response.json()["reason"] == "ungrounded"
    assert SECRET not in caplog.text
    assert "p-khong-co-that" not in caplog.text
