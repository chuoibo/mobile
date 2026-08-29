"""Stable API errors shared by route handlers and application services."""

from __future__ import annotations

from dataclasses import dataclass

#: A guest token that resolves to no capability at all -- which is a different
#: fact from a capability that exists and has expired or been revoked. Named
#: here because `app.api.main` matches on it: under `/g` that one code is
#: answered with the guest page rather than the JSON envelope.
#:
#: `app.api.service` still raises it as a literal, so what holds the two
#: together is a test rather than a shared symbol: every route that can raise
#: it is driven with an unknown token in `tests/api/test_guest_link_broken.py`,
#: and a literal that drifted from this constant turns those red.
GUEST_LINK_NOT_FOUND = "guest_link_not_found"


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
