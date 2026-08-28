"""Offline contract tests for ADR-0009's draft money skill.

The corpus run proves orchestration and deterministic validation only. The fake
does not measure whether any real extraction model can recover these answers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api.money_skill import run_money_skill
from app.domain.money_skill import MoneySkillError, extract_vnd_amounts
from tests.skills.fakes import DeterministicMoneyExtractor

CORPUS_PATH = Path(__file__).parent / "corpus" / "doc-luong-nhom.json"
SYNTHETIC_GROUP = ("Nam", "Ha", "Quyen", "Linh", "Nam A", "Nam B")

FAKE_RESPONSES = {
    "01-ro-rang": {
        "expenses": [
            {
                "total_vnd": 800_000,
                "paid_by": "Nam",
                "label": "an toi",
                "source_message_ids": ["m1"],
            }
        ],
        "questions": ["ai co mat trong bua an toi"],
    },
    "02-so-tien-o-tin-nhan-sau": {
        "expenses": [
            {
                "total_vnd": 1_200_000,
                "paid_by": "Quyen",
                "label": "khach san",
                "source_message_ids": ["m1", "m3"],
            }
        ],
        "questions": [],
    },
    "03-cac-cach-viet-so": {
        "expenses": [
            {
                "total_vnd": 300_000,
                "paid_by": "Nam",
                "label": "xe",
                "source_message_ids": ["m1"],
            },
            {
                "total_vnd": 85_000,
                "paid_by": "Ha",
                "label": "an sang",
                "source_message_ids": ["m2"],
            },
            {
                "total_vnd": 2_350_000,
                "paid_by": "Quyen",
                "label": "ve may bay",
                "source_message_ids": ["m3"],
            },
            {
                "total_vnd": 120_000,
                "paid_by": "Linh",
                "label": "ca phe",
                "source_message_ids": ["m4"],
            },
        ],
        "questions": [],
    },
    "04-noi-dua-khong-phai-khoan-chi": {
        "expenses": [
            {
                "total_vnd": 60_000,
                "paid_by": "Quyen",
                "label": "tien nuoc",
                "source_message_ids": ["m3"],
            }
        ],
        "questions": [],
    },
    "05-loai-tru-nguoi": {
        "expenses": [
            {
                "total_vnd": 1_000_000,
                "paid_by": "Nam",
                "label": "bua lau",
                "excluded": ["Linh"],
                "source_message_ids": ["m1", "m2"],
            }
        ],
        "questions": [],
    },
    "06-them-muon": {
        "expenses": [
            {
                "total_vnd": 450_000,
                "paid_by": "Nam",
                "label": "an trua",
                "source_message_ids": ["m1"],
            },
            {
                "total_vnd": 50_000,
                "paid_by": "Nam",
                "label": "gui xe",
                "source_message_ids": ["m4"],
            },
        ],
        "questions": [],
    },
    "07-sua-lai-so": {
        "expenses": [
            {
                "total_vnd": 1_800_000,
                "paid_by": "Quyen",
                "label": "khach san",
                "source_message_ids": ["m1", "m2"],
            }
        ],
        "questions": [],
    },
    "08-hai-nguoi-ke-cung-mot-khoan": {
        "expenses": [
            {
                "total_vnd": 200_000,
                "paid_by": "Nam",
                "label": "taxi",
                "source_message_ids": ["m1", "m2"],
            }
        ],
        "questions": [],
    },
    "09-du-dinh-khong-phai-da-chi": {"expenses": [], "questions": []},
    "10-tra-ho-mot-nguoi": {
        "expenses": [
            {
                "total_vnd": 320_000,
                "paid_by": "Nam",
                "shared_by_hint": ["Linh"],
                "label": "ve cua Linh",
                "source_message_ids": ["m1"],
            }
        ],
        "questions": [],
    },
    "11-khong-du-chac-chan": {
        "expenses": [],
        "questions": ["bua an hom qua het bao nhieu tien"],
    },
    "12-nguoi-trung-ten": {
        "expenses": [
            {
                "total_vnd": 600_000,
                "paid_by": "Nam A",
                "label": "an",
                "source_message_ids": ["m1"],
            }
        ],
        "questions": [],
    },
}


def _load_cases() -> list[dict]:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["cases"]


def _context_for(case: dict) -> tuple[dict, dict[str, str]]:
    ids_by_name = {
        name: f"synthetic-member-{index}"
        for index, name in enumerate(SYNTHETIC_GROUP, start=1)
    }
    messages = [
        {
            "id": message["id"],
            "author_id": ids_by_name[message["author"]],
            "text": message["text"],
        }
        for message in case["messages"]
    ]
    return (
        {
            "group_members": [
                {"id": member_id, "display_name": name}
                for name, member_id in ids_by_name.items()
            ],
            "messages": messages,
            "context_manifest": {
                "first_message_id": messages[0]["id"],
                "last_message_id": messages[-1]["id"],
                "message_count": len(messages),
                "captured_at": "2026-08-27T09:00:00+07:00",
            },
        },
        ids_by_name,
    )


def _wire_fake_response(response: dict, ids_by_name: dict[str, str]) -> dict:
    result = {"expenses": [], "questions": list(response["questions"])}
    for raw in response["expenses"]:
        expense = dict(raw)
        expense["paid_by"] = ids_by_name[raw["paid_by"]]
        for field in ("excluded", "shared_by_hint"):
            if field in raw:
                expense[field] = [ids_by_name[name] for name in raw[field]]
        result["expenses"].append(expense)
    return result


def _project_names(result: dict, ids_by_name: dict[str, str]) -> dict:
    names_by_id = {member_id: name for name, member_id in ids_by_name.items()}
    expenses = []
    for raw in result["expenses"]:
        expense = dict(raw)
        expense["paid_by"] = names_by_id[raw["paid_by"]]
        for field in ("excluded", "shared_by_hint"):
            if field in raw:
                expense[field] = [names_by_id[value] for value in raw[field]]
        expenses.append(expense)
    return {"expenses": expenses, "questions": result["questions"]}


@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: case["case_id"])
def test_handwritten_corpus_runs_offline_through_deterministic_fake(case):
    context, ids_by_name = _context_for(case)
    fake = DeterministicMoneyExtractor(
        _wire_fake_response(FAKE_RESPONSES[case["case_id"]], ids_by_name)
    )

    result = _project_names(
        run_money_skill(context, extractor=fake),
        ids_by_name,
    )

    assert result["expenses"] == case["expected"]["expenses"]
    assert result["questions"] == case["expected"].get("must_ask", [])
    assert len(fake.calls) == 1


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1tr2", {1_200_000}),
        ("1 triệu 2", {1_200_000}),
        ("1.200.000", {1_200_000}),
        ("1200k", {1_200_000}),
        ("vé 2tr350", {2_350_000}),
        ("ăn sáng 85 nghìn", {85_000}),
        ("cà phê 120.000", {120_000}),
        ("đã trả 800000 đồng", {800_000}),
    ],
)
def test_amount_normalization_vectors(text, expected):
    assert extract_vnd_amounts(text) == expected


def test_validator_drops_hallucinated_amount_and_asks_for_review():
    case = _load_cases()[0]
    context, ids_by_name = _context_for(case)
    fake = DeterministicMoneyExtractor(
        {
            "expenses": [
                {
                    "total_vnd": 900_000,
                    "paid_by": ids_by_name["Nam"],
                    "label": "an toi",
                    "source_message_ids": ["m1"],
                }
            ],
            "questions": [],
        }
    )

    result = run_money_skill(context, extractor=fake)

    assert result["expenses"] == []
    assert len(result["questions"]) == 1


def test_validator_drops_candidate_with_confidence_field():
    case = _load_cases()[0]
    context, ids_by_name = _context_for(case)
    fake = DeterministicMoneyExtractor(
        {
            "expenses": [
                {
                    "total_vnd": 800_000,
                    "paid_by": ids_by_name["Nam"],
                    "label": "an toi",
                    "source_message_ids": ["m1"],
                    "confidence": 99,
                }
            ],
            "questions": [],
        }
    )

    result = run_money_skill(context, extractor=fake)

    assert result["expenses"] == []
    assert result["questions"]


def test_paid_by_must_be_a_member_id_not_a_display_name():
    case = _load_cases()[0]
    context, _ = _context_for(case)
    fake = DeterministicMoneyExtractor(
        {
            "expenses": [
                {
                    "total_vnd": 800_000,
                    "paid_by": "Nam",
                    "label": "an toi",
                    "source_message_ids": ["m1"],
                }
            ],
            "questions": [],
        }
    )

    result = run_money_skill(context, extractor=fake)

    assert result["expenses"] == []
    assert result["questions"]


@pytest.mark.parametrize("bad_total", [True, 800_000.0, "800000", 0, -1])
def test_total_vnd_is_a_strict_positive_integer(bad_total):
    case = _load_cases()[0]
    context, ids_by_name = _context_for(case)
    fake = DeterministicMoneyExtractor(
        {
            "expenses": [
                {
                    "total_vnd": bad_total,
                    "paid_by": ids_by_name["Nam"],
                    "label": "an toi",
                    "source_message_ids": ["m1"],
                }
            ],
            "questions": [],
        }
    )

    result = run_money_skill(context, extractor=fake)

    assert result["expenses"] == []


def test_source_message_must_be_inside_manifest_snapshot():
    case = _load_cases()[0]
    context, ids_by_name = _context_for(case)
    fake = DeterministicMoneyExtractor(
        {
            "expenses": [
                {
                    "total_vnd": 800_000,
                    "paid_by": ids_by_name["Nam"],
                    "label": "an toi",
                    "source_message_ids": ["outside"],
                }
            ],
            "questions": [],
        }
    )

    result = run_money_skill(context, extractor=fake)

    assert result["expenses"] == []
    assert result["questions"]


def test_context_limit_fails_before_extractor_is_called():
    case = _load_cases()[0]
    context, _ = _context_for(case)
    fake = DeterministicMoneyExtractor({"expenses": [], "questions": []})

    with pytest.raises(MoneySkillError, match="CONTEXT_TOO_LONG") as caught:
        run_money_skill(context, extractor=fake, max_messages=1)

    assert caught.value.code == "CONTEXT_TOO_LONG"
    assert fake.calls == []


def test_context_manifest_must_match_the_actual_snapshot():
    case = _load_cases()[0]
    context, _ = _context_for(case)
    context["context_manifest"]["message_count"] = 99
    fake = DeterministicMoneyExtractor({"expenses": [], "questions": []})

    with pytest.raises(MoneySkillError) as caught:
        run_money_skill(context, extractor=fake)

    assert caught.value.code == "CONTEXT_MANIFEST_COUNT_MISMATCH"
    assert fake.calls == []


def test_extractor_cannot_mutate_the_snapshot_used_for_grounding():
    case = _load_cases()[0]
    context, ids_by_name = _context_for(case)

    class MutatingExtractor:
        def extract(self, mutable_context):
            mutable_context["messages"][0]["text"] = "an toi 900k"
            return {
                "expenses": [
                    {
                        "total_vnd": 900_000,
                        "paid_by": ids_by_name["Nam"],
                        "label": "an toi",
                        "source_message_ids": ["m1"],
                    }
                ],
                "questions": [],
            }

    result = run_money_skill(context, extractor=MutatingExtractor())

    assert result["expenses"] == []
    assert result["questions"]
    assert context["messages"][0]["text"] == "tao vua tra tien an toi 800k nhe"
