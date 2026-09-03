#!/usr/bin/env python3
"""Every screen component must be rendered by something the entry point reaches.

## Why this exists

`check_server_routes_called.py` asks whether a route the server declares has a
screen that calls it. It does not ask the next question: whether that screen is
itself rendered by anything. A screen file can hold eight hundred lines, call
its routes correctly, typecheck, and be imported by nobody -- `tsc` is happy,
the route gate is happy, and no person can open it.

That gap is not hypothetical. On 2026-08-31 a work item arrived claiming two
screens had no way in, derived from counting how many times each name appeared
in `apps/mobile/src`. Both claims were wrong and the count missed a third
screen that really was dead:

  - `ChiaSe` was called dead on 3 mentions. It is rendered at `App.tsx:951`,
    behind two real buttons (`DotThu.tsx` "Chia sẻ cho từng người",
    `KetQuaThanhToan.tsx` "Chia sẻ kết quả"). The count only read `src/`, and
    `App.tsx` sits one directory above it.
  - `MaCuaToi` was called dead on 2 mentions. Both mentions ARE the wiring --
    the import and the render inside `MaKetBan`, which `CaNhan.tsx` draws.
    A screen wired in exactly one place is the normal case, not a defect.
  - `TheDeXuat` was not mentioned at all by the count, and it is the one screen
    in the tree that nothing renders.

Counting mentions cannot tell those three apart, because the number it produces
answers a different question than the one being asked.

## What "reachable" means here, precisely

A directed graph over files. There is an edge `G -> F` when `G` renders `<Name`
in real code and `Name` is imported into `G` from `F`. The roots are whatever
`package.json` names as the door: under `expo-router/entry` every route file
under `app/` (its default export -- `export { X as default } from`, or
`export default X` -- IS the render, because expo-router mounts it), otherwise
the classic pair `index.ts` / `App.tsx`. Judged screens live under both
`src/screens` (legacy tree) and `src/rudi/screens` (the shell that ships). A
screen file passes when it is reachable from a root by following those edges.
`const X = lazy(() => import("…"))` binds a renderable name too: it is how the
shell reaches the legacy tree through `app/legacy.tsx`.

Two things make this different from a text search, and both were failure modes
of the hand-rolled attempts it replaces:

  - **Comments and strings are stripped first**, by the same `tokenize`/`mask`
    pair `check_api_contract.py` uses. This codebase writes about itself
    constantly: `ChupBill.tsx:285` names `KetQuaNhanDien`, `GoiYChia` and
    `KetQuaThanhToan` in a prose paragraph. A reader that counts those as
    renders reports three dead screens as alive.
  - **The edge requires a render, not an import.** `KetQuaThanhToan.tsx` does
    `import type { Envelope } from "./ChiaSe"`, and `api.ts` and
    `fixtures/thanh-toan-demo.ts` do the same. Three imports, zero renders --
    if importing counted, a screen would be kept alive by the fact that another
    screen borrows a type from it.

## What it does NOT prove

Stated because a green here is narrower than it reads:

- **Not that a person can tap it.** The edge is a render, and a render inside
  `{step === "chia-se" && ...}` counts even if nothing ever sets that step.
  This gate proves a chain of renders exists from the entry point; it does not
  execute a condition. `tools/tab-snapshots.mjs` and the QA walks are what
  prove a human path.
- **Not that the screen works, or is correct, or is reached with the right
  props.** Any of those can be broken under a green here.
- **Not that a dead screen is a defect.** Sometimes it is a screen landing
  ahead of the flow that will open it. That is why the answer is a pinned file
  and not a hard failure: say so in `.screens-unrendered.json`, with a reason,
  and the gate stays quiet about it while keeping the name visible.

A `no` from this gate is conclusive -- nothing renders that file, so nothing can
show it. A `yes` is only permission for the other gates to speak.

Usage:
  scripts/check_screens_reachable.py            check the tree this file is in
  scripts/check_screens_reachable.py --json     the same findings, machine-readable
  scripts/check_screens_reachable.py --selftest prove the gate can be red, on canaries

Exit codes: 0 every screen is reachable or is pinned with a reason, 1 a screen
is not, 2 the check could not run -- and could not run is never a pass.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MOBILE_ROOT = REPO_ROOT / "apps" / "mobile"
SCREEN_ROOT = MOBILE_ROOT / "src" / "screens"

# The shell that ships. `package.json` names `expo-router/entry` as `main`, so the
# door is every route file under `app/` and the screens they render live in
# `src/rudi/screens`. Both roots are judged; derived from MOBILE_ROOT at call
# time so the canary trees, which repoint MOBILE_ROOT, get the same shape.
ROUTER_ENTRY = "expo-router/entry"


def rudi_screen_root() -> Path:
    return MOBILE_ROOT / "src" / "rudi" / "screens"


def app_root() -> Path:
    return MOBILE_ROOT / "app"


def package_main() -> str | None:
    """What `package.json` says the door is, or None when there is no manifest."""
    manifest = MOBILE_ROOT / "package.json"
    if not manifest.is_file():
        return None
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("main")
    except (OSError, ValueError):
        return None


def entry_roots() -> list[Path]:
    """The files a phone actually starts from.

    Under `expo-router/entry` those are the route files -- every `.tsx` under
    `app/`, because the file system IS the navigator and each file is a door a
    URL can open. `index.ts` / `App.tsx` are then NOT roots: the legacy tree is
    reachable only through `app/legacy.tsx`, and the gate should say so rather
    than grant it a door `package.json` no longer names. Without a manifest
    (the canary trees) the classic pair stays the root.
    """
    if package_main() == ROUTER_ENTRY and app_root().is_dir():
        return sorted(p for p in app_root().rglob("*.tsx") if p.is_file())
    return [
        MOBILE_ROOT / name for name in ENTRY_RELATIVE if (MOBILE_ROOT / name).is_file()
    ]


# Screens that nothing renders on purpose, each with a reason. Keyed by path so
# the entry survives edits above it -- a pin that moves with every unrelated
# line goes red for the wrong reason, which is how a gate stops being run.
PIN_PATH = REPO_ROOT / ".screens-unrendered.json"

# Entry points. `index.ts` is what `package.json` names as `main`; `App.tsx` is
# what it registers. Both are roots so the graph does not depend on which of
# the two a future Expo version treats as the real door.
ENTRY_RELATIVE = ("index.ts", "App.tsx")

# Files that pass the chain along by importing rather than by rendering.
#
# Deliberately `index.ts` alone, and this line is the whole gate. `index.ts`
# does `registerRootComponent(App)` -- no JSX anywhere -- so requiring a render
# edge there would cut the graph at the door and report every screen dead.
#
# `App.tsx` was in this tuple for one draft and it made the gate lie. It is a
# root, but it is also the file that imports and renders most of the expense
# flow, so letting its imports carry the chain marked every screen it merely
# imports as reachable. Measured, not reasoned: deleting the single
# `<ChiaSe ... />` render from `App.tsx` left the gate GREEN, because the
# `import { ChiaSe }` above it still supplied an edge. That is precisely the
# false pass this gate exists to prevent, so `App.tsx` earns its edges by
# rendering like every other file.
REGISTRATION_FILES = ("index.ts",)

# Directories under `apps/mobile` that hold shipped code. `tests/` and `tools/`
# are deliberately excluded: a screen rendered only by its own test is exactly
# the thing this gate exists to name, so letting a test file supply the edge
# would make the answer always yes.
SOURCE_DIRS = ("src", "app")

# The twin gate, imported for its tokenizer rather than re-implemented. Loaded
# by path because `scripts/` is not a package and this file must run as a plain
# script from the repository root, which is how `gate.sh` invokes it.
_TWIN_PATH = REPO_ROOT / "scripts" / "check_api_contract.py"
_SPEC = importlib.util.spec_from_file_location("check_api_contract", _TWIN_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - defensive
    raise RuntimeError(f"không nạp được {_TWIN_PATH}")
twin = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = twin
_SPEC.loader.exec_module(twin)

# `import ... from "..."` / `export ... from "..."`, captured in two halves: the
# clause naming what is bound, and the module specifier. Run against masked
# source, so a specifier's contents are `x`-filled -- the real text is sliced
# out of the original at the offsets found here.
IMPORT_RE = re.compile(
    r"\b(?:import|export)\s+(?P<clause>[^;'\"]*?)\s*from\s*(?P<quote>['\"])(?P<spec>[^'\"]*)(?P=quote)",
    re.DOTALL,
)

# A JSX opening tag for a capitalised name: `<Foo`, `<Foo.Bar`. Lowercase tags
# are host elements (`<View`), never components defined in this tree.
JSX_RE = re.compile(r"<([A-Z][A-Za-z0-9_]*)")

# `const LegacyApp = lazy(() => import("../../App"))` -- a dynamic import bound
# to a name that is later rendered as `<LegacyApp />`. This is how the shell
# reaches the legacy tree; without this edge every legacy screen reads dead.
LAZY_IMPORT_RE = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[A-Z][A-Za-z0-9_]*)\s*=\s*(?:React\.)?lazy\(\s*(?:async\s*)?\(\)\s*=>\s*"
    r"import\(\s*(?P<quote>['\"])(?P<spec>[^'\"]*)(?P=quote)\s*\)"
)

# `export default Foo;` in a route file: expo-router renders the default export,
# so this IS the render edge of that file.
EXPORT_DEFAULT_NAME_RE = re.compile(
    r"^\s*export\s+default\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*;?\s*$", re.M
)

# `import type {...}` and `import {type Foo}` bind types, which cannot be
# rendered. Excluded so a type borrowed across files never supplies an edge.
TYPE_ONLY_CLAUSE = re.compile(r"^\s*type\b")


@dataclass
class Module:
    """One source file: what it imports, and what it renders."""

    path: Path
    rel: str
    # Rendered component name -> module specifier it was imported from, or None
    # when the name is defined in this same file.
    renders: dict[str, str | None] = field(default_factory=dict)
    # Every name bound by a value import, mapped to its specifier.
    imports: dict[str, str] = field(default_factory=dict)
    # Specifiers a route file hands to expo-router as its default export:
    # `export { Screen as default } from "..."`, or `export default Name` where
    # `Name` was imported. Only honoured for files under `app/`.
    default_from: list[str] = field(default_factory=list)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def masked_source(src: str) -> str:
    """`src` with comments and literal contents blanked, offsets unchanged."""
    return twin.mask(src, twin.tokenize(src))


def bound_names(clause: str) -> list[str]:
    """The value names an import clause binds.

    `import React, { useState } from "react"` binds `React` and `useState`.
    `import type { Envelope } from "./ChiaSe"` binds nothing renderable, and
    neither does the `type Foo` member inside a mixed brace list -- both are
    dropped here rather than filtered later, so a type can never be the thing
    that keeps a screen looking alive.
    """
    if TYPE_ONLY_CLAUSE.match(clause):
        return []
    names: list[str] = []
    # The brace list, if any, then whatever sits outside it (default import,
    # namespace import). Handled separately because the separators differ.
    brace = re.search(r"\{(?P<body>[^}]*)\}", clause, re.DOTALL)
    if brace:
        for member in brace.group("body").split(","):
            member = member.strip()
            if not member or TYPE_ONLY_CLAUSE.match(member):
                continue
            # `Foo as Bar` binds `Bar` -- the local name is what JSX writes.
            parts = re.split(r"\s+as\s+", member)
            names.append(parts[-1].strip())
        clause = clause[: brace.start()] + "," + clause[brace.end() :]
    for part in clause.split(","):
        part = part.strip()
        if not part or part == "*":
            continue
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", part):
            names.append(part)
        else:
            # `* as Foo`
            ns = re.fullmatch(r"\*\s+as\s+([A-Za-z_$][A-Za-z0-9_$]*)", part)
            if ns:
                names.append(ns.group(1))
    return [n for n in names if n]


def parse_module(path: Path, rel: str) -> Module:
    src = read(path)
    masked = masked_source(src)
    module = Module(path=path, rel=rel)

    for match in IMPORT_RE.finditer(masked):
        # Slice the real source: the specifier is `x`-filled in `masked`.
        spec = src[match.start("spec") : match.end("spec")]
        clause = src[match.start("clause") : match.end("clause")]
        for name in bound_names(clause):
            module.imports[name] = spec
        # `export { X as default } from "spec"`: the re-export IS the screen.
        if masked[match.start() : match.start() + 6] == "export" and re.search(
            r"\bdefault\b", clause
        ):
            module.default_from.append(spec)

    for match in LAZY_IMPORT_RE.finditer(masked):
        module.imports[match.group("name")] = src[
            match.start("spec") : match.end("spec")
        ]

    for match in EXPORT_DEFAULT_NAME_RE.finditer(masked):
        spec = module.imports.get(match.group("name"))
        if spec:
            module.default_from.append(spec)

    for match in JSX_RE.finditer(masked):
        name = match.group(1)
        # `Foo.Bar` -- the module edge belongs to `Foo`, which is what was
        # imported. Taking `Bar` would look up a name nothing ever binds.
        root = name.split(".")[0]
        module.renders.setdefault(root, module.imports.get(root))

    return module


def resolve(spec: str, importer: Path) -> Path | None:
    """A relative module specifier to the file it names, or None."""
    if not spec.startswith("."):
        return None  # a package, not a file in this tree
    base = (importer.parent / spec).resolve()
    for candidate in (
        base,
        base.with_suffix(".tsx"),
        base.with_suffix(".ts"),
        base / "index.tsx",
        base / "index.ts",
    ):
        if candidate.is_file():
            return candidate
    # `.mjs` specifiers reach outside `apps/mobile` (packages/shared). Nothing
    # there is a screen, so failing to resolve is the right answer, not an error.
    return None


def source_files() -> list[Path]:
    files: list[Path] = []
    for name in ENTRY_RELATIVE:
        entry = MOBILE_ROOT / name
        if entry.is_file():
            files.append(entry)
    for directory in SOURCE_DIRS:
        root = MOBILE_ROOT / directory
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.suffix in (".ts", ".tsx") and path.is_file():
                files.append(path)
    return files


def display_path(path: Path) -> str:
    """A path to print. Repo-relative normally, canary-relative under selftest.

    The canary trees live in a temporary directory outside the repository, so a
    bare `relative_to(REPO_ROOT)` raises there -- and a gate that cannot run its
    own canary is a gate whose zero means nothing.
    """
    for base in (REPO_ROOT, MOBILE_ROOT.parent, MOBILE_ROOT):
        try:
            return path.relative_to(base).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def build_graph(files: list[Path]) -> dict[Path, Module]:
    graph: dict[Path, Module] = {}
    for path in files:
        graph[path] = parse_module(path, display_path(path))
    return graph


def reachable_files(graph: dict[Path, Module]) -> set[Path]:
    """Files reachable from an entry point by following render edges.

    A file joins the set when something already in the set renders a component
    imported from it. Import alone is not enough -- see the module docstring on
    why `import type { Envelope } from "./ChiaSe"` must not count.
    """
    roots = entry_roots()
    seen: set[Path] = set()
    queue = [r for r in roots if r in graph]
    seen.update(queue)
    while queue:
        current = queue.pop()
        module = graph[current]
        # A registration file hands the chain on by importing (`index.ts` calls
        # `registerRootComponent(App)` and renders nothing). Everywhere else --
        # `App.tsx` included, see `REGISTRATION_FILES` -- only a render counts.
        specs: list[str] = []
        if current.name in REGISTRATION_FILES:
            specs.extend(module.imports.values())
        # A route file's default export is rendered by expo-router itself. A
        # plain import in a route file still counts for nothing -- see the
        # CANARY_ROUTER_IMPORT_ONLY tree.
        if app_root() in current.parents:
            specs.extend(module.default_from)
        specs.extend(spec for spec in module.renders.values() if spec)
        for spec in specs:
            target = resolve(spec, current)
            if target is None or target not in graph or target in seen:
                continue
            seen.add(target)
            queue.append(target)
    return seen


def screen_files(graph: dict[Path, Module]) -> list[Path]:
    """Every `.tsx` under `src/screens` -- the files this gate judges.

    `.ts` siblings there are data and API modules, not screens; they are
    reached by import rather than by render and judging them would report a
    dead screen for every helper a live screen calls through a function.
    """
    roots = (SCREEN_ROOT, rudi_screen_root())
    return sorted(
        p for p in graph if p.suffix == ".tsx" and any(r in p.parents for r in roots)
    )


def load_pins() -> dict[str, str]:
    if not PIN_PATH.is_file():
        return {}
    raw = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    entries = raw.get("screens", raw) if isinstance(raw, dict) else raw
    pins: dict[str, str] = {}
    for entry in entries:
        path = entry["path"]
        reason = entry.get("reason", "").strip()
        if not reason:
            raise ValueError(f"{path}: pin thiếu `reason`")
        pins[path] = reason
    return pins


@dataclass
class Finding:
    rel: str
    kind: str  # "unrendered" | "stale_pin"
    detail: str


def check(graph: dict[Path, Module] | None = None) -> tuple[list[Finding], dict]:
    graph = build_graph(source_files()) if graph is None else graph
    live = reachable_files(graph)
    screens = screen_files(graph)
    pins = load_pins()

    findings: list[Finding] = []
    dead: list[str] = []
    for path in screens:
        rel = graph[path].rel
        if path in live:
            continue
        dead.append(rel)
        if rel in pins:
            continue
        findings.append(
            Finding(
                rel=rel,
                kind="unrendered",
                detail="không file nào đang sống render màn này",
            )
        )

    # A pin that no longer describes anything is a claim nobody rechecked. It
    # goes red so the file cannot quietly outlive the thing it excused.
    for rel in sorted(pins):
        if rel not in dead:
            findings.append(
                Finding(
                    rel=rel,
                    kind="stale_pin",
                    detail="đã có màn gọi, gỡ pin khỏi .screens-unrendered.json",
                )
            )

    stats = {
        "screens": len(screens),
        "reachable": len(screens) - len(dead),
        "unrendered": len(dead),
        "pinned": len(pins),
        "files_scanned": len(graph),
    }
    return findings, stats


# ------------------------------------------------------------------- canary


CANARY_LIVE = {
    "index.ts": 'import { App } from "./App";\nexport default App;\n',
    "App.tsx": (
        'import { Sang } from "./src/screens/Sang";\n'
        'import type { Kieu } from "./src/screens/Toi";\n'
        "// Prose naming <Toi> the way this codebase writes about itself.\n"
        'const s = "<Toi />";\n'
        "export function App() {\n"
        "  return <Sang k={null as Kieu | null} />;\n"
        "}\n"
    ),
    "src/screens/Sang.tsx": "export function Sang(_: unknown) {\n  return null;\n}\n",
}

# The same tree with one screen nothing renders. `Toi.tsx` is imported for its
# type by `App.tsx` and named in a comment and a string there -- so a reader
# that counts mentions, or that counts imports, calls it alive. It is not.
CANARY_DEAD = dict(CANARY_LIVE)
CANARY_DEAD["src/screens/Toi.tsx"] = (
    "export type Kieu = { a: number };\nexport function Toi() {\n  return null;\n}\n"
)

# The regression canary for the bug this gate shipped with for one draft, and
# the reason `REGISTRATION_FILES` is `index.ts` alone.
#
# Here `App.tsx` imports `Toi` as a VALUE -- not a type -- and never renders it.
# The first draft let an entry file's plain imports carry the chain, so this
# tree came back GREEN with a screen nobody could open. Caught by deleting the
# real `<ChiaSe />` render from `App.tsx` and watching the gate stay green;
# written down here so it cannot come back in silence.
CANARY_IMPORT_ONLY = dict(CANARY_LIVE)
CANARY_IMPORT_ONLY["src/screens/Toi.tsx"] = (
    "export function Toi() {\n  return null;\n}\n"
)
CANARY_IMPORT_ONLY["App.tsx"] = (
    'import { Sang } from "./src/screens/Sang";\n'
    'import { Toi } from "./src/screens/Toi";\n'
    "export function App() {\n"
    "  return <Sang />;\n"
    "}\n"
)


# The shell that ships: no `index.ts`, `main` is `expo-router/entry`, and a route
# file re-exports the screen. `Sang` must read live through that re-export alone.
CANARY_ROUTER_LIVE = {
    "package.json": '{"main": "expo-router/entry"}\n',
    "app/sang.tsx": 'export { Sang as default } from "../src/rudi/screens/Sang";\n',
    "app/legacy.tsx": (
        'import { LegacyEntry } from "../src/rudi/LegacyEntry";\n'
        "export default LegacyEntry;\n"
    ),
    "src/rudi/LegacyEntry.tsx": (
        'import { lazy } from "react";\n'
        'const LegacyApp = lazy(() => import("../../App"));\n'
        "export function LegacyEntry() {\n  return <LegacyApp />;\n}\n"
    ),
    "App.tsx": (
        'import { Cu } from "./src/screens/Cu";\n'
        "export function App() {\n  return <Cu />;\n}\n"
    ),
    "src/screens/Cu.tsx": "export function Cu() {\n  return null;\n}\n",
    "src/rudi/screens/Sang.tsx": "export function Sang() {\n  return null;\n}\n",
}

# Same shell, plus a RuDi screen no route file exports: it must be the one and
# only dead screen, and the legacy `Cu` reached through `lazy(import)` must NOT be.
CANARY_ROUTER_DEAD = dict(CANARY_ROUTER_LIVE)
CANARY_ROUTER_DEAD["src/rudi/screens/Toi.tsx"] = (
    "export function Toi() {\n  return null;\n}\n"
)

# A route file that merely imports a screen hands nothing to expo-router. Same
# trap as CANARY_IMPORT_ONLY, one level up.
CANARY_ROUTER_IMPORT_ONLY = dict(CANARY_ROUTER_DEAD)
CANARY_ROUTER_IMPORT_ONLY["app/sang.tsx"] = (
    'import { Toi } from "../src/rudi/screens/Toi";\n'
    'export { Sang as default } from "../src/rudi/screens/Sang";\n'
)


def _write_canary(root: Path, files: dict[str, str]) -> None:
    for rel, body in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")


def _check_canary(root: Path) -> tuple[list[Finding], dict]:
    """Run the real reader against a canary tree by repointing the roots."""
    global MOBILE_ROOT, SCREEN_ROOT, PIN_PATH
    saved = (MOBILE_ROOT, SCREEN_ROOT, PIN_PATH)
    MOBILE_ROOT = root
    SCREEN_ROOT = root / "src" / "screens"
    PIN_PATH = root / ".screens-unrendered.json"
    try:
        return check()
    finally:
        MOBILE_ROOT, SCREEN_ROOT, PIN_PATH = saved


def selftest() -> int:
    """Prove the gate goes red on a dead screen and green on a live one.

    Both halves matter and the order is the point. A gate that only ever runs
    the clean case reports zero findings whether it works or whether it is
    blind, and this repository has shipped that mistake more than once -- a
    scanner with no browser returns `[]` and exit 0, which reads exactly like a
    clean page. The dead canary has to be RED before the zero on the real tree
    means anything.
    """
    import tempfile

    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "dead"
        _write_canary(root, CANARY_DEAD)
        findings, stats = _check_canary(root)
        dead_hits = [f for f in findings if f.kind == "unrendered"]
        if len(dead_hits) == 1 and dead_hits[0].rel.endswith("src/screens/Toi.tsx"):
            print(f"canary CHẾT: ĐỎ đúng 1 màn ({dead_hits[0].rel}) — {stats}")
        else:
            print(
                f"canary CHẾT: SAI, mong đúng 1 finding cho Toi.tsx, nhận {findings} — {stats}"
            )
            ok = False

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "chi-import"
        _write_canary(root, CANARY_IMPORT_ONLY)
        findings, stats = _check_canary(root)
        hits = [f for f in findings if f.kind == "unrendered"]
        if len(hits) == 1 and hits[0].rel.endswith("src/screens/Toi.tsx"):
            print(f"canary CHỈ-IMPORT: ĐỎ đúng 1 màn ({hits[0].rel}) — {stats}")
        else:
            print(
                "canary CHỈ-IMPORT: SAI — App.tsx import màn này mà không render,"
                f" phải ĐỎ. Nhận {findings} — {stats}"
            )
            ok = False

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "live"
        _write_canary(root, CANARY_LIVE)
        findings, stats = _check_canary(root)
        if not findings:
            print(f"canary SỐNG: XANH, 0 finding — {stats}")
        else:
            print(f"canary SỐNG: SAI, mong 0 finding, nhận {findings} — {stats}")
            ok = False

    for label, tree, want_dead in (
        ("ROUTER SỐNG", CANARY_ROUTER_LIVE, None),
        ("ROUTER CHẾT", CANARY_ROUTER_DEAD, "src/rudi/screens/Toi.tsx"),
        ("ROUTER CHỈ-IMPORT", CANARY_ROUTER_IMPORT_ONLY, "src/rudi/screens/Toi.tsx"),
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "router"
            _write_canary(root, tree)
            findings, stats = _check_canary(root)
            hits = [f for f in findings if f.kind == "unrendered"]
            if want_dead is None and not findings:
                print(f"canary {label}: XANH, 0 finding — {stats}")
            elif want_dead and len(hits) == 1 and hits[0].rel.endswith(want_dead):
                print(f"canary {label}: ĐỎ đúng 1 màn ({hits[0].rel}) — {stats}")
            else:
                print(f"canary {label}: SAI, nhận {findings} — {stats}")
                ok = False

    if ok:
        print("selftest ĐẠT: cổng đỏ được khi có màn chết, và xanh khi không có.")
        return 0
    print("selftest HỎNG: đừng tin con số của cổng này.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Màn nào không có gì render?")
    parser.add_argument("--json", action="store_true", help="in findings dạng JSON")
    parser.add_argument("--selftest", action="store_true", help="tự kiểm bằng canary")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    if not MOBILE_ROOT.is_dir():
        # `apps/mobile` is absent on some checkouts by design (see CLAUDE.md).
        # Skipping is honest; claiming a pass is not.
        print("apps/mobile không có trong cây này — BỎ QUA, không phải ĐẠT")
        return 0

    try:
        findings, stats = check()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"không chạy được: {exc}", file=sys.stderr)
        return 2

    # Zero screens is the green-because-nothing-ran shape, and this gate must
    # never hand it out: with no file to read, every screen is trivially
    # reachable and the run prints "0/0" and exits 0 -- indistinguishable from a
    # clean tree. Could not run is not a pass.
    if stats["screens"] == 0:
        print(
            f"không đọc được màn nào dưới {SCREEN_ROOT} — cổng này không kết luận"
            " được, và 0/0 không phải ĐẠT",
            file=sys.stderr,
        )
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "stats": stats,
                    "findings": [
                        {"path": f.rel, "kind": f.kind, "detail": f.detail}
                        for f in findings
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if findings else 0

    print(
        f"{stats['reachable']}/{stats['screens']} màn có đường render từ cửa vào"
        f" · {stats['pinned']} pin · {stats['files_scanned']} file đã đọc"
    )
    if not findings:
        return 0
    print("")
    for finding in findings:
        print(f"  {finding.rel}: {finding.detail}")
    print("")
    print(
        "Màn không ai render là màn không ai mở được. Nối nó vào chỗ gọi, hoặc"
        f" ghi lý do vào {PIN_PATH.relative_to(REPO_ROOT)} nếu nó cố ý nằm chờ."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
