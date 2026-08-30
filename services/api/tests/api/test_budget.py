"""F34 HTTP orchestration over a fake ledger-backed recap repository."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.api.repository import OutingRecord, RecapOutingRecord

from .helpers import CONTEXT_ID, OTHER_ID, actor_headers

NOW = datetime(2030, 8, 30, 8, 0, tzinfo=UTC)


def _record(
    *,
    title: str,
    headcount: int,
    budget_per_person_vnd: int,
    split_total_vnd: int,
    in_progress: bool,
) -> RecapOutingRecord:
    outing = OutingRecord(
        id=uuid.uuid4(),
        context_id=CONTEXT_ID,
        created_by_id=uuid.uuid4(),
        title=title,
        starts_on=date(2030, 8, 20),
        ends_on=date(2030, 8, 30) if in_progress else date(2030, 8, 23),
        headcount=headcount,
        budget_per_person_vnd=budget_per_person_vnd,
        created_at=NOW,
        stops=(),
    )
    return RecapOutingRecord(
        outing=outing,
        in_progress=in_progress,
        split_total_vnd=split_total_vnd,
        expense_count=1,
        memory_count=0,
    )


@pytest.fixture
def budget_records(repository, monkeypatch):
    records: list[RecapOutingRecord] = []
    monkeypatch.setattr(
        repository,
        "group_recap",
        lambda context_id, *, today: tuple(records),
        raising=False,
    )
    return records


def _get(client, query: str = ""):
    return client.get(
        f"/contexts/{CONTEXT_ID}/budget{query}",
        headers=actor_headers(),
    )


def test_group_budget_route_declares_no_request_body(client) -> None:
    operation = client.app.openapi()["paths"]["/contexts/{context_id}/budget"][
        "get"
    ]

    assert "requestBody" not in operation


def test_group_budget_returns_history_live_ledger_spend_and_comparison(
    client, budget_records
) -> None:
    budget_records.extend(
        [
            _record(
                title="Đà Lạt",
                headcount=4,
                budget_per_person_vnd=300_000,
                split_total_vnd=1_200_000,
                in_progress=False,
            ),
            _record(
                title="Nướng cuối tuần",
                headcount=5,
                budget_per_person_vnd=250_000,
                split_total_vnd=800_000,
                in_progress=False,
            ),
            _record(
                title="Đang đi biển",
                headcount=3,
                budget_per_person_vnd=300_000,
                split_total_vnd=1_000_001,
                in_progress=True,
            ),
        ]
    )

    response = _get(client, "?candidate_per_person_vnd=450000")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["context_id"] == str(CONTEXT_ID)
    assert body["outing_count"] == 2
    assert body["active_member_count"] == 2
    assert body["avg_per_person_vnd"] == 222_222
    assert body["in_progress"] == [
        {
            "outing_id": str(budget_records[2].outing.id),
            "title": "Đang đi biển",
            "headcount": 3,
            "budget_per_person_vnd": 300_000,
            "spent_per_person_vnd": 333_333,
            "remaining_per_person_vnd": -33_333,
            "over_budget": True,
        }
    ]
    assert body["comparison"] == {
        "candidate_per_person_vnd": 450_000,
        "delta_vnd": 227_778,
        "verdict": "cao-hon",
    }


def test_group_budget_without_history_refuses_to_invent_a_comparison(
    client, budget_records
) -> None:
    budget_records.append(
        _record(
            title="Đang đi",
            headcount=2,
            budget_per_person_vnd=300_000,
            split_total_vnd=100_000,
            in_progress=True,
        )
    )

    response = _get(client, "?candidate_per_person_vnd=450000")

    assert response.status_code == 200
    assert response.json()["avg_per_person_vnd"] is None
    assert response.json()["comparison"] is None


def test_group_budget_without_candidate_omits_comparison(
    client, budget_records
) -> None:
    budget_records.append(
        _record(
            title="Đã đi",
            headcount=2,
            budget_per_person_vnd=300_000,
            split_total_vnd=360_000,
            in_progress=False,
        )
    )

    response = _get(client)

    assert response.status_code == 200
    assert response.json()["avg_per_person_vnd"] == 180_000
    assert response.json()["comparison"] is None


def test_group_budget_requires_active_membership_before_reading_ledger(
    client, repository, monkeypatch
) -> None:
    calls: list[uuid.UUID] = []

    def forbidden_read(context_id, *, today):
        del today
        calls.append(context_id)
        return ()

    monkeypatch.setattr(repository, "group_recap", forbidden_read, raising=False)

    response = client.get(
        f"/contexts/{CONTEXT_ID}/budget",
        headers=actor_headers(actor_id=OTHER_ID),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"
    assert calls == []


@pytest.mark.parametrize("candidate", ["-1", "180000.0", "true", "not-money"])
def test_group_budget_rejects_an_invalid_candidate_query(
    client, budget_records, candidate: str
) -> None:
    response = _get(client, f"?candidate_per_person_vnd={candidate}")

    assert response.status_code == 422


def test_budget_outing_schema_ties_remaining_to_over_budget() -> None:
    from app.api.schemas import BudgetOutingView

    fields = {
        "outing_id": uuid.uuid4(),
        "title": "Đang đi",
        "headcount": 2,
        "budget_per_person_vnd": 300_000,
        "spent_per_person_vnd": 350_000,
        "remaining_per_person_vnd": -50_000,
        "over_budget": True,
    }

    assert BudgetOutingView(**fields).over_budget is True
    with pytest.raises(ValidationError):
        BudgetOutingView(**{**fields, "over_budget": False})


@pytest.mark.parametrize(
    ("model_name", "field_name", "bad_value", "fields"),
    [
        (
            "BudgetOutingView",
            "budget_per_person_vnd",
            300_000.0,
            {
                "outing_id": uuid.uuid4(),
                "title": "Đang đi",
                "headcount": 2,
                "budget_per_person_vnd": 300_000,
                "spent_per_person_vnd": 350_000,
                "remaining_per_person_vnd": -50_000,
                "over_budget": True,
            },
        ),
        (
            "BudgetOutingView",
            "spent_per_person_vnd",
            True,
            {
                "outing_id": uuid.uuid4(),
                "title": "Đang đi",
                "headcount": 2,
                "budget_per_person_vnd": 300_000,
                "spent_per_person_vnd": 350_000,
                "remaining_per_person_vnd": -50_000,
                "over_budget": True,
            },
        ),
        (
            "BudgetOutingView",
            "remaining_per_person_vnd",
            "-50000",
            {
                "outing_id": uuid.uuid4(),
                "title": "Đang đi",
                "headcount": 2,
                "budget_per_person_vnd": 300_000,
                "spent_per_person_vnd": 350_000,
                "remaining_per_person_vnd": -50_000,
                "over_budget": True,
            },
        ),
        (
            "BudgetComparison",
            "candidate_per_person_vnd",
            450_000.0,
            {
                "candidate_per_person_vnd": 450_000,
                "delta_vnd": 270_000,
                "verdict": "cao-hon",
            },
        ),
        (
            "BudgetComparison",
            "delta_vnd",
            True,
            {
                "candidate_per_person_vnd": 450_000,
                "delta_vnd": 270_000,
                "verdict": "cao-hon",
            },
        ),
    ],
)
def test_group_budget_response_money_fields_are_strict(
    model_name: str,
    field_name: str,
    bad_value,
    fields: dict,
) -> None:
    from app.api import schemas

    model = getattr(schemas, model_name)
    with pytest.raises(ValidationError):
        model(**{**fields, field_name: bad_value})
