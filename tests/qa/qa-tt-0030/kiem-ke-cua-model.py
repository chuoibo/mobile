"""Census: which routes can reach Gemini, and does each have something in front.

This is the question `test_the_roster_of_doors_onto_the_model_is_accounted_for`
says outright that it does not answer. That case reads guards off `app.state`
and compares them to a written-down roster, which catches a door being aliased,
renamed, or deleted -- but a route that reaches the model while building nothing
discoverable puts nothing there to compare, so it is invisible. N1 in
`dot_bien_cua_khong_ai_thay.py` measures exactly that blindness.

So this walks the other way round. Instead of starting from the guards and
asking which doors they cover, it starts from the *routes* -- every one the app
actually registered -- follows each endpoint's dependency graph, and asks two
separate questions: can this route reach a Gemini backend, and does it depend on
a guard. The interesting cell is `model=yes, guard=no`.

Two honest limits, because a census that oversells itself is worse than none.
It resolves dependencies statically through `Depends(...)` and the module graph,
so a backend reached by a runtime lookup rather than a dependency would be
missed. And "has a guard" here means a guard is *wired in*, not that its ceiling
is right or that it is consulted before the expensive call -- a limiter that is
injected and never asked would count as guarded here.

Run from the repo root of a tree with #301 applied.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, "services/api")

from fastapi.dependencies.utils import get_dependant  # noqa: E402

from app.api.main import create_app  # noqa: E402


# Discovered, not listed. The first version of this file hand-wrote five
# `app.api.*_gemini` module names and therefore missed `GET /places`, whose
# model call lives in `app.places.*` -- the identical failure to the one this
# census exists to look for, committed by the census. So the set is now built
# by asking every loaded module whether it names the Gemini endpoint.
def _discover_model_modules() -> set[str]:
    found = set()
    for name, module in list(sys.modules.items()):
        if not name.startswith(("app.", "app")) or module is None:
            continue
        src = getattr(module, "__file__", None)
        if not src or not src.endswith(".py"):
            continue
        try:
            text = pathlib.Path(src).read_text()
        except OSError:
            continue
        if "generativelanguage" in text or "GEMINI_API_KEY" in text:
            found.add(name)
    return found


MODEL_MODULES: set[str] = set()

GUARD_NAMES = ("limiter", "limit", "reason_writer", "writer", "quota", "budget")


def _reaches_model(fn: object, seen: set[int] | None = None, depth: int = 0) -> bool:
    """Does this callable, or anything it closes over, live in a model module."""

    if depth > 4:
        return False
    seen = seen if seen is not None else set()
    if id(fn) in seen:
        return False
    seen.add(id(fn))

    module = getattr(fn, "__module__", "") or ""
    if module in MODEL_MODULES:
        return True

    # Dependency factories such as `get_contextual_suggester` import the backend
    # inside the function body, so the name never appears in `__module__`. The
    # constant pool is where it does appear.
    code = getattr(fn, "__code__", None)
    if code is not None:
        blob = " ".join(str(c) for c in code.co_consts) + " ".join(code.co_names)
        if any(m.rsplit(".", 1)[-1] in blob for m in MODEL_MODULES):
            return True
        if "gemini" in blob.lower():
            return True
    return False


def main() -> int:
    app = create_app()
    global MODEL_MODULES
    MODEL_MODULES = _discover_model_modules()
    print("module cham model (do tim ra, khong liet ke):", len(MODEL_MODULES))
    for m in sorted(MODEL_MODULES):
        print("   ", m)
    print()
    rows: list[tuple[str, str, bool, bool]] = []

    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        path = getattr(route, "path", "")
        # Every registered route, not a prefix the author of this script thought
        # of: narrowing the sweep by path is the same mistake as narrowing a
        # gate by name, and the first pass here really did miss `/receipts`,
        # `/screenshots` and `GET /places` that way.
        if endpoint is None or not path.startswith("/"):
            continue
        methods = ",".join(sorted(getattr(route, "methods", []) - {"HEAD", "OPTIONS"}))

        dependant = get_dependant(path=path, call=endpoint)
        calls = [dependant.call]
        stack = list(dependant.dependencies)
        while stack:
            dep = stack.pop()
            if dep.call is not None:
                calls.append(dep.call)
            stack.extend(dep.dependencies)

        model = any(_reaches_model(c) for c in calls)
        guard = any(
            any(g in (getattr(c, "__name__", "") or "").lower() for g in GUARD_NAMES)
            for c in calls
        )
        if model:
            rows.append((methods, path, model, guard))

    print(f"{'guard':6}  {'method':6}  route")
    print("-" * 74)
    unguarded = []
    for methods, path, _model, guard in sorted(rows, key=lambda r: r[1]):
        mark = "CO" if guard else "KHONG"
        print(f"{mark:6}  {methods:6}  {path}")
        if not guard:
            unguarded.append(f"{methods} {path}")

    print("-" * 74)
    print(f"route cham model: {len(rows)}   khong thay guard: {len(unguarded)}")
    for u in unguarded:
        print("   KHONG GUARD:", u)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
