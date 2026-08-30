#!/usr/bin/env python3
"""Prove the `hero-walk` gate is red for the reasons it claims to be red for.

A new gate that has only ever been seen green proves nothing: the green could
come from the product working, or from the gate being unable to fail. This
script breaks the thing on purpose, one edit at a time, and checks the gate
notices.

Two layers, because the gate has two and they fail independently:

  A. the live walk (`scripts/hero_walk.sh` with no --status). Mutations here
     break the SCAN SEAM in the client -- the joint this gate exists for. The
     runner rebuilds `dist-test/` from `src/` on every run, so editing `src/`
     is what actually reaches the walk.

  B. the recorded verdict (`scripts/hero_walk.sh --status`), which is what sits
     in the default gate list. Mutations here are the four ways a verdict can
     be worthless: absent, failed, stale, or about another box.

The control matters as much as the mutants. A table where every row is red
cannot tell "the gate catches breakage" from "the gate is red at anything", so
one row makes a behaviour-PRESERVING edit and must stay green. If the control
goes red, the table below says nothing and the run fails.

    python3 scripts/dot_bien_hero_walk.py            all layers
    python3 scripts/dot_bien_hero_walk.py --lop B    only the cheap layer

Layer A spends one real Gemini call per row. Layer B spends none.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

import time

REPO = pathlib.Path(__file__).resolve().parent.parent
RUNNER = REPO / "scripts" / "hero_walk.sh"
RECEIPT = REPO / "apps" / "mobile" / "src" / "receipt.ts"
API = REPO / "apps" / "mobile" / "src" / "api.ts"
URL = "http://127.0.0.1:8099"

# Each: label, file, old, new, expect_red, why
#
# Anchors are checked for uniqueness before use. `lineTotalVnd:
# item.line_total_vnd,` alone appears TWICE in receipt.ts -- once as the value
# the screen reads and once inside `read:` -- so the money mutant carries the
# following line as part of its anchor. Patching the wrong copy of a duplicated
# anchor is a mutation that measures nothing while looking like it measured.
LAYER_A = [
    (
        "A1 readingFromWire trả 0 món",
        RECEIPT,
        "wire.items.map(",
        "wire.items.slice(0, 0).map(",
        True,
        "màn gán món sẽ trống; bài đi bộ assert lines.length > 0",
    ),
    (
        "A2 tiền không còn là số nguyên đồng",
        RECEIPT,
        "lineTotalVnd: item.line_total_vnd,\n      read: {",
        "lineTotalVnd: item.line_total_vnd / 1.5,\n      read: {",
        True,
        "luật tiền 1; bài đi bộ assert Number.isInteger từng dòng",
    ),
    (
        "A3 scanReceipt gọi sai đường",
        API,
        'BASE_URL + "/receipts/scan"',
        'BASE_URL + "/receipts/scan-khong-ton-tai"',
        True,
        "đứt ngay tại mối nối client<->server",
    ),
    (
        "C1 ĐỐI CHỨNG: đổi hình dạng, GIỮ hành vi",
        RECEIPT,
        "    lines: wire.items.map(",
        "    lines: [...wire.items].map(",
        False,
        "phải XANH — nếu đỏ thì bảng này không phân biệt được gì",
    ),
]


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, **kw)


def walk_rc() -> int:
    """One live walk. Its exit code is the measurement."""
    return run([str(RUNNER), "--url", URL]).returncode


def status_rc(*extra: str) -> tuple[int, str]:
    proc = run([str(RUNNER), "--status", "--url", URL, *extra])
    return proc.returncode, (proc.stdout + proc.stderr).strip().splitlines()[0] if (
        proc.stdout + proc.stderr
    ).strip() else ""


def verdict_path() -> pathlib.Path:
    import os

    base = os.environ.get(
        "MOBILE_HERO_WALK_DIR",
        os.path.join(
            os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
            "mobile-hero-walk",
        ),
    )
    return pathlib.Path(base) / "verdict.json"


def layer_a() -> list[tuple[str, bool, str]]:
    rows = []
    for label, path, old, new, expect_red, why in LAYER_A:
        text = path.read_text(encoding="utf-8")
        n = text.count(old)
        if n != 1:
            rows.append(
                (label, False, f"neo xuất hiện {n} lần, cần đúng 1 — BỎ, không đo được")
            )
            continue
        backup = text
        try:
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
            rc = walk_rc()
        finally:
            path.write_text(backup, encoding="utf-8")
        red = rc != 0
        ok = red == expect_red
        got = "ĐỎ" if red else "XANH"
        want = "ĐỎ" if expect_red else "XANH"
        rows.append((label, ok, f"{got} (cần {want}) — {why}"))
    return rows


def layer_b() -> list[tuple[str, bool, str]]:
    """Break the verdict, not the product."""
    rows = []
    vp = verdict_path()
    saved = vp.read_text(encoding="utf-8") if vp.exists() else None

    def check(label, expect_red, why, mutate):
        try:
            mutate()
            rc, line = status_rc()
        finally:
            if saved is not None:
                vp.parent.mkdir(parents=True, exist_ok=True)
                vp.write_text(saved, encoding="utf-8")
            elif vp.exists():
                vp.unlink()
        red = rc != 0
        ok = red == expect_red
        rows.append(
            (
                label,
                ok,
                f"{'ĐỎ' if red else 'XANH'} (cần {'ĐỎ' if expect_red else 'XANH'}) — {why}",
            )
        )

    head_sha = run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()

    def write(**over):
        base = json.loads(saved) if saved else {}
        # Pin sha to THIS tree unless the row is deliberately varying it. The
        # saved verdict comes from whatever walk ran last, quite possibly on
        # another branch, and `--status` now refuses that (B9). Without this
        # line B2/B3 would go red for the wrong reason and B0 -- the control
        # this whole table depends on -- would go red for no reason at all,
        # which reads as "gate is broken" rather than "row set up wrong".
        base["sha"] = head_sha
        base.update(over)
        vp.parent.mkdir(parents=True, exist_ok=True)
        vp.write_text(json.dumps(base), encoding="utf-8")

    check(
        "B1 chưa ai đi bộ bao giờ",
        True,
        "không có phán quyết KHÔNG phải là đạt",
        lambda: vp.unlink() if vp.exists() else None,
    )
    check(
        "B2 lượt gần nhất ĐỨT",
        True,
        "rc khác 0",
        lambda: write(rc=1, buoc_hong="QUET BILL: anh -> mon"),
    )
    check(
        "B3 phán quyết quá cũ",
        True,
        "quá ngưỡng 24 giờ",
        lambda: write(rc=0, ts=time.time() - 40 * 3600),
    )
    check(
        "B4 phán quyết về máy KHÁC",
        True,
        "khớp máy khác không nói gì về máy này",
        lambda: write(rc=0, ts=time.time(), url="http://127.0.0.1:9999"),
    )
    check(
        "B5 phán quyết hỏng",
        True,
        "đọc không được cũng không phải đạt",
        lambda: vp.write_text("{khong-phai-json", encoding="utf-8"),
    )
    check(
        "B0 ĐỐI CHỨNG: phán quyết tốt",
        False,
        "phải XANH",
        lambda: write(rc=0, ts=time.time(), url=URL),
    )

    # --- the sha axis: which CODE was walked ------------------------------
    #
    # B4 asks "which box". These ask "which client", and before #354 was
    # reviewed nothing did: the field was recorded and printed on the pass line
    # but never compared to anything, so a walk on any branch vouched for any
    # tree. The verdict dir is shared by every worktree on this machine, so the
    # borrowed-evidence case is the normal one, not a contrived one.
    #
    # A commit that exists but is unreachable from HEAD, built here rather than
    # borrowed from a branch: after this branch merges main, main's tip IS an
    # ancestor, so naming any real branch would quietly stop testing anything.
    ngoai = run(
        ["git", "commit-tree", "HEAD^{tree}", "-m", "dot bien B9"]
    ).stdout.strip()
    if not ngoai:
        rows.append(
            (
                "B9 phán quyết về NHÁNH KHÁC",
                False,
                "không đúc được commit rời — không đo được",
            )
        )
    else:
        check(
            f"B9 phán quyết về NHÁNH KHÁC ({ngoai[:7]})",
            True,
            "commit có thật nhưng không nằm trong HEAD — không nói gì về cây này",
            lambda: write(rc=0, ts=time.time(), url=URL, sha=ngoai[:7]),
        )

    check(
        "B10 sha repo chưa từng thấy",
        True,
        "không đặt được vào đâu so với HEAD",
        lambda: write(rc=0, ts=time.time(), url=URL, sha="deadbee"),
    )

    check(
        "B11 phán quyết không ghi được sha",
        True,
        "'?' không buộc được vào cây nào",
        lambda: write(rc=0, ts=time.time(), url=URL, sha="?"),
    )

    # The control that keeps B9-B11 honest. Without it "always red on the sha
    # axis" and "checks ancestry" look identical from the table -- and an equality
    # check would burn a model call on every docs commit, so the difference is
    # the difference between a gate that survives and one that gets deleted.
    to_tien = run(["git", "rev-parse", "--short", "HEAD~1"]).stdout.strip()
    check(
        f"B12 ĐỐI CHỨNG: sha là TỔ TIÊN của HEAD ({to_tien})",
        False,
        "phải XANH — là kiểm tổ tiên, không phải ghim đúng bằng HEAD",
        lambda: write(rc=0, ts=time.time(), url=URL, sha=to_tien),
    )

    # The runner's own refusals: these are the edits that must not turn the
    # stage green by removing the thing it measures.
    missing = run([str(RUNNER), "--walk", "/khong/co/file.mjs", "--url", URL])
    rows.append(
        (
            "B6 xoá bài đi bộ",
            missing.returncode == 2,
            f"mã {missing.returncode} (cần 2) — xoá file duy nhất đi qua mối nối không được thành xanh",
        )
    )

    # A box that is up but older than the feature: 200 on /healthz, no
    # /receipts/scan. This is the case that has already cost this repo two
    # measurements, so it gets a real server rather than an assertion.
    #
    # The port is chosen BY THE CHILD (bind 0) and read back, not picked here.
    # The first cut of this hard-coded 8477, which was already taken on this
    # machine by something that answers 404: the child died on bind, the runner
    # correctly reported "no box", and the table recorded that correct answer as
    # a gate defect. An instrument that cannot bind must say so, not blame the
    # thing it is measuring.
    server = subprocess.Popen(
        [sys.executable, "-c", CU_HON_TINH_NANG],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        first = server.stdout.readline().strip()
        if not first.startswith("PORT "):
            rows.append(
                (
                    "B7 máy cũ hơn tính năng",
                    False,
                    f"KHÔNG DỰNG ĐƯỢC máy giả ({first or server.stderr.read()[:120]}) — không đo được",
                )
            )
        else:
            port = int(first.split()[1])
            old_box = run([str(RUNNER), "--url", f"http://127.0.0.1:{port}"])
            rows.append(
                (
                    f"B7 máy cũ hơn tính năng (200 /healthz, không /receipts/scan, cổng {port})",
                    old_box.returncode == 2,
                    f"mã {old_box.returncode} (cần 2) — máy cũ, không phải tính năng hỏng",
                )
            )
    finally:
        server.terminate()
        server.wait(timeout=10)

    # Nothing listening at all is an ABSENCE, and must skip (1), not fail (2).
    # A gate that is red on every machine without a demo box gets deleted.
    # The port must be one nothing holds, so it is claimed and released here
    # rather than guessed -- same lesson as B7.
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        dead_port = s.getsockname()[1]
    dead = run([str(RUNNER), "--url", f"http://127.0.0.1:{dead_port}"])
    rows.append(
        (
            f"B8 không có máy nào (vắng mặt, không phải lỗi, cổng {dead_port})",
            dead.returncode == 1,
            f"mã {dead.returncode} (cần 1) — bỏ qua có lý do, không phải hỏng",
        )
    )
    return rows


CU_HON_TINH_NANG = """
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            body = json.dumps({"status": "ok"}).encode()
        elif self.path == "/openapi.json":
            # Every route EXCEPT the bill path -- a container built before the
            # feature existed.
            body = json.dumps({"paths": {"/expenses": {}, "/batches": {}}}).encode()
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


# Port 0: the OS picks a free one and we report it, so this can never collide
# with whatever else this machine is already running.
srv = HTTPServer(("127.0.0.1", 0), H)
print("PORT %d" % srv.server_address[1], flush=True)
srv.serve_forever()
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lop", choices=["A", "B", "AB"], default="AB")
    args = ap.parse_args()

    if not shutil.which("node"):
        print("không có node — không đo được", file=sys.stderr)
        return 2

    rows: list[tuple[str, bool, str]] = []
    if "B" in args.lop:
        print(
            "=== Lớp B: phán quyết và các lời từ chối của runner (không tốn model) ==="
        )
        rows += layer_b()
    if "A" in args.lop:
        print("=== Lớp A: phá MỐI NỐI thật, mỗi dòng một lần gọi model ===")
        rows += layer_a()

    print()
    width = max(len(r[0]) for r in rows)
    for label, ok, note in rows:
        print(f"  {'ĐẠT ' if ok else 'HỎNG'}  {label:<{width}}  {note}")
    bad = [r for r in rows if not r[1]]
    print()
    print(f"{len(rows) - len(bad)}/{len(rows)} dòng đúng kỳ vọng.")
    if bad:
        print("Bảng KHÔNG chứng minh được cổng gác đúng — xem dòng HỎNG ở trên.")
        return 1
    print("Cổng đỏ đúng chỗ nó khai, và ĐỐI CHỨNG vẫn xanh nên bảng phân biệt được.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
