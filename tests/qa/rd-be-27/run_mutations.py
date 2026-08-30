#!/usr/bin/env python3
"""Mutation table for F24 — the chat-expense draft route (rd-be-27).

Why this file exists. A green suite proves nothing about what the suite would
notice. This harness breaks one property at a time and records the colour, so
the claim "F24 is gated" is a measurement instead of an assertion.

Read the GREEN rows first. Four RED rows on their own would only prove the
suite reacts to *any* edit in these files -- a gate that goes red for every
change is as useless as one that never does, and gets disabled within a week.
The three property-preserving rows are what separate "measures the property"
from "measures whether somebody touched the file": each is a change a tidier
would plausibly make, and none may turn the suite red.

Run from the repo root:

    python3 tests/qa/rd-be-27/run_mutations.py

Every mutation is applied to a committed tree and reverted with `git checkout`
plus a bytecode purge. Run it with a clean `git status`: a dirty tree means the
revert would discard work that was never committed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
API = REPO / "services" / "api"

# The covering set, deliberately wider than the F24 files themselves. The
# money-law rows are caught by the repo-wide response/request gates rather than
# by anything F24 wrote, and a table that ran only F24's own tests would report
# those rows as blind.
PYTEST_TARGETS = [
    "tests/domain/test_chat_expense.py",
    "tests/api/test_chat_expense.py",
    "tests/api/test_chat_expense_gemini.py",
    "tests/domain/test_screenshot.py",
    "tests/api/test_screenshots_scan.py",
    "tests/api/test_screenshot_gemini.py",
    "tests/domain/test_budget.py",
    "tests/api/test_budget.py",
    "tests/api/test_money_response_type_gate.py",
    "tests/api/test_money_wire_type_gate.py",
    "tests/test_import_boundary.py",
]

SERVICE = API / "app" / "api" / "service.py"
DOMAIN = API / "app" / "domain" / "chat_expense.py"
SCHEMAS = API / "app" / "api" / "schemas.py"
ROUTES = API / "app" / "api" / "routes" / "messages.py"


SCREENSHOT_SKILL = API / "app" / "api" / "screenshot_skill.py"
SCREENSHOT_DOMAIN = API / "app" / "domain" / "screenshot.py"
SCREENSHOT_ROUTES = API / "app" / "api" / "routes" / "screenshots.py"
BUDGET_DOMAIN = API / "app" / "domain" / "budget.py"
PERMISSIONS = API / "app" / "domain" / "permissions.py"


@dataclass(frozen=True)
class Mutation:
    name: str
    path: Path
    old: str
    new: str
    expect: str  # "RED" or "GREEN"
    why: str
    feature: str = "F24"


MUTATIONS = [
    # ---------------------------------------------------------------- RED ---
    Mutation(
        name="service trusts the model for who paid",
        path=SERVICE,
        old="                paid_by_id=message.author_id,",
        new="                paid_by_id=shared_by[0],",
        expect="RED",
        why="Payer must be the stored message author, not any other person.",
    ),
    Mutation(
        name="cross-context message id is answered instead of refused",
        path=SERVICE,
        old="        if message is None or message.context_id != context_id:",
        new="        if message is None:",
        expect="RED",
        why="A guessed UUID must not become a window on another group's chat.",
    ),
    Mutation(
        name="domain stringifies a float amount instead of refusing it",
        path=DOMAIN,
        old='    amount_text = raw.get("amount_text")\n    if not isinstance(amount_text, str):',
        new='    amount_text = raw.get("amount_text")\n    if isinstance(amount_text, (int, float)):\n        amount_text = str(amount_text)\n    if not isinstance(amount_text, str):',
        expect="RED",
        why="Money law 1: 180000.0 from a model is a float that crossed money.",
    ),
    Mutation(
        name="draft money field declared lax int",
        path=SCHEMAS,
        old="    amount_vnd: PositiveMoneyVnd\n    paid_by_id: UUID",
        new="    amount_vnd: int\n    paid_by_id: UUID",
        expect="RED",
        why="A plain int launders 180000.0 into 180000 before any body assert.",
    ),
    # -------------------------------------------------------------- GREEN ---
    # Each of these changes something a tidier would change. If the suite turns
    # red here it is anchored on incidental text, not on the property.
    Mutation(
        name="GIU TINH CHAT: refusal wording reworded",
        path=ROUTES,
        old='    "Không đọc được khoản chi từ tin nhắn. Hãy kiểm tra lại nội dung."',
        new='    "Chưa đọc được khoản chi trong tin nhắn này. Bạn xem lại nội dung nhé."',
        expect="GREEN",
        why="Wire code and status are the contract; the Vietnamese prose is not.",
    ),
    Mutation(
        name="GIU TINH CHAT: identity fragments reordered",
        path=DOMAIN,
        old='_IDENTITY_KEY_FRAGMENTS = (\n    "paidby",\n    "payer",',
        new='_IDENTITY_KEY_FRAGMENTS = (\n    "payer",\n    "paidby",',
        expect="GREEN",
        why="Membership of the set decides the refusal; its order cannot.",
    ),
    Mutation(
        name="GIU TINH CHAT: roster sorted by str instead of bytes",
        path=SERVICE,
        old="            key=lambda person_id: person_id.bytes,",
        new="            key=lambda person_id: str(person_id),",
        expect="GREEN",
        why="Hex renders bytes in order, so both keys yield the same sequence.",
    ),
    # ================================================================ F26 ===
    Mutation(
        feature="F26",
        name="model is shown the raw upload instead of rebuilt pixels",
        path=SCREENSHOT_SKILL,
        old="    return read_screenshot(reader.read(sanitized.data, sanitized.content_type))",
        new="    return read_screenshot(reader.read(image, mime_type))",
        expect="RED",
        why="A bill shot at the table reaches the model with its GPS intact.",
    ),
    Mutation(
        feature="F26",
        name="scan money field declared lax int",
        path=SCHEMAS,
        old="    total_vnd: PositiveMoneyVnd\n    occurred_on: date | None",
        new="    total_vnd: int\n    occurred_on: date | None",
        expect="RED",
        why="A plain int launders a float total before any body assert runs.",
    ),
    Mutation(
        feature="F26",
        name="domain stringifies a float total instead of refusing it",
        path=SCREENSHOT_DOMAIN,
        old='    total_text = raw.get("total_text")\n    if not isinstance(total_text, str):',
        new='    total_text = raw.get("total_text")\n    if isinstance(total_text, (int, float)):\n        total_text = str(total_text)\n    if not isinstance(total_text, str):',
        expect="RED",
        why="Money law 1 at the boundary the model actually writes through.",
    ),
    Mutation(
        feature="F26",
        name="GIU TINH CHAT: refusal wording reworded",
        path=SCREENSHOT_ROUTES,
        old='_UNSUPPORTED_IMAGE_DETAIL = "Định dạng ảnh chụp màn hình không được hỗ trợ."',
        new='_UNSUPPORTED_IMAGE_DETAIL = "Ảnh chụp màn hình này chưa đúng định dạng."',
        expect="GREEN",
        why="The wire code and status are the contract; the prose is not.",
    ),
    Mutation(
        feature="F26",
        name="GIU TINH CHAT: __all__ entries reordered",
        path=SCREENSHOT_SKILL,
        old='__all__ = [\n    "ALLOWED_MIME_TYPES",\n    "MAX_IMAGE_BYTES",',
        new='__all__ = [\n    "MAX_IMAGE_BYTES",\n    "ALLOWED_MIME_TYPES",',
        expect="GREEN",
        why="Export order is style; the exported names are what callers bind.",
    ),
    # ================================================================ F34 ===
    Mutation(
        feature="F34",
        name="average per person divided with / instead of //",
        path=BUDGET_DOMAIN,
        old="        finished_total // finished_headcount if finished_headcount else None",
        new="        finished_total / finished_headcount if finished_headcount else None",
        expect="RED",
        why="Money law 1: a float average is money that stopped being integer.",
    ),
    Mutation(
        feature="F34",
        name="spend per person divided with / instead of //",
        path=BUDGET_DOMAIN,
        old="        spent = split_total // headcount if headcount else 0",
        new="        spent = split_total / headcount if headcount else 0",
        expect="RED",
        why="Same law on the figure a group reads while still on the trip.",
    ),
    Mutation(
        feature="F34",
        name="budget read drops its active-membership requirement",
        path=PERMISSIONS,
        old='    "view_group_budget": {\n        "roles": {"group_admin", "member"},\n        "requires": ("is_group_member",),\n    },',
        new='    "view_group_budget": {\n        "roles": {"group_admin", "member"},\n        "requires": (),\n    },',
        expect="RED",
        why="A context id from a link must not read the group's ledger totals.",
    ),
    Mutation(
        feature="F34",
        name="GIU TINH CHAT: comparison branch inverted",
        path=BUDGET_DOMAIN,
        old='    elif delta < 0:\n        verdict = "re-hon"\n    else:\n        verdict = "cao-hon"',
        new='    elif delta > 0:\n        verdict = "cao-hon"\n    else:\n        verdict = "re-hon"',
        expect="GREEN",
        why="Past the tolerance test delta is non-zero, so both spellings agree.",
    ),
    Mutation(
        feature="F34",
        name="GIU TINH CHAT: result dict keys reordered",
        path=BUDGET_DOMAIN,
        old='        "candidate_per_person_vnd": candidate,\n        "delta_vnd": delta,',
        new='        "delta_vnd": delta,\n        "candidate_per_person_vnd": candidate,',
        expect="GREEN",
        why="A dict is keyed, not ordered; the schema reads it by name.",
    ),
]


def purge_bytecode() -> None:
    """Drop stale .pyc so a reverted file is not shadowed by its mutation."""

    for cache in API.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def run_suite() -> tuple[bool, str]:
    """Return (green, last summary line) for the covering set."""

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", *PYTEST_TARGETS, "-q"],
        cwd=API,
        capture_output=True,
        text=True,
    )
    # Only the final summary line. Grepping the whole output is how a harness
    # reads "1527 passed" out of the docstring of the one test that is failing.
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    summary = lines[-1] if lines else "<no output>"
    return completed.returncode == 0, summary


def restore(path: Path) -> None:
    subprocess.run(
        ["git", "checkout", "--", str(path.relative_to(REPO))],
        cwd=REPO,
        check=True,
    )
    purge_bytecode()


def main() -> int:
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True
    ).stdout.strip()
    if dirty:
        print("REFUSING: working tree is dirty; revert would discard real work.")
        print(dirty)
        return 2

    purge_bytecode()
    green, summary = run_suite()
    print(f"BASELINE      {'GREEN' if green else 'RED  '}  {summary}")
    if not green:
        print("REFUSING: baseline is not green, so no row below means anything.")
        return 2

    rows, failures = [], 0
    for mutation in MUTATIONS:
        source = mutation.path.read_text(encoding="utf-8")
        occurrences = source.count(mutation.old)
        if occurrences != 1:
            # Guessing an anchor that matches twice patches the wrong copy and
            # reports a colour for a mutation that was never applied where the
            # table claims.
            print(f"REFUSING: anchor for {mutation.name!r} matched {occurrences}x")
            return 2

        mutation.path.write_text(
            source.replace(mutation.old, mutation.new, 1), encoding="utf-8"
        )
        purge_bytecode()
        try:
            observed_green, summary = run_suite()
        finally:
            restore(mutation.path)

        observed = "GREEN" if observed_green else "RED"
        ok = observed == mutation.expect
        failures += not ok
        rows.append((mutation, observed, ok, summary))

    print()
    for feature in ("F24", "F26", "F34"):
        subset = [row for row in rows if row[0].feature == feature]
        if not subset:
            continue
        print("=" * 78)
        print(f"{feature}   {'expect':7} {'got':6} {'ok':3} mutation")
        print("-" * 78)
        for mutation, observed, ok, summary in subset:
            print(
                f"      {mutation.expect:7} {observed:6} "
                f"{'..' if ok else 'XX':3} {mutation.name}\n{'':25}{summary}"
            )
        greens = sum(row[0].expect == "GREEN" for row in subset)
        print(f"      -> {len(subset) - greens} RED / {greens} GIU TINH CHAT")
        print()

    if failures:
        print(f"\n{failures} row(s) did not match. The gate does not measure what")
        print("this table claims it measures.")
        return 1
    reds = sum(row[0].expect == "RED" for row in rows)
    greens = len(rows) - reds
    print(
        f"\nAll {len(rows)} rows matched: {reds} RED (gate bites), "
        f"{greens} GREEN (gate is not merely edit-detection)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
