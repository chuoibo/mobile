"""Every job in the workflows must be reachable from `scripts/gate.sh`.

## Why

`test_workflow_gates_have_local_callers.py` (#148) closed half of the problem
that GitHub Actions dying exposed: a gate that is a *script* must have a caller
outside the workflows. It names the half it cannot close, in its own words:

    "It also says nothing about workflow steps written inline rather than as a
     script. Those cannot be detected this way; the offline DDL render in the
     `api` job is one such step, and it is covered locally by
     services/api/tests/db/test_migration_matches_models.py, by hand and by
     luck."

By hand and by luck is the part this file replaces. `scripts/gate.sh` runs the
inline steps too -- the offline DDL render, the image running as non-root, the
container answering /healthz, the native bundle, and the environment variable
that turns three accessibility checks from decoration into a gate. This test
holds the line that it keeps doing so: add a job to a workflow and this fails on
the commit that adds it, rather than the next time somebody wonders whether the
local gate still means anything.

## What this proves and what it does not

It proves each workflow job has a *named stage* in the local gate. It does not
prove the stage runs the same commands the job runs -- nobody can prove that
while Actions cannot execute, and a shell script and a YAML job are not
comparable by any check worth trusting. The claim is deliberately the weak one,
for the same reason #148 gives: the failure being guarded against is total
absence, not weak equivalence.

Drift between the two remains possible and is a thing a reviewer has to look
for. `COVERED_BY` is where that review is recorded.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
GATE = REPO_ROOT / "scripts" / "gate.sh"

# workflow job id -> the gate stage that covers it.
#
# `lint` maps to `ruff` and not to a stage of its own name because the local
# form is strictly wider: CI can only diff pushed commits, while the gate's
# one-argument call to ruff_changed.sh compares the merge base against the
# working tree, so it also sees changes that are not committed yet.
#
# `api` maps to three stages: the job runs the test suite AND two inline
# checks that need Python and nothing else -- `alembic upgrade head --sql`, and
# the client/API route check. The gate splits them so a migration that cannot
# compile is not reported as "the test suite failed".
#
# `contract` and `client-routes` are two stages and not one on purpose. They
# read the same two files and answer different questions: `contract` asks
# whether a call sends X-Actor-ID, `client-routes` asks whether the path it
# calls exists at all. Folding them together is not a tidy-up -- it is how one
# of them stops running, which is exactly what happened when both were briefly
# named `contract` (see tests/test_gate_stage_bodies_are_unique.py).
#
# `repo-guard` maps to two stages because the job runs two scans that answer
# different questions. `tree HEAD` asks what the branch is delivering;
# `range base..head` asks what it ever committed. A secret added and then
# deleted a commit later is invisible to the first and caught by the second,
# so folding them into one stage would silently drop the only check that sees
# it -- see tests/test_gate_guard_range_stage.py, which holds that line.
COVERED_BY: dict[str, tuple[str, ...]] = {
    "repo-guard": ("guard", "guard-range"),
    "lint": ("ruff",),
    # `server-routes` joins the same job for the same reason `client-routes` is
    # there: it needs Python and the two source trees, nothing else. It is a
    # fourth stage rather than a fold into `client-routes` because the two ask
    # opposite questions -- one whether a path the app calls exists, one whether
    # a route the API declares is called -- and the comment below on `contract`
    # records what folding two questions into one stage cost the last time.
    "api": ("api", "migration", "client-routes", "server-routes"),
    # Two stages, one job. `contract` asks whether a call sends X-Actor-ID;
    # `cors` asks whether the headers it does send survive a browser's
    # preflight at all. They share a job because they need the identical
    # setup, and stay two stages for the reason given just above.
    "contract": ("contract", "cors"),
    # The third link in the chain `client-routes` and `server-routes` are the
    # first two of, and a job of its own rather than a fifth stage on `api`
    # because it needs neither the API source nor a pip install -- the checker
    # is stdlib Python reading apps/mobile only. Behind `api` it would sit
    # after a dependency install and a full pytest run, so a red suite would
    # stop it answering a question the suite has nothing to do with.
    "screens": ("screens",),
    # `pinned-import` has no job of its own because the `docker` job already
    # proves what it proves: it builds the image and starts the container, so
    # an app that cannot be imported under the pinned fastapi fails there too.
    # It is a separate LOCAL stage because that proof cost a full image build
    # and a HEALTHCHECK wait, so in practice it was skipped before pushing --
    # and an app that could not be imported at all reached main that way. Two
    # seconds gets run; ninety seconds gets skipped.
    "docker": ("docker", "pinned-import"),
    "shared": ("shared",),
    "mobile": ("mobile",),
    "repository-postgres": ("postgres",),
    # The one job where both sides of a request are real. It is its own job
    # rather than a step of `mobile` because it needs what that job does not:
    # a Python that can serve the API and a database to serve it from. Folding
    # it in would make the whole mobile job unrunnable on a machine with no
    # Docker, and the way that gets resolved is by deleting the slice.
    "e2e": ("e2e",),
}

# Stages that deliberately have no workflow job, because the question they ask
# does not exist on a CI runner.
#
# This is the "deliberate, recorded choice" that
# `test_every_gate_stage_is_claimed_by_some_job` asks for, in the one shape
# COVERED_BY cannot express: `pinned-import` has no job of its own but the
# `docker` job does prove what it proves, so it maps honestly. A stage with no
# CI counterpart at all has nothing to map to, and inventing one would make
# COVERED_BY say a job checks something it does not.
#
# It is not a place to park a stage that is merely inconvenient in CI --
# `test_local_only_stages_are_really_local` refuses an entry whose name a
# workflow job declares, an entry already claimed in COVERED_BY, and an entry
# the gate no longer has.
LOCAL_ONLY: dict[str, str] = {
    "harness-deploy": (
        "asks whether the `agent_supervisor.py` / `agent_checkpoint.py` copies "
        "installed under ~/agent-harness -- the ones the launcher actually "
        "executes -- match what was merged to main. A CI runner installs no "
        "harness, so a job would be comparing against an empty directory and "
        "reporting green for the reason this stage exists to refuse. It runs "
        "locally because the gap was real and silent: measured 2026-08-31, the "
        "installed supervisor was three commits behind and the three it lacked "
        "included both #470 and #477, the two clock fixes -- merged, reviewed, "
        "gated, and never running, #470 for three days."
    ),
    "demo-watch": (
        "asks whether the demo box on 8099 is still being watched, and whether "
        "its last recorded verdict was about main. A CI runner has no demo box "
        "and no crontab of ours, so a job would be answering about nothing. It "
        "runs locally because the demo drifted from main twice -- 58 routes "
        "against 62 for sixteen commits, then 65 against 69 -- and neither time "
        "was a gate failing: the gate that would have caught it had no caller."
    ),
    "hero-walk": (
        "asks whether somebody recently walked the whole hero path -- photo to "
        "Gemini to assignment to split to guest page -- on the demo box, and "
        "whether it worked. Local for the same reason as demo-watch (a runner "
        "has no demo box) and for one of its own: the walk spends a real Gemini "
        "call, which is not something to put on every push. It exists because "
        "the scan seam had no gate at all: `duong-bill.test.mjs` starts from a "
        "hand-written reading, the client unit tests replay a wire body frozen "
        "on 2026-08-29, and the live model tier is opt-in behind "
        "MOBILE_LIVE_GEMINI, which `grep -rn` finds in no script and no "
        "workflow. Two green halves that never met."
    ),
}

JOB_ID = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$", re.M)


def _workflow_jobs() -> dict[str, str]:
    """Map each job id to the workflow file that declares it."""
    jobs: dict[str, str] = {}
    for workflow in sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")):
        text = workflow.read_text(encoding="utf-8")
        if "\njobs:" not in text:
            continue
        body = text.split("\njobs:", 1)[1]
        for match in JOB_ID.finditer(body):
            jobs[match.group(1)] = workflow.name
    return jobs


def _gate_stages() -> list[str]:
    """The stage names the gate itself reports, asked of the gate rather than
    parsed out of it. Reading the STAGES array with a regex would keep passing
    after a rename that breaks the script, because the array would still be
    there to match."""
    result = subprocess.run(
        ["bash", str(GATE), "--list"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"gate.sh --list exited {result.returncode}: {result.stderr}"
        )
    stages = []
    for line in result.stdout.splitlines():
        parts = line.split()
        # Stage lines are indented and start with the bare name.
        # Digits belong in the class: `[a-z-]+` dropped the `e2e` stage, and a
        # stage missing from this list is one `test_every_gate_stage_is_claimed
        # _by_some_job` cannot notice going unclaimed.
        if line.startswith("  ") and parts and re.fullmatch(r"[a-z0-9-]+", parts[0]):
            stages.append(parts[0])
    return stages


class GateCoversEveryWorkflowJob(unittest.TestCase):
    def test_the_gate_script_is_there_and_answers(self):
        """Guard the guard.

        Every assertion below iterates something derived from these two lists.
        If the gate stopped listing stages, or the job pattern went stale, the
        rest of this file would compare empty against empty and pass -- which
        is the failure shape the whole directory exists to refuse.
        """
        self.assertTrue(GATE.is_file(), f"{GATE} is missing")
        self.assertGreaterEqual(
            len(_gate_stages()),
            5,
            "scripts/gate.sh --list reported almost no stages -- either the gate "
            "lost them or this test's parser went stale",
        )
        self.assertGreaterEqual(
            len(_workflow_jobs()),
            5,
            "found almost no jobs in .github/workflows -- the job pattern is stale",
        )

    def test_every_workflow_job_has_a_local_stage(self):
        unmapped = {
            job: workflow
            for job, workflow in sorted(_workflow_jobs().items())
            if job not in COVERED_BY
        }
        self.assertEqual(
            unmapped,
            {},
            "these workflow jobs have no stage in scripts/gate.sh, so they stop "
            "existing the moment Actions does:\n"
            + "\n".join(f"  {job} -- declared in {wf}" for job, wf in unmapped.items())
            + "\n\nAdd a stage to scripts/gate.sh and map it in COVERED_BY here.",
        )

    def test_every_mapped_stage_exists_in_the_gate(self):
        """A mapping naming a stage the gate does not have is a false claim of
        coverage, and reads as coverage to anyone skimming this file."""
        stages = set(_gate_stages())
        for job, mapped in sorted(COVERED_BY.items()):
            for stage in mapped:
                with self.subTest(job=job, stage=stage):
                    self.assertIn(
                        stage,
                        stages,
                        f"COVERED_BY maps job {job!r} to gate stage {stage!r}, "
                        f"which scripts/gate.sh does not have. Stages: {sorted(stages)}",
                    )

    def test_the_mapping_has_no_entries_for_jobs_that_are_gone(self):
        """A stale entry keeps a deleted job looking covered and hides that the
        stage behind it now guards nothing."""
        jobs = set(_workflow_jobs())
        stale = sorted(set(COVERED_BY) - jobs)
        self.assertEqual(
            stale,
            [],
            f"COVERED_BY names jobs no workflow declares any more: {stale}. "
            "Drop the entries, and check whether the gate stages behind them "
            "are still worth running.",
        )

    def test_every_gate_stage_is_claimed_by_some_job(self):
        """The other direction. A stage nobody maps to is not wrong -- the gate
        may legitimately run more than CI -- but it must be a deliberate,
        recorded choice rather than a leftover, so it is listed here."""
        claimed = {stage for stages in COVERED_BY.values() for stage in stages}
        unclaimed = sorted(set(_gate_stages()) - claimed - set(LOCAL_ONLY))
        self.assertEqual(
            unclaimed,
            [],
            f"scripts/gate.sh has stages no workflow job maps to: {unclaimed}. "
            "If that is intended, map them in COVERED_BY with a comment saying "
            "why the local gate runs more than CI does -- or, if no CI job "
            "could ever cover them, record them in LOCAL_ONLY with the reason.",
        )

    def test_local_only_stages_are_really_local(self):
        """LOCAL_ONLY must not become the drawer unclaimed stages go to be quiet.

        It subtracts from the assertion above, so every entry weakens that
        check by exactly one stage. The three ways it could be abused are the
        three things refused here: naming a stage CI *does* run, double-listing
        one COVERED_BY already maps, and leaving behind a stage the gate has
        since dropped -- the last being how the list would slowly stop
        describing the gate at all.
        """
        stages = set(_gate_stages())
        jobs = set(_workflow_jobs())
        claimed = {stage for stages_ in COVERED_BY.values() for stage in stages_}
        for stage, reason in LOCAL_ONLY.items():
            self.assertIn(
                stage,
                stages,
                f"LOCAL_ONLY lists '{stage}', which scripts/gate.sh no longer has.",
            )
            self.assertNotIn(
                stage,
                jobs,
                f"a workflow job is named '{stage}', so CI does run it -- map it "
                "in COVERED_BY instead of excusing it here.",
            )
            self.assertNotIn(
                stage,
                claimed,
                f"'{stage}' is already claimed in COVERED_BY; listing it here too "
                "hides which of the two is the real reason it passes.",
            )
            self.assertTrue(
                reason.strip(),
                f"LOCAL_ONLY['{stage}'] has no reason recorded.",
            )


if __name__ == "__main__":
    unittest.main()
