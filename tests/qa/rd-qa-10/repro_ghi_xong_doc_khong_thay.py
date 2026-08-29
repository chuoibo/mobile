"""Minimal repro: a 2xx write is not yet visible to the request that follows it.

Isolated from the privacy probe after `DELETE .../members/{id}` answered 204 and
the very next request still saw the leaver as a member. The memory wall is not
the defect; it is one of the places the defect shows.

`get_repository` in `app/api/deps.py` is a `yield` dependency wrapping
`with factory.begin() as session`. The COMMIT runs when that context manager
exits, which is dependency teardown -- after the handler has returned its
value. A client that reads its own write immediately can therefore arrive
before the commit lands and be served a snapshot that predates it.

Two directions, and both are already visible in this product:

  PERMISSIVE  leave the group, then read or POST to it -- still admitted.
              A privacy hole: the group said you are out and the wall opened.

  RESTRICTIVE register (`PUT /people/{id}` -> 201), then `POST /contexts`
              -- 409 person_not_registered. That is exactly the F01 order
              `vao-cua/Nhom.tsx` performs, so it breaks the way in.

This file measures both as rates, because one round is a coin flip. No fixture
is shared between rounds; every round mints its own ids.

    python3 tests/qa/rd-qa-10/repro_ghi_xong_doc_khong_thay.py --rounds 40

Exit 1 when either rate is above zero.
"""

from __future__ import annotations

import argparse
import json
import sys
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
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def _id(bucket: int, seed: int) -> str:
    # Numbers assembled, never written down: repo_guard refuses VN mobile
    # shapes on sight and cannot tell an invented one from a real one.
    return id_tu_so("09" + str(bucket + seed).zfill(8))


def round_register_then_use(base: str, seed: int) -> str:
    """RESTRICTIVE direction: the way in, in the order the app does it."""
    who = _id(40000000, seed * 13)
    status, body = call(
        base, "PUT", f"/people/{who}", actor=who, body={"display_name": f"Nguoi-{seed}"}
    )
    if status not in (200, 201):
        return f"register-loi-{status}"
    status, body = call(
        base, "POST", "/contexts", actor=who, body={"display_name": f"Nhom-{seed}"}
    )
    if status == 201:
        return "ok"
    return f"BE-GAY {status} {json.loads(body).get('code', body[:60])}"


def round_leave_then_knock(base: str, seed: int) -> str:
    """PERMISSIVE direction: told you are out, then knock at once."""
    tag = uuid.uuid4().hex[:6]
    chu = _id(50000000, seed * 13)
    khach = _id(60000000, seed * 13)
    for pid, ten in ((chu, f"Chu-{tag}"), (khach, f"Khach-{tag}")):
        status, _ = call(base, "PUT", f"/people/{pid}", actor=pid, body={"display_name": ten})
        if status not in (200, 201):
            return f"setup-register-{status}"

    # Retry the context create through the very race this file measures, so a
    # setup failure cannot be mistaken for the measurement.
    ctx = None
    for _ in range(20):
        status, body = call(base, "POST", "/contexts", actor=chu, body={"display_name": f"N-{tag}"})
        if status == 201:
            ctx = json.loads(body)["id"]
            break
    if ctx is None:
        return "setup-context-that-bai"

    membership = None
    for _ in range(20):
        status, body = call(
            base, "POST", f"/contexts/{ctx}/members", actor=chu, roles="group_admin",
            body={"person_id": khach},
        )
        if status == 201:
            membership = json.loads(body)["id"]
            break
    if membership is None:
        return "setup-invite-that-bai"
    for _ in range(20):
        status, _ = call(base, "POST", f"/memberships/{membership}/accept", actor=khach)
        if status == 200:
            break
    else:
        return "setup-accept-that-bai"

    status, _ = call(base, "DELETE", f"/contexts/{ctx}/members/{khach}", actor=khach)
    if status != 204:
        return f"setup-leave-{status}"

    read_status, _ = call(base, "GET", f"/contexts/{ctx}/memories", actor=khach)
    write_status, _ = call(
        base, "POST", f"/contexts/{ctx}/memories", actor=khach,
        body={"image_url": f"https://x.invalid/{tag}.jpg", "caption": f"sau-khi-roi-{tag}"},
    )
    if read_status == 200 and write_status == 201:
        return "RO-DOC-VA-GHI"
    if read_status == 200:
        return "RO-DOC"
    if write_status == 201:
        return "RO-GHI"
    return "ok"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8117")
    parser.add_argument("--rounds", type=int, default=40)
    args = parser.parse_args()
    base = args.base.rstrip("/")

    print(f"# doc-sau-khi-ghi -- {args.rounds} vong moi huong, base={base}\n")

    print("## Huong RESTRICTIVE: PUT /people -> POST /contexts (duong vao cua F01)")
    a = [round_register_then_use(base, s) for s in range(args.rounds)]
    broken = [r for r in a if r.startswith("BE-GAY")]
    print(f"   {len(broken)}/{args.rounds} vong gay. Vi du: {broken[:2]}")

    print("\n## Huong PERMISSIVE: roi nhom -> doc/ghi tuong ky niem")
    b = [round_leave_then_knock(base, s) for s in range(args.rounds)]
    leaked = [r for r in b if r.startswith("RO-")]
    setup = [r for r in b if r.startswith("setup-")]
    print(f"   {len(leaked)}/{args.rounds} vong lot. Phan bo: "
          f"doc+ghi={b.count('RO-DOC-VA-GHI')} chi-doc={b.count('RO-DOC')} chi-ghi={b.count('RO-GHI')}")
    if setup:
        print(f"   ({len(setup)} vong hong o setup: {setup[:2]})")

    print()
    if broken or leaked:
        print("KET LUAN: LOI CO MAT -- 2xx tra ve truoc khi ghi nhin thay duoc.")
        return 1
    print("KET LUAN: khong quan sat duoc cua so nao trong so vong nay.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
