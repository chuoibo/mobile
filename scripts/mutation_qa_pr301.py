#!/usr/bin/env python3
"""Do the tests added for PR #301 bite, and does the PR's own suite bite too?

Four mutations, one per question the Lead asked. For each one the table records
two verdicts, not one:

  MOI   -- the three files added by rd-qa-39
  #301  -- the test files the PR itself ships

A mutation that turns MOI red and leaves #301 green is the interesting row: it
names coverage this branch adds. A mutation both catch is honest and worth
printing too, because "my test also catches it" is a weaker claim than "only my
test catches it" and the difference should be visible rather than argued.

Anchors are full, unique strings and the replacement asserts the count is
exactly one. Anchoring on a fragment that appears in four service methods is
how a mutation run patches the wrong function and reports GREEN for a gate that
was never touched.

Every mutation is valid Python that runs. A mutation that raises `NameError`
turns every case red for a reason that has nothing to do with the property, and
reads exactly like a working gate.

    python3 scripts/mutation_qa_pr301.py

Needs MOBILE_TEST_DATABASE_URL: two of the four claims live in tests/postgres,
and a skipped tier scores every mutation as SURVIVED.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

API = Path(__file__).resolve().parents[1] / "services" / "api"

MINE = [
    "tests/postgres/test_pr301_cross_group_leak_postgres.py",
    "tests/api/test_pr301_guest_boundary.py",
    "tests/api/test_pr301_contextual_window_is_not_shared.py",
]
THEIRS = [
    "tests/postgres/test_group_intelligence_postgres.py",
    "tests/api/test_contextual_suggestion_rate_limit.py",
]


@dataclass(frozen=True)
class Mutation:
    name: str
    question: str
    path: str
    before: str
    after: str


MUTATIONS = [
    Mutation(
        name="header-decides-membership",
        question="1. quyen chot bang is_member hay bang X-Actor-Contexts?",
        path="app/api/service.py",
        before=(
            '            "view_group_preference_profile",\n'
            "            actor,\n"
            '            {"is_group_member": self.repository.is_member('
            "context_id, actor.id)},\n"
        ),
        after=(
            '            "view_group_preference_profile",\n'
            "            actor,\n"
            '            {"is_group_member": context_id in actor.context_ids},\n'
        ),
    ),
    Mutation(
        name="album-drops-context-join",
        question="4. cover album co the la anh cua nhom khac khong?",
        path="app/api/repository.py",
        before=(
            "                .where(\n"
            "                    Memory.context_id == outing.context_id,\n"
            "                    _wall_clock_date(Memory.created_at).between(\n"
        ),
        after=(
            "                .where(\n"
            "                    _wall_clock_date(Memory.created_at).between(\n"
        ),
    ),
    Mutation(
        name="f33-reads-the-f32-window",
        question="3. tran nhip F33 co dung chung cua so voi cua khac khong?",
        path="app/api/routes/suggestions.py",
        before="    return request.app.state.contextual_suggestion_limiter\n",
        after="    return request.app.state.suggestion_limiter\n",
    ),
    Mutation(
        name="missing-actor-header-is-anonymous",
        question="2. khach tren /g/{token} co cham duoc ba route nay khong?",
        path="app/api/deps.py",
        before=(
            "    if actor_id is None:\n"
            '        raise ApiProblem(401, "authentication_required", '
            '"Missing X-Actor-ID")\n'
        ),
        # Built rather than written out: a literal nil UUID is a 32-digit run,
        # and `scripts/repo_guard.py` refuses those on sight because that is
        # also the shape of a bank account number. `deps.py` already imports
        # `UUID`, so this stays valid Python inside the function it patches.
        after=("    if actor_id is None:\n        actor_id = str(UUID(int=0))\n"),
    ),
]


def run(files: list[str]) -> tuple[bool, str]:
    """True when every test passed. Anything that is not a clean pass is red."""

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *files,
            "-q",
            "--no-header",
            "-p",
            "no:randomly",
        ],
        cwd=API,
        capture_output=True,
        text=True,
    )
    tail = [line for line in result.stdout.strip().splitlines() if line.strip()]
    summary = tail[-1] if tail else "(no output)"
    # A collection error exits non-zero with no "failed" in the summary, and a
    # fully skipped tier exits ZERO. Both must read as "this run proved
    # nothing" rather than as a verdict.
    if "skipped" in summary and "passed" not in summary:
        raise SystemExit(f"tier skipped, so nothing was measured: {summary}")
    return result.returncode == 0, summary


def patch(path: str, before: str, after: str) -> str:
    target = API / path
    original = target.read_text()
    count = original.count(before)
    if count != 1:
        raise SystemExit(
            f"anchor for {path} matched {count} times, expected exactly 1 -- "
            "a mutation that patches the wrong copy reports a gate it never touched"
        )
    target.write_text(original.replace(before, after))
    return original


def main() -> int:
    if not os.environ.get("MOBILE_TEST_DATABASE_URL"):
        raise SystemExit(
            "set MOBILE_TEST_DATABASE_URL; two claims live in tests/postgres"
        )

    print("== baseline (no mutation): both suites must be green ==")
    for label, files in (("MOI ", MINE), ("#301", THEIRS)):
        ok, summary = run(files)
        print(f"  {label}  {'XANH' if ok else 'DO  '}  {summary}")
        if not ok:
            raise SystemExit("baseline is not green; measuring mutants is meaningless")

    rows = []
    for mutation in MUTATIONS:
        original = patch(mutation.path, mutation.before, mutation.after)
        try:
            mine_ok, mine_summary = run(MINE)
            theirs_ok, theirs_summary = run(THEIRS)
        finally:
            (API / mutation.path).write_text(original)
        rows.append((mutation, mine_ok, mine_summary, theirs_ok, theirs_summary))
        print(f"\n== {mutation.name} ==")
        print(f"   {mutation.question}")
        print(f"   MOI   {'SONG SOT' if mine_ok else 'BAT DUOC'}  {mine_summary}")
        print(f"   #301  {'SONG SOT' if theirs_ok else 'BAT DUOC'}  {theirs_summary}")

    print("\n== bang tong ==")
    print(f"   {'dot bien':<34} {'MOI':<10} {'#301':<10}")
    for mutation, mine_ok, _, theirs_ok, _ in rows:
        print(
            f"   {mutation.name:<34} "
            f"{'song sot' if mine_ok else 'bat duoc':<10} "
            f"{'song sot' if theirs_ok else 'bat duoc':<10}"
        )

    survived = [mutation.name for mutation, mine_ok, _, _, _ in rows if mine_ok]
    only_mine = [
        mutation.name
        for mutation, mine_ok, _, theirs_ok, _ in rows
        if not mine_ok and theirs_ok
    ]
    print(f"\n   dot bien MOI khong bat duoc: {survived or 'khong co'}")
    print(f"   chi MOI bat duoc (do phu them): {only_mine or 'khong co'}")

    # Verified afterwards, because a mutation run that leaves the tree edited is
    # worse than one that never ran.
    dirty = subprocess.run(
        ["git", "diff", "--name-only", "--", "services/api/app"],
        cwd=API.parents[1],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise SystemExit(f"tree left mutated: {dirty}")
    print("   cay san pham da khoi phuc sach")

    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
