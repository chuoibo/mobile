#!/usr/bin/env python3
"""Every header and method the app sends must survive the API's CORS preflight.

## Why this exists

`services/api/app/api/cors.py` is careful, and every test that guards it reads
the **server**:

    test_allowed_headers_covers_every_header_the_server_itself_demands()
    test_allowed_methods_covers_every_method_the_routers_expose()

Both derive the expected set from `services/api`. Nothing derives it from the
side that actually sends the bytes -- `apps/mobile/src`. So the one failure
this policy exists to prevent is the one nothing looks for: the client starts
sending a header, the allowlist does not know about it, and the browser
cancels the request at the preflight before a single line of either codebase
runs.

That is not hypothetical. `cors.py` records it happening already, in its own
comment on `Idempotency-Key`:

    "Leaving it out made the API refuse a header it requires -- the browser
     cancelled every write at the preflight, so the web build could not name a
     person or file an expense at all."

Every gate in this repository stayed green through that, and they would stay
green through the next one, because none of them is a browser:

  - `services/api/tests` uses Starlette's `TestClient`, which speaks to the app
    in-process. It can *assert* CORS headers, and it does -- but only for the
    origins, headers and methods the test itself names.
  - `apps/mobile` tests inject a `fetchImpl`. Node's `fetch` does not enforce
    CORS, so a call that a browser would refuse returns 200 here.
  - `scripts/e2e_slice.sh` runs the vertical slice on node, for the same
    reason and with the same blindness. Its own header says so.
  - `expo export` builds the bundle. It never issues a request.

So the two halves of a *preflight* are compared nowhere, exactly as the two
halves of a *path* were compared nowhere until `check_api_contract.py`. This is
that gate, for the other half of the request line.

## What it checks

Two things, both offline, both derived rather than typed by hand:

1.  Every header name `apps/mobile/src` puts on a request is either in
    `app.api.cors.ALLOWED_HEADERS` or CORS-safelisted.
2.  Every HTTP method it sends is either in `app.api.cors.ALLOWED_METHODS` or
    CORS-safelisted.

The server side is imported from `app.api.cors`, never copied here. A copy is a
third thing to drift, and the drift would be invisible in precisely the
direction that matters.

## About the safelist

The Fetch standard lets four request headers through with no allowlist entry:
`Accept`, `Accept-Language`, `Content-Language`, `Content-Type`. Three of them
are treated as free here. `Content-Type` is **not**, and that is deliberate:
it is only safelisted for three media types, and `application/json` -- what
every write in this app sends -- is not one of them. Treating it as free would
make this gate agree that a JSON write is fine when the browser would refuse
it. It is in `ALLOWED_HEADERS` today, so nothing changes but the reasoning.

Methods are safelisted the same way: `GET`, `HEAD` and `POST` need no entry.

## What it does NOT prove

- That a browser was ever run. It reads two trees. A running server with a
  different `MOBILE_CORS_ALLOW_ORIGINS` can still refuse the origin the web
  build is served from -- that is a deployment question and this is not it.
- That the *origin* is allowed. Only headers and methods.
- That a request succeeds. A preflight that passes says the browser will
  forward the request, nothing about the answer.
- Anything about headers a *third party* is sent. `screens/kham-pha/places.ts`
  talks to a places service, not this API, and its `Accept` header is judged
  here anyway. Being wrong in that direction is loud and cheap to fix; being
  wrong in the other direction is the bug this file exists for.

## Reading a call site it cannot follow

A header object it cannot resolve is a **finding**, not a silence. That is the
lesson `check_api_contract.py` paid for: until 2026-08-30 an unfollowable call
site there contributed a number to a summary nobody asserted on, and a route
that never existed exited 0. Here, an unresolved header position fails the run
and names the file and line.

## Usage

  scripts/check_cors_contract.py
  scripts/check_cors_contract.py --json
  scripts/check_cors_contract.py --selftest   # the canaries; run this first
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "services" / "api"
CLIENT_DIR = REPO_ROOT / "apps" / "mobile" / "src"

# Exit 2, not 1. "Could not run" and "ran and found a problem" are different
# answers, and collapsing them is how a dead gate reads as a failing one.
EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_CANNOT_RUN = 2

# Fetch standard, CORS-safelisted request-header names. `content-type` is
# excluded on purpose -- see the module docstring.
SAFELISTED_HEADERS = frozenset({"accept", "accept-language", "content-language"})

# Fetch standard, CORS-safelisted methods.
SAFELISTED_METHODS = frozenset({"GET", "HEAD", "POST"})


def die(message: str) -> None:
    """Report that the check could not run, and exit 2."""
    print(f"check_cors_contract: {message}", file=sys.stderr)
    raise SystemExit(EXIT_CANNOT_RUN)


# --------------------------------------------------------------- source scan


def _strip_to_spaces(src: str, blank_strings: bool = True) -> str:
    """Blank out comments -- and string bodies too, when asked -- keeping offsets.

    Two views of one file are needed, and conflating them was this reader's
    first bug. Brace matching needs string bodies gone, because a `{` inside a
    template literal desynchronises it. Reading a header *name* needs them
    kept, because the name IS the string body: with both views collapsed into
    one, `headers["Authorization"] = ...` and `method: "PATCH"` were matched
    against a run of spaces and the gate answered clean. Two canaries below
    hold that shut.

    Strings are still parsed in both modes, never merely skipped: a `//` inside
    `"http://x"` is not a comment, and treating it as one silently deletes the
    rest of the line.
    """
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            while i < n and not (src[i] == "*" and i + 1 < n and src[i + 1] == "/"):
                if src[i] != "\n":
                    out[i] = " "
                i += 1
            for j in range(i, min(i + 2, n)):
                out[j] = " "
            i += 2
            continue
        if ch in "\"'`":
            quote = ch
            i += 1
            while i < n:
                if src[i] == "\\":
                    if blank_strings:
                        out[i] = " "
                        if i + 1 < n:
                            out[i + 1] = " "
                    i += 2
                    continue
                if src[i] == quote:
                    break
                # A `${` inside a template literal is real code; leaving it
                # blanked would hide a brace and desynchronise the matcher.
                if quote == "`" and src[i] == "$" and i + 1 < n and src[i + 1] == "{":
                    depth = 0
                    while i < n:
                        if src[i] == "{":
                            depth += 1
                        elif src[i] == "}":
                            depth -= 1
                            if depth == 0:
                                i += 1
                                break
                        i += 1
                    continue
                if blank_strings and src[i] != "\n":
                    out[i] = " "
                i += 1
        i += 1
    return "".join(out)


def _match_brace(blank: str, open_idx: int) -> int:
    """Index just past the `}` closing the `{` at `open_idx`, or -1."""
    depth = 0
    for i in range(open_idx, len(blank)):
        if blank[i] == "{":
            depth += 1
        elif blank[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    return -1


_KEY = re.compile(
    r"""^\s*(?:"(?P<dq>[^"]+)"|'(?P<sq>[^']+)'|(?P<bare>[A-Za-z_$][\w$]*))\s*:"""
)


def _literal_keys(
    text: str, blank: str, start: int, end: int
) -> tuple[list[str], bool]:
    """Top-level keys of the object literal spanning [start, end).

    `blank` drives the structure (commas at depth 1) and `text` supplies the
    names, so `text` must be the comment-blanked view rather than the raw
    source: a key sitting behind `/* ... */` inside the literal makes the
    anchored key pattern miss, and missing a key here is the gate going quiet.

    Returns the keys and whether the literal spreads something in. A spread is
    not resolved here; the caller decides what an unresolved contribution means.
    """
    keys: list[str] = []
    has_spread = False
    depth = 0
    piece_start = start + 1
    for i in range(start, end):
        c = blank[i]
        if c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
            if depth == 0:  # the closing brace of this literal
                pieces = [(piece_start, i)]
                piece_start = i
                for a, b in pieces:
                    chunk = text[a:b]
                    if "..." in blank[a:b]:
                        has_spread = True
                    m = _KEY.match(chunk)
                    if m:
                        keys.append(m.group("dq") or m.group("sq") or m.group("bare"))
                break
        elif c == "," and depth == 1:
            chunk = text[piece_start:i]
            if "..." in blank[piece_start:i]:
                has_spread = True
            m = _KEY.match(chunk)
            if m:
                keys.append(m.group("dq") or m.group("sq") or m.group("bare"))
            piece_start = i + 1
    return keys, has_spread


# `headers:` as an object property, and the shorthand `headers,` / `headers }`.
_HEADERS_PROP = re.compile(r"(?<![\w$.])headers\s*(?P<sep>:|,|\})")
# A function whose name ends in `headers`/`Headers`: it exists to build them.
_HEADERS_FN = re.compile(r"(?<![\w$])function\s+(?P<name>[\w$]*[Hh]eaders)\s*\(")
# `h["Idempotency-Key"] = ...` / `headers["X"] = ...`
_BRACKET_SET = re.compile(
    r"(?<![\w$.])(?P<obj>[\w$]+)\s*\[\s*[\"'](?P<key>[\w-]+)[\"']\s*\]\s*="
)
# `const h = {` / `const chatHeaders = {`. Which names count is decided per
# file by `_header_vars`, not by this pattern.
_HEADER_CONST = re.compile(
    r"(?<![\w$])const\s+(?P<name>[\w$]+)\s*(?::[^=;]*)?=\s*(?P<eq>)"
)
# The one-letter name is only a header object when it says so in its type.
# Without this the reader claimed `const h = hex.replace(...)` in
# `navigation/Gradient.tsx` and three more like it were unreadable header
# positions -- four findings on a tree the browser is fine with.
_ANNOTATED_H = re.compile(
    r"(?<![\w$])const\s+h\s*:\s*Record\s*<\s*string\s*,\s*string\s*>"
)
_METHOD = re.compile(r"(?<![\w$.])method\s*[:=]\s*[\"'](?P<m>[A-Za-z]+)[\"']")
_IDENT = re.compile(r"[A-Za-z_$][\w$]*")
_DECL_BEFORE = re.compile(r"(?<![\w$])(?:const|let|var)\s+$")


def _enclosing_bracket(blank: str, idx: int) -> str | None:
    """The innermost bracket still open at `idx`: `{`, `(`, `[` or None.

    This is what tells a header *property* from a header-shaped *type
    annotation*. `headers: Record<string, string>` in a parameter list is
    enclosed by `(`; `headers: {...}` handed to `fetch` is enclosed by `{`.
    Reading the first as a call site produced two findings on a tree where the
    browser is perfectly happy, and a gate that cries on correct code gets
    switched off, which is the same outcome as not having one.
    """
    stack: list[str] = []
    for i in range(idx):
        c = blank[i]
        if c in "{([":
            stack.append(c)
        elif c in "})]":
            if stack:
                stack.pop()
    return stack[-1] if stack else None


@dataclass
class Finding:
    file: str
    line: int
    kind: str
    message: str


@dataclass
class ClientFacts:
    headers: dict[str, str] = field(default_factory=dict)  # name -> "file:line"
    methods: dict[str, str] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    literal_sites: int = 0
    indirect_sites: int = 0
    files_read: int = 0


def _line_of(src: str, idx: int) -> int:
    return src.count("\n", 0, idx) + 1


def _source_files(root: Path) -> list[Path]:
    out = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in (".ts", ".tsx"):
            continue
        if ".test." in path.name or "__tests__" in path.parts:
            continue
        out.append(path)
    return out


def read_client(root: Path) -> ClientFacts:
    """Header names and methods `root` puts on requests."""
    facts = ClientFacts()
    for path in _source_files(root):
        src = path.read_text(encoding="utf-8", errors="replace")
        # Structure comes from `blank` (strings gone, braces trustworthy);
        # every NAME comes from `named` (comments gone, strings intact).
        blank = _strip_to_spaces(src)
        named = _strip_to_spaces(src, blank_strings=False)
        rel = (
            str(path.relative_to(REPO_ROOT))
            if path.is_relative_to(REPO_ROOT)
            else path.name
        )
        facts.files_read += 1

        # Names bound from a header-producing function, so `...headers` and
        # `headers,` shorthand can be resolved instead of reported.
        producers = {m.group("name") for m in _HEADERS_FN.finditer(blank)}
        producers.add("headers")
        bound: set[str] = set()
        for m in re.finditer(
            r"(?<![\w$])(?:const|let|var)\s+(?P<lhs>[^=;]+)=(?P<rhs>[^;\n]*)", blank
        ):
            if any(p in m.group("rhs") for p in producers):
                bound.update(_IDENT.findall(m.group("lhs")))
        # Names that hold a header object in THIS file: something that builds
        # them, something bound from one, or the one-letter name when its type
        # annotation says what it is. Deciding by name alone read four
        # unrelated `const h = ...` in this tree as header positions.
        header_vars = set(producers) | bound
        if _ANNOTATED_H.search(blank):
            header_vars.add("h")

        def record(keys: list[str], at: int) -> None:
            for key in keys:
                facts.headers.setdefault(key, f"{rel}:{_line_of(src, at)}")

        # 1. `headers: {...}` -- the literal handed straight to fetch.
        for m in _HEADERS_PROP.finditer(blank):
            sep = m.group("sep")
            if sep != ":":
                # Shorthand `{ ..., headers, body }`. Resolvable only if this
                # file binds `headers` from something that builds them.
                if "headers" not in bound:
                    facts.indirect_sites += 1
                    facts.findings.append(
                        Finding(
                            rel,
                            _line_of(src, m.start()),
                            "vi_tri_header_khong_doc_duoc",
                            "`headers` shorthand không truy được về chỗ dựng header "
                            "nào trong file này.",
                        )
                    )
                else:
                    facts.indirect_sites += 1
                continue
            # Two shapes wear a colon without being a header object. A
            # declaration (`const headers: Record<string, string> = ...`)
            # carries its value after the `=`, read by rule 3 below; a
            # parameter (`headers: Record<string, string>,`) carries no value
            # at all and its caller is what supplies the names.
            if _DECL_BEFORE.search(blank[max(0, m.start() - 12) : m.start()]):
                continue
            if _enclosing_bracket(blank, m.start()) == "(":
                continue

            rest = blank[m.end() :]
            offset = len(rest) - len(rest.lstrip())
            open_idx = m.end() + offset
            if open_idx < len(blank) and blank[open_idx] == "{":
                end = _match_brace(blank, open_idx)
                if end == -1:
                    facts.findings.append(
                        Finding(
                            rel,
                            _line_of(src, open_idx),
                            "vi_tri_header_khong_doc_duoc",
                            "object literal của `headers:` không đóng ngoặc được.",
                        )
                    )
                    continue
                keys, _ = _literal_keys(named, blank, open_idx, end)
                facts.literal_sites += 1
                record(keys, open_idx)
            else:
                expr = blank[m.end() : m.end() + 200].split(";")[0].split("\n")[0]
                idents = set(_IDENT.findall(expr))
                facts.indirect_sites += 1
                if not (idents & producers) and not (idents & bound):
                    facts.findings.append(
                        Finding(
                            rel,
                            _line_of(src, m.start()),
                            "vi_tri_header_khong_doc_duoc",
                            f"`headers:` nhận `{expr.strip()[:60]}` — không truy được "
                            "về chỗ dựng header nào trong file này.",
                        )
                    )

        # 2. Every `return {...}` inside a function that builds headers.
        for m in _HEADERS_FN.finditer(blank):
            body_open = blank.find("{", m.end())
            if body_open == -1:
                continue
            body_end = _match_brace(blank, body_open)
            if body_end == -1:
                continue
            for r in re.finditer(r"(?<![\w$])return\s*\{", blank[body_open:body_end]):
                open_idx = body_open + r.end() - 1
                end = _match_brace(blank, open_idx)
                if end == -1:
                    continue
                keys, _ = _literal_keys(named, blank, open_idx, end)
                facts.literal_sites += 1
                record(keys, open_idx)

        # 3. `const h: Record<string, string> = { ... }`
        for m in _HEADER_CONST.finditer(blank):
            if m.group("name") not in header_vars:
                continue
            rest = blank[m.end() :]
            offset = len(rest) - len(rest.lstrip())
            open_idx = m.end() + offset
            if open_idx < len(blank) and blank[open_idx] == "{":
                end = _match_brace(blank, open_idx)
                if end == -1:
                    continue
                keys, _ = _literal_keys(named, blank, open_idx, end)
                facts.literal_sites += 1
                record(keys, open_idx)
            else:
                # `const headers = actorId ? actorHeaders(a) : {...}`. The
                # ternary is real: api.ts:280. Read any literal branch, and
                # still require the whole thing to trace back to something
                # that builds headers.
                stmt = blank[open_idx : open_idx + 400].split(";")[0]
                brace = stmt.find("{")
                resolved = bool(set(_IDENT.findall(stmt)) & (producers | bound))
                if brace != -1:
                    lit = open_idx + brace
                    end = _match_brace(blank, lit)
                    if end != -1:
                        keys, _ = _literal_keys(named, blank, lit, end)
                        facts.literal_sites += 1
                        record(keys, lit)
                        resolved = True
                facts.indirect_sites += 1
                if not resolved:
                    facts.findings.append(
                        Finding(
                            rel,
                            _line_of(src, m.start()),
                            "vi_tri_header_khong_doc_duoc",
                            f"`{m.group('name')}` nhận `{stmt.strip()[:60]}` — không "
                            "truy được về chỗ dựng header nào trong file này.",
                        )
                    )

        # 4. `h["Idempotency-Key"] = key`
        for m in _BRACKET_SET.finditer(named):
            if m.group("obj") not in header_vars:
                continue
            facts.literal_sites += 1
            facts.headers.setdefault(
                m.group("key"), f"{rel}:{_line_of(src, m.start())}"
            )

        # 5. Methods.
        for m in _METHOD.finditer(named):
            facts.methods.setdefault(
                m.group("m").upper(), f"{rel}:{_line_of(src, m.start())}"
            )

    return facts


# --------------------------------------------------------------- server side


def server_policy(api_dir: Path) -> dict[str, list[str]]:
    """`ALLOWED_HEADERS` and `ALLOWED_METHODS`, imported rather than copied."""
    if not api_dir.is_dir():
        die(f"không thấy {api_dir} — chạy từ trong repo.")
    code = (
        "import json;from app.api.cors import ALLOWED_HEADERS, ALLOWED_METHODS;"
        "print(json.dumps({'headers':list(ALLOWED_HEADERS),"
        "'methods':list(ALLOWED_METHODS)}))"
    )
    try:
        out = subprocess.run(
            [sys.executable, "-c", code],
            cwd=api_dir,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover
        die(f"không đọc được chính sách CORS từ {api_dir}: {exc}")
    if out.returncode != 0:
        die(
            "không import được app.api.cors "
            f"(mã {out.returncode}):\n{out.stderr.strip()[-2000:]}"
        )
    try:
        policy = json.loads(out.stdout)
    except json.JSONDecodeError as exc:
        die(f"app.api.cors trả về thứ không phải JSON: {exc}")
    if not policy.get("headers") or not policy.get("methods"):
        die("app.api.cors khai allowlist rỗng — cổng này sẽ không đo được gì.")
    return policy


# ------------------------------------------------------------------ compare


def compare(facts: ClientFacts, policy: dict[str, list[str]]) -> list[Finding]:
    """Findings from the client facts against the server policy."""
    allowed_headers = {h.lower() for h in policy["headers"]}
    allowed_methods = {m.upper() for m in policy["methods"]}
    findings = list(facts.findings)

    for name, where in sorted(facts.headers.items()):
        low = name.lower()
        if low in SAFELISTED_HEADERS or low in allowed_headers:
            continue
        file, _, line = where.rpartition(":")
        findings.append(
            Finding(
                file,
                int(line),
                "header_khong_qua_duoc_preflight",
                f"client gửi `{name}` mà ALLOWED_HEADERS không có và Fetch không "
                "safelist. Trình duyệt huỷ request ở preflight.",
            )
        )

    for method, where in sorted(facts.methods.items()):
        if method in SAFELISTED_METHODS or method in allowed_methods:
            continue
        file, _, line = where.rpartition(":")
        findings.append(
            Finding(
                file,
                int(line),
                "method_khong_qua_duoc_preflight",
                f"client gửi `{method}` mà ALLOWED_METHODS không có. Trình duyệt "
                "huỷ request ở preflight.",
            )
        )
    return findings


def run(client_dir: Path, api_dir: Path, as_json: bool) -> int:
    facts = read_client(client_dir)

    # A reader that read nothing is not a clean tree. This is the whole
    # difference between "sạch" and "máy quét chết", and every gate in this
    # repository that skipped it has been wrong at least once.
    if facts.files_read == 0:
        die(f"không đọc được file .ts/.tsx nào dưới {client_dir}.")
    if facts.literal_sites == 0:
        die(
            f"đọc {facts.files_read} file nhưng không thấy chỗ dựng header nào. "
            "Client đổi cách viết header, hoặc reader này đã mù."
        )
    if not facts.headers:
        die("không rút được tên header nào — cổng này đang mù, không phải sạch.")

    policy = server_policy(api_dir)
    findings = compare(facts, policy)

    if as_json:
        print(
            json.dumps(
                {
                    "headers_client_gui": sorted(facts.headers),
                    "methods_client_gui": sorted(facts.methods),
                    "allowed_headers": sorted(h.lower() for h in policy["headers"]),
                    "allowed_methods": sorted(policy["methods"]),
                    "file_da_doc": facts.files_read,
                    "vi_tri_literal": facts.literal_sites,
                    "vi_tri_gian_tiep": facts.indirect_sites,
                    "findings": [f.__dict__ for f in findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(
            f"Client gửi {len(facts.headers)} header và {len(facts.methods)} method, "
            f"đọc từ {facts.literal_sites} chỗ dựng header trong {facts.files_read} "
            f"file ({facts.indirect_sites} chỗ gián tiếp đã truy được)."
        )
        print(f"  header: {', '.join(sorted(facts.headers))}")
        print(f"  method: {', '.join(sorted(facts.methods))}")

    if not findings:
        if not as_json:
            print("Mọi header và method client gửi đều qua được preflight.")
        return EXIT_OK

    if not as_json:
        print()
        for f in findings:
            print(f"{f.file}:{f.line}  [{f.kind}]")
            print(f"    {f.message}")
        print()
        print(f"{len(findings)} chỗ client sẽ bị trình duyệt chặn ở preflight.")
    return EXIT_MISMATCH


# ----------------------------------------------------------------- selftest

# Each canary is a synthetic client tree plus the exit code this gate has to
# answer with. A gate that cannot be red is decoration; these are what make the
# green run above mean something.
CANARIES: list[tuple[str, str, int]] = [
    (
        "sach",
        """
        function actorHeaders(a: string): Record<string, string> {
          return { "Content-Type": "application/json", "X-Actor-ID": a };
        }
        export async function go(a: string) {
          const h = actorHeaders(a);
          h["Idempotency-Key"] = "k";
          return fetch("/x", { method: "POST", headers: h });
        }
        """,
        EXIT_OK,
    ),
    (
        "header-la-trong-literal",
        """
        export async function go(a: string) {
          return fetch("/x", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Trace-Id": a },
          });
        }
        """,
        EXIT_MISMATCH,
    ),
    (
        "header-la-gan-bang-ngoac-vuong",
        """
        function actorHeaders(a: string): Record<string, string> {
          return { "X-Actor-ID": a };
        }
        export async function go(a: string) {
          const headers = actorHeaders(a);
          headers["Authorization"] = "Bearer x";
          return fetch("/x", { method: "POST", headers });
        }
        """,
        EXIT_MISMATCH,
    ),
    (
        "header-la-trong-ham-dung-header",
        """
        function chatHeaders(a: string): Record<string, string> {
          const h: Record<string, string> = { "X-Actor-ID": a, "X-Client-Build": "7" };
          return h;
        }
        export async function go(a: string) {
          return fetch("/x", { headers: chatHeaders(a) });
        }
        """,
        EXIT_MISMATCH,
    ),
    (
        "method-la",
        """
        export async function go(a: string) {
          return fetch("/x", { method: "PATCH", headers: { "X-Actor-ID": a } });
        }
        """,
        EXIT_MISMATCH,
    ),
    (
        "header-nam-sau-template-literal",
        # A `${...}` in a URL used to desynchronise the brace matcher, which
        # would drop every header after it and read as clean.
        """
        export async function go(a: string, id: string) {
          return fetch(`/x/${id}/y`, {
            method: "POST",
            headers: { "X-Actor-ID": a, "X-Sneaky": "1" },
          });
        }
        """,
        EXIT_MISMATCH,
    ),
    (
        "header-la-bi-comment-che",
        # A header name mentioned only inside a comment must NOT be a finding,
        # and a real one after it must still be read.
        """
        export async function go(a: string) {
          // "X-Not-Real": never sent, just discussed
          /* "X-Also-Not-Real": same */
          return fetch("/x", { headers: { "X-Actor-ID": a } });
        }
        """,
        EXIT_OK,
    ),
    (
        "khong-co-cho-dung-header-nao",
        # The blindness case: a tree this reader cannot see into must be
        # "cannot run", never "clean".
        """
        export const x = 1;
        """,
        EXIT_CANNOT_RUN,
    ),
    (
        "accept-duoc-safelist",
        # Accept is CORS-safelisted; flagging it would make the gate noise.
        """
        export async function go() {
          return fetch("/x", { headers: { Accept: "application/json" } });
        }
        """,
        EXIT_OK,
    ),
]


def selftest(api_dir: Path) -> int:
    """Run every canary and report which of them the gate answered wrong."""
    policy = server_policy(api_dir)
    failures: list[str] = []
    for name, source, want in CANARIES:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "src"
            root.mkdir()
            (root / "canary.ts").write_text(source, encoding="utf-8")
            try:
                facts = read_client(root)
                if (
                    facts.files_read == 0
                    or facts.literal_sites == 0
                    or not facts.headers
                ):
                    got = EXIT_CANNOT_RUN
                else:
                    got = EXIT_MISMATCH if compare(facts, policy) else EXIT_OK
            except SystemExit as exc:
                got = int(exc.code or 0)
        mark = "ok  " if got == want else "SAI "
        print(f"  {mark} {name}: mong {want}, ra {got}")
        if got != want:
            failures.append(name)
    if failures:
        print(f"self-test HỎNG: {', '.join(failures)}", file=sys.stderr)
        return EXIT_MISMATCH
    print(f"self-test ĐẠT: {len(CANARIES)} canary, cổng đỏ được và xanh được.")
    return EXIT_OK


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="máy đọc")
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="chạy canary: cổng phải đỏ với header lạ và exit 2 khi không đọc được gì",
    )
    parser.add_argument("--client-dir", default=str(CLIENT_DIR))
    args = parser.parse_args()

    if args.selftest:
        return selftest(API_DIR)
    return run(Path(args.client_dir), API_DIR, args.json)


if __name__ == "__main__":
    sys.exit(main())
