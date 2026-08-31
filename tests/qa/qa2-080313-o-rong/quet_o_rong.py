#!/usr/bin/env python3
"""Scan gates for the shape "a neutral/empty state treated as nothing to check".

Three gates fell to the same shape in one night, written by three different
people:

    #359  an EMPTY persona set    -> read as CLEAN
    #430  an EMPTY wrapper list   -> read as NOTHING WAS LOST
    #439  tree == "clean"         -> read as NOTHING TO COMPARE

Every one of them is a branch where some neutral value (an empty collection, a
zero, a `None`, a sentinel string) skips the check instead of failing it. The
gate then says green for two very different reasons and cannot tell them apart:
"measured everything, all fine" and "measured nothing".

This scanner locates CANDIDATES; it does not judge them. The judgement is one
question per site, and it needs a human: is that neutral value a LEGITIMATE
STATE that still needs checking, or is it genuinely "nothing here"?

What it reports (Python AST, plus Python extracted from shell heredocs):

  V1  vacuous-loop   a `for` whose body is the only place a verdict is emitted,
                     with no size/floor guard on the same iterable in scope
  V2  neutral-guard  `if x != <literal>:` / `if x == <literal>: <green>` where
                     checks live on one side only
  V3  truthy-guard   `if x:` / `if x is not None:` wrapping checks, no else
  V4  empty-early    `if not x: return` / `if len(x) == 0: return` on a
                     verdict-returning function
  V5  vacuous-agg    `all(...)`, or a comprehension compared to an empty
                     literal -- both say True on an empty source

A site is only reported when the guarded region actually emits a VERDICT
(raise SystemExit / sys.exit / assert / return an exit code / append to a
failure list / self.fail). A neutral branch that guards nothing is noise.

Usage:
    python3 quet_o_rong.py [--root DIR] [--json] [--only PATTERN] [--selftest]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Sentinel/neutral values. A comparison against one of these is what makes a
# branch a candidate: the value names a state that the author decided is
# uninteresting.
NEUTRAL_LITERALS: tuple[object, ...] = (0, "", None, False)
NEUTRAL_NAMES = frozenset({"clean", "ok", "none", "sạch", "sach", "empty", "?"})

# Names that signal "this collection holds problems". A loop that only appends
# to one of these emits its verdict inside the loop.
FAILURE_NAMES = re.compile(
    r"(fail|loi|lỗi|error|problem|viol|bad|missing|thieu|thiếu|mat|mất|drift|"
    r"dirty|ban|bẩn|hong|hỏng|lech|lệch|sot|sót|gap|hở|ho)",
    re.IGNORECASE,
)

EXIT_CALLS = frozenset({"exit", "_exit", "fail", "failed", "abort", "die", "skip"})


@dataclass
class Site:
    path: str
    line: int
    pattern: str
    neutral: str
    snippet: str
    why: str
    func: str = "?"

    def key(self) -> tuple:
        return (self.path, self.line, self.pattern)


@dataclass
class ScanResult:
    sites: list[Site] = field(default_factory=list)
    files_read: int = 0
    files_parsed: int = 0
    parse_errors: list[tuple[str, str]] = field(default_factory=list)

    def add(self, site: Site) -> None:
        self.sites.append(site)


# --------------------------------------------------------------------------
# verdict detection
# --------------------------------------------------------------------------


def _call_name(node: ast.AST) -> str:
    """Dotted name of a call target, or ''."""
    if not isinstance(node, ast.Call):
        return ""
    f = node.func
    parts: list[str] = []
    while isinstance(f, ast.Attribute):
        parts.append(f.attr)
        f = f.value
    if isinstance(f, ast.Name):
        parts.append(f.id)
    return ".".join(reversed(parts))


def emits_verdict(nodes: list[ast.AST]) -> bool:
    """True when this region can turn the gate red on its own.

    Anything that raises, exits non-zero, asserts, or records a failure counts.
    A region that merely prints or computes does not: a neutral branch skipping
    a `print` is not a blind gate.
    """

    for top in nodes:
        for node in ast.walk(top):
            if isinstance(node, (ast.Raise, ast.Assert)):
                return True
            if isinstance(node, ast.Call):
                name = _call_name(node)
                tail = name.rsplit(".", 1)[-1]
                if tail in EXIT_CALLS or name in {
                    "sys.exit",
                    "os._exit",
                    "pytest.fail",
                }:
                    return True
                # failures.append(...) / problems.add(...)
                if tail in {
                    "append",
                    "add",
                    "extend",
                    "update",
                } and FAILURE_NAMES.search(name):
                    return True
            if isinstance(node, ast.Return) and node.value is not None:
                # `return 1` / `return EXIT_DIRTY` -- a non-zero exit code.
                v = node.value
                if (
                    isinstance(v, ast.Constant)
                    and isinstance(v.value, int)
                    and v.value != 0
                ):
                    return True
                if isinstance(v, ast.Name) and re.search(
                    r"EXIT_(?!OK)|_DIRTY|_FAIL", v.id, re.IGNORECASE
                ):
                    return True
    return False


def wraps_a_checking_region(nodes: list[ast.AST]) -> bool:
    """True when the body is a REGION of checking, not a single direct verdict.

    This is the discriminator that keeps the scan honest. Two shapes look
    identical to a grep:

        if rc != 0:  raise SystemExit(1)      <- the check ITSELF. `rc == 0` is
                                                 the pass condition. Not blind.
        if tree != "clean":                   <- a WRAPPER. The real check is
            if tree != now: raise                `tree != now`, about a
                                                 different property, and
                                                 `clean` never reaches it.

    Only the second shape can hide a check behind a neutral value, so only the
    second is reported. Without this the scan drowns in every ordinary
    `if bad: fail` in the repo and the output becomes unreadable -- which is
    its own way of finding nothing.
    """

    for top in nodes:
        if isinstance(top, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            if emits_verdict([top]):
                return True
        # a call into a helper that does the checking
        if isinstance(top, (ast.Expr, ast.Assign)):
            for sub in ast.walk(top):
                if isinstance(sub, ast.Call) and re.search(
                    r"(check|kiem|kiểm|verify|assert|gate|cong|cổng|scan|quet|quét|"
                    r"compare|so_|doi_chieu)",
                    _call_name(sub),
                    re.IGNORECASE,
                ):
                    return True
    return False


def is_green_exit(nodes: list[ast.AST]) -> bool:
    """True when this region leaves on the happy path: bare return, return 0/True."""

    if not nodes:
        return False
    for node in nodes:
        if isinstance(node, ast.Return):
            if node.value is None:
                return True
            v = node.value
            if isinstance(v, ast.Constant) and v.value in (0, True, None):
                return True
            if isinstance(v, ast.Name) and re.search(r"EXIT_OK|_OK\b", v.id):
                return True
        if isinstance(node, (ast.Continue, ast.Pass)):
            return True
    return False


def returns_a_complaint(nodes: list[ast.AST]) -> bool:
    """True when this branch RETURNS something non-empty instead of exiting.

    #430 landed its floor in exactly this form -- `if not WRAPPERS: return
    ["<complaint>"]`. The function's contract is "return the list of
    problems", so a non-empty return IS the red signal even though nothing
    raises. Read the empty case as unguarded and the scanner keeps reporting a
    site that was fixed an hour ago.
    """

    for top in nodes:
        for node in ast.walk(top):
            if isinstance(node, ast.Return) and node.value is not None:
                v = node.value
                if isinstance(v, (ast.List, ast.Tuple, ast.Set)) and v.elts:
                    return True
                if isinstance(v, ast.Dict) and v.keys:
                    return True
                if isinstance(v, ast.Constant) and isinstance(v.value, str) and v.value:
                    return True
                if isinstance(v, ast.JoinedStr):
                    return True
    return False


def _describe(node: ast.AST, src_lines: list[str]) -> str:
    line = getattr(node, "lineno", 0)
    if 1 <= line <= len(src_lines):
        return src_lines[line - 1].strip()[:130]
    return "?"


def _neutral_repr(node: ast.AST) -> str | None:
    """Return a printable neutral value if this node is one, else None."""

    if isinstance(node, ast.Constant):
        v = node.value
        if v in NEUTRAL_LITERALS or (isinstance(v, str) and v.lower() in NEUTRAL_NAMES):
            return repr(v)
        if isinstance(v, str) and v == "":
            return "''"
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)) and not node.elts:
        return "[] (rỗng)"
    if isinstance(node, ast.Dict) and not node.keys:
        return "{} (rỗng)"
    return None


# --------------------------------------------------------------------------
# the five patterns
# --------------------------------------------------------------------------


class Visitor(ast.NodeVisitor):
    def __init__(self, path: str, src: str, out: ScanResult):
        self.path = path
        self.lines = src.splitlines()
        self.out = out
        self.func_stack: list[str] = []
        # Names that already carry a floor/size guard somewhere in the module.
        self.guarded: set[str] = set()

    # -- helpers ---------------------------------------------------------

    @property
    def func(self) -> str:
        return self.func_stack[-1] if self.func_stack else "<module>"

    def report(self, node: ast.AST, pattern: str, neutral: str, why: str) -> None:
        self.out.add(
            Site(
                path=self.path,
                line=getattr(node, "lineno", 0),
                pattern=pattern,
                neutral=neutral,
                snippet=_describe(node, self.lines),
                why=why,
                func=self.func,
            )
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.func_stack.append(node.name)
        self.generic_visit(node)
        self.func_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    # -- V1: vacuous loop -------------------------------------------------

    def visit_For(self, node: ast.For) -> None:
        if emits_verdict(list(node.body)) and not node.orelse:
            src = ast.unparse(node.iter) if hasattr(ast, "unparse") else "?"
            # A literal with elements can never be empty -- not a candidate.
            literal_nonempty = isinstance(
                node.iter, (ast.List, ast.Tuple, ast.Set)
            ) and bool(node.iter.elts)
            if not literal_nonempty and not self._has_floor(src):
                self.report(
                    node,
                    "V1 vòng-lặp-rỗng",
                    f"{src} rỗng",
                    "mọi khẳng định nằm trong thân vòng lặp; nguồn rỗng ⇒ không "
                    "khẳng định nào chạy, phán quyết vẫn xanh",
                )
        self.generic_visit(node)

    def _has_floor(self, iter_src: str) -> bool:
        """Does the module guard the SIZE of this iterable anywhere?

        A floor (`assert len(X) >= N`, `if not X: exit(2)`, `if len(X) != N`)
        is exactly the patch #359 landed. Loops that already have one are not
        candidates.
        """

        base = re.split(r"[.(\[]", iter_src.strip())[0]
        return bool(base) and base in self.guarded

    # -- V2 / V3 / V4: the if-branches ------------------------------------

    def visit_If(self, node: ast.If) -> None:
        test = node.test
        body_verdict = emits_verdict(list(node.body))
        orelse_verdict = emits_verdict(list(node.orelse)) if node.orelse else False

        # V2 -- `if x != <neutral>:` with checks inside and no else.
        if isinstance(test, ast.Compare) and len(test.ops) == 1:
            op = test.ops[0]
            right = test.comparators[0]
            neutral = _neutral_repr(right)
            left_src = ast.unparse(test.left) if hasattr(ast, "unparse") else "?"
            if neutral is not None:
                if (
                    isinstance(op, (ast.NotEq, ast.IsNot))
                    and body_verdict
                    and not orelse_verdict
                    and wraps_a_checking_region(list(node.body))
                ):
                    self.report(
                        node,
                        "V2 giá-trị-trung-tính",
                        f"{left_src} == {neutral}",
                        f"mọi kiểm bên trong chỉ chạy khi {left_src} khác {neutral}; "
                        f"khi bằng {neutral} thì đi thẳng xuống đường xanh",
                    )
                elif (
                    isinstance(op, (ast.Eq, ast.Is))
                    and is_green_exit(list(node.body))
                    and not body_verdict
                ):
                    self.report(
                        node,
                        "V4 rỗng-về-sớm",
                        f"{left_src} == {neutral}",
                        f"{neutral} thoát sớm theo đường xanh trước khi bất kỳ kiểm nào chạy",
                    )

        # A size guard that turns the gate red IS the floor. #359 landed exactly
        # this shape -- `if len(people) < DEMO_CAST_SIZE: die(...)` -- so the
        # scanner has to read it, or it re-reports a site that is already fixed
        # and its count stops meaning anything.
        if body_verdict and isinstance(test, ast.Compare):
            for sub in ast.walk(test):
                if isinstance(sub, ast.Call) and _call_name(sub) == "len" and sub.args:
                    src = ast.unparse(sub.args[0]) if hasattr(ast, "unparse") else ""
                    base = re.split(r"[.(\[]", src.strip())[0]
                    if base:
                        self.guarded.add(base)

        # V4 -- `if not x: return` / `if len(x) == 0: return`
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            src = ast.unparse(test.operand) if hasattr(ast, "unparse") else "?"
            if is_green_exit(list(node.body)) and not body_verdict:
                self.report(
                    node,
                    "V4 rỗng-về-sớm",
                    f"{src} rỗng/None/0",
                    f"{src} rỗng thoát sớm theo đường xanh, không kiểm gì",
                )
            elif body_verdict or returns_a_complaint(list(node.body)):
                # `if not X: raise` and `if not X: return [complaint]` are both
                # the floor -- remember it for V1/V6.
                base = re.split(r"[.(\[]", src.strip())[0]
                self.guarded.add(base)

        # V3 -- `if x:` wrapping checks, nothing on the falsy side.
        if (
            isinstance(test, (ast.Name, ast.Attribute, ast.Call))
            and body_verdict
            and not node.orelse
            and wraps_a_checking_region(list(node.body))
        ):
            src = ast.unparse(test) if hasattr(ast, "unparse") else "?"
            if not isinstance(test, ast.Call) or _call_name(test) in {"len", "bool"}:
                self.report(
                    node,
                    "V3 điều-kiện-truthy",
                    f"{src} rỗng/0/None",
                    f"kiểm chỉ chạy khi {src} truthy; rỗng/0/None đi thẳng xuống đường xanh",
                )

        self.generic_visit(node)

    # -- floors we should notice ------------------------------------------

    def visit_Assert(self, node: ast.Assert) -> None:
        self._note_floor(node.test)
        self.generic_visit(node)

    def _note_floor(self, test: ast.AST) -> None:
        for sub in ast.walk(test):
            if isinstance(sub, ast.Call) and _call_name(sub) == "len" and sub.args:
                src = ast.unparse(sub.args[0]) if hasattr(ast, "unparse") else ""
                base = re.split(r"[.(\[]", src.strip())[0]
                if base:
                    self.guarded.add(base)
            if isinstance(sub, ast.Name):
                # `assert PEOPLE` / `assert DEMO_CAST_SIZE <= len(people)`
                self.guarded.add(sub.id)

    # -- V6: a comprehension whose SOURCE can vanish -----------------------

    def visit_Return(self, node: ast.Return) -> None:
        """`return [msg for name in WRAPPERS if name not in declared]` -- #430.

        Same blindness as V1, written as a comprehension instead of a `for`, so
        a scanner that only reads `ast.For` walks straight past it. The
        returned list means "nothing is wrong"; an empty SOURCE also means
        "nothing is wrong"; the caller cannot tell which it got.

        Only bare-Name sources are reported. A comprehension over
        `scan.results()` is a computed intermediate; a comprehension over a
        module-level anchor list is the gate's own power supply, and that is
        the one that can silently be unplugged.
        """

        comp = node.value
        if isinstance(
            comp, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)
        ):
            for gen in comp.generators:
                if isinstance(gen.iter, ast.Name) and gen.iter.id not in self.guarded:
                    self.report(
                        node,
                        "V6 nguồn-comprehension-rỗng",
                        f"{gen.iter.id} rỗng",
                        f"kết quả rỗng diễn đạt cả 'không có gì sai' lẫn "
                        f"'{gen.iter.id} rỗng nên không có gì để mà sai'; "
                        "người gọi không phân biệt được hai cái",
                    )
        self.generic_visit(node)

    # -- V5: aggregates that are True on empty ----------------------------

    def visit_Call(self, node: ast.Call) -> None:
        if _call_name(node) == "all" and node.args:
            arg = node.args[0]
            if isinstance(arg, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
                src = (
                    ast.unparse(arg.generators[0].iter)
                    if hasattr(ast, "unparse")
                    else "?"
                )
                self.report(
                    node,
                    "V5 gộp-rỗng-là-True",
                    f"{src} rỗng",
                    "all() trên nguồn rỗng trả True — 'không có gì sai' và "
                    "'không có gì để mà sai' cùng một giá trị",
                )
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        # `[x for x in SRC if ...] == []` / `assertEqual(comp, [])`
        if len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
            left, right = node.left, node.comparators[0]
            for comp, other in ((left, right), (right, left)):
                if isinstance(comp, (ast.ListComp, ast.SetComp)) and _neutral_repr(
                    other
                ):
                    src = (
                        ast.unparse(comp.generators[0].iter)
                        if hasattr(ast, "unparse")
                        else "?"
                    )
                    self.report(
                        node,
                        "V5 gộp-rỗng-là-True",
                        f"{src} rỗng",
                        f"so sánh với rỗng: {src} rỗng cho ra rỗng, không phân biệt "
                        "được với 'đã duyệt hết và không thấy gì'",
                    )
        self.generic_visit(node)


# --------------------------------------------------------------------------
# shell heredocs
# --------------------------------------------------------------------------

HEREDOC = re.compile(
    r"python3?\b[^\n]*<<-?\s*'?(?P<tag>[A-Za-z_][A-Za-z0-9_]*)'?\s*\n(?P<body>.*?)^\1\s*$",
    re.DOTALL | re.MULTILINE,
)


def python_blocks_from_shell(text: str) -> list[tuple[int, str]]:
    """Extract embedded Python from `python3 - <<'PY' ... PY` heredocs.

    #439 lives inside one of these. A scanner that only reads *.py would miss
    the very case that started this scan.
    """

    blocks: list[tuple[int, str]] = []
    for m in HEREDOC.finditer(text):
        start_line = text[: m.start("body")].count("\n") + 1
        blocks.append((start_line, m.group("body")))
    return blocks


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def scan_source(path: str, src: str, out: ScanResult, line_offset: int = 0) -> None:
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        out.parse_errors.append((path, str(exc)))
        return
    out.files_parsed += 1
    before = len(out.sites)
    v = Visitor(path, src, out)
    # Two passes: the first collects floors, the second reports. Without this a
    # floor written BELOW a loop would not protect it.
    prescan = Visitor(path, src, ScanResult())
    prescan.visit(tree)
    v.guarded = prescan.guarded
    v.visit(tree)
    if line_offset:
        for site in out.sites[before:]:
            site.line += line_offset


def scan_tree(root: Path, only: str | None = None) -> ScanResult:
    out = ScanResult()
    targets: list[Path] = []
    for pat in ("scripts/**/*.py", "tests/**/*.py", "scripts/**/*.sh", "tests/**/*.sh"):
        targets.extend(sorted(root.glob(pat)))
    for path in targets:
        rel = str(path.relative_to(root))
        if "__pycache__" in rel:
            continue
        if only and only not in rel:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        out.files_read += 1
        if path.suffix == ".py":
            scan_source(rel, text, out)
        else:
            for start, body in python_blocks_from_shell(text):
                scan_source(rel, body, out, line_offset=start - 1)
    return out


def selftest() -> int:
    """Prove each pattern fires on a hand-written positive, and stays quiet on
    the matching negative. A scanner nobody tested is a zero nobody can read."""

    cases: list[tuple[str, str, bool]] = [
        (
            "V1 dương",
            "def g(items):\n"
            "    for x in items:\n"
            "        if x.bad:\n"
            "            raise SystemExit(1)\n",
            True,
        ),
        (
            "V1 âm (có sàn)",
            "def g(items):\n"
            "    assert len(items) >= 7\n"
            "    for x in items:\n"
            "        if x.bad:\n"
            "            raise SystemExit(1)\n",
            False,
        ),
        (
            "V2 dương",
            "def g(tree, now):\n"
            '    if tree != "clean":\n'
            "        if tree != now:\n"
            "            raise SystemExit(2)\n",
            True,
        ),
        (
            "V2 âm (kiểm thẳng)",
            "def g(rc):\n    if rc != 0:\n        raise SystemExit(1)\n",
            False,
        ),
        (
            "V3 dương",
            "def g(names):\n"
            "    if names:\n"
            "        for n in names:\n"
            "            assert n\n",
            True,
        ),
        (
            "V3 âm (kiểm thẳng)",
            "def g(x):\n    if x.bad:\n        raise SystemExit(1)\n",
            False,
        ),
        (
            "V4 dương",
            "def g(items):\n    if not items:\n        return 0\n    raise SystemExit(1)\n",
            True,
        ),
        (
            "V5 dương",
            "def g(src):\n    assert all(x.ok for x in src)\n",
            True,
        ),
        (
            "V6 dương (#430)",
            "WRAPPERS = ('callAsActor',)\n"
            "def lost(declared):\n"
            "    return [n for n in WRAPPERS if n not in declared]\n",
            True,
        ),
        (
            "V6 âm (có sàn)",
            "WRAPPERS = ('callAsActor',)\n"
            "def lost(declared):\n"
            "    if not WRAPPERS:\n"
            "        raise SystemExit(2)\n"
            "    return [n for n in WRAPPERS if n not in declared]\n",
            False,
        ),
        (
            "âm sạch",
            "def g(a, b):\n    return a + b\n",
            False,
        ),
    ]
    bad = 0
    for name, src, want_hit in cases:
        r = ScanResult()
        scan_source("<selftest>", src, r)
        got = bool(r.sites)
        mark = "OK " if got == want_hit else "SAI"
        if got != want_hit:
            bad += 1
        pats = ",".join(sorted({s.pattern.split()[0] for s in r.sites})) or "-"
        print(
            f"  [{mark}] {name:16s} kỳ vọng={'bắt' if want_hit else 'im':4s} thực={pats}"
        )

    # heredoc extraction
    sh = "run() {\n  python3 - <<'PY'\nif tree != \"clean\":\n    raise SystemExit(2)\nPY\n}\n"
    blocks = python_blocks_from_shell(sh)
    ok = len(blocks) == 1 and "clean" in blocks[0][1]
    print(
        f"  [{'OK ' if ok else 'SAI'}] heredoc          rút được {len(blocks)} khối python"
    )
    if not ok:
        bad += 1

    print(f"\nselftest: {'ĐẠT' if bad == 0 else f'HỎNG {bad}'}")
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--only", default=None, help="chỉ quét đường dẫn chứa chuỗi này")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    out = scan_tree(Path(args.root).resolve(), args.only)
    if args.json:
        print(
            json.dumps(
                {
                    "files_read": out.files_read,
                    "files_parsed": out.files_parsed,
                    "parse_errors": out.parse_errors,
                    "sites": [s.__dict__ for s in out.sites],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    by_pattern: dict[str, list[Site]] = {}
    for s in out.sites:
        by_pattern.setdefault(s.pattern, []).append(s)
    for pattern in sorted(by_pattern):
        print(f"\n=== {pattern} ({len(by_pattern[pattern])}) ===")
        for s in by_pattern[pattern]:
            print(f"{s.path}:{s.line}  [{s.func}]  trung tính: {s.neutral}")
            print(f"    {s.snippet}")
    print(
        f"\nĐọc {out.files_read} file, phân tích được {out.files_parsed} khối, "
        f"{len(out.parse_errors)} khối không parse được, {len(out.sites)} chỗ ứng viên."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
