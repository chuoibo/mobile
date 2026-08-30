#!/usr/bin/env python3
"""The demo machine must serve exactly what `main` declares -- no fewer, no more.

## Why this is a second gate and not a flag on the first one

`check_server_routes.py` asks "does the port serve what THIS WORKTREE declares".
That is the right question at the end of `make up`, which has just built the
image from the tree you are standing in.

It is the wrong question for the demo machine, and on 2026-08-30 it answered
the wrong question with a clean pass. Measured on this machine at 15:5xZ,
before this gate existed:

    $ cd /home/lakiet/mobile && python3 scripts/check_server_routes.py \
        --url http://127.0.0.1:8099 --json
    {"declared": 58, "served": 58, "missing": [], "extra": []}
    Route máy chủ: 58 phục vụ / 58 cây này khai — đủ, không thiếu route nào.
    exit 0

    $ git -C /tmp/mainref log --oneline -1     # origin/main
    3e64ccf ...
    MAIN ROUTES: 62

Both numbers were 58 because the demo stack builds from `/home/lakiet/mobile`,
that checkout was sitting 16 commits behind `origin/main`, and the gate read
the same stale tree it built the image from. Server and reference were the same
mistake, so the comparison could not see it. Four routes were missing and every
signal on the machine was green:

    /areas                                          F45 điểm hẹn giữa đường
    /contexts/{context_id}/budget                   F34 ngân sách
    /contexts/{context_id}/messages/{message_id}/expense-draft   F24
    /screenshots/scan                               F26 quét ảnh chụp màn hình

That is green-by-construction: a check whose two sides are read from one source
cannot fail, and it reads exactly like a check that is passing.

## What it checks

The set of paths the running server publishes in its own `/openapi.json` must
EQUAL the set of paths `services/api` declares at `--ref` (default
`origin/main`). Both sides are rendered by FastAPI; neither is kept by hand.

## Why equality, and not "contains" like its sibling

`check_server_routes.py` deliberately tolerates a server carrying extra paths:
the shared stack is often built from somebody's branch, and failing that would
be a false positive people would learn to ignore.

The demo machine is the one place where that tolerance is wrong. It is what a
leader opens to decide whether the product works. A route it serves that `main`
does not have is a feature demonstrated from an unmerged branch -- it will
vanish the next time anybody rebuilds, and a demo that shows what does not
exist is a worse failure than one that is merely behind. So both directions
fail here, with different text, because the fixes differ:

    missing -> the demo is behind main; rebuild it
    extra   -> the demo was built from a branch; rebuild it from main

## Why it fetches

Comparing against a local `origin/main` that itself has not been fetched is the
same bug one layer up: a stale reference cannot detect staleness. So the gate
fetches, and if it cannot fetch it exits 2 rather than comparing against a ref
of unknown age. `--no-fetch` is the explicit escape hatch for offline use, and
it says so in the output -- a gate that silently degrades is the thing this
file exists to argue against.

## What it does NOT prove

- Nothing here sends a request beyond fetching the schema document. A path that
  is served but answers 500 to every caller passes this gate. The hero-path
  walk and `tests/postgres` remain the only things that prove a route works.
- It compares paths, not methods, bodies, status codes, or permissions.
- It says nothing about the database. A server can carry every route of main
  and still answer 500 where tables are missing; `check_db_revision.sh` is the
  half that answers that, and `make smoke` runs it.
- It says nothing about the mobile bundle, which is built separately and can be
  older than the API on the same machine.

Usage:
  scripts/check_demo_matches_main.py
  scripts/check_demo_matches_main.py --url http://127.0.0.1:8099 --json
  scripts/check_demo_matches_main.py --ref origin/main --no-fetch

Exit codes: 0 the demo serves exactly `--ref`,
1 the demo differs from `--ref`,
2 the check could not run -- and could not run is never a pass.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_URL = "http://127.0.0.1:8099"
DEFAULT_REF = "origin/main"

# Exit 2, not 1. "Could not run" and "ran and found a problem" are different
# answers, and collapsing them is how a dead gate reads as a failing one.
EXIT_OK = 0
EXIT_DIFFERS = 1
EXIT_CANNOT_RUN = 2

# Rendering a fresh worktree imports the whole app. Slower than reading a file
# and the only honest way to get main's route set.
RENDER_TIMEOUT = 180


def die(message: str) -> None:
    """Report that the check could not run, and exit 2."""
    print(f"check_demo_matches_main: {message}", file=sys.stderr)
    raise SystemExit(EXIT_CANNOT_RUN)


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run git, capturing both streams so failures can be quoted verbatim."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )


def fetch_ref(ref: str) -> None:
    """Refresh `ref` from its remote, or exit 2 saying why it could not."""
    remote = ref.split("/", 1)[0] if "/" in ref else "origin"
    out = git("fetch", remote, "--quiet")
    if out.returncode != 0:
        die(
            f"không fetch được '{remote}' nên không biết {ref} có mới không:\n"
            f"{out.stderr.strip()[-800:]}\n"
            "   So với một ref cũ thì chính cổng này mù — đó là lỗi nó sinh ra để bắt.\n"
            "   Offline thì nói ra:  --no-fetch"
        )


def ref_paths(ref: str) -> set[str]:
    """Paths `services/api` declares at `ref`, rendered by FastAPI itself.

    Rendered in a throwaway worktree rather than in the current one, because the
    caller is usually standing on a branch and the question is about `main`.
    """
    out = git("rev-parse", "--verify", f"{ref}^{{commit}}")
    if out.returncode != 0:
        die(f"không phân giải được ref '{ref}': {out.stderr.strip()[-400:]}")
    sha = out.stdout.strip()

    tmp = Path(tempfile.mkdtemp(prefix="demo-vs-main-"))
    tree = tmp / "tree"
    try:
        add = git("worktree", "add", "--detach", "--quiet", str(tree), sha)
        if add.returncode != 0:
            die(f"không dựng được worktree tạm cho {ref}: {add.stderr.strip()[-800:]}")

        api_dir = tree / "services" / "api"
        if not api_dir.is_dir():
            die(f"{ref} không có services/api — ref này có phải của repo này không?")

        code = (
            "import json;from app.api.main import app;"
            "print(json.dumps(sorted(app.openapi()['paths'])))"
        )
        try:
            rendered = subprocess.run(
                [sys.executable, "-c", code],
                cwd=str(api_dir),
                capture_output=True,
                text=True,
                timeout=RENDER_TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            die(f"không dựng được OpenAPI của {ref}: {exc}")
        if rendered.returncode != 0:
            die(
                f"không dựng được OpenAPI của {ref} (mã {rendered.returncode}):\n"
                f"{rendered.stderr.strip()[-2000:]}\n"
                "   Thiếu thư viện thì:  pip install -r services/api/requirements-dev.txt"
            )
        try:
            paths = set(json.loads(rendered.stdout))
        except json.JSONDecodeError as exc:
            die(f"OpenAPI của {ref} trả về thứ không phải JSON: {exc}")
        # A ref that renders zero routes is not a clean answer, it is no answer.
        if not paths:
            die(f"{ref} khai 0 route. Không có gì để đối chiếu, nên không thể ĐẠT.")
        return paths
    finally:
        # Remove the worktree through git so its administrative entry goes too;
        # a leaked entry makes the NEXT run fail on a path that no longer exists.
        git("worktree", "remove", "--force", str(tree))
        shutil.rmtree(tmp, ignore_errors=True)


def server_paths(url: str, timeout: float) -> set[str]:
    """Paths the running server publishes, read from its own /openapi.json."""
    doc_url = url.rstrip("/") + "/openapi.json"
    try:
        with urllib.request.urlopen(doc_url, timeout=timeout) as resp:
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
            body = resp.read()
    except urllib.error.HTTPError as exc:
        die(f"{doc_url} trả về HTTP {exc.code}. Máy chủ có đang chạy đúng ảnh không?")
    except (urllib.error.URLError, OSError) as exc:
        die(f"không gọi được {doc_url}: {exc}\n   Máy chủ chưa chạy. Gỡ:  make up")

    if ctype != "application/json":
        die(
            f"{doc_url} trả về Content-Type '{ctype}', không phải application/json.\n"
            "   Cổng này đang nói chuyện với thứ không phải API."
        )
    try:
        doc = json.loads(body)
    except json.JSONDecodeError as exc:
        die(f"{doc_url} trả về JSON hỏng: {exc}")

    # `doc` is whatever the far end sent. A JSON array parses fine and then
    # `.get` raises AttributeError, which nobody catches, so Python exits 1 --
    # and 1 is this gate's word for "the demo differs from main". Measured on
    # 2026-08-30: body `["/healthz"]` gave exit 1 plus a traceback, sending the
    # reader off to rebuild a demo machine for a drift never measured. Exit 2
    # is the honest answer: the check could not run.
    if not isinstance(doc, dict):
        die(
            f"{doc_url} trả về JSON kiểu {type(doc).__name__}, không phải object.\n"
            "   Tài liệu OpenAPI phải là một object có mục 'paths'."
        )

    paths = doc.get("paths")
    if not isinstance(paths, dict):
        die(f"{doc_url} không có mục 'paths' — đây không phải tài liệu OpenAPI.")
    # Empty result plus exit 0 is what every dead detector in this repo has
    # looked like. It is never a pass.
    if not paths:
        die(f"{doc_url} khai 0 route. Không có gì để đối chiếu, nên không thể ĐẠT.")
    return set(paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Máy demo phải phục vụ đúng bộ route mà main khai."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help=f"mặc định {DEFAULT_URL}")
    parser.add_argument("--ref", default=DEFAULT_REF, help=f"mặc định {DEFAULT_REF}")
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="đừng fetch trước khi so — chỉ dùng khi offline, và sẽ được ghi ra",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--json", action="store_true", help="in kết quả dạng máy đọc")
    args = parser.parse_args(argv)

    if args.no_fetch:
        print(
            f"(--no-fetch: so với {args.ref} đang có sẵn trên máy, có thể đã cũ.)",
            file=sys.stderr,
        )
    else:
        fetch_ref(args.ref)

    # Server first: if nothing is listening there is no point rendering main.
    served = server_paths(args.url, args.timeout)
    declared = ref_paths(args.ref)

    missing = sorted(declared - served)
    extra = sorted(served - declared)

    if args.json:
        print(
            json.dumps(
                {
                    "url": args.url,
                    "ref": args.ref,
                    "ref_routes": len(declared),
                    "served": len(served),
                    "missing": missing,
                    "extra": extra,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    if missing or extra:
        print(file=sys.stderr)
        print(f"!! Máy demo KHÔNG khớp {args.ref}.", file=sys.stderr)
        print(f"   máy chủ: {args.url}", file=sys.stderr)
        print(
            f"   {args.ref} khai {len(declared)} route, máy chủ phục vụ {len(served)}.",
            file=sys.stderr,
        )
        if missing:
            print(file=sys.stderr)
            print(
                f"   THIẾU {len(missing)} route — leader bấm vào sẽ nhận 404:",
                file=sys.stderr,
            )
            for path in missing:
                print(f"      {path}", file=sys.stderr)
            print(file=sys.stderr)
            print(
                "   Máy demo đứng sau main. Dựng lại TỪ MAIN:\n"
                "       git -C <cây dựng demo> fetch origin\n"
                "       git -C <cây dựng demo> checkout --detach origin/main\n"
                "       make up",
                file=sys.stderr,
            )
        if extra:
            print(file=sys.stderr)
            print(
                f"   THỪA {len(extra)} route — máy demo đang khoe thứ chưa có trên main:",
                file=sys.stderr,
            )
            for path in extra:
                print(f"      {path}", file=sys.stderr)
            print(file=sys.stderr)
            print(
                "   Máy demo dựng từ một nhánh chưa merge. Những route này sẽ biến mất\n"
                "   ở lần dựng lại kế tiếp. Dựng lại từ main.",
                file=sys.stderr,
            )
        return EXIT_DIFFERS

    # Printed on the pass path too. A count that falls while the tree grows is
    # this check going blind, and going blind looks exactly like a clean tree.
    print(f"Máy demo khớp {args.ref}: {len(served)} route, không thiếu, không thừa.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
