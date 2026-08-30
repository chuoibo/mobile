"""Pure F34 arithmetic for comparing one candidate with group history."""

from __future__ import annotations

import ast
import inspect
from importlib import import_module

import pytest


def _contract():
    return import_module("app.domain.budget")


def _outing(
    *,
    outing_id: str = "outing-1",
    title: str = "Đà Lạt",
    headcount: int = 4,
    budget_per_person_vnd: int = 300_000,
    split_total_vnd: int = 1_200_000,
    in_progress: bool = False,
) -> dict:
    return {
        "outing_id": outing_id,
        "title": title,
        "headcount": headcount,
        "budget_per_person_vnd": budget_per_person_vnd,
        "split_total_vnd": split_total_vnd,
        "in_progress": in_progress,
    }


def test_budget_computes_history_current_spend_and_candidate_together() -> None:
    module = _contract()
    trips = [
        _outing(),
        _outing(
            outing_id="outing-2",
            title="Nướng cuối tuần",
            headcount=5,
            split_total_vnd=800_000,
        ),
        _outing(
            outing_id="outing-live",
            title="Đang đi biển",
            headcount=3,
            budget_per_person_vnd=300_000,
            split_total_vnd=1_000_001,
            in_progress=True,
        ),
    ]

    result = module.build_group_budget(
        trips,
        active_member_count=2,
        candidate_per_person_vnd=450_000,
    )

    assert result == {
        "outing_count": 2,
        "active_member_count": 2,
        "avg_per_person_vnd": 222_222,
        "in_progress": [
            {
                "outing_id": "outing-live",
                "title": "Đang đi biển",
                "headcount": 3,
                "budget_per_person_vnd": 300_000,
                "spent_per_person_vnd": 333_333,
                "remaining_per_person_vnd": -33_333,
                "over_budget": True,
            }
        ],
        "comparison": {
            "candidate_per_person_vnd": 450_000,
            "delta_vnd": 227_778,
            "verdict": "cao-hon",
        },
    }


def test_budget_uses_floor_division_for_every_per_person_figure() -> None:
    module = _contract()
    result = module.build_group_budget(
        [
            _outing(headcount=3, split_total_vnd=10),
            _outing(
                outing_id="live",
                headcount=3,
                split_total_vnd=11,
                in_progress=True,
            ),
        ],
        active_member_count=1,
        candidate_per_person_vnd=None,
    )

    assert result["avg_per_person_vnd"] == 3
    assert result["in_progress"][0]["spent_per_person_vnd"] == 3
    assert type(result["avg_per_person_vnd"]) is int
    assert type(result["in_progress"][0]["spent_per_person_vnd"]) is int


def test_budget_module_contains_no_true_division_rounding_or_decimal() -> None:
    module = _contract()
    tree = ast.parse(inspect.getsource(module))

    assert not any(isinstance(node, ast.Div) for node in ast.walk(tree))
    assert not any(
        isinstance(node, ast.Name) and node.id in {"round", "Decimal"}
        for node in ast.walk(tree)
    )


@pytest.mark.parametrize(
    ("candidate", "verdict"),
    [
        (161_999, "re-hon"),
        (162_000, "nhu-thuong"),
        (198_000, "nhu-thuong"),
        (198_001, "cao-hon"),
    ],
)
def test_budget_comparison_has_an_inclusive_ten_percent_band(
    candidate: int, verdict: str
) -> None:
    module = _contract()

    result = module.build_group_budget(
        [_outing(headcount=3, split_total_vnd=540_000)],
        active_member_count=3,
        candidate_per_person_vnd=candidate,
    )

    assert result["avg_per_person_vnd"] == 180_000
    assert result["comparison"] == {
        "candidate_per_person_vnd": candidate,
        "delta_vnd": candidate - 180_000,
        "verdict": verdict,
    }


def test_budget_without_a_candidate_has_no_comparison() -> None:
    module = _contract()

    result = module.build_group_budget(
        [_outing()],
        active_member_count=2,
        candidate_per_person_vnd=None,
    )

    assert result["comparison"] is None


def test_budget_without_finished_history_does_not_invent_a_baseline() -> None:
    module = _contract()

    result = module.build_group_budget(
        [_outing(in_progress=True)],
        active_member_count=2,
        candidate_per_person_vnd=450_000,
    )

    assert result["outing_count"] == 0
    assert result["avg_per_person_vnd"] is None
    assert result["comparison"] is None


def test_budget_zero_completed_headcount_has_no_baseline_or_division() -> None:
    module = _contract()

    result = module.build_group_budget(
        [_outing(headcount=0, split_total_vnd=0)],
        active_member_count=0,
        candidate_per_person_vnd=450_000,
    )

    assert result["outing_count"] == 1
    assert result["active_member_count"] == 0
    assert result["avg_per_person_vnd"] is None
    assert result["comparison"] is None


def test_budget_zero_live_headcount_is_explicitly_zero_not_a_500() -> None:
    module = _contract()

    result = module.build_group_budget(
        [
            _outing(
                headcount=0,
                budget_per_person_vnd=400_000,
                split_total_vnd=340_000,
                in_progress=True,
            )
        ],
        active_member_count=0,
        candidate_per_person_vnd=None,
    )

    assert result["in_progress"][0]["spent_per_person_vnd"] == 0
    assert result["in_progress"][0]["remaining_per_person_vnd"] == 400_000
    assert result["in_progress"][0]["over_budget"] is False


def test_budget_zero_baseline_compares_without_dividing() -> None:
    module = _contract()

    same = module.build_group_budget(
        [_outing(headcount=2, split_total_vnd=0)],
        active_member_count=2,
        candidate_per_person_vnd=0,
    )
    higher = module.build_group_budget(
        [_outing(headcount=2, split_total_vnd=0)],
        active_member_count=2,
        candidate_per_person_vnd=1,
    )

    assert same["comparison"]["verdict"] == "nhu-thuong"
    assert higher["comparison"]["verdict"] == "cao-hon"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("headcount", True),
        ("headcount", 2.0),
        ("headcount", -1),
        ("budget_per_person_vnd", True),
        ("budget_per_person_vnd", 300_000.0),
        ("budget_per_person_vnd", -1),
        ("split_total_vnd", True),
        ("split_total_vnd", 300_000.0),
        ("split_total_vnd", -1),
        ("in_progress", 1),
    ],
)
def test_budget_rejects_malformed_repository_facts(field: str, value) -> None:
    module = _contract()

    with pytest.raises(module.BudgetError) as caught:
        module.build_group_budget(
            [_outing(**{field: value})],
            active_member_count=2,
            candidate_per_person_vnd=None,
        )

    assert caught.value.code == "INVALID_BUDGET_INPUT"


@pytest.mark.parametrize("candidate", [True, 180_000.0, "180000", -1])
def test_budget_rejects_non_integer_or_negative_candidates(candidate) -> None:
    module = _contract()

    with pytest.raises(module.BudgetError) as caught:
        module.build_group_budget(
            [_outing()],
            active_member_count=2,
            candidate_per_person_vnd=candidate,
        )

    assert caught.value.code == "INVALID_BUDGET_INPUT"


@pytest.mark.parametrize("active_member_count", [True, 2.0, "2", -1])
def test_budget_rejects_malformed_active_member_counts(active_member_count) -> None:
    module = _contract()

    with pytest.raises(module.BudgetError) as caught:
        module.build_group_budget(
            [_outing()],
            active_member_count=active_member_count,
            candidate_per_person_vnd=None,
        )

    assert caught.value.code == "INVALID_BUDGET_INPUT"
