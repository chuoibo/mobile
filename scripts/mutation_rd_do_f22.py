#!/usr/bin/env python3
"""Mutation table for F22 -- face detection without identity, and self-tagging.

A green suite is not evidence that a gate exists. This script edits the shipped
source one mutation at a time and reports what the suite does about it.

Two kinds of row, and the second is the one that makes the table worth reading:

``BREAKS``  changes behaviour a case claims to guard. Must go **RED**.
``KEEPS``   changes the source without changing the property under test --
            a renamed local, a reordered pair of independent statements, a
            constant moved somewhere that is genuinely free. Must stay
            **GREEN**.

A table of only BREAKS rows cannot tell "the suite guards this property" apart
from "the suite goes red whenever the file is touched". The KEEPS rows are the
control: if one of them goes red, some case is pinned to the shape of the code
rather than to the behaviour, and its green is worth less than it looks.

Run from the repository root::

    python3 scripts/mutation_rd_do_f22.py

Exit code is 0 only when every BREAKS row went red and every KEEPS row stayed
green.
"""

from __future__ import annotations

import dataclasses
import os
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "services" / "api"

PRIVACY = "tests/postgres/test_face_boxes_privacy_postgres.py"
CLAIM = "tests/postgres/test_bill_self_claim_postgres.py"
DOMAIN = "tests/domain/test_faces.py"
LIMIT = "tests/api/test_face_detection_rate_limit.py"


@dataclasses.dataclass(frozen=True)
class Mutation:
    name: str
    kind: str  # "BREAKS" or "KEEPS"
    path: str
    old: str
    new: str
    tests: tuple[str, ...]
    why: str


MUTATIONS: tuple[Mutation, ...] = (
    # ------------------------------------------------- the privacy boundary ---
    Mutation(
        name="f22-boxes-served-to-a-stranger",
        kind="BREAKS",
        path="app/api/service.py",
        old="        retained to withdraw.\n"
        '        """\n'
        "\n"
        "        _require_permission(\n"
        '            "view_group_memories",\n'
        "            actor,\n"
        '            {"is_group_member": self.repository.is_member(context_id, actor.id)},',
        new="        retained to withdraw.\n"
        '        """\n'
        "\n"
        "        _require_permission(\n"
        '            "view_group_memories",\n'
        "            actor,\n"
        '            {"is_group_member": True},',
        tests=(PRIVACY,),
        why="How many faces are in a group's dinner photo, and where they sit, "
        "is a description of the evening. Returning it to somebody who may "
        "not see the picture leaks the evening without returning a pixel.",
    ),
    Mutation(
        name="f22-detection-runs-before-the-door-is-checked",
        kind="BREAKS",
        path="app/api/service.py",
        old="        record = self.repository.get_context_image(context_id, photo_id)\n"
        "        if record is None:\n"
        '            raise ApiProblem(404, "photo_not_found", "Photo does not exist")\n'
        "        try:\n"
        "            content = self.photo_storage.read(record.storage_key)",
        new="        record = self.repository.get_context_image(context_id, photo_id)\n"
        "        if record is None:\n"
        '            raise ApiProblem(404, "photo_not_found", "Photo does not exist")\n'
        "        detector.detect(b'')\n"
        "        try:\n"
        "            content = self.photo_storage.read(record.storage_key)",
        tests=(PRIVACY,),
        why="A refusal that has already run the cascade has already spent the "
        "CPU it was refusing, and on the stranger path it means the model "
        "touched a photograph the caller may not see.",
    ),
    # ------------------------------------------------- what may be published ---
    Mutation(
        name="f22-box-key-becomes-a-cross-photo-join-key",
        kind="BREAKS",
        path="app/domain/faces.py",
        old='            "box_key": f"face-{index}",',
        new='            "box_key": f"box-{hash((top, left, width, height)) & 0xffffff:06x}",',
        tests=(DOMAIN,),
        why="A key derived from the geometry is stable across photographs, so "
        "two responses can be lined up. Lining up who appeared in which photo "
        "is identity assembled from parts none of which is called identity -- "
        "the thing ADR-0011 says must not be writable.",
    ),
    Mutation(
        name="f22-order-follows-the-detector-not-the-picture",
        kind="BREAKS",
        path="app/domain/faces.py",
        old="    ordered = sorted(\n"
        "        {(top, left, width, height) for left, top, width, height in clamped}\n"
        "    )",
        new="    ordered = list(dict.fromkeys((top, left, width, height) for left, top, width, height in clamped))",
        tests=(DOMAIN,),
        why="Two scans of one photo may report the same faces in either order. "
        "With input order the ordinal follows the library's internals, so "
        '"face-2" names a different person between the response somebody '
        "looked at and the one behind their next tap.",
    ),
    Mutation(
        name="f22-a-crowd-is-truncated-instead-of-refused",
        kind="BREAKS",
        path="app/domain/faces.py",
        old='    if len(ordered) > MAX_FACES:\n        raise FaceError("TOO_MANY_FACES")',
        new="    ordered = ordered[:MAX_FACES]",
        tests=(DOMAIN,),
        why="Silently keeping the first N drops somebody's box, and a person "
        "with no box cannot tap it. They are locked out of the feature by a "
        "truncation nothing in the response mentions.",
    ),
    Mutation(
        name="f22-edge-face-is-not-clamped-back-into-the-frame",
        kind="BREAKS",
        path="app/domain/faces.py",
        old="        left = max(0, min(x, image_width))\n"
        "        top = max(0, min(y, image_height))",
        new="        left = x\n        top = y",
        tests=(DOMAIN,),
        why="The detector legitimately reports a face at the frame edge as "
        "running past the border. Publishing that raw gives a negative "
        "fraction, which the response schema refuses -- so the person sitting "
        "at the end of the table breaks the whole request.",
    ),
    # ------------------------------------------------------- the write path ---
    Mutation(
        name="f22-claim-charges-somebody-other-than-the-caller",
        kind="BREAKS",
        path="app/api/service.py",
        old="            record = self.repository.claim_bill_items(\n"
        "                bill_id=bill_id,\n"
        "                participant_id=actor.id,",
        new="            record = self.repository.claim_bill_items(\n"
        "                bill_id=bill_id,\n"
        "                participant_id=record.created_by_id,",
        tests=(CLAIM,),
        why="The whole point of the route is that the person charged is the "
        "one holding the header. Taking it from anywhere else reintroduces "
        "the door the shape of the request body was built to close.",
    ),
    Mutation(
        name="f22-claim-evicts-everyone-else-on-the-dish",
        kind="BREAKS",
        path="app/api/repository.py",
        old="                .where(BillItemShare.bill_item_id.in_([item.id for item in item_rows]))\n"
        "                .where(BillItemShare.participant_id == participant_id)",
        new="                .where(BillItemShare.bill_item_id.in_([item.id for item in item_rows]))",
        tests=(CLAIM,),
        why="This is the bug the obvious implementation has -- reusing "
        "`confirm_bill_assignments`, which clears every share on the keys it "
        "is handed. Invisible with one diner; with two it deletes the other "
        "person's dish and the split charges one of them for both.",
    ),
    Mutation(
        name="f22-claim-adds-without-releasing-so-a-mistap-is-permanent",
        kind="BREAKS",
        path="app/api/repository.py",
        old="            for share in mine:\n                self.session.delete(share)\n",
        new="            for share in mine:\n                pass\n",
        tests=(CLAIM,),
        why="If the list only ever adds, a wrong tap can never be taken back "
        "and the person keeps paying for a dish they did not eat. There is no "
        "second endpoint that would undo it.",
    ),
    # ---------------------------------------------------------- the ceiling ---
    Mutation(
        name="f22-ninth-door-shares-the-eighth-door-window",
        kind="BREAKS",
        path="app/api/main.py",
        old="    application.state.face_detection_limiter = build_face_detection_limiter()",
        new="    application.state.face_detection_limiter = (\n"
        "        application.state.contextual_suggestion_limiter\n"
        "    )",
        tests=(LIMIT,),
        why="The cheapest way to add a ninth window is to hand the route one "
        "that already exists. Every per-route ceiling assertion survives that "
        "-- each route alone still stops somewhere -- while a burst of face "
        "detection silently spends the group's chat-card allowance.",
    ),
    Mutation(
        name="f22-ceiling-checked-after-the-cascade-has-run",
        kind="BREAKS",
        path="app/api/routes/faces.py",
        old="    limiter.check(actor.id)\n"
        "    return ApiService(\n"
        "        repository, photo_storage=photo_storage\n"
        "    ).detect_faces_in_context_photo(context_id, photo_id, actor, detector)",
        new="    boxes = ApiService(\n"
        "        repository, photo_storage=photo_storage\n"
        "    ).detect_faces_in_context_photo(context_id, photo_id, actor, detector)\n"
        "    limiter.check(actor.id)\n"
        "    return boxes",
        tests=(LIMIT,),
        why="A 429 raised after the work has already spent what it was "
        "refusing. The window still reports a ceiling, and the box still "
        "burns the CPU on every request in the burst.",
    ),
    # ------------------------------------------------------------- controls ---
    #
    # Every row above is red. A table that is only red cannot distinguish "the
    # suite guards this" from "the suite dislikes being touched".
    Mutation(
        name="f22-KEEPS-cap-spelled-as-arithmetic",
        kind="KEEPS",
        path="app/domain/faces.py",
        old="MAX_FACES = 24",
        new="MAX_FACES = 12 + 12",
        tests=(DOMAIN,),
        why="Same value, written differently. A red here means a case is "
        "reading the literal rather than the behaviour.",
    ),
    Mutation(
        name="f22-KEEPS-dedupe-written-as-an-explicit-loop",
        kind="KEEPS",
        path="app/domain/faces.py",
        old="    ordered = sorted(\n"
        "        {(top, left, width, height) for left, top, width, height in clamped}\n"
        "    )",
        new="    unique = set()\n"
        "    for left, top, width, height in clamped:\n"
        "        unique.add((top, left, width, height))\n"
        "    ordered = sorted(unique)",
        tests=(DOMAIN,),
        why="The same set by a different route. A red here would mean a case "
        "is pinned to how the de-duplication is written rather than to the "
        "boxes it produces.",
    ),
    Mutation(
        name="f22-KEEPS-limiter-reached-through-a-local-name",
        kind="KEEPS",
        path="app/api/routes/faces.py",
        old="    limiter.check(actor.id)\n",
        new="    gate = limiter\n    gate.check(actor.id)\n",
        tests=(LIMIT,),
        why="Identical call through a rebound name, still before the work. A "
        "red here means a case is matching source text rather than measuring "
        "when the ceiling is consulted.",
    ),
    Mutation(
        name="f22-KEEPS-claim-list-de-duplicated-with-a-loop",
        kind="KEEPS",
        path="app/api/repository.py",
        old="        requested = dict.fromkeys(item_keys)",
        new="        requested = {}\n"
        "        for requested_key in item_keys:\n"
        "            requested[requested_key] = None",
        tests=(CLAIM,),
        why="Same keys, same order, built by hand. A red here means a case is "
        "reading the idiom instead of the resulting claim set.",
    ),
)

# A row whose replacement equals its anchor is a no-op that would report itself
# as a caught mutation. Refuse the whole table rather than print a green that
# was never earned.
_NOOP = [m.name for m in MUTATIONS if m.old == m.new]
if _NOOP:
    raise SystemExit(f"mutation table has no-op rows: {_NOOP}")


def run_tests(paths: tuple[str, ...]) -> tuple[bool, str]:
    """(passed, output) for the selected tests. Postgres tier required, not skipped."""

    env = dict(os.environ)
    env.setdefault(
        "MOBILE_TEST_DATABASE_URL",
        "postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile",
    )
    env["MOBILE_REQUIRE_POSTGRES_TESTS"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *paths,
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    return completed.returncode == 0, completed.stdout + completed.stderr


# A mutation that makes the module raise on import, or leaves a name undefined,
# goes red for a reason that has nothing to do with the property under test.
# For a BREAKS row that is a false pass -- the table would claim the suite
# caught something when it only tripped over a broken edit.
_BROKEN_EDIT_MARKERS = ("NameError", "SyntaxError", "ImportError", "IndentationError")


def broken_edit(output: str) -> str | None:
    for marker in _BROKEN_EDIT_MARKERS:
        if marker in output:
            return marker
    return None


def main() -> int:
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", "services/api"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        print("REFUSING: services/api has uncommitted changes.")
        print("Commit first -- reverting a mutation would overwrite them.")
        print(dirty)
        return 2

    print("Baseline: the suite must be green before any mutation means anything.")
    every_test = tuple(sorted({path for m in MUTATIONS for path in m.tests}))
    baseline_passed, baseline_output = run_tests(every_test)
    if not baseline_passed:
        print("BASELINE RED -- stopping. Nothing below would be interpretable.")
        print(baseline_output[-2000:])
        return 2
    print("Baseline GREEN.\n")

    rows = []
    ok = True
    for mutation in MUTATIONS:
        target = API_ROOT / mutation.path
        original = target.read_text()
        if mutation.old not in original:
            rows.append((mutation, "ANCHOR-MISSING", False))
            ok = False
            print(
                f"[{mutation.kind}] {mutation.name}: ANCHOR NOT FOUND -- table is stale"
            )
            continue
        if original.count(mutation.old) != 1:
            # A duplicate anchor patches whichever copy comes first, which is
            # how a mutation reports GREEN while the code it meant to break is
            # untouched.
            rows.append((mutation, "ANCHOR-AMBIGUOUS", False))
            ok = False
            print(
                f"[{mutation.kind}] {mutation.name}: ANCHOR APPEARS "
                f"{original.count(mutation.old)} TIMES -- would patch the wrong copy"
            )
            continue

        target.write_text(original.replace(mutation.old, mutation.new, 1))
        try:
            passed, output = run_tests(mutation.tests)
        finally:
            target.write_text(original)

        marker = broken_edit(output)
        if mutation.kind == "BREAKS":
            if marker is not None:
                verdict, good = f"RED-BUT-BROKEN({marker})", False
            elif passed:
                verdict, good = "GREEN", False
            else:
                verdict, good = "RED", True
        else:
            if marker is not None:
                verdict, good = f"BROKEN({marker})", False
            elif passed:
                verdict, good = "GREEN", True
            else:
                verdict, good = "RED", False

        ok = ok and good
        rows.append((mutation, verdict, good))
        print(f"[{mutation.kind}] {mutation.name}: {verdict} {'ok' if good else 'BAD'}")

    print("\n--- table ---")
    for mutation, verdict, good in rows:
        print(
            f"{'ok ' if good else 'BAD'} {mutation.kind:6} {verdict:22} {mutation.name}"
        )
    breaks = sum(1 for m, _, _ in rows if m.kind == "BREAKS")
    keeps = len(rows) - breaks
    print(f"\n{breaks} BREAKS rows, {keeps} KEEPS rows.")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
