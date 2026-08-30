"""Credential and schema boundary tests for the real F24 Gemini adapter."""

from __future__ import annotations

from importlib import import_module

import pytest


def _backend():
    return import_module("app.api.chat_expense_gemini")


@pytest.mark.parametrize("key", [None, ""])
def test_chat_expense_gemini_missing_key_has_a_distinct_code(
    monkeypatch, key: str | None
) -> None:
    backend = _backend()
    if key is None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    else:
        monkeypatch.setenv("GEMINI_API_KEY", key)

    with pytest.raises(backend.ChatExpenseError) as caught:
        backend.GeminiChatExpenseReader().read("Tao trả Grab 180k rồi nhé.")

    assert caught.value.code == "CHAT_READER_NOT_CONFIGURED"


def test_chat_expense_gemini_schema_has_no_identity_channel(monkeypatch) -> None:
    backend = _backend()
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-key")
    captured: dict = {}

    class Response:
        parsed = {
            "is_expense": True,
            "title": "Grab",
            "amount_text": "180k",
        }
        text = ""

    class Models:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return Response()

    class Client:
        def __init__(self, *, api_key: str):
            assert api_key == "synthetic-key"
            self.models = Models()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback

    monkeypatch.setattr(backend.genai, "Client", Client)

    result = backend.GeminiChatExpenseReader().read("Tao trả Grab 180k rồi nhé.")

    assert result == Response.parsed
    schema = captured["config"].response_schema
    assert set(schema.properties) == {"is_expense", "title", "amount_text"}
    assert "Tao trả Grab 180k rồi nhé." in captured["contents"][0]


def test_chat_expense_gemini_redacts_upstream_exception_text(monkeypatch) -> None:
    backend = _backend()
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-key")

    class Client:
        def __init__(self, *, api_key: str):
            del api_key

        def __enter__(self):
            raise ValueError("private message and synthetic-key")

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback

    monkeypatch.setattr(backend.genai, "Client", Client)

    with pytest.raises(RuntimeError) as caught:
        backend.GeminiChatExpenseReader().read("private group message")

    assert str(caught.value) == "ValueError"
    assert caught.value.__cause__ is None
