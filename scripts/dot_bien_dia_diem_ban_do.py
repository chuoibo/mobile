#!/usr/bin/env python3
"""Mutation tables for the four place features: F10, F43, F44, F45.

One table per feature, each with two kinds of row.

  CONTROL -- breaks the property the feature exists to hold. The suite must go
  RED. A control row that stays green is a hole: the tests are describing the
  behaviour without constraining it.

  KEEP -- changes a constant while leaving the property intact. The suite must
  stay GREEN. This is the row that distinguishes a gate from a byte-pin, and it
  is the row most often missing: a table where every row is red proves the tests
  react to *edits*, not that they react to *defects*. A gate that goes red when
  somebody tunes a limit is a gate somebody deletes.

## Two hazards this file is written around

**Red for the wrong reason.** A mutation that renames a symbol makes the suite
red with a NameError, which reads exactly like a caught defect. Every row below
substitutes real, in-scope expressions only, and each row names the specific
test it expects to fail so the reason can be checked rather than assumed.

**A no-op mutation.** A replacement whose anchor is absent, or which matches in
two places and patches the wrong one, prints the baseline's verdict and reads as
a working gate. Every anchor is asserted to occur EXACTLY ONCE before it is
used, and the file is asserted to have actually changed afterwards.

Restores from text held in memory rather than `git checkout --`, so running this
against a tree with uncommitted work cannot destroy it.

    python3 scripts/dot_bien_dia_diem_ban_do.py

Exit 0 = every row landed on expectation. Exit 1 = a hole or a byte-pin.
Exit 2 = the harness could not conclude anything, which is not a pass.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
API = REPO_ROOT / "services" / "api"

SERVICE = API / "app" / "api" / "service.py"
PLACES_ROUTE = API / "app" / "api" / "routes" / "places.py"
AREAS = API / "app" / "places" / "areas.py"
SOCIAL_MAP = API / "app" / "places" / "social_map.py"
MEETING = API / "app" / "places" / "meeting.py"
DETAILS = API / "app" / "places" / "details.py"

PURE = "tests/places"
DETAIL_API = "tests/api/test_place_detail.py"
LIVE = "tests/postgres/test_social_map_postgres.py"

DB_URL = "postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile"


# (tag, feature, kind, description, file, anchor, replacement, tests, expect)
ROWS = [
    # ---------------- F10 -- Place Detail ---------------------------------
    (
        "F10-C1",
        "F10",
        "CONTROL",
        "unknown place id falls back to a real row instead of 404",
        PLACES_ROUTE,
        '    place = find_place(place_id)\n'
        '    if place is None:\n'
        '        raise ApiProblem(404, "place_not_found", '
        '"Không tìm thấy địa điểm này.")',
        "    place = find_place(place_id) or PLACES[0]",
        [DETAIL_API],
        "RED",
    ),
    (
        "F10-C2",
        "F10",
        "CONTROL",
        "claims venue photos exist when there is no image store",
        PLACES_ROUTE,
        "        photos_available=False,",
        "        photos_available=True,",
        [DETAIL_API],
        "RED",
    ),
    (
        "F10-C3",
        "F10",
        "CONTROL",
        "detail recomputes its own score instead of reusing the card's",
        PLACES_ROUTE,
        "    return PlaceDetail(\n        **card.model_dump(),",
        "    card = card.model_copy(\n"
        "        update={'match': card.match.model_copy(\n"
        "            update={'score': card.match.score - 1})}\n"
        "    )\n"
        "    return PlaceDetail(\n        **card.model_dump(),",
        [DETAIL_API],
        "RED",
    ),
    (
        "F10-K1",
        "F10",
        "KEEP",
        "a seed review rating is retuned, prose still served",
        DETAILS,
        '                "author": "Trang",\n                "rating": 5.0,',
        '                "author": "Trang",\n                "rating": 4.5,',
        [DETAIL_API],
        "GREEN",
    ),
    # ---------------- F43 -- Social Map -----------------------------------
    (
        "F43-C1",
        "F43",
        "CONTROL",
        "map stops checking membership",
        SERVICE,
        '        _require_permission(\n'
        '            "view_social_map",\n'
        "            actor,\n"
        '            {"is_group_member": self.repository.is_member('
        "context_id, actor.id)},\n"
        "        )",
        '        _require_permission(\n'
        '            "view_social_map",\n'
        "            actor,\n"
        '            {"is_group_member": True},\n'
        "        )",
        [LIVE],
        "RED",
    ),
    (
        "F43-C2",
        "F43",
        "CONTROL",
        "recommends places the group has already been to",
        SERVICE,
        '            (place for place in PLACES if place["id"] not in seen),',
        "            (place for place in PLACES),",
        [LIVE],
        "RED",
    ),
    (
        "F43-C3",
        "F43",
        "CONTROL",
        "visited layer carries the author of each check-in",
        SOCIAL_MAP,
        '                "visit_count": 1,\n            }\n        else:',
        '                "visit_count": 1,\n'
        '                "author_id": row.get("author_id"),\n'
        "            }\n        else:",
        [PURE, LIVE],
        "RED",
    ),
    (
        "F43-K1",
        "F43",
        "KEEP",
        "recommended list shortened from 8 to 6",
        SERVICE,
        "_MAP_RECOMMENDED = 8",
        "_MAP_RECOMMENDED = 6",
        [LIVE],
        "GREEN",
    ),
    # ---------------- F44 -- Group Heatmap --------------------------------
    (
        "F44-C1",
        "F44",
        "CONTROL",
        "heatmap stops checking membership",
        SERVICE,
        '        _require_permission(\n'
        '            "view_group_heatmap",\n'
        "            actor,\n"
        '            {"is_group_member": self.repository.is_member('
        "context_id, actor.id)},\n"
        "        )",
        '        _require_permission(\n'
        '            "view_group_heatmap",\n'
        "            actor,\n"
        '            {"is_group_member": True},\n'
        "        )",
        [LIVE],
        "RED",
    ),
    (
        "F44-C2",
        "F44",
        "CONTROL",
        "area lookup loses its radius, so every point gets a district",
        AREAS,
        "    best_km = MAX_AREA_RADIUS_KM",
        '    best_km = float("inf")',
        [PURE],
        "RED",
    ),
    (
        "F44-C3",
        "F44",
        "CONTROL",
        "heatmap row carries the time of the visit",
        SOCIAL_MAP,
        '            rolled[area["id"]] = {**area_summary(area), "visit_count": 1}',
        '            rolled[area["id"]] = {\n'
        "                **area_summary(area),\n"
        '                "visit_count": 1,\n'
        '                "created_at": str(_row.get("created_at")),\n'
        "            }",
        [PURE, LIVE],
        "RED",
    ),
    (
        "F44-K1",
        "F44",
        "KEEP",
        "radius tightened 25km -> 20km, still covers every seed row",
        AREAS,
        "MAX_AREA_RADIUS_KM = 25.0",
        "MAX_AREA_RADIUS_KM = 20.0",
        [PURE, LIVE],
        "GREEN",
    ),
    # ---------------- F45 -- Meet-in-the-middle ---------------------------
    (
        "F45-C1",
        "F45",
        "CONTROL",
        "meeting point stops checking membership",
        SERVICE,
        '        _require_permission(\n'
        '            "view_meeting_point",\n'
        "            actor,\n"
        '            {"is_group_member": self.repository.is_member('
        "context_id, actor.id)},\n"
        "        )",
        '        _require_permission(\n'
        '            "view_meeting_point",\n'
        "            actor,\n"
        '            {"is_group_member": True},\n'
        "        )",
        [LIVE],
        "RED",
    ),
    (
        "F45-C2",
        "F45",
        "CONTROL",
        "ranks by total travel, abandoning minimax fairness",
        MEETING,
        '                "_sort": (worst, sum(legs), place["id"]),',
        '                "_sort": (sum(legs), place["id"]),',
        [PURE],
        "RED",
    ),
    (
        "F45-C3",
        "F45",
        "CONTROL",
        "an unknown origin area is silently dropped",
        SERVICE,
        "            if area is None:\n"
        "                raise ApiProblem(\n"
        "                    422,\n"
        '                    "unknown_area",\n'
        '                    f"Không có khu vực nào tên {area_id}.",\n'
        "                )",
        "            if area is None:\n                continue",
        [LIVE],
        "RED",
    ),
    (
        "F45-C4",
        "F45",
        "CONTROL",
        "one origin accepted, so a 'meeting' can be where you already are",
        SERVICE,
        "        if not (MIN_ORIGIN_AREAS <= len(request.from_areas) "
        "<= MAX_ORIGIN_AREAS):",
        "        if not (1 <= len(request.from_areas) <= MAX_ORIGIN_AREAS):",
        [LIVE],
        "RED",
    ),
    (
        "F45-K1",
        "F45",
        "KEEP",
        "origin ceiling lowered 12 -> 10",
        MEETING,
        "MAX_ORIGIN_AREAS = 12",
        "MAX_ORIGIN_AREAS = 10",
        [PURE, LIVE],
        "GREEN",
    ),
]


def _env() -> dict:
    env = dict(os.environ)
    env["MOBILE_TEST_DATABASE_URL"] = DB_URL
    env["MOBILE_REQUIRE_POSTGRES_TESTS"] = "1"
    return env


def _clear_pycache() -> None:
    """Stale bytecode is how a restored tree keeps failing like a mutated one.

    Cheap insurance: mtime-based invalidation is usually enough, but a write
    inside the same second as the previous one is not guaranteed to be seen.
    """

    for cache in (API / "app").rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def run_tests(selection: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *selection, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=API,
        env=_env(),
        capture_output=True,
        text=True,
    )
    # Only the final summary line. Grepping the whole output reads counts out
    # of the docstrings of whichever test is currently failing.
    lines = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    summary = lines[-1] if lines else "(no output)"
    return proc.returncode, summary[:70]


def main() -> int:
    originals = {path: path.read_text(encoding="utf-8") for path in {r[4] for r in ROWS}}

    # Anchors first, before anything is written. A table that discovers a stale
    # anchor halfway through has already reported rows built on a tree it was
    # editing.
    bad = []
    for tag, _feature, _kind, _desc, path, anchor, _rep, _tests, _expect in ROWS:
        found = originals[path].count(anchor)
        if found != 1:
            bad.append(f"{tag}: anchor occurs {found}x in {path.name} (need exactly 1)")
    if bad:
        print("ANCHORS UNUSABLE -- refusing to run. A no-op mutation prints the")
        print("baseline verdict and reads exactly like a gate that is holding.")
        for line in bad:
            print(f"  {line}")
        return 2

    selections = sorted({tuple(row[7]) for row in ROWS})
    baseline: dict[tuple, tuple[int, str]] = {}
    for selection in selections:
        rc, summary = run_tests(list(selection))
        baseline[selection] = (rc, summary)
        print(f"{'BASE':<8} {'-':<7} {' '.join(selection):<58} "
              f"expect GREEN  got {'GREEN' if rc == 0 else 'RED':<5}  {summary}")
        if rc != 0:
            print("BASELINE IS RED -- every row below would be uninterpretable.")
            return 2
    print()

    verdicts = []
    try:
        for tag, feature, kind, desc, path, anchor, replacement, tests, expect in ROWS:
            original = originals[path]
            path.write_text(original.replace(anchor, replacement, 1), encoding="utf-8")
            if path.read_text(encoding="utf-8") == original:
                print(f"{tag}: MUTATION WAS A NO-OP -- cannot conclude.")
                return 2
            _clear_pycache()
            rc, summary = run_tests(list(tests))
            path.write_text(original, encoding="utf-8")
            _clear_pycache()

            got = "GREEN" if rc == 0 else "RED"
            ok = got == expect
            verdicts.append((tag, feature, kind, ok, got, expect, desc))
            print(
                f"{tag:<8} {kind:<7} {desc:<58} "
                f"expect {expect:<5}  got {got:<5}  "
                f"{'ok' if ok else '<<< MISMATCH'}  {summary}"
            )
    finally:
        for path, text in originals.items():
            path.write_text(text, encoding="utf-8")
        _clear_pycache()

    holes = [v for v in verdicts if not v[3] and v[2] == "CONTROL"]
    pinned = [v for v in verdicts if not v[3] and v[2] == "KEEP"]

    print()
    for feature in ("F10", "F43", "F44", "F45"):
        rows = [v for v in verdicts if v[1] == feature]
        controls = [v for v in rows if v[2] == "CONTROL"]
        keeps = [v for v in rows if v[2] == "KEEP"]
        caught = len([v for v in controls if v[3]])
        held = len([v for v in keeps if v[3]])
        print(
            f"{feature}: {caught}/{len(controls)} defects caught, "
            f"{held}/{len(keeps)} keep row(s) stayed green"
        )
    print()

    if not holes and not pinned:
        print("ALL ROWS AS EXPECTED -- every defect caught, every keep row green.")
        return 0
    if holes:
        print(
            f"HOLES: {len(holes)} control row(s) stayed GREEN with the property "
            f"broken: {', '.join(h[0] for h in holes)}. The tests describe the "
            "behaviour without constraining it."
        )
    if pinned:
        print(
            f"BYTE-PIN: {len(pinned)} keep row(s) went RED with the property "
            f"intact: {', '.join(p[0] for p in pinned)}. The gate is pinned to a "
            "constant, not to a property."
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
