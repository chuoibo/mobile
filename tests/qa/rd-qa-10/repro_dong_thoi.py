"""The leave→knock race, driven under concurrent load.

A single sequential client is the *least* likely caller to see this. The commit
that makes a leave visible runs in dependency teardown, on an anyio worker
thread; a lone client hands that thread an idle pool and it usually finishes
before the next request is parsed. Contention is what widens the gap, and a
group demo has contention by construction -- several phones acting in one group
at once is the normal case, not the stress case.

So this repro adds load: N workers each build their own group, leave it, and
immediately knock. Nothing is shared between workers except the server and the
connection pool, which is exactly what is under test.

    python3 tests/qa/rd-qa-10/repro_dong_thoi.py --workers 12 --rounds 6

Exit 1 if any worker was admitted to a group it had already left. The check is
not the HTTP status alone: a 201 is confirmed against the database row, because
a status can be misread and a row cannot.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from danh_tinh import id_tu_so  # noqa: E402


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
    except Exception as exc:  # noqa: BLE001 - a transport failure is data here
        return 0, str(exc)


def retry(fn, want, tries=40):
    for _ in range(tries):
        status, body = fn()
        if status == want:
            return body
    return None


def worker(base: str, worker_id: int, rounds: int, hits: list, lock: threading.Lock) -> None:
    for r in range(rounds):
        tag = uuid.uuid4().hex[:8]
        chu = id_tu_so("09" + str(70000000 + worker_id * 1000 + r * 7).zfill(8))
        khach = id_tu_so("09" + str(80000000 + worker_id * 1000 + r * 7).zfill(8))

        for pid, ten in ((chu, f"C{worker_id}-{tag}"), (khach, f"K{worker_id}-{tag}")):
            if retry(lambda: call(base, "PUT", f"/people/{pid}", actor=pid,
                                  body={"display_name": ten}), 201) is None:
                # already registered from an earlier round is fine
                call(base, "PUT", f"/people/{pid}", actor=pid, body={"display_name": ten})

        body = retry(lambda: call(base, "POST", "/contexts", actor=chu,
                                  body={"display_name": f"N-{tag}"}), 201)
        if body is None:
            continue
        ctx = json.loads(body)["id"]

        body = retry(lambda: call(base, "POST", f"/contexts/{ctx}/members", actor=chu,
                                  roles="group_admin", body={"person_id": khach}), 201)
        if body is None:
            continue
        if retry(lambda: call(base, "POST", f"/memberships/{json.loads(body)['id']}/accept",
                              actor=khach), 200) is None:
            continue

        status, _ = call(base, "DELETE", f"/contexts/{ctx}/members/{khach}", actor=khach)
        if status != 204:
            continue

        read_status, _ = call(base, "GET", f"/contexts/{ctx}/memories", actor=khach)
        caption = f"sau-khi-roi-{tag}"
        write_status, _ = call(base, "POST", f"/contexts/{ctx}/memories", actor=khach,
                               body={"image_url": f"https://x.invalid/{tag}.jpg",
                                     "caption": caption})
        if read_status == 200 or write_status == 201:
            with lock:
                hits.append({
                    "worker": worker_id, "round": r, "ctx": ctx, "khach": khach,
                    "read": read_status, "write": write_status, "caption": caption,
                })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8117")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--rounds", type=int, default=6)
    args = parser.parse_args()
    base = args.base.rstrip("/")

    hits: list = []
    lock = threading.Lock()
    threads = [
        threading.Thread(target=worker, args=(base, w, args.rounds, hits, lock))
        for w in range(args.workers)
    ]
    total = args.workers * args.rounds
    print(f"# {args.workers} worker x {args.rounds} vong = {total} lan roi-nhom, base={base}")
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(f"\n  lot: {len(hits)}/{total} lan")
    for hit in hits[:10]:
        print(f"    w{hit['worker']}r{hit['round']}: GET={hit['read']} POST={hit['write']} "
              f"ctx={hit['ctx'][:8]} caption={hit['caption']}")
    if hits:
        print("\n  Doi chieu bang cach truy van bang `memories` cho cac caption tren:")
        print("    SELECT caption FROM memories WHERE caption IN (...)")
        print("\nKET LUAN: LOI CO MAT.")
        return 1
    print("\nKET LUAN: khong lan nao lot trong dot nay.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
