#!/usr/bin/env python3
"""Every route the server declares must have something that calls it.

## Why this exists

`scripts/check_api_contract.py` asks one direction of one question: every path
`apps/mobile` calls must exist on the server. That direction has had a gate
since 2026-08-29.

The other direction had none. A route the server declares that no screen ever
calls does not exist as far as a user is concerned -- it ships, it is tested,
it is merged, and nobody can reach it. `tests/postgres` proves it answers,
`tests/api` proves it orchestrates, the OpenAPI document lists it, and every
one of those stays green while the feature is unreachable.

## Why this is a separate reader from its twin, and not a `not in` flipped

The two directions need opposite scopes, and getting that backwards is how the
two hand-rolled attempts on 2026-08-30 both failed:

  - Substring matching (`"posts" in source`) reported the four `/posts` routes
    from #308 as called. This codebase writes about itself constantly; the word
    "posts" appears in prose in `CheckIn.tsx` and `KyNiem.tsx` and in neither
    case is it a URL. FALSE PASS -- four dead routes called alive.
  - Whole-string matching reported 32 routes dead, including `/places/search`
    and the `/contexts/{id}/messages` family, which the client demonstrably
    calls. The client writes `` `${base}/contexts/${nhomId}/messages` ``; the
    server writes `/contexts/{context_id}/messages`. Same route, different
    text. FALSE FAIL -- and a gate that is wrong about 32 routes on the day it
    lands is a gate nobody runs twice.

Both are avoided by not writing a third URL reader. This file imports the one
`check_api_contract.py` already has -- `tokenize`, `literal_shape`,
`path_from_shape`, `normalise` -- so client and server are compared after the
same normalisation, and `${nhomId}` and `{context_id}` collapse to the same
hole before anything is compared.

## The one place the scope deliberately differs from its twin

`check_api_contract.py` only reads literals reachable from a call to `fetch` /
`call` / `translated`. This file reads EVERY path-shaped literal in
`apps/mobile/src`, whether or not the reader can connect it to a request.

That difference is not an oversight, it is forced by which way a mistake cuts:

  - For "the app calls a route that is not there", a narrow scope is safe. Miss
    a call site and you under-report; you never invent a 404 that is not there.
  - For "nobody calls this route", a narrow scope is the DANGEROUS one. Every
    call the reader cannot follow becomes a route falsely declared dead. The
    pinned blind spots in `.api-contract-unresolved.json` say this outright --
    `taiAnhCoQuyen(url, ...)` hides the path of every image route from the twin
    reader. Measured on main at 8b6f847: under the twin's scope this file would
    report 29 dead routes, under the wider scope 22, and all seven of the
    difference are routes the twin cannot see rather than routes anybody
    deleted.

So the rule here is deliberately generous to the client: if the route is named
anywhere in the client source as a literal, something plausibly calls it and
this gate stays quiet. It still refuses prose, because comments are stripped by
`tokenize` before any literal is read -- which is exactly the distinction the
substring attempt could not make.

## What it does NOT prove

- Not that the call is reachable. A path named in a module nobody imports
  counts as called, the same limitation its twin states about itself.
- Not that the call is correct. Method, body, headers and permissions are all
  outside this: a route named in a literal and called with the wrong verb
  passes here.
- Not that the screen works. `tests/qa` and the QA walks remain the only things
  that prove a user can reach the feature.

## The blind spot this reader cannot close, stated rather than hidden

A URL the SERVER hands to the client never appears in client source, so this
reader structurally cannot see its caller. `AlbumPhoto.image_url`
(`services/api/app/api/schemas.py:1496`) is exactly that: it carries the
`/contexts/{id}/photos/{id}` path in a response body, and the client fetches
whatever arrived. No amount of reading `apps/mobile/src` finds that call.

There is no honest way to detect it from source, so it is not detected -- it is
written down. Such a route belongs in `.server-routes-uncalled.json` with a
reason saying so, and the reason has to name the schema field that carries the
URL, so the next reader can check the claim instead of trusting it. Marking one
of these as "nobody calls it" without that sentence would be this gate telling
the same kind of lie it was built to catch.

It answers exactly one question -- is this route named anywhere on the client
at all -- and a `no` to that is conclusive while a `yes` is only permission for
the other gates to speak.

Usage:
  scripts/check_server_routes_called.py            check the tree this file is in
  scripts/check_server_routes_called.py --json     the same findings, machine-readable
  scripts/check_server_routes_called.py --selftest prove the gate can be red, on canaries

Exit codes: 0 every route has a caller or is accounted for, 1 a route has none,
2 the check could not run -- and could not run is never a pass.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The twin gate, imported for its reader rather than re-implemented. Loaded by
# path because `scripts/` is not a package and this file must run as a plain
# script from the repository root, which is how `gate.sh` invokes it.
_TWIN_PATH = REPO_ROOT / "scripts" / "check_api_contract.py"
_SPEC = importlib.util.spec_from_file_location("check_api_contract", _TWIN_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - defensive
    raise RuntimeError(f"không nạp được {_TWIN_PATH}")
twin = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = twin
_SPEC.loader.exec_module(twin)


# --------------------------------------------------------------------------
# Miễn trừ: route có NGƯỜI GỌI KHÁC, không phải route chết
# --------------------------------------------------------------------------

# Routes whose caller is not `apps/mobile` at all. Each one is written out in
# full with the file that calls it, because the alternative -- a prefix or a
# regular expression over `/g/` -- is a blanket, and a blanket cannot tell an
# exemption from the next route somebody adds under the same prefix. Adding a
# guest route makes this gate red until a human writes down who calls it, and
# that is the intended cost: it is one line, and it is the only moment anybody
# is forced to say out loud that a route has a caller.
#
# `reason` is not decoration. The whole failure this repository keeps hitting is
# a list of accepted exceptions that nobody can distinguish from a list of
# shrugs, so an entry without a reason is refused by `_load_exemptions`.
EXEMPT_ROUTES = (
    {
        "route": "/g/{token}",
        "reason": (
            "Trang khách. Khách mở nó từ link trong envelope VietQR, không phải "
            "app gọi. Template render nó là services/api/app/web/templates/"
            "guest.html; hai template khác link ngược về nó (guest_not_me.html:69, "
            "guest_wrong_amount.html:105)."
        ),
    },
    {
        "route": "/g/{token}/da-chuyen",
        "reason": (
            "Khách bấm 'đã chuyển' trên trang khách. Người gọi là form POST ở "
            "services/api/app/web/templates/guest.html:165, không phải apps/mobile."
        ),
    },
    {
        "route": "/g/{token}/doi-so-tien",
        "reason": (
            "Khách báo số tiền không đúng. Người gọi: link ở guest.html:119 và "
            "form POST ở guest_wrong_amount.html:36."
        ),
    },
    {
        "route": "/g/{token}/khong-phai-toi",
        "reason": (
            "Khách nói mình không phải người được ghi tên. Người gọi: link ở "
            "guest.html:121 và form POST ở guest_not_me.html:52."
        ),
    },
    {
        "route": "/g/{token}/xin-cach-tinh",
        "reason": (
            "Khách xin cách tính. Người gọi: form POST ở guest_wrong_amount.html:90."
        ),
    },
)

# Routes with no caller anywhere today. Separate from EXEMPT_ROUTES on purpose:
# an exemption says "this is called, just not from here", debt says "this is
# genuinely unreachable and we are shipping it anyway". Collapsing the two would
# lose the only distinction that matters when somebody reads this list later.
#
# Held in a file rather than in code so the diff that pays a debt down is one
# line in a data file rather than a code change, and so `--json` consumers can
# read the outstanding list. Every entry needs a reason, same rule as above.
DEBT_PIN = REPO_ROOT / ".server-routes-uncalled.json"


@dataclass(frozen=True)
class Accounted:
    """A route excused from needing a caller, and why."""

    route: str
    reason: str
    kind: str  # "mien" (has another caller) | "no" (genuinely uncalled, pinned)


def _require_reason(entry: dict, where: str) -> tuple[str, str]:
    route = entry.get("route")
    if not route:
        raise RuntimeError(f"{where}: có mục thiếu 'route'")
    reason = entry.get("reason")
    if not reason:
        raise RuntimeError(f"{where}: {route} thiếu 'reason'")
    return route, reason


def load_exemptions() -> dict[str, Accounted]:
    """The in-code exemption list, keyed the way a server route is looked up."""
    out: dict[str, Accounted] = {}
    for entry in EXEMPT_ROUTES:
        route, reason = _require_reason(entry, "EXEMPT_ROUTES")
        out[twin.normalise(route)] = Accounted(route, reason, "mien")
    return out


def load_debt() -> dict[str, Accounted]:
    """Routes already known to have no caller.

    An absent file means no debt rather than an error -- a branch that owes
    nothing needs no file. A malformed one is fatal: reading it as empty would
    turn every outstanding debt into a finding at once, and a gate that goes
    red in bulk for a typo gets reverted rather than read.
    """
    if not DEBT_PIN.exists():
        return {}
    try:
        raw = json.loads(DEBT_PIN.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{DEBT_PIN.name} không phải JSON hợp lệ: {exc}") from exc

    out: dict[str, Accounted] = {}
    for entry in raw.get("uncalled", []):
        route, reason = _require_reason(entry, DEBT_PIN.name)
        out[twin.normalise(route)] = Accounted(route, reason, "no")
    return out


# --------------------------------------------------------------------------
# Đọc client: mọi literal hình dạng đường dẫn, không chỉ literal ở chỗ gọi
# --------------------------------------------------------------------------


@dataclass
class Mention:
    """Where in the client a route is named."""

    file: str
    line: int


def mentions_in_source(src: str, rel: str) -> dict[str, list[Mention]]:
    """Normalised API paths named by a literal in one client file.

    Comments never reach here: `tokenize` classifies them as their own token
    kind and `literal_shape` returns None for anything that is not a string or
    a template. That is the whole reason this is not a substring search --
    `CheckIn.tsx` says "the button posts" in prose, and a substring reader
    counts that as a caller for `POST /posts`.
    """
    found: dict[str, list[Mention]] = {}
    for token in twin.tokenize(src):
        shape = twin.literal_shape(token)
        if shape is None:
            continue
        api_path = twin.path_from_shape(shape)
        if api_path is None:
            continue
        key = twin.normalise(api_path)
        found.setdefault(key, []).append(Mention(rel, twin.line_of(src, token.start)))
    return found


def client_mentions() -> dict[str, list[Mention]]:
    """Every route named anywhere in `apps/mobile/src`."""
    all_found: dict[str, list[Mention]] = {}
    for path in twin.client_files():
        rel = str(path.relative_to(REPO_ROOT))
        for key, where in mentions_in_source(
            path.read_text(encoding="utf-8"), rel
        ).items():
            all_found.setdefault(key, []).extend(where)
    return all_found


# --------------------------------------------------------------------------
# So sánh
# --------------------------------------------------------------------------


@dataclass
class Finding:
    kind: str
    route: str
    message: str


def uncalled(
    contract,
    mentions: dict[str, list[Mention]],
    exemptions: dict[str, Accounted],
    debt: dict[str, Accounted],
) -> tuple[list[Finding], list[Accounted], list[str]]:
    """Routes with no caller, the ones excused, and the excuses gone stale.

    Split out from `check` so the whole comparison can be exercised on a
    hand-built contract with no OpenAPI render and no repository -- which is
    what `--selftest` and `tests/test_server_routes_called_gate.py` do.
    """
    findings: list[Finding] = []
    excused: list[Accounted] = []
    stale: list[str] = []

    for key in sorted(contract.routes):
        spelling = contract.spelling.get(key, key)
        if key in mentions:
            # Called AND still pinned as debt is the good news case: somebody
            # built the screen. Reported so the pin can be struck off, never
            # fatal -- a gate that goes red for an improvement is switched off
            # within a day.
            if key in debt:
                stale.append(f"{spelling} -- đã có người gọi, gỡ khỏi {DEBT_PIN.name}")
            continue
        if key in exemptions:
            excused.append(exemptions[key])
            continue
        if key in debt:
            excused.append(debt[key])
            continue
        findings.append(
            Finding(
                "route_khong_ai_goi",
                spelling,
                f"máy chủ khai {spelling} nhưng không màn nào trong "
                f"apps/mobile/src nhắc tới đường dẫn này -- với người dùng, "
                f"route này chưa tồn tại",
            )
        )

    # An excuse for a route the server no longer declares is an excuse pointing
    # at nothing. Reported, not fatal, for the same reason as above: it means
    # somebody deleted a dead route, which is the outcome this gate wants.
    declared = set(contract.routes)
    for key, entry in sorted(
        list(exemptions.items()) + list(debt.items()), key=lambda kv: kv[1].route
    ):
        if key not in declared:
            stale.append(f"{entry.route} -- máy chủ không còn khai route này")

    return findings, excused, stale


def check() -> tuple[list[Finding], list[Accounted], list[str], dict]:
    if not twin.CLIENT_ROOT.is_dir():
        raise RuntimeError(
            f"{twin.CLIENT_ROOT.relative_to(REPO_ROOT)} không có trên nhánh này -- "
            "không có client để đối chiếu"
        )
    if not twin.API_ROOT.is_dir():
        raise RuntimeError("services/api không có trên nhánh này")

    contract = twin.read_contract(twin.load_openapi())
    if not contract.routes:
        raise RuntimeError(
            "OpenAPI dựng được nhưng không có route nào -- từ chối coi là đạt"
        )

    mentions = client_mentions()
    # Zero is what a broken reader prints, and it is also what a client with no
    # API calls prints. Neither is a pass. This is the same refusal the twin
    # gate makes about its own path count, and it is the single guard that
    # stops this file from reporting every route on the server as dead the day
    # somebody breaks `tokenize`.
    if not mentions:
        raise RuntimeError(
            "không đọc được đường dẫn API nào trong apps/mobile/src -- hoặc "
            "client không còn gọi API, hoặc bộ đọc đã hỏng. Cả hai đều không "
            "phải 'đạt', và nếu coi là đạt thì mọi route đều bị báo chết."
        )

    exemptions = load_exemptions()
    debt = load_debt()
    findings, excused, stale = uncalled(contract, mentions, exemptions, debt)

    summary = {
        "routes_may_chu": len(contract.routes),
        "route_co_nguoi_goi": len(contract.routes) - len(excused) - len(findings),
        "route_duoc_mien": sum(1 for e in excused if e.kind == "mien"),
        "route_dang_no": sum(1 for e in excused if e.kind == "no"),
        "route_khong_ai_goi": len(findings),
        "duong_dan_client_doc_duoc": len(mentions),
        "ghim_cu": stale,
    }
    return findings, excused, stale, summary


# --------------------------------------------------------------------------
# Tự kiểm: cổng phải ĐỎ được, và phải XANH được
# --------------------------------------------------------------------------

CANARY_ROUTE = "/khong-ai-goi-canary"


def _contract_of(*paths: str):
    """A server declaring exactly these paths. No OpenAPI render, no database."""
    return twin.read_contract({"paths": {p: {"get": {}} for p in paths}})


def _client(*sources: str) -> dict[str, list[Mention]]:
    found: dict[str, list[Mention]] = {}
    for i, src in enumerate(sources):
        for key, where in mentions_in_source(src, f"__canary_{i}__.ts").items():
            found.setdefault(key, []).extend(where)
    return found


def _run_canary(contract, sources: tuple[str, ...]) -> list[Finding]:
    """The comparison under the real exemption list and an EMPTY debt list.

    Empty on purpose: the canary asks whether the gate can see a route with no
    caller, not whether this repository happens to have written that particular
    route down as debt. Reading the real pin file here would let a growing debt
    list quietly disable the canaries.
    """
    findings, _, _ = uncalled(contract, _client(*sources), load_exemptions(), {})
    return findings


# A route nobody names. The defect this gate exists for.
CANARY_DEAD = '\nexport const nothing = "/healthz";\n'

# Every route named. The control for the case above: a probe that answers
# "dead" to everything would fail this one, and a table of nothing but red rows
# cannot tell a working gate from a stuck one.
CANARY_ALL_CALLED = """
import { call } from "./api";
export async function a() { return call<void>("/healthz", { method: "GET" }); }
export async function b() { return call<void>(`/contexts/${id}/messages`, {}); }
"""

# The client spells the parameter its own way. Measured 2026-08-30: whole-string
# matching called 32 live routes dead on exactly this shape, `/places/search`
# and the `/contexts/{id}/messages` family among them. Must stay GREEN.
CANARY_PARAM_RENAMED = """
import { call } from "./api";
export async function c() { return call<void>(`${base}/contexts/${nhomId}/messages`, {}); }
"""

# `/posts` is a suffix of `/people/{id}/posts`, and the word appears in prose in
# two screens. Substring matching called all four of #308's `/posts` routes
# alive on exactly this shape. Must be RED, and must name `/posts`.
CANARY_SUBSTRING_TRAP = """
import { call } from "./api";
/* The button posts, and the list underneath is re-read from the server. */
export async function d() { return call<void>(`/people/${id}/posts`, {}); }
"""

# A guest route that is NOT on the exemption list. Must be RED: the exemption is
# five spelled-out routes, and the moment somebody rewrites it as a prefix over
# `/g/` this canary is the thing that notices.
CANARY_NEW_GUEST_ROUTE = '\nexport const nothing = "/healthz";\n'


def selftest() -> int:
    """Prove the gate reddens on a dead route, and stays quiet when it should.

    Every row asserts on the route NAME, not merely on "some finding appeared".
    A gate that goes red for the wrong route reads identically to one that
    works, and this repository has shipped that mistake before.
    """
    cases = (
        (
            "canary xấu: route không ai gọi",
            _contract_of("/healthz", CANARY_ROUTE),
            (CANARY_DEAD,),
            {CANARY_ROUTE},
        ),
        (
            "đối chứng: mọi route đều có người gọi",
            _contract_of("/healthz", "/contexts/{context_id}/messages"),
            (CANARY_ALL_CALLED,),
            set(),
        ),
        (
            "đối chứng: client đặt tên tham số khác máy chủ",
            _contract_of("/contexts/{context_id}/messages"),
            (CANARY_PARAM_RENAMED,),
            set(),
        ),
        (
            "canary xấu: tên route là hậu tố của route khác",
            _contract_of("/posts", "/people/{person_id}/posts"),
            (CANARY_SUBSTRING_TRAP,),
            {"/posts"},
        ),
        (
            "đối chứng: route trang khách đã ghi lý do",
            _contract_of("/g/{token}", "/g/{token}/da-chuyen"),
            (CANARY_DEAD,),
            set(),
        ),
        (
            "canary xấu: route trang khách MỚI chưa ai ghi lý do",
            _contract_of("/g/{token}/canary-chua-ghi-ly-do"),
            (CANARY_NEW_GUEST_ROUTE,),
            {"/g/{token}/canary-chua-ghi-ly-do"},
        ),
    )

    ok = True
    for label, contract, sources, want in cases:
        got = {f.route for f in _run_canary(contract, sources)}
        if got != want:
            ok = False
        print(
            f"  {'ĐẠT' if got == want else 'HỎNG':6} {label}: "
            f"báo {sorted(got) or 'không route nào'} "
            f"(mong đợi {sorted(want) or 'không route nào'})"
        )

    print()
    if ok:
        print(
            "Tự kiểm ĐẠT — cổng đỏ được khi một route không ai gọi và gọi đúng "
            "tên nó, xanh khi client viết tham số theo cách khác, và không nuốt "
            "route trang khách chưa ghi lý do."
        )
        return 0
    print(
        "Tự kiểm HỎNG — cổng này không phân biệt được route chết với route sống.",
        file=sys.stderr,
    )
    return 1


# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="in findings dạng JSON")
    parser.add_argument("--selftest", action="store_true", help="tự kiểm bằng canary")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    try:
        findings, excused, stale, summary = check()
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
                    "duoc_mien": [e.__dict__ for e in excused],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if findings else 0

    print(
        f"Máy chủ khai {summary['routes_may_chu']} route. "
        f"{summary['route_co_nguoi_goi']} có người gọi, "
        f"{summary['route_duoc_mien']} miễn (người gọi ở nơi khác), "
        f"{summary['route_dang_no']} đang nợ (đã ghi nhận là chưa ai gọi), "
        f"{summary['route_khong_ai_goi']} không ai gọi và chưa ghi nhận."
    )

    # Printed on every run, including the passing one. A debt list that stops
    # being read is a debt list that stops being paid, and "exit 0" with the
    # names hidden is exactly how 22 unreachable routes would read as clean.
    debt_routes = [e for e in excused if e.kind == "no"]
    if debt_routes:
        print()
        print(
            f"{len(debt_routes)} route KHÔNG AI GỌI đã được ghi nhận trong {DEBT_PIN.name}:"
        )
        for entry in debt_routes:
            print(f"  {entry.route}")
        print("  Ghi nhận không phải là đã sửa — mỗi dòng ở trên là một tính năng")
        print("  đã merge mà người dùng chưa chạm tới được.")

    for note in stale:
        print(f"GHIM CŨ: {note}")

    if not findings:
        print()
        print("Không có route mới nào bị bỏ rơi.")
        return 0

    print()
    for finding in findings:
        print(f"{finding.route}  [{finding.kind}]")
        print(f"    {finding.message}")
    print()
    print("Sửa bằng một trong ba cách, theo đúng thứ tự ưu tiên:")
    print("  1. Gọi nó từ một màn trong apps/mobile/src -- đây là cách đúng.")
    print("  2. Xoá route nếu không ai định gọi. Route chết vẫn là bề mặt tấn công.")
    print(f"  3. Nếu phải ship trước màn: thêm vào {DEBT_PIN.name} kèm 'reason'.")
    print("     Người gọi ở NGOÀI apps/mobile (ví dụ template trang khách) thì")
    print("     thuộc EXEMPT_ROUTES trong chính file này, không phải nợ.")
    print()
    print(f"{len(findings)} route không ai gọi.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
