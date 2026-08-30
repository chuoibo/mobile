"""Pure validation for the model-independent ``money_skill`` contract.

The extraction backend may be probabilistic. This module is deliberately not:
it validates the explicit context snapshot and rejects any extracted expense
that cannot be grounded in that snapshot. It never allocates an expense.
"""

from __future__ import annotations

import re
from datetime import datetime

from .contract import MAX_AMOUNT_VND
from .money import count_violation, vnd_violation

__all__ = [
    "DEFAULT_MAX_MESSAGES",
    "MoneySkillError",
    "extract_vnd_amounts",
    "validate_context",
    "validate_extraction",
]


DEFAULT_MAX_MESSAGES = 200

_GROUPED_AMOUNT = re.compile(r"(?<![\w.,])\d{1,3}(?:[.,]\d{3})+(?![\w.,])")
_MILLION_AMOUNT = re.compile(
    r"(?<!\w)(\d+)\s*(?:tr|tri[eệ]u)\s*(\d{1,3})?(?!\w)",
    re.IGNORECASE,
)
_THOUSAND_AMOUNT = re.compile(
    r"(?<!\w)(\d[\d.,]*)\s*(?:k|ngh[iì]n|ng[aà]n)(?!\w)",
    re.IGNORECASE,
)
_PLAIN_AMOUNT = re.compile(r"(?<![\w.,])\d{4,}(?![\w.,])")

_EXPENSE_KEYS = frozenset(
    {
        "total_vnd",
        "paid_by",
        "label",
        "source_message_ids",
        "excluded",
        "shared_by_hint",
    }
)
_REQUIRED_EXPENSE_KEYS = frozenset(
    {"total_vnd", "paid_by", "label", "source_message_ids"}
)
_OUTPUT_KEYS = frozenset({"expenses", "questions"})
_REPLACEMENT_QUESTION = (
    "Không thể kiểm chứng một khoản chi từ tin nhắn nguồn; "
    "vui lòng xác nhận lại số tiền và người trả."
)


class MoneySkillError(Exception):
    """Report one stable, model-independent contract violation."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _strict_positive_int(value: object) -> bool:
    """A positive amount in đồng, at or under the cap.

    The integer-shape half is `money.vnd_violation`; only the ceiling is this
    module's own rule. This used to read `type(value) is int`, a third
    spelling of law 1 that no count of the copies could see -- neither the one
    that found four nor the one that corrected it to six.
    """
    return vnd_violation(value, positive=True) is None and value <= MAX_AMOUNT_VND


def _digits(value: str) -> int | None:
    normalized = value.replace(".", "").replace(",", "")
    if len(normalized) > 16:
        return None
    return int(normalized)


def _million_value(whole: str, remainder: str | None) -> int | None:
    parsed_whole = _digits(whole)
    if parsed_whole is None:
        return None
    amount = parsed_whole * 1_000_000
    if remainder is None:
        return amount
    return amount + int(remainder) * 10 ** (6 - len(remainder))


def extract_vnd_amounts(text: str) -> frozenset[int]:
    """Return integer-VND readings explicitly written in ``text``.

    The accepted spellings are intentionally narrow: grouped raw dong,
    ungrouped raw dong with at least four digits, ``k``/``nghin``/``ngan``, and
    ``tr``/``trieu`` forms. Semantic interpretation stays with the extraction
    backend; this helper only proves that a proposed number is present.
    """

    if not isinstance(text, str):
        return frozenset()

    amounts: set[int] = set()
    occupied: list[tuple[int, int]] = []

    for match in _MILLION_AMOUNT.finditer(text):
        amount = _million_value(match.group(1), match.group(2))
        if amount is not None:
            amounts.add(amount)
        occupied.append(match.span())

    for match in _THOUSAND_AMOUNT.finditer(text):
        amount = _digits(match.group(1))
        if amount is not None:
            amounts.add(amount * 1_000)
        occupied.append(match.span())

    def is_occupied(start: int, end: int) -> bool:
        return any(
            start < occupied_end and end > occupied_start
            for occupied_start, occupied_end in occupied
        )

    for match in _GROUPED_AMOUNT.finditer(text):
        if not is_occupied(*match.span()):
            amount = _digits(match.group(0))
            if amount is not None:
                amounts.add(amount)
            occupied.append(match.span())

    for match in _PLAIN_AMOUNT.finditer(text):
        if not is_occupied(*match.span()):
            amount = _digits(match.group(0))
            if amount is not None:
                amounts.add(amount)

    return frozenset(amounts)


def _require_nonempty_string(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MoneySkillError(code)
    return value


def _member_ids(context: dict) -> frozenset[str]:
    members = context.get("group_members")
    if not isinstance(members, list) or not members:
        raise MoneySkillError("INVALID_GROUP_MEMBERS")

    result: list[str] = []
    for member in members:
        if not isinstance(member, dict):
            raise MoneySkillError("INVALID_GROUP_MEMBERS")
        result.append(
            _require_nonempty_string(member.get("id"), "INVALID_GROUP_MEMBERS")
        )
    if len(set(result)) != len(result):
        raise MoneySkillError("DUPLICATE_GROUP_MEMBER_ID")
    return frozenset(result)


def _captured_at_is_a_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def validate_context(
    context: dict, *, max_messages: int = DEFAULT_MAX_MESSAGES
) -> None:
    """Validate the explicit snapshot before any extraction backend sees it."""

    if not isinstance(context, dict):
        raise MoneySkillError("INVALID_CONTEXT")
    if count_violation(max_messages, minimum=1):
        raise ValueError("max_messages must be a positive integer")

    members = _member_ids(context)
    messages = context.get("messages")
    if not isinstance(messages, list) or not messages:
        raise MoneySkillError("EMPTY_CONTEXT")
    if len(messages) > max_messages:
        raise MoneySkillError("CONTEXT_TOO_LONG")

    message_ids: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            raise MoneySkillError("INVALID_MESSAGE")
        message_ids.append(
            _require_nonempty_string(message.get("id"), "INVALID_MESSAGE_ID")
        )
        author_id = _require_nonempty_string(
            message.get("author_id"), "INVALID_MESSAGE_AUTHOR"
        )
        if author_id not in members:
            raise MoneySkillError("UNKNOWN_MESSAGE_AUTHOR")
        if not isinstance(message.get("text"), str):
            raise MoneySkillError("INVALID_MESSAGE_TEXT")
    if len(set(message_ids)) != len(message_ids):
        raise MoneySkillError("DUPLICATE_MESSAGE_ID")

    manifest = context.get("context_manifest")
    if not isinstance(manifest, dict) or not manifest:
        raise MoneySkillError("INVALID_CONTEXT_MANIFEST")
    if manifest.get("first_message_id") != message_ids[0]:
        raise MoneySkillError("CONTEXT_MANIFEST_RANGE_MISMATCH")
    if manifest.get("last_message_id") != message_ids[-1]:
        raise MoneySkillError("CONTEXT_MANIFEST_RANGE_MISMATCH")
    # `minimum=None`: a negative count was already refused one line below, by
    # the comparison against the messages actually present.
    if count_violation(manifest.get("message_count"), minimum=None):
        raise MoneySkillError("INVALID_CONTEXT_MANIFEST")
    if manifest["message_count"] != len(messages):
        raise MoneySkillError("CONTEXT_MANIFEST_COUNT_MISMATCH")
    if not _captured_at_is_a_timestamp(manifest.get("captured_at")):
        raise MoneySkillError("INVALID_CONTEXT_MANIFEST_TIMESTAMP")


def _validate_participant_references(expense: dict, members: frozenset[str]) -> None:
    if expense["paid_by"] not in members:
        raise MoneySkillError("UNKNOWN_PAID_BY")
    for field in ("excluded", "shared_by_hint"):
        if field not in expense:
            continue
        values = expense[field]
        if not isinstance(values, list) or any(
            not isinstance(value, str) or value not in members for value in values
        ):
            raise MoneySkillError("UNKNOWN_PARTICIPANT_REFERENCE")
        if len(set(values)) != len(values):
            raise MoneySkillError("DUPLICATE_PARTICIPANT_REFERENCE")


def _validated_expense(
    raw: object,
    *,
    messages_by_id: dict[str, dict],
    members: frozenset[str],
) -> dict:
    if not isinstance(raw, dict):
        raise MoneySkillError("INVALID_EXTRACTED_EXPENSE")
    if set(raw) - _EXPENSE_KEYS or not _REQUIRED_EXPENSE_KEYS.issubset(raw):
        raise MoneySkillError("INVALID_EXTRACTED_EXPENSE")
    if not _strict_positive_int(raw["total_vnd"]):
        raise MoneySkillError("INVALID_TOTAL_VND")
    _require_nonempty_string(raw["paid_by"], "INVALID_PAID_BY")
    _require_nonempty_string(raw["label"], "INVALID_EXPENSE_LABEL")
    _validate_participant_references(raw, members)

    source_ids = raw["source_message_ids"]
    if not isinstance(source_ids, list) or not source_ids:
        raise MoneySkillError("MISSING_SOURCE_MESSAGE_IDS")
    if any(not isinstance(source_id, str) for source_id in source_ids):
        raise MoneySkillError("INVALID_SOURCE_MESSAGE_ID")
    if len(set(source_ids)) != len(source_ids):
        raise MoneySkillError("DUPLICATE_SOURCE_MESSAGE_ID")
    if any(source_id not in messages_by_id for source_id in source_ids):
        raise MoneySkillError("SOURCE_MESSAGE_OUTSIDE_CONTEXT")

    cited_amounts = frozenset(
        amount
        for source_id in source_ids
        for amount in extract_vnd_amounts(messages_by_id[source_id]["text"])
    )
    if raw["total_vnd"] not in cited_amounts:
        raise MoneySkillError("TOTAL_NOT_IN_SOURCE")

    result = {
        "total_vnd": raw["total_vnd"],
        "paid_by": raw["paid_by"],
        "label": raw["label"],
        "source_message_ids": list(source_ids),
    }
    for field in ("excluded", "shared_by_hint"):
        if field in raw:
            result[field] = list(raw[field])
    return result


def validate_extraction(context: dict, extraction: dict) -> dict:
    """Return only grounded expenses plus questions safe for presentation.

    Invalid candidate expenses are fail-closed: they are omitted and replaced
    by one explicit review question. Validation never silently repairs model
    output and never adds allocation fields.
    """

    if not isinstance(extraction, dict) or set(extraction) - _OUTPUT_KEYS:
        raise MoneySkillError("INVALID_EXTRACTOR_OUTPUT")
    expenses = extraction.get("expenses", [])
    questions = extraction.get("questions", [])
    if not isinstance(expenses, list) or not isinstance(questions, list):
        raise MoneySkillError("INVALID_EXTRACTOR_OUTPUT")
    if any(
        not isinstance(question, str) or not question.strip() for question in questions
    ):
        raise MoneySkillError("INVALID_EXTRACTED_QUESTION")

    members = _member_ids(context)
    messages_by_id = {message["id"]: message for message in context["messages"]}
    accepted: list[dict] = []
    rejected = False
    for expense in expenses:
        try:
            accepted.append(
                _validated_expense(
                    expense,
                    messages_by_id=messages_by_id,
                    members=members,
                )
            )
        except MoneySkillError:
            rejected = True

    public_questions = list(questions)
    if rejected and _REPLACEMENT_QUESTION not in public_questions:
        public_questions.append(_REPLACEMENT_QUESTION)
    return {"expenses": accepted, "questions": public_questions}
