"""A ratchet that keeps unformatted Python out of tests/qa/.

Three files from rd-qa-37 reached main while `ruff format` rejected all three.
Nothing was broken about the gate that should have stopped them: the CI job
`ruff on changed files` runs `scripts/ruff_changed.sh`, which would have caught
them on the pull request. It simply never executed -- GitHub Actions started no
job at all during the billing outage of 2026-08-29, so the change went to main
unchecked.

That is the hole this file covers. `ruff_changed.sh` is a *diff* gate: standing
on main with nothing changed, it finds zero candidate files, prints "no Python
files changed" and exits 0. That is correct behaviour for a diff gate and wrong
as a safety net -- it means main's own contents are never re-examined by
anything that runs locally. A check that reports success while inspecting
nothing is the exact failure mode that let these three files land, so this gate
asserts that it inspected something before it is allowed to pass.

Why a ratchet and not `ruff format --check tests/qa`:

19 of the 25 Python files under tests/qa/ are unformatted on main. A blanket
gate would be red on the commit that introduces it, and the only way to land it
green would be to reformat 16 files belonging to other QA turns -- which
CLAUDE.md forbids, because a 16-file formatting diff drowns the real change
underneath it. So the legacy debt is written down in LEGACY_UNFORMATTED and
frozen. It cannot grow, and STALE-entry detection means it can only shrink:
clean a file up and this gate tells you to strike it off the list.

The allowlist is version-stable. ruff 0.9.2 (the pin in
services/api/requirements-dev.txt, which CI installs) and ruff 0.15.15 name the
identical dirty set across all 25 files and produce byte-identical output, so
the list does not depend on which of the two a developer happens to have.

Note that tests/qa/ sits outside services/api/pyproject.toml, so ruff applies
its default configuration here -- line-length 88, not the project's. That is
why most of the diff this gate demands is line wrapping.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
QA_ROOT = REPO_ROOT / "tests" / "qa"

# Unformatted on main before this gate existed, and left alone on purpose.
# These belong to other QA turns; reformatting them here would bury the real
# change. Entries may only ever be removed -- see test_no_stale_allowlist_entry.
LEGACY_UNFORMATTED = frozenset(
    {
        "tests/qa/pr-57/test_rendered_contrast_pr57.py",
        "tests/qa/pr-67/test_script_bill_mo_phan_loai_status.py",
        "tests/qa/rd-qa-02/run_mutations.py",
        "tests/qa/rd-qa-03/test_confidence_does_not_certify_correctness.py",
        "tests/qa/rd-qa-07/03-mutation-gate.py",
        "tests/qa/rd-qa-10/do_commit_sau_phan_hoi.py",
        "tests/qa/rd-qa-10/probe_quyen_rieng_tu.py",
        "tests/qa/rd-qa-10/repro_dong_thoi.py",
        "tests/qa/rd-qa-10/repro_ghi_xong_doc_khong_thay.py",
        "tests/qa/rd-qa-11/forward_link_to_active.py",
        "tests/qa/rd-qa-11/race_invite_link.py",
        "tests/qa/rd-qa-12/probe_may_da_seed.py",
        "tests/qa/rd-qa-18/tan-cong-tim-dia-diem.py",
        "tests/qa/rd-qa-24/f16-di-bo.py",
        "tests/qa/rd-qa-27/f32-di-bo.py",
        "tests/qa/rd-qa-27/f32-gemini-that.py",
    }
)


def qa_python_files() -> list[Path]:
    """Every Python file under tests/qa/, sorted for a stable failure message."""
    return sorted(QA_ROOT.rglob("*.py"))


def ruff_rejects_format(path: Path) -> bool:
    """True when `ruff format` would rewrite *path*.

    Exit code, not stdout parsing: ruff's wording has changed between releases
    and a gate that silently stops matching its own grep is a gate that stops
    biting. rc 0 means formatted, rc 1 means it would reformat; anything else
    is ruff failing to run, which must surface as an error rather than as a
    quiet pass.
    """
    result = subprocess.run(
        ["ruff", "format", "--check", "--no-cache", "--", str(path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        raise AssertionError(
            f"ruff could not check {path}: rc={result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result.returncode == 1


class QaScriptsAreRuffFormatted(unittest.TestCase):
    def setUp(self) -> None:
        # A missing tool is a failure, never a skip. The whole reason those
        # three files reached main is a check that reported success without
        # having looked at anything; reproducing that here would be perverse.
        if shutil.which("ruff") is None:
            self.fail(
                "ruff is not installed -- refusing to report a check that did "
                "not run. Install it with: "
                "pip install -r services/api/requirements-dev.txt"
            )

    def test_the_gate_actually_inspects_files(self) -> None:
        """A pass must mean files were read, not that the glob found nothing.

        `ruff_changed.sh` exits 0 on an empty file list, which is right for a
        diff gate and is also precisely how these three files slipped through
        unnoticed on main. If tests/qa/ is ever moved or renamed, this gate
        must go red rather than turn into decoration that passes forever.
        """
        files = qa_python_files()
        self.assertGreaterEqual(
            len(files),
            20,
            f"expected tests/qa/ to hold the QA lane's Python scripts, found "
            f"{len(files)} -- has the directory moved? A gate that checks "
            f"nothing must not report success.",
        )

    def test_no_new_unformatted_file_under_tests_qa(self) -> None:
        """The biting half: anything not on the legacy list must be clean."""
        offenders = [
            str(path.relative_to(REPO_ROOT))
            for path in qa_python_files()
            if str(path.relative_to(REPO_ROOT)) not in LEGACY_UNFORMATTED
            and ruff_rejects_format(path)
        ]
        self.assertEqual(
            offenders,
            [],
            "ruff format rejects these files under tests/qa/:\n  "
            + "\n  ".join(offenders)
            + "\n\nRun: ruff format "
            + " ".join(offenders),
        )

    def test_no_stale_allowlist_entry(self) -> None:
        """The tightening half: a cleaned-up file must leave the list.

        Without this, the allowlist rots into a permanent exemption -- a file
        gets formatted, the entry stays, and the next unformatted version of
        that same file sails past the gate.
        """
        stale = sorted(
            entry
            for entry in LEGACY_UNFORMATTED
            if (REPO_ROOT / entry).is_file()
            and not ruff_rejects_format(REPO_ROOT / entry)
        )
        self.assertEqual(
            stale,
            [],
            "these files are formatted now and must be struck off "
            "LEGACY_UNFORMATTED:\n  " + "\n  ".join(stale),
        )

    def test_no_allowlist_entry_points_at_a_missing_file(self) -> None:
        """A dead entry silently exempts the path if the file ever returns."""
        missing = sorted(
            entry for entry in LEGACY_UNFORMATTED if not (REPO_ROOT / entry).is_file()
        )
        self.assertEqual(
            missing,
            [],
            "LEGACY_UNFORMATTED names files that no longer exist:\n  "
            + "\n  ".join(missing),
        )


if __name__ == "__main__":
    unittest.main()
