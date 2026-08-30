"""The gate that asks whether a green run tested the software that ships.

`scripts/check_pin_drift.py` compares `services/api/requirements-dev.txt` --
what the image installs, and therefore what production runs -- against the
versions importable in the interpreter that runs `pytest`. Nothing in this
repository compared those two before; `grep -rn "importlib.metadata\\|pip freeze"`
over `scripts/`, `tests/` and `.github/` returned nothing on 2026-08-30.

## Why the gap was worth closing

Measured on main at 56a2c19, on the interpreter `scripts/gate.sh api` uses: of
12 pinned packages, 5 matched, 6 drifted and 1 was not installed at all. The
suite's green cases were produced by different software than ships, and the
report said nothing about it.

That condition is not theoretical -- it is what made #288 expensive. A 204 route
annotated `-> None` imports fine under fastapi 0.135.3 (this machine) and fails
an assert at route registration under 0.115.6 (the pin, and the image). 2305
cases were green while the container could not boot, and the demo machine stayed
dead for hours. `test_route_declarations_under_pinned_fastapi.py` now models that
one assert and `scripts/check_pinned_import.sh` loads the app under the real pin,
but both were written after the fact and both are about route declarations. The
*condition* -- tests running on versions that are not the shipping versions --
was still unmeasured, and it is the condition, not the route shape, that
generalises to pydantic, sqlalchemy, alembic and the test runner itself.

`pytest-subtests` is the clearest case and was found by this gate: pytest 9.0.3
absorbed subtests into core, so the plugin the pins name is not installed here at
all, and every "N subtests passed" line in this repository is produced by one
implementation locally and a different one in the image.

## Both halves are load bearing

As in `test_declared_deps_reach_ci.py` and `test_dockerfile_pinning.py`:

  * `test_the_shipping_requirements_file_is_readable` and the `gate.sh` cases are
    *the gate*.
  * the synthetic cases prove the gate knows how to be red, and -- just as
    importantly -- knows how to stay green. A checker that flagged everything
    would be switched off in a day, so the non-critical-drift case below is not
    padding; it is the reason the gate is survivable.

The synthetic requirements files are built from versions this interpreter really
has, so these cases mean the same thing on a machine whose drift set differs from
the one measured above.
"""

from __future__ import annotations

import importlib.metadata as md
import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "scripts" / "check_pin_drift.py"
GATE = REPO_ROOT / "scripts" / "gate.sh"
SHIPPING_REQUIREMENTS = REPO_ROOT / "services" / "api" / "requirements-dev.txt"


def run_checker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def installed(name: str) -> str | None:
    try:
        return md.version(name)
    except md.PackageNotFoundError:
        return None


def write_requirements(path: pathlib.Path, lines: list[str]) -> pathlib.Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def load_checker_module():
    """Import the script itself, so the critical set has one definition.

    Restating the list here would let the two drift apart, which is a comic way
    for a drift gate to fail.
    """

    import importlib.util

    spec = importlib.util.spec_from_file_location("check_pin_drift", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def absent_critical_name() -> str | None:
    """An import-critical package this interpreter genuinely does not have.

    Chosen at run time rather than hardcoded: which one is missing is a property
    of the machine, and on the one measured above it is `pytest-subtests`.
    """

    for name in sorted(load_checker_module().IMPORT_CRITICAL):
        if installed(name) is None:
            return name
    return None


def no_drift_copy_of_the_shipping_file(
    path: pathlib.Path,
) -> tuple[pathlib.Path, list[str]]:
    """The shipping file's own pin names, each set to what is installed here.

    This is the state CI is in and this machine has never been in: every pin
    matches. Built from the real file rather than a literal list, so it exercises
    the names the gate actually reads, and from `importlib.metadata` rather than
    hardcoded versions, so it means the same thing on any machine.

    Pins this interpreter does not have are dropped -- they cannot be made to
    match locally, and their absence is already covered by
    `test_a_critical_pin_that_is_not_installed_at_all_is_red`.
    """

    module = load_checker_module()
    names: list[str] = []
    lines: list[str] = []
    for name, _pinned in sorted(module.read_pins(SHIPPING_REQUIREMENTS).items()):
        here = installed(name)
        if here is None:
            continue
        names.append(name)
        lines.append(f"{name}=={here}")
    write_requirements(path, lines)
    return path, names


# --- the gate ------------------------------------------------------------


def test_the_shipping_requirements_file_is_readable():
    """The gate must be able to read the file it exists to check.

    Exit 2 rather than 0 is the contract for "could not tell". This case is here
    because the failure it guards against is silent: a requirements file moved or
    a parser that stops matching would otherwise turn the gate green forever, and
    green is exactly the answer it must never give by accident.
    """

    assert SHIPPING_REQUIREMENTS.is_file(), (
        f"{SHIPPING_REQUIREMENTS} is what the image installs; the gate reads it"
    )
    result = run_checker()
    assert result.returncode in (0, 1), (
        "the checker could not read the real requirements file "
        f"(exit {result.returncode})\n{result.stdout}\n{result.stderr}"
    )
    assert "fastapi" in result.stdout, (
        "fastapi is pinned in the shipping requirements and must appear in the "
        f"survey; the parser has gone blind\n{result.stdout}"
    )


def test_the_survey_names_every_pin_when_nothing_drifts(tmp_path):
    """The state CI runs in, and the one this machine cannot reach on its own.

    This case exists because the gate above went red on CI at 2862154 while
    every pin matched -- the exact opposite of its intent. The survey printed pin
    names only inside an `if drifted or absent:` block, so a clean interpreter
    got a report that named nothing it had surveyed, and the "has the parser gone
    blind" assertion had no name to find.

    A survey that speaks only when it has bad news cannot be used as evidence
    that it read anything, which is the one thing that case needs it for. So the
    listing is unconditional, and this proves it on the branch the local machine
    never takes: the drift set here is 6/12, and it was that permanent drift that
    made the hole invisible to every local run.
    """

    req, names = no_drift_copy_of_the_shipping_file(tmp_path / "no-drift.txt")
    assert "fastapi" in names, (
        "fastapi must be installed and pinned for this case to reproduce CI"
    )

    result = run_checker("--requirements", str(req))
    assert result.returncode == 0, (
        f"every pin was set to the installed version, so there is no drift\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "Không pin quan trọng nào lệch" in result.stdout, (
        f"the clean verdict is missing\n{result.stdout}"
    )

    missing = [name for name in names if name not in result.stdout]
    assert not missing, (
        "a clean survey must still name what it surveyed, or it cannot prove it "
        f"read the file at all; {len(missing)} of {len(names)} pins unnamed: "
        f"{missing}\n{result.stdout}"
    )


def test_the_survey_names_matching_pins_alongside_drifted_ones(tmp_path):
    """Both states in one file, so the listing cannot be made conditional again.

    Printing names only on the clean branch would satisfy the case above and
    reintroduce the same blindness in reverse. A reader of a red report needs to
    see what was checked *and passed*, not only the offenders -- otherwise a pin
    that silently stopped being parsed looks identical to a pin that matched.
    """

    fastapi_here = installed("fastapi")
    jinja_here = installed("jinja2")
    assert fastapi_here and jinja_here
    req = write_requirements(
        tmp_path / "r.txt",
        [
            "fastapi==0.0.1-not-a-real-version",  # drifted
            f"jinja2=={jinja_here}",  # matches
        ],
    )

    result = run_checker("--requirements", str(req))
    assert result.returncode == 1, f"critical drift is red\n{result.stdout}"
    assert "fastapi" in result.stdout, f"the offender must be named\n{result.stdout}"
    assert "jinja2" in result.stdout, (
        "a pin that matched must be named too, or a red report cannot "
        f"distinguish 'checked and fine' from 'never read'\n{result.stdout}"
    )
    assert jinja_here in result.stdout, (
        "the matching row must carry the version it compared, not just the name "
        f"-- a name alone is not evidence of a comparison\n{result.stdout}"
    )


def test_the_survey_counts_every_pin_in_the_shipping_file():
    """Every `name==version` line is surveyed, not a subset.

    A parser that silently dropped lines would under-report drift, which is the
    direction that costs something.
    """

    import re

    expected = len(
        [
            line
            for line in SHIPPING_REQUIREMENTS.read_text(encoding="utf-8").splitlines()
            if re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*\s*==", line.split("#")[0].strip())
        ]
    )
    assert expected > 0, "the shipping file has no pins at all -- read it by hand"
    result = run_checker()
    assert (
        f"pin đọc từ services/api/requirements-dev.txt: {expected}" in result.stdout
    ), f"expected {expected} pins in the survey header\n{result.stdout}"


# --- the gate knows how to be red ----------------------------------------


def test_a_drifted_critical_pin_is_red(tmp_path):
    """fastapi pinned to a version this interpreter does not have."""

    here = installed("fastapi")
    assert here is not None, "fastapi must be installed for this case to mean anything"
    fake = "0.0.1-not-a-real-version"
    assert fake != here
    req = write_requirements(tmp_path / "r.txt", [f"fastapi=={fake}"])

    result = run_checker("--requirements", str(req))
    assert result.returncode == 1, (
        f"drift in an import-critical pin must be red\n{result.stdout}"
    )
    assert "fastapi" in result.stdout
    assert "pinned-import" in result.stdout, (
        "a red gate has to name the way out, or it gets waived instead of fixed"
    )


def test_a_critical_pin_that_is_not_installed_at_all_is_red(tmp_path):
    """The `pytest-subtests` shape: pinned, named, and simply absent.

    This is the case that found a real one. It must not be confused with a match.
    """

    name = absent_critical_name()
    if name is None:
        pytest.skip(
            "every import-critical package is installed on this machine, so "
            "there is no real absence to exercise"
        )
    req = write_requirements(tmp_path / "r.txt", [f"{name}==2.10.0"])

    result = run_checker("--requirements", str(req))
    assert result.returncode == 1, (
        f"a pinned-but-absent critical package must be red\n{result.stdout}"
    )
    assert "KHÔNG CÀI" in result.stdout, (
        f"absence must be reported as absence, not as a version\n{result.stdout}"
    )


def test_a_requirements_file_with_no_pins_cannot_report_clean(tmp_path):
    """No parseable pin means "cannot tell", which is exit 2 -- never 0."""

    req = write_requirements(
        tmp_path / "r.txt",
        ["# only a comment", "", "-r other.txt", "somepkg>=1,<2"],
    )
    result = run_checker("--requirements", str(req))
    assert result.returncode == 2, (
        f"a file with no pins must be 'cannot tell', not 'clean'\n"
        f"{result.stdout}\n{result.stderr}"
    )


def test_a_missing_requirements_file_cannot_report_clean(tmp_path):
    result = run_checker("--requirements", str(tmp_path / "nope.txt"))
    assert result.returncode == 2, (
        f"an unreadable file must be 'cannot tell', not 'clean'\n{result.stderr}"
    )


# --- the gate knows how to stay green ------------------------------------


def test_a_matching_critical_pin_is_green(tmp_path):
    """Pin fastapi to what is actually here: the gate must go quiet.

    Built from `importlib.metadata` rather than a literal, so this case says the
    same thing on a machine with a different fastapi.
    """

    here = installed("fastapi")
    assert here is not None
    req = write_requirements(tmp_path / "r.txt", [f"fastapi=={here}"])

    result = run_checker("--requirements", str(req))
    assert result.returncode == 0, (
        f"a pin that matches the installed version is not drift\n{result.stdout}"
    )
    assert "Không pin quan trọng nào lệch" in result.stdout


def test_drift_in_a_non_critical_pin_is_reported_but_not_red(tmp_path):
    """A gate that fails on everything gets deleted; this is why it does not.

    `jinja2` is exercised by assertions rather than at import, so a test that
    passed has actually observed its behaviour. The drift is still printed --
    silence would be its own bug -- but it does not invalidate the run.
    """

    here = installed("jinja2")
    assert here is not None, "jinja2 must be installed for this case to mean anything"
    req = write_requirements(tmp_path / "r.txt", ["jinja2==0.0.1-not-a-real-version"])

    result = run_checker("--requirements", str(req))
    assert result.returncode == 0, (
        f"non-critical drift must not fail the run\n{result.stdout}"
    )
    assert "jinja2" in result.stdout, (
        f"non-critical drift must still be VISIBLE\n{result.stdout}"
    )
    assert "[quan trọng]" not in result.stdout


def test_names_only_prints_exactly_the_critical_offenders(tmp_path):
    """The machine-readable channel `gate.sh` consumes."""

    fastapi_here = installed("fastapi")
    jinja_here = installed("jinja2")
    assert fastapi_here and jinja_here
    req = write_requirements(
        tmp_path / "r.txt",
        [
            "fastapi==0.0.1-not-a-real-version",  # critical, drifted
            "jinja2==0.0.2-not-a-real-version",  # non-critical, drifted
        ],
    )

    result = run_checker("--requirements", str(req), "--names-only")
    assert result.returncode == 1
    assert result.stdout.split() == ["fastapi"], (
        "--names-only must list critical offenders and nothing else, or gate.sh "
        f"prints noise as a blocking reason\n{result.stdout!r}"
    )


# --- the wiring in gate.sh ------------------------------------------------
#
# The checker being right is half of it. The hole this closes is that
# `scripts/gate.sh api` exited 0 on a tree that could not boot, so what matters
# is that the verdict actually reaches gate.sh's exit code.


def test_a_stage_that_says_nothing_about_libraries_stays_green():
    """`guard` scans files. Drift is irrelevant to it and must not block it.

    Without this, a machine without docker could not run the repo guard at all,
    and the gate would be switched off rather than fixed.
    """

    result = subprocess.run(
        [str(GATE), "guard"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"the repo-guard stage must not be blocked by library drift\n"
        f"{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
    )
    assert "KHÔNG PHẢI TRÊN BẢN SẼ SHIP" not in result.stdout


def test_a_code_tier_alone_matches_the_measured_drift_state():
    """`migration` runs application code, so its green is subject to the verdict.

    Written against whatever this machine's drift actually is rather than against
    a hardcoded expectation: on the machine measured above it is red and names
    `pinned-import`, and on a machine whose pins are installed exactly it is
    green. Both are correct, and asserting only one of them would make this case
    a machine-specific tripwire instead of a test of the rule.
    """

    drift = run_checker("--names-only")
    assert drift.returncode in (0, 1)
    result = subprocess.run(
        [str(GATE), "migration"], cwd=REPO_ROOT, capture_output=True, text=True
    )

    if drift.returncode == 1:
        assert result.returncode == 1, (
            "critical pins drift here, and no stage in this run loaded the app "
            "under the shipping versions -- the run must not report green\n"
            f"{result.stdout[-2000:]}"
        )
        assert "KHÔNG PHẢI TRÊN BẢN SẼ SHIP" in result.stdout
        assert "pinned-import" in result.stdout, "the verdict must name the way out"
    else:
        assert result.returncode == 0, (
            f"no drift here, so nothing should block\n{result.stdout[-2000:]}"
        )


def test_the_waiver_is_loud_and_recorded():
    """A machine with no docker needs a way past. It must never be a silent one.

    The waiver is the same shape as a skip, and CLAUDE.md's rule for skips is
    that they are never a pass. So the run may exit 0, but it may not do so
    quietly: the reason has to survive into the summary a merge decision reads.
    """

    drift = run_checker("--names-only")
    if drift.returncode != 1:
        pytest.skip("no critical drift on this machine, so there is nothing to waive")

    summary = REPO_ROOT / ".pin-drift-summary.tmp"
    try:
        result = subprocess.run(
            [str(GATE), "migration"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env={
                **__import__("os").environ,
                "MOBILE_GATE_ALLOW_DRIFT": "1",
                "GATE_SUMMARY_FILE": str(summary),
            },
        )
        assert result.returncode == 0, (
            f"the waiver must let the run finish\n{result.stdout[-2000:]}"
        )
        assert "MOBILE_GATE_ALLOW_DRIFT=1" in result.stdout, (
            "a waived run that does not say so is exactly the silent pass this "
            f"gate exists against\n{result.stdout[-2000:]}"
        )
        assert summary.is_file(), "gate.sh did not write the summary"
        text = summary.read_text(encoding="utf-8")
        assert "pin-drift=drift-waived" in text, (
            f"the waiver must reach the machine-readable channel too\n{text}"
        )
    finally:
        summary.unlink(missing_ok=True)
