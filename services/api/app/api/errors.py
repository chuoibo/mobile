"""Stable API errors shared by route handlers and application services."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ApiProblem(Exception):
    """An expected request failure with a wire-stable code."""

    status_code: int
    code: str
    detail: str

    def __post_init__(self) -> None:
        Exception.__init__(self, self.code)


class RepositoryConflict(Exception):
    """A persistence invariant rejected an otherwise well-formed request."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
