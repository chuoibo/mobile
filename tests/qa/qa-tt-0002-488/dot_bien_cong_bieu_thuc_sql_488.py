#!/usr/bin/env python3
"""Mutation harness for the expression-side Law 1 gate added by PR #488.

## What it answers

PR #488 adds `tests/postgres/test_money_expressions_are_integer_postgres.py`,
which states Law 1 over the *result type PostgreSQL reports* instead of over a
list of function names. The gate is real: it goes red on the code that shipped
before the PR. The question this harness asks is the next one -- **which
regressions can slip past it while it still prints green** -- and it asks it by
breaking one thing at a time rather than by picking one case to try.

Four mutant families, all derived from the tree instead of typed out here:

    C  revert ONE `cast(..., BigInteger)` in app/api/repository.py
    N  drop ONE name from MONEY_QUERY_SURFACE
    D  drop ONE call from _drive_money_query_surface, KEEP the name in the list
    P  D and its matching C together -- disarm the gate, then regress for real

## Why nothing here is a hand-written list

A harness that carries its own list of seven line numbers inherits exactly the
weakness it is measuring: it cannot know when the tree grew an eighth. So the
cast sites are found by walking the AST for `cast(<expr>, BigInteger)`, the
surface names are imported from the gate module, and the drive calls are found
by reading the body of `_drive_money_query_surface`. The harness REFUSES to run
when any of those comes back empty -- an empty source list makes every loop run
zero times and the whole table print green without measuring anything.

## How to run it

Needs a real PostgreSQL, because the gate under test does. Get a disposable one
and leave it up:

    scripts/postgres_tier.sh --keep -k money_expressions      # prints the URL

then, from the repository root:

    MOBILE_TEST_DATABASE_URL='<the URL it printed>' \
      python3 tests/qa/qa-tt-0002-488/dot_bien_cong_bieu_thuc_sql_488.py

Exit 0 means every mutant was caught. Exit 1 means at least one survived, and
the survivors are named. Exit 2 means the harness could not measure anything
and is saying so instead of printing a clean table.

## What it does NOT prove

It mutates two files. A regression that lives anywhere else -- a new money
query in another module, a value mangled after it leaves SQL -- is outside it.
And "caught" here means the gate file goes red; it says nothing about whether
the delivered number was right, which is what the 41 golden vectors are for.
"""

from __future__ import annotations

import argparse
import ast
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
API = REPO / "services/api"
REPOSITORY = API / "app/api/repository.py"
GATE = API / "tests/postgres/test_money_expressions_are_integer_postgres.py"

TRACKED = (
    "services/api/app/api/repository.py",
    "services/api/tests/postgres/test_money_expressions_are_integer_postgres.py",
)


class Refuse(Exception):
    """The harness cannot measure. Never downgraded to a warning."""


# --------------------------------------------------------------------------
# Finding the mutation sites, by reading the tree rather than by remembering
# --------------------------------------------------------------------------


def cast_sites(source: str) -> list[tuple[int, int, str, str]]:
    """Every `cast(<expr>, BigInteger)` call, as (start, end, original, inner).

    Offsets are absolute into `source` so a duplicated call text -- and there
    are several identical ones in `person_finance_summary` -- still addresses
    one site rather than the first match.
    """

    tree = ast.parse(source)
    line_start = [0]
    for line in source.splitlines(keepends=True):
        line_start.append(line_start[-1] + len(line))

    def offset(lineno: int, col: int) -> int:
        return line_start[lineno - 1] + col

    sites: list[tuple[int, int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "cast"):
            continue
        if len(node.args) != 2:
            continue
        second = node.args[1]
        if not (isinstance(second, ast.Name) and second.id == "BigInteger"):
            continue
        inner = node.args[0]
        sites.append(
            (
                offset(node.lineno, node.col_offset),
                offset(node.end_lineno, node.end_col_offset),
                ast.get_source_segment(source, node) or "",
                ast.get_source_segment(source, inner) or "",
            )
        )
    sites.sort()
    return sites


def surface_names() -> tuple[str, ...]:
    sys.path.insert(0, str(API))
    from tests.postgres.test_money_expressions_are_integer_postgres import (  # noqa: PLC0415
        MONEY_QUERY_SURFACE,
    )

    return tuple(MONEY_QUERY_SURFACE)


def drive_body_lines(source: str) -> tuple[int, int]:
    """The (first, last) 0-based line indices of `_drive_money_query_surface`.

    The docstring is skipped, not just filtered later: it names three of the
    four entry points in prose, and deleting a line of prose alongside a call
    would make the mutant two edits when the whole point is one.
    """

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name == "_drive_money_query_surface":
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]
            if not body:
                raise Refuse("_drive_money_query_surface has no statements")
            return body[0].lineno - 1, node.end_lineno - 1
    raise Refuse("_drive_money_query_surface not found in the gate file")


def drive_lines_for(source: str, name: str) -> list[int]:
    """0-based line indices inside the drive body that CALL `name`.

    `name(` and not `name`: the difference is what keeps a comment or a piece
    of prose out of the mutant.
    """

    first, last = drive_body_lines(source)
    lines = source.splitlines(keepends=True)
    return [
        index
        for index in range(first, last + 1)
        if f"{name}(" in lines[index] and not lines[index].lstrip().startswith("#")
    ]


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


def tree_is_clean() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain", "--", *TRACKED],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def restore() -> None:
    subprocess.run(["git", "checkout", "--", *TRACKED], cwd=REPO, check=True)
    dirty = tree_is_clean()
    if dirty:
        raise Refuse(f"khong khoi phuc duoc cay sau dot bien:\n{dirty}")


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
    options = parser.parse_args()

    if not options.database_url:
        print(
            "KHONG KIEM DUOC: chua co MOBILE_TEST_DATABASE_URL. Cong duoi do can "
            "PostgreSQL that; chay 'scripts/postgres_tier.sh --keep' de lay mot cai.",
            file=sys.stderr,
        )
        return 2

    # This harness measures a gate that arrives with PR #488. On a tree where
    # that PR has not landed the file is simply absent, and the honest answer
    # is "cannot measure" -- not an import traceback, and above all not an
    # empty table read as "nothing survived".
    if not GATE.exists():
        print(
            f"KHONG KIEM DUOC: khong co {GATE.relative_to(REPO)}. Cong nay den "
            "cung PR #488; checkout nhanh do roi chay lai.",
            file=sys.stderr,
        )
        return 2

    dirty = tree_is_clean()
    if dirty:
        print(
            "KHONG KIEM DUOC: hai file se bi dot bien dang co thay doi chua commit.\n"
            "Commit hoac stash truoc, neu khong ban sua cua ban se bi xoa:\n"
            f"{dirty}",
            file=sys.stderr,
        )
        return 2

    repository_source = REPOSITORY.read_text(encoding="utf-8")
    gate_source = GATE.read_text(encoding="utf-8")

    sites = cast_sites(repository_source)
    names = surface_names()
    if not sites:
        print(
            "KHONG KIEM DUOC: khong tim thay diem cast(..., BigInteger) nao trong "
            f"{REPOSITORY.relative_to(REPO)}. Danh sach nguon rong lam ca bang tu thao.",
            file=sys.stderr,
        )
        return 2
    if not names:
        print("KHONG KIEM DUOC: MONEY_QUERY_SURFACE rong.", file=sys.stderr)
        return 2

    drive_map = {name: drive_lines_for(gate_source, name) for name in names}
    print(f"tim thay {len(sites)} diem cast(..., BigInteger) trong repository.py")
    print(f"MONEY_QUERY_SURFACE co {len(names)} ten: {', '.join(names)}")
    for name, lines in drive_map.items():
        state = f"{len(lines)} dong goi" if lines else "KHONG CO DONG GOI NAO"
        print(f"  {name}: {state}")
    print()

    survivors: list[str] = []

    def measure(label: str) -> bool:
        code, summary = run_gate(options.database_url)
        caught = code != 0
        print(f"{label:<56} rc={code}  {summary:<34} -> {'BAT DUOC' if caught else 'LOT'}")
        if not caught:
            survivors.append(label)
        return caught

    # A mutation table run on an already-red tree cannot tell what is guarded
    # from what was broken before it started, so the baseline is a refusal
    # condition rather than a row.
    print("=== M0 nen ===")
    baseline_code, baseline_summary = run_gate(options.database_url)
    print(f"{'M0 khong dot bien (phai XANH)':<56} rc={baseline_code}  {baseline_summary}")
    if baseline_code != 0:
        print(
            "KHONG KIEM DUOC: nen da DO san. Bang dot bien tren mot cay do san "
            "khong phan biet duoc cai gi duoc gac.",
            file=sys.stderr,
        )
        return 2

    print(f"\n=== C1-C{len(sites)}: lui TUNG cast mot cai mot ===")
    for index, (start, end, original, inner) in enumerate(sites, start=1):
        mutated = repository_source[:start] + inner + repository_source[end:]
        REPOSITORY.write_text(mutated, encoding="utf-8")
        head = " ".join(original.split())[:58]
        measure(f"C{index} lui cast: {head}")
        restore()

    print(f"\n=== N1-N{len(names)}: bo TUNG ten khoi MONEY_QUERY_SURFACE ===")
    for index, name in enumerate(names, start=1):
        needle = f'    "{name}",\n'
        if needle not in gate_source:
            raise Refuse(f"khong tim thay muc surface cho {name}")
        GATE.write_text(gate_source.replace(needle, "", 1), encoding="utf-8")
        measure(f"N{index} surface thieu {name}")
        restore()

    print(f"\n=== D1-D{len(names)}: bo DONG GOI, GIU ten trong list ===")
    for index, name in enumerate(names, start=1):
        lines = drive_map[name]
        if not lines:
            print(f"D{index} {name}: khong co dong goi de bo -- da khong duoc lai san")
            survivors.append(f"D{index} {name} khong duoc lai san")
            continue
        source_lines = gate_source.splitlines(keepends=True)
        for line_index in reversed(lines):
            del source_lines[line_index]
        GATE.write_text("".join(source_lines), encoding="utf-8")
        measure(f"D{index} khong con lai {name} (ten van con trong list)")
        restore()

    print("\n=== P: bo dong goi VA lui cast that cua chinh no ===")
    # Pair a drive call with a cast whose enclosing function is that entry
    # point, so the mutant is "disarm the gate, then commit the regression it
    # was watching for" rather than two unrelated edits.
    enclosing = _cast_owners(repository_source)
    paired = 0
    for name in names:
        owned = [site for site, owner in zip(sites, enclosing, strict=True) if owner == name]
        lines = drive_map[name]
        if not owned or not lines:
            continue
        paired += 1
        start, end, original, inner = owned[0]
        source_lines = gate_source.splitlines(keepends=True)
        for line_index in reversed(lines):
            del source_lines[line_index]
        GATE.write_text("".join(source_lines), encoding="utf-8")
        REPOSITORY.write_text(
            repository_source[:start] + inner + repository_source[end:], encoding="utf-8"
        )
        measure(f"P khong lai {name} + lui 1 cast that cua no")
        restore()
    if paired == 0:
        print(
            "KHONG KIEM DUOC: khong ghep duoc cap nao (dong goi <-> cast cung ham).",
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


def _cast_owners(source: str) -> list[str | None]:
    """For each cast site, the name of the function that encloses it."""

    tree = ast.parse(source)
    spans: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            spans.append((node.lineno, node.end_lineno or node.lineno, node.name))
    line_start = [0]
    for line in source.splitlines(keepends=True):
        line_start.append(line_start[-1] + len(line))

    def line_of(offset: int) -> int:
        low, high = 0, len(line_start) - 1
        while low < high:
            mid = (low + high + 1) // 2
            if line_start[mid] <= offset:
                low = mid
            else:
                high = mid - 1
        return low + 1

    owners: list[str | None] = []
    for start, _end, _original, _inner in cast_sites(source):
        line = line_of(start)
        candidates = [name for first, last, name in spans if first <= line <= last]
        owners.append(candidates[-1] if candidates else None)
    return owners


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refuse as error:
        print(f"KHONG KIEM DUOC: {error}", file=sys.stderr)
        sys.exit(2)
