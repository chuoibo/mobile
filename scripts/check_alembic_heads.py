#!/usr/bin/env python3
"""Refuse a migration tree that has more than one head.

## Why this exists

Two branches added a migration in the same afternoon. Both hung off the same
parent, because both were cut from a `main` where that parent was the tip.
Neither author did anything visibly wrong, and neither branch was broken on its
own -- but together they made two alembic heads, and `alembic upgrade head`
picked one.

The database that ran it was a shared one. It ended up stamped with a revision
that lived on a branch nobody had merged, missing every table from the other
fork, and `alembic upgrade head` on it failed from then on. Rebuilding it was
the only way out, because the schema had genuinely diverged -- re-stamping a
number would only have moved the lie.

The tell was available the whole time and nobody was looking at it: the tree had
two heads. That is a property of the files in the repository, needs no database,
and takes milliseconds to check. So it is checked here.

## Why this reads the files instead of asking alembic

The first version of this script used `ScriptDirectory.from_config`, which
imports each version module. That made it wrong in a way a guard must never be:
run it, edit a `down_revision`, run it again, and it reported the OLD value from
a cached `.pyc` in `__pycache__`. It was caught here only because the fix was
tested for going green as well as for going red -- a guard trusted after one red
would have shipped reporting stale answers, including a green on a forked tree.

Reading `revision` and `down_revision` out of the source with `ast` has no
import step, so there is no bytecode to go stale, no module-level side effects,
and no dependency on alembic being installed at all.

## What this does and does not prove

It proves the migration files in THIS tree form one chain. It says nothing about
what any database has been stamped with -- a database can still be ahead, behind
or off on a revision this tree has never heard of. That is a different check
against a live server, and this one deliberately needs no connection so it can
run in a hook, in CI, and on a laptop with nothing started.

Exit 0 when there is exactly one head, 1 otherwise.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSIONS_DIR = (
    REPO_ROOT / "services" / "api" / "app" / "db" / "migrations" / "versions"
)


def _literal(node: ast.AST) -> object:
    """The value of an assignment, or None when it is not a plain literal."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None


def doc_migrations(versions_dir: Path) -> dict[str, dict]:
    """Map revision -> {down, doc, file} for every version file."""
    found: dict[str, dict] = {}
    for path in sorted(versions_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        revision = None
        down = None
        for node in tree.body:
            # Both `x = "..."` and `x: str = "..."` appear in this tree.
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                name, value = node.target.id, node.value
            elif (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                name, value = node.targets[0].id, node.value
            else:
                continue
            if value is None:
                continue
            if name == "revision":
                revision = _literal(value)
            elif name == "down_revision":
                down = _literal(value)
        if isinstance(revision, str):
            found[revision] = {
                "down": down,
                "doc": (ast.get_docstring(tree) or "").split("\n")[0],
                "file": path.name,
            }
    return found


def main() -> int:
    if not VERSIONS_DIR.is_dir():
        print(f"check_alembic_heads: khong thay {VERSIONS_DIR}", file=sys.stderr)
        return 1

    migrations = doc_migrations(VERSIONS_DIR)
    if not migrations:
        print("check_alembic_heads: khong co migration nao.", file=sys.stderr)
        return 1

    # A head is a revision nothing else points down to. `down_revision` may be
    # a tuple on a merge revision, which is a legitimate way to have one head
    # again after a fork -- so every element counts as a parent.
    parents: set[str] = set()
    for meta in migrations.values():
        down = meta["down"]
        if isinstance(down, str):
            parents.add(down)
        elif isinstance(down, (tuple, list)):
            parents.update(x for x in down if isinstance(x, str))

    heads = sorted(set(migrations) - parents)

    if len(heads) == 1:
        print(f"Alembic guard: mot head duy nhat ({heads[0]}).")
        return 0

    print(f"Alembic guard: {len(heads)} head, phai co dung 1.", file=sys.stderr)
    print("", file=sys.stderr)
    for head in heads:
        meta = migrations[head]
        print(f"  {head}  <- {meta['down']}   [{meta['file']}]", file=sys.stderr)
        print(f"      {meta['doc']}", file=sys.stderr)
    print("", file=sys.stderr)
    print(
        "Hai migration cung treo duoi mot cha. `alembic upgrade head` se chon\n"
        "MOT nhanh, va database chay no se thieu bang cua nhanh kia -- roi bi\n"
        "dong dau mot revision khong nhanh nao giu.\n"
        "\n"
        "Sua: tro `down_revision` cua migration moi hon sang head kia, dung\n"
        "de hai cai cung tro vao mot cho.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
