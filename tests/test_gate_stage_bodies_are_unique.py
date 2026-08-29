"""No two gate stages may share a name, and no checker may go unreachable.

## Why

`scripts/gate.sh` dispatches a stage by calling `"do_$stage"`. That indirection
is what makes the gate extensible, and it is also what lets a stage die without
saying so.

On 2026-08-29 two branches added a stage named `contract` independently. #163
(actor headers) reached `main` first; #165 (client route existence) had been cut
before it, so on neither branch was there a collision to see. Merging them
produced this, and it is worth reading slowly because every step is silent:

  - `git merge` reported conflicts in `STAGES=` and `check_prereq` only. A
    reviewer resolves those two, sees a clean tree, and is done.
  - The two `do_contract()` bodies do not overlap textually, so git merged them
    *both* into the file with no marker between them.
  - `bash -n scripts/gate.sh` parses it. Two definitions of one function is
    legal shell.
  - Bash keeps the LAST definition. `stage_help`'s `case` keeps the FIRST.
  - So `./scripts/gate.sh contract` printed "every route wanting X-Actor-ID is
    called with it", ran the route-existence check instead, and exited 0.
  - The actor-header checker's two canaries never ran. 61 client calls went
    uncounted. `tests/test_gate_covers_every_workflow_job.py` stayed green,
    because `--list` still reported one stage named `contract` and every job
    still mapped to a stage that existed.

Reproduced end to end in `tests/qa/rd-qa-28/va-cham-ten-chang-contract.sh`.

## What this proves and what it does not

It proves the stage table and the stage bodies are a bijection, and that no
checker the script *invokes* has been orphaned behind a shadowed definition. It
does not prove a stage runs the right commands -- nothing here can, and
`test_gate_covers_every_workflow_job.py` says the same about its own claim. The
failure guarded against is a gate that stops running while still reporting.

The bodies are parsed out of the file rather than asked of bash, because bash
is exactly the component that resolves the collision silently: `declare -F`
after sourcing would report one `do_contract` and agree with the bug.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "scripts" / "gate.sh"

DEF = re.compile(r"^do_([A-Za-z0-9_-]+)\(\)")
# A checker invoked by the gate. Deliberately not every `scripts/` path: the
# question is whether a *gate check* became unreachable.
CHECKER = re.compile(r"scripts/(check_[A-Za-z0-9_]+\.(?:py|sh))")

# gate stage -> the checker its body must invoke.
#
# The uniqueness assertions below catch a checker that has been *shadowed* by a
# second definition. They do not catch one that has been *replaced*, because a
# checker deleted from the file is no longer a name anything can look for. That
# gap was found by mutation and this table is what closes it: point `contract`
# at the route checker and the mutation is red here, on the stage that changed.
#
# Not every checker in `scripts/` belongs here -- `check_server_routes.py` asks
# a running server and is driven from the Makefile, so the gate does not call
# it. The rule is the narrower one, held in both directions below: a checker
# `gate.sh` invokes is a checker this table has to name.
STAGE_CHECKERS: dict[str, str] = {
    "contract": "check_actor_headers.py",
    "client-routes": "check_api_contract.py",
    "docker": "check_dockerfile_pinning.sh",
}


def _stage_bodies() -> list[tuple[str, str]]:
    """Every `do_<stage>()` definition in file order, as (stage, body).

    Duplicates are kept -- finding them is the point. `do_api() { ...; }` on one
    line closes on that line; the multi-line form closes on a `}` in column 1,
    which is the shape every body in the file uses.
    """
    lines = GATE.read_text(encoding="utf-8").splitlines()
    bodies: list[tuple[str, str]] = []
    index = 0
    while index < len(lines):
        match = DEF.match(lines[index])
        if not match:
            index += 1
            continue
        stage = match.group(1)
        if lines[index].rstrip().endswith("}"):
            bodies.append((stage, lines[index]))
            index += 1
            continue
        end = index + 1
        while end < len(lines) and lines[end] != "}":
            end += 1
        if end >= len(lines):
            raise AssertionError(
                f"do_{stage}() at line {index + 1} of scripts/gate.sh never "
                "closes with a '}' in column 1. Either the file changed shape "
                "or it is truncated; this parser cannot tell, so it refuses to "
                "report the rest of the file as clean."
            )
        bodies.append((stage, "\n".join(lines[index : end + 1])))
        index = end + 1
    return bodies


def _effective_bodies() -> dict[str, str]:
    """What bash would actually run: for a duplicated name, the last one."""
    return dict(_stage_bodies())


def _declared_stages() -> list[str]:
    """The stages the gate reports, asked of the gate rather than parsed."""
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
        if line.startswith("  ") and parts and re.fullmatch(r"[a-z-]+", parts[0]):
            stages.append(parts[0])
    return stages


def _code_lines() -> list[str]:
    """Non-comment lines. A checker named only in prose is not an invocation."""
    return [
        line
        for line in GATE.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    ]


class GateStageBodiesAreUnique(unittest.TestCase):
    def test_the_parsers_find_something(self):
        """Guard the guard.

        Every assertion below iterates one of these. If the body parser or the
        `--list` parser went stale they would return nothing, and comparing
        empty against empty passes -- the failure shape this whole directory
        exists to refuse.
        """
        self.assertTrue(GATE.is_file(), f"{GATE} is missing")
        self.assertGreaterEqual(
            len(_stage_bodies()),
            5,
            "found almost no do_<stage>() definitions in scripts/gate.sh -- "
            "either the gate lost them or the parser in this file went stale",
        )
        self.assertGreaterEqual(
            len(_declared_stages()),
            5,
            "scripts/gate.sh --list reported almost no stages",
        )

    def test_no_stage_name_is_defined_twice(self):
        """The collision itself.

        Two bodies under one name is legal bash and invisible to `bash -n`, to
        `--list`, and to a reviewer resolving the conflicts git chose to show.
        """
        seen: dict[str, int] = {}
        for stage, _ in _stage_bodies():
            seen[stage] = seen.get(stage, 0) + 1
        duplicates = sorted(name for name, count in seen.items() if count > 1)
        self.assertEqual(
            duplicates,
            [],
            f"scripts/gate.sh defines these stage bodies more than once: "
            f"{duplicates}. Bash keeps the last definition and `stage_help`'s "
            "case keeps the first, so the gate would describe one check and run "
            "another while exiting 0. Give the new check its own stage name, "
            "add it to STAGES, stage_help and check_prereq, and map it in "
            "tests/test_gate_covers_every_workflow_job.py.",
        )

    def test_every_declared_stage_has_a_body(self):
        """A name in STAGES with no `do_` behind it dispatches to nothing."""
        bodies = set(_effective_bodies())
        missing = sorted(set(_declared_stages()) - bodies)
        self.assertEqual(
            missing,
            [],
            f"scripts/gate.sh lists these stages but defines no body for them: "
            f"{missing}. `\"do_$stage\"` would be a command-not-found.",
        )

    def test_every_body_belongs_to_a_declared_stage(self):
        """The other direction: a body no stage name reaches never runs.

        This is the half of the collision a rename alone can leave behind --
        drop the duplicate name from STAGES, keep its body, and the check is
        gone with nothing to show for it.
        """
        declared = set(_declared_stages())
        orphans = sorted(stage for stage in _effective_bodies() if stage not in declared)
        self.assertEqual(
            orphans,
            [],
            f"scripts/gate.sh defines these stage bodies that no stage name "
            f"reaches: {orphans}. Add them to STAGES or delete them -- an "
            "unreachable body reads as coverage and runs never.",
        )

    def test_every_checker_the_gate_invokes_is_reachable(self):
        """A checker invoked from a shadowed body is a dead gate.

        This is the consequence the collision actually had: after the merge
        `scripts/check_actor_headers.py` was still there, still spelled out in
        the file, and no longer run by anything.
        """
        invoked = {
            name for line in _code_lines() for name in CHECKER.findall(line)
        }
        reachable = {
            name
            for body in _effective_bodies().values()
            for name in CHECKER.findall(body)
        }
        stranded = sorted(invoked - reachable)
        self.assertEqual(
            stranded,
            [],
            f"scripts/gate.sh invokes these checkers from somewhere no stage "
            f"reaches: {stranded}. The usual cause is a second definition of a "
            "stage further down the file shadowing the one that called them.",
        )

    def test_each_stage_still_invokes_the_checker_it_is_named_for(self):
        """A stage that swapped bodies with another one keeps its name.

        That is the whole shape of the bug: `gate.sh contract` went on printing
        the actor-header description and exiting 0 while running a different
        check entirely. Nothing about the name, the description or the exit code
        changes when this happens, so the mapping is asserted directly.
        """
        bodies = _effective_bodies()
        for stage, checker in sorted(STAGE_CHECKERS.items()):
            with self.subTest(stage=stage):
                self.assertIn(
                    stage,
                    bodies,
                    f"scripts/gate.sh has no do_{stage}() any more, but this "
                    f"file still expects it to run {checker}. If the stage was "
                    "renamed, rename it here too; if it was dropped, say so by "
                    "dropping it here.",
                )
                self.assertIn(
                    checker,
                    CHECKER.findall(bodies[stage]),
                    f"the `{stage}` stage no longer invokes {checker}. A stage "
                    "that keeps its name and its description while running a "
                    "different check reports on a question it never asked.",
                )

    def test_no_checker_is_invoked_without_being_recorded(self):
        """Keeps the table above from going stale by omission.

        Without this, a new checker-backed stage could be added and simply not
        listed, and the mapping test would pass by not looking at it.
        """
        invoked = {name for line in _code_lines() for name in CHECKER.findall(line)}
        unrecorded = sorted(invoked - set(STAGE_CHECKERS.values()))
        self.assertEqual(
            unrecorded,
            [],
            f"scripts/gate.sh invokes these checkers that STAGE_CHECKERS in "
            f"this file does not name: {unrecorded}. Add the stage that runs "
            "each one, so a later edit that points a stage somewhere else is "
            "caught here rather than by whoever notices the gate went quiet.",
        )


if __name__ == "__main__":
    unittest.main()
