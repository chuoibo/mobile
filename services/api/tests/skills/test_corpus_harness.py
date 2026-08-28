"""Regression tests for the independent money-skill corpus harness."""

from __future__ import annotations

from copy import deepcopy

import pytest

from tests.skills.corpus_harness import (
    compare_case_result,
    evaluate_corpus,
    load_cases,
)


def test_baseline_reports_every_case_and_does_not_stop_at_first_failure():
    outcomes = evaluate_corpus()

    assert len(outcomes) == 12
    assert [outcome.case_id for outcome in outcomes if not outcome.passed] == [
        "02-so-tien-o-tin-nhan-sau",
        "05-loai-tru-nguoi",
        "07-sua-lai-so",
        "08-hai-nguoi-ke-cung-mot-khoan",
        "10-tra-ho-mot-nguoi",
    ]


@pytest.mark.parametrize(
    "case_id",
    [
        "04-noi-dua-khong-phai-khoan-chi",
        "07-sua-lai-so",
        "09-du-dinh-khong-phai-da-chi",
        "12-nguoi-trung-ten",
    ],
)
def test_must_not_extract_cases_keep_their_safety_note_and_reject_extra_expense(
    case_id,
):
    case = next(case for case in load_cases() if case["case_id"] == case_id)
    actual = {
        "expenses": deepcopy(case["expected"]["expenses"]),
        "questions": list(case["expected"].get("must_ask", [])),
    }
    actual["expenses"].append(
        {
            "total_vnd": 999_000,
            "paid_by": "Nam",
            "label": "mutant",
            "source_message_ids": ["m1"],
        }
    )

    outcome = compare_case_result(case, actual)

    assert outcome.failures == ("EXPENSES_MISMATCH",)
    assert outcome.safety_notes == case["expected"]["must_not_extract"]


def test_must_ask_is_a_required_subset_not_an_exact_question_script():
    case = load_cases()[0]
    actual = {
        "expenses": deepcopy(case["expected"]["expenses"]),
        "questions": [
            *case["expected"]["must_ask"],
            "co can bo sung thong tin gi khac khong",
        ],
    }

    assert compare_case_result(case, actual).passed


def test_missing_required_question_is_reported_together_with_expense_failure():
    case = load_cases()[0]
    outcome = compare_case_result(case, {"expenses": [], "questions": []})

    assert outcome.failures == (
        "EXPENSES_MISMATCH",
        "MISSING_REQUIRED_QUESTION",
    )
