"""Application boundary for pluggable chat-expense readers."""

from __future__ import annotations

from typing import Protocol

from app.domain.chat_expense import read_chat_expense

__all__ = ["ChatExpenseReader", "run_chat_expense_skill"]


class ChatExpenseReader(Protocol):
    """Copy expense-shaped fields from one private chat message."""

    def read(self, text: str) -> dict:
        """Return the raw chat-expense contract."""
        ...


def run_chat_expense_skill(text: str, *, reader: ChatExpenseReader) -> dict:
    """Read one message, then validate the untrusted model answer."""

    return read_chat_expense(reader.read(text))
