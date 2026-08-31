#!/usr/bin/env python3
"""Two-way control for the three 403s reported against F43 / F44 / F45.

The report `docs/claude/2026-08-31/qa2-022247-con-thieu-gi-va-vi-sao.md` listed
three rows as TAC (blocked):

    F43  GET  403 /contexts/1aa00000-aaaa-4aaa-8aaa-0000a0000001/map
    F44  GET  403 /contexts/1aa00000-aaaa-4aaa-8aaa-0000a0000001/heatmap
    F45  POST 403 /contexts/1aa00000-aaaa-4aaa-8aaa-0000a0000001/meet

Same context id, same status. That shape has two readings, and they need
opposite fixes, so a report that does not separate them is worse than no
report:

  (a) The caller is not a member of that group. 403 is then CORRECT, the
      server is fine, and the probe pointed at the wrong group.
  (b) A real permission defect: a caller who IS a member is still refused.

One direction cannot tell them apart. A 403 alone is consistent with both.
This script therefore runs FOUR directions against one live stack:

    A  member  x  1aa00000-...   the reported call, reproduced
    B  member  x  real group     the control (a) predicts 200 for
    C  stranger x  real group    the positive control -- proves the gate
                                 bites, so a 200 in B is membership being
                                 honoured and not the gate being off
    D  GET /contexts/{id}        does the id name a group at all?

Direction C is not optional. Without it, "B answered 200" is equally well
explained by a gate that lets everyone through, and the conclusion would rest
on the assumption the run was supposed to test.

It also answers a question the Lead asked separately, because a 403 and a
200-with-zero-areas look the same from a screen that only renders the empty
state: on the real group, does GET /heatmap return areas, or an empty list?
Those need different fixes too -- permissions versus seed data.

Nothing here writes. POST /meet is documented as reading no history and
writing no row; every other call is a GET.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

# The id `apps/mobile/src/screens/kham-pha/places.ts` pins, and the default
# argument of `banDoUrl` / `nhietDoUrl` / `diemHenUrl` in ban-do-nhom.ts.
ID_GHIM = "1aa00000-aaaa-4aaa-8aaa-0000a0000001"

# A stranger: syntactically valid, deliberately absent from `people`. What the
# gate is asked about is `memberships`, so a row in `people` is not needed to
# ask the question honestly.
NGUOI_LA = "0b0b0b0b-0b0b-4b0b-8b0b-0b0b0b0b0b0b"

ROLES = "member"

# Filled from `GET /areas` at startup, never written by hand. The route's own
# docstring says why: a list of district ids kept in a second place is a third
# copy to drift, and the symptom is a 422 that looks like a product defect. The
# first run of this probe made exactly that mistake -- it sent "quan-1" and
# read the 422 back as evidence about F45.
KHU: list[str] = []


def goi(api: str, method: str, path: str, actor: str, body: dict | None = None):
    """One HTTP call. Returns (status, decoded-body-or-raw-text)."""

    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(api + path, data=data, method=method)
    req.add_header("X-Actor-ID", actor)
    req.add_header("X-Actor-Roles", ROLES)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def ma_loi(body) -> str:
    if isinstance(body, dict):
        return str(body.get("code") or body.get("detail") or "")[:60]
    return str(body)[:60]


def ba_route(api: str, actor: str, ctx: str, nhan: str) -> dict[str, int]:
    """The three routes the report named, in the order it named them."""

    ket = {}
    for ten, method, path, body in (
        ("F43 map", "GET", f"/contexts/{ctx}/map", None),
        ("F44 heatmap", "GET", f"/contexts/{ctx}/heatmap", None),
        ("F45 meet", "POST", f"/contexts/{ctx}/meet", {"from_areas": KHU}),
    ):
        status, doc = goi(api, method, path, actor, body)
        ket[ten] = status
        thua = ""
        if ten == "F44 heatmap" and status == 200:
            # The distinction the Lead asked for: 403 and "200 with nothing in
            # it" are the same blank screen and different bugs.
            thua = (
                f"  khu={len(doc['areas'])}"
                f" resolved={doc['resolved_checkins']}"
                f" scanned={doc['scanned_checkins']}"
            )
        elif status != 200:
            thua = f"  {ma_loi(doc)}"
        print(f"  {nhan:<34} {method:<4} {ten:<12} -> {status}{thua}")
    return ket


def nhom_that(dsn: str) -> tuple[str, str, str]:
    """(context_id, ten, person_id cua mot thanh vien ACTIVE) from the database.

    Read with SQL because no route answers "which groups exist" -- and asking
    the API to name the group whose access is under test would be circular.
    """

    import psycopg

    with psycopg.connect(dsn) as conn:
        cur = conn.cursor()
        cur.execute(
            """select c.id, c.display_name, m.person_id
                 from contexts c
                 join memberships m on m.context_id = c.id
                where m.state = 'active'
                  and c.display_name not like '%KHONG dung%'
                  and c.display_name not like '%KHÔNG dùng%'
             order by c.created_at desc, m.role
                limit 1"""
        )
        row = cur.fetchone()
        if row is None:
            sys.exit(
                "khong tim thay nhom nao co thanh vien ACTIVE trong database nay "
                "-- chay scripts/seed_demo_data.py truoc"
            )
        return str(row[0]), str(row[1]), str(row[2])


def dem_hang(dsn: str, ctx: str) -> None:
    import psycopg

    with psycopg.connect(dsn) as conn:
        cur = conn.cursor()
        for ten, sql in (
            ("contexts", "select count(*) from contexts where id=%s"),
            ("memberships", "select count(*) from memberships where context_id=%s"),
        ):
            cur.execute(sql, (ctx,))
            print(f"    {ten:<12} {cur.fetchone()[0]} dong")


def heatmap_rong(api: str, ctx: str, actor: str) -> None:
    """Is an empty heatmap a permission problem or a data problem?

    Only reachable with --ghi, because unlike everything else here it WRITES:
    two check-ins onto the group's wall, through the same route the app uses.
    Run it on a disposable stack, never on the shared one.

    The question is worth a write because 403 and "200 with an empty list"
    reach a screen as the same blank rectangle, and they have opposite fixes.
    If posting a check-in makes areas appear, then permissions were never the
    problem on this route and seed data is.

    One trap this stage exists to name: this product has TWO things called a
    check-in. `POST /outing-stops/{id}/checkins` (F46, an arrival on a plan)
    writes `outing_stop_checkins`, and that table deliberately holds no
    coordinates. The heatmap reads `memories` with `kind="checkin"`, which is
    what `POST /contexts/{id}/checkins` writes. Posting the first and watching
    the heatmap stay empty looks exactly like a broken aggregation, and is not.
    """

    st, truoc = goi(api, "GET", f"/contexts/{ctx}/heatmap", actor)
    print(
        f"  truoc      GET  /heatmap -> {st}  khu={len(truoc['areas'])}"
        f" scanned={truoc['scanned_checkins']}"
    )

    st, doc = goi(api, "GET", f"/places?context_id={ctx}", actor)
    places = doc["places"] if isinstance(doc, dict) and "places" in doc else doc
    for place in places[:2]:
        st, _ = goi(
            api, "POST", f"/contexts/{ctx}/checkins", actor, {"place_id": place["id"]}
        )
        print(f"  ghi        POST /contexts/{{id}}/checkins {place['id']} -> {st}")

    st, sau = goi(api, "GET", f"/contexts/{ctx}/heatmap", actor)
    print(
        f"  sau        GET  /heatmap -> {st}  khu={len(sau['areas'])}"
        f" scanned={sau['scanned_checkins']}"
        f" {[(a['id'], a['visit_count']) for a in sau['areas']]}"
    )
    if len(truoc["areas"]) == 0 and len(sau["areas"]) > 0:
        print(
            "  => heatmap rong la DU LIEU, khong phai quyen: seed khong tao"
            " mot memory kind='checkin' nao."
        )
    else:
        print("  => khong khop hinh dang du kien -- doc hai dong tren.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=os.environ.get("MOBILE_SEED_API_BASE_URL"))
    ap.add_argument("--dsn", default=os.environ.get("MOBILE_DATABASE_URL"))
    ap.add_argument(
        "--ghi",
        action="store_true",
        help="chay them chang GHI check-in de phan biet heatmap rong voi 403 "
        "(sua du lieu -- chi chay tren stack dung mot lan)",
    )
    args = ap.parse_args()
    if not args.api or not args.dsn:
        sys.exit(
            "can --api va --dsn (hoac MOBILE_SEED_API_BASE_URL / MOBILE_DATABASE_URL)"
        )
    api = args.api.rstrip("/")
    dsn = args.dsn.replace("postgresql+psycopg://", "postgresql://")

    status, _ = goi(api, "GET", "/healthz", NGUOI_LA)
    print(f"API {api}  /healthz -> {status}")
    if status != 200:
        return 2

    st, khu = goi(api, "GET", "/areas", NGUOI_LA)
    if st != 200 or len(khu) < 2:
        sys.exit(f"GET /areas -> {st}, khong lay duoc khu xuat phat that")
    KHU[:] = [k["id"] for k in khu[:2]]
    print(f"khu xuat phat cho F45, lay tu GET /areas: {KHU}")

    ctx_that, ten, thanh_vien = nhom_that(dsn)
    print(f"nhom that: {ten}  {ctx_that}")
    print(f"thanh vien ACTIVE dung lam actor: {thanh_vien}")
    print()

    print(f"[D] id co phai mot nhom khong -- GET /contexts/{{id}} boi {thanh_vien[:8]}")
    for nhan, ctx in (
        ("ID GHIM 1aa00000-...", ID_GHIM),
        (f"NHOM THAT {ctx_that[:8]}", ctx_that),
    ):
        st, doc = goi(api, "GET", f"/contexts/{ctx}", thanh_vien)
        print(
            f"  {nhan:<34} GET  /contexts/{{id}} -> {st}  {ma_loi(doc) if st != 200 else ''}"
        )
        dem_hang(dsn, ctx)
    print()

    print("[A] TAI LAP -- thanh vien that x id ghim trong app")
    a = ba_route(api, thanh_vien, ID_GHIM, "thanh vien x ID GHIM")
    print()
    print("[B] DOI CHUNG -- CUNG actor do x nhom ho THUC SU thuoc ve")
    b = ba_route(api, thanh_vien, ctx_that, "thanh vien x NHOM THAT")
    print()
    print("[C] DOI CHUNG DUONG -- nguoi la x nhom that (cong phai can)")
    c = ba_route(api, NGUOI_LA, ctx_that, "nguoi la   x NHOM THAT")
    print()

    if args.ghi:
        print("[E] heatmap rong: quyen hay du lieu? (chang nay GHI)")
        heatmap_rong(api, ctx_that, thanh_vien)
        print()

    a_het_403 = set(a.values()) == {403}
    b_het_200 = set(b.values()) == {200}
    c_het_403 = set(c.values()) == {403}

    print("KET LUAN")
    print(f"  A  thanh vien x id ghim   : {sorted(set(a.values()))}")
    print(f"  B  thanh vien x nhom that : {sorted(set(b.values()))}")
    print(f"  C  nguoi la   x nhom that : {sorted(set(c.values()))}")
    if not c_het_403:
        print("  => C KHONG do. Cong khong can, moi ket luan tu B deu vo nghia.")
        return 1
    if a_het_403 and b_het_200:
        print("  => (a) PHEP DO CHON NHAM NHOM. San pham khong hong o quyen.")
        print("     403 la cau tra loi dung cho mot id khong phai nhom cua ai ca.")
        return 0
    if a_het_403 and not b_het_200:
        print("  => (b) LOI QUYEN THAT: thanh vien van bi tu choi tren nhom cua ho.")
        return 1
    print("  => khong khop hinh dang nao du kien -- doc bang tren, dung tin dong nay.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
