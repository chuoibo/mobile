"""Offline extraction doubles for money-skill contract tests."""

from __future__ import annotations

from copy import deepcopy


class DeterministicMoneyExtractor:
    """Return one predeclared response without network or model access."""

    def __init__(self, response: dict):
        self._response = deepcopy(response)
        self.calls: list[dict] = []

    def extract(self, context: dict) -> dict:
        self.calls.append(deepcopy(context))
        return deepcopy(self._response)
