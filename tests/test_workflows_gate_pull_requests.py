"""A gate must run where the merge decision is made: on the pull request.

## Why

`1e7e65b` ("ci: cắt mạnh Actions") removed the `pull_request` trigger from
`test.yml` and `postgres-repository.yml` to cut Actions minutes. It left
`repo-guard.yml` triggering on pull requests and the other two triggering only
on `push: branches: [main]`.

The effect is not "fewer runs". It is that a pull request's check mark stopped
meaning what a reader takes it to mean. Measured against the API on
2026-08-30, over the 300 most recent runs:

    90 pull_request  Repo Guard
    70 push          test
    70 push          Repo Guard
    70 push          PostgreSQL Repository

Every pull-request run in the repository's history is the repo guard. The test
suite, ruff, the mobile bundle, the docker image, the route contract and the
293 PostgreSQL cases have never once gated a pull request -- they run after the
merge, on `main`, where a defect they catch is already in the branch everyone
else builds on. `test.yml` says the opposite about itself in its own header
("Runs on every push and every pull request"), so the file most likely to be
read as the authority on what CI covers is the file that misdescribes it.

This is the shape CLAUDE.md names as the repository's most common failure: a
green that is green because nothing ran. The commit that created it says its
reason was cost, and cost is a real reason -- but it did not prevent the
outage, and the thing traded away was the gate on the one event where a human
is about to make an irreversible decision.

## What this proves and what it does not

It proves each workflow declares `pull_request` among its triggers. It does
not prove GitHub honours it, that the jobs pass, or that the runner has what
they need -- Actions has not started a job since 2026-08-29T07:45:42Z (339
consecutive billing failures as of this commit), so nothing can prove that
here. The claim is deliberately the narrow one: the trigger is declared, so
the day the account is payable again the gate is where it belongs rather than
one more thing somebody has to remember.

`POST_MERGE_ONLY` is where an exemption gets argued in writing.

## Why this parses the trigger block by hand

`test_workflow_gates_have_local_callers.py` set the rule that these tests do
not grow a YAML dependency, and there is a sharper reason here. YAML 1.1 reads
the unquoted key `on` as the boolean true, so `yaml.safe_load` returns a dict
keyed by `True` and a natural `"on" in data` check is False for every workflow
ever written. A gate whose parser silently reports "no triggers" for all input
is worse than no gate. `test_reader_handles_the_shapes_yaml_allows` pins the
reader against that trap and against the forms these files may legitimately
take.
"""

from __future__ import annotations

import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# Workflows that legitimately run only after a merge, each with the reason it
# cannot gate the pull request -- a deploy that needs a production secret, a
# nightly, a job that publishes. Empty on purpose: every workflow in this
# repository today is a gate, and a gate that runs after the merge is not
# gating. An entry here is a claim a reviewer should have to read and agree
# with, not a place to park a workflow that is merely slow.
POST_MERGE_ONLY: dict[str, str] = {}

# A top-level `on:` key, quoted or not. Anchored at column zero because that is
# what makes it top-level; a nested `on:` inside a job is a different thing.
ON_KEY = re.compile(r'^(?:on|"on"|\'on\'):(.*)$')


def _strip_comment(line: str) -> str:
    """Drop a trailing `#` comment.

    Good enough for these files and deliberately conservative: a `#` inside a
    quoted string would be mangled, so the reader is only ever pointed at
    trigger blocks, which contain no quoted strings.
    """
    return line.split("#", 1)[0] if "#" in line else line


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def triggers(text: str) -> set[str]:
    """The event names in a workflow's top-level `on:` block.

    Handles the three forms GitHub accepts:
      on: push                  -> {"push"}
      on: [push, pull_request]  -> {"push", "pull_request"}
      on:                       -> {"push", "pull_request"}
        push:
          branches: [main]
        pull_request:
    """
    lines = text.splitlines()
    for i, raw in enumerate(lines):
        match = ON_KEY.match(raw)
        if not match:
            continue

        inline = _strip_comment(match.group(1)).strip()
        if inline:
            # `on: push` or `on: [push, pull_request]`
            inline = inline.strip("[]")
            return {
                part.strip().strip("\"'") for part in inline.split(",") if part.strip()
            }

        # Block form: the immediate children are the lines at the shallowest
        # indentation before the next top-level key.
        found: set[str] = set()
        depth: int | None = None
        for follow in lines[i + 1 :]:
            body = _strip_comment(follow)
            if not body.strip():
                continue
            if _indent(body) == 0:
                break
            if depth is None:
                depth = _indent(body)
            if _indent(body) != depth:
                continue
            key = body.strip()
            # `pull_request:` / `- pull_request` / `pull_request: {}`
            key = key[1:].strip() if key.startswith("- ") else key
            key = key.split(":", 1)[0].strip().strip("\"'")
            if key:
                found.add(key)
        return found
    return set()


def _workflow_files() -> list[pathlib.Path]:
    return sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))


class ReaderTests(unittest.TestCase):
    def test_reader_handles_the_shapes_yaml_allows(self) -> None:
        cases = [
            ("on: pull_request\n", {"pull_request"}),
            ("on: [push, pull_request]\n", {"push", "pull_request"}),
            ('"on": [push]\n', {"push"}),
            (
                "name: x\non:\n  push:\n    branches: [main]\n  pull_request:\n"
                "  workflow_dispatch:\n\njobs:\n  a:\n    runs-on: x\n",
                {"push", "pull_request", "workflow_dispatch"},
            ),
            # A nested `branches:` is not a trigger, and a job-level key after
            # the block ends must not leak in.
            (
                "on:\n  push:\n    branches: [main]\n\njobs:\n  pull_request:\n"
                "    runs-on: x\n",
                {"push"},
            ),
            # The trap this file exists to survive: no trigger block at all.
            ("name: x\njobs: {}\n", set()),
        ]
        for text, expected in cases:
            with self.subTest(text=text[:40]):
                self.assertEqual(triggers(text), expected)

    def test_reader_is_not_fooled_by_yaml_reading_on_as_a_boolean(self) -> None:
        """The failure mode that makes a naive parser green for everything."""
        text = "on:\n  pull_request:\n"
        self.assertIn("pull_request", triggers(text))
        self.assertNotIn("True", triggers(text))
        self.assertNotIn("true", triggers(text))


class WorkflowTriggerTests(unittest.TestCase):
    def test_there_are_workflows_to_check(self) -> None:
        """An empty glob would make every assertion below vacuously true."""
        self.assertTrue(
            _workflow_files(), f"không tìm thấy workflow nào trong {WORKFLOWS}"
        )

    def test_every_workflow_gates_the_pull_request(self) -> None:
        missing = []
        for workflow in _workflow_files():
            if workflow.name in POST_MERGE_ONLY:
                continue
            found = triggers(workflow.read_text(encoding="utf-8"))
            if "pull_request" not in found:
                missing.append(f"  {workflow.name}: on = {sorted(found) or 'không có'}")

        self.assertFalse(
            missing,
            "Workflow chạy sau khi merge thì không gác merge — nó báo thiệt hại đã "
            "nằm trên main:\n"
            + "\n".join(missing)
            + "\n\nThêm `pull_request:` vào khối `on:`, hoặc khai vào POST_MERGE_ONLY "
            "kèm lý do vì sao nó không thể gác pull request.",
        )

    def test_exemptions_carry_a_reason(self) -> None:
        for name, reason in POST_MERGE_ONLY.items():
            with self.subTest(workflow=name):
                self.assertTrue(reason.strip(), f"{name} được miễn mà không nêu lý do")
                self.assertTrue(
                    (WORKFLOWS / name).is_file(),
                    f"{name} được miễn nhưng workflow đó không còn tồn tại",
                )


if __name__ == "__main__":
    unittest.main()
