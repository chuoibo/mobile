#!/usr/bin/env python3
"""F14. Walk the two outing-invite routes against a LIVE server.

Why this file exists rather than another fake-repository case: the invite
screen's copy makes two claims about what the server will refuse, and both are
now printed to a person BEFORE they press anything. A claim about a refusal is
only worth the run that produced it.

    1. A `group` invite may only name an ACTIVE member. An `invited`
       membership must answer 422 `participant_not_in_context`.
    2. Revoking does NOT free the person to be invited again. The second
       invite must answer 409 `invite_already_exists`.

Claim 2 is the one that would be easy to get backwards by reading the code
optimistically, and it is the sentence the screen prints under every "Thu hồi"
button.

## The positive control is not decoration

Three of the five checks below expect a REFUSAL. A dead server, a wrong port,
or a typo in the path also produces a refusal, so a table of green "refused as
expected" rows is exactly what a broken harness prints. `PHAI_XANH` asserts the
happy path FIRST, and nothing else runs unless a real invite was really
created. Without it this file could pass against a server that is not running.

Run:  MOBILE_API=http://localhost:8099 python3 tests/qa/qa2-moi-vao-chuyen/di-bo-loi-moi-chuyen.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("MOBILE_API", "http://localhost:8099").rstrip("/")
# Two spellings of the same claim, kept apart so a failure names which one.
QUYEN = "group_admin,member,advancer,recipient,batch_owner"


class Ket:
    def __init__(self, status: int, body: object) -> None:
        self.status = status
        self.body = body

    def ma(self) -> str:
        if isinstance(self.body, dict):
            v = self.body.get("code") or self.body.get("detail")
            if isinstance(v, str):
                return v
            if isinstance(v, dict):
                return str(v.get("code", ""))
        return ""


def goi(
    method: str,
    path: str,
    body: object | None = None,
    actor: str | None = None,
    contexts: str | None = None,
    khoa: str | None = None,
) -> Ket:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if actor:
        req.add_header("X-Actor-ID", actor)
        req.add_header("X-Actor-Roles", QUYEN)
    if contexts:
        req.add_header("X-Actor-Contexts", contexts)
    if khoa:
        req.add_header("Idempotency-Key", khoa)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode() or "null"
            return Ket(r.status, json.loads(raw))
    except urllib.error.HTTPError as e:
        raw = e.read().decode() or "null"
        try:
            return Ket(e.code, json.loads(raw))
        except json.JSONDecodeError:
            return Ket(e.code, raw)
    except urllib.error.URLError as e:
        return Ket(0, f"khong noi duoc toi may chu: {e.reason}")


def nguoi_moi(so: str, ten: str) -> str:
    """A registered person, through the same two calls the app makes."""
    r = goi("POST", "/identity/person-id", {"phone": so})
    assert r.status == 200, f"person-id {so}: {r.status} {r.body}"
    pid = r.body["person_id"]
    r = goi("PUT", f"/people/{pid}", {"display_name": ten}, actor=pid)
    assert r.status in (200, 201), f"dat ten {ten}: {r.status} {r.body}"
    return pid


def so_dt() -> str:
    """A distinct Vietnamese mobile number per run.

    Fixed numbers would make the second run of this file collide with the
    first: `POST /identity/person-id` is a lookup, so it hands back the SAME
    person, who is already in a group and already invited to a trip. The walk
    would then measure yesterday's state and call it today's.
    """
    return "09" + uuid.uuid4().int.__str__()[:8]


ket_qua: list[tuple[bool, str, str]] = []


def kiem(ten: str, that: bool, ghi: str) -> None:
    ket_qua.append((that, ten, ghi))
    print(f"{'DAT ' if that else 'HONG'}  {ten}\n        {ghi}")


def main() -> int:
    print(f"# may chu: {BASE}\n")

    hp = goi("GET", "/healthz")
    if hp.status != 200:
        print(f"KHONG CHAY: /healthz -> {hp.status} {hp.body}")
        return 2

    chu = nguoi_moi(so_dt(), "Chu nhom")
    ban = nguoi_moi(so_dt(), "Ban da vao nhom")
    cho = nguoi_moi(so_dt(), "Nguoi con cho duyet")

    r = goi("POST", "/contexts", {"display_name": "Nhom di bo F14"}, actor=chu,
            khoa=str(uuid.uuid4()))
    assert r.status == 201, f"tao nhom: {r.status} {r.body}"
    ctx = r.body["id"]

    # `ban` accepts and becomes ACTIVE; `cho` is left at `invited` on purpose.
    r = goi("POST", f"/contexts/{ctx}/members", {"person_id": ban}, actor=chu,
            contexts=ctx, khoa=str(uuid.uuid4()))
    assert r.status == 201, f"moi ban vao nhom: {r.status} {r.body}"
    mid = r.body["id"]
    r = goi("POST", f"/memberships/{mid}/accept", actor=ban, contexts=ctx,
            khoa=str(uuid.uuid4()))
    assert r.status == 200, f"ban nhan loi moi nhom: {r.status} {r.body}"

    r = goi("POST", f"/contexts/{ctx}/members", {"person_id": cho}, actor=chu,
            contexts=ctx, khoa=str(uuid.uuid4()))
    assert r.status == 201, f"moi nguoi cho vao nhom: {r.status} {r.body}"
    assert r.body["state"] == "invited", r.body["state"]

    r = goi("POST", f"/contexts/{ctx}/outings", {
        "title": "Da Lat cuoi tuan",
        "starts_on": "2026-10-17",
        "ends_on": "2026-10-19",
        "headcount": 8,
        "budget_per_person_vnd": 2500000,
    }, actor=chu, contexts=ctx, khoa=str(uuid.uuid4()))
    assert r.status == 201, f"tao chuyen: {r.status} {r.body}"
    chuyen = r.body["id"]

    # ---- PHAI_XANH: the positive control, first and unconditional ----------
    r = goi("POST", f"/outings/{chuyen}/invites",
            {"source": "group", "person_id": ban},
            actor=chu, contexts=ctx, khoa=str(uuid.uuid4()))
    kiem(
        "PHAI_XANH moi mot thanh vien ACTIVE thi tao duoc loi moi",
        r.status == 201 and r.body.get("invited_person_id") == ban,
        f"HTTP {r.status}, invited_person_id khop: "
        f"{r.body.get('invited_person_id') == ban if isinstance(r.body, dict) else r.body}",
    )
    if r.status != 201:
        print("\nDoi chung duong bi hong -> moi ket qua 'tu choi' duoi day vo nghia.")
        return 1
    moi_id = r.body["id"]
    kiem(
        "loi moi kieu group KHONG phat token",
        r.body.get("invite_token") is None and r.body.get("invite_path") is None,
        f"invite_token={r.body.get('invite_token')!r} "
        f"invite_path={r.body.get('invite_path')!r}",
    )

    # ---- claim 1: an `invited` membership is not invitable ----------------
    r = goi("POST", f"/outings/{chuyen}/invites",
            {"source": "group", "person_id": cho},
            actor=chu, contexts=ctx, khoa=str(uuid.uuid4()))
    kiem(
        "moi nguoi chua nhan loi vao nhom -> 422 participant_not_in_context",
        r.status == 422 and "participant_not_in_context" in r.ma(),
        f"HTTP {r.status}, ma={r.ma()!r}",
    )

    # ---- claim 2: revoke does not free the person -------------------------
    r = goi("POST", f"/outings/{chuyen}/invites/{moi_id}/revoke",
            actor=chu, contexts=ctx, khoa=str(uuid.uuid4()))
    kiem(
        "thu hoi loi moi tra 200 va dong dau revoked_at",
        r.status == 200 and bool(r.body.get("revoked_at")),
        f"HTTP {r.status}, revoked_at={r.body.get('revoked_at') if isinstance(r.body, dict) else r.body!r}",
    )

    r = goi("POST", f"/outings/{chuyen}/invites",
            {"source": "group", "person_id": ban},
            actor=chu, contexts=ctx, khoa=str(uuid.uuid4()))
    kiem(
        "moi LAI dung nguoi do sau khi thu hoi -> 409 invite_already_exists "
        "(CUA MOT CHIEU)",
        r.status == 409 and "invite_already_exists" in r.ma(),
        f"HTTP {r.status}, ma={r.ma()!r}",
    )

    # ---- a link invite hands its token back exactly once -------------------
    r = goi("POST", f"/outings/{chuyen}/invites", {"source": "link"},
            actor=chu, contexts=ctx, khoa=str(uuid.uuid4()))
    kiem(
        "loi moi bang link co token va khong goi ten ai",
        r.status == 201
        and isinstance(r.body.get("invite_token"), str)
        and r.body.get("invited_person_id") is None,
        f"HTTP {r.status}, co token={isinstance(r.body.get('invite_token'), str) if isinstance(r.body, dict) else False}, "
        f"invited_person_id={r.body.get('invited_person_id') if isinstance(r.body, dict) else r.body!r}",
    )

    hong = [t for ok, t, _ in ket_qua if not ok]
    print(f"\n# {len(ket_qua) - len(hong)}/{len(ket_qua)} dat")
    for t in hong:
        print(f"#   HONG: {t}")
    return 1 if hong else 0


if __name__ == "__main__":
    sys.exit(main())
