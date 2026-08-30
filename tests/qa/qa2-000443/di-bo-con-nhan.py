#!/usr/bin/env python3
"""07.02. Walk *Còn nhận* against a LIVE server, from both sides of one dinner.

Mockup 07.02 puts three figures in a row -- Đã trả, Còn nhận, Còn phải trả --
and until this change only two of them existed, both about money going out.
`receivable_vnd` is the third: what other people still owe this person for
shares they fronted.

Why a live walk on top of `tests/postgres/test_person_finance_postgres.py`,
which already drives the same ledger: that file calls the repository directly.
It cannot see the route, the response model, or the strict-int wire type, and
those are the three places a correct query still reaches the screen wrong. A
`Decimal` escaping here serialises as `150000.0`, and every assertion written
in Python is still true of it.

## The shape being checked, and why both sides are walked

One expense, 300.000đ, paid by A and split evenly with B.

    A fronted B's 150.000đ         -> A: còn nhận 150.000đ, còn phải trả 0
    B owes A their share           -> B: còn nhận 0,        còn phải trả 150.000đ

Walking only A would pass against a query that forgot
`participant_id != person_id`: A's own share is also 150.000đ here, so the
number would be right for the wrong reason. B is what separates the two -- B
fronted nothing, so any receivable at all on B is the bug.

## The positive control is not decoration

Several checks below expect a ZERO. A dead server, a wrong port, an empty
database, or a typo in the path all produce zeroes too, so a table of green
"đúng 0đ" rows is exactly what a broken harness prints. `PHAI_XANH` asserts a
NON-zero first -- A really is owed 150.000đ -- and nothing after it can be read
as evidence unless that one held.

The same trap caught this walk once already: pointed at the wrong uvicorn (this
machine runs four at a time, one per lane) every refusal-shaped row was green
while the server had never heard of the field.

Run:  MOBILE_API=http://127.0.0.1:48131 python3 tests/qa/qa2-000443/di-bo-con-nhan.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime

BASE = os.environ.get("MOBILE_API", "http://localhost:8099").rstrip("/")
QUYEN = "group_admin,member,advancer,recipient,batch_owner"

TONG_VND = 300_000
PHAN_VND = 150_000


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
        with urllib.request.urlopen(req, timeout=20) as r:
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


def so_dt() -> str:
    """A distinct Vietnamese mobile number per run.

    Fixed numbers would make the second run measure the first run's ledger:
    `POST /identity/person-id` is a lookup, so it hands back the SAME person,
    who already fronted a dinner and is already owed for it. The walk would
    then read yesterday's money and call it today's.
    """
    return "09" + uuid.uuid4().int.__str__()[:8]


def nguoi_moi(ten: str) -> str:
    r = goi("POST", "/identity/person-id", {"phone": so_dt()})
    assert r.status == 200, f"person-id: {r.status} {r.body}"
    pid = r.body["person_id"]
    r = goi("PUT", f"/people/{pid}", {"display_name": ten}, actor=pid)
    assert r.status in (200, 201), f"dat ten {ten}: {r.status} {r.body}"
    return pid


def tai_chinh(person_id: str) -> dict:
    """The exact call `layTaiChinh` in the app makes, headers and all."""
    r = goi("GET", f"/people/{person_id}/finance", actor=person_id)
    assert r.status == 200, f"finance {person_id}: {r.status} {r.body}"
    return r.body


ket_qua: list[tuple[bool, str, str]] = []


def kiem(ten: str, that: bool, ghi: str) -> None:
    ket_qua.append((that, ten, ghi))


def main() -> int:
    print(f"Máy chủ: {BASE}\n")

    # --- dựng: một nhóm, hai người, một bữa ăn A trả cho cả hai -------------
    a = nguoi_moi("An")
    b = nguoi_moi("Bình")

    r = goi("POST", "/contexts", {"display_name": "Bữa tối"}, actor=a)
    assert r.status in (200, 201), f"tao nhom: {r.status} {r.body}"
    ctx = r.body["id"]

    r = goi("POST", f"/contexts/{ctx}/members", {"person_id": b}, actor=a, contexts=ctx)
    assert r.status in (200, 201), f"moi B: {r.status} {r.body}"
    mid = r.body["id"]
    r = goi("POST", f"/memberships/{mid}/accept", None, actor=b)
    assert r.status in (200, 201), f"B nhan loi: {r.status} {r.body}"

    de_xuat = {
        "context_id": ctx,
        "description": "Lẩu nấm",
        "recorded_by_id": a,
        "paid_by_id": a,
        "verification_scope": "totals_only",
        "occurred_at": datetime.now(UTC).isoformat(),
        "participants": [a, b],
        "total_amount_vnd": TONG_VND,
        "items": [],
        "surcharges": [],
        "discounts": [],
    }
    r = goi("POST", "/expenses", de_xuat, actor=a, contexts=ctx, khoa=str(uuid.uuid4()))
    assert r.status in (200, 201), f"de xuat: {r.status} {r.body}"
    expense_id = r.body["expense_id"]
    phan = r.body["allocation"]["allocations"]

    r = goi(
        "POST",
        f"/expenses/{expense_id}/confirm",
        {
            "proposal": de_xuat,
            "expected_allocations": phan,
            "acknowledge_as_advancer": True,
        },
        actor=a,
        contexts=ctx,
        khoa=str(uuid.uuid4()),
    )
    assert r.status in (200, 201), f"xac nhan: {r.status} {r.body}"

    # --- ĐỐI CHỨNG DƯƠNG: phải thấy một số KHÁC 0 trước đã ------------------
    #
    # Mọi dòng sau đây kiểm một số 0 hoặc một số không đổi, và cả ba thứ đó là
    # cái một máy chủ chết cũng trả về. Dòng này là dòng duy nhất không thể
    # xanh nếu phép đo hỏng.
    so_a = tai_chinh(a)
    kiem(
        "PHẢI XANH: A ứng tiền cho B thì A có tiền để nhận",
        so_a.get("receivable_vnd") == PHAN_VND,
        f"receivable_vnd = {so_a.get('receivable_vnd')} (chờ {PHAN_VND})",
    )
    if so_a.get("receivable_vnd") != PHAN_VND:
        print("Đối chứng dương ĐỎ — không đọc tiếp các dòng dưới.\n")
        bao_cao()
        return 1

    kiem(
        "A không nợ ai: phần của chính A là tiền đã tiêu, không phải nợ",
        so_a["outstanding_vnd"] == 0,
        f"outstanding_vnd = {so_a['outstanding_vnd']}",
    )
    kiem(
        "A đã chi đúng phần của A, không phải cả hoá đơn",
        so_a["spend_vnd"] == TONG_VND - PHAN_VND,
        f"spend_vnd = {so_a['spend_vnd']} (chờ {TONG_VND - PHAN_VND})",
    )

    # B là ca tách hai lỗi khác nhau ra: nếu truy vấn quên
    # `participant_id != person_id` thì B cũng "được nhận" 150.000đ trên một
    # bữa ăn B không trả một đồng nào.
    so_b = tai_chinh(b)
    kiem(
        "B chưa ứng cho ai nên không có gì để nhận",
        so_b["receivable_vnd"] == 0,
        f"receivable_vnd = {so_b['receivable_vnd']}",
    )
    kiem(
        "B nợ A đúng phần của B",
        so_b["outstanding_vnd"] == PHAN_VND,
        f"outstanding_vnd = {so_b['outstanding_vnd']}",
    )

    # Luật 1: số nguyên đồng, kiểm ở đúng biên làm hỏng nó. PostgreSQL cộng
    # bigint ra numeric, psycopg trả Decimal, FastAPI in ra 150000.0 — và mọi
    # dòng == ở trên vẫn xanh, vì Decimal("150000") == 150000.
    #
    # Đọc lại từ JSON THÔ, không đọc từ dict đã parse: json.loads đã biến
    # 150000.0 thành float rồi, nên `isinstance(..., int)` trên dict chỉ nói
    # được kiểu Python, không nói được cái gì đã đi qua dây.
    tho = goi("GET", f"/people/{a}/finance", actor=a)
    raw = json.dumps(tho.body)
    kiem(
        "mọi số tiền đi qua dây là số nguyên, không có .0 nào",
        all(
            isinstance(so_a[k], int) and not isinstance(so_a[k], bool)
            for k in ("spend_vnd", "settled_vnd", "outstanding_vnd", "receivable_vnd")
        )
        and ".0" not in raw,
        f"receivable_vnd kiểu {type(so_a['receivable_vnd']).__name__}",
    )

    # --- người khác không đọc được phần này của ai -------------------------
    r = goi("GET", f"/people/{a}/finance", actor=b)
    kiem(
        "B không đọc được tài chính của A, kể cả khi chung nhóm",
        r.status == 403 and r.ma() == "not_your_finances",
        f"{r.status} {r.ma()}",
    )
    kiem(
        "lời từ chối không mang theo con số nó đang từ chối",
        "150000" not in json.dumps(r.body),
        json.dumps(r.body)[:80],
    )

    print("Đã đi bộ xong. Kết quả:\n")
    bao_cao()
    return 0 if all(ok for ok, _, _ in ket_qua) else 1


def bao_cao() -> None:
    for ok, ten, ghi in ket_qua:
        print(f"  {'ĐẠT ' if ok else 'HỎNG'}  {ten}")
        print(f"          {ghi}")
    dat = sum(1 for ok, _, _ in ket_qua if ok)
    print(f"\n{dat}/{len(ket_qua)} đạt")


if __name__ == "__main__":
    sys.exit(main())
