#!/usr/bin/env python3
"""Run a mutation table against the HTTP integer-money boundary gate.

The probe edits one tracked file at a time, runs the committed pytest gate,
and restores that file from Git before moving to the next row. Mutation points
are discovered from the current AST or imported from the gate itself so the
probe does not silently depend on a second handwritten inventory.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from types import ModuleType

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[5]
SERVICE_ROOT = REPO_ROOT / "services" / "api"
SCHEMAS_PATH = SERVICE_ROOT / "app" / "api" / "schemas.py"
GATE_PATH = SERVICE_ROOT / "tests" / "test_money_api_boundary_is_integer.py"
GATE_TEST = "tests/test_money_api_boundary_is_integer.py"

FieldKey = tuple[str, str]
Mutation = Callable[[str], str]


class CannotMeasure(RuntimeError):
    """Signal that an experiment cannot produce trustworthy evidence."""


@dataclass(frozen=True)
class MoneyFieldTarget:
    """AST-selected money field whose whole annotation will be replaced."""

    model_name: str
    field_name: str
    annotation: ast.expr


@dataclass(frozen=True)
class WalkerLoopTarget:
    """The dependency-parameter loop and its body-only iterable expression."""

    iterator: ast.expr
    body_only_source: str


@dataclass(frozen=True)
class MutationCase:
    """One mutation-table row and its allowed outcome."""

    mutation_id: str
    description: str
    path: Path
    mutate: Mutation
    expectation: str


@dataclass(frozen=True)
class GateResult:
    """The observable result of invoking the real pytest gate."""

    returncode: int
    summary: str


def _run_command(
    arguments: list[str], *, cwd: Path
) -> subprocess.CompletedProcess[str]:
    """Run a local command without a shell and retain both output streams."""

    try:
        return subprocess.run(
            arguments,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise CannotMeasure(f"không chạy được {arguments[0]!r}: {exc}") from exc


def _require_clean_tree() -> None:
    """Refuse to let checkout-based restoration overwrite pending work."""

    status = _run_command(["git", "status", "--porcelain"], cwd=REPO_ROOT)
    if status.returncode != 0:
        raise CannotMeasure(f"git status lỗi rc={status.returncode}")
    dirty_lines = status.stdout.splitlines()
    if dirty_lines:
        raise CannotMeasure(
            f"cây có {len(dirty_lines)} thay đổi chưa commit theo git status --porcelain"
        )


def _load_gate_module() -> ModuleType:
    """Import the gate so mutation keys come from its live constants."""

    spec = importlib.util.spec_from_file_location(
        "_backend_tt_0005_money_boundary_gate", GATE_PATH
    )
    if spec is None or spec.loader is None:
        raise CannotMeasure("không tạo được import spec cho file cổng")

    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SERVICE_ROOT))
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise CannotMeasure(f"không import được module cổng: {exc}") from exc
    finally:
        del sys.path[0]
    return module


def _import_mapping(module: ModuleType, name: str) -> dict[FieldKey, str]:
    """Read and validate one two-string-key review mapping from the gate."""

    value = getattr(module, name, None)
    if not isinstance(value, dict) or not value:
        raise CannotMeasure(f"{name} không phải dict khác rỗng trong module cổng")
    if not all(
        isinstance(key, tuple)
        and len(key) == 2
        and all(isinstance(part, str) for part in key)
        and isinstance(reason, str)
        for key, reason in value.items()
    ):
        raise CannotMeasure(f"{name} có hình dạng khoá hoặc lý do không đo được")
    return dict(value)


def _find_money_field(source: str) -> MoneyFieldTarget:
    """Find the first class field whose name ends in ``_vnd`` by AST."""

    tree = ast.parse(source)
    for model in tree.body:
        if not isinstance(model, ast.ClassDef):
            continue
        for statement in model.body:
            if not isinstance(statement, ast.AnnAssign):
                continue
            if not isinstance(statement.target, ast.Name):
                continue
            if statement.target.id.endswith("_vnd"):
                return MoneyFieldTarget(
                    model_name=model.name,
                    field_name=statement.target.id,
                    annotation=statement.annotation,
                )
    raise CannotMeasure("AST không dò được trường có tên kết thúc bằng _vnd")


def _find_mapping(tree: ast.Module, name: str) -> ast.Dict:
    """Find a module-level dictionary literal assigned to ``name``."""

    for statement in tree.body:
        value: ast.expr | None = None
        if (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == name
        ):
            value = statement.value
        elif isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in statement.targets
        ):
            value = statement.value
        if isinstance(value, ast.Dict):
            return value
    raise CannotMeasure(f"AST không dò được dict {name}")


def _find_mapping_entry(
    source: str, name: str, wanted_key: FieldKey
) -> tuple[ast.expr, ast.expr]:
    """Find one dictionary entry using a key imported from the gate."""

    mapping = _find_mapping(ast.parse(source), name)
    for key_node, value_node in zip(mapping.keys, mapping.values, strict=True):
        if key_node is None:
            continue
        try:
            key = ast.literal_eval(key_node)
        except (ValueError, TypeError, SyntaxError):
            continue
        if key == wanted_key:
            return key_node, value_node
    raise CannotMeasure(f"AST không dò được khoá import {wanted_key!r} trong {name}")


def _node_offsets(source: str, node: ast.AST) -> tuple[int, int]:
    """Convert AST UTF-8 line/column coordinates to byte offsets."""

    if (
        not hasattr(node, "lineno")
        or not hasattr(node, "end_lineno")
        or node.end_lineno is None
        or node.end_col_offset is None
    ):
        raise CannotMeasure("AST thiếu toạ độ kết thúc cho điểm đột biến")
    lines = source.encode("utf-8").splitlines(keepends=True)
    start = sum(len(line) for line in lines[: node.lineno - 1]) + node.col_offset
    end = sum(len(line) for line in lines[: node.end_lineno - 1])
    end += node.end_col_offset
    return start, end


def _replace_node(source: str, node: ast.AST, replacement: str) -> str:
    """Replace exactly one AST node while preserving all surrounding text."""

    start, end = _node_offsets(source, node)
    encoded = source.encode("utf-8")
    mutated = encoded[:start] + replacement.encode("utf-8") + encoded[end:]
    return mutated.decode("utf-8")


def _ensure_decimal_import(source: str) -> str:
    """Add the import needed for a real Decimal field mutation."""

    tree = ast.parse(source)
    for statement in tree.body:
        if not isinstance(statement, ast.ImportFrom) or statement.module != "decimal":
            continue
        if any(
            alias.name == "Decimal" and alias.asname in (None, "Decimal")
            for alias in statement.names
        ):
            return source

    future_imports = [
        statement
        for statement in tree.body
        if isinstance(statement, ast.ImportFrom) and statement.module == "__future__"
    ]
    if not future_imports:
        raise CannotMeasure("AST không dò được vị trí import Decimal an toàn")
    insert_at = future_imports[-1].end_lineno
    lines = source.splitlines(keepends=True)
    lines.insert(insert_at, "from decimal import Decimal\n")
    return "".join(lines)


def _mutate_money_annotation(
    source: str, *, target: MoneyFieldTarget, replacement: str
) -> str:
    """Replace the AST-selected money annotation with one requested type."""

    mutated = _replace_node(source, target.annotation, replacement)
    if replacement == "Decimal":
        mutated = _ensure_decimal_import(mutated)
    ast.parse(mutated)
    return mutated


def _remove_mapping_entry(source: str, *, name: str, key: FieldKey) -> str:
    """Delete one complete dictionary-entry line range selected by AST."""

    key_node, value_node = _find_mapping_entry(source, name, key)
    encoded_lines = source.encode("utf-8").splitlines(keepends=True)
    first_index = key_node.lineno - 1
    last_index = value_node.end_lineno - 1
    prefix = encoded_lines[first_index][: key_node.col_offset]
    tail = encoded_lines[last_index][value_node.end_col_offset :].rstrip(b"\r\n")
    if prefix.strip() or re.fullmatch(rb",[ \t]*(?:#.*)?", tail) is None:
        raise CannotMeasure(f"AST tìm thấy {key!r} nhưng không tách được nguyên mục")
    del encoded_lines[first_index : last_index + 1]
    mutated = b"".join(encoded_lines).decode("utf-8")
    ast.parse(mutated)
    return mutated


def _add_mapping_entry(source: str, *, name: str, key: FieldKey, reason: str) -> str:
    """Insert one garbage entry immediately before a dictionary's closing brace."""

    tree = ast.parse(source)
    mapping = _find_mapping(tree, name)
    existing_keys: set[object] = set()
    for key_node in mapping.keys:
        if key_node is None:
            continue
        try:
            existing_keys.add(ast.literal_eval(key_node))
        except (ValueError, TypeError, SyntaxError):
            continue
    if key in existing_keys:
        raise CannotMeasure(f"khoá rác sinh ra đã tồn tại trong {name}: {key!r}")

    encoded_lines = source.encode("utf-8").splitlines(keepends=True)
    closing_index = mapping.end_lineno - 1
    closing_line = encoded_lines[closing_index]
    brace_index = mapping.end_col_offset - 1
    if (
        closing_line[brace_index : brace_index + 1] != b"}"
        or closing_line[:brace_index].strip()
        or closing_line[brace_index + 1 :].strip()
    ):
        raise CannotMeasure(f"AST không tách được dấu đóng của {name}")
    key_columns = [node.col_offset for node in mapping.keys if node is not None]
    if not key_columns:
        raise CannotMeasure(f"{name} không có mục mẫu để xác định thụt lề")
    indent = " " * key_columns[0]
    entry = f"{indent}{key!r}: {reason!r},\n".encode()
    encoded_lines.insert(closing_index, entry)
    mutated = b"".join(encoded_lines).decode("utf-8")
    ast.parse(mutated)
    return mutated


def _change_mapping_reason(
    source: str, *, name: str, key: FieldKey, old_reason: str
) -> str:
    """Change only an imported entry's reason string, never its key."""

    _, value_node = _find_mapping_entry(source, name, key)
    try:
        current_reason = ast.literal_eval(value_node)
    except (ValueError, TypeError, SyntaxError) as exc:
        raise CannotMeasure(f"lý do của {key!r} không phải literal") from exc
    if current_reason != old_reason:
        raise CannotMeasure(f"lý do import và AST lệch nhau tại {key!r}")
    new_reason = f"{old_reason}; mutation changes wording only"
    mutated = _replace_node(source, value_node, repr(new_reason))
    ast.parse(mutated)
    return mutated


def _find_walk_function(tree: ast.Module) -> ast.FunctionDef:
    """Find the named contract walker at module scope."""

    candidates = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_walk_contract"
    ]
    if len(candidates) != 1:
        raise CannotMeasure(
            f"AST dò được {len(candidates)} hàm _walk_contract, cần đúng 1"
        )
    return candidates[0]


def _find_visit_function(source: str) -> ast.FunctionDef:
    """Find the nested ``visit`` function inside the contract walker."""

    walker = _find_walk_function(ast.parse(source))
    candidates = [
        node
        for node in walker.body
        if isinstance(node, ast.FunctionDef) and node.name == "visit"
    ]
    if len(candidates) != 1 or not candidates[0].body:
        raise CannotMeasure(f"AST dò được {len(candidates)} hàm visit dùng được")
    return candidates[0]


def _break_visit(source: str) -> str:
    """Insert an immediate return as the first statement of ``visit``."""

    visit = _find_visit_function(source)
    first_statement = visit.body[0]
    encoded_lines = source.encode("utf-8").splitlines(keepends=True)
    first_index = first_statement.lineno - 1
    prefix = encoded_lines[first_index][: first_statement.col_offset]
    if prefix.strip():
        raise CannotMeasure("AST không tách được đầu thân hàm visit")
    encoded_lines.insert(first_index, prefix + b"return\n")
    mutated = b"".join(encoded_lines).decode("utf-8")
    ast.parse(mutated)
    return mutated


def _find_dependency_loop(source: str) -> WalkerLoopTarget:
    """Find the loop that combines body, query, and path parameters."""

    walker = _find_walk_function(ast.parse(source))
    candidates: list[ast.For] = []
    for node in ast.walk(walker):
        if not isinstance(node, ast.For):
            continue
        attributes = {
            child.attr
            for child in ast.walk(node.iter)
            if isinstance(child, ast.Attribute)
        }
        if {"body_params", "query_params", "path_params"} <= attributes:
            candidates.append(node)
    if len(candidates) != 1:
        raise CannotMeasure(
            f"AST dò được {len(candidates)} vòng lặp body+query+path, cần đúng 1"
        )

    iterator = candidates[0].iter
    body_calls: list[ast.Call] = []
    for node in ast.walk(iterator):
        if not isinstance(node, ast.Call):
            continue
        attributes = {
            child.attr for child in ast.walk(node) if isinstance(child, ast.Attribute)
        }
        if "body_params" in attributes and not attributes & {
            "query_params",
            "path_params",
        }:
            body_calls.append(node)
    if len(body_calls) != 1:
        raise CannotMeasure(
            f"AST dò được {len(body_calls)} biểu thức chỉ-body, cần đúng 1"
        )
    body_only_source = ast.get_source_segment(source, body_calls[0])
    if body_only_source is None:
        raise CannotMeasure("AST không lấy được source của body_params")
    return WalkerLoopTarget(iterator=iterator, body_only_source=body_only_source)


def _drop_query_and_path(source: str, *, target: WalkerLoopTarget) -> str:
    """Keep only the AST-discovered body-parameter term in the loop."""

    mutated = _replace_node(source, target.iterator, target.body_only_source)
    ast.parse(mutated)
    return mutated


def _pytest_summary(output: str, returncode: int) -> str:
    """Extract pytest's compact final count and prefix its observed colour."""

    plain = re.sub(r"\x1b\[[0-9;]*m", "", output)
    lines = [line.strip() for line in plain.splitlines() if line.strip()]
    summary = "không có tóm tắt pytest"
    result_words = re.compile(
        r"\b(?:passed|failed|errors?|skipped|xfailed|xpassed)\b", re.IGNORECASE
    )
    for line in reversed(lines):
        if result_words.search(line):
            summary = line.strip("= ")
            break
    colour = "XANH" if returncode == 0 else "ĐỎ"
    return f"{colour}; {summary}".replace("|", "/")


def _run_gate() -> GateResult:
    """Run exactly the committed five-test gate through pytest."""

    try:
        process = subprocess.run(
            ["python3", "-m", "pytest", GATE_TEST, "-q"],
            cwd=SERVICE_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
    except subprocess.TimeoutExpired as exc:
        raise CannotMeasure("pytest vượt quá 180 giây") from exc
    except OSError as exc:
        raise CannotMeasure(f"không chạy được python3/pytest: {exc}") from exc
    output = f"{process.stdout}\n{process.stderr}"
    return GateResult(
        returncode=process.returncode,
        summary=_pytest_summary(output, process.returncode),
    )


def _restore_with_checkout(path: Path, pristine: str) -> None:
    """Restore one mutated path with the required Git checkout command."""

    relative = path.relative_to(REPO_ROOT).as_posix()
    restored = _run_command(["git", "checkout", "--", relative], cwd=REPO_ROOT)
    if restored.returncode != 0:
        raise CannotMeasure(f"git checkout -- {relative} lỗi rc={restored.returncode}")
    if path.read_text(encoding="utf-8") != pristine:
        raise CannotMeasure(f"git checkout -- {relative} không khôi phục đúng nội dung")


def _run_mutation(case: MutationCase) -> GateResult:
    """Apply one mutation, run the gate, and always restore the tracked file."""

    pristine = case.path.read_text(encoding="utf-8")
    mutated = case.mutate(pristine)
    if mutated == pristine:
        raise CannotMeasure(f"đột biến {case.mutation_id} không thay đổi file")

    try:
        case.path.write_text(mutated, encoding="utf-8")
        relative = case.path.relative_to(REPO_ROOT).as_posix()
        diff = _run_command(["git", "diff", "--quiet", "--", relative], cwd=REPO_ROOT)
        if diff.returncode == 0:
            raise CannotMeasure(
                f"đột biến {case.mutation_id} không hiện trong git diff"
            )
        if diff.returncode != 1:
            raise CannotMeasure(
                f"git diff của {case.mutation_id} lỗi rc={diff.returncode}"
            )
        return _run_gate()
    finally:
        _restore_with_checkout(case.path, pristine)


def _garbage_key(imported_key: FieldKey, existing: dict[FieldKey, str]) -> FieldKey:
    """Derive an absent garbage key from a real imported key."""

    model, field = imported_key
    suffix = "__MUTATION_GARBAGE__"
    candidate = (f"{model}{suffix}", f"{field}{suffix}")
    while candidate in existing:
        suffix += "_"
        candidate = (f"{model}{suffix}", f"{field}{suffix}")
    return candidate


def _build_cases() -> list[MutationCase]:
    """Discover every required mutation point before the first edit."""

    schemas_source = SCHEMAS_PATH.read_text(encoding="utf-8")
    gate_source = GATE_PATH.read_text(encoding="utf-8")
    money_target = _find_money_field(schemas_source)
    gate_module = _load_gate_module()
    inexact = _import_mapping(gate_module, "INEXACT_API_FIELDS_REVIEWED")
    routes = _import_mapping(gate_module, "ROUTES_WITHOUT_RESPONSE_VALIDATION")
    inexact_key = next(iter(inexact))
    route_key = next(iter(routes))
    garbage_key = _garbage_key(inexact_key, inexact)
    walker_loop = _find_dependency_loop(gate_source)

    target_label = f"{money_target.model_name}.{money_target.field_name}"
    inexact_label = f"{inexact_key[0]}.{inexact_key[1]}"
    route_label = f"{route_key[0]} {route_key[1]}"
    cases = [
        MutationCase(
            "A1",
            f"AST: {target_label} -> float",
            SCHEMAS_PATH,
            partial(
                _mutate_money_annotation,
                target=money_target,
                replacement="float",
            ),
            "red",
        ),
        MutationCase(
            "A2",
            f"AST: {target_label} -> Decimal",
            SCHEMAS_PATH,
            partial(
                _mutate_money_annotation,
                target=money_target,
                replacement="Decimal",
            ),
            "red",
        ),
        MutationCase(
            "A3",
            f"AST: {target_label} -> str",
            SCHEMAS_PATH,
            partial(
                _mutate_money_annotation,
                target=money_target,
                replacement="str",
            ),
            "red",
        ),
        MutationCase(
            "B1",
            f"xoá khoá import {inexact_label} khỏi INEXACT_API_FIELDS_REVIEWED",
            GATE_PATH,
            partial(
                _remove_mapping_entry,
                name="INEXACT_API_FIELDS_REVIEWED",
                key=inexact_key,
            ),
            "red",
        ),
        MutationCase(
            "C1",
            "thêm khoá rác dẫn xuất vào INEXACT_API_FIELDS_REVIEWED",
            GATE_PATH,
            partial(
                _add_mapping_entry,
                name="INEXACT_API_FIELDS_REVIEWED",
                key=garbage_key,
                reason="mutation-only garbage entry",
            ),
            "red",
        ),
        MutationCase(
            "W1",
            "cho visit() trong _walk_contract return ngay",
            GATE_PATH,
            _break_visit,
            "red",
        ),
        MutationCase(
            "W2",
            "bỏ query_params + path_params khỏi vòng lặp",
            GATE_PATH,
            partial(_drop_query_and_path, target=walker_loop),
            "observe",
        ),
        MutationCase(
            "R1",
            f"xoá khoá import {route_label} khỏi ROUTES_WITHOUT_RESPONSE_VALIDATION",
            GATE_PATH,
            partial(
                _remove_mapping_entry,
                name="ROUTES_WITHOUT_RESPONSE_VALIDATION",
                key=route_key,
            ),
            "red",
        ),
        MutationCase(
            "E1",
            f"chỉ đổi lý do của khoá import {inexact_label}",
            GATE_PATH,
            partial(
                _change_mapping_reason,
                name="INEXACT_API_FIELDS_REVIEWED",
                key=inexact_key,
                old_reason=inexact[inexact_key],
            ),
            "green",
        ),
    ]

    original_by_path = {SCHEMAS_PATH: schemas_source, GATE_PATH: gate_source}
    for case in cases:
        original = original_by_path[case.path]
        mutated = case.mutate(original)
        if mutated == original:
            raise CannotMeasure(f"AST không tạo được điểm đột biến {case.mutation_id}")
        ast.parse(mutated)
    return cases


def _print_row(
    mutation_id: str, description: str, result: GateResult, *, baseline: bool = False
) -> None:
    """Print one stable pipe-delimited mutation-table row."""

    if baseline:
        conclusion = "BẮT ĐƯỢC" if result.returncode == 0 else "LỌT"
    else:
        conclusion = "BẮT ĐƯỢC" if result.returncode != 0 else "LỌT"
    safe_description = description.replace("|", "/")
    print(
        f"{mutation_id} | {safe_description} | {result.returncode} | "
        f"{result.summary} | {conclusion}",
        flush=True,
    )


def _measure() -> int:
    """Run the baseline and all required mutation-table rows."""

    if not GATE_PATH.is_file():
        raise CannotMeasure("không tìm thấy file cổng")
    if not SCHEMAS_PATH.is_file():
        raise CannotMeasure("không tìm thấy app/api/schemas.py")
    _require_clean_tree()
    cases = _build_cases()

    print("id | mô tả | rc | tóm tắt kết quả | kết luận")
    print("--- | --- | --- | --- | ---")
    baseline = _run_gate()
    _print_row("M0", "không đột biến (nền phải XANH)", baseline, baseline=True)
    if baseline.returncode != 0:
        raise CannotMeasure(f"nền M0 đã đỏ sẵn, rc={baseline.returncode}")

    unexpected: list[str] = []
    for case in cases:
        result = _run_mutation(case)
        _print_row(case.mutation_id, case.description, result)
        if result.returncode not in (0, 1):
            raise CannotMeasure(
                f"{case.mutation_id} trả rc={result.returncode}, không phải xanh/đỏ của test"
            )
        if case.expectation == "red" and result.returncode == 0:
            unexpected.append(f"{case.mutation_id} LỌT nhưng phải ĐỎ")
        elif case.expectation == "green" and result.returncode != 0:
            unexpected.append(f"{case.mutation_id} ĐỎ nhưng phải XANH")

    _require_clean_tree()
    if unexpected:
        print("KẾT QUẢ NGOÀI DỰ KIẾN: " + "; ".join(unexpected))
        return 1
    print("KẾT QUẢ ĐÚNG KỲ VỌNG; W2 là phép đo quan sát, E1 được phép LỌT.")
    return 0


def main() -> int:
    """Convert every unmeasurable path into an explicit fail-closed exit 2."""

    try:
        return _measure()
    except KeyboardInterrupt:
        print("KHONG KIEM DUOC: bị ngắt khi đang đo", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"KHONG KIEM DUOC: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
