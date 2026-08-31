"""Machine census of every place a money value can be written to the database.

The question this answers: after #450 closed ``allocate()`` to float/bool, is
there any OTHER door through which a non-int money value reaches a ``*_vnd``
column?  ``allocate()`` guards the split.  It does not, by itself, guard the
INSERT.

Denominator = every construction of a money-carrying ORM model, every
``insert()``/``update()``/``values()`` naming a money column, and every raw SQL
string naming one, across the whole repository -- app, migrations, scripts,
tests, tools.  Counting only ``app/`` would hide seeds and fixtures, which is
exactly what the question asks about.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys


def _repo_root() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    raise SystemExit("cannot locate repo root (.git)")


REPO = _repo_root()
API = REPO / "services" / "api"

# Money-carrying ORM classes, derived from models.py -- not hand-listed, so a
# new money table cannot be silently missed.
MODELS = API / "app" / "db" / "models.py"


def money_classes() -> dict[str, tuple[str | None, list[str]]]:
    tree = ast.parse(MODELS.read_text())
    out: dict[str, tuple[str | None, list[str]]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        cols: list[str] = []
        table: str | None = None
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                if stmt.target.id.endswith("_vnd"):
                    cols.append(stmt.target.id)
            if isinstance(stmt, ast.Assign) and any(
                getattr(t, "id", "") == "__tablename__" for t in stmt.targets
            ):
                table = getattr(stmt.value, "value", None)
        if cols:
            out[node.name] = (table, cols)
    return out


CLASSES = money_classes()
TABLES = {t for t, _ in CLASSES.values() if t}
COLUMNS = sorted({c for _, cols in CLASSES.values() for c in cols})

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "phase0"}

# This scanner's own directory. The probe next door constructs ExpenseVersion,
# ExpenseItem and Bill with money kwargs against a real database, so leaving it
# in makes the census grow by six the moment the census is written -- a number
# that moves when nothing about the product moved. Excluded and counted aloud
# rather than filtered silently.
SELF_DIR = pathlib.Path(__file__).resolve().parent


def py_files(include_self: bool = False) -> list[pathlib.Path]:
    files = []
    for p in REPO.rglob("*.py"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if not include_self and p.resolve().parent == SELF_DIR:
            continue
        files.append(p)
    return sorted(files)


SQL_WRITE = re.compile(r"\b(insert\s+into|update)\b", re.IGNORECASE | re.DOTALL)


class Visitor(ast.NodeVisitor):
    def __init__(self, path: pathlib.Path) -> None:
        self.path = path
        self.hits: list[dict] = []

    def _add(self, node: ast.AST, kind: str, target: str, detail: str = "") -> None:
        self.hits.append(
            {
                "file": str(self.path.relative_to(REPO)),
                "line": getattr(node, "lineno", 0),
                "kind": kind,
                "target": target,
                "detail": detail,
            }
        )

    def visit_Call(self, node: ast.Call) -> None:
        name = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr

        # 1. ORM model construction, e.g. ExpenseVersion(total_amount_vnd=...)
        if name in CLASSES:
            kwargs = {k.arg for k in node.keywords if k.arg}
            money_kwargs = sorted(kwargs & set(CLASSES[name][1]))
            self._add(
                node,
                "orm_construct",
                name,
                ",".join(money_kwargs) or "(no money kwarg -- default/attr-set)",
            )

        # 2. Core insert()/update()/values() naming a money column
        if name in {"insert", "update", "values", "bindparam"}:
            for kw in node.keywords:
                if kw.arg and kw.arg.endswith("_vnd"):
                    self._add(node, f"core_{name}", kw.arg)
            for arg in node.args:
                if isinstance(arg, ast.Name) and arg.id in CLASSES:
                    self._add(node, f"core_{name}", arg.id)

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # 4. Attribute assignment on a live ORM row, e.g. row.amount_vnd = x.
        # Constructor-only counting is blind to this shape; a mutation after
        # load writes just as hard as an INSERT.
        for target in node.targets:
            if isinstance(target, ast.Attribute) and target.attr.endswith("_vnd"):
                self._add(node, "attr_assign", target.attr)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        t = node.target
        if isinstance(t, ast.Attribute) and t.attr.endswith("_vnd"):
            self._add(node, "attr_augassign", t.attr)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        # 3. Raw SQL naming a money column inside an INSERT/UPDATE
        if isinstance(node.value, str) and SQL_WRITE.search(node.value):
            named = [c for c in COLUMNS if c in node.value]
            named += [t for t in TABLES if t in node.value]
            if named:
                self._add(node, "raw_sql", ",".join(sorted(set(named)))[:120])
        self.generic_visit(node)


def main() -> int:
    all_hits: list[dict] = []
    for path in py_files():
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        v = Visitor(path)
        v.visit(tree)
        all_hits.extend(v.hits)

    if len(CLASSES) == 0 or len(COLUMNS) == 0:
        print(
            "FAIL: derived zero money classes/columns -- scanner is blind",
            file=sys.stderr,
        )
        return 2

    buckets: dict[str, list[dict]] = {}
    for h in all_hits:
        f = h["file"]
        if "/migrations/versions/" in f:
            b = "migration"
        elif f.startswith("services/api/tests/") or "/tests/" in f:
            b = "test/fixture"
        elif f.startswith("scripts/") or "/scripts/" in f:
            b = "script/seed"
        elif f.startswith("services/api/app/db/"):
            b = "app:db-layer"
        elif f.startswith("services/api/app/api/"):
            b = "app:api-layer"
        else:
            b = "other"
        buckets.setdefault(b, []).append(h)

    if "--json" in sys.argv:
        print(json.dumps(all_hits, indent=2, ensure_ascii=False))
        return 0

    print(f"money-carrying ORM classes : {len(CLASSES)}")
    print(f"money columns              : {len(COLUMNS)} -> {COLUMNS}")
    print(f"python files scanned       : {len(py_files())}")
    print(
        f"  (excluded this probe's own directory: "
        f"{len(py_files(include_self=True)) - len(py_files())} file(s))"
    )
    print(f"TOTAL write sites found    : {len(all_hits)}")
    print()
    for b in sorted(buckets, key=lambda k: -len(buckets[k])):
        print(f"  {b:16s} {len(buckets[b]):4d}")
    print()

    for b in sorted(buckets, key=lambda k: -len(buckets[k])):
        print(f"### {b}")
        for h in sorted(buckets[b], key=lambda h: (h["file"], h["line"])):
            print(
                f"  {h['file']}:{h['line']} [{h['kind']}] {h['target']} {h['detail']}"
            )
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
