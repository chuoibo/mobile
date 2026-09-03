#!/usr/bin/env python3
"""Cổng: mọi route đòi `X-Actor-ID` phải được app gọi kèm header đó.

## Vì sao có file này

Ngày 2026-08-29, PR #155 (rd-be-13) bắt `POST /places/search` phải có
`X-Actor-ID`. #155 vào main lúc b122d8a. Ô tìm kiếm trong app không gửi header
đó, nên từ lúc đó tới lúc #158 vá (6c7d2ab) — khoảng hai tiếng — **màn Khám phá
hỏng trên main**: máy chủ trả 401 và màn hình báo "sự cố máy chủ" cho một
chuyện không phải sự cố máy chủ.

Trong hai tiếng ấy mọi cổng đều xanh, và chúng xanh một cách trung thực:

* `pytest services/api/tests` xanh — test API tự gửi header, vì test biết route
  cần gì.
* `npm test` trong `apps/mobile` xanh — test client tiêm `fetchImpl` giả, mà
  fetch giả không bao giờ trả 401.
* `tsc --noEmit` xanh — không bên nào khai kiểu cho header HTTP.
* Cổng docker, cổng migration, repo guard: không cái nào biết HTTP header là gì.

Hợp đồng bị vỡ nằm ĐÚNG giữa hai bên, và cả hai bên đều tự kiểm chỉ phía mình.
Không cổng nào nhìn qua khe đó. File này là cổng nhìn qua khe đó.

## Nó so cái gì với cái gì

Phía máy chủ **không** đọc bằng grep. Nó dựng `app.openapi()` từ chính ứng dụng
FastAPI, rồi lấy các operation có tham số header tên `X-Actor-ID`. Đó là hệ quả
của `Depends(get_actor)` do chính FastAPI khai ra — thêm route mới có
`get_actor` là nó tự xuất hiện ở đây, không ai phải nhớ cập nhật danh sách.

Phía client đọc tĩnh `apps/mobile/src/**/*.ts(x)`, bỏ file test. Với mỗi hàm ở
cấp ngoài cùng, nó thu:

* các **đường route** hàm đó nhắc tới — trực tiếp bằng template literal
  (`${base}/contexts/${id}/messages`), hoặc gián tiếp qua một hàm dựng URL
  trong cùng file (`searchUrl`, `messagesUrl`, `placesUrl`, `aiTurnUrl`);
* các **phương thức** HTTP nó nhắc tới (`method: "POST"`), mặc định GET như
  `fetch` mặc định;
* **bằng chứng có actor**: hoặc chuỗi `X-Actor-ID` viết thẳng trong thân hàm,
  hoặc một lời gọi tới hàm-có-actor trong cùng file (một hàm mà thân nó chứa
  `X-Actor-ID`, ví dụ `headers()` hay `actorHeaders()`) VÀ hàm này có nhắc tên
  một định danh actor (`actorId`, `personId`, ...).

Vế sau của điều kiện cuối không thừa. `call<T>()` trong `api.ts` chỉ gắn header
actor KHI có `actorId` truyền vào (`actorId ? actorHeaders(...) : ...`). Chỉ
kiểm "có gọi `call`" thì một hàm quên `actorId` vẫn lọt.

## Nó KHÔNG chứng minh gì

Đọc kỹ chỗ này trước khi tin dấu xanh của nó:

* **Phạm vi là hàm, không phải từng lời gọi.** Một hàm gọi hai route và chỉ gửi
  actor cho một route thì cổng này vẫn xanh. Nó bắt "quên hẳn", không bắt "gửi
  thiếu chỗ".
* **Không kiểm ĐÚNG người.** Gửi `X-Actor-ID` của người khác là 403 hoặc tệ hơn
  là ghi tiền cho người không liên quan, và cổng này mù hoàn toàn với chuyện đó.
  Đó là việc của test quyền và của QA.
* **Không kiểm `X-Actor-Roles` / `X-Actor-Contexts`.** Route đòi vai trò mà
  client claim thiếu thì ra 403, và cổng này không thấy. Cố ý: vai trò cần
  thiết nằm trong `app/domain/permissions.py` chứ không nằm trong chữ ký HTTP,
  nên OpenAPI không nói được, và đoán thì tệ hơn im lặng.
* **Không chạy gì cả.** Nó đọc mã nguồn. Bundle thật sự dựng ra có thể khác —
  xem `scripts/gate.sh` chặng `mobile`.
* **Đường dựng động thì nó không phân giải được**, và những chỗ đó phải được
  ghim vào `.actor-header-unresolved.json` kèm lý do. Ghim chứ không bỏ qua:
  thêm một chỗ không phân giải được mới là cổng ĐỎ, để danh sách không tự phình
  ra trong im lặng.

Đó là lý do file này báo ba con số — ĐẠT, HỎNG, KHÔNG PHÂN GIẢI — chứ không chỉ
báo xanh/đỏ. Một cổng giấu phần nó không kiểm được thì nguy hiểm hơn không có
cổng, vì nó làm người đọc thôi tìm.

Dùng:
    python3 scripts/check_actor_headers.py            # kiểm
    python3 scripts/check_actor_headers.py --list     # in bảng route -> hàm gọi
    python3 scripts/check_actor_headers.py --selftest # tự kiểm bằng canary

Mã thoát: 0 đạt, 1 có vi phạm, 2 cổng không làm được việc của nó.

`2` gồm cả chỗ dựng URL không phân giải được. Ba trạng thái, không phải hai:
"client quên header" là khuyết tật của SẢN PHẨM, "tôi không đọc nổi URL này" là
khuyết tật của CỔNG, và trước 31/08 cả hai đều in `HỎNG` rồi thoát `1`. Ở #379
điều đó làm QA đọc phán quyết thành FAIL cho một client vốn GỬI ĐÚNG header; họ
phải tự đọc mã nguồn mới gỡ ra được, và người đọc sau sẽ không đọc.

Chỗ mù vẫn ĐỎ — `2` khác `0`, `gate.sh` vẫn chặn — nó chỉ được gọi đúng tên.
Làm nó xanh mới là sai: chỗ cổng không đọc được có thể đang giấu header thiếu.
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
API_DIR = REPO_ROOT / "services" / "api"
CLIENT_DIR = REPO_ROOT / "apps" / "mobile" / "src"
UNRESOLVED_PIN = REPO_ROOT / ".actor-header-unresolved.json"

ACTOR_HEADER = "X-Actor-ID"

# Three answers, not two. `CANNOT_READ` is the gate admitting a blind spot; it
# must never be folded into `VIOLATION`, which is a confirmed product defect.
EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_CANNOT_READ = 2

# Identifiers that stand for "the person this request acts as". Used only to
# tell "delegates to a header helper and passes an actor" from "delegates to a
# header helper and forgot to". Deliberately narrow: a name not on this list
# makes the gate louder, never quieter.
ACTOR_IDENT = re.compile(r"\b(actorId|actor_id|personId|person_id|actorID)\b")


# --------------------------------------------------------------------------
# Phía máy chủ: hỏi chính ứng dụng, không grep
# --------------------------------------------------------------------------


def server_routes() -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """(cần actor, không cần actor) dưới dạng {(METHOD, path đã chuẩn hoá)}.

    Rendered in a subprocess so this script does not need the API's imports on
    its own path, and so an import error in the app surfaces as this gate
    failing loudly rather than as a stack trace three frames deep.
    """

    code = (
        "import json;from app.api.main import app;"
        "print(json.dumps(app.openapi()['paths']))"
    )
    try:
        out = subprocess.run(
            [sys.executable, "-c", code],
            cwd=API_DIR,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover
        die(f"không dựng được OpenAPI từ services/api: {exc}")
    if out.returncode != 0:
        die(
            "không dựng được OpenAPI từ services/api "
            f"(mã {out.returncode}):\n{out.stderr.strip()[-2000:]}"
        )

    try:
        paths = json.loads(out.stdout)
    except json.JSONDecodeError as exc:
        die(f"OpenAPI trả về thứ không phải JSON: {exc}")

    need: set[tuple[str, str]] = set()
    free: set[tuple[str, str]] = set()
    for path, ops in paths.items():
        for method, op in ops.items():
            if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            headers = {
                p.get("name")
                for p in (op.get("parameters") or [])
                if p.get("in") == "header"
            }
            key = (method.upper(), normalise(path))
            (need if ACTOR_HEADER in headers else free).add(key)

    if not need:
        # Every route losing its actor dependency at once is not a green tree,
        # it is this gate reading the wrong thing. Refuse rather than pass.
        die(
            "OpenAPI không có route nào đòi X-Actor-ID. Cổng này không tin nổi "
            "kết quả đó — nhiều khả năng get_actor đã đổi hình dạng."
        )
    return need, free


def normalise(path: str) -> str:
    """`/contexts/{context_id}/messages` và `/contexts/${id}/messages` -> cùng một chuỗi."""

    path = path.split("?", 1)[0].split("#", 1)[0]
    path = re.sub(r"\$\{[^}]*\}", "{}", path)  # client template hole
    path = re.sub(r"\{[^}]*\}", "{}", path)  # server path param
    path = re.sub(r"//+", "/", path)
    return path.rstrip("/") or "/"


# --------------------------------------------------------------------------
# Phía client: đọc tĩnh
# --------------------------------------------------------------------------

# A path literal worth taking seriously. Anchored at `/` and made of the
# characters a route is made of, which is what keeps regex literals like
# `/\/$/` and CSS-ish strings out of the results.
PATH_SHAPE = re.compile(r"^/[a-z][A-Za-z0-9/_{}.-]*$")

# Top-level declarations. Column 0 only: everything nested inside a function
# belongs to that function's region, which is exactly what we want.
#
# `[^=;]` and not `[^=]` in the arrow-const branch, and the `;` is the whole
# point. A character class excluding only `=` crosses newlines, so a plain
# `const MINH_SLUG = "minh";` kept scanning forward for an `=>` and found one
# three functions later, in a type annotation (`json: () => Promise<unknown>`).
# The const then claimed all three as its own region: `headers`, `goc` and
# `docLoi` in `screens/chat/nhom.ts` vanished from the graph, and every route
# reached through them read as "gọi mà không gửi actor" -- fifteen false
# accusations at once.
#
# What kept it hidden is worth writing down: the swallow only happens when no
# bare `=` appears before the first `=>`. `headers()` used to open with
# `const h: Record<string, string> = {`, so the scan stopped one line in and
# the bug was invisible. Deleting that line -- while making the client MORE
# correct -- is what exposed it. `CANARY_CONST_NUOT_HAM` pins it.
DECL = re.compile(
    r"^(?:export\s+)?(?:default\s+)?"
    r"(?:async\s+)?function\s+(?P<fn>[A-Za-z_$][\w$]*)"
    r"|^(?:export\s+)?const\s+(?P<cn>[A-Za-z_$][\w$]*)\s*[:=][^=;]*=>",
    re.MULTILINE,
)

METHOD_LITERAL = re.compile(r"""method\s*:\s*["'`](GET|POST|PUT|PATCH|DELETE)["'`]""")


@dataclass
class Region:
    """One top-level function, and what it says about HTTP."""

    name: str
    file: Path
    line: int
    text: str
    paths: set[str] = field(default_factory=set)
    methods: set[str] = field(default_factory=set)
    unresolved: list[str] = field(default_factory=list)
    calls: set[str] = field(default_factory=set)
    actor: bool = False
    actor_conditional: bool = False
    requester: bool = False

    @property
    def has_actor_literal(self) -> bool:
        return ACTOR_HEADER in self.text

    @property
    def where(self) -> str:
        # Một file dựng tạm (canary, ca test) nằm ngoài repo, và `relative_to`
        # ném ValueError chứ không trả về đường dẫn tuyệt đối. Rơi về đường dẫn
        # đầy đủ thay vì làm cổng chết giữa lúc đang in báo cáo.
        try:
            where = self.file.relative_to(REPO_ROOT)
        except ValueError:
            where = self.file
        return f"{where}:{self.line} {self.name}()"


def strip_noise(src: str) -> str:
    """Blank out comments so a route path inside a docstring is not a call.

    Replaces with spaces rather than deleting, so every byte offset — and so
    every line number this gate prints — still points at the real source.
    """

    out = list(src)
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in "\"'`":
            quote = c
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j == -1 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
            continue
        i += 1
    return "".join(out)


def literals(text: str) -> list[str]:
    """Every string/template literal body in `text`, templates left un-expanded."""

    found: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in "\"'`":
            quote, start = c, i + 1
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == quote:
                    break
                i += 1
            found.append(text[start:i])
            i += 1
            continue
        i += 1
    return found


def route_paths(text: str) -> tuple[set[str], list[str]]:
    """Route paths a chunk of code names, and the literals it could not resolve.

    Two accepted shapes, both anchored on something that is unmistakably a URL
    being built:

      `${base}/contexts/${id}/messages`   template starting with an expression
      "/batches"                          a bare path handed to a request helper

    `fetch(photo.uri)` has neither, which is how a blob read stays out of an
    API contract check without needing a special case for it.
    """

    paths: set[str] = set()
    unresolved: list[str] = []
    for lit in literals(text):
        body = lit
        if body.startswith("${"):
            close = body.find("}")
            if close == -1:
                continue
            body = body[close + 1 :]
            # `${base}${expr}` -- the path segment itself is an expression, so
            # this reader cannot say WHICH route is called. That is a blind
            # spot, not an absence, and the two must not share an exit. Before
            # this branch existed the literal fell through to the `/` test
            # below and was dropped, so `fetch(`${BASE}${ENDPOINTS.search}`)`
            # with no actor header passed the gate while the same call written
            # `fetch(`${BASE}/places/search`)` failed it.
            #
            # Prose keeps its exemption: real text separates its interpolations
            # (`${ten} có ${so} món`), so only two ADJACENT ones read as a URL
            # assembled from a base.
            if body.startswith("${"):
                unresolved.append(lit)
                continue
        if not body.startswith("/"):
            continue
        candidate = normalise(body)
        if PATH_SHAPE.match(candidate):
            paths.add(candidate)
        elif "${" in body or "{" in body:
            unresolved.append(lit)
    return paths, unresolved


def regions_of(path: Path) -> list[Region]:
    src = path.read_text(encoding="utf-8")
    clean = strip_noise(src)
    marks = [(m.start(), m.group("fn") or m.group("cn")) for m in DECL.finditer(clean)]
    if not marks:
        return []
    marks.append((len(src), ""))

    out: list[Region] = []
    for (start, name), (end, _) in zip(marks, marks[1:]):
        if not name:
            continue
        text = src[start:end]
        paths, unresolved = route_paths(strip_noise(text))
        out.append(
            Region(
                name=name,
                file=path,
                line=src.count("\n", 0, start) + 1,
                text=strip_noise(text),
                paths=paths,
                methods=set(METHOD_LITERAL.findall(text)),
                unresolved=unresolved,
            )
        )
    return out


#: Thư mục ĐỌC THÊM, dành cho ca test cần thả một file mẫu trước mặt bộ đọc mà
#: không được bẩn cây client thật. Cố ý là CỘNG THÊM chứ không phải THAY THẾ:
#: một biến môi trường đổi được phạm vi quét là một cửa hậu — trỏ nó vào một
#: thư mục chỉ có một lời gọi sạch thì cổng xanh trong khi cây thật đang hỏng,
#: và phép gác `call_sites == 0` không bắt được vì con số đó là 1. Cộng thêm thì
#: chỉ làm cổng ồn hơn, không bao giờ làm nó im hơn.
EXTRA_CLIENT_DIR_ENV = "MOBILE_ACTOR_EXTRA_CLIENT_DIR"


def _scan_roots() -> list[Path]:
    roots = [CLIENT_DIR]
    extra = os.environ.get(EXTRA_CLIENT_DIR_ENV)
    if extra:
        roots.append(Path(extra))
    return [r for r in roots if r.is_dir()]


def client_files() -> list[Path]:
    return sorted(
        p
        for root in _scan_roots()
        for p in root.rglob("*")
        if p.suffix in {".ts", ".tsx"}
        and ".test." not in p.name
        and "__tests__" not in p.parts
    )


DIRECT_FETCH = re.compile(r"\b(?:fetch|doFetch|fetchImpl)\s*\(")

# An actor header this helper attaches only *sometimes*. `call<T>()` in api.ts
# is the shape: `actorId ? actorHeaders(...) : { "Content-Type": ... }`. Callers
# of a helper like this must be checked for actually passing somebody, because
# omitting an optional field type-checks -- which is precisely how a route can
# be called with no actor while every gate stays green.
#
# The lookahead keeps the *optional property* form (`actorId?: string`) out: a
# type annotation is a declaration, not a branch.
CONDITIONAL_ACTOR = re.compile(
    r"\b(?:actorId|actor_id|personId|person_id)\s*(?:\?(?!\s*:)|&&|\|\|)"
    r"|\bif\s*\(\s*!?\s*(?:actorId|actor_id|personId|person_id)\b"
)


def call_args(text: str, name: str) -> list[str]:
    """The argument text of every call to `name` in `text`.

    Paren-matched rather than regex-matched, because the arguments in this app
    are nested object literals and a regex that stops at the first `)` reads
    `{ method: "PUT", body: f(x) }` as ending halfway through.
    """

    pattern = re.compile(rf"\b{re.escape(name)}\s*(?:<[^<>()]*>)?\s*\(")
    out: list[str] = []
    for m in pattern.finditer(text):
        i, depth, n = m.end(), 1, len(text)
        start = i
        while i < n and depth:
            c = text[i]
            if c in "\"'`":
                quote = c
                i += 1
                while i < n:
                    if text[i] == "\\":
                        i += 2
                        continue
                    if text[i] == quote:
                        break
                    i += 1
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        out.append(text[start:i])
    return out


def has_required_actor_param(region: Region) -> bool:
    """Does this function take an actor that a caller cannot leave out?

    `registerPerson(person, actorId: string, attempt)` does: TypeScript refuses
    the call that omits it, so no gate needs to re-check its callers. An
    options bag whose `actorId?` is optional does not, and that difference is
    the whole reason `DangKy()` was accused the first time this ran.
    """

    m = re.search(r"[A-Za-z_$][\w$]*\s*(?:<[^<>()]*>)?\s*\(", region.text)
    if not m:
        return False
    i, depth, n = m.end(), 1, len(region.text)
    start = i
    while i < n and depth:
        c = region.text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    params = region.text[start:i]
    for hit in ACTOR_IDENT.finditer(params):
        rest = params[hit.end() :].lstrip()
        if not rest.startswith("?"):
            return True
    return False


def passes_an_actor(caller: Region, name: str) -> bool:
    """Does `caller` hand `name` somebody to act as?

    Three answers count as yes, and the third is the one that matters:

    * the arguments name an actor identifier outright;
    * the arguments spread an object through (`{...opts, before}`), where the
      required-ness of the field is TypeScript's job and it does it;
    * the arguments forward a plain variable (`call<T>(path, options)`), same
      reason.

    Only an object literal built on the spot, with no spread and no actor in
    it, is read as an omission. That is the one shape where leaving the actor
    out compiles cleanly and fails at runtime with a 401.
    """

    blobs = call_args(caller.text, name)
    if not blobs:
        return False
    for blob in blobs:
        if ACTOR_IDENT.search(blob):
            return True
        if "..." in blob:
            return True
        if "{" not in blob:
            return True
    return False


IMPORT = re.compile(
    r"""import\s*\{(?P<names>[^}]*)\}\s*from\s*["'](?P<from>[^"']+)["']""",
)


def resolve_specifier(source: Path, spec: str) -> Path | None:
    """`../../api` seen from `screens/kham-pha/check-in.ts` -> `src/api.ts`.

    Only relative specifiers. A bare specifier is a node_modules package and
    cannot be a module of this app, which is the whole reason to ignore it
    rather than to search for it.
    """

    if not spec.startswith("."):
        return None
    base = (source.parent / spec).resolve()
    for cand in (
        base.with_suffix(".ts"),
        base.with_suffix(".tsx"),
        base / "index.ts",
        base / "index.tsx",
    ):
        if cand.is_file():
            return cand
    return None


def build_graph(files: list[Path]) -> list[Region]:
    """Every top-level function in the app, linked to the ones it calls.

    Links are resolved through real `import` statements rather than by matching
    bare names across the tree. Two files both defining `headers()` is normal
    here, and a name-only index would let one file's header helper vouch for
    the other file's omission -- a gate that is wrong in the permissive
    direction, which is the direction that does not get noticed.
    """

    per_file: dict[Path, list[Region]] = {}
    for path in files:
        per_file[path] = regions_of(path)

    # (file, name) -> region, plus each file's view of what a name refers to.
    index: dict[tuple[Path, str], Region] = {}
    for path, regions in per_file.items():
        for r in regions:
            index.setdefault((path, r.name), r)

    scope: dict[Path, dict[str, tuple[Path, str]]] = {}
    for path, regions in per_file.items():
        local = {r.name: (path, r.name) for r in regions}
        src = strip_noise(path.read_text(encoding="utf-8"))
        for m in IMPORT.finditer(src):
            target = resolve_specifier(path, m.group("from"))
            if target is None:
                continue
            for chunk in m.group("names").split(","):
                chunk = chunk.strip()
                if not chunk or chunk.startswith("type "):
                    continue
                parts = [p.strip() for p in chunk.split(" as ")]
                origin, localname = parts[0], parts[-1]
                local[localname] = (target, origin)
        scope[path] = local

    all_regions = [r for regions in per_file.values() for r in regions]

    # Edges. A name is a callee when it appears in call position, which keeps
    # a bare type reference or a re-export out of the graph.
    for path, regions in per_file.items():
        names = scope[path]
        for r in regions:
            for name in names:
                if name == r.name:
                    continue
                if re.search(rf"\b{re.escape(name)}\s*[<(]", r.text):
                    r.calls.add(name)

    def callees(r: Region) -> list[Region]:
        out = []
        for name in r.calls:
            key = scope[r.file].get(name)
            if key and key in index:
                out.append(index[key])
        return out

    # Seeds, then a fixed point over the call graph. One pass is not enough:
    # `checkIn` -> `translated` -> `call` -> `actorHeaders` is four hops, and
    # every hop was a false accusation the first time this ran.
    for r in all_regions:
        r.actor = r.has_actor_literal
        r.requester = bool(DIRECT_FETCH.search(r.text))
        r.actor_conditional = bool(CONDITIONAL_ACTOR.search(r.text))

    for _ in range(len(all_regions) + 1):
        changed = False
        for r in all_regions:
            for name in sorted(r.calls):
                key = scope[r.file].get(name)
                if not key or key not in index:
                    continue
                callee = index[key]
                if callee.requester and not r.requester:
                    r.requester = True
                    changed = True
                if callee.paths - r.paths:
                    r.paths |= callee.paths
                    changed = True
                if callee.methods - r.methods:
                    r.methods |= callee.methods
                    changed = True
                if r.actor or not callee.actor:
                    continue
                if callee.actor_conditional:
                    # The helper attaches the header only if handed somebody,
                    # so calling it is not evidence -- passing an actor to it
                    # is. Forwarding stays conditional up the chain: whoever
                    # eventually builds the literal object is the one who can
                    # leave the actor out.
                    if passes_an_actor(r, name):
                        r.actor = True
                        # Conditionality stops at a function that takes the
                        # actor as a required parameter: its own callers cannot
                        # omit what the compiler insists on.
                        r.actor_conditional = not has_required_actor_param(r)
                        changed = True
                else:
                    r.actor = True
                    changed = True
        if not changed:
            break
    else:  # pragma: no cover
        die("đồ thị lời gọi không hội tụ — cổng từ chối đoán")

    return all_regions


# --------------------------------------------------------------------------
# So hai phía
# --------------------------------------------------------------------------


@dataclass
class Violation:
    where: str
    method: str
    path: str


def load_pins() -> dict:
    if not UNRESOLVED_PIN.exists():
        return {"unresolved": []}
    try:
        return json.loads(UNRESOLVED_PIN.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"{UNRESOLVED_PIN.name} không phải JSON hợp lệ: {exc}")


def die(msg: str) -> None:
    print(f"cổng không làm được việc của nó: {msg}", file=sys.stderr)
    raise SystemExit(EXIT_CANNOT_READ)


def analyse() -> tuple[list[Violation], list[tuple[str, str]], list[Region], int]:
    need, free = server_routes()
    known = {p for _, p in need} | {p for _, p in free}

    files = client_files()
    if not files:
        die(
            "không thấy file nào trong apps/mobile/src. Trên nhánh không có "
            "apps/mobile thì đừng gọi cổng này (xem scripts/gate.sh)."
        )

    violations: list[Violation] = []
    checked: list[tuple[str, str]] = []
    unresolved: list[Region] = []
    call_sites = 0

    for region in build_graph(files):
        # A function that only spells a URL is not a call site. `messagesUrl`
        # has no headers by design and never will, and demanding one of it
        # would train people to read this gate's output as noise.
        if not region.requester:
            continue
        if region.unresolved:
            unresolved.append(region)
        if not region.paths:
            continue
        methods = region.methods or {"GET"}
        for route in sorted(region.paths):
            if route not in known:
                # A path the server does not serve is its own defect, but this
                # gate is not the one that owns it: `places.ts` names `/places`
                # inside a 404 message. Counted, not failed.
                continue
            for method in sorted(methods):
                if (method, route) not in need:
                    continue
                call_sites += 1
                checked.append((f"{method} {route}", region.where))
                if not region.actor:
                    violations.append(Violation(region.where, method, route))
    return violations, checked, unresolved, call_sites


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="in bảng route -> hàm gọi")
    ap.add_argument("--selftest", action="store_true", help="tự kiểm bằng canary")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    violations, checked, unresolved, call_sites = analyse()
    pins = load_pins()
    pinned = {p["where"] for p in pins.get("unresolved", [])}

    print(
        f"Cổng header actor — {len(client_files())} file client, "
        f"{call_sites} lời gọi tới route đòi {ACTOR_HEADER}."
    )

    if args.list:
        print()
        for route, where in sorted(checked):
            print(f"  {route:52} <- {where}")

    # Guard the guard. Nothing matched means the extractor stopped seeing the
    # client, not that the client became correct.
    if call_sites == 0:
        die(
            "không lời gọi nào khớp một route đòi actor. Trước đây con số này "
            "chưa bao giờ là 0, nên nhiều khả năng phép đọc client đã hỏng chứ "
            "không phải app đã sạch."
        )

    new_unresolved = [r for r in unresolved if r.where not in pinned]

    if violations:
        print()
        print(
            f"HỎNG — {len(violations)} chỗ gọi route đòi {ACTOR_HEADER} mà không gửi:"
        )
        for v in violations:
            print(f"  {v.method} {v.path}")
            print(f"      {v.where}")
        print()
        print("Đây là hình dạng của bug-191433: máy chủ trả 401 và màn hình báo")
        print("sự cố máy chủ. Sửa ở phía client, hoặc nếu route KHÔNG nên đòi")
        print("actor thì sửa ở phía route — nhưng phải sửa một trong hai.")

    # Deliberately not the word `HỎNG`. This block says nothing about whether
    # the client is correct -- it says this reader could not tell. Both blocks
    # print when both apply; only the exit code has to pick one.
    if new_unresolved:
        print()
        print(f"MÙ — {len(new_unresolved)} chỗ dựng URL mà cổng không phân giải được:")
        for r in new_unresolved:
            print(f"  {r.where}")
            for lit in r.unresolved[:3]:
                print(f"      {lit[:90]}")
        print()
        print("Đây KHÔNG phải kết luận là client thiếu header — cổng chưa đọc")
        print("được chỗ này nên chưa kết luận được gì. Viết lại đường dẫn thành")
        print(f"template literal mà cổng đọc được, hoặc ghim vào {UNRESOLVED_PIN.name}")
        print("— ghim là nói ra chỗ mù, không phải xoá nó:")
        print('  {"unresolved": [{"where": "<đúng dòng ở trên>", "reason": "..."}]}')

    # A confirmed defect outranks a blind spot: it is the one somebody can act
    # on, and letting `MÙ` overwrite it would report a real missing header as
    # "could not read".
    if violations:
        return EXIT_VIOLATION
    if new_unresolved:
        return EXIT_CANNOT_READ

    pinned_now = len([r for r in unresolved if r.where in pinned])
    print(
        f"ĐẠT — {call_sites} lời gọi đều gửi {ACTOR_HEADER}"
        f"{f', {pinned_now} chỗ mù đã ghim' if pinned_now else ''}."
    )
    return EXIT_OK


# --------------------------------------------------------------------------
# Tự kiểm: cổng phải ĐỎ được
# --------------------------------------------------------------------------

CANARY_BAD = """
const BASE = "http://x";
export function searchUrl(base: string): string {
  return `${base.replace(/\\/$/, "")}/places/search`;
}
export async function askSearch(query: string): Promise<void> {
  await fetch(searchUrl(BASE), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}
"""

CANARY_GOOD = CANARY_BAD.replace(
    '{ "Content-Type": "application/json" }',
    '{ "Content-Type": "application/json", "X-Actor-ID": actorId }',
).replace("askSearch(query: string)", "askSearch(query: string, actorId: string)")

# The same omission as CANARY_BAD, written the way that used to walk past this
# gate: the path lives in a lookup table, so the URL is `${base}${expr}` and the
# reader cannot name the route. Measured on main 7adf961, this file passed with
# exit 0 while CANARY_BAD failed with exit 1 -- identical bug, two verdicts.
# Một hằng ở cấp ngoài cùng KHÔNG được nuốt các hàm đứng sau nó.
#
# Đo trên chính cây này ngày 2026-09-03: `const MINH_SLUG = "minh";` trong
# `screens/chat/nhom.ts` quét tiếp qua ba hàm để tìm `=>` và gặp nó ở
# `json: () => Promise<unknown>` trong chữ ký `docLoi`. Ba hàm — trong đó có
# `headers()`, chỗ dựng header của cả file — biến mất khỏi đồ thị, và 15 lời
# gọi bị buộc tội "không gửi actor" trong khi chúng gửi đủ.
#
# Hình dạng ở đây được giữ ĐÚNG như bản gốc, kể cả thứ tự: hằng, rồi hàm dựng
# header KHÔNG chứa dấu `=` nào, rồi một chữ ký có `=>`. Đổi thứ tự đó là canary
# thôi tái lập.
CANARY_CONST_NUOT_HAM = """
const BASE = "http://x";
const SLUG = "minh";

function headers(actorId: string): Record<string, string> {
  return { "X-Actor-ID": actorId };
}

function docLoi(res: { json: () => Promise<unknown> }): string {
  return "x";
}

export async function docNhom(actorId: string, ctx: string): Promise<void> {
  await fetch(`${BASE}/contexts/${ctx}/members`, { headers: headers(actorId) });
}
"""

# Cặp đỏ của canary trên, dưới cùng phép đo. Không có nó, một `_missing_actor`
# luôn trả False cũng "đạt" canary sạch — và cái file này tồn tại là để chặn
# đúng kiểu xanh đó.
CANARY_CONST_NUOT_HAM_XAU = CANARY_CONST_NUOT_HAM.replace(
    "{ headers: headers(actorId) }", "{ headers: { Accept: \"application/json\" } }"
)

CANARY_BLIND = """
const BASE = "http://x";
const ENDPOINTS = { search: "/places/search" };
export async function askSearch(query: string): Promise<void> {
  await fetch(`${BASE}${ENDPOINTS.search}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}
"""


def _missing_actor(regions: list[Region]) -> bool:
    """A call site naming `/places/search` and sending no actor header."""
    return any(
        r.requester and "/places/search" in r.paths and not r.actor for r in regions
    )


def _missing_actor_members(regions: list[Region]) -> bool:
    """A call site naming `/contexts/{}/members` and sending no actor header.

    A second probe rather than a second path in `_missing_actor`, because the
    pair it reads has to fail for its OWN reason. Widening the existing probe
    would have made the const-swallow canary pass on the strength of
    `/places/search`, which is not the route it is about.
    """
    return any(
        r.requester and "/contexts/{}/members" in r.paths and not r.actor
        for r in regions
    )


def _blind_url(regions: list[Region]) -> bool:
    """A call site whose URL this reader admits it could not follow."""
    return any(r.requester and r.unresolved for r in regions)


def selftest() -> int:
    """Prove the checker can be red, on the canaries the repo insists on.

    A checker only ever run against a healthy tree proves nothing: `[]` and
    exit 0 is what a dead scanner prints too. So: a file that omits the header
    must be reported, and the same file with the header must not be.

    Each canary is paired with the probe that reads it, because the two failure
    modes are different questions. "Did it see the omission" is not the same as
    "did it admit it saw nothing", and a canary answering only the first is how
    the `${base}${expr}` shape stayed invisible while this self-check printed
    ĐẠT. Every red canary is paired with a clean one under the same probe, so a
    probe that answers True to everything cannot pass either.
    """

    import shutil
    import tempfile

    ok = True
    for label, source, probe, want_violation in (
        ("canary xấu", CANARY_BAD, _missing_actor, True),
        ("canary sạch", CANARY_GOOD, _missing_actor, False),
        ("canary mù", CANARY_BLIND, _blind_url, True),
        ("canary mù/sạch", CANARY_GOOD, _blind_url, False),
        ("hằng nuốt hàm/sạch", CANARY_CONST_NUOT_HAM, _missing_actor_members, False),
        ("hằng nuốt hàm/xấu", CANARY_CONST_NUOT_HAM_XAU, _missing_actor_members, True),
    ):
        tmp = Path(tempfile.mkdtemp(prefix="actor-canary-"))
        # Cố ý KHÔNG ghi vào CLIENT_DIR. `build_graph` nhận thẳng danh sách file
        # nên canary không cần nằm trong cây client để được đọc; bản trước ghi
        # vào đó và cây client thật bẩn trong lúc mỗi lượt gate chạy, đủ để bộ
        # đọc của lane khác thấy và buộc tội sản phẩm. Thư mục tạm này vốn đã
        # được tạo sẵn ở dòng trên mà không ai dùng — đây là chỗ nó phải dùng.
        target = tmp / "__actor_canary__.ts"
        try:
            target.write_text(source, encoding="utf-8")
            regions = build_graph([target])
            got = probe(regions)
            mark = "ĐẠT" if got == want_violation else "HỎNG"
            if got != want_violation:
                ok = False
            print(
                f"  {mark:6} {label}: "
                f"{'có' if got else 'không có'} vi phạm "
                f"(mong đợi {'có' if want_violation else 'không có'})"
            )
        finally:
            target.unlink(missing_ok=True)
            shutil.rmtree(tmp, ignore_errors=True)

    print()
    if ok:
        print(
            "Tự kiểm ĐẠT — cổng đỏ được khi thiếu header, khi URL không đọc "
            "được, và xanh khi không có cả hai."
        )
        return 0
    print("Tự kiểm HỎNG — cổng này không phân biệt được thiếu với có.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    os.chdir(REPO_ROOT)
    raise SystemExit(main())
