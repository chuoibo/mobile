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
- Whether a call is *reachable*. A path written in a module nobody imports
  still counts as called.
- It reads the tree it is in. A route that exists only on an unmerged branch
  counts as missing, which is the honest answer for `main` and the confusing
  one on a feature branch waiting for its API.

## Paths this reader cannot follow

Some are genuinely unfollowable: `call(path, ...)` inside the wrapper every
screen funnels through has no route in it, and `fetch(photo.uri)` is a local
blob rather than an API call at all. Those are pinned in
`.api-contract-unresolved.json` with a reason each.

Pinned, not skipped -- and that distinction is the whole point. Until
2026-08-30 an unfollowable call site contributed nothing but a number to the
summary, and the summary was printed rather than asserted on. So the shape
below passed:

    async function go(path: string) { return call<void>(path, ...); }
    export async function e() { return go("/khong-ton-tai-canary"); }

Measured on this tree at 15726d2, the same non-existent route four ways:
written as a literal, via one const, via `"a" + b`, and via `` `${base}/x` ``
all failed with exit 1 -- and the two shapes above (a path handed to a helper
parameter, and `"/" + parts.join("-")`) exited 0 while `duong_dan_tim_thay`
held at 36 and `lan_goi_doc_duoc` climbed 45 -> 46. That climb is the tell the
old comment here named, and naming a tell nobody checks is not a gate.

Now a call site this reader cannot follow is either pinned or a finding, so
the blind list cannot grow in silence. `scripts/check_actor_headers.py` --
this file's twin, reading the same sources for the adjacent question -- has
worked this way all along; this is that mechanism brought across.

A pin that no longer matches anything is reported too, loudly, but does not
fail the run: it means somebody made the client *more* readable, and a gate
that goes red for an improvement is a gate switched off within a day.

Usage:
  scripts/check_api_contract.py            check the tree this file is in
  scripts/check_api_contract.py --json     the same findings, machine-readable
  scripts/check_api_contract.py --selftest prove the gate can be red, on canaries

Exit codes: 0 client and server agree, 1 they disagree,
2 the check could not run -- and could not run is never a pass.

`2` covers unresolvable URLs too. "The app calls a route that does not exist" is
a defect in the PRODUCT; "I could not follow this URL" is a defect in the GATE,
and until 2026-08-31 both exited 1. Its twin `check_actor_headers.py` had the
same collapse, and at #379 that made QA read a FAIL for a client that was in
fact sending the header correctly.

A blind spot is still RED -- 2 is not 0 and `gate.sh` still blocks. It is only
named correctly. Making it green would be the real bug: a URL this reader cannot
follow may be hiding a route that genuinely does not exist.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENT_ROOT = REPO_ROOT / "apps" / "mobile" / "src"
API_ROOT = REPO_ROOT / "services" / "api"

# Call sites whose URL this reader cannot follow, each with a reason. Keyed by
# the expression text rather than by line number on purpose: `api.ts` is edited
# almost daily, and a pin that moves with every unrelated line above it goes red
# for the wrong reason, which is how a gate stops being run at all.
UNRESOLVED_PIN = REPO_ROOT / ".api-contract-unresolved.json"

# Three answers, not two. `CANNOT_READ` is the gate admitting a blind spot and
# must never collapse into `VIOLATION`, which is a confirmed product defect.
EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_CANNOT_READ = 2

# The one finding kind that says nothing about the client, only about this
# reader. Everything else in `Finding.kind` is a real contract mismatch.
BLIND_KIND = "duong_dan_khong_phan_giai_duoc"

# The placeholder a `${...}` or a `{param}` collapses to. A control character
# so it cannot occur in real source and be mistaken for one.
HOLE = "\x00"

# Names that make an HTTP request directly, rather than through a wrapper this
# repository writes. `fetch` is the platform's; `doFetch` is the alias the
# search and places modules bind so a test can inject its own implementation.
#
# Neither is declared in `api.ts`, which is the whole reason they are named
# separately: `tests/test_api_contract.py` holds every *other* entry of
# `REQUEST_FUNCTIONS` to a declaration in `api.ts`, and these two would fail
# that check for being right.
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
# and which holds the options. The four `*AsActor` / `*Anonymous` names are the
# wrappers in `src/api.ts`; every screen outside the chat modules goes through
# one of them. They were `call` and `translated` until each was split in two, so
# that making a request as nobody became something written down at the call site
# rather than a field somebody left off.
#
# This dict is the reader's one hardcoded dependency on how the client spells
# itself, and getting it wrong is silent in the worst direction: a name that is
# no longer used matches nothing, every call site through it stops being read,
# and the gate still exits 0 on whatever it can still see. Measured on this
# branch before the rename was taught here -- 60 of the client's 76 call sites
# went unread and `scripts/check_api_contract.py` stayed green.
#
# So this list is not trusted on its own. `tests/test_api_contract.py` holds
# every name below to a declaration in `api.ts`, and `--selftest` puts a
# non-existent route through each one and insists the gate goes red.
REQUEST_FUNCTIONS = {
    "fetch": (0, 1),
    "doFetch": (0, 1),
    "callAsActor": (0, 1),
    "callAnonymous": (0, 1),
    "translatedAsActor": (1, 2),
    "translatedAnonymous": (1, 2),
}

# The floor under the table above, written out a SECOND time as a literal.
#
# #430 put a floor under `WRAPPERS`, which is derived from `REQUEST_FUNCTIONS`.
# That floor only fires when `WRAPPERS` reaches *empty*, and emptiness is not
# how this table actually degrades. Losing ONE name leaves `WRAPPERS` non-empty,
# so #430's floor stays quiet, and the sibling test
# `test_every_wrapper_it_reads_is_still_declared_in_api_ts` iterates `WRAPPERS`
# -- a name deleted from the table deletes its own guard along with it. Both
# defences ask "is every name I know still in the client"; neither can ask "is
# every name the client has still known to me".
#
# Measured on this tree before this floor existed, deleting a single entry:
#
#   intact                        67 đường dẫn, 79 lần gọi, 12 file, exit 0
#   bỏ "translatedAnonymous"      64 đường dẫn, 75 lần gọi, 12 file, exit 0
#   bỏ "doFetch"                  63 đường dẫn, 75 lần gọi,  8 file, exit 0
#
# Four files stopped being read and the gate still printed "Client và máy chủ
# khớp hợp đồng". A smaller number is indistinguishable from a client that
# makes fewer calls -- which is the sentence `lost_wrappers` already carries,
# and this is the half of it that had no code.
#
# Anchored to a literal, not to `REQUEST_FUNCTIONS`: a floor derived from the
# table it guards is satisfied by emptying both. `REQUIRED_REQUEST_FUNCTION_COUNT`
# is here so that gutting this anchor is caught rather than being the way to
# disarm the check.
REQUIRED_REQUEST_FUNCTIONS = frozenset(
    {
        "fetch",
        "doFetch",
        "callAsActor",
        "callAnonymous",
        "translatedAsActor",
        "translatedAnonymous",
    }
)
REQUIRED_REQUEST_FUNCTION_COUNT = 6

# The subset the repository spells itself, stated literally for the same reason.
# Deriving it as `REQUIRED_REQUEST_FUNCTIONS - set(DIRECT_FETCH)` would let
# `DIRECT_FETCH` grow to swallow every wrapper and take this floor with it.
REQUIRED_WRAPPERS = frozenset(
    {
        "callAsActor",
        "callAnonymous",
        "translatedAsActor",
        "translatedAnonymous",
    }
)

# The wrappers this repository declares, as opposed to the platform's `fetch`.
WRAPPERS = tuple(name for name in REQUEST_FUNCTIONS if name not in DIRECT_FETCH)

# Longest name first: alternation is ordered, and with `call` before
# `callAsActor` the shorter branch matches, fails on the `A` that follows, and
# only finds the real name by backtracking. Sorting removes the question.
CALLEE = re.compile(
    r"(?<![\w$.])("
    + "|".join(sorted(REQUEST_FUNCTIONS, key=len, reverse=True))
    + r")\s*(?:<[^()]*>)?\s*\("
)


def verify_request_functions() -> None:
    """Refuse to answer at all when the reader's name table has been gutted.

    Five branches. The last two check a CONSEQUENCE rather than an input,
    because the first three can all hold while the derivation between the table
    and the scan has been rewritten -- and a table that is full but no longer
    reaches the scanner produces exactly the reassuring output this whole file
    is built to distrust.

    Reads module globals live rather than closing over them, so a table replaced
    after import is caught as well as a source edit.

    Raises `RuntimeError`, which `main` already turns into `EXIT_CANNOT_READ`.
    Never `EXIT_VIOLATION`: this is the reader admitting its own configuration
    is broken, and saying nothing whatsoever about the client. Reporting a blind
    spot as a client defect is the mistake #398 was opened to undo.
    """

    if len(REQUIRED_REQUEST_FUNCTIONS) < REQUIRED_REQUEST_FUNCTION_COUNT:
        raise RuntimeError(
            f"REQUIRED_REQUEST_FUNCTIONS chỉ còn {len(REQUIRED_REQUEST_FUNCTIONS)} "
            f"tên, phải có ít nhất {REQUIRED_REQUEST_FUNCTION_COUNT} -- chính cái "
            "neo bị rút ruột, nên nó không giữ được REQUEST_FUNCTIONS nữa."
        )

    if not REQUEST_FUNCTIONS:
        raise RuntimeError(
            "REQUEST_FUNCTIONS rỗng -- bộ đọc không còn nhận ra lời gọi nào, nên "
            "'không tìm thấy vi phạm' chỉ có nghĩa là không nhìn thấy gì."
        )

    if missing := sorted(REQUIRED_REQUEST_FUNCTIONS - set(REQUEST_FUNCTIONS)):
        raise RuntimeError(
            f"REQUEST_FUNCTIONS không còn tên {missing}. Bộ đọc nhận diện lời gọi "
            "BẰNG TÊN, nên mọi lời gọi qua tên đó trở thành vô hình: con số đường "
            "dẫn chỉ NHỎ ĐI chứ không đỏ, mà nhỏ đi thì không phân biệt được với "
            "một client gọi ít hơn. Đổi tên ở api.ts thì sửa KHỚP cả "
            "REQUEST_FUNCTIONS lẫn REQUIRED_REQUEST_FUNCTIONS."
        )

    # Only the PARTIAL case. An empty `WRAPPERS` is #430's floor to answer, and
    # it answers from inside `check` on purpose -- `tests/test_api_contract.py ::
    # test_an_empty_wrapper_list_reaches_the_check_instead_of_killing_import`
    # pins that it must not become an import-time death. Firing here first would
    # take a deliberate decision away from that gate and replace its message with
    # a vaguer one. What #430 cannot see is `DIRECT_FETCH` swallowing SOME of the
    # wrappers: the tuple stays non-empty, its floor stays quiet, and the
    # swallowed names stop being asked about.
    if WRAPPERS and (lost := sorted(REQUIRED_WRAPPERS - set(WRAPPERS))):
        raise RuntimeError(
            f"{lost} không còn nằm trong WRAPPERS dù vẫn có trong "
            "REQUEST_FUNCTIONS -- DIRECT_FETCH đã nuốt mất wrapper của chính repo "
            "này, nên phép kiểm 'client có đổi tên wrapper không' thôi không hỏi "
            "tới chúng nữa."
        )

    # The consequence: the compiled matcher must still recognise a call written
    # through every required name. This is what survives a rewrite of the
    # alternation above -- the table can be complete and the regex still not
    # built from it.
    unmatched = [
        name
        for name in sorted(REQUIRED_REQUEST_FUNCTIONS)
        if not CALLEE.search(f"{name}(")
    ]
    if unmatched:
        raise RuntimeError(
            f"REQUEST_FUNCTIONS vẫn đủ tên, nhưng CALLEE không khớp lời gọi qua "
            f"{unmatched}. Dây từ bảng tới bộ quét đã đứt ở chỗ dựng regex — bảng "
            "đầy không cứu được một phép dẫn xuất đã bị viết lại."
        )


# At import, not only inside `check`: a broken table must stop every caller --
# `tests/test_api_contract.py`, `--selftest`, any script importing this for
# `client_files` -- not just the one that comes through `check`. #458 made the
# same move on `repo_guard.SECRET_RULES`.
#
# Run as a script the raise has to be converted, not left to propagate. An
# uncaught exception exits 1, and 1 here is `EXIT_VIOLATION` -- "the client
# breaks the contract". That is the exact confusion `verify_request_functions`
# is documented to avoid: gate.sh would report a reader that cannot configure
# itself as a defect in somebody else's code. Imported, it still raises, because
# an importer holding a half-built module must not get a usable object.
try:
    verify_request_functions()
except RuntimeError as _broken:  # pragma: no cover - exercised via subprocess
    if __name__ == "__main__":
        print(f"KHÔNG CHẠY ĐƯỢC: {_broken}", file=sys.stderr)
        raise SystemExit(EXIT_CANNOT_READ) from None
    raise

# The anchor, over exactly the names above that this repository owns and can
# therefore rename -- `WRAPPERS`, not a second list. Two tuples both meaning
# "the wrappers we spell ourselves" is how a rename updates one of them, and
# this file has already run that experiment: `WRAPPERS` and a hand-written
# `("call", "translated")` arrived here from two branches and disagreed, which
# made the gate refuse to run at all until they were collapsed into one.
#
# Why the anchor exists at all. On 2026-08-31 PR #397 renamed both wrappers.
# The reader did not then report fewer routes, which somebody would have read.
# It stopped matching those call sites at all, and a call site that is never
# seen produces no path, no unresolved entry and no finding -- and no finding
# is printed as "Client và máy chủ khớp hợp đồng". Measured on main a6fdbe4:
# 67 paths -> 11, 76 call sites -> 17, exit 0, while every existing defence
# stayed green. `--selftest` stayed green because its canaries wrote the name
# `call` themselves. `test_the_real_client_still_has_routes_to_check` stayed
# green because 11 > 10: it is a floor, and unrelated growth had lifted the
# client past the point where the floor could catch this.
#
# A count cannot tell a blinded reader from a client that got smaller. A name
# can, so the reader is made to check the one assumption it cannot see failing.
#
# `function callAsActor` / `const callAsActor =`, and deliberately not
# `import { callAsActor }`: every screen imports the wrappers, so an import
# would keep the anchor holding on to a name that no longer exists anywhere --
# the exact failure it guards.
WRAPPER_DECLARATION = {
    name: re.compile(
        r"(?<![\w$.])(?:function|const|let|var)\s+" + re.escape(name) + r"(?![\w$])"
    )
    for name in WRAPPERS
}

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
    wrapper: bool  # went through one of src/api.ts's wrappers, not bare fetch


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
                wrapper=name in WRAPPERS,
            )
        )
    return sites


@dataclass
class Finding:
    kind: str
    file: str
    line: int
    message: str


class Unresolved(NamedTuple):
    """A request whose URL this reader could not turn into a route."""

    file: str
    line: int
    expr: str

    @property
    def where(self) -> str:
        """The pin key: file plus the expression, whitespace collapsed.

        Deliberately not the line number -- see `UNRESOLVED_PIN`.
        """
        return f"{self.file} :: {' '.join(self.expr.split())}"


class Scan(NamedTuple):
    findings: list[Finding]
    paths: int
    sites: int
    unresolved: list[Unresolved]
    # Which of `WRAPPERS` this file defines -- the anchor `check` holds the
    # whole reader by. Empty for the 110-odd files that only call them.
    declares: frozenset[str] = frozenset()


def findings_for_source(src: str, rel: str, contract: Contract) -> Scan:
    """Findings for one client file, plus what the reader could not follow.

    Separate from `check` so the reader can be exercised on a snippet without a
    repository and without a rendered OpenAPI document -- see
    `tests/test_api_contract.py`, which is what keeps this from going quietly
    blind.
    """
    findings: list[Finding] = []
    masked = mask(src, tokenize(src))
    sites = call_sites(src, masked)
    # Computed before the early return: a file that defines a wrapper and calls
    # nothing is exactly the file the anchor needs to hear from.
    declares = frozenset(
        name for name, pattern in WRAPPER_DECLARATION.items() if pattern.search(masked)
    )
    if not sites:
        return Scan(findings, 0, 0, [], declares)

    decls = declarations(src, masked)
    total_paths = 0
    unresolved: list[Unresolved] = []

    for site in sites:
        api_paths = paths_in(site.url_text, decls)
        # A request whose URL this reader cannot follow used to contribute
        # nothing but its presence in a printed count. It is now carried out of
        # here so `check` can insist every one of them is pinned with a reason.
        if not api_paths:
            unresolved.append(Unresolved(rel, site.line, site.url_text))
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

    return Scan(findings, total_paths, len(sites), unresolved, declares)


def lost_wrappers(declared: set[str]) -> list[str]:
    """What is wrong with this reader's assumptions -- never with the client.

    `CANNOT_READ`, never `VIOLATION`. A blind spot is not evidence about the
    client, and reporting it as one is the mistake #398 was opened to undo on
    the sibling CORS gate.

    Deliberately only asks whether the name still exists, and not the second
    question it looks like it should ask -- "is the reader still matching call
    sites for it". Measured while writing this: `CALLEE` matches the
    *declaration* too, because `function callAsActor<T>(path: string, ...)` has
    the same shape as a call, so a declared wrapper always scores at least one
    site and the question can never answer no. Those phantom sites are what
    the `api.ts :: path: string` entries in the pin file are. Making
    declarations not count is a real fix and a separate one: it moves the
    counts every other check here is calibrated against.

    An empty `WRAPPERS` is its own complaint, and has to be, because the loop
    below expresses "no name is missing" and "there is no name to miss" as the
    same empty list. The second one is the anchor switched off: with no name to
    hold, every rename this function exists to catch walks past it and the gate
    reports agreement. Nothing intentional stops that today -- an empty tuple
    happens to raise `IndexError` while a canary builds `WRAPPERS[0]` at import,
    which is protection by accident, in the wrong place, and under the wrong
    exit code. Measured: give the canaries an empty tuple they tolerate and the
    gate prints "khớp hợp đồng" and exits 0 with the anchor fully disarmed.
    """
    if not WRAPPERS:
        return [
            "WRAPPERS rỗng -- bộ đọc không còn tên wrapper nào để neo, nên phép "
            "kiểm 'client có đổi tên wrapper không' không hỏi được gì và mọi lần "
            "đổi tên sẽ đi lọt. Đây là lỗi CẤU HÌNH CỦA BỘ ĐỌC, không phải bằng "
            "chứng về client: sửa REQUEST_FUNCTIONS/DIRECT_FETCH để ít nhất một "
            "wrapper của repo này còn nằm ngoài DIRECT_FETCH."
        ]

    return [
        f"`{name}` không còn được khai báo ở đâu trong "
        f"{CLIENT_ROOT.relative_to(REPO_ROOT)} -- bộ đọc này nhận diện lời gọi "
        f"BẰNG TÊN, nên mọi lời gọi qua nó giờ vô hình, không phải 'khớp hợp "
        f"đồng'. Đổi tên thì sửa REQUEST_FUNCTIONS cho khớp tên api.ts đang "
        f"dùng; bỏ hẳn wrapper thì gỡ tên khỏi đó."
        for name in WRAPPERS
        if name not in declared
    ]


def declared_wrappers() -> set[str]:
    """The anchor measured against the real client, for tests and for `check`."""
    declared: set[str] = set()
    for path in client_files():
        src = path.read_text(encoding="utf-8")
        masked = mask(src, tokenize(src))
        declared |= {
            name
            for name, pattern in WRAPPER_DECLARATION.items()
            if pattern.search(masked)
        }
    return declared


def load_pins() -> dict[str, int]:
    """Pin key -> how many occurrences of it a human reviewed and accepted.

    An absent file means an empty pin list rather than an error: a branch whose
    client has nothing unfollowable in it needs no file. A malformed one is
    fatal, because the alternative -- reading as empty -- would turn every
    pinned blind spot into a finding at once, and a gate that fails that
    loudly for a typo gets reverted rather than read.
    """
    if not UNRESOLVED_PIN.exists():
        return {}
    try:
        raw = json.loads(UNRESOLVED_PIN.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{UNRESOLVED_PIN.name} không phải JSON hợp lệ: {exc}"
        ) from exc

    pins: dict[str, int] = {}
    for entry in raw.get("unresolved", []):
        where = entry.get("where")
        if not where:
            raise RuntimeError(f"{UNRESOLVED_PIN.name}: có mục thiếu 'where'")
        # A pin with no reason is how the list turns into a parking lot: the
        # next reader cannot tell an accepted limitation from a shrug.
        if not entry.get("reason"):
            raise RuntimeError(f"{UNRESOLVED_PIN.name}: {where} thiếu 'reason'")
        pins[where] = int(entry.get("count", 1))
    return pins


def unpinned_findings(
    unresolved: list[Unresolved], pins: dict[str, int]
) -> list[Finding]:
    """Every unfollowable call site the pin file does not already account for.

    When a key appears more often than it is pinned, every occurrence is
    reported rather than an arbitrary one of them. The reader cannot tell which
    is new -- they are the same expression -- and pointing at one line would be
    a guess dressed up as a location.
    """
    seen = Counter(u.where for u in unresolved)
    out: list[Finding] = []
    for site in unresolved:
        allowed = pins.get(site.where, 0)
        if seen[site.where] <= allowed:
            continue
        expr = " ".join(site.expr.split())[:80]
        if allowed == 0:
            message = (
                f"không phân giải được đường dẫn của lời gọi này ({expr!r}), "
                f"và nó chưa được ghim -- cổng không biết route nào đang bị gọi"
            )
        else:
            message = (
                f"chỗ mù {expr!r} được ghim {allowed} lần, cây này có "
                f"{seen[site.where]} -- có chỗ mới"
            )
        out.append(
            Finding("duong_dan_khong_phan_giai_duoc", site.file, site.line, message)
        )
    return out


def stale_pins(unresolved: list[Unresolved], pins: dict[str, int]) -> list[str]:
    """Pins matching fewer sites than they claim -- reported, never fatal."""
    seen = Counter(u.where for u in unresolved)
    return sorted(where for where, n in pins.items() if seen[where] < n)


def verdict(findings: list[Finding]) -> int:
    """Which of the three answers this run is.

    A confirmed mismatch outranks a blind spot: it is the one somebody can act
    on, and letting `BLIND_KIND` overwrite it would report a route that really
    does not exist as "could not read".
    """
    if any(f.kind != BLIND_KIND for f in findings):
        return EXIT_VIOLATION
    if findings:
        return EXIT_CANNOT_READ
    return EXIT_OK


def check() -> tuple[list[Finding], dict]:
    # First, before a single file is opened. `verify_request_functions` ran at
    # import too, but the table is a module global and anything holding this
    # module can rebind it afterwards. A scan run through a gutted table still
    # produces a full, confident-looking summary -- just a smaller one.
    verify_request_functions()

    if not CLIENT_ROOT.is_dir():
        raise RuntimeError(
            f"{CLIENT_ROOT.relative_to(REPO_ROOT)} không có trên nhánh này -- "
            "không có client để đối chiếu"
        )
    if not API_ROOT.is_dir():
        raise RuntimeError("services/api không có trên nhánh này")

    contract = read_contract(load_openapi())
    if not contract.routes:
        raise RuntimeError(
            "OpenAPI dựng được nhưng không có route nào -- từ chối coi là đạt"
        )

    findings: list[Finding] = []
    total_paths = 0
    total_sites = 0
    files_with_calls = 0
    unresolved: list[Unresolved] = []
    declared: set[str] = set()

    for path in client_files():
        rel = str(path.relative_to(REPO_ROOT))
        scan = findings_for_source(path.read_text(encoding="utf-8"), rel, contract)
        findings.extend(scan.findings)
        total_paths += scan.paths
        total_sites += scan.sites
        unresolved.extend(scan.unresolved)
        declared |= scan.declares
        if scan.paths:
            files_with_calls += 1

    # Before any count is believed. `total_paths == 0` below catches the reader
    # being switched off; this catches it being *renamed out of the client*,
    # which leaves a number that is merely smaller -- and a smaller number is
    # indistinguishable from a client that makes fewer calls.
    if lost := lost_wrappers(declared):
        raise RuntimeError(
            "bộ đọc mất dấu wrapper của client, nên con số bên dưới không nói "
            "lên điều gì:\n  - " + "\n  - ".join(lost)
        )

    pins = load_pins()
    findings.extend(unpinned_findings(unresolved, pins))
    stale = stale_pins(unresolved, pins)

    summary = {
        "routes_may_chu": len(contract.routes),
        "duong_dan_tim_thay": total_paths,
        "lan_goi_doc_duoc": total_sites,
        "file_co_goi_api": files_with_calls,
        "khong_phan_giai_duoc": len(unresolved),
        "ghim_cu": stale,
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


# --------------------------------------------------------------------------
# Tự kiểm: cổng phải ĐỎ được
# --------------------------------------------------------------------------

# The canaries call one route the fake contract below does not have. Written in
# shapes this reader *does* follow, and two that it does not -- the second group
# is the whole reason the pin file exists, and the pair of them is what stops
# "0 finding, exit 0" from being indistinguishable from a dead scanner.
CANARY_ROUTE = "/khong-ton-tai-canary"

# The wrapper the shape canaries below are written through, where what is being
# proved is the shape of the URL expression rather than which function receives
# it. A name that leaves `REQUEST_FUNCTIONS` stops being read, so those canaries
# stop biting and this self-test goes red -- which is the direction to fail in.
#
# Read off `WRAPPERS` rather than spelled out, for the reason the whole anchor
# exists: a second hand-written copy of a name is how a rename updates one of
# them. Identical to `"callAsActor"` today. The `DIRECT_FETCH` fallback keeps
# the module importable when `WRAPPERS` is empty, so `lost_wrappers` gets to
# report that as the reader's own misconfiguration instead of the module dying
# on `IndexError` before `check` can say anything.
CANARY_WRAPPER = WRAPPERS[0] if WRAPPERS else DIRECT_FETCH[0]


def canary_through(name: str, route: str) -> str:
    """One call to `route` through `name`, URL in the argument that holds it.

    Generated from `REQUEST_FUNCTIONS` rather than written out, so every name in
    it is exercised under its own spelling. The canaries used to say `call`
    literally, and that made this self-test agree with the reader's own list
    instead of checking anything: when the client renamed its wrappers, the list
    and the canaries both still said `call`, `--selftest` passed, and 60 of the
    client's 76 call sites were going unread at the same moment.
    """
    url_at, _ = REQUEST_FUNCTIONS[name]
    args = ["TABLE"] * url_at + [f'"{route}"', '{ method: "GET" }']
    return (
        "const TABLE: Record<string, string> = {};\n"
        f"export async function probe() {{ "
        f"return {name}<void>({', '.join(args)}); }}\n"
    )


CANARY_ONE_HOP = f"""
const p = "{CANARY_ROUTE}";
export async function b() {{ return {CANARY_WRAPPER}<void>(p, {{ method: "GET" }}); }}
"""

# Handed to a helper's parameter. Measured on 2026-08-30 at 15726d2: this
# exited 0 while the literal shapes exited 1 -- the identical non-existent
# route, two verdicts, which is the shape this gate was extended to refuse.
CANARY_BLIND_PARAM = f"""
async function go(path: string) {{
  return {CANARY_WRAPPER}<void>(path, {{ method: "GET" }});
}}
export async function e() {{ return go("{CANARY_ROUTE}"); }}
"""

# The same, assembled at runtime. A second blind shape on purpose: one canary
# proves one hole, and a gate with one canary is a gate tuned to one mistake.
CANARY_BLIND_JOIN = f"""
const parts = ["khong-ton-tai", "canary"];
export async function g() {{
  return {CANARY_WRAPPER}<void>("/" + parts.join("-"), {{ method: "GET" }});
}}
"""

CANARY_GOOD = canary_through(CANARY_WRAPPER, "/healthz")

# The wrapper anchor's own canaries. Written as source and read through
# `findings_for_source`, not by handing `lost_wrappers` a dictionary: a canary
# that skips the plumbing scores a copy of the logic rather than the gate, and
# the plumbing -- `declares` reaching `check` -- is the half that would
# actually rot.
#
# Generated from `WRAPPERS` for the same reason `canary_through` is: these were
# written spelling `call` and `translated` literally, and a canary that writes
# its own names agrees with the reader's list instead of checking it. Under the
# renamed wrappers all four of them reported "lost" -- including the clean one,
# whose whole job is to be silent -- so the pair that makes the anchor mean
# anything had quietly collapsed into "everything is always lost".


def canary_declaring(names: tuple[str, ...]) -> str:
    """A client that declares exactly `names` and calls each one once.

    The declaration is what the anchor counts, so the argument list is shaped
    from `REQUEST_FUNCTIONS` and not guessed: a wrapper whose URL is its second
    argument has to be declared with two.
    """
    lines = ['const KIND = "k";']
    for name in names:
        url_at, _ = REQUEST_FUNCTIONS.get(name, (0, 1))
        params = ["kind: string"] * url_at + ["path: string", "init: RequestInit"]
        args = ["KIND"] * url_at + ['"/healthz"', '{ method: "GET" }']
        lines.append(
            f"async function {name}<T>({', '.join(params)}) "
            "{ return fetch(path, init); }"
        )
        lines.append(
            f"export async function probe_{name}() "
            f"{{ return {name}<void>({', '.join(args)}); }}"
        )
    return "\n".join(lines) + "\n"


# Every wrapper where the reader expects it: the anchor must stay silent, or
# "everything is lost" would pass for vigilance.
CANARY_WRAPPERS_PRESENT = canary_declaring(WRAPPERS)

# The same client after a rename like #397's. Nothing here is malformed and
# nothing is missing -- the names simply moved, and the reader that keys on
# them sees an empty file.
CANARY_WRAPPERS_RENAMED = canary_declaring(tuple(f"{name}Renamed" for name in WRAPPERS))

# Half a rename: one wrapper moved, the rest did not. The anchor has to name
# the one that moved rather than shrug at the group -- a partial rename is the
# shape where the counts drop least and so look most like a client that got
# smaller.
CANARY_WRAPPER_HALF_RENAMED = canary_declaring(
    tuple(f"{name}Renamed" for name in WRAPPERS[:1]) + WRAPPERS[1:]
)

# Imports the wrappers and defines none, which is all 110-odd screens. The
# anchor must not read a caller as an anchor, or it would hold on to a name
# that no longer exists anywhere.
CANARY_WRAPPER_ONLY_IMPORTED = (
    f'import {{ {", ".join(WRAPPERS)} }} from "./api";\n'
    f'export async function a() {{ return {CANARY_WRAPPER}<void>("/healthz", '
    '{ method: "GET" }); }\n'
)


def _canary_contract() -> Contract:
    """A server offering exactly `/healthz`. No OpenAPI render, no database."""
    contract = Contract()
    contract.routes[normalise("/healthz")] = {"GET"}
    contract.spelling[normalise("/healthz")] = "/healthz"
    return contract


def _kinds(source: str) -> set[str]:
    scan = findings_for_source(source, "__canary__.ts", _canary_contract())
    kinds = {f.kind for f in scan.findings}
    # Unpinned against an EMPTY pin file: the canary asks whether the reader
    # notices it went blind, not whether this repository happens to pin it.
    kinds |= {f.kind for f in unpinned_findings(scan.unresolved, {})}
    return kinds


def selftest() -> int:
    """Prove the gate can be red, on both kinds of failure it claims to catch.

    A checker only ever run against a healthy tree proves nothing: `[]` and
    exit 0 is exactly what a broken scanner prints. So each red canary is
    paired with a clean one under the same question -- a probe that answers
    "violation" to everything cannot pass either.
    """
    missing = "route_khong_ton_tai"
    blind = "duong_dan_khong_phan_giai_duoc"

    # One pair per name the reader claims to read: a route that does not exist
    # must be found through it, and one that does must not be reported. A name
    # listed with the wrong argument positions passes neither, which is the
    # mistake that adding a name to `REQUEST_FUNCTIONS` invites.
    per_name: list[tuple[str, str, str, bool]] = []
    for name in REQUEST_FUNCTIONS:
        per_name.append(
            (
                f"canary xấu qua {name}()",
                canary_through(name, CANARY_ROUTE),
                missing,
                True,
            )
        )
        per_name.append(
            (
                f"canary sạch qua {name}()",
                canary_through(name, "/healthz"),
                missing,
                False,
            )
        )

    cases = tuple(per_name) + (
        ("canary xấu: qua một const", CANARY_ONE_HOP, missing, True),
        ("canary sạch (route có thật)", CANARY_GOOD, missing, False),
        ("canary mù: tham số hàm", CANARY_BLIND_PARAM, blind, True),
        ("canary mù: nối lúc chạy", CANARY_BLIND_JOIN, blind, True),
        ("canary mù/sạch", CANARY_GOOD, blind, False),
    )

    ok = True
    for label, source, kind, want in cases:
        got = kind in _kinds(source)
        if got != want:
            ok = False
        print(
            f"  {'ĐẠT' if got == want else 'HỎNG':6} {label}: "
            f"{'có' if got else 'không có'} [{kind}] "
            f"(mong đợi {'có' if want else 'không có'})"
        )

    # The anchor is a census rather than a finding kind, so it gets its own
    # pair under the same rule: one canary proves one hole, and a clean canary
    # is what stops "everything is lost" from passing for vigilance.
    anchors = (
        ("canary neo: đổi tên mọi wrapper", CANARY_WRAPPERS_RENAMED, True),
        ("canary neo: đổi tên đúng một wrapper", CANARY_WRAPPER_HALF_RENAMED, True),
        (
            "canary neo: chỉ import, không định nghĩa",
            CANARY_WRAPPER_ONLY_IMPORTED,
            True,
        ),
        (
            "canary neo/sạch: wrapper còn được định nghĩa",
            CANARY_WRAPPERS_PRESENT,
            False,
        ),
    )
    for label, source, want in anchors:
        scan = findings_for_source(source, "__canary__.ts", _canary_contract())
        got = bool(lost_wrappers(set(scan.declares)))
        if got != want:
            ok = False
        print(
            f"  {'ĐẠT' if got == want else 'HỎNG':6} {label}: "
            f"{'mất dấu' if got else 'còn dấu'} "
            f"(mong đợi {'mất dấu' if want else 'còn dấu'})"
        )

    print()
    if ok:
        print(
            "Tự kiểm ĐẠT — cổng đỏ được khi route không tồn tại, đỏ được khi "
            "chính nó không đọc nổi đường dẫn, đỏ được khi client đổi tên "
            "wrapper ra khỏi tầm nhìn của nó, và xanh khi không có cả ba."
        )
        return 0
    print(
        "Tự kiểm HỎNG — cổng này không phân biệt được sai với đúng.",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="in findings dạng JSON")
    parser.add_argument("--selftest", action="store_true", help="tự kiểm bằng canary")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    try:
        findings, summary = check()
    except RuntimeError as problem:
        if args.json:
            print(json.dumps({"error": str(problem)}, ensure_ascii=False))
        else:
            print(f"KHÔNG CHẠY ĐƯỢC: {problem}", file=sys.stderr)
        return EXIT_CANNOT_READ

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
        return verdict(findings)

    print(
        f"Máy chủ có {summary['routes_may_chu']} route. "
        f"Đọc được {summary['duong_dan_tim_thay']} đường dẫn qua "
        f"{summary['lan_goi_doc_duoc']} lần gọi trong "
        f"{summary['file_co_goi_api']} file, "
        f"{summary['khong_phan_giai_duoc']} chỗ không phân giải được."
    )

    # Printed whether the run passes or fails: a pin that stopped matching is
    # the one change to this file nobody is otherwise told about.
    for where in summary["ghim_cu"]:
        print(
            f"GHIM CŨ: {where} -- không còn khớp chỗ nào; gỡ khỏi "
            f"{UNRESOLVED_PIN.name} hoặc giảm 'count'."
        )

    if not findings:
        print("Client và máy chủ khớp hợp đồng.")
        return EXIT_OK

    print()
    for finding in findings:
        print(f"{finding.file}:{finding.line}  [{finding.kind}]")
        print(f"    {finding.message}")
    print()

    blind = [f for f in findings if f.kind == BLIND_KIND]
    mismatched = [f for f in findings if f.kind != BLIND_KIND]

    if blind:
        print("Viết đường dẫn ra thành literal mà cổng đọc được, hoặc ghim vào")
        print(f"{UNRESOLVED_PIN.name} -- ghim là nói ra chỗ mù, không phải xoá nó:")
        print(
            '  {"unresolved": [{"where": "<file> :: <biểu thức>", '
            '"count": 1, "reason": "..."}]}'
        )
        print()

    # Two counts, never one total. A single number here is what let a blind
    # spot be reported as "the client is wrong" -- see the module docstring.
    if mismatched:
        print(f"{len(mismatched)} chỗ lệch hợp đồng.")
    if blind:
        print(
            f"{len(blind)} chỗ cổng KHÔNG ĐỌC ĐƯỢC -- chưa kết luận gì về "
            "client ở những chỗ này."
        )
    return verdict(findings)


if __name__ == "__main__":
    sys.exit(main())
