"""Pure F24 contract tests for turning one chat message into a draft."""

from __future__ import annotations

from importlib import import_module

import pytest

from app.domain.contract import MAX_AMOUNT_VND


def _contract():
    return import_module("app.domain.chat_expense")


def test_chat_expense_normalizes_only_the_money_and_title() -> None:
    module = _contract()

    result = module.read_chat_expense(
        {
            "is_expense": True,
            "title": "  Grab ra sân bay  ",
            "amount_text": "180k",
            "confidence": 0.99,
        }
    )

    assert result == {
        "is_expense": True,
        "title": "Grab ra sân bay",
        "amount_vnd": 180_000,
        "needs_review": True,
    }
    assert set(result) == {"is_expense", "title", "amount_vnd", "needs_review"}


@pytest.mark.parametrize(
    ("amount_text", "amount_vnd"),
    [("1 triệu", 1_000_000), ("180.000đ", 180_000)],
)
def test_chat_expense_reuses_vietnamese_amount_normalization(
    amount_text: str, amount_vnd: int
) -> None:
    module = _contract()

    result = module.read_chat_expense(
        {"is_expense": True, "title": "Bữa tối", "amount_text": amount_text}
    )

    assert result["amount_vnd"] == amount_vnd


def test_chat_expense_non_expense_has_no_draft_values() -> None:
    module = _contract()

    assert module.read_chat_expense({"is_expense": False}) == {
        "is_expense": False,
        "title": None,
        "amount_vnd": None,
        "needs_review": False,
    }


@pytest.mark.parametrize("value", [None, 1, 0, "true", [], {}])
def test_chat_expense_requires_a_real_boolean_decision(value) -> None:
    module = _contract()

    with pytest.raises(module.ChatExpenseError) as caught:
        module.read_chat_expense({"is_expense": value})

    assert caught.value.code == "UNREADABLE"


@pytest.mark.parametrize("amount", [180_000, 180_000.0, True])
def test_chat_expense_rejects_model_money_that_is_not_text(amount) -> None:
    module = _contract()

    with pytest.raises(module.ChatExpenseError) as caught:
        module.read_chat_expense(
            {"is_expense": True, "title": "Grab", "amount_text": amount}
        )

    assert caught.value.code == "UNREADABLE"


# The over-ceiling case is derived from the constant rather than typed out. A
# 13-digit literal also trips the repo guard's long-number rule, which cannot
# tell a ceiling probe from a leaked account number -- and deriving it keeps the
# case meaningful if `MAX_AMOUNT_VND` ever moves.
@pytest.mark.parametrize(
    "amount_text", ["0", str(MAX_AMOUNT_VND + 1), "-1", ""]
)
def test_chat_expense_rejects_non_positive_or_oversized_money(
    amount_text: str,
) -> None:
    module = _contract()

    with pytest.raises(module.ChatExpenseError) as caught:
        module.read_chat_expense(
            {"is_expense": True, "title": "Grab", "amount_text": amount_text}
        )

    assert caught.value.code == "UNREADABLE"


@pytest.mark.parametrize("title", [None, 7, "", "   ", "x" * 201])
def test_chat_expense_rejects_an_unusable_title(title) -> None:
    module = _contract()

    with pytest.raises(module.ChatExpenseError) as caught:
        module.read_chat_expense(
            {"is_expense": True, "title": title, "amount_text": "180k"}
        )

    assert caught.value.code == "UNREADABLE"


@pytest.mark.parametrize(
    "identity_key",
    [
        "paid_by",
        "paid_by_id",
        "payer",
        "payer_name",
        "person_id",
        "people",
        "shared_by",
        "participants",
        "participant_ids",
        "author_id",
    ],
)
def test_chat_expense_refuses_any_model_channel_that_names_a_person(
    identity_key: str,
) -> None:
    module = _contract()

    with pytest.raises(module.ChatExpenseError) as caught:
        module.read_chat_expense(
            {
                "is_expense": True,
                "title": "Grab",
                "amount_text": "180k",
                identity_key: "somebody",
            }
        )

    assert caught.value.code == "MODEL_NAMED_A_PERSON"


def test_chat_expense_refuses_identity_even_when_model_says_not_an_expense() -> None:
    module = _contract()

    with pytest.raises(module.ChatExpenseError) as caught:
        module.read_chat_expense({"is_expense": False, "participants": ["somebody"]})

    assert caught.value.code == "MODEL_NAMED_A_PERSON"


def test_chat_expense_rejects_a_non_object_model_answer() -> None:
    module = _contract()

    with pytest.raises(module.ChatExpenseError) as caught:
        module.read_chat_expense(["180k"])

    assert caught.value.code == "UNREADABLE"
