"""Independent offline harness for the handwritten Vietnamese money corpus.

The baseline in this module is intentionally small. It reads only the context
given to a real ``MoneyExtractor`` and never receives a corpus id or expected
answer. It is useful for exposing the difference between replaying an oracle
and actually interpreting text; it is not a production extraction backend.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from app.api.money_skill import run_money_skill
from app.domain.money_skill import extract_vnd_amounts

CORPUS_PATH = Path(__file__).parent / "corpus" / "doc-luong-nhom.json"
SYNTHETIC_GROUP = ("Nam", "Ha", "Quyen", "Linh", "Nam A", "Nam B")

_LABELS = (
    ("ve may bay", "ve may bay"),
    ("tien gui xe", "gui xe"),
    ("gui xe", "gui xe"),
    ("tien khach san", "khach san"),
    ("khach san", "khach san"),
    ("tien nuoc", "tien nuoc"),
    ("bua lau", "bua lau"),
    ("an trua", "an trua"),
    ("an sang", "an sang"),
    ("an toi", "an toi"),
    ("ca phe", "ca phe"),
    ("taxi", "taxi"),
    ("tien ve", "ve"),
    ("tien an", "an"),
    ("xe", "xe"),
)
_MEAL_LABELS = frozenset({"an", "an sang", "an toi", "an trua", "bua lau"})
_FUTURE_MARKERS = ("mai ", "du dinh", "chua tra", "de tinh sau")
_PAID_MARKERS = ("tra roi", "vua tra", "tao tra", "tao ung")


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    without_marks = "".join(
        character for character in decomposed if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"\s+", " ", without_marks.replace("đ", "d")).strip()


def _label_for(text: str) -> str | None:
    for phrase, label in _LABELS:
        if phrase in text:
            return label
    return None


def _missing_amount_question(text: str, label: str) -> str:
    if "tien an hom qua" in text:
        return "bua an hom qua het bao nhieu tien"
    return f"{label} het bao nhieu tien"


class DeterministicVietnameseBaseline:
    """Extract obvious one-message expenses with conservative lexical rules.

    Deliberate non-features are cross-message linking, correction handling,
    duplicate merging, exclusions, and single-beneficiary attribution. Those
    are precisely the discourse behaviours the corpus should make visible.
    """

    def extract(self, context: dict) -> dict:
        expenses: list[dict] = []
        questions: list[str] = []

        for message in context["messages"]:
            text = _plain(message["text"])
            label = _label_for(text)
            amounts = sorted(extract_vnd_amounts(message["text"]))

            if any(marker in text for marker in _FUTURE_MARKERS):
                continue

            if not amounts:
                if label is not None and any(
                    marker in text for marker in _PAID_MARKERS
                ):
                    questions.append(_missing_amount_question(text, label))
                continue

            if label is None:
                continue

            for amount in amounts:
                expenses.append(
                    {
                        "total_vnd": amount,
                        "paid_by": message["author_id"],
                        "label": label,
                        "source_message_ids": [message["id"]],
                    }
                )

            if label in _MEAL_LABELS:
                questions.append(f"ai co mat trong {label}")

        return {"expenses": expenses, "questions": questions}


@dataclass(frozen=True)
class CorpusOutcome:
    """One fully evaluated case, including evidence needed to diagnose it."""

    case_id: str
    expected_expenses: list[dict]
    actual_expenses: list[dict]
    required_questions: list[str]
    actual_questions: list[str]
    safety_notes: list[str]
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


def load_cases(path: Path = CORPUS_PATH) -> list[dict]:
    """Load the handwritten oracle without exposing it to the extractor."""

    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def context_for(case: dict) -> tuple[dict, dict[str, str]]:
    """Build a synthetic manifest and stable opaque member ids for one case."""

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
                "captured_at": "2026-08-28T09:00:00+07:00",
            },
        },
        ids_by_name,
    )


def project_names(result: dict, ids_by_name: dict[str, str]) -> dict:
    """Project opaque ids back to synthetic display names for oracle comparison."""

    names_by_id = {member_id: name for name, member_id in ids_by_name.items()}
    expenses = []
    for raw in result["expenses"]:
        expense = dict(raw)
        expense["paid_by"] = names_by_id[raw["paid_by"]]
        for field in ("excluded", "shared_by_hint"):
            if field in raw:
                expense[field] = [names_by_id[value] for value in raw[field]]
        expenses.append(expense)
    return {"expenses": expenses, "questions": list(result["questions"])}


def compare_case_result(case: dict, actual: dict) -> CorpusOutcome:
    """Compare one result while retaining every handwritten safety note.

    ``must_ask`` is a lower bound, as its name states. Extra questions are not
    treated as extraction errors. Natural-language ``must_not_extract`` notes
    are reported verbatim; their observable examples are enforced by exact
    comparison with the expected expense list.
    """

    expected = case["expected"]
    required_questions = list(expected.get("must_ask", []))
    missing_questions = [
        question
        for question in required_questions
        if question not in actual["questions"]
    ]
    failures = []
    if actual["expenses"] != expected["expenses"]:
        failures.append("EXPENSES_MISMATCH")
    if missing_questions:
        failures.append("MISSING_REQUIRED_QUESTION")

    return CorpusOutcome(
        case_id=case["case_id"],
        expected_expenses=list(expected["expenses"]),
        actual_expenses=list(actual["expenses"]),
        required_questions=required_questions,
        actual_questions=list(actual["questions"]),
        safety_notes=list(expected.get("must_not_extract", [])),
        failures=tuple(failures),
    )


def evaluate_corpus(
    cases: list[dict] | None = None,
    *,
    extractor: object | None = None,
) -> list[CorpusOutcome]:
    """Run every case through ``run_money_skill`` without stopping early."""

    selected_cases = load_cases() if cases is None else cases
    backend = DeterministicVietnameseBaseline() if extractor is None else extractor
    outcomes = []
    for case in selected_cases:
        context, ids_by_name = context_for(case)
        actual = project_names(
            run_money_skill(context, extractor=backend),
            ids_by_name,
        )
        outcomes.append(compare_case_result(case, actual))
    return outcomes
