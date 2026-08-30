"""Run a workflow's `run:` steps and record what they actually executed.

## Why this exists

`tests/_workflow_steps.py` hands back the text of each step. Every gate built
on it so far has then asked whether that text *contains* something, and twice
now that has been the wrong question.

`#267` asked `assertIn("scripts/postgres_tier.sh", <whole workflow file>)`.
`#271` found the hole -- a shell comment reading `# was:
scripts/postgres_tier.sh -q` satisfies a substring while the step runs the
narrow tier again -- and narrowed the search from the file to the `run:` body.
The diagnosis was right and the repair was not, because a comment inside a
`run:` block is still part of the body. `bug-095404` measured what survived:
five ways of writing the same violation, all five green.

The four that hid an inline `pytest tests/postgres` did it with shell, not with
prose -- a line continuation, one more `cd`, a `./` prefix, a variable. No
pattern over source text decides those, because the shell decides them at run
time. So this module stops reading and starts running.

## How

Each step's body is executed by bash in a throwaway tree where nothing can do
its job:

  - Every file under `scripts/` is replaced by a recorder that appends its own
    repo-relative path to a log and exits 0. Identity comes from **the file
    that ran**, so `scripts/postgres_tier.sh`, `./scripts/postgres_tier.sh`,
    `bash scripts/postgres_tier.sh` and `$RUNNER` all record the same thing,
    and a comment mentioning it records nothing at all.
  - `PATH` holds only `bash` and `sh`, so every other command misses and
    `command_not_found_handle` records the argv the shell built -- after
    continuations are joined, variables expanded and `cd` applied.
  - The directory tree is mirrored (directories only) so a `cd` anywhere in the
    repo succeeds. Under `bash -e` a failed `cd` would abort the step and hide
    everything after it.

What comes back is a list of invocations, each with the cwd it ran in. That is
evidence about behaviour: a mention cannot appear in it.

## What this does NOT prove

It does not run the real commands, so it says nothing about whether
`scripts/postgres_tier.sh` does its job -- `RunnerCannotGoQuiet` and
`LiveCasesOutsideTestsPostgresAlsoRun` in tests/test_postgres_tier_runner.py
carry that, by running the runner for real.

It does not evaluate `if:`. A conditional step is executed here and would be
recorded as having run even when GitHub would skip it, so callers must refuse
to conclude anything about a step carrying a condition rather than trust this.
`test_no_step_of_this_workflow_is_conditional` in
tests/test_postgres_tier_runner.py is that refusal.

It does not follow a command into a subprocess it launches by absolute path,
and it cannot see inside a `python -c` string. Both are recorded as the
invocation they are, which is enough for the caller's question ("did this file
run?") and not enough to enumerate everything a step might do.

## A note on running shell out of a workflow

The bodies executed here are this repository's own workflow files, and every
command in them is defused by construction: `PATH` is emptied, `HOME` points
into the sandbox and the working directory is a temporary tree. A step that
reaches outside all of that -- an absolute path to a real binary -- would run
for real, so it would also be visible in the diff that introduced it.
"""

from __future__ import annotations

import dataclasses
import os
import pathlib
import shlex
import shutil
import subprocess
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Mirrored as directories so `cd` succeeds anywhere; their contents are never
# copied. node_modules alone is tens of thousands of directories and nothing in
# a workflow cds into one.
_SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".expo",
        "dist",
        "build",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
    }
)

_LOG_VAR = "MOBILE_STEP_EXEC_LOG"

# Kinds of recorded invocation.
FILE = "file"
"""A file in the tree was executed. `name` is its repo-relative path."""
LOOKUP = "path-lookup"
"""A bare command name was never found. `name` is the name as the shell had it."""


@dataclasses.dataclass(frozen=True)
class Invocation:
    """One command a step actually ran."""

    kind: str
    name: str
    cwd: str
    """Repo-relative directory the command ran in; `.` at the root."""
    args: tuple[str, ...]

    @property
    def argv(self) -> tuple[str, ...]:
        return (self.name,) + self.args

    def resolved(self, arg: str) -> str:
        """`arg` read as a path from where this command ran, repo-relative.

        This is what makes `cd services/api/tests && pytest postgres` and
        `cd services/api && pytest ./tests/postgres` the same fact. Returns the
        argument unchanged when it is not path-shaped (a flag, a `-k`
        expression), so callers can compare the whole argv without filtering.
        """
        if not arg or arg.startswith("-"):
            return arg
        return os.path.normpath(os.path.join(self.cwd, arg))

    def __str__(self) -> str:
        return f"[{self.cwd}] {shlex.join(self.argv)}"


class StepExecutionError(RuntimeError):
    """The sandbox could not be built or bash could not be run.

    Raised rather than returning an empty list: no invocations reads exactly
    like a step that ran nothing, which is one of the violations being looked
    for.
    """


_RECORDER = """#!/bin/bash
# Not the real script: records that this path was executed, then exits 0.
{{ printf '{kind}\\t%s\\t%s' {name} "$PWD"; for a in "$@"; do printf '\\t%s' "$a"; done; printf '\\n'; }} >> "${log}"
exit 0
"""

_PRELUDE = """\
command_not_found_handle() {{
  __n="$1"; shift
  {{ printf '{kind}\\t%s\\t%s' "$__n" "$PWD"; for a in "$@"; do printf '\\t%s' "$a"; done; printf '\\n'; }} >> "${log}"
  return 0
}}
export -f command_not_found_handle
"""


class WorkflowStepSandbox:
    """A throwaway copy of the repository in which nothing can do its job."""

    def __init__(self) -> None:
        if not shutil.which("bash", path="/bin:/usr/bin"):
            raise StepExecutionError("no /bin/bash -- cannot execute workflow steps")
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="workflow-step-exec-"))
        self.log = self.root / ".exec-log"
        self.log.write_text("", encoding="utf-8")
        self._mirror_directories()
        self._plant_recorders()
        self._make_path_dir()
        self._prelude = self.root / ".prelude.bash"
        self._prelude.write_text(
            _PRELUDE.format(kind=LOOKUP, log=_LOG_VAR), encoding="utf-8"
        )

    # -- construction ----------------------------------------------------

    def _mirror_directories(self) -> None:
        for current, dirs, _files in os.walk(REPO_ROOT):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            rel = pathlib.Path(current).relative_to(REPO_ROOT)
            (self.root / rel).mkdir(parents=True, exist_ok=True)

    def _plant_recorders(self) -> None:
        """One recorder per file under scripts/, at the same relative path.

        Every path-invoked program in these workflows lives there. A file the
        workflow invokes from somewhere else is simply not found, which is
        recorded as an absent path rather than silently counted as a run.
        """
        planted = 0
        for path in sorted((REPO_ROOT / "scripts").rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(REPO_ROOT)
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                _RECORDER.format(kind=FILE, name=shlex.quote(str(rel)), log=_LOG_VAR),
                encoding="utf-8",
            )
            target.chmod(0o755)
            planted += 1
        if planted == 0:
            raise StepExecutionError(
                f"no files under {REPO_ROOT / 'scripts'} -- every step would "
                "record nothing and read as a step that runs nothing"
            )

    def _make_path_dir(self) -> None:
        """`PATH` with only the two shells a step may need to reach a script.

        `bash scripts/x.sh` and `sh scripts/x.sh` have to reach the recorder,
        or rewriting the invocation style would read as removing the call. Every
        other name misses and lands in `command_not_found_handle`.
        """
        self.bin = self.root / ".bin"
        self.bin.mkdir(exist_ok=True)
        for shell in ("bash", "sh"):
            found = shutil.which(shell, path="/bin:/usr/bin")
            if found:
                (self.bin / shell).symlink_to(found)

    # -- running ---------------------------------------------------------

    def run(self, body: str, working_directory: str = "") -> list[Invocation]:
        """Execute one step body; return what it invoked, in order."""
        cwd = self.root / working_directory if working_directory else self.root
        if not cwd.is_dir():
            raise StepExecutionError(
                f"working-directory {working_directory!r} does not exist in the tree"
            )
        script = self.root / ".step.bash"
        script.write_text(
            f"source {shlex.quote(str(self._prelude))}\n{body}\n", encoding="utf-8"
        )
        before = self.log.stat().st_size
        env = {
            "PATH": str(self.bin),
            "HOME": str(self.root),
            _LOG_VAR: str(self.log),
            "BASH_ENV": str(self._prelude),
        }
        try:
            subprocess.run(
                ["bash", "--noprofile", "--norc", "-eo", "pipefail", str(script)],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
                executable=shutil.which("bash", path="/bin:/usr/bin"),
            )
        except subprocess.TimeoutExpired as exc:  # pragma: no cover - a hang
            raise StepExecutionError(f"step did not finish in 120s: {body!r}") from exc
        # The exit status is deliberately ignored: every command is a stub, so
        # a step that would pass in CI can still end non-zero here. What was
        # invoked before it stopped is the evidence, and a step that stopped
        # early simply has fewer invocations -- which is a failure, not a pass.
        with self.log.open("r", encoding="utf-8") as handle:
            handle.seek(before)
            return [self._parse(line) for line in handle if line.strip()]

    def _parse(self, line: str) -> Invocation:
        kind, name, cwd, *args = line.rstrip("\n").split("\t")
        rel = os.path.relpath(cwd, self.root)
        return Invocation(kind=kind, name=name, cwd=rel, args=tuple(args))

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> "WorkflowStepSandbox":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
