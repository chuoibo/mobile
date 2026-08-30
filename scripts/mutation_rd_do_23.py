#!/usr/bin/env python3
"""Mutation table for rd-do-23 -- F31 profile, F33 contextual card, F36 album.

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

    python3 scripts/mutation_rd_do_23.py

Exit code is 0 only when every BREAKS row went red and every KEEPS row stayed
green.
"""

from __future__ import annotations

import dataclasses
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "services" / "api"


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
    # ---------------------------------------------------------------- F31 ---
    Mutation(
        name="f31-profile-served-to-a-stranger",
        kind="BREAKS",
        path="app/api/service.py",
        old='            "view_group_preference_profile",\n'
        "            actor,\n"
        '            {"is_group_member": self.repository.is_member(context_id, actor.id)},',
        new='            "view_group_preference_profile",\n'
        "            actor,\n"
        '            {"is_group_member": True},',
        tests=("tests/postgres/test_group_intelligence_postgres.py",),
        why="The profile says what a group likes, spends and where it goes. "
        "Handing it to a non-member is the privacy failure this feature is "
        "most able to cause.",
    ),
    Mutation(
        name="f31-sections-scored-against-a-global-maximum",
        kind="BREAKS",
        path="app/domain/preferences.py",
        old="        top = max(counts.values())",
        new="        top = max(\n"
        "            max(c.values())\n"
        "            for c in per_section.values()\n"
        "            if c\n"
        "        )",
        tests=("tests/domain/test_preferences.py",),
        why="A group with forty cafe check-ins and four dinners has a real "
        "food preference. Dividing by a global maximum rounds it to nothing "
        "and the Food section reads as though they never eat.",
    ),
    Mutation(
        name="f31-score-stops-being-a-share-of-its-own-section",
        kind="BREAKS",
        path="app/domain/preferences.py",
        old='                        "score": ((count * 200 + top) // (2 * top)) / 100,',
        new='                        "score": 1.0,',
        tests=("tests/domain/test_preferences.py",),
        why="Every taste scoring 1.0 is a profile that says nothing while "
        "looking exactly like one that says something.",
    ),
    Mutation(
        name="f31-unknown-category-gets-filed-under-food",
        kind="BREAKS",
        path="app/domain/preferences.py",
        old="    section = SECTION_OF_CATEGORY.get(category)\n    if section is None:",
        new='    section = SECTION_OF_CATEGORY.get(category, "food")\n'
        "    if section is None:",
        tests=("tests/domain/test_preferences.py",),
        why="Defaulting a category the mapping does not know puts a bar under "
        "Food and invents a taste nobody expressed.",
    ),
    Mutation(
        name="f31-average-spend-divides-by-outings-not-people",
        kind="BREAKS",
        path="app/domain/preferences.py",
        old='        "avg_per_person_vnd": total // people if people else None,',
        new='        "avg_per_person_vnd": total // len(trips) if trips else None,',
        tests=("tests/domain/test_preferences.py",),
        why="Per-person budget is what F34 reasons about. Dividing by trips "
        "reports a number four times too large for a group of four.",
    ),
    Mutation(
        name="f31-KEEPS-count-tastes-with-an-explicit-loop",
        kind="KEEPS",
        path="app/domain/preferences.py",
        old="        for label in labels:\n"
        "            per_section[section][label] += 1",
        new="        bucket = per_section[section]\n"
        "        for label in labels:\n"
        "            bucket.update([label])",
        tests=("tests/domain/test_preferences.py",),
        why="Same counts by a different route through Counter. A case that "
        "goes red here is pinned to how the tally is written rather than to "
        "what it holds.",
    ),
    # ---------------------------------------------------------------- F33 ---
    Mutation(
        name="f33-card-built-from-chat-served-to-a-stranger",
        kind="BREAKS",
        path="app/api/service.py",
        old='            "view_contextual_suggestion",\n'
        "            actor,\n"
        '            {"is_group_member": self.repository.is_member(context_id, actor.id)},',
        new='            "view_contextual_suggestion",\n'
        "            actor,\n"
        '            {"is_group_member": True},',
        tests=("tests/postgres/test_group_intelligence_postgres.py",),
        why="Reading this card means the server read the group's last few "
        "messages. Whoever may not read the chat may not read the card.",
    ),
    Mutation(
        name="f33-the-companion-reads-its-own-cards-back",
        kind="BREAKS",
        path="app/domain/conversation.py",
        old='        if message.get("kind") != CONVERSATION_KIND:\n            continue',
        new='        if message.get("kind") == "never-matches-anything":\n            continue',
        tests=("tests/domain/test_conversation.py",),
        why="Feeding ai_card rows back in makes suggestion two evidence for "
        "suggestion three -- a loop that drifts and looks better grounded "
        "every round.",
    ),
    Mutation(
        name="f33-a-silent-group-gets-interrupted",
        kind="BREAKS",
        path="app/domain/conversation.py",
        old='    return digest["message_count"] >= MIN_LINES',
        new="    return True",
        tests=("tests/domain/test_conversation.py",),
        why="A card fired at a group that said nothing is the product "
        "interrupting, which spec section 3 spends a page refusing.",
    ),
    Mutation(
        name="f33-speaker-names-reach-the-model-prompt",
        kind="BREAKS",
        path="app/domain/conversation.py",
        old='        "recent_lines": lines,',
        new='        "recent_lines": lines,\n        "speakers": sorted(speakers),',
        tests=("tests/domain/test_conversation.py",),
        why="The digest is what the model is handed. A real person's id "
        "leaving the group for no gain the feature can point at.",
    ),
    Mutation(
        name="f33-route-reaches-gemini-with-no-ceiling",
        kind="BREAKS",
        path="app/api/routes/suggestions.py",
        old="    limiter.check(actor.id)\n"
        "    return ApiService(repository).contextual_suggestion(context_id, actor, suggester)",
        new="    return ApiService(repository).contextual_suggestion(context_id, actor, suggester)",
        tests=("tests/api/test_contextual_suggestion_rate_limit.py",),
        why="One model call per GET on a screen that remounts. This is the "
        "gap the route shipped with and the reason the file exists.",
    ),
    Mutation(
        name="f33-KEEPS-limiter-checked-one-statement-earlier",
        kind="KEEPS",
        path="app/api/routes/suggestions.py",
        old="    limiter.check(actor.id)\n"
        "    return ApiService(repository).contextual_suggestion(context_id, actor, suggester)",
        new="    service = ApiService(repository)\n"
        "    limiter.check(actor.id)\n"
        "    return service.contextual_suggestion(context_id, actor, suggester)",
        tests=("tests/api/test_contextual_suggestion_rate_limit.py",),
        why="Constructing the service is not the model call. The ceiling still "
        "runs before anything is spent, so the property holds.",
    ),
    # ---------------------------------------------------------------- F36 ---
    # Two call sites, mutated separately and on purpose. `view_trip_album` is
    # asserted in both `list_trip_albums` and `trip_album`, and a table that
    # patched "the" check would leave whichever one it missed unproven -- the
    # shelf leaks titles and covers, the album leaks the photographs.
    Mutation(
        name="f36-shelf-served-to-a-stranger",
        kind="BREAKS",
        path="app/api/service.py",
        old='            "view_trip_album",\n'
        "            actor,\n"
        '            {"is_group_member": self.repository.is_member(context_id, actor.id)},\n'
        "        )\n\n"
        "        today = _now().astimezone(ZoneInfo(WALL_CLOCK_ZONE)).date()\n"
        "        albums = []",
        new='            "view_trip_album",\n'
        "            actor,\n"
        '            {"is_group_member": True},\n'
        "        )\n\n"
        "        today = _now().astimezone(ZoneInfo(WALL_CLOCK_ZONE)).date()\n"
        "        albums = []",
        tests=("tests/postgres/test_group_intelligence_postgres.py",),
        why="The shelf names a group's trips and shows a cover photograph from "
        "each. A stranger reading it learns where they went.",
    ),
    Mutation(
        name="f36-album-served-to-a-stranger",
        kind="BREAKS",
        path="app/api/service.py",
        old='            "view_trip_album",\n'
        "            actor,\n"
        '            {"is_group_member": self.repository.is_member(context_id, actor.id)},\n'
        "        )\n\n"
        "        today = _now().astimezone(ZoneInfo(WALL_CLOCK_ZONE)).date()\n"
        "        found = next(",
        new='            "view_trip_album",\n'
        "            actor,\n"
        '            {"is_group_member": True},\n'
        "        )\n\n"
        "        today = _now().astimezone(ZoneInfo(WALL_CLOCK_ZONE)).date()\n"
        "        found = next(",
        tests=("tests/postgres/test_group_intelligence_postgres.py",),
        why="The album is the photo gate's own rows. If it answers a stranger "
        "it is a second door to photographs the wall refuses them.",
    ),
    Mutation(
        name="f36-album-mints-its-own-media-path",
        kind="BREAKS",
        path="app/domain/album.py",
        old='                    "image_url": image_url,',
        new='                    "image_url": "/albums/media/" + str(memory.get("id")),',
        tests=(
            "tests/domain/test_album.py",
            "tests/postgres/test_group_intelligence_postgres.py",
        ),
        why="A second URL for the same bytes is the door nobody remembers to "
        "lock. The album must serve the wall's own guarded path.",
    ),
    Mutation(
        name="f36-silence-promotes-itself-to-highlights",
        kind="BREAKS",
        path="app/domain/album.py",
        old="MIN_HIGHLIGHT_REACTIONS = 1",
        new="MIN_HIGHLIGHT_REACTIONS = 0",
        tests=("tests/domain/test_album.py",),
        why="With no threshold an album where nobody reacted promotes its six "
        "newest photos and calls the group's silence a verdict.",
    ),
    Mutation(
        name="f36-new-year-trip-filed-under-its-start-year",
        kind="BREAKS",
        path="app/domain/album.py",
        old="    if ends_on.year != starts_on.year:\n"
        '        return f"{starts_on.year}–{ends_on.year}"',
        new='    if False:\n        return f"{starts_on.year}–{ends_on.year}"',
        tests=("tests/domain/test_album.py",),
        why="A small lie that appears once a year, which is exactly how long "
        "it survives without anybody noticing.",
    ),
    Mutation(
        name="f36-KEEPS-highlight-cap-spelled-as-arithmetic",
        kind="KEEPS",
        path="app/domain/album.py",
        old="MAX_HIGHLIGHTS = 6",
        new="MAX_HIGHLIGHTS = 3 + 3",
        tests=("tests/domain/test_album.py",),
        why="Same value, written differently. A red here means a case is "
        "reading the literal rather than the behaviour.",
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

    import os

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
    # Refuse to run on a dirty tree: a mutation is applied by editing the file
    # and reverted by writing the original bytes back, so an uncommitted edit
    # in one of these files would be destroyed by the revert.
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
                f"[{mutation.kind}] {mutation.name}: anchor appears "
                f"{original.count(mutation.old)} times -- refusing to guess"
            )
            continue

        target.write_text(original.replace(mutation.old, mutation.new, 1))
        try:
            passed, output = run_tests(mutation.tests)
        finally:
            target.write_text(original)

        # Checked before the verdict, for both kinds. A red caused by an
        # undefined name is the mutation being wrong, not the suite being
        # right, and reading it as "caught" is how a table reports a gate that
        # is not there.
        broken = None if passed else broken_edit(output)
        if broken is not None:
            good = False
            verdict = f"BROKEN EDIT ({broken}) -- verdict withheld"
        elif mutation.kind == "BREAKS":
            good = not passed
            verdict = "RED (caught)" if not passed else "GREEN (NOT CAUGHT)"
        else:
            good = passed
            verdict = "GREEN (property held)" if passed else "RED (over-pinned)"
        ok = ok and good
        rows.append((mutation, verdict, good))
        print(f"[{mutation.kind}] {mutation.name}: {verdict}")
        if mutation.kind == "KEEPS" and not passed and broken is None:
            # The failing case is the interesting part: it names what the suite
            # pinned itself to.
            for line in output.splitlines():
                if line.startswith("FAILED"):
                    print(f"         {line}")

    print("\n" + "=" * 78)
    print(f"{'kind':<8} {'mutation':<48} verdict")
    print("-" * 78)
    for mutation, verdict, good in rows:
        mark = " " if good else "X"
        print(f"{mark}{mutation.kind:<7} {mutation.name:<48} {verdict}")
    print("=" * 78)

    breaks = [r for r in rows if r[0].kind == "BREAKS"]
    keeps = [r for r in rows if r[0].kind == "KEEPS"]
    print(f"BREAKS caught: {sum(1 for r in breaks if r[2])}/{len(breaks)}")
    print(f"KEEPS  held:   {sum(1 for r in keeps if r[2])}/{len(keeps)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
