"""Is the write committed by the time the client is told it succeeded?

This is the question underneath the one-off privacy hole seen on the memory
wall: a departed member read and then WROTE to a group after `DELETE
.../members/{id}` had answered 204. That happened once in ~130 attempts, so
rather than keep hammering the HTTP surface hoping to catch it again, this
measures the underlying property directly.

Method, with no change to the product:

  - open a psycopg connection FIRST and warm it, so the observation itself
    costs microseconds and cannot be blamed for the gap;
  - send `DELETE .../members/{id}`;
  - the instant the 204 is in hand, SELECT the membership row on that warm
    connection, in autocommit, so every read takes a fresh snapshot;
  - if the row still reads `active`, the server answered before its own write
    was visible, and every rule that consults that row is open for the gap.

A single observation is a coin flip; the run reports a rate over N rounds and
the measured width of the gap where there is one.

    python3 tests/qa/rd-qa-10/do_commit_sau_phan_hoi.py --rounds 30

Exit 1 if any round saw a 204 arrive before its own commit.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from danh_tinh import id_tu_so  # noqa: E402

DSN = "postgresql://mobile:mobile-dev-only@localhost:5432/qa_priv"


def call(base, method, path, actor=None, body=None, roles="member"):
    request = urllib.request.Request(
        base + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
    )
    if body is not None:
        request.add_header("Content-Type", "application/json")
    if actor:
        request.add_header("X-Actor-ID", actor)
        request.add_header("X-Actor-Roles", roles)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8117")
    parser.add_argument("--rounds", type=int, default=30)
    args = parser.parse_args()
    base = args.base.rstrip("/")

    conn = psycopg.connect(DSN, autocommit=True)
    with conn.cursor() as warm:  # warm the connection and the plan cache
        for _ in range(50):
            warm.execute("SELECT state FROM memberships LIMIT 1")
            warm.fetchall()

    late = 0
    gaps = []
    print(f"# {args.rounds} vong: 204 den truoc hay sau commit cua chinh no?\n")

    for r in range(args.rounds):
        tag = uuid.uuid4().hex[:8]
        chu = id_tu_so("09" + str(31000000 + r * 11).zfill(8))
        khach = id_tu_so("09" + str(32000000 + r * 11).zfill(8))
        for pid, ten in ((chu, f"C-{tag}"), (khach, f"K-{tag}")):
            call(base, "PUT", f"/people/{pid}", actor=pid, body={"display_name": ten})
        status, body = call(base, "POST", "/contexts", actor=chu,
                            body={"display_name": f"N-{tag}"})
        if status != 201:
            continue
        ctx = json.loads(body)["id"]
        status, body = call(base, "POST", f"/contexts/{ctx}/members", actor=chu,
                            roles="group_admin", body={"person_id": khach})
        if status != 201:
            continue
        call(base, "POST", f"/memberships/{json.loads(body)['id']}/accept", actor=khach)

        status, _ = call(base, "DELETE", f"/contexts/{ctx}/members/{khach}", actor=khach)
        got_204 = time.monotonic()
        if status != 204:
            continue

        # First look, as close to the response as this process can get.
        with conn.cursor() as cur:
            cur.execute(
                "SELECT state FROM memberships WHERE context_id=%s AND person_id=%s",
                (ctx, khach),
            )
            first = cur.fetchone()
        first_at = time.monotonic()

        if first and first[0] == "left":
            print(f"  vong {r:2}: commit XONG truoc phan hoi "
                  f"(doc mat {1000 * (first_at - got_204):.2f}ms)")
            continue

        # Still active after the server said 204: measure how long that lasts.
        late += 1
        deadline = got_204 + 5.0
        seen = None
        while time.monotonic() < deadline:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT state FROM memberships WHERE context_id=%s AND person_id=%s",
                    (ctx, khach),
                )
                row = cur.fetchone()
            if row and row[0] == "left":
                seen = time.monotonic() - got_204
                break
        gaps.append(seen)
        print(f"  vong {r:2}: *** 204 VE TRUOC COMMIT *** hang ghi con 'active' them "
              f"{'%.2fms' % (1000 * seen) if seen else '>5s'}")

    conn.close()
    print(f"\n  {late}/{args.rounds} vong tra loi truoc khi commit nhin thay duoc")
    if gaps:
        real = [g for g in gaps if g]
        if real:
            print(f"  do rong khe: min={1000 * min(real):.2f}ms max={1000 * max(real):.2f}ms")
        print("\nKET LUAN: LOI CO MAT -- phan hoi 2xx di truoc commit cua chinh no.")
        return 1
    print("\nKET LUAN: moi vong deu commit xong truoc khi tra loi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
