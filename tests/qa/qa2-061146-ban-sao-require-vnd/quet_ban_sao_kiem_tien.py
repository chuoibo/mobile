"""Shape-based scan for hand-rolled copies of the single money validator.

Counts by SHAPE, never by function name, because a copy that got renamed or
inlined is exactly the copy a name-based count cannot see.

Three axes, each collected blind and classified afterwards:

  A  int-ness guard   isinstance(X, int) / type(X) is int  (incl. bool exclusion)
  B  sign guard       X < 0 / X <= 0 / X > 0 / X == 0
  C  money raise      raise ...("<CODE>") where CODE is in the money vocabulary

Axis C's vocabulary is DISCOVERED from the tree, not assumed, so an "equivalent"
code nobody told us about still shows up.
"""

from __future__ import annotations

import ast
import json
import pathlib
import sys

APP = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "services/api/app")

# Tokens that make a raised string code look like a money-validation code.
# Used to DISCOVER the vocabulary, not to gate the scan.
CODE_TOKENS = (
    "AMOUNT",
    "INTEGER",
    "INT",
    "NEGATIVE",
    "POSITIVE",
    "MONEY",
    "VND",
    "TOTAL",
    "PRICE",
    "NUMERIC",
    "FLOAT",
    "DECIMAL",
)

# Tokens that make an EXPRESSION look like it holds money.
MONEY_TOKENS = (
    "_vnd",
    "vnd",
    "amount",
    "total",
    "price",
    "cost",
    "fee",
    "balance",
    "paid",
    "owed",
    "share",
    "subtotal",
    "tip",
    "discount",
    "surcharge",
    "budget",
    "limit_",
)


def src(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover - unparse covers every node we hit
        return "<?>"


def looks_like_money(expr: str) -> bool:
    low = expr.lower()
    return any(tok in low for tok in MONEY_TOKENS)


class Enclosing:
    """Map each node to the innermost function that contains it."""

    def __init__(self, tree: ast.AST):
        self.owner: dict[int, str] = {}
        self.calls: dict[str, set[str]] = {}
        self._walk(tree, "<module>")

    def _walk(self, node, fn: str):
        for child in ast.iter_child_nodes(node):
            name = fn
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = child.name
            self.owner[id(child)] = name
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                self.calls.setdefault(name, set()).add(child.func.id)
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                self.calls.setdefault(name, set()).add(child.func.attr)
            self._walk(child, name)


def scan_file(path: pathlib.Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    enc = Enclosing(tree)
    hits: list[dict] = []

    def owner(node) -> str:
        return enc.owner.get(id(node), "<module>")

    for node in ast.walk(tree):
        # --- Axis A: int-ness guard -------------------------------------
        if isinstance(node, ast.Call):
            f = node.func
            is_isinstance = isinstance(f, ast.Name) and f.id == "isinstance"
            if is_isinstance and len(node.args) == 2:
                subject = src(node.args[0])
                classes = src(node.args[1])
                if "int" in classes or "bool" in classes or "float" in classes:
                    hits.append(
                        {
                            "axis": "A-isinstance",
                            "line": node.lineno,
                            "fn": owner(node),
                            "subject": subject,
                            "detail": classes,
                        }
                    )
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Call):
            f = node.left.func
            if isinstance(f, ast.Name) and f.id == "type" and node.left.args:
                rhs = " ".join(src(c) for c in node.comparators)
                if "int" in rhs or "float" in rhs:
                    hits.append(
                        {
                            "axis": "A-type-is",
                            "line": node.lineno,
                            "fn": owner(node),
                            "subject": src(node.left.args[0]),
                            "detail": rhs,
                        }
                    )

        # --- Axis B: sign guard against literal zero ---------------------
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            op = node.ops[0]
            rhs = node.comparators[0]
            if isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)):
                zero_right = isinstance(rhs, ast.Constant) and rhs.value == 0
                zero_left = isinstance(node.left, ast.Constant) and node.left.value == 0
                if zero_right or zero_left:
                    subject = src(rhs if zero_left else node.left)
                    hits.append(
                        {
                            "axis": "B-sign",
                            "line": node.lineno,
                            "fn": owner(node),
                            "subject": subject,
                            "detail": src(node),
                        }
                    )

        # --- Axis C: raise carrying a string code ------------------------
        if isinstance(node, ast.Raise) and node.exc is not None:
            codes = [
                n.value
                for n in ast.walk(node.exc)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
            ]
            for code in codes:
                if any(tok in code.upper() for tok in CODE_TOKENS):
                    hits.append(
                        {
                            "axis": "C-raise",
                            "line": node.lineno,
                            "fn": owner(node),
                            "subject": code,
                            "detail": src(node.exc)[:80],
                        }
                    )

    for h in hits:
        h["file"] = str(path)
        h["calls_require_vnd"] = "require_vnd" in enc.calls.get(h["fn"], set())
        h["money_ish"] = looks_like_money(h["subject"])
    return hits


def main() -> int:
    all_hits: list[dict] = []
    for path in sorted(APP.rglob("*.py")):
        all_hits.extend(scan_file(path))

    if "--json" in sys.argv:
        print(json.dumps(all_hits, ensure_ascii=False, indent=1))
        return 0

    # The discovered vocabulary. Printed because assuming it is how a scan
    # goes blind: three of the copies below use a code nobody would guess.
    codes = sorted({h["subject"] for h in all_hits if h["axis"] == "C-raise"})
    print(f"=== ma loi tien phat hien duoc trong cay ({len(codes)}) ===")
    for code in codes:
        print(f"  {code}")

    # A validator site is any function carrying BOTH an int-ness guard and
    # either a sign guard or a money raise -- require_vnd's shape, whatever
    # the function ended up being called.
    by_fn: dict[tuple[str, str], list[dict]] = {}
    for hit in all_hits:
        by_fn.setdefault((hit["file"], hit["fn"]), []).append(hit)

    sites = []
    for (path, fn), hits in sorted(by_fn.items()):
        axes = {h["axis"] for h in hits}
        if not ({"A-isinstance", "A-type-is"} & axes):
            continue
        if not ({"B-sign", "C-raise"} & axes):
            continue
        sites.append((path, fn, hits))

    print(f"\n=== ung vien mang HINH DANG cua require_vnd ({len(sites)}) ===")
    for path, fn, hits in sites:
        calls = hits[0]["calls_require_vnd"]
        line = min(h["line"] for h in hits)
        via = "goi require_vnd" if calls else "TU KIEM"
        print(f"  {path}:{line} {fn}()  [{via}]")

    print(f"\ntong hit theo truc: {len(all_hits)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
