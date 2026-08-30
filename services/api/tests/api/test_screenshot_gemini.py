"""Credential and schema boundary tests for the F26 Gemini adapter."""

from __future__ import annotations

from importlib import import_module

import pytest


def _backend():
    return import_module("app.api.screenshot_gemini")


@pytest.mark.parametrize("key", [None, ""])
def test_screenshot_gemini_missing_key_has_a_distinct_code(
    monkeypatch, key: str | None
) -> None:
    backend = _backend()
    if key is None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    else:
        monkeypatch.setenv("GEMINI_API_KEY", key)

    with pytest.raises(backend.ScreenshotError) as caught:
        backend.GeminiScreenshotReader().read(b"rebuilt pixels", "image/jpeg")

    assert caught.value.code == "SCREENSHOT_READER_NOT_CONFIGURED"


def test_screenshot_gemini_schema_has_no_identity_or_confidence_channel(
    monkeypatch,
) -> None:
    backend = _backend()
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-key")
    captured: dict = {}

    class Response:
        parsed = {
            "source": "grab",
            "merchant": "GrabFood",
            "total_text": "180k",
            "occurred_on": "2030-08-30",
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

    result = backend.GeminiScreenshotReader().read(
        b"rebuilt pixels", "image/jpeg"
    )

    assert result == Response.parsed
    schema = captured["config"].response_schema
    assert set(schema.properties) == {
        "source",
        "merchant",
        "total_text",
        "occurred_on",
    }
    assert "confidence" not in schema.properties
    prompt = captured["contents"][0].casefold()
    assert "do not name any person" in prompt
    image_part = captured["contents"][1]
    assert image_part.inline_data.data == b"rebuilt pixels"
    assert image_part.inline_data.mime_type == "image/jpeg"


def test_screenshot_gemini_redacts_upstream_exception_text(monkeypatch) -> None:
    backend = _backend()
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-key")

    class Client:
        def __init__(self, *, api_key: str):
            del api_key

        def __enter__(self):
            raise ValueError("private screenshot reading and synthetic-key")

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback

    monkeypatch.setattr(backend.genai, "Client", Client)

    with pytest.raises(RuntimeError) as caught:
        backend.GeminiScreenshotReader().read(b"private pixels", "image/jpeg")

    assert str(caught.value) == "ValueError"
    assert caught.value.__cause__ is None
