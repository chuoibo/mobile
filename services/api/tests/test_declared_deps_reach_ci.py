"""Every dependency the application declares must reach the machine CI tests on.

`services/api/pyproject.toml` declares what the application needs.
`services/api/requirements-dev.txt` is what CI actually installs -- the `api` job
in `.github/workflows/test.yml` runs

    pip install -r services/api/requirements-dev.txt
    python -m pytest services/api/tests tests -q

and nothing else. There is no `pip install -e services/api`, so a dependency that
lives only in `pyproject.toml` is never installed on the runner. CLAUDE.md states
the resulting rule plainly -- "thêm phụ thuộc thì sửa cả hai chỗ" -- and until this
file that rule was enforced by remembering it.

Remembering failed on 2026-08-29. `f50a6a0` added `pillow>=11,<14` to
`pyproject.toml` for the upload sanitiser and did not add it to
`requirements-dev.txt`. The local suite stayed green because Pillow happened to be
present in this machine's conda environment, pulled in by something unrelated. On a
runner the same tree gives:

    ERROR tests/media/test_image_sanitizer.py
    E   ImportError: No module named 'PIL'
    Interrupted: 1 error during collection

That is a *collection* error, so it does not cost twenty red cases -- it costs the
entire run, including every gate that would otherwise have reported. The failure
also reads as "the new code is broken" rather than "a line is missing from a
requirements file", which is the expensive part.

The gate runs on the developer machine, where the missing package is installed and
therefore where the symptom is invisible. That is the point: it goes red at the
moment the two files disagree, not an hour later on a runner.

Both halves are load bearing, as in `test_dockerfile_pinning.py`:

  * `test_every_declared_dependency_is_installed_by_ci` is *the gate*.
  * the synthetic cases prove the gate knows how to be red. A gate seen only in the
    green has not been distinguished from a gate that cannot fail, and this
    repository has counted several of those in a single afternoon.

What this does not cover: whether the pinned version actually satisfies the range
in `pyproject.toml` (that needs a version parser this tree does not pin), whether
the pin is installable on the runner's platform, and the transitive dependencies of
either file. It checks exactly one thing -- that a declared name is also a pinned
name.
"""

from __future__ import annotations

import pathlib
import re
import tomllib
import unittest

API = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT = API / "pyproject.toml"
REQUIREMENTS_DEV = API / "requirements-dev.txt"

# A requirement string starts with the distribution name and ends it at the first
# extra, specifier, marker or comment: `psycopg[binary]>=3.2,<4` -> `psycopg`.
NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def normalise(name: str) -> str:
    """PEP 503: case, and runs of `-`, `_` and `.`, do not distinguish names."""
    return re.sub(r"[-_.]+", "-", name).lower()


def declared_dependencies(pyproject_text: str) -> set[str]:
    """Normalised names from `[project].dependencies`."""
    project = tomllib.loads(pyproject_text).get("project", {})
    names = set()
    for requirement in project.get("dependencies", []):
        match = NAME.match(requirement.strip())
        if match:
            names.add(normalise(match.group(1)))
    return names


def pinned_dependencies(requirements_text: str) -> dict[str, str]:
    """Normalised name -> the text that follows it, for each real requirement line.

    Comments are dropped rather than parsed. A package named only in a comment is
    not installed by anything, so it must not be able to satisfy the gate.
    """
    pins: dict[str, str] = {}
    for raw in requirements_text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = NAME.match(line)
        if match:
            pins[normalise(match.group(1))] = line[match.end() :]
    return pins


def declared_but_not_installed(pyproject_text: str, requirements_text: str) -> set[str]:
    return declared_dependencies(pyproject_text) - set(pinned_dependencies(requirements_text))


class DeclaredDependenciesReachCI(unittest.TestCase):
    """The gate itself, read off the two real files in this tree."""

    def test_the_two_files_exist(self):
        self.assertTrue(PYPROJECT.is_file(), PYPROJECT)
        self.assertTrue(REQUIREMENTS_DEV.is_file(), REQUIREMENTS_DEV)

    def test_every_declared_dependency_is_installed_by_ci(self):
        missing = declared_but_not_installed(
            PYPROJECT.read_text(encoding="utf-8"),
            REQUIREMENTS_DEV.read_text(encoding="utf-8"),
        )
        self.assertEqual(
            set(),
            missing,
            "declared in pyproject.toml but never installed by CI: "
            f"{sorted(missing)}. CI runs `pip install -r requirements-dev.txt` and "
            "nothing else, so these are absent on the runner even though they are "
            "present here. Add a pinned line for each to requirements-dev.txt.",
        )

    def test_the_declared_dependencies_are_pinned_exactly(self):
        """requirements-dev.txt exists so CI and a dev machine resolve one tree.

        A range in this file would defeat that, silently, on whichever day the
        index starts serving a different resolution.
        """
        pins = pinned_dependencies(REQUIREMENTS_DEV.read_text(encoding="utf-8"))
        for name in sorted(declared_dependencies(PYPROJECT.read_text(encoding="utf-8"))):
            with self.subTest(dependency=name):
                specifier = pins.get(name)
                self.assertIsNotNone(specifier, f"{name} is not in requirements-dev.txt")
                self.assertTrue(
                    specifier.lstrip("[").split("]")[-1].startswith("=="),
                    f"{name} must be pinned with `==`, found `{specifier}`",
                )


class TheGateKnowsHowToBeRed(unittest.TestCase):
    """Synthetic trees. None of these read the repository."""

    PYPROJECT_WITH_PILLOW = """
[project]
dependencies = ["fastapi>=0.115,<1", "pillow>=11,<14"]
"""

    def test_a_dependency_absent_from_requirements_is_reported(self):
        """Exactly the shape of f50a6a0."""
        self.assertEqual(
            {"pillow"},
            declared_but_not_installed(self.PYPROJECT_WITH_PILLOW, "fastapi==0.115.6\n"),
        )

    def test_a_dependency_present_in_both_is_not_reported(self):
        self.assertEqual(
            set(),
            declared_but_not_installed(
                self.PYPROJECT_WITH_PILLOW, "fastapi==0.115.6\npillow==12.2.0\n"
            ),
        )

    def test_a_package_named_only_in_a_comment_does_not_count_as_installed(self):
        """`# pillow is needed by the sanitiser` installs nothing."""
        self.assertEqual(
            {"pillow"},
            declared_but_not_installed(
                self.PYPROJECT_WITH_PILLOW,
                "fastapi==0.115.6\n# pillow is needed by the sanitiser\n",
            ),
        )

    def test_a_trailing_comment_does_not_hide_the_requirement(self):
        self.assertEqual(
            set(),
            declared_but_not_installed(
                self.PYPROJECT_WITH_PILLOW,
                "fastapi==0.115.6\npillow==12.2.0  # image sanitiser\n",
            ),
        )

    def test_names_differing_only_in_case_or_separator_are_the_same_name(self):
        """`Pillow` and `pillow`, `python_multipart` and `python-multipart`."""
        pyproject = '[project]\ndependencies = ["Pillow>=11", "python_multipart>=0.0.20"]\n'
        self.assertEqual(
            set(),
            declared_but_not_installed(pyproject, "pillow==12.2.0\npython-multipart==0.0.20\n"),
        )

    def test_an_extra_is_not_part_of_the_name(self):
        """`psycopg[binary]` is satisfied by a line pinning `psycopg`."""
        pyproject = '[project]\ndependencies = ["psycopg[binary]>=3.2,<4"]\n'
        self.assertEqual(
            set(), declared_but_not_installed(pyproject, "psycopg[binary]==3.2.3\n")
        )

    def test_an_option_line_is_not_a_requirement(self):
        """`-r base.txt` names no distribution."""
        self.assertEqual({}, pinned_dependencies("-r base.txt\n--index-url https://x/\n"))

    def test_optional_dependencies_are_not_required_of_ci(self):
        """`[project.optional-dependencies]` is a different contract."""
        pyproject = (
            "[project]\ndependencies = []\n"
            '[project.optional-dependencies]\ndev = ["pytest>=8.3,<10"]\n'
        )
        self.assertEqual(set(), declared_but_not_installed(pyproject, ""))


if __name__ == "__main__":
    unittest.main()
