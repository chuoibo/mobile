"""Two mutants the branch's own table does not carry, aimed at the new gate.

`scripts/mutation_cong_cua_so_model.py` measures five rows and the new gate
catches 4/4 property-breaking ones against the legacy gate's 1/4. That table is
real -- it was re-run in a clean merge tree and reproduced. Every one of its
mutants, though, edits a door the roster *already discovered*: it aliases one,
deletes one, or empties discovery outright. None of them adds a door the way a
feature branch adds one.

So these two ask the question the table leaves open: what happens to a door that
arrives *after* the gate was written?

N1 registers a real ninth route that calls the model on every GET with no guard
in front of it. This is the exact shape that let F33 ship unmetered, and it is
what the branch says it set out to stop happening again. The gate's own
docstring declares this one uncovered -- N1 exists to hold that declaration to a
measurement rather than to a sentence.

N2 is the one nobody declared. It adds a ninth door that *does* build a guard on
`app.state`, in `create_app`, eagerly -- but of a class that is not one of the
two in `_MODEL_GUARD_TYPES`. Discovery filters by `isinstance` against that
hand-written pair, so the new door is filtered out before the roster is
compared. The roster still equals `_KNOWN_DOORS`, distinctness still holds over
the eight it can see, and both cases stay green.

Read together the pair says where the rewrite landed: the gate stopped
enumerating door *names* and started enumerating guard *types*. That is a real
level up -- the roster now drags a new same-type door into view, which is what
M1 and M3 measure -- but the list is still hand-written, and a door outside it
is still invisible.

Run from the repo root of a tree with #301 applied.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]

NEW_GATE = (
    "services/api/tests/api/test_contextual_suggestion_rate_limit.py"
    "::test_every_door_onto_the_model_carries_its_own_guard"
)
ROSTER_GATE = (
    "services/api/tests/api/test_contextual_suggestion_rate_limit.py"
    "::test_the_roster_of_doors_onto_the_model_is_accounted_for"
)

ROUTES = REPO / "services/api/app/api/routes/suggestions.py"
MAIN = REPO / "services/api/app/api/main.py"

# N1: a real route onto the model with nothing standing in front of it. It is a
# copy of the metered route with the limiter dependency removed -- the cheapest
# way a ninth door actually gets added in this repo.
N1_ROUTE = '''

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
    """MUTANT N1: ninth door onto the model, no guard of any shape."""

    return ApiService(repository).contextual_suggestion(context_id, actor, suggester)
'''

# N2: a ninth door that IS guarded, eagerly, on app.state -- by a class the
# discovery filter does not name. Nothing about this is exotic: a token bucket
# is the ordinary second thing somebody reaches for after a fixed window.
N2_GUARD = '''

class TokenBucketLimiter:
    """MUTANT N2: a guard of a shape `_MODEL_GUARD_TYPES` does not list."""

    def __init__(self) -> None:
        self._tokens = 8

    def check(self, actor_id: object) -> None:
        return None
'''

N2_WIRING = """
    # MUTANT N2: ninth door, guarded eagerly on app.state, unknown class.
    application.state.trip_recap_limiter = TokenBucketLimiter()
"""


def _run(args: list[str]) -> tuple[int, str]:
    done = subprocess.run(args, capture_output=True, text=True, cwd=REPO)
    tail = (done.stdout.strip().splitlines() or ["<no output>"])[-1]
    return done.returncode, tail


def _verdict(code: int) -> str:
    return "XANH" if code == 0 else "ĐỎ"


def _registered(needle: str) -> str:
    """Prove the mutant is really in the app, not a dead edit read as a finding."""

    code, out = _run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, 'services/api');"
            "from app.api.main import create_app;"
            f"print([r.path for r in create_app().routes if {needle!r} in getattr(r, 'path', '')])",
        ]
    )
    return out


def _state_names() -> str:
    code, out = _run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, 'services/api');"
            "from app.api.main import create_app;"
            "print(sorted(n for n in vars(create_app().state)['_state']))",
        ]
    )
    return out


def main() -> int:
    route_src = ROUTES.read_text()
    main_src = MAIN.read_text()

    print("Bản sạch — cả hai ca của cổng mới phải XANH trước khi bảng có nghĩa")
    for label, node in (("phân biệt", NEW_GATE), ("roster", ROSTER_GATE)):
        code, _ = _run([sys.executable, "-m", "pytest", node, "-q"])
        print(f"  {label}: {_verdict(code)}")

    try:
        # ---- N1 -------------------------------------------------------------
        ROUTES.write_text(route_src + N1_ROUTE)
        print("\nN1  route thứ chín gọi model, KHÔNG có guard nào")
        print("  route có thật trong app:", _registered("contextual-suggestion"))
        for label, node in (("phân biệt", NEW_GATE), ("roster", ROSTER_GATE)):
            code, tail = _run([sys.executable, "-m", "pytest", node, "-q"])
            print(f"  {label}: {_verdict(code)}  ({tail})")
        ROUTES.write_text(route_src)

        # ---- N2 -------------------------------------------------------------
        anchor = "    application.state.search_limiter = build_search_limiter()"
        assert main_src.count(anchor) == 1, "neo N2 không duy nhất — đừng đoán"
        MAIN.write_text(
            main_src.replace(anchor, anchor + N2_WIRING, 1).replace(
                "\ndef create_app(", N2_GUARD + "\ndef create_app(", 1
            )
        )
        print("\nN2  cửa thứ chín CÓ guard trên app.state, nhưng lớp khác")
        print("  app.state sau đột biến:", _state_names())
        for label, node in (("phân biệt", NEW_GATE), ("roster", ROSTER_GATE)):
            code, tail = _run([sys.executable, "-m", "pytest", node, "-q"])
            print(f"  {label}: {_verdict(code)}  ({tail})")
    finally:
        ROUTES.write_text(route_src)
        MAIN.write_text(main_src)

    print("\nCây đã hoàn nguyên:", _run(["git", "diff", "--stat"])[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
