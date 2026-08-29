"""The base-image pinning gate must bite, and it must bite on this tree.

`scripts/check_dockerfile_pinning.sh` has existed since the `docker` job was
written, and until this file it was referenced exactly once in the whole
repository: by `.github/workflows/test.yml`. That was survivable while Actions
ran. It stopped being survivable at 07:45Z on 2026-08-29, when Actions began
refusing to start jobs over billing -- from then the gate did not merely go
unenforced, it did not execute at all, and nothing said so, because every pull
request was already showing a red X for the billing reason.

So the gate moves here, into `python3 -m pytest services/api/tests tests -q`,
which needs no Actions, no database and no Docker daemon: the script is text
analysis of a Dockerfile, and text is all it reads.

Both halves are load bearing, the same way they are in `test_alembic_heads.py`:

  * `test_the_real_dockerfile_is_digest_pinned` is *the gate*. It goes red on
    the day somebody writes `FROM python:3.12-slim` with no digest, and that is
    the only reason any of this exists.
  * the synthetic cases prove the gate **knows how to be red**. A gate observed
    only in the green has not been distinguished from a gate that cannot fail,
    and this repository counted five of those in a single afternoon.

Every case runs the real script through `subprocess` and reads its real exit
code. Exit codes are what a hook and a workflow act on, so exit codes are what
gets tested -- not a reimplementation of the parsing compared against itself.

What this does not cover: the rest of the `docker` job -- that the image builds,
runs as non-root, ships no pytest, and answers its own HEALTHCHECK. Those need a
Docker daemon and cannot join the standard command. They remain Actions-only and
are, today, not running anywhere.
"""

from __future__ import annotations

import pathlib
import subprocess
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "scripts" / "check_dockerfile_pinning.sh"
REAL_DOCKERFILE = REPO_ROOT / "services" / "api" / "Dockerfile"

DIGEST = "sha256:" + "0" * 64


def _run(*paths: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(GATE), *paths],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


class TheGateOnThisTree(unittest.TestCase):
    def test_the_gate_script_is_present_and_executable_shell(self):
        self.assertTrue(GATE.is_file(), f"{GATE} is missing")

    def test_the_real_dockerfile_is_digest_pinned(self):
        """The gate itself. Red the day a base image loses its digest."""
        self.assertTrue(REAL_DOCKERFILE.is_file(), f"{REAL_DOCKERFILE} is missing")
        result = _run(str(REAL_DOCKERFILE.relative_to(REPO_ROOT)))
        self.assertEqual(
            result.returncode,
            0,
            f"services/api/Dockerfile is not digest-pinned:\n{result.stdout}\n{result.stderr}",
        )

    def test_the_default_argument_points_at_the_real_dockerfile(self):
        """Called with no arguments -- the form the workflow used for a year --
        it must still check the API image rather than silently checking nothing."""
        result = _run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("services/api/Dockerfile", result.stdout)


class TheGateKnowsHowToBeRed(unittest.TestCase):
    """Synthetic Dockerfiles. These prove failure is reachable at all."""

    def _check(self, body: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "Dockerfile"
            path.write_text(body, encoding="utf-8")
            return _run(str(path))

    def test_a_mutable_tag_is_rejected(self):
        result = self._check("FROM python:3.12-slim\nRUN true\n")
        self.assertEqual(
            result.returncode, 1, f"tag-pinned image passed:\n{result.stdout}"
        )
        self.assertIn("pinned by tag", result.stderr)

    def test_a_bare_image_with_no_tag_is_rejected(self):
        result = self._check("FROM ubuntu\n")
        self.assertEqual(
            result.returncode, 1, f"untagged image passed:\n{result.stdout}"
        )

    def test_a_literal_digest_is_accepted(self):
        result = self._check(f"FROM python:3.12-slim@{DIGEST}\nRUN true\n")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_truncated_digest_is_rejected(self):
        """63 hex characters is not a sha256, and a near-miss must not pass for
        one -- this is the case a length-blind `grep sha256` would wave through."""
        short = "sha256:" + "0" * 63
        result = self._check(f"FROM python:3.12-slim@{short}\n")
        self.assertEqual(
            result.returncode, 1, f"63-hex digest passed:\n{result.stdout}"
        )

    def test_a_reference_to_an_earlier_stage_needs_no_digest(self):
        """`FROM build` is not a registry pull. Rejecting it would make every
        multi-stage Dockerfile unfixable, which is how a gate gets switched off."""
        result = self._check(
            f"FROM python:3.12-slim@{DIGEST} AS build\nRUN true\nFROM build AS runtime\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_an_arg_default_carrying_a_digest_is_accepted(self):
        """The shape services/api/Dockerfile actually uses."""
        result = self._check(
            f"ARG PYTHON_IMAGE=python:3.12-slim@{DIGEST}\nFROM ${{PYTHON_IMAGE}} AS build\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_an_arg_default_without_a_digest_is_rejected(self):
        """Indirection through an ARG must not launder a mutable tag."""
        result = self._check(
            "ARG PYTHON_IMAGE=python:3.12-slim\nFROM ${PYTHON_IMAGE} AS build\n"
        )
        self.assertEqual(
            result.returncode, 1, f"tag hidden behind an ARG passed:\n{result.stdout}"
        )
        self.assertIn("not digest-pinned", result.stderr)

    def test_a_missing_file_fails_closed(self):
        """Absence must not read as cleanliness. A path typo in a caller would
        otherwise turn this gate green for a Dockerfile nobody checked."""
        result = _run("services/api/Dockerfile.does-not-exist")
        self.assertEqual(result.returncode, 1, f"missing file passed:\n{result.stdout}")
        self.assertIn("does not exist", result.stderr)

    def test_one_bad_stage_fails_the_whole_file(self):
        """A file whose first image is pinned and whose second is not must fail;
        reporting on only the first line is how half-checked files pass."""
        result = self._check(
            f"FROM python:3.12-slim@{DIGEST} AS build\nFROM node:20 AS web\n"
        )
        self.assertEqual(
            result.returncode, 1, f"second unpinned stage passed:\n{result.stdout}"
        )


class TheDigestHasToBeTheArgValue(unittest.TestCase):
    """A digest *somewhere on the ARG line* is not a pin.

    The gate used to ask whether the line ended in `@sha256:<64 hex>`, which is a
    question about the line rather than about the value Docker resolves. Both
    cases below pull `python:3.12-slim` -- the mutable tag this gate exists to
    forbid -- while the old check printed `ok: every base image ... is pinned`.
    A gate that is merely silent is bad; this one made a false statement.
    """

    def _check(self, body: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "Dockerfile"
            path.write_text(body, encoding="utf-8")
            return _run(str(path))

    def test_a_digest_left_behind_in_a_trailing_comment_is_not_a_pin(self):
        """services/api/Dockerfile carries a "To bump: ... copy the Digest"
        note directly above its ARG, so the likeliest way this repository loses
        its pin is a bump that leaves the old digest in a comment on the line."""
        result = self._check(
            f"ARG PYTHON_IMAGE=python:3.12-slim  # bump from @{DIGEST}\n"
            "FROM ${PYTHON_IMAGE} AS build\n"
        )
        self.assertEqual(
            result.returncode,
            1,
            f"a digest in a comment passed as a pin:\n{result.stdout}",
        )
        self.assertIn("not digest-pinned", result.stderr)

    def test_a_later_unpinned_redeclaration_is_not_saved_by_an_earlier_pin(self):
        """`grep -q` is satisfied by any one matching line, so a pinned first
        declaration used to vouch for an unpinned second one. Whichever of the
        two Docker resolves, one `FROM` here pulls a mutable tag."""
        result = self._check(
            f"ARG PY=python:3.12-slim@{DIGEST}\n"
            "ARG PY=python:3.12-slim\n"
            "FROM ${PY} AS build\n"
        )
        self.assertEqual(
            result.returncode,
            1,
            f"an unpinned redeclaration passed:\n{result.stdout}",
        )
        self.assertIn("not digest-pinned", result.stderr)

    def test_an_earlier_unpinned_declaration_is_not_saved_by_a_later_pin(self):
        """The same defect with the declarations swapped. Reading only the last
        declaration would let the `FROM` that sits between them pull a tag."""
        result = self._check(
            "ARG PY=python:3.12-slim\n"
            "FROM ${PY} AS build\n"
            f"ARG PY=python:3.12-slim@{DIGEST}\n"
            "FROM ${PY} AS runtime\n"
        )
        self.assertEqual(
            result.returncode,
            1,
            f"an unpinned first declaration passed:\n{result.stdout}",
        )

    def test_a_comment_naming_the_arg_does_not_count_as_a_declaration(self):
        """The mirror of the first case, and the reason the scan stops at `#`:
        a note that mentions `PY=<old tag>` must not be read as a second, worse
        declaration and fail a file whose real value is pinned. A gate with
        false positives gets bypassed, which costs the same as one with holes."""
        result = self._check(
            f"ARG PY=python:3.12-slim@{DIGEST}  # was PY=python:3.12-slim\n"
            "FROM ${PY} AS build\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_an_arg_that_is_only_redeclared_without_a_value_keeps_its_pin(self):
        """`ARG PY` with no `=` pulls the global value into a stage; it does not
        blank it. Rejecting this shape would break the one legal way to use a
        build arg across stages, and an unusable gate gets deleted."""
        result = self._check(
            f"ARG PY=python:3.12-slim@{DIGEST}\n"
            "FROM ${PY} AS build\n"
            "ARG PY\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class TheGateReadsFromFlags(unittest.TestCase):
    """`FROM --platform=$BUILDPLATFORM image@sha256:...` is a correctly pinned
    image. The gate rejected it -- right verdict is not the issue, the issue is
    that it rejected it by handing `--platform=...` to `grep` as an option and
    printing grep's usage screen. A gate whose failure output is another tool's
    help text teaches people to stop reading its output.
    """

    def _check(self, body: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "Dockerfile"
            path.write_text(body, encoding="utf-8")
            return _run(str(path))

    def test_a_platform_flag_does_not_hide_the_pinned_image_behind_it(self):
        result = self._check(
            f"FROM --platform=$BUILDPLATFORM python:3.12-slim@{DIGEST} AS build\n"
        )
        self.assertEqual(
            result.returncode,
            0,
            f"a correctly pinned image was rejected:\n{result.stdout}\n{result.stderr}",
        )
        self.assertNotIn("Usage: grep", result.stderr)

    def test_a_platform_flag_does_not_hide_a_mutable_tag_either(self):
        result = self._check("FROM --platform=$BUILDPLATFORM python:3.12-slim\n")
        self.assertEqual(
            result.returncode, 1, f"tag behind a flag passed:\n{result.stdout}"
        )
        self.assertIn("python:3.12-slim", result.stderr)
        self.assertNotIn("Usage: grep", result.stderr)

    def test_a_stage_declared_behind_a_platform_flag_is_still_a_known_stage(self):
        """The stage-name scan skipped `FROM --platform=x img AS build`, so the
        later `FROM build` looked like an unknown registry image."""
        result = self._check(
            f"FROM --platform=$BUILDPLATFORM python:3.12-slim@{DIGEST} AS build\n"
            "FROM build AS runtime\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
