#!/usr/bin/env python3
"""Reproduce, in isolation, why the actor-header gate calls `docChiaBill` a violation.

Run from the repo root, on a tree that has PR #365 merged:

    python3 docs/claude/2026-08-30/qa-tt-0042/tai-lap-cong-do.py

Exit 0 means the diagnosis still holds: the gate reports the violation, the
function body demonstrably contains `actorId`, and the only thing standing
between the two is a regex that cannot cross a nested `<>`.

The point of this file is that the finding is reproducible without reading
2000 lines of TypeScript. It asserts on the gate's OWN helper functions, so it
stays honest if somebody changes the gate: fix the regex and this script fails,
which is exactly what should happen.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
GATE = REPO / "scripts" / "check_actor_headers.py"
CLIENT = REPO / "apps" / "mobile" / "src" / "api.ts"


def load_gate():
    """Import the gate as a module. It must be registered in sys.modules first:
    its @dataclass decorator resolves annotations through the module entry."""
    spec = importlib.util.spec_from_file_location("cong_actor", GATE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cong_actor"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    g = load_gate()

    # 1. The regex, on its own. Three call shapes, one of which the gate cannot see.
    pattern = re.compile(r"\bcall\s*(?:<[^<>()]*>)?\s*\(")
    shapes = [
        ("call<SoDuWire>(path, { actorId })", "generic la mot ten", True),
        ("call<{ a: string }>(path, { actorId })", "inline, khong long <>", True),
        (
            "call<{ a: Record<string, number> }>(path, { actorId })",
            "inline, CO long <>",
            False,
        ),
    ]
    print("1. Regex `<[^<>()]*>` gap ba hinh dang generic:")
    for src, ten, mong_doi in shapes:
        thay = bool(pattern.search(src))
        dau = "KHOP " if thay else "TRUOT"
        print(f"   {dau} | {ten}")
        assert thay == mong_doi, f"hinh dang '{ten}' doi {mong_doi}, thuc te {thay}"

    # 2. The same failure, on the real function in the real file.
    regions = g.regions_of(CLIENT)
    doc = [r for r in regions if r.name == "docChiaBill"]
    if not doc:
        print("\nKHONG tim thay docChiaBill — cay nay chua merge #365?")
        return 2
    r = doc[0]
    blobs = g.call_args(r.text, "call")
    print(f"\n2. Tren file that — {r.where}:")
    print(f"   than ham chua 'actorId,' : {'actorId,' in r.text}")
    print(f"   call_args(...,'call')    : {blobs}")
    print(f"   passes_an_actor          : {g.passes_an_actor(r, 'call')}")
    assert "actorId," in r.text, (
        "than ham phai chua actorId — neu khong, day la bug that"
    )
    assert blobs == [], "call_args da doc duoc lenh goi — cong co the da duoc va"
    assert not g.passes_an_actor(r, "call"), "cong khong con bao vi pham — da duoc va"

    # 3. Same body, generic reshaped so no `<>` nests. Nothing else changes.
    fixed = r.text.replace("Record<string, number>", "RecordSN").replace(
        "Record<string, string>", "RecordSS"
    )
    blobs_fixed = g.call_args(fixed, "call")
    co_actor = any(g.ACTOR_IDENT.search(b) for b in blobs_fixed)
    print("\n3. Cung than ham, chi bo <> long trong generic:")
    print(f"   so blob doc duoc         : {len(blobs_fixed)}")
    print(f"   blob co chua actorId     : {co_actor}")
    assert len(blobs_fixed) == 1 and co_actor, (
        "doi hinh dang ma van khong doc duoc — chan doan sai"
    )

    print("\nKET LUAN: cong do dung mot lo hong co that trong chinh no, khong do")
    print("client quen gui header. San pham gui header — xem do-header-tren-day.mjs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
