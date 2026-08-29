#!/usr/bin/env python3
"""Every route the app calls must exist on the server. Checked offline.

## Why this exists

Nothing in this repository compares the two halves of a request. The server's
tests call the server; the app's tests call a fake. Both stay green while they
disagree, and `src/api.ts` records in its own header comment what that costs:

    "Publishing names its batch. The app called `/batches/current/publish`,
     a route that has never existed."

A call to a route that is not there answers 404 forever. Nothing sees it: the
API suite never calls the app's URL, the mobile suite injects a `fetchImpl`
that answers whatever the test wants, and `tsc` has no opinion about strings.
Measured on 2026-08-29 by putting that exact path back into `api.ts`:
`tsc --noEmit` exited 0 and `npm test` reported 493 passing, 0 failing.

## What it checks

One thing. Path literals in `apps/mobile/src` are normalised (`${x}` and
`{param}` both become the same hole) and matched against the paths FastAPI
itself reports. An unmatched path is a call that can only ever answer 404.

The server side is the *rendered* OpenAPI document, not a list kept by hand. A
list kept by hand is a third copy to drift.

## What it deliberately does not check

Whether a call sends `X-Actor-ID`. That is a real and separate gap -- it cost
the Khám phá screen two hours on `main` the same day -- and it has its own gate
in `scripts/check_actor_headers.py`, which answers it far more thoroughly than
a second copy here would. Two gates that read the same source and can disagree
about it is worse than one gate per question.

## What it does NOT prove

- Nothing here executes a request. Methods, bodies, query parameters, response
  shapes and permission rules are all outside it: a path that exists for GET
  and is called with POST passes. `tests/postgres` and the QA walks are still
  the only things that prove a route does what it says.
- Paths assembled from variables rather than written down are invisible. That
  is why the summary always prints how many it found and how many requests it
  read: paths falling while requests hold steady is this checker going blind,
  and going blind looks exactly like a clean tree.
- It reads the tree it is in. A route that exists only on an unmerged branch
  counts as missing, which is the honest answer for `main` and the confusing
  one on a feature branch waiting for its API.

Usage:
  scripts/check_api_contract.py            check the tree this file is in
  scripts/check_api_contract.py --json     the same findings, machine-readable

Exit codes: 0 client and server agree, 1 they disagree,
2 the check could not run -- and could not run is never a pass.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENT_ROOT = REPO_ROOT / "apps" / "mobile" / "src"
API_ROOT = REPO_ROOT / "services" / "api"

# The placeholder a `${...}` or a `{param}` collapses to. A control character
# so it cannot occur in real source and be mistaken for one.
HOLE = "\x00"

# Names that make an HTTP request directly. `doFetch` is the alias the search
# and places modules use so a test can inject its own implementation.
DIRECT_FETCH = ("fetch", "doFetch")


# --------------------------------------------------------------- tokenizing


@dataclass
class Token:
    kind: str  # "code" | "line_comment" | "block_comment" | "string" | "template"
    start: int
    end: int
    text: str


def tokenize(src: str) -> list[Token]:
    """Split TypeScript into code, comments and literals.

    Written by hand rather than with a parser because the check has to run with
    nothing installed but Python. It only needs to be right about four things:
    where comments are, where string and template literals are, where a `/`
    begins a regular expression rather than a division, and where a `${` inside
    a template returns to code.

    The regex case is not pedantry. `base.replace(/\\/$/, "")` appears in three
    client modules; reading that `/` as division swallows the rest of the line
    into a phantom literal and the paths after it disappear -- a checker going
    quiet on the files it is pointed at.
    """
    tokens: list[Token] = []
    i = 0
    n = len(src)
    # Template literals nest: `${cond ? `a` : `b`}`. Depth of `${` we are in.
    template_stack: list[int] = []

    def last_significant() -> str:
        """The last non-space character of code emitted so far."""
        for tok in reversed(tokens):
            if tok.kind in ("line_comment", "block_comment"):
                continue
            if tok.kind in ("string", "template"):
                return "x"  # a literal is a value, so a following / is division
            stripped = tok.text.rstrip()
            if stripped:
                return stripped[-1]
        return ""

    code_start = 0

    def flush_code(upto: int) -> None:
        if upto > code_start:
            tokens.append(Token("code", code_start, upto, src[code_start:upto]))

    while i < n:
        ch = src[i]

        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            flush_code(i)
            j = src.find("\n", i)
            j = n if j == -1 else j
            tokens.append(Token("line_comment", i, j, src[i:j]))
            i = code_start = j
            continue

        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            flush_code(i)
            j = src.find("*/", i + 2)
            j = n if j == -1 else j + 2
            tokens.append(Token("block_comment", i, j, src[i:j]))
            i = code_start = j
            continue

        if ch in ("'", '"'):
            flush_code(i)
            j = i + 1
            while j < n and src[j] != ch:
                j += 2 if src[j] == "\\" else 1
            j = min(j + 1, n)
            tokens.append(Token("string", i, j, src[i:j]))
            i = code_start = j
            continue

        if ch == "`":
            flush_code(i)
            j, text = _scan_template(src, i)
            tokens.append(Token("template", i, j, text))
            i = code_start = j
            continue

        if ch == "}" and template_stack:
            # Unreachable: `_scan_template` consumes its own `${...}` holes.
            pass

        if ch == "/":
            prev = last_significant()
            # A `/` after a value is division; after an operator, a keyword or
            # an opening bracket it starts a regular expression.
            if prev and (prev.isalnum() or prev in ")]}_$"):
                i += 1
                continue
            j = i + 1
            in_class = False
            while j < n:
                c = src[j]
                if c == "\\":
                    j += 2
                    continue
                if c == "[":
                    in_class = True
                elif c == "]":
                    in_class = False
                elif c == "/" and not in_class:
                    break
                elif c == "\n":
                    # Not a regex after all; treat the `/` as ordinary code.
                    j = i
                    break
                j += 1
            if j == i:
                i += 1
                continue
            i = j + 1
            continue

        i += 1

    flush_code(n)
    return tokens


def _scan_template(src: str, start: int) -> tuple[int, str]:
    """Consume one template literal, returning (end index, raw text)."""
    i = start + 1
    n = len(src)
    while i < n:
        ch = src[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "`":
            return i + 1, src[start : i + 1]
        if ch == "$" and i + 1 < n and src[i + 1] == "{":
            depth = 1
            i += 2
            while i < n and depth:
                c = src[i]
                if c == "`":
                    i, _ = _scan_template(src, i)
                    continue
                if c in ("'", '"'):
                    quote = c
                    i += 1
                    while i < n and src[i] != quote:
                        i += 2 if src[i] == "\\" else 1
                    i += 1
                    continue
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                i += 1
            continue
        i += 1
    return n, src[start:n]


def literal_shape(token: Token) -> str | None:
    """The literal's text with every interpolation replaced by HOLE.

    Returns None for anything that is not a string or template literal.
    """
    if token.kind == "string":
        return token.text[1:-1]
    if token.kind != "template":
        return None
    body = token.text[1:-1] if token.text.endswith("`") else token.text[1:]
    out: list[str] = []
    i = 0
    n = len(body)
    while i < n:
        if body[i] == "\\":
            out.append(body[i : i + 2])
            i += 2
            continue
        if body[i] == "$" and i + 1 < n and body[i + 1] == "{":
            depth = 1
            i += 2
            while i < n and depth:
                if body[i] == "{":
                    depth += 1
                elif body[i] == "}":
                    depth -= 1
                i += 1
            out.append(HOLE)
            continue
        out.append(body[i])
        i += 1
    return "".join(out)


# ------------------------------------------------------------ path handling

# The first segment must be spelled out. `${dd}/${mm}` is a date, not a route,
# and it is the shape three modules use to format one -- an earlier draft of
# this file reported four of them as missing endpoints. A real route always
# names its collection: /contexts, /people, /places.
FIRST_SEGMENT = re.compile(r"^[a-z][a-z0-9-]*$", re.IGNORECASE)


def path_from_shape(shape: str) -> str | None:
    """The API path a literal refers to, or None if it is not one.

    Two spellings occur in this client and both must be understood:
    a bare `/contexts/${id}/members`, and `${base}/contexts/${id}/messages`
    where the base URL is interpolated in front.
    """
    candidate = shape
    if candidate.startswith(HOLE):
        candidate = candidate[len(HOLE) :]
    if not candidate.startswith("/"):
        return None
    candidate = candidate.split("?", 1)[0].split("#", 1)[0]
    segments = candidate[1:].split("/")
    if not segments or not FIRST_SEGMENT.match(segments[0]):
        return None
    if any(" " in segment for segment in segments):
        return None
    return candidate


def normalise(path: str) -> str:
    """Collapse every parameter to HOLE so client and server compare equal."""
    path = re.sub(r"\{[^}]*\}", HOLE, path)
    path = path.rstrip("/") or "/"
    return path


# ------------------------------------------------------------------ server


def load_openapi() -> dict:
    """Render the API's own OpenAPI document. No database, no server running.

    Run in a subprocess with `services/api` as the working directory because
    that is where `pyproject.toml` puts the import root, and importing the app
    into this process would leave its settings loaded for anything that follows.
    """
    program = (
        "import json,sys\n"
        "from app.api.main import create_app\n"
        "sys.stdout.write(json.dumps(create_app().openapi()))\n"
    )
    env = dict(os.environ, PYTHONPATH=str(API_ROOT))
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=API_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-6:]
        raise RuntimeError(
            "không dựng được OpenAPI từ services/api:\n  " + "\n  ".join(tail)
        )
    return json.loads(result.stdout)


@dataclass
class Contract:
    """What the server offers, keyed the way a client path can be looked up."""

    # normalised path -> set of upper-case methods
    routes: dict[str, set[str]] = field(default_factory=dict)
    # normalised path -> the path as the server spells it, for messages
    spelling: dict[str, str] = field(default_factory=dict)


def read_contract(spec: dict) -> Contract:
    contract = Contract()
    for raw_path, operations in spec.get("paths", {}).items():
        key = normalise(raw_path)
        contract.spelling.setdefault(key, raw_path)
        for method, operation in operations.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            contract.routes.setdefault(key, set()).add(method.upper())
    return contract


# ------------------------------------------------------------------ client


def line_of(src: str, offset: int) -> int:
    return src.count("\n", 0, offset) + 1


def client_files() -> list[Path]:
    return sorted(
        p
        for p in CLIENT_ROOT.rglob("*.ts*")
        if p.suffix in (".ts", ".tsx") and not p.name.endswith(".d.ts")
    )


# The functions that actually send a request, and which argument holds the URL
# and which holds the options. `call` and `translated` are the wrappers in
# `src/api.ts`; every screen outside the chat modules goes through them.
REQUEST_FUNCTIONS = {
    "fetch": (0, 1),
    "doFetch": (0, 1),
    "call": (0, 1),
    "translated": (1, 2),
}

CALLEE = re.compile(
    r"(?<![\w$.])(" + "|".join(REQUEST_FUNCTIONS) + r")\s*(?:<[^()]*>)?\s*\("
)

IDENTIFIER = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)")

# How many times an identifier may be replaced by its declaration while looking
# for the literal. `url -> placesUrl(base, opts) -> `${base}/places?...`` is
# three, which is the deepest chain in this client.
MAX_HOPS = 3


@dataclass
class CallSite:
    line: int
    url_text: str
    options_text: str
    wrapper: bool  # went through src/api.ts's `call`/`translated`


def mask(src: str, tokens: list[Token]) -> str:
    """`src` with comments and literal contents blanked, offsets unchanged.

    Every structural scan below runs on this string and then slices the real
    source at the offsets it found. Scanning the token stream directly did not
    work: a literal splits its own statement into three tokens, so
    `const {"Content-Type": _, ...headers} = actorHeaders(actorId)` never
    matched as one declaration and the call that uses `headers` was reported as
    sending no actor. Masking keeps the statement whole while making sure no
    bracket, comma or semicolon inside a comment or a string can be read as
    structure.
    """
    out: list[str] = []
    for token in tokens:
        if token.kind == "code":
            out.append(token.text)
        elif token.kind in ("line_comment", "block_comment"):
            out.append("".join(ch if ch == "\n" else " " for ch in token.text))
        else:
            body = token.text[1:-1] if len(token.text) >= 2 else ""
            filler = "".join("\n" if ch == "\n" else "x" for ch in body)
            out.append(token.text[0] + filler + token.text[-1:])
    return "".join(out)


def end_of_call(masked: str, start: int) -> int | None:
    """Index of the `)` closing a call whose `(` is just before `start`."""
    depth = 1
    for i in range(start, len(masked)):
        if masked[i] == "(":
            depth += 1
        elif masked[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return None


def arg_spans(masked: str, start: int, end: int) -> list[tuple[int, int]]:
    """The (start, end) of each argument between `start` and `end`."""
    spans: list[tuple[int, int]] = []
    depth = 0
    at = start
    for i in range(start, end):
        ch = masked[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            spans.append((at, i))
            at = i + 1
    spans.append((at, end))
    return spans


DECLARATION = re.compile(
    r"(?<![\w$.])(?:function\s+([A-Za-z_$][\w$]*)"
    r"|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=;]+)?="
    r"|(?:const|let|var)\s*(\{[^=]*?\}|\[[^=]*?\])\s*=)"
)


def declarations(src: str, masked: str) -> dict[str, str]:
    """Every `function f` / `const x =` in the file, mapped to its body text.

    The end of a declaration is found by matching brackets rather than by
    guessing a window. A window that overshoots pulls the *next* function's
    headers into this one, which would make a call look as though it sends an
    actor because its neighbour does -- a false pass, and false passes are the
    only kind of wrong this file must not be.
    """
    found: dict[str, str] = {}
    for match in DECLARATION.finditer(masked):
        start = match.end()
        body = src[start : end_of_statement(masked, start)]
        if match.group(3) is not None:
            for name in bound_names(match.group(3)):
                found[name] = body
            continue
        found[match.group(1) or match.group(2)] = body
    return found


def bound_names(pattern: str) -> list[str]:
    """The names a destructuring pattern binds.

    Taking the last identifier of each comma-separated part gets the binding
    rather than the key, so `{"Content-Type": _dropped}` binds `_dropped`. The
    `...` of a rest element is stripped first: the general identifier pattern
    refuses a name preceded by a dot, so that `response.json` is not read as a
    name, and `...headers` looked exactly like one.
    """
    names: list[str] = []
    for part in re.sub(r"[\"'][^\"']*[\"']", " ", pattern.strip("{}[]")).split(","):
        found = re.findall(r"[A-Za-z_$][\w$]*", part.replace("...", " "))
        if found:
            names.append(found[-1])
    return names


def end_of_statement(masked: str, start: int) -> int:
    """Index one past the declaration that begins at `start`.

    Ending at the first balanced group was wrong in the way that matters:
    `function headers(actorId, contextId)` closed on the parameter list, so the
    body -- the part that spells out X-Actor-ID -- was never read, and three
    correct calls in `tin-nhan.ts` were reported as sending no actor.

    A declaration ends at a `;` at depth zero, or at the newline after a `{...}`
    block closes at depth zero, which is where a function declaration ends and
    where the next one has not yet begun.
    """
    depth = 0
    closed_block = False
    for i in range(start, len(masked)):
        ch = masked[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth < 0:
                return i
            if depth == 0 and ch == "}":
                closed_block = True
        elif ch == ";" and depth == 0:
            return i
        elif ch == "\n" and depth == 0 and closed_block:
            return i
    return len(masked)


def paths_in(text: str, decls: dict[str, str], hops: int = MAX_HOPS) -> list[str]:
    """API paths reachable from an expression, following identifiers.

    `fetch(url, ...)` says nothing on its own; the path is wherever `url` came
    from, and in three modules that is two declarations away
    (`url` -> `placesUrl(base, opts)` -> the template inside `placesUrl`).
    """
    seen: set[str] = set()
    out: list[str] = []

    def walk(expr: str, budget: int, visited: frozenset[str]) -> None:
        for token in tokenize(expr):
            shape = literal_shape(token)
            if shape is None:
                continue
            api_path = path_from_shape(shape)
            if api_path is not None and api_path not in seen:
                seen.add(api_path)
                out.append(api_path)
        if budget <= 0:
            return
        for match in IDENTIFIER.finditer(_code_only(expr)):
            name = match.group(1)
            if name in visited or name not in decls:
                continue
            walk(decls[name], budget - 1, visited | {name})

    walk(text, hops, frozenset())
    return out


def _code_only(text: str) -> str:
    return "".join(t.text for t in tokenize(text) if t.kind == "code")


def call_sites(src: str, masked: str) -> list[CallSite]:
    sites: list[CallSite] = []
    for match in CALLEE.finditer(masked):
        name = match.group(1)
        close = end_of_call(masked, match.end())
        if close is None:
            continue
        url_at, options_at = REQUEST_FUNCTIONS[name]
        spans = arg_spans(masked, match.end(), close)
        if len(spans) <= url_at:
            continue
        sites.append(
            CallSite(
                line=line_of(src, match.start()),
                url_text=src[spans[url_at][0] : spans[url_at][1]].strip(),
                options_text=(
                    src[spans[options_at][0] : spans[options_at][1]].strip()
                    if len(spans) > options_at
                    else ""
                ),
                wrapper=name in ("call", "translated"),
            )
        )
    return sites


@dataclass
class Finding:
    kind: str
    file: str
    line: int
    message: str


def findings_for_source(
    src: str, rel: str, contract: Contract
) -> tuple[list[Finding], int, int]:
    """Findings for one client file, plus (paths read, request sites seen).

    Separate from `check` so the reader can be exercised on a snippet without a
    repository and without a rendered OpenAPI document -- see
    `tests/test_api_contract.py`, which is what keeps this from going quietly
    blind.
    """
    findings: list[Finding] = []
    masked = mask(src, tokenize(src))
    sites = call_sites(src, masked)
    if not sites:
        return findings, 0, 0

    decls = declarations(src, masked)
    total_paths = 0

    for site in sites:
        api_paths = paths_in(site.url_text, decls)
        # A request whose URL this reader cannot follow contributes nothing but
        # its presence in the count. That number is the tell: it climbing while
        # the path count falls is this checker going blind, and going blind
        # looks exactly like a clean tree.
        total_paths += len(api_paths)
        for api_path in api_paths:
            if normalise(api_path) not in contract.routes:
                findings.append(
                    Finding(
                        "route_khong_ton_tai",
                        rel,
                        site.line,
                        f"app gọi {api_path} nhưng máy chủ không có route nào "
                        f"khớp -- mọi lần gọi sẽ là 404",
                    )
                )

    return findings, total_paths, len(sites)


def check() -> tuple[list[Finding], dict]:
    if not CLIENT_ROOT.is_dir():
        raise RuntimeError(
            f"{CLIENT_ROOT.relative_to(REPO_ROOT)} không có trên nhánh này -- "
            "không có client để đối chiếu"
        )
    if not API_ROOT.is_dir():
        raise RuntimeError("services/api không có trên nhánh này")

    contract = read_contract(load_openapi())
    if not contract.routes:
        raise RuntimeError("OpenAPI dựng được nhưng không có route nào -- từ chối coi là đạt")

    findings: list[Finding] = []
    total_paths = 0
    total_sites = 0
    files_with_calls = 0

    for path in client_files():
        rel = str(path.relative_to(REPO_ROOT))
        found, paths_read, sites_seen = findings_for_source(
            path.read_text(encoding="utf-8"), rel, contract
        )
        findings.extend(found)
        total_paths += paths_read
        total_sites += sites_seen
        if paths_read:
            files_with_calls += 1

    summary = {
        "routes_may_chu": len(contract.routes),
        "duong_dan_tim_thay": total_paths,
        "lan_goi_doc_duoc": total_sites,
        "file_co_goi_api": files_with_calls,
    }

    # A checker that found nothing to check has proved nothing. This is the
    # same rule scripts/gate.sh applies to itself when every stage is filtered
    # away, and it is here for the same reason: silence must not read as green.
    if total_paths == 0:
        raise RuntimeError(
            "không tìm thấy đường dẫn API nào trong apps/mobile/src -- "
            "hoặc client không còn gọi API, hoặc bộ đọc đã hỏng. "
            "Cả hai đều không phải 'đạt'."
        )

    return findings, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="in findings dạng JSON")
    args = parser.parse_args()

    try:
        findings, summary = check()
    except RuntimeError as problem:
        if args.json:
            print(json.dumps({"error": str(problem)}, ensure_ascii=False))
        else:
            print(f"KHÔNG CHẠY ĐƯỢC: {problem}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "summary": summary,
                    "findings": [f.__dict__ for f in findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if findings else 0

    print(
        f"Máy chủ có {summary['routes_may_chu']} route. "
        f"Đọc được {summary['duong_dan_tim_thay']} đường dẫn qua "
        f"{summary['lan_goi_doc_duoc']} lần gọi trong "
        f"{summary['file_co_goi_api']} file."
    )
    if not findings:
        print("Client và máy chủ khớp hợp đồng.")
        return 0

    print()
    for finding in findings:
        print(f"{finding.file}:{finding.line}  [{finding.kind}]")
        print(f"    {finding.message}")
    print()
    print(f"{len(findings)} chỗ lệch hợp đồng.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
