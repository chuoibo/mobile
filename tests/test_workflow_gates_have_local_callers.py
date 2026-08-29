"""A gate that only a workflow calls is not a gate on a day the workflow cannot run.

GitHub Actions stopped starting jobs at 07:45Z on 2026-08-29 -- every run since
ends in three seconds with "The job was not started because recent account
payments have failed or your spending limit needs to be increased". Nothing was
wrong with the code. The jobs simply never ran, on all three workflows, for both
`push` and `pull_request`.

That turned a question nobody had asked into an urgent one: *which of our gates
exist only inside those workflows?* Because those had not merely gone
unenforced, they had stopped executing entirely, while every pull request kept
showing a red X that meant "billing" and not "broken" -- so the red carried no
information and people learned to click past it.

A hand sweep at the time found exactly one: `scripts/check_dockerfile_pinning.sh`
was referenced once in the whole repository, by `.github/workflows/test.yml`.
`scripts/check_alembic_heads.py` had been the same until a day earlier, when it
was moved into this directory for this same reason.

This test is that hand sweep, kept. It is deliberately a meta-gate: it does not
check any Dockerfile, migration or lockfile itself. It checks that every gate
script a workflow invokes is also reachable from something a person can run on a
laptop -- the standard command `python3 -m pytest services/api/tests tests -q`,
or a `make` target. The next gate somebody writes workflow-only fails here on
the commit that adds it, instead of being discovered the next time CI dies.

## What this proves and what it does not

It proves each such script has a *caller* outside the workflows. It does not
prove the caller is any good -- a test that invokes a script and asserts nothing
would satisfy this. That weaker claim is still the one worth automating, because
the failure it caught was total absence, not weak assertion.

It also says nothing about workflow steps written inline rather than as a script.
Those cannot be detected this way; the offline DDL render in the `api` job is one
such step, and it is covered locally by
`services/api/tests/db/test_migration_matches_models.py`, by hand and by luck.
"""

from __future__ import annotations

import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
TESTS = REPO_ROOT / "tests"
API_TESTS = REPO_ROOT / "services" / "api" / "tests"
MAKEFILE = REPO_ROOT / "Makefile"

# Scripts a workflow may legitimately own alone, each with the reason it cannot
# run off a laptop -- needs a GitHub token, a runner-only path, a secret. Empty
# on purpose: today every gate script in the workflows is runnable locally, and
# an entry here is a claim a reviewer should have to read. Prefer wiring the
# script into `tests/` over adding a line here.
CI_ONLY: dict[str, str] = {}

# `scripts/foo.sh` / `scripts/foo.py`, however it is quoted or prefixed in the
# YAML. Matching the path rather than parsing YAML keeps this independent of
# whether PyYAML is installed -- the standard gate command must not grow a
# dependency to run one test.
SCRIPT_REFERENCE = re.compile(r"scripts/([A-Za-z0-9_.-]+\.(?:sh|py))")


def _scripts_invoked_by_workflows() -> dict[str, set[str]]:
    """Map each referenced script to the workflow files that reference it."""
    found: dict[str, set[str]] = {}
    for workflow in sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")):
        text = workflow.read_text(encoding="utf-8")
        for name in SCRIPT_REFERENCE.findall(text):
            found.setdefault(name, set()).add(workflow.name)
    return found


def _local_callers(script: str) -> list[str]:
    """Places a person can run that reach this script, excluding the workflows.

    This file is excluded from the search. It names every script it reports on,
    so counting itself would make the gate self-satisfying: the moment it
    complained about a script it would also be a caller of it, and go green.
    """
    callers: list[str] = []
    haystacks: list[pathlib.Path] = []
    for root in (TESTS, API_TESTS):
        if root.is_dir():
            haystacks.extend(
                p for p in root.rglob("*.py") if "__pycache__" not in p.parts
            )
    if MAKEFILE.is_file():
        haystacks.append(MAKEFILE)

    for path in haystacks:
        if path.resolve() == pathlib.Path(__file__).resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if script in text:
            callers.append(str(path.relative_to(REPO_ROOT)))
    return callers


class WorkflowGatesHaveLocalCallers(unittest.TestCase):
    def test_the_workflows_reference_some_scripts_at_all(self):
        """Guard the guard.

        If the reference pattern ever stops matching -- the workflows move, get
        renamed, or start invoking scripts a different way -- every assertion
        below would iterate an empty set and pass. A gate whose subject has
        silently become empty is the exact shape of failure this file exists to
        catch, so it must not be able to happen here.
        """
        self.assertTrue(WORKFLOWS.is_dir(), f"{WORKFLOWS} is missing")
        invoked = _scripts_invoked_by_workflows()
        self.assertGreaterEqual(
            len(invoked),
            2,
            "no scripts/* references found in .github/workflows -- either the "
            "workflows stopped calling scripts, or this test's pattern went stale",
        )

    def test_every_workflow_gate_script_is_runnable_without_actions(self):
        orphans = {}
        for script, workflows in sorted(_scripts_invoked_by_workflows().items()):
            if script in CI_ONLY:
                continue
            if not _local_callers(script):
                orphans[script] = sorted(workflows)

        self.assertEqual(
            orphans,
            {},
            "these gate scripts run ONLY inside a GitHub workflow, so they stop "
            "existing the moment Actions does:\n"
            + "\n".join(
                f"  scripts/{name} -- referenced only by {', '.join(wfs)}"
                for name, wfs in sorted(orphans.items())
            )
            + "\n\nGive each one a caller under tests/ so it runs in "
            "`python3 -m pytest services/api/tests tests -q`, or add it to "
            "CI_ONLY in this file with the reason it cannot run locally.",
        )

    def test_every_referenced_script_actually_exists(self):
        """A workflow naming a script that is not there fails only when the job
        runs. While Actions is down that is never, so the typo would sit on main
        looking like a gate."""
        missing = {
            f"scripts/{name}": sorted(workflows)
            for name, workflows in sorted(_scripts_invoked_by_workflows().items())
            if not (REPO_ROOT / "scripts" / name).is_file()
        }
        self.assertEqual(
            missing, {}, f"workflows reference scripts that do not exist: {missing}"
        )

    def test_ci_only_entries_are_justified_and_real(self):
        """An allowlist that can hold a stale or unexplained entry is a hole."""
        for name, reason in CI_ONLY.items():
            with self.subTest(script=name):
                self.assertTrue(
                    (REPO_ROOT / "scripts" / name).is_file(),
                    f"CI_ONLY names scripts/{name}, which does not exist",
                )
                self.assertIn(
                    name,
                    _scripts_invoked_by_workflows(),
                    f"CI_ONLY names scripts/{name}, which no workflow invokes -- drop the entry",
                )
                self.assertGreaterEqual(
                    len(reason.split()),
                    4,
                    f"CI_ONLY[{name}] needs a real reason, got {reason!r}",
                )


if __name__ == "__main__":
    unittest.main()
