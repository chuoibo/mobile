#!/usr/bin/env python3
"""Prove `make db-reset` empties the ledger, keeps the photos, and cleans the cast.

WHY THIS IS A LIVE RUN AND NOT A UNIT TEST

`tests/test_db_reset_guard.py` reads the script's source and exercises its
refusals. That catches a recipe that hardcodes the confirmation and a teardown
that reaches for `down -v`. It cannot catch the thing that actually matters:
whether a real Docker volume full of real photo bytes is still there after a
real teardown. Only destroying a real stack answers that.

WHAT IT ASSERTS, IN ORDER

  1. RED first. Spend money for the demo persona in a scratch group, through
     the real routes, and watch `scripts/cong_persona_demo_sach.py` go to
     exit 1. A gate that was never red proves nothing when it turns green.
  2. Photo bytes go in, through the app's own `PhotoStorage`, and their sha256
     is recorded.
  3. `make db-reset` runs.
  4. The photo reads back byte-identical FROM A NEW CONTAINER. This is the
     whole point of the command; if it fails, `db-reset` is `clean`.
  5. The ledger is empty -- measured by counting rows, not by trusting that a
     volume disappeared.
  6. Re-seed, then the persona gate goes to exit 0 on the same machine.

WHAT IT DOES NOT PROVE

Nothing about the shared demo machine. It refuses to run against `mobile-local`
outright: this script's entire method is destroying a ledger, and 8099 is the
one leader presses. Point it at a throwaway project.

It also does not rebuild the image. `docker-compose.yml` tags the API
`mobile-local/api:dev`, a name every project on this machine shares, so a
`--build` here would retag another lane's stack from this worktree. The stack
comes back up on the image it was already running.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

OWNER_ROLES = "group_admin,member,advancer,recipient,batch_owner"

# Recognisable in a hexdump and containing a NUL, so a transport that quietly
# treats the payload as text cannot pass. Same reasoning as
# scripts/check_media_persists.sh, which this deliberately mirrors.
PAYLOAD_EXPR = "bytes(range(256)) * 8"
PHOTO_KEY = "00112233445566778899aabbccddeeff"


def api(base: str, method: str, path: str, body=None, actor=None, context=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if actor is not None:
        headers["X-Actor-ID"] = str(actor)
        headers["X-Actor-Roles"] = OWNER_ROLES
    if context is not None:
        headers["X-Actor-Contexts"] = str(context)
    headers["Idempotency-Key"] = str(uuid.uuid4())
    req = urllib.request.Request(
        f"{base}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        sys.exit(f"HỎNG: {method} {path} -> {exc.code}\n{exc.read().decode()[:600]}")


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess[str]:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, text=True, capture_output=True, timeout=900, **kw)


def compose(project: str, *args: str, env: dict) -> subprocess.CompletedProcess[str]:
    return run(["docker", "compose", "-p", project, *args], cwd=REPO_ROOT, env=env)


def gate(dsn: str, base: str) -> tuple[int, str]:
    proc = run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "cong_persona_demo_sach.py"),
            "--dsn",
            dsn,
            "--api",
            base,
        ],
        cwd=REPO_ROOT,
    )
    return proc.returncode, proc.stdout + proc.stderr


def photo_bytes(project: str, env: dict, write: bool) -> str | None:
    """Write or read the probe photo through the app's own storage layer.

    `run --rm` each way, never `restart`: a restarted container keeps its
    writable layer, so the read would succeed with no volume mounted at all --
    green for exactly the defect being measured.
    """
    verb = "write" if write else "read"
    code = (
        "import hashlib\n"
        "from app.media.storage import PhotoStorage\n"
        "s = PhotoStorage()\n"
        + (
            f"s.write('{PHOTO_KEY}', {PAYLOAD_EXPR})\n"
            f"print('SHA', hashlib.sha256({PAYLOAD_EXPR}).hexdigest())\n"
            if write
            else "import sys\n"
            "try:\n"
            f"    b = s.read('{PHOTO_KEY}')\n"
            "except FileNotFoundError:\n"
            "    print('MISSING'); sys.exit(0)\n"
            "print('SHA', hashlib.sha256(b).hexdigest())\n"
        )
    )
    proc = compose(
        project, "run", "--rm", "--no-deps", "-T", "api", "python", "-c", code, env=env
    )
    out = proc.stdout + proc.stderr
    if "MISSING" in out:
        return None
    for line in out.splitlines():
        if line.startswith("SHA "):
            return line.split()[1]
    sys.exit(f"HỎNG: không đọc được sha ảnh ({verb}):\n{out[-800:]}")


def ledger_rows(dsn: str) -> dict:
    import psycopg

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        out = {}
        for table in ("contexts", "expenses", "confirmed_allocations"):
            cur.execute(f"SELECT count(*) FROM {table}")
            out[table] = cur.fetchone()[0]
        return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--api", required=True)
    p.add_argument("--dsn", required=True)
    p.add_argument("--api-port", required=True)
    p.add_argument("--pg-port", required=True)
    args = p.parse_args()

    if args.project in {"mobile-local", ""}:
        sys.exit("Từ chối: script này XOÁ SỔ CÁI. Không chạy trên bộ dùng chung.")

    import os

    env = dict(os.environ)
    env.update(
        MOBILE_PROJECT=args.project,
        COMPOSE_PROJECT_NAME=args.project,
        MOBILE_API_PORT=args.api_port,
        MOBILE_POSTGRES_PORT=args.pg_port,
    )

    import seed_demo_data as seed  # noqa: E402  (path set above)

    minh = seed.PEOPLE[0][0]

    print("=" * 72)
    print("1. LÀM BẨN persona qua ROUTE THẬT, rồi đòi cổng phải ĐỎ")
    print("=" * 72)
    before_code, _ = gate(args.dsn, args.api)
    print(f"  cổng trước khi làm bẩn: exit {before_code}")
    # Informational, not an assertion. The claim under test is "a dirty machine
    # comes back clean", and that holds whatever shape the machine started in.
    # Demanding a pristine start would also make this script un-rerunnable: its
    # own first step dirties the stack, so attempt two would refuse to run.
    if before_code != 0:
        print("  (máy đã bẩn sẵn — vẫn đo được, vì điều cần chứng minh là bẩn -> sạch)")

    junk = f"rác chứng minh db-reset {uuid.uuid4().hex[:8]}"
    ctx = api(args.api, "POST", "/contexts", {"display_name": junk}, actor=minh)
    ctx_id = ctx["id"]
    print(f"  nhóm rác: {junk}  ({ctx_id})")

    proposal = api(
        args.api,
        "POST",
        "/expenses",
        {
            "context_id": ctx_id,
            "description": "bữa không thuộc nhóm demo",
            "recorded_by_id": str(minh),
            "paid_by_id": str(minh),
            "verification_scope": "totals_only",
            "occurred_at": datetime.now(UTC).isoformat(),
            "participants": [str(minh)],
            "total_amount_vnd": 999000,
            "items": [],
            "surcharges": [],
            "discounts": [],
        },
        actor=minh,
        context=ctx_id,
    )
    api(
        args.api,
        "POST",
        f"/expenses/{proposal['expense_id']}/confirm",
        {
            "proposal": proposal["proposal"],
            "expected_allocations": proposal["allocation"]["allocations"],
            "acknowledge_as_advancer": True,
        },
        actor=minh,
        context=ctx_id,
    )
    print("  đã ghi 999.000đ cho Minh ngoài nhóm demo")

    red_code, red_out = gate(args.dsn, args.api)
    print(red_out.strip()[-700:])
    if red_code == 0:
        sys.exit("HỎNG: cổng vẫn XANH sau khi làm bẩn — cổng không có răng.")
    print(f"  => ĐỎ như phải thế: exit {red_code}")

    print()
    print("=" * 72)
    print("2. GHI ẢNH qua PhotoStorage của chính app")
    print("=" * 72)
    sha_before = photo_bytes(args.project, env, write=True)
    print(f"  sha256 đã ghi: {sha_before}")
    rows_before = ledger_rows(args.dsn)
    print(f"  sổ trước khi xoá: {rows_before}")

    print()
    print("=" * 72)
    print("3. make db-reset — trước hết phải TỪ CHỐI khi thiếu CONFIRM")
    print("=" * 72)
    refused = run(["make", "db-reset"], cwd=REPO_ROOT, env=env)
    print(f"  không CONFIRM -> exit {refused.returncode}")
    if refused.returncode == 0:
        sys.exit("HỎNG: chạy mà không cần xác nhận.")
    print("  " + "\n  ".join(refused.stderr.strip().splitlines()[:4]))

    applied = run(
        ["make", "db-reset", f"CONFIRM={args.project}"], cwd=REPO_ROOT, env=env
    )
    print(applied.stdout.strip())
    if applied.returncode != 0:
        sys.exit(f"HỎNG: db-reset thất bại:\n{applied.stderr[-1200:]}")

    print()
    print("=" * 72)
    print("4. ẢNH còn không — đọc lại từ CONTAINER MỚI")
    print("=" * 72)
    sha_after = photo_bytes(args.project, env, write=False)
    print(f"  sha256 đọc lại: {sha_after}")
    if sha_after is None:
        sys.exit("HỎNG: ảnh biến mất. db-reset đang là `clean` đội tên khác.")
    if sha_after != sha_before:
        sys.exit(f"HỎNG: byte đổi {sha_before} -> {sha_after}")
    print("  => ảnh sống sót, byte y hệt")

    print()
    print("=" * 72)
    print("5. SỔ CÁI có thật sự rỗng không — đếm hàng, không tin volume")
    print("=" * 72)
    compose(args.project, "up", "-d", "--wait", "--wait-timeout", "300", env=env)
    rows_after = ledger_rows(args.dsn)
    print(f"  sổ sau khi xoá: {rows_after}")
    dirty = {k: v for k, v in rows_after.items() if v != 0}
    if dirty:
        sys.exit(f"HỎNG: sổ chưa rỗng: {dirty}")
    print("  => rỗng thật")

    print()
    print("=" * 72)
    print("6. SEED LẠI rồi đòi cổng XANH")
    print("=" * 72)
    compose(args.project, "run", "--rm", "--no-deps", "demo", env=env)
    green_code, green_out = gate(args.dsn, args.api)
    print(green_out.strip()[-900:])
    if green_code != 0:
        sys.exit(f"HỎNG: cổng vẫn đỏ sau khi dựng lại: exit {green_code}")

    print()
    print("=" * 72)
    print(f"ĐẠT.  cổng: {red_code} (bẩn) -> {green_code} (sau db-reset + seed)")
    print(f"      ảnh: {sha_before} còn nguyên")
    print(f"      sổ:  {rows_before} -> {rows_after} -> đã seed lại")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
