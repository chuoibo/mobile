#!/usr/bin/env python3
"""The server answering the published port must serve the routes this tree declares.

## Why this exists

Every gate in this repository reads something that is *at rest*: the migration
files form one chain, the app calls paths the source declares, the image runs
as non-root. Nothing asked the process that is actually listening on 8099 what
it is. So nothing could see the one thing that went wrong on 2026-08-29:

    the demo machine served code from before two merges, for six hours,
    while reporting healthy the entire time.

The mechanism is worth writing down, because it is built into Compose and will
happen again. `api` declares `depends_on: migrate: service_completed_successfully`.
When `migrate` fails, `docker compose up -d` aborts *before* it touches `api` --
and the previously running `api` container is left alone, still serving the
port. The stack is then in its worst state: an old process answering a fresh
URL. `make up` exits non-zero, but the failure text is about alembic, and the
API that keeps answering makes it look survivable.

Nothing downstream noticed:

  - `/healthz` deliberately never touches the database (CLAUDE.md), so it
    answered 200 throughout -- correctly. It reports "this process serves",
    which was true. It was the wrong question.
  - Compose reported the container `healthy`, because it was.
  - `check_db_revision.sh` would have caught the *schema* half, but `make up`
    dies at `migrate` long before `make smoke` runs it.

Measured on the real machine at 2026-08-29T21:2xZ, before the fix:

    code (services/api at main 0fbf500)   42 paths
    server (http://127.0.0.1:8099)        37 paths

    missing:  /places/search                                (F12, #155)
              /contexts/{context_id}/checkins               (F46, #136)
              /outings/{outing_id}/checkins                 (F46)
              /outing-stops/{stop_id}/checkins              (F46)
              /outings/{outing_id}/invites/{invite_id}/revoke

Five routes the phone calls, answering 404 on the machine the demo runs on.

## What it checks

One thing. The set of paths the running server publishes in its own
`/openapi.json` must contain every path `services/api` declares here. Both
sides are rendered, never kept by hand -- a hand-kept list is a third copy to
drift.

## Why "contains" and not "equals"

A server carrying paths this tree does not have is a different situation and
usually a legitimate one: the shared stack was last built from a branch, or
from a main that is ahead of the worktree you are standing in. That is
reported, and it does not fail the gate. A server *missing* what this tree
declares is the failure, because it is the direction that answers 404 to a
phone.

## Why it compares against this worktree

`check_db_revision.sh` argues the opposite for schema, and the difference is
real rather than an inconsistency. Migrating a shared database up to an
unmerged branch revision is destructive to every other lane -- that is what
caused the outage its header describes. Reading routes is not: nothing is
written, and the caller learns the true answer to "does the server I am about
to test carry my code".

The contract is anchored by where it is called from. `make smoke` runs at the
end of `make up`, which has just built the image from this worktree; there the
question "does the port serve what I just built" has exactly one right answer
and no false-positive mode. Called on its own from a branch whose API is not
built yet, it reports the branch's routes as missing, which is the honest
answer and the same convention `check_api_contract.py` documents for itself.

## What it does NOT prove

- Nothing here executes a request beyond fetching the schema document. A path
  that is served but returns 500 to every caller passes. `tests/postgres` and
  the QA walks remain the only things that prove a route works.
- It compares paths, not methods, bodies, or permissions. A path present for
  GET and called with POST passes.
- It says nothing about the database. A server can carry every route and still
  answer 500 on the ones whose tables are missing -- that is the other half,
  and `check_db_revision.sh` is the half that answers it. `make smoke` runs
  both because either alone reports a broken stack as usable.

Usage:
  scripts/check_server_routes.py --url http://127.0.0.1:8099
  scripts/check_server_routes.py --url http://127.0.0.1:8099 --json

Exit codes: 0 the server carries every route this tree declares,
1 the server is behind this tree,
2 the check could not run -- and could not run is never a pass.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "services" / "api"

# Exit 2, not 1. "Could not run" and "ran and found a problem" are different
# answers, and collapsing them is how a dead gate reads as a failing one.
EXIT_OK = 0
EXIT_BEHIND = 1
EXIT_CANNOT_RUN = 2


def die(message: str) -> None:
    """Report that the check could not run, and exit 2."""
    print(f"check_server_routes: {message}", file=sys.stderr)
    raise SystemExit(EXIT_CANNOT_RUN)


def code_paths() -> set[str]:
    """Paths `services/api` declares, rendered by FastAPI itself.

    Rendered in a subprocess so this script does not need the API's imports on
    its own path, and so an import error in the app surfaces as this gate
    failing loudly rather than as a stack trace three frames deep.
    """
    code = (
        "import json;from app.api.main import app;"
        "print(json.dumps(sorted(app.openapi()['paths'])))"
    )
    if not API_DIR.is_dir():
        die(f"không thấy {API_DIR} — chạy từ trong repo.")
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
        return set(json.loads(out.stdout))
    except json.JSONDecodeError as exc:
        die(f"OpenAPI dựng tại chỗ trả về thứ không phải JSON: {exc}")
    raise AssertionError("unreachable")  # pragma: no cover


def server_paths(url: str, timeout: float) -> set[str]:
    """Paths the running server publishes, read from its own /openapi.json.

    The content type is checked before the body is parsed. A reverse proxy or a
    stale container answering an HTML error page is a real thing that happens
    on this machine, and `json.loads` on an error page fails with a message
    about character 0 that sends the reader to the wrong place.
    """
    doc_url = url.rstrip("/") + "/openapi.json"
    try:
        with urllib.request.urlopen(doc_url, timeout=timeout) as resp:
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
            body = resp.read()
    except urllib.error.HTTPError as exc:
        die(f"{doc_url} trả về HTTP {exc.code}. Máy chủ có đang chạy đúng ảnh không?")
    except (urllib.error.URLError, OSError) as exc:
        die(
            f"không gọi được {doc_url}: {exc}\n"
            "   Máy chủ chưa chạy. Gỡ:  make up"
        )

    if ctype != "application/json":
        die(
            f"{doc_url} trả về Content-Type '{ctype}', không phải application/json.\n"
            "   Cổng này đang nói chuyện với thứ không phải API."
        )
    try:
        doc = json.loads(body)
    except json.JSONDecodeError as exc:
        die(f"{doc_url} trả về JSON hỏng: {exc}")

    paths = doc.get("paths")
    if not isinstance(paths, dict):
        die(f"{doc_url} không có mục 'paths' — đây không phải tài liệu OpenAPI.")
    # An OpenAPI document with zero paths is not a clean tree, it is a document
    # that told us nothing. Every dead detector in this repository has looked
    # exactly like this: empty result, exit 0.
    if not paths:
        die(f"{doc_url} khai 0 route. Không có gì để đối chiếu, nên không thể ĐẠT.")
    return set(paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Máy chủ đang chạy phải phục vụ đủ route mà cây này khai."
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Gốc của API đang chạy, ví dụ http://127.0.0.1:8099",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--json", action="store_true", help="In kết quả dạng máy đọc")
    args = parser.parse_args(argv)

    served = server_paths(args.url, args.timeout)
    declared = code_paths()

    missing = sorted(declared - served)
    extra = sorted(served - declared)

    if args.json:
        print(
            json.dumps(
                {
                    "url": args.url,
                    "declared": len(declared),
                    "served": len(served),
                    "missing": missing,
                    "extra": extra,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    if missing:
        print(file=sys.stderr)
        print("!! Máy chủ đang chạy MÃ CŨ hơn cây này.", file=sys.stderr)
        print(f"   máy chủ: {args.url}", file=sys.stderr)
        print(f"   cây này khai {len(declared)} route, máy chủ phục vụ {len(served)}.",
              file=sys.stderr)
        print(file=sys.stderr)
        print(f"   Thiếu {len(missing)} route — app gọi tới sẽ nhận 404:", file=sys.stderr)
        for path in missing:
            print(f"      {path}", file=sys.stderr)
        print(file=sys.stderr)
        print(
            "Hay gặp nhất: `migrate` hỏng nên `docker compose up` dừng TRƯỚC khi\n"
            "thay container `api`, và container cũ vẫn giữ cổng. `make up` báo đỏ\n"
            "ở dòng alembic, còn API thì vẫn trả lời — nên nhìn như vẫn dùng được.\n"
            "   Kiểm:  make db-check   (xem database có đứng sau không)\n"
            "   Gỡ:    sửa migrate cho xanh, rồi  make up",
            file=sys.stderr,
        )
        return EXIT_BEHIND

    # Printed on the pass path too. Counts falling while the tree grows is this
    # check going blind, and going blind looks exactly like a clean tree.
    print(
        f"Route máy chủ: {len(served)} phục vụ / {len(declared)} cây này khai — "
        "đủ, không thiếu route nào."
    )
    if extra:
        print(
            f"   ({len(extra)} route máy chủ có mà cây này không: máy chủ dựng từ "
            "nhánh khác hoặc từ main mới hơn. Không phải lỗi.)"
        )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
