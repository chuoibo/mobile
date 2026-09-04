"""The app's demo people must be the rows the seed script actually writes.

Two files now carry the same seven ids: `scripts/seed_demo_data.py` derives
them with `uuid5`, and `apps/mobile/src/rudi/nhom-demo.ts` has them
written out because Hermes cannot derive a `uuid5` without shipping SHA-1.

Duplicated constants drift. This one drifts *silently*, which is why it is
worth a test rather than a comment: the personal screen would ask the API about
a person who does not exist, and the API would answer correctly -- 200, all
zeros, no transactions. A wrong id and a person who has genuinely never split a
bill produce the same screen. Nobody debugging that starts by suspecting a
constant.

Parses the TypeScript rather than executing it, so this test needs no Node and
runs in the same `pytest` invocation as everything else.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_SCRIPT = REPO_ROOT / "scripts" / "seed_demo_data.py"
DEMO_TS = REPO_ROOT / "apps" / "mobile" / "src" / "rudi" / "nhom-demo.ts"

# One object literal per person, in the DEMO_PEOPLE array. Deliberately strict
# about the field order it accepts: a loose pattern that silently matched fewer
# people would make this test pass by finding nothing.
ENTRY = re.compile(
    r'\{\s*id:\s*"(?P<slug>[a-z-]+)",\s*'
    r'personId:\s*"(?P<person_id>[0-9a-f-]{36})",\s*'
    r'name:\s*"(?P<name>[^"]+)",\s*'
    r'initials:\s*"(?P<initials>[^"]+)",?\s*\}'
)


def _seed_module():
    """Import the seed script without running it.

    It reads environment and talks to a database at call time, never at import
    time, so importing is safe -- but it is a script rather than a package, so
    it needs loading by path.
    """
    spec = importlib.util.spec_from_file_location("seed_demo_data", SEED_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def seed():
    if not SEED_SCRIPT.exists():  # pragma: no cover - repo layout guard
        pytest.fail(f"missing {SEED_SCRIPT}")
    try:
        return _seed_module()
    except ImportError as error:
        pytest.skip(f"seed script dependencies unavailable: {error}")


@pytest.fixture(scope="module")
def app_people() -> list[re.Match[str]]:
    if not DEMO_TS.exists():
        pytest.skip(f"{DEMO_TS} is not on this branch")
    matches = list(ENTRY.finditer(DEMO_TS.read_text(encoding="utf-8")))
    assert matches, "parsed no people out of nhom-demo.ts -- the shape changed"
    return matches


def test_every_demo_person_id_is_the_seeded_uuid(seed, app_people):
    """Re-derived, not compared against a second copy of the answer."""
    for entry in app_people:
        slug = entry["slug"]
        expected = seed.person_id(slug)
        assert entry["person_id"] == str(expected), (
            f"{slug}: nhom-demo.ts says {entry['person_id']}, "
            f"seed_demo_data.py derives {expected}"
        )


def test_the_app_and_the_seed_agree_on_who_is_in_the_group(seed, app_people):
    """Same people, same names. A member in one file only is a drift too."""
    app_names = {entry["name"] for entry in app_people}
    seed_names = set(seed.NAME_OF.values())

    assert app_names == seed_names


def test_the_written_ids_are_real_uuid5_values(app_people):
    """Version 5, not hand-typed hex that merely looks the part."""
    for entry in app_people:
        parsed = uuid.UUID(entry["person_id"])
        assert parsed.version == 5, f"{entry['slug']} is not a uuid5"


def test_no_written_id_carries_a_digit_run_the_repo_guard_would_block(app_people):
    """The reason the seed script derives its ids instead of writing them.

    The guard cannot tell a padded demo UUID from an account number and blocks
    long digit runs on sight. These ids are safe today; a future name whose
    hash lands on a long run would be blocked at commit time, and finding that
    out here is cheaper than finding it out in a failing hook.
    """
    for entry in app_people:
        longest = max(
            (len(run) for run in re.findall(r"\d+", entry["person_id"])), default=0
        )
        assert longest < 12, f"{entry['slug']} has a {longest}-digit run"
