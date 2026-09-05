#!/usr/bin/env python3
"""Mutation harness for the PYTHON half of the expression-side Law 1 gate.

## Why a second harness

`tests/qa/qa-tt-0002-488/dot_bien_cong_bieu_thuc_sql_488.py` measures the wire
half of `test_money_expressions_are_integer_postgres.py`: seven `cast(...)`
sites, the surface names, and the wire driver's call lines. It has no mutant
that touches the Python half at all, so the eighteen-row table it prints says
nothing about whether `test_money_values_reaching_python_are_int` is load
bearing. That test was dead when it was written -- its loop body ran zero times
because `group_recap` returned early -- and eighteen green rows never noticed.

This harness asks the question the other one does not ask: **if a money value
arrives in Python as something other than `int`, does anything go red?**

Three families, all derived from the tree rather than typed out here:

    W  neuter ONE registered probe to `return ()`   -- the vacuous-probe shape
    R  turn ONE money `int(...)` in the repository into `float(...)` -- a real
       regression, with the gate left fully armed
    P  R together with the W of the same surface name -- disarm the probe that
       watches this value, then regress it for real

R is the family that matters. The wire type is unchanged by it -- the SQL still
says `cast(... AS bigint)` -- so the wire rule cannot see it. Only the Python
assert can, which makes R a direct measurement of whether that assert is alive.

## How the sites are found

Probes are read out of the gate file's AST by their `@_register_python_money_probe`
decorator, so a fifth probe added tomorrow is mutated tomorrow without editing
this file. Repository sites are `int(<expr>)` calls inside a method whose name
is on the surface.

**One stated limit.** Not every `int()` in those methods is money -- some wrap
`memory_count` or a membership count -- and Law 1 is about money. Money sites
are selected by `"_vnd"` appearing in the call's source text. That is a
name-shaped filter inside a *measuring* tool, which is a different thing from a
name-shaped filter inside a gate: it decides what this harness mutates, not
what the product is allowed to do. A money value spelled without `_vnd` is
outside this table, and the count printed at the top is how you check it.

The harness REFUSES rather than printing a clean table when it cannot measure:
no database, a dirty tree, an already-red baseline, or an empty site list.

## How to run it

    scripts/postgres_tier.sh --keep -k money_expressions    # a disposable DB

then from the repository root:

    MOBILE_TEST_DATABASE_URL='<url>' python3 \\
      services/api/tests/qa/backend-tt-0002-tang-python-488/dot_bien_tang_python_488.py

Exit 0: every mutant caught. Exit 1: at least one survived, named. Exit 2: the
harness could not measure and is saying so.

### Comparing against an older gate

    ... dot_bien_tang_python_488.py --gate-from e03b56f

replaces the gate file with that revision's version and runs the R family
against it, leaving the repository mutations identical. That is the before/after
for a fix to the gate: the same regression, the old file, and whether it was
caught then. W and P are skipped in this mode and reported as skipped, because
the older file has no registered probes to neuter.

## What it does NOT prove

It mutates one repository module and one test file. A money value mangled in
`app/api/service.py`, or in a module this surface does not name, is outside it
-- as is whether the delivered amount was *correct*, which is what the 41 golden
vectors are for.
"""

from __future__ import annotations

import argparse
import ast
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[5]
API = REPO / "services/api"
REPOSITORY = API / "app/api/repository.py"
GATE = API / "tests/postgres/test_money_expressions_are_integer_postgres.py"

TRACKED = (
    "services/api/app/api/repository.py",
    "services/api/tests/postgres/test_money_expressions_are_integer_postgres.py",
)

REGISTER_DECORATOR = "_register_python_money_probe"
MONEY_HINT = "_vnd"


class Refuse(Exception):
    """The harness cannot measure. Never downgraded to a warning."""


def _line_starts(source: str) -> list[int]:
    starts = [0]
    for line in source.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    return starts


# --------------------------------------------------------------------------
# Finding the mutation sites by reading the tree
# --------------------------------------------------------------------------


class ProbeSite:
    """One `@_register_python_money_probe("name")` function in the gate file."""

    def __init__(self, surface: str, function: str, offset: int, indent: str) -> None:
        self.surface = surface
        self.function = function
        self.offset = offset
        self.indent = indent


def probe_sites(source: str) -> list[ProbeSite]:
    """Every registered Python probe, with where a `return ()` would go.

    The insertion point is the first *statement* of the body rather than the
    line after `def`, so a probe that grows a docstring later is still neutered
    by one edit instead of two.
    """

    starts = _line_starts(source)
    tree = ast.parse(source)
    sites: list[ProbeSite] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not (
                isinstance(decorator.func, ast.Name)
                and decorator.func.id == REGISTER_DECORATOR
            ):
                continue
            if len(decorator.args) != 1 or not isinstance(
                decorator.args[0], ast.Constant
            ):
                raise Refuse(
                    f"{REGISTER_DECORATOR} on {node.name} does not carry exactly "
                    "one literal surface name; the harness will not guess"
                )
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]
            if not body:
                raise Refuse(f"probe {node.name} has no statements")
            first = body[0]
            sites.append(
                ProbeSite(
                    surface=str(decorator.args[0].value),
                    function=node.name,
                    offset=starts[first.lineno - 1],
                    indent=" " * first.col_offset,
                )
            )
    sites.sort(key=lambda site: site.offset)
    return sites


class MoneySite:
    """One `int(<expr>)` call carrying money inside a surface method."""

    def __init__(self, owner: str, start: int, end: int, text: str) -> None:
        self.owner = owner
        self.start = start
        self.end = end
        self.text = text


def money_int_sites(source: str, surfaces: frozenset[str]) -> list[MoneySite]:
    """`int(...)` calls inside surface methods whose source mentions money.

    The offsets address the callee `int` alone, so the mutant is exactly one
    token wide: `int(x)` becomes `float(x)` and nothing else moves.
    """

    starts = _line_starts(source)
    tree = ast.parse(source)

    def offset(lineno: int, col: int) -> int:
        return starts[lineno - 1] + col

    sites: list[MoneySite] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if node.name not in surfaces:
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            if not (isinstance(inner.func, ast.Name) and inner.func.id == "int"):
                continue
            if len(inner.args) != 1:
                continue
            segment = ast.get_source_segment(source, inner) or ""
            if MONEY_HINT not in segment:
                continue
            sites.append(
                MoneySite(
                    owner=node.name,
                    start=offset(inner.func.lineno, inner.func.col_offset),
                    end=offset(inner.func.end_lineno, inner.func.end_col_offset),
                    text=" ".join(segment.split())[:54],
                )
            )
    sites.sort(key=lambda site: site.start)
    return sites


# --------------------------------------------------------------------------
# Running the gate
# --------------------------------------------------------------------------


def run_gate(database_url: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["MOBILE_TEST_DATABASE_URL"] = database_url
    env["MOBILE_REQUIRE_POSTGRES_TESTS"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(GATE.relative_to(API)),
            "-q",
            "--no-header",
        ],
        cwd=API,
        capture_output=True,
        text=True,
        env=env,
        timeout=900,
    )
    body = [line for line in proc.stdout.splitlines() if line.strip()]
    return proc.returncode, body[-1] if body else "(khong co dau ra)"


def dirty_tracked() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain", "--", *TRACKED],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def restore() -> None:
    subprocess.run(["git", "checkout", "--", *TRACKED], cwd=REPO, check=True)
    dirty = dirty_tracked()
    if dirty:
        raise Refuse(f"khong khoi phuc duoc cay sau dot bien:\n{dirty}")


def gate_source_at(ref: str) -> str:
    """The gate file as of `ref`, or a refusal naming the revision."""

    proc = subprocess.run(
        ["git", "show", f"{ref}:{GATE.relative_to(REPO)}"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise Refuse(f"khong doc duoc file cong tai {ref}: {proc.stderr.strip()}")
    return proc.stdout


# --------------------------------------------------------------------------
# The table
# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("MOBILE_TEST_DATABASE_URL", ""),
        help="PostgreSQL URL; defaults to MOBILE_TEST_DATABASE_URL",
    )
    parser.add_argument(
        "--gate-from",
        default="",
        metavar="REF",
        help="run the R family against the gate file as of REF (before/after)",
    )
    options = parser.parse_args()

    if not options.database_url:
        print(
            "KHONG KIEM DUOC: chua co MOBILE_TEST_DATABASE_URL. Cong duoi do can "
            "PostgreSQL that; chay 'scripts/postgres_tier.sh --keep' de lay mot cai.",
            file=sys.stderr,
        )
        return 2
    if not GATE.exists():
        print(
            f"KHONG KIEM DUOC: khong co {GATE.relative_to(REPO)}.",
            file=sys.stderr,
        )
        return 2

    dirty = dirty_tracked()
    if dirty:
        print(
            "KHONG KIEM DUOC: hai file se bi dot bien dang co thay doi chua commit.\n"
            "Commit hoac stash truoc, neu khong ban sua cua ban se bi xoa:\n"
            f"{dirty}",
            file=sys.stderr,
        )
        return 2

    gate_source = GATE.read_text(encoding="utf-8")
    repository_source = REPOSITORY.read_text(encoding="utf-8")

    probes = probe_sites(gate_source)
    if not probes:
        print(
            f"KHONG KIEM DUOC: khong tim thay probe nao mang @{REGISTER_DECORATOR} "
            f"trong {GATE.relative_to(REPO)}. Danh sach nguon rong lam ca bang tu "
            "thao va in xanh ma khong do gi.",
            file=sys.stderr,
        )
        return 2

    surfaces = frozenset(site.surface for site in probes)
    money = money_int_sites(repository_source, surfaces)
    if not money:
        print(
            "KHONG KIEM DUOC: khong tim thay diem int(...) mang tien nao trong "
            f"{len(surfaces)} method surface. Khong co gi de hoi quy.",
            file=sys.stderr,
        )
        return 2

    # In --gate-from mode the file under measurement is the older one, so the
    # replacement is applied for every run including the baseline.
    old_gate = gate_source_at(options.gate_from) if options.gate_from else ""

    def install_gate(source: str) -> None:
        GATE.write_text(old_gate if options.gate_from else source, encoding="utf-8")

    print(f"probe dang ky trong file cong: {len(probes)}")
    for site in probes:
        print(f"  {site.surface} <- {site.function}()")
    print(f"diem int(...) mang tien trong {len(surfaces)} method surface: {len(money)}")
    for site in money:
        print(f"  {site.owner}: {site.text}")
    if options.gate_from:
        print(
            f"\nCHE DO --gate-from {options.gate_from}: file cong bi thay bang ban cu."
        )
        print("Chi chay ho R. Ho W va P bi BO QUA (ban cu khong co probe de vo hieu).")
    print()

    survivors: list[str] = []

    def measure(label: str) -> None:
        code, summary = run_gate(options.database_url)
        caught = code != 0
        print(
            f"{label:<58} rc={code}  {summary:<34} -> {'BAT DUOC' if caught else 'LOT'}"
        )
        if not caught:
            survivors.append(label)

    print("=== M0 nen ===")
    if options.gate_from:
        install_gate(gate_source)
    baseline_code, baseline_summary = run_gate(options.database_url)
    print(
        f"{'M0 khong dot bien (phai XANH)':<58} rc={baseline_code}  {baseline_summary}"
    )
    restore()
    if baseline_code != 0:
        print(
            "KHONG KIEM DUOC: nen da DO san. Bang dot bien tren mot cay do san "
            "khong phan biet duoc cai gi duoc gac.",
            file=sys.stderr,
        )
        return 2

    if not options.gate_from:
        print(f"\n=== W1-W{len(probes)}: vo hieu TUNG probe thanh `return ()` ===")
        for index, site in enumerate(probes, start=1):
            mutated = (
                gate_source[: site.offset]
                + f"{site.indent}return ()\n"
                + gate_source[site.offset :]
            )
            GATE.write_text(mutated, encoding="utf-8")
            measure(f"W{index} probe {site.surface} tra ve rong")
            restore()

    print(f"\n=== R1-R{len(money)}: int(...) -> float(...), cong CON NGUYEN VU KHI ===")
    for index, site in enumerate(money, start=1):
        REPOSITORY.write_text(
            repository_source[: site.start] + "float" + repository_source[site.end :],
            encoding="utf-8",
        )
        install_gate(gate_source)
        measure(f"R{index} {site.owner}: float({site.text[4:44]}")
        restore()

    if not options.gate_from:
        print("\n=== P: vo hieu probe VA hoi quy that gia tri no canh ===")
        paired = 0
        for site in probes:
            owned = [item for item in money if item.owner == site.surface]
            if not owned:
                continue
            paired += 1
            target = owned[0]
            REPOSITORY.write_text(
                repository_source[: target.start]
                + "float"
                + repository_source[target.end :],
                encoding="utf-8",
            )
            GATE.write_text(
                gate_source[: site.offset]
                + f"{site.indent}return ()\n"
                + gate_source[site.offset :],
                encoding="utf-8",
            )
            measure(f"P {site.surface}: probe rong + float mot gia tri that cua no")
            restore()
        if paired == 0:
            print(
                "KHONG KIEM DUOC: khong ghep duoc cap nao (probe <-> int() cung ten).",
                file=sys.stderr,
            )
            return 2

    print("\n=== TONG KET ===")
    if not survivors:
        print("khong dot bien nao song sot")
        return 0
    print(f"{len(survivors)} dot bien SONG SOT -- cong in xanh trong khi loi con song:")
    for item in survivors:
        print(f"  - {item}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refuse as error:
        print(f"KHONG KIEM DUOC: {error}", file=sys.stderr)
        sys.exit(2)
