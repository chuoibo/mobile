"""Census every arithmetic operation in `app/` that could manufacture a non-int.

Why an AST and not a grep. The lesson this lane keeps relearning (#437, #450,
#460) is that a count is only worth the unit it is counted in: a person
copy-pasting code can rename a variable, reword a comment, or change an error
code, so any count anchored to those numbers is a count the copier controls.
`ast.Div` is not one of those. A `/` is a `/` whatever it is called and whatever
is written above it, so pass A below cannot be evaded by rewriting.

Three passes, deliberately of decreasing hardness:

  A. EVERY `ast.Div` under `app/`, with no money filter at all. True division is
     the only operator in Python that turns (int, int) into float, so if Law 1
     is broken by an operator it is broken here. The list is short enough to
     read by hand, which is the point: no heuristic gets to hide a row.

  B. Money-shaped `+ - * // % **` nodes. Softer, because "money-shaped" is a
     name heuristic and names are exactly what a copier can change. Pass B is
     a lead generator, not a gate.

  C. Money-shaped `sum/round/float/min/max/abs` calls, same caveat as B.

What this scanner does NOT prove: that the operands are ints at runtime. It
reads shape, not behaviour. `probe_phep_cong.py` next door does the behaviour
half, and neither substitutes for the other.

Run from `services/api`:

    python tests/qa/backend-100055-phep-cong-bill-104/quet_phep_tinh_tien.py
"""

from __future__ import annotations

import ast
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve()
API_ROOT = HERE.parents[3]
APP = API_ROOT / "app"

MONEY_HINTS = ("vnd", "amount", "total", "price", "cost", "tien", "money", "fee")

OPNAME = {
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mult: "*",
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mod: "%",
    ast.Pow: "**",
}

CALL_NAMES = frozenset({"sum", "round", "float", "min", "max", "abs", "Decimal"})


def _name_tokens(node: ast.AST) -> list[str]:
    """Every identifier-ish string reachable inside an expression."""
    tokens: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            tokens.append(sub.id)
        elif isinstance(sub, ast.Attribute):
            tokens.append(sub.attr)
        elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            tokens.append(sub.value)
        elif isinstance(sub, ast.arg):
            tokens.append(sub.arg)
    return tokens


def _is_moneyish(node: ast.AST) -> bool:
    return any(
        hint in tok.lower() for tok in _name_tokens(node) for hint in MONEY_HINTS
    )


def _rel(path: pathlib.Path) -> str:
    return str(path.relative_to(API_ROOT))


def scan() -> tuple[list, list, list]:
    divs: list[tuple[str, int, bool, str]] = []
    arith: list[tuple[str, int, str, str]] = []
    calls: list[tuple[str, int, str, str]] = []

    for path in sorted(APP.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        tree = ast.parse(source, filename=str(path))
        seen: set[tuple[str, int, str]] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp | ast.AugAssign):
                op = type(node.op)
                text = lines[node.lineno - 1].strip()
                key = (_rel(path), node.lineno, OPNAME.get(op, "?"))
                if key in seen:
                    continue
                seen.add(key)
                if op is ast.Div:
                    divs.append((_rel(path), node.lineno, _is_moneyish(node), text))
                elif op in OPNAME and _is_moneyish(node):
                    arith.append((_rel(path), node.lineno, OPNAME[op], text))
            elif isinstance(node, ast.Call):
                func = node.func
                name = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr
                    if isinstance(func, ast.Attribute)
                    else ""
                )
                if name in CALL_NAMES and _is_moneyish(node):
                    key = (_rel(path), node.lineno, name)
                    if key in seen:
                        continue
                    seen.add(key)
                    calls.append(
                        (_rel(path), node.lineno, name, lines[node.lineno - 1].strip())
                    )

    return divs, arith, calls


def main() -> int:
    divs, arith, calls = scan()

    money_divs = [row for row in divs if row[2]]
    print("=" * 78)
    print(f"PASS A -- every ast.Div under app/: {len(divs)}")
    print(f"         of which money-shaped:     {len(money_divs)}")
    print("=" * 78)
    for path, lineno, moneyish, text in divs:
        print(f"  {'MONEY?' if moneyish else '      '} {path}:{lineno}: {text}")

    print()
    print("=" * 78)
    print(f"PASS B -- money-shaped + - * // % ** : {len(arith)}")
    print("=" * 78)
    for path, lineno, op, text in arith:
        print(f"  [{op:>2}] {path}:{lineno}: {text}")

    print()
    print("=" * 78)
    print(f"PASS C -- money-shaped {'/'.join(sorted(CALL_NAMES))}: {len(calls)}")
    print("=" * 78)
    for path, lineno, name, text in calls:
        print(f"  [{name}] {path}:{lineno}: {text}")

    print()
    print("Blind spots of this scanner, stated so nobody reads a 0 as safety:")
    print("  - pass A is complete for `/` written as `/`; it does not see")
    print("    operator.truediv, __truediv__, or a division done inside a library.")
    print("  - passes B and C filter on NAMES, which a copier can change.")
    print("  - none of the three prove an operand is an int at runtime.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
