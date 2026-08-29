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
    "api": ("api", "migration", "client-routes"),
    "contract": ("contract",),
    "docker": ("docker",),
    "shared": ("shared",),
    "mobile": ("mobile",),
    "repository-postgres": ("postgres",),
}

# Gate stages that deliberately map to no workflow job, and why.
#
# `test_every_gate_stage_is_claimed_by_some_job` used to require that every
# stage appear in COVERED_BY, while its own docstring said the opposite: "A
# stage nobody maps to is not wrong -- the gate may legitimately run more than
# CI -- but it must be a deliberate, recorded choice rather than a leftover".
# There was nowhere to record it, so the only way to add a local-only stage was
# to invent a workflow job for it. This is that place. An entry needs a reason,
# and a reason that is empty is not an entry.
LOCAL_ONLY: dict[str, str] = {
    "gemini": (
        "Tầng model sống (services/api/tests/live). CI chưa bao giờ chạy nó và "
        "cũng không chạy được: repository không có secret GEMINI_API_KEY, nên "
        "một job ở đây sẽ vĩnh viễn skip — đúng thứ đồ trang trí mà cả thư mục "
        "này tồn tại để từ chối. Nó vẫn phải là một chặng, vì 'AI là THẬT' là "
        "khẳng định lớn nhất của sản phẩm và đây là tầng duy nhất kiểm nó."
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
        if line.startswith("  ") and parts and re.fullmatch(r"[a-z-]+", parts[0]):
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
            "If that is intended, record them in LOCAL_ONLY with the reason the "
            "local gate runs more than CI does.",
        )

    def test_every_local_only_stage_gives_a_reason(self):
        """An entry with no reason is a hole with a name on it.

        The whole value of LOCAL_ONLY over deleting the assertion is that the
        next reader can tell a deliberate choice from a stage somebody wanted to
        stop failing this file.
        """
        for stage, reason in sorted(LOCAL_ONLY.items()):
            with self.subTest(stage=stage):
                self.assertTrue(
                    reason and reason.strip(),
                    f"LOCAL_ONLY[{stage!r}] has no reason",
                )
                self.assertGreater(
                    len(reason.strip()),
                    40,
                    f"LOCAL_ONLY[{stage!r}] says {reason.strip()!r}, which does "
                    "not explain anything to the person who finds it later",
                )

    def test_the_local_only_list_has_no_stages_that_are_gone(self):
        """Same failure as a stale COVERED_BY entry: it describes a gate that is
        not there any more, and reads as though something is still covered."""
        stages = set(_gate_stages())
        stale = sorted(set(LOCAL_ONLY) - stages)
        self.assertEqual(
            stale,
            [],
            f"LOCAL_ONLY names stages scripts/gate.sh no longer has: {stale}.",
        )

    def test_no_stage_is_both_claimed_and_local_only(self):
        """A stage cannot be both covered by CI and deliberately outside it. If
        it is in both lists, one of them is wrong and the reader cannot tell
        which."""
        claimed = {stage for stages in COVERED_BY.values() for stage in stages}
        both = sorted(claimed & set(LOCAL_ONLY))
        self.assertEqual(
            both,
            [],
            f"these stages are in COVERED_BY and in LOCAL_ONLY at once: {both}",
        )


if __name__ == "__main__":
    unittest.main()
