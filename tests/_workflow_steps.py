"""Read the `run:` steps out of .github/workflows without a YAML parser.

Shared by tests/test_gate_covers_every_inline_step.py. It lives beside that
test rather than inside it so the parser can be exercised on its own, and so
the test file reads as the rule it enforces instead of as string handling.

## Why not PyYAML

The standard command is `python3 -m pytest services/api/tests tests -q`, and
services/api/requirements-dev.txt does not pin PyYAML -- checked 2026-08-30,
no `yaml` line in it and none in pyproject's dev extra. Importing it here
would make the whole suite depend on a package that happens to be present on
one machine. `pytest.importorskip` would be worse: it turns the gate into a
skip, and a gate that skips is the failure this directory exists to refuse.

The two sibling meta-gates made the same call for the same reason --
test_workflow_gates_have_local_callers.py says it outright: "the standard gate
command must not grow a dependency to run one test".

## What this parses, and how it fails

The workflows in this repository are written in one consistent shape: jobs at
two spaces, `steps:` at four, each step a `- ` item at six, keys at eight.
This reads exactly that shape and nothing more general.

A hand parser that goes stale is the danger -- it would return an empty list
and every assertion built on it would pass. So this raises rather than
returning empty when it finds no jobs or no steps, and the test file asserts
the counts on top of that.
"""

from __future__ import annotations

import dataclasses
import hashlib
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

_JOB_ID = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
_STEP_START = re.compile(r"^      - (.*)$")
_STEP_KEY = re.compile(r"^        ([A-Za-z0-9_-]+):\s?(.*)$")
_BLOCK_SCALAR = re.compile(r"^[|>][+-]?$")


@dataclasses.dataclass(frozen=True)
class Step:
    """One `run:` step of one job."""

    workflow: str
    job: str
    label: str
    """`name:` if the step has one, else `id:`, else the first line it runs.

    Steps in these workflows are not all named -- `npm ci` in the mobile job is
    a bare `run:` under an `if:`. Falling back keeps every step addressable
    without editing the workflows to suit the test.
    """
    body: str
    """The shell the step runs, dedented, trailing whitespace stripped."""

    @property
    def key(self) -> str:
        return f"{self.workflow}::{self.job}::{self.label}"

    @property
    def body_sha(self) -> str:
        return hashlib.sha256(self.body.encode("utf-8")).hexdigest()[:16]

    @property
    def can_fail_on_purpose(self) -> bool:
        """Does this step contain a deliberate failure?

        `::error::` is GitHub's way of failing a step with a message, and a
        non-zero `exit` is the other. Either one means the step is asserting
        something -- which makes it a gate, whatever it is labelled.

        Deliberately not a judgement about whether the step *can* fail: `pip
        install` fails when the network is down, and `docker build` fails on a
        bad Dockerfile. Those are errors, not assertions. What separates a gate
        is that it was written to be able to say no.

        The pattern is not anchored to the start of a line, and that is the
        whole of it. It was, until a canary on 2026-08-30 wrote the same
        violation a second way: a step filed SETUP grew
        `test -f services/api/pyproject.toml || exit 1`, and the anchored
        version read it as harmless because the `exit` sat after a `||` --
        blind to the shape a shell script most often uses to say no. `exit 0`
        stays excluded on purpose: that is a step declining to do work, not
        refusing to pass.
        """
        return (
            "::error::" in self.body
            or re.search(r"\bexit\s+[1-9][0-9]*\b", self.body) is not None
        )


def _dedent(lines: list[str]) -> str:
    """Strip the common indent, drop blank edges, drop trailing whitespace.

    Indentation is an artefact of where the block sits in the YAML, so a step
    moved into an `if:` would otherwise read as a changed command.
    """
    stripped = [line.rstrip() for line in lines]
    while stripped and not stripped[0]:
        stripped.pop(0)
    while stripped and not stripped[-1]:
        stripped.pop()
    if not stripped:
        return ""
    indents = [len(line) - len(line.lstrip()) for line in stripped if line]
    common = min(indents) if indents else 0
    return "\n".join(line[common:] if line else "" for line in stripped)


def _steps_of_workflow(path: pathlib.Path) -> list[Step]:
    text = path.read_text(encoding="utf-8")
    if "\njobs:" not in text:
        return []
    lines = text.splitlines()

    steps: list[Step] = []
    job = ""
    in_jobs = False
    # The step currently being accumulated.
    cur: dict[str, str] | None = None
    run_lines: list[str] = []
    in_run_block = False

    def flush() -> None:
        nonlocal cur, run_lines, in_run_block
        if cur is not None and ("run" in cur or run_lines):
            body = _dedent(run_lines) if run_lines else cur.get("run", "")
            first_line = body.splitlines()[0] if body else ""
            label = (cur.get("name") or cur.get("id") or first_line).strip()
            steps.append(Step(workflow=path.name, job=job, label=label, body=body))
        cur = None
        run_lines = []
        in_run_block = False

    for line in lines:
        if line.startswith("jobs:"):
            in_jobs = True
            continue
        if not in_jobs:
            continue

        job_match = _JOB_ID.match(line)
        if job_match:
            flush()
            job = job_match.group(1)
            continue

        step_match = _STEP_START.match(line)
        if step_match:
            flush()
            cur = {}
            first = step_match.group(1)
            # `- name: x` and `- uses: x` put the first key on the dash line.
            key_on_dash = re.match(r"^([A-Za-z0-9_-]+):\s?(.*)$", first)
            if key_on_dash:
                cur[key_on_dash.group(1)] = key_on_dash.group(2).strip()
            continue

        if cur is None:
            continue

        if in_run_block:
            # The block ends at the first line indented no further than the
            # `run:` key itself, ignoring blank lines.
            if line.strip() and (len(line) - len(line.lstrip())) <= 8:
                in_run_block = False
            else:
                run_lines.append(line)
                continue

        key_match = _STEP_KEY.match(line)
        if key_match:
            name, value = key_match.group(1), key_match.group(2).strip()
            if name == "run":
                if _BLOCK_SCALAR.match(value):
                    in_run_block = True
                    run_lines = []
                else:
                    cur["run"] = value
            else:
                cur.setdefault(name, value)

    flush()
    return steps


def run_steps() -> list[Step]:
    """Every step in every workflow that runs shell, in file order.

    Raises rather than returning empty: a parser that has gone stale must not
    look like a repository with no steps in it.
    """
    if not WORKFLOWS.is_dir():
        raise AssertionError(f"{WORKFLOWS} is missing")
    found: list[Step] = []
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    if not files:
        raise AssertionError(f"no workflow files under {WORKFLOWS}")
    for path in files:
        found.extend(_steps_of_workflow(path))
    if not found:
        raise AssertionError(
            f"parsed {len(files)} workflow files and found no `run:` steps -- "
            "the parser in tests/_workflow_steps.py has gone stale"
        )
    return found


if __name__ == "__main__":  # pragma: no cover - a hand tool, not a gate
    # Prints one table entry per step. Pasting the output wholesale is not
    # review: the point of the table is that a person decided what each step
    # is. Copy the single entry you are adding.
    for step in run_steps():
        print(f'    "{step.key}": Covered(')
        print(f'        kind="GATE", stages=("?",), body_sha="{step.body_sha}",')
        print(f'        why="?",  # can_fail_on_purpose={step.can_fail_on_purpose}')
        print("    ),")
