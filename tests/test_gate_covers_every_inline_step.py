"""Every inline workflow step must be accounted for on a laptop.

## The hole this closes

Two meta-gates already stand here, and each names the piece it cannot reach.

`test_workflow_gates_have_local_callers.py` (#148) makes every gate that is a
*script* have a caller outside the workflows. Its own last paragraph:

    "It also says nothing about workflow steps written inline rather than as a
     script. Those cannot be detected this way."

`test_gate_covers_every_workflow_job.py` answers that at the granularity of a
*job*: every job in the workflows has a named stage in `scripts/gate.sh`. That
is the right claim for a job appearing or disappearing, and it is blind to
everything inside one. The `api` job is mapped, so the `api` job is covered --
and a thirty-line inline step added to it tomorrow inherits that coverage
without anybody running it anywhere.

This file is that granularity. Every step in every workflow that runs shell is
listed below with what it is and where it runs locally. Add a step and this
fails on the commit that adds it.

## Why it matters more than it looks

GitHub Actions stopped starting jobs at 07:45Z on 2026-08-29 -- every run since
ends in seconds with "The job was not started because recent account payments
have failed". Re-measured 2026-08-30T00:5xZ: the last 300 runs are 300
failures and 0 successes, and the annotation on the newest one still says
billing. So `scripts/gate.sh` is not a convenience that mirrors CI. It is the
only place these commands run at all. A step that drifts out of it does not
degrade to "checked later" -- it stops being checked by anything.

Writing the table found one already: `test.yml`'s lint job asserts a `ruff==`
pin exists in services/api/requirements-dev.txt and exits 1 when it does not,
and nothing outside that dead workflow looked at the pin -- `ruff_changed.sh`
only checks a ruff is on PATH, and no test greps `ruff==`. `do_ruff` in
scripts/gate.sh now checks it.

## What this proves and what it does not

It proves each inline step is *classified* and, when it is a gate, that it
names a stage `scripts/gate.sh` actually has. It does not prove the stage runs
the same shell -- a bash function and a YAML block are not comparable by any
check worth trusting, and nobody can run the YAML to compare while Actions is
down.

`body_sha` narrows that gap without pretending to close it. It pins the text
each entry was reviewed against, so editing a step's commands fails here and
the reviewer is asked whether the local stage still does the same thing. It is
the repo guard's allowlist idea -- pin the bytes, re-review on change -- and it
catches drift only in the direction of the workflow moving first.

`kind` is where the review is recorded, and `SETUP`/`INFO` are the entries a
reviewer should read hardest, because they are the ones claiming a step needs
no local runner. `test_nothing_that_asserts_is_filed_as_setup_or_info` keeps
that from becoming a place to hide a gate.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from _workflow_steps import run_steps  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "scripts" / "gate.sh"

GATE_KIND = "GATE"
SETUP_KIND = "SETUP"
INFO_KIND = "INFO"


@dataclasses.dataclass(frozen=True)
class Covered:
    kind: str
    """GATE (asserts something), SETUP (prepares the machine), INFO (prints)."""

    stages: tuple[str, ...]
    """Stages of scripts/gate.sh that run this step's work. GATE only."""

    body_sha: str
    """First 16 hex of sha256 over the dedented shell, as reviewed."""

    why: str
    """Required for SETUP and INFO: why this step needs no local runner."""


# Every `run:` step in .github/workflows, keyed workflow::job::label. The label
# is the step's `name:`, or its `id:` when it has none, or the first line it
# runs -- `npm ci` in the mobile job is a bare `run:` under an `if:`.
#
# Regenerate one entry with:  python3 tests/_workflow_steps.py
# Pasting the whole output is not review. The value of this table is that a
# person decided what each step is and where it runs.
INLINE_STEPS: dict[str, Covered] = {
    # --- repo-guard.yml ---------------------------------------------------
    "repo-guard.yml::repo-guard::Run synthetic guard tests": Covered(
        kind=GATE_KIND,
        stages=("api",),
        body_sha="927df439250056de",
        # The workflow runs it through unittest directly; the `api` stage is
        # `pytest services/api/tests tests`, which collects the same file.
        why="tests/test_repo_guard.py runs in the standard pytest command",
    ),
    "repo-guard.yml::repo-guard::Scan the complete checked-out tree": Covered(
        kind=GATE_KIND,
        stages=("guard",),
        body_sha="ac78c294ab4241ad",
        why="",
    ),
    "repo-guard.yml::repo-guard::Refuse a migration tree with more than one head": Covered(
        kind=GATE_KIND,
        stages=("api",),
        body_sha="e7de4fb969944667",
        why="tests/test_alembic_heads.py calls scripts/check_alembic_heads.py",
    ),
    "repo-guard.yml::repo-guard::Scan every commit introduced by the pull request": Covered(
        kind=GATE_KIND,
        stages=("guard-range",),
        body_sha="8d1bdbf43888c4c0",
        why="",
    ),
    "repo-guard.yml::repo-guard::Scan every commit introduced by the push": Covered(
        kind=GATE_KIND,
        stages=("guard-range",),
        body_sha="c752b4de6efe4d7b",
        # Same question -- what did this branch ever commit -- reached by the
        # merge base rather than by github.event.before.
        why="",
    ),
    # --- test.yml: lint ---------------------------------------------------
    "test.yml::lint::Install the pinned ruff": Covered(
        kind=GATE_KIND,
        stages=("ruff",),
        body_sha="777ea75c46c95f21",
        # The entry that found the hole. Until 2026-08-30 this step's
        # assertion -- that a `ruff==` pin exists at all -- ran in no other
        # place, so with Actions down it ran nowhere. do_ruff checks it now.
        why="",
    ),
    "test.yml::lint::Check the files this pull request changes": Covered(
        kind=GATE_KIND,
        stages=("ruff",),
        body_sha="34fc7988a9d6ad88",
        why="",
    ),
    "test.yml::lint::Check the files this push changes": Covered(
        kind=GATE_KIND,
        stages=("ruff",),
        body_sha="4a5e6f2d72f0f84e",
        why="",
    ),
    # --- test.yml: api ----------------------------------------------------
    "test.yml::api::Install": Covered(
        kind=SETUP_KIND,
        stages=(),
        body_sha="8538143a61ef5f34",
        why="pip install of the pinned dev requirements; asserts nothing about the tree",
    ),
    "test.yml::api::Test": Covered(
        kind=GATE_KIND,
        stages=("api",),
        body_sha="4de3b2ef5948cb27",
        why="",
    ),
    "test.yml::api::Every route the app calls exists": Covered(
        kind=GATE_KIND,
        stages=("client-routes",),
        body_sha="9e42404468c805b6",
        why="",
    ),
    "test.yml::api::Migration renders to DDL": Covered(
        kind=GATE_KIND,
        stages=("migration",),
        body_sha="ff578e0fc31141e6",
        why="",
    ),
    # --- test.yml: contract -----------------------------------------------
    "test.yml::contract::present": Covered(
        kind=GATE_KIND,
        stages=("contract",),
        body_sha="e549a91f8b2f09d5",
        # Refuse-to-skip: apps/mobile present without src/ is a defect, not an
        # absence. check_prereq's return 2 is the same rule.
        why="",
    ),
    "test.yml::contract::Install": Covered(
        kind=SETUP_KIND,
        stages=(),
        body_sha="8538143a61ef5f34",
        why="pip install of the pinned dev requirements; asserts nothing about the tree",
    ),
    "test.yml::contract::The checker can be red": Covered(
        kind=GATE_KIND,
        stages=("contract",),
        body_sha="d96eaa8e11998db2",
        why="",
    ),
    "test.yml::contract::Every route wanting X-Actor-ID is called with it": Covered(
        kind=GATE_KIND,
        stages=("contract",),
        body_sha="b09efaf22972b612",
        why="",
    ),
    # --- test.yml: docker -------------------------------------------------
    "test.yml::docker::Base images are pinned by digest": Covered(
        kind=GATE_KIND,
        stages=("docker",),
        body_sha="eb4e5a75fe27bdee",
        why="",
    ),
    "test.yml::docker::Build": Covered(
        kind=GATE_KIND,
        stages=("docker",),
        body_sha="a1096490d8b8e7fa",
        # No `exit 1` of its own, but the build failing is the assertion.
        why="",
    ),
    "test.yml::docker::Runs as a non-root user": Covered(
        kind=GATE_KIND,
        stages=("docker",),
        body_sha="b02e4d152ce162e2",
        why="",
    ),
    "test.yml::docker::No test tooling in the runtime image": Covered(
        kind=GATE_KIND,
        stages=("docker",),
        body_sha="677e558f8eb3dc3c",
        why="",
    ),
    "test.yml::docker::The container actually serves /healthz": Covered(
        kind=GATE_KIND,
        stages=("docker",),
        body_sha="732b09e74f85a7f0",
        why="",
    ),
    "test.yml::docker::Image size": Covered(
        kind=INFO_KIND,
        stages=(),
        body_sha="83312e5632b67af6",
        why="prints ::notice:: with the image size and has no threshold to fail against",
    ),
    # --- test.yml: shared -------------------------------------------------
    "test.yml::shared::present": Covered(
        kind=GATE_KIND,
        stages=("shared",),
        body_sha="ca2483b7fbae9fb6",
        why="",
    ),
    "test.yml::shared::Both surfaces agree on the same golden cases": Covered(
        kind=GATE_KIND,
        stages=("shared",),
        body_sha="45df49e243893a25",
        why="",
    ),
    # --- test.yml: mobile -------------------------------------------------
    "test.yml::mobile::present": Covered(
        kind=GATE_KIND,
        stages=("mobile",),
        body_sha="2d17f2983dfabd6e",
        why="",
    ),
    "test.yml::mobile::npm ci": Covered(
        kind=SETUP_KIND,
        stages=(),
        body_sha="9db3f780def6105e",
        # The gate's mobile prerequisite refuses to run without node_modules
        # rather than installing them, so this has no local counterpart by
        # design: a gate that installs is a gate that can hide a broken lock.
        why="installs node_modules from the lockfile; asserts nothing about the tree",
    ),
    "test.yml::mobile::Types": Covered(
        kind=GATE_KIND,
        stages=("mobile",),
        body_sha="81940cc0844279f0",
        why="",
    ),
    "test.yml::mobile::App bundles, client never computes money, shell renders right": Covered(
        kind=GATE_KIND,
        stages=("mobile",),
        body_sha="328e123c63857fd8",
        why="",
    ),
    "test.yml::mobile::The app bundles for native too, not just web": Covered(
        kind=GATE_KIND,
        stages=("mobile",),
        body_sha="1fd46fa6e1f4354f",
        why="",
    ),
    # --- postgres-repository.yml ------------------------------------------
    "postgres-repository.yml::repository-postgres::Install pinned API test dependencies": Covered(
        kind=SETUP_KIND,
        stages=(),
        body_sha="64429455861e6239",
        why="pip install of the pinned dev requirements; asserts nothing about the tree",
    ),
    "postgres-repository.yml::repository-postgres::Migrate an isolated schema and exercise the real repository": Covered(
        kind=GATE_KIND,
        stages=("postgres",),
        body_sha="65b54b7877a65de5",
        why="",
    ),
    # --- test.yml: e2e ----------------------------------------------------
    "test.yml::e2e::present": Covered(
        kind=GATE_KIND,
        stages=("e2e",),
        body_sha="8e9d2b349a474504",
        why="",
    ),
    "test.yml::e2e::Install the API and its client": Covered(
        kind=SETUP_KIND,
        stages=(),
        # Same reasoning as the mobile job's `npm ci`: the gate's e2e
        # prerequisite refuses to run without node_modules rather than
        # installing them, because a gate that installs is a gate that can hide
        # a broken lockfile.
        why="pip install and npm ci from the pinned files; asserts nothing about the tree",
        body_sha="6b7a8c6d1a215640",
    ),
    "test.yml::e2e::Fetch the database image the runner provisions from": Covered(
        kind=SETUP_KIND,
        stages=(),
        # scripts/e2e_slice.sh deliberately refuses to pull, so that its
        # runtime never depends on the network. On a laptop the image is
        # already present because docker-compose.yml uses the same tag; only a
        # fresh runner needs this, which is why it is here and not in the
        # script.
        why="docker pull of the database image; asserts nothing about the tree",
        body_sha="30562f5f5da92903",
    ),
    "test.yml::e2e::Propose, confirm, batch, publish, guest page, receipt": Covered(
        kind=GATE_KIND,
        stages=("e2e",),
        body_sha="1cc1857bf0badd70",
        why="",
    ),
}


def _gate_stages() -> list[str]:
    """The stages the gate reports, asked of the gate rather than parsed out.

    Same reasoning as the sibling job-level test: reading the STAGES array with
    a regex keeps matching after a rename that breaks the script.
    """
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
        # Digits belong in the class: `[a-z-]+` dropped the `e2e` stage, so a
        # GATE entry naming it read as naming a stage the gate does not have.
        if line.startswith("  ") and parts and re.fullmatch(r"[a-z0-9-]+", parts[0]):
            stages.append(parts[0])
    return stages


class GateCoversEveryInlineStep(unittest.TestCase):
    def test_the_parser_and_the_gate_both_still_answer(self):
        """Guard the guard.

        Every assertion below iterates the parsed steps. If the parser went
        stale it would return nothing and the whole file would pass by
        comparing empty against empty -- the failure shape this directory
        exists to refuse. `run_steps()` raises rather than returning empty;
        these bounds catch the subtler version where it still finds a few.
        """
        steps = run_steps()
        self.assertGreaterEqual(
            len(steps),
            25,
            f"parsed only {len(steps)} run-steps from .github/workflows -- the "
            "parser in tests/_workflow_steps.py has probably gone stale",
        )
        self.assertGreaterEqual(
            len({step.workflow for step in steps}),
            3,
            "found run-steps in fewer than three workflow files",
        )
        self.assertGreaterEqual(
            len(_gate_stages()), 5, "gate.sh reported almost no stages"
        )

    def test_every_inline_step_is_accounted_for(self):
        """A new step in a workflow is a new command that runs nowhere else."""
        missing = {
            step.key: step.body_sha
            for step in run_steps()
            if step.key not in INLINE_STEPS
        }
        self.assertEqual(
            missing,
            {},
            "these workflow steps are not listed in INLINE_STEPS, so nothing "
            "says where they run while Actions cannot start a job:\n"
            + "\n".join(f"  {key}" for key in sorted(missing))
            + "\n\nAdd each one: GATE with the scripts/gate.sh stage that runs "
            "it, or SETUP/INFO with the reason it needs no local runner. "
            "`python3 tests/_workflow_steps.py` prints a starting entry.",
        )

    def test_the_table_has_no_entries_for_steps_that_are_gone(self):
        """A stale entry keeps a deleted step looking covered, and hides that
        the stage behind it may now be guarding nothing."""
        live = {step.key for step in run_steps()}
        stale = sorted(set(INLINE_STEPS) - live)
        self.assertEqual(
            stale,
            [],
            f"INLINE_STEPS lists steps no workflow has any more: {stale}. Drop "
            "them, and check whether the gate stage behind each is still worth "
            "running.",
        )

    def test_step_bodies_match_the_text_they_were_reviewed_against(self):
        """The workflow moving first is how the local gate goes quietly stale.

        A changed step is not necessarily a problem -- it is a question: does
        the stage named here still do the same thing? Nobody can answer that by
        running the workflow right now, so it has to be asked of a person.
        """
        drifted = []
        for step in run_steps():
            entry = INLINE_STEPS.get(step.key)
            if entry is None:
                continue  # reported by test_every_inline_step_is_accounted_for
            if entry.body_sha != step.body_sha:
                drifted.append(
                    f"  {step.key}\n    reviewed {entry.body_sha}, now {step.body_sha}"
                )
        self.assertEqual(
            drifted,
            [],
            "these workflow steps changed since their entry was written:\n"
            + "\n".join(drifted)
            + "\n\nCheck that the stage named in INLINE_STEPS still runs the "
            "same thing, fix scripts/gate.sh if it does not, then update "
            "body_sha. Updating body_sha alone is how the two drift apart.",
        )

    def test_gate_kind_steps_name_stages_the_gate_actually_has(self):
        """A mapping to a stage that does not exist reads as coverage."""
        stages = set(_gate_stages())
        for key, entry in sorted(INLINE_STEPS.items()):
            if entry.kind != GATE_KIND:
                continue
            with self.subTest(step=key):
                self.assertTrue(
                    entry.stages,
                    f"{key} is filed as {GATE_KIND} but names no gate stage",
                )
                for stage in entry.stages:
                    self.assertIn(
                        stage,
                        stages,
                        f"{key} maps to gate stage {stage!r}, which "
                        f"scripts/gate.sh does not have. Stages: {sorted(stages)}",
                    )

    def test_nothing_that_asserts_is_filed_as_setup_or_info(self):
        """The escape hatch, closed.

        SETUP and INFO are the two labels that say "no local runner needed", so
        they are where a real gate would go to hide -- not usually on purpose,
        but because a step grows an `exit 1` a year after somebody classified
        it. A step written so it can say no is a gate, whatever it is called.
        """
        mislabelled = []
        for step in run_steps():
            entry = INLINE_STEPS.get(step.key)
            if entry is None or entry.kind == GATE_KIND:
                continue
            if step.can_fail_on_purpose:
                mislabelled.append(f"  {step.key} -- filed {entry.kind}")
        self.assertEqual(
            mislabelled,
            [],
            "these steps contain a deliberate failure (`::error::` or `exit 1`) "
            "but are filed as needing no local runner:\n"
            + "\n".join(mislabelled)
            + "\n\nA step that can say no is a gate. File it GATE and name the "
            "scripts/gate.sh stage that runs it.",
        )

    def test_setup_and_info_entries_carry_a_real_reason(self):
        """An allowlist that holds an unexplained entry is a hole with a lid."""
        for key, entry in sorted(INLINE_STEPS.items()):
            if entry.kind == GATE_KIND:
                continue
            with self.subTest(step=key):
                self.assertGreaterEqual(
                    len(entry.why.split()),
                    5,
                    f"{key} is filed {entry.kind} and needs a real reason, got {entry.why!r}",
                )
                self.assertEqual(
                    entry.stages,
                    (),
                    f"{key} is filed {entry.kind} but names gate stages {entry.stages}",
                )

    def test_every_entry_uses_a_kind_this_file_defines(self):
        """A typo in `kind` would slip past every check above: it is not GATE,
        so the stage checks skip it, and it is not SETUP or INFO either."""
        known = {GATE_KIND, SETUP_KIND, INFO_KIND}
        wrong = {key: e.kind for key, e in INLINE_STEPS.items() if e.kind not in known}
        self.assertEqual(wrong, {}, f"unknown kinds in INLINE_STEPS: {wrong}")


if __name__ == "__main__":
    unittest.main()
