"""The mutation that decides PR #301's rate-limit gate: an eighth paid route.

`test_every_route_that_reaches_the_model_carries_its_own_window` says in its own
docstring that it is "counted, not enumerated -- so the *next* paid route cannot
slip through", and that "adding a seventh paid route without a window fails
here". Its body reads seven named attributes off `app.state` and asserts the set
of `id()`s has seven members. That proves the seven limiters are distinct
objects. It says nothing about how many routes reach the model.

This script registers a real eighth route that calls the model on every GET with
no limiter in front of it, then runs the suite. If the gate were counting, the
suite would go red. Run it from the repo root of a tree that has #301 applied.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

MUTANT = '''

@router.get(
    "/contexts/{context_id}/contextual-suggestion-v2",
    response_model=ContextualSuggestionResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def read_contextual_suggestion_v2(
    context_id: UUID,
    actor: Annotated[Actor, Depends(get_actor)],
    repository: Annotated[ApiRepository, Depends(get_repository)],
    suggester: Annotated[ContextualSuggester, Depends(get_contextual_suggester)],
) -> ContextualSuggestionResponse:
    """MUTANT: eighth paid route, reaches the model, no window in front of it."""

    return ApiService(repository).contextual_suggestion(context_id, actor, suggester)
'''

ROUTE = pathlib.Path("services/api/app/api/routes/suggestions.py")
GATE = (
    "services/api/tests/api/test_contextual_suggestion_rate_limit.py"
    "::test_every_route_that_reaches_the_model_carries_its_own_window"
)


def main() -> int:
    original = ROUTE.read_text()
    ROUTE.write_text(original + MUTANT)
    try:
        # The route really is registered -- otherwise this is a no-op mutation
        # dressed up as a finding, which is its own way of lying.
        registered = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; sys.path.insert(0, 'services/api');"
                "from app.api.main import create_app;"
                "print([r.path for r in create_app().routes"
                " if 'contextual-suggestion' in getattr(r, 'path', '')])",
            ],
            capture_output=True,
            text=True,
        )
        print(
            "routes registered:", registered.stdout.strip() or registered.stderr[-400:]
        )

        gate = subprocess.run(
            [sys.executable, "-m", "pytest", GATE, "-q"], capture_output=True, text=True
        )
        print(
            "the gate that claims to catch this:", gate.stdout.strip().splitlines()[-1]
        )

        suite = subprocess.run(
            [sys.executable, "-m", "pytest", "services/api/tests", "tests", "-q"],
            capture_output=True,
            text=True,
        )
        print("whole suite with the mutant:", suite.stdout.strip().splitlines()[-1])
    finally:
        ROUTE.write_text(original)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
