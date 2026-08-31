"""Derive, from the code itself, every SOURCE a money value reaches `allocate()` from.

The call-site axis was counted first and answered 3 (service.py 3624, 3636, 3754).
This is the other axis. A call site is a place the allocator is *invoked*; a source
is a place a money value is *created*. One call site can stand on several sources,
and two call sites can share one.

Nothing here is hand-written, because a hand-written list cannot notice the tenth
entry. Three anchors, in order, each derived from the previous one:

  1. the money SLOT NAMES are read out of `allocator.py`'s own subscripts -- whoever
     copies allocator code cannot rename `expense["total_vnd"]` and still be read by
     the allocator, so this anchor survives a copy;
  2. the PRODUCERS are every dict literal in `app/` that binds one of those slots and
     sits on a path the allocator is reached from;
  3. the BARRIER family (`MoneyVnd` and relatives) is read out of `schemas.py` as
     "module-level Annotated[int, Field(strict=True, ...)]", not by name, so a fourth
     alias added tomorrow is counted without editing this file.

A shape this file cannot classify is reported as UNRESOLVED and exits non-zero. An
empty answer is a failure of the scanner, never a clean bill of health.
"""

from __future__ import annotations

import ast
import pathlib
import sys

API_ROOT = pathlib.Path(__file__).resolve().parents[3]
APP = API_ROOT / "app"
SCHEMAS = APP / "api" / "schemas.py"
REPOSITORY = APP / "api" / "repository.py"
ALLOCATOR = APP / "domain" / "allocator.py"


# --------------------------------------------------------------------------
# module index
# --------------------------------------------------------------------------


class Module:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self.source = path.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    @property
    def rel(self) -> str:
        return str(self.path.relative_to(API_ROOT))

    def segment(self, node: ast.AST) -> str:
        return ast.get_source_segment(self.source, node) or ast.dump(node)


MODULES = {path: Module(path) for path in sorted(APP.rglob("*.py"))}


def _functions(module: Module):
    for node in ast.walk(module.tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node


FUNCTIONS: dict[str, list[tuple[Module, ast.FunctionDef]]] = {}
for _module in MODULES.values():
    for _function in _functions(_module):
        FUNCTIONS.setdefault(_function.name, []).append((_module, _function))


def _classes(module: Module):
    for node in module.tree.body:
        if isinstance(node, ast.ClassDef):
            yield node


def _field_annotations(module: Module) -> dict[str, dict[str, str]]:
    """class name -> field name -> annotation source text."""
    out: dict[str, dict[str, str]] = {}
    for klass in _classes(module):
        fields: dict[str, str] = {}
        for statement in klass.body:
            if isinstance(statement, ast.AnnAssign) and isinstance(
                statement.target, ast.Name
            ):
                fields[statement.target.id] = module.segment(statement.annotation)
        out[klass.name] = fields
    return out


SCHEMA_FIELDS = _field_annotations(MODULES[SCHEMAS])
RECORD_FIELDS = _field_annotations(MODULES[REPOSITORY])


# --------------------------------------------------------------------------
# anchor 1 -- the money slots the allocator itself reads
# --------------------------------------------------------------------------


def money_slots() -> set[str]:
    module = MODULES[ALLOCATOR]
    keys = set()
    for node in ast.walk(module.tree):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            key = node.slice.value
            if isinstance(key, str) and key.endswith("_vnd"):
                keys.add(key)
    return keys


# --------------------------------------------------------------------------
# anchor 3 -- the strict-int barrier family, read out of schemas.py
# --------------------------------------------------------------------------


def barrier_aliases() -> set[str]:
    """Module-level `X = Annotated[int, Field(strict=True, ...)]` in schemas.py."""
    module = MODULES[SCHEMAS]
    aliases = set()
    for statement in module.tree.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = statement.value
        if not (
            isinstance(value, ast.Subscript)
            and isinstance(value.value, ast.Name)
            and value.value.id == "Annotated"
            and isinstance(value.slice, ast.Tuple)
            and value.slice.elts
            and isinstance(value.slice.elts[0], ast.Name)
            and value.slice.elts[0].id == "int"
        ):
            continue
        for element in value.slice.elts[1:]:
            if isinstance(element, ast.Call) and any(
                keyword.arg == "strict"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in element.keywords
            ):
                aliases.add(target.id)
    return aliases


# --------------------------------------------------------------------------
# anchor 2 -- producers on a path the allocator is reached from
# --------------------------------------------------------------------------


def _called_names(function: ast.FunctionDef) -> set[str]:
    names = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Call):
            callee = node.func
            if isinstance(callee, ast.Name):
                names.add(callee.id)
            elif isinstance(callee, ast.Attribute):
                names.add(callee.attr)
    return names


def call_site_functions() -> list[tuple[Module, ast.FunctionDef]]:
    """Functions in app/ whose body calls `allocate(...)` directly."""
    sites = []
    for module in MODULES.values():
        if module.path == ALLOCATOR:
            continue
        for function in _functions(module):
            for node in ast.walk(function):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "allocate"
                ):
                    sites.append((module, function, node))
    return sites


def reachable_functions(seeds: list[str]) -> set[str]:
    """Transitive callees of the seed functions, by simple name."""
    seen: set[str] = set()
    frontier = list(seeds)
    while frontier:
        name = frontier.pop()
        if name in seen:
            continue
        seen.add(name)
        for _module, function in FUNCTIONS.get(name, []):
            frontier.extend(_called_names(function))
    return seen


def producers(slots: set[str], reachable: set[str]):
    """Every dict literal binding a money slot, inside a reachable function."""
    found = []
    for module in MODULES.values():
        for function in _functions(module):
            if function.name not in reachable:
                continue
            for node in ast.walk(function):
                if not isinstance(node, ast.Dict):
                    continue
                for key, value in zip(node.keys, node.values, strict=True):
                    if (
                        isinstance(key, ast.Constant)
                        and isinstance(key.value, str)
                        and key.value in slots
                    ):
                        found.append((module, function, key.value, value))
    return found


# --------------------------------------------------------------------------
# classification -- by AST shape, never by name
# --------------------------------------------------------------------------


def _element_type(annotation: str) -> str:
    text = annotation.strip()
    for prefix in ("list[", "Sequence[", "tuple["):
        if text.startswith(prefix) and text.endswith("]"):
            return text[len(prefix) : -1].split(",")[0].strip()
    return text


def _strip_optional(annotation: str) -> str:
    return annotation.split("|")[0].strip()


def _binding_of(name: str, function: ast.FunctionDef):
    """Return ('param', annotation) | ('assign', expr) | ('iter', expr) | None."""
    for argument in (
        function.args.posonlyargs + function.args.args + function.args.kwonlyargs
    ):
        if argument.arg == name and argument.annotation is not None:
            return ("param", argument.annotation)
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == name:
                return ("assign", node.value)
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            if node.target.id == name:
                return ("iter", node.iter)
        if isinstance(node, ast.comprehension) and isinstance(node.target, ast.Name):
            if node.target.id == name:
                return ("iter", node.iter)
    return None


def _return_annotation(name: str) -> str | None:
    for module, function in FUNCTIONS.get(name, []):
        if function.returns is not None:
            return module.segment(function.returns)
    return None


def type_of(expr: ast.AST, module: Module, function: ast.FunctionDef) -> str | None:
    """Best-effort static type name of `expr`, or None."""
    if isinstance(expr, ast.Name):
        binding = _binding_of(expr.id, function)
        if binding is None:
            return None
        kind, node = binding
        if kind == "param":
            return _strip_optional(module.segment(node))
        if kind == "assign":
            return type_of(node, module, function)
        return _element_type(type_of(node, module, function) or "")
    if isinstance(expr, ast.Attribute):
        owner = type_of(expr.value, module, function)
        if owner is None:
            return None
        for table in (SCHEMA_FIELDS, RECORD_FIELDS):
            if owner in table and expr.attr in table[owner]:
                return table[owner][expr.attr]
        return None
    if isinstance(expr, ast.Call):
        callee = expr.func
        name = (
            callee.attr
            if isinstance(callee, ast.Attribute)
            else callee.id
            if isinstance(callee, ast.Name)
            else None
        )
        if name is None:
            return None
        return _strip_optional(_return_annotation(name) or "") or None
    return None


def _dict_path(expr: ast.AST, function: ast.FunctionDef):
    """Reduce `bill["items"]`-style access to (root parameter, path)."""
    if isinstance(expr, ast.Subscript) and isinstance(expr.slice, ast.Constant):
        inner = _dict_path(expr.value, function)
        if inner is None:
            return None
        root, path = inner
        return root, path + (expr.slice.value,)
    if isinstance(expr, ast.Name):
        binding = _binding_of(expr.id, function)
        if binding is None:
            return None
        kind, node = binding
        if kind == "param":
            return expr.id, ()
        if kind == "iter":
            inner = _dict_path(node, function)
            if inner is None:
                return None
            root, path = inner
            return root, path + ("*",)
        return _dict_path(node, function)
    if isinstance(expr, ast.Call) and expr.args:
        # `_by_key(items)` and `list(items)` reorder or copy; neither changes
        # which dict a money value came out of.
        return _dict_path(expr.args[0], function)
    return None


def _walk_literal(node: ast.AST, path: tuple):
    """Follow a path like ('items', '*', 'amount_vnd') into a dict/list literal."""
    if not path:
        return node
    head, rest = path[0], path[1:]
    if head == "*":
        if isinstance(node, ast.ListComp):
            return _walk_literal(node.elt, rest)
        if isinstance(node, ast.List | ast.Tuple) and node.elts:
            return _walk_literal(node.elts[0], rest)
        if isinstance(node, ast.Call) and node.args:
            return _walk_literal(node.args[0], path)
        return None
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values, strict=True):
            if isinstance(key, ast.Constant) and key.value == head:
                return _walk_literal(value, rest)
    return None


def _callers_of(function_name: str):
    for module in MODULES.values():
        for function in _functions(module):
            for node in ast.walk(function):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == function_name
                ):
                    yield module, function, node


class Source:
    def __init__(self, slot, origin, module, node, expr_text, barrier, note=""):
        self.slot = slot
        self.origin = origin
        self.where = f"{module.rel}:{node.lineno}"
        self.expr = expr_text
        self.barrier = barrier
        self.note = note


def classify(
    slot: str,
    expr: ast.AST,
    module: Module,
    function: ast.FunctionDef,
    barriers: set[str],
    depth: int = 0,
) -> list[Source]:
    """Resolve one money-slot value expression back to its origin(s)."""
    if depth > 4:
        return [Source(slot, "UNRESOLVED", module, expr, module.segment(expr), "-")]

    # A local name with more than one assignment is more than one source.
    if isinstance(expr, ast.Name):
        binding = _binding_of(expr.id, function)
        if binding is not None and binding[0] == "assign":
            assignments = [
                node.value
                for node in ast.walk(function)
                if isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == expr.id
            ]
            out: list[Source] = []
            for assignment in assignments:
                out.extend(
                    classify(slot, assignment, module, function, barriers, depth + 1)
                )
            return out

    if isinstance(expr, ast.BinOp) or (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == "sum"
    ):
        return [
            Source(
                slot,
                "COMPUTED",
                module,
                expr,
                module.segment(expr),
                "không có",
                "cộng trừ trong domain; kiểu kế thừa từ các số hạng",
            )
        ]

    if isinstance(expr, ast.Attribute):
        owner = type_of(expr.value, module, function)
        annotation = None
        if owner in SCHEMA_FIELDS:
            annotation = SCHEMA_FIELDS[owner].get(expr.attr)
            crosses = annotation in barriers if annotation else False
            return [
                Source(
                    slot,
                    "PYDANTIC",
                    module,
                    expr,
                    module.segment(expr),
                    annotation if crosses else f"KHÔNG ({annotation})",
                    f"{owner}.{expr.attr}",
                )
            ]
        if owner in RECORD_FIELDS:
            annotation = RECORD_FIELDS[owner].get(expr.attr)
            return [
                Source(
                    slot,
                    "DB_RECORD",
                    module,
                    expr,
                    module.segment(expr),
                    "không có",
                    f"{owner}.{expr.attr}: {annotation} (dataclass, không kiểm khi đọc)",
                )
            ]

    if isinstance(expr, ast.Subscript):
        reduced = _dict_path(expr, function)
        if reduced is not None:
            root, path = reduced
            parameters = [
                argument.arg
                for argument in function.args.posonlyargs + function.args.args
            ]
            if root in parameters:
                index = parameters.index(root)
                out = []
                for caller_module, caller_function, call in _callers_of(function.name):
                    if index >= len(call.args):
                        continue
                    literal = _walk_literal(call.args[index], path)
                    if literal is None:
                        continue
                    out.extend(
                        classify(
                            slot,
                            literal,
                            caller_module,
                            caller_function,
                            barriers,
                            depth + 1,
                        )
                    )
                if out:
                    return out

    return [Source(slot, "UNRESOLVED", module, expr, module.segment(expr), "-")]


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------


def main() -> int:
    problems: list[str] = []

    slots = money_slots()
    print("=" * 78)
    print("NGUỒN CỦA MỘT SỐ TIỀN ĐI VÀO allocate() — suy ra từ code, không viết tay")
    print("=" * 78)
    print()
    print(
        f"[1] Ô tiền allocator TỰ đọc (subscript hằng chuỗi *_vnd trong {ALLOCATOR.name}):"
    )
    for slot in sorted(slots):
        print(f"      {slot}")
    print(f"    → {len(slots)} ô")
    if not slots:
        problems.append("tập ô tiền RỖNG — máy quét hỏng, không phải code sạch")

    barriers = barrier_aliases()
    print()
    print(
        "[2] Họ rào strict trong schemas.py (Annotated[int, Field(strict=True, ...)]):"
    )
    for alias in sorted(barriers):
        print(f"      {alias}")
    print(f"    → {len(barriers)} bí danh")
    if not barriers:
        problems.append("không tìm thấy bí danh rào nào trong schemas.py")

    sites = call_site_functions()
    print()
    print("[3] Call site của allocate() trong app/:")
    for module, function, node in sites:
        print(f"      {module.rel}:{node.lineno}  trong {function.name}()")
    print(f"    → {len(sites)} call site")
    if not sites:
        problems.append("không tìm thấy lời gọi allocate() nào trong app/")

    reachable = reachable_functions([function.name for _m, function, _n in sites])
    found = producers(slots, reachable)
    print()
    print(
        f"[4] Producer (dict literal buộc một ô tiền, trong hàm tới được allocate): {len(found)}"
    )

    resolved: list[Source] = []
    for module, function, slot, value in found:
        resolved.extend(classify(slot, value, module, function, barriers))

    # A passthrough is a relay, not a second source. `bill.py` re-binds a value
    # that `service.py` already bound, so both producers resolve to one origin
    # and must be counted once -- otherwise the length of the chain, not the
    # number of ways money enters, would set the number.
    sources: list[Source] = []
    seen: set[tuple[str, str, str, str]] = set()
    for source in resolved:
        key = (source.slot, source.origin, source.where, source.expr)
        if key in seen:
            continue
        seen.add(key)
        sources.append(source)
    print(f"    trong đó {len(resolved) - len(sources)} là RELAY của một nguồn khác")

    print()
    print("[5] BẢNG NGUỒN")
    print("-" * 78)
    header = f"{'ô tiền':<12} {'gốc':<12} {'ở đâu':<28} biểu thức"
    print(header)
    print("-" * 78)
    for source in sorted(sources, key=lambda s: (s.origin, s.where)):
        print(f"{source.slot:<12} {source.origin:<12} {source.where:<28} {source.expr}")
        print(f"{'':<12} {'rào:':<12} {source.barrier}")
        if source.note:
            print(f"{'':<12} {'':<12} {source.note}")
    print("-" * 78)

    crossed = [
        s
        for s in sources
        if s.origin == "PYDANTIC" and not s.barrier.startswith("KHÔNG")
    ]
    unresolved = [s for s in sources if s.origin == "UNRESOLVED"]
    print()
    print(f"TỔNG: {len(sources)} nguồn")
    print(f"  đi qua họ rào strict : {len(crossed)}")
    print(f"  KHÔNG đi qua         : {len(sources) - len(crossed)}")
    for origin in sorted({s.origin for s in sources}):
        print(f"    {origin:<14} {len([s for s in sources if s.origin == origin])}")
    print()
    print(f"HAI TRỤC: call site = {len(sites)}   ·   nguồn = {len(sources)}")

    if unresolved:
        problems.append(
            f"{len(unresolved)} biểu thức không phân loại được — "
            "hình dạng mới, máy quét phải được dạy chứ không được đếm thiếu im lặng"
        )
    for module, _function, node in sites:
        argument = node.args[0] if node.args else None
        if argument is None:
            problems.append(
                f"allocate() không có đối số tại {module.rel}:{node.lineno}"
            )
    if not sources:
        problems.append("0 nguồn — không phân biệt được với máy quét hỏng")

    if problems:
        print()
        print("ĐỎ:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
