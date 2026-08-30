"""Walk the five group-administration routes on a live API, as the screen sends them.

Not a unit test and not a substitute for one. What this proves is narrow and
worth stating: that the exact method, path, headers and body
`apps/mobile/src/screens/quan-tri/quan-tri.ts` builds are accepted by a real
FastAPI on a real PostgreSQL, and that the two refusals the screen's controls
are gated on are real refusals rather than assumptions written into a comment.

The two negative cases are the point. A walk that only presses the happy path
cannot tell "the server allows this" from "the server allows anything":

  - promoting somebody while NOT an admin of that group must be 403. The screen
    hides the role control on that basis (`laQuanTri` reads the roster row, not
    the header the app itself writes), so if this came back 200 the control
    would be hidden from people who could in fact use it -- and, worse, the
    comment claiming the header is insufficient would be false.
  - deleting somebody ELSE's membership must be 403. The screen offers "Rời
    nhóm" only on your own row on that basis. If this came back 204 the product
    would have a remove-member route nobody had noticed, and the screen would be
    hiding a real feature behind an incorrect explanation.

Usage:
    API=http://127.0.0.1:46821 python3 tests/qa/qa2-quan-tri/di-bo-quan-tri.py

Runs against whatever `API` names. Point it at a disposable stack
(`scripts/e2e_slice.sh --keep`), never at the shared demo machine on 8099: it
writes memberships, roles and invites.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid

API = os.environ.get("API", "http://127.0.0.1:8099").rstrip("/")

MINH = "46b55e67-932b-5415-a5ee-08fb2641a4ff"
TRANG = "49871dab-3bf9-5140-acf3-6c9736b31e8f"

# The two role strings the client sends, verbatim from `quan-tri.ts`. The
# default four are what `actorHeaders` builds; QUYEN_ADMIN is what the one
# admin call adds `group_admin` to.
MAC_DINH = "member,advancer,recipient,batch_owner"
QUYEN_ADMIN = "group_admin,member,advancer,recipient,batch_owner"

hong: list[str] = []


def goi(
    method: str,
    path: str,
    *,
    actor: str | None = None,
    roles: str = MAC_DINH,
    contexts: str | None = None,
    body: dict | None = None,
    key: str | None = None,
) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, method=method, data=data)
    req.add_header("Content-Type", "application/json")
    if actor:
        req.add_header("X-Actor-ID", actor)
        req.add_header("X-Actor-Roles", roles)
    if contexts:
        req.add_header("X-Actor-Contexts", contexts)
    if key:
        req.add_header("Idempotency-Key", key)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw.decode(errors="replace")[:300]


def can(nhan: str, thuc: int, mong: int, them: str = "") -> bool:
    ok = thuc == mong
    print(f"  {'ĐẠT ' if ok else 'HỎNG'} {nhan}: {thuc} (cần {mong}) {them}")
    if not ok:
        hong.append(f"{nhan}: {thuc} != {mong}")
    return ok


def main() -> int:
    print(f"# API = {API}")
    st, _ = goi("GET", "/healthz")
    if st != 200:
        print(f"máy chủ không trả lời /healthz ({st}) — dừng", file=sys.stderr)
        return 2

    print("\n## nền: hai người, một nhóm, một lời mời đã nhận")
    for pid, ten in ((MINH, "Minh"), (TRANG, "Trang")):
        st, _ = goi(
            "PUT",
            f"/people/{pid}",
            actor=pid,
            body={"display_name": ten},
            key=str(uuid.uuid4()),
        )
        can(f"PUT /people/{ten}", st, 200)

    st, nhom = goi(
        "POST",
        "/contexts",
        actor=MINH,
        roles=QUYEN_ADMIN,
        body={"display_name": f"QA quan tri {uuid.uuid4().hex[:8]}"},
        key=str(uuid.uuid4()),
    )
    can("POST /contexts", st, 201)
    cid = nhom["id"]  # type: ignore[index]
    print(f"  context_id = {cid}")

    st, tv = goi(
        "POST",
        f"/contexts/{cid}/members",
        actor=MINH,
        roles=QUYEN_ADMIN,
        contexts=cid,
        body={"person_id": TRANG},
        key=str(uuid.uuid4()),
    )
    can("POST /contexts/{id}/members (mời Trang)", st, 201)
    mid = tv["id"]  # type: ignore[index]
    st, _ = goi(
        "POST", f"/memberships/{mid}/accept", actor=TRANG, key=str(uuid.uuid4())
    )
    can("POST /memberships/{id}/accept", st, 200)

    print("\n## route 1 — GET /contexts/{context_id}")
    st, chi = goi("GET", f"/contexts/{cid}", actor=TRANG, contexts=cid)
    can("đọc nhóm bằng tư cách thành viên", st, 200)
    if st == 200:
        print(f"    display_name = {chi['display_name']!r}, created_by_id = {chi['created_by_id']}")  # type: ignore[index]

    print("\n## đối chứng âm — người ngoài nhóm phải bị từ chối")
    nguoi_la = str(uuid.uuid4())
    st, _ = goi("GET", f"/contexts/{cid}", actor=nguoi_la, contexts=cid)
    can("người lạ đọc nhóm", st, 403)

    print("\n## đối chứng âm — đổi vai trò khi CHƯA là admin của nhóm này")
    # Trang is an ACTIVE member and asserts `group_admin` in the header, which
    # is exactly the state the screen refuses to show the control in. If this
    # were 200, `laQuanTri` would be hiding a control that works.
    st, than = goi(
        "PUT",
        f"/contexts/{cid}/members/{MINH}/role",
        actor=TRANG,
        roles=QUYEN_ADMIN,
        contexts=cid,
        body={"role": "member"},
        key=str(uuid.uuid4()),
    )
    can("Trang (member) tự nhận group_admin rồi hạ Minh", st, 403,
        f"code={than.get('code') if isinstance(than, dict) else than}")

    print("\n## route 2 — PUT /contexts/{context_id}/members/{person_id}/role")
    st, sau = goi(
        "PUT",
        f"/contexts/{cid}/members/{TRANG}/role",
        actor=MINH,
        roles=QUYEN_ADMIN,
        contexts=cid,
        body={"role": "admin"},
        key=str(uuid.uuid4()),
    )
    can("Minh (admin) nâng Trang lên admin", st, 200)
    if st == 200:
        print(f"    role sau khi ghi = {sau['role']!r}, state = {sau['state']!r}")  # type: ignore[index]
    st, ds = goi("GET", f"/contexts/{cid}/members", actor=MINH, contexts=cid)
    vai = {m["person_id"]: m["role"] for m in ds["members"]}  # type: ignore[index]
    can("đọc lại roster thấy vai trò mới", 200 if vai.get(TRANG) == "admin" else 0, 200,
        f"roster nói {vai.get(TRANG)!r}")

    print("\n## nền cho lời mời: một chuyến đi")
    st, buoi = goi(
        "POST",
        f"/contexts/{cid}/outings",
        actor=MINH,
        contexts=cid,
        body={
            "title": "QA quản trị: chuyến thử",
            "starts_on": "2026-09-07",
            "ends_on": "2026-09-08",
            "headcount": 2,
            "budget_per_person_vnd": 500000,
        },
        key=str(uuid.uuid4()),
    )
    can("POST /contexts/{id}/outings", st, 201)
    oid = buoi["id"]  # type: ignore[index]

    print("\n## route 3 — POST /outings/{outing_id}/invites")
    st, moi_link = goi(
        "POST",
        f"/outings/{oid}/invites",
        actor=TRANG,
        contexts=cid,
        body={"source": "link"},
        key=str(uuid.uuid4()),
    )
    can("mời bằng link", st, 201)
    if st == 201:
        co_token = bool(moi_link.get("invite_token"))  # type: ignore[union-attr]
        print(f"    invite_path = {moi_link['invite_path']!r}, có token = {co_token}")  # type: ignore[index]
        if not co_token:
            hong.append("lời mời link không kèm token — màn không dựng được đường dẫn")

    st, moi_nhom = goi(
        "POST",
        f"/outings/{oid}/invites",
        actor=MINH,
        contexts=cid,
        body={"source": "group", "person_id": TRANG},
        key=str(uuid.uuid4()),
    )
    can("mời một thành viên trong nhóm", st, 201)
    if st == 201:
        print(f"    invited_person_id = {moi_nhom['invited_person_id']}, token = {moi_nhom['invite_token']!r}")  # type: ignore[index]

    print("\n## route 4 — POST /outings/{outing_id}/invites/{invite_id}/revoke")
    st, thu = goi(
        "POST",
        f"/outings/{oid}/invites/{moi_link['id']}/revoke",  # type: ignore[index]
        actor=TRANG,
        contexts=cid,
        key=str(uuid.uuid4()),
    )
    can("thu hồi lời mời link", st, 200)
    if st == 200:
        print(f"    revoked_at = {thu['revoked_at']!r}")  # type: ignore[index]
    # Measured, not assumed: revoking twice is 200, not a refusal. The route is
    # idempotent and only an ACCEPTED invite earns 409. The screen still hides
    # the second button, but as courtesy rather than as a guard -- and the
    # comment in `coTheThuHoi` says so because this line proved it.
    st, lai = goi(
        "POST",
        f"/outings/{oid}/invites/{moi_link['id']}/revoke",  # type: ignore[index]
        actor=TRANG,
        contexts=cid,
        key=str(uuid.uuid4()),
    )
    can("thu hồi lần hai là idempotent, không phải lỗi", st, 200)
    if st == 200:
        giu = lai["revoked_at"] == thu["revoked_at"]  # type: ignore[index]
        print(f"    revoked_at giữ nguyên = {giu}")
        if not giu:
            hong.append("thu hồi lần hai dời revoked_at — không idempotent như tưởng")

    print("\n## đối chứng âm — xoá tư cách thành viên của NGƯỜI KHÁC")
    st, than = goi(
        "DELETE",
        f"/contexts/{cid}/members/{MINH}",
        actor=TRANG,
        roles=QUYEN_ADMIN,
        contexts=cid,
        key=str(uuid.uuid4()),
    )
    can("Trang xoá Minh khỏi nhóm", st, 403,
        f"code={than.get('code') if isinstance(than, dict) else than}")

    print("\n## route 5 — DELETE /contexts/{context_id}/members/{person_id} (rời nhóm)")
    st, _ = goi(
        "DELETE",
        f"/contexts/{cid}/members/{TRANG}",
        actor=TRANG,
        contexts=cid,
        key=str(uuid.uuid4()),
    )
    can("Trang tự rời nhóm", st, 204)
    st, ds = goi("GET", f"/contexts/{cid}/members", actor=MINH, contexts=cid)
    trang_state = next(
        (m["state"] for m in ds["members"] if m["person_id"] == TRANG), None  # type: ignore[index]
    )
    print(f"    roster (Minh đọc) sau khi rời: Trang = {trang_state!r}")

    # The thing the screen had to be changed for. Leaving revokes the actor's
    # own read access, so a screen that re-reads after a successful leave
    # prints `permission_denied` underneath "bạn đã rời nhóm". `QuanTriNhom`
    # switches to a terminal state instead, and this pair of lines is why.
    st_ds, _ = goi("GET", f"/contexts/{cid}/members", actor=TRANG, contexts=cid)
    can("người vừa rời đọc lại roster", st_ds, 403)
    st_nhom, _ = goi("GET", f"/contexts/{cid}", actor=TRANG, contexts=cid)
    can("người vừa rời đọc lại nhóm", st_nhom, 403)

    print()
    if hong:
        print(f"HỎNG {len(hong)} mục:")
        for h in hong:
            print(f"  - {h}")
        return 1
    print("ĐẠT: 5 route + 3 đối chứng âm, tất cả đúng mã trạng thái mong đợi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
