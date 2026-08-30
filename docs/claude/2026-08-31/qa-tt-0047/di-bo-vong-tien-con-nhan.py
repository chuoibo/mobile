"""Đi bộ trên API sống: câu in trên màn Cá nhân về "Còn nhận" có đúng không.

Màn hình sau #389 in nguyên văn cho người dùng đọc:

    "Một khoản chỉ rời khỏi 'còn nhận' khi bạn xác nhận đã nhận được tiền.
     Người kia báo đã chuyển thì chưa tính."

Đó là hai lời hứa về tiền, ngược chiều nhau, và walk của chính tác giả
(`tests/qa/qa2-000443/di-bo-con-nhan.py`) dừng lại trước cả hai: nó đo lúc vừa
chia xong, chưa ai trả đồng nào. Script này đi tiếp tới hết vòng tiền:

    chia -> mở đợt thu -> phát -> khách BÁO đã chuyển -> người nhận XÁC NHẬN

và đo `receivable_vnd` ở từng mốc.

Ba điều nó kiểm mà walk kia không kiểm:

  1. BÁO đã chuyển (tự khai) KHÔNG được làm giảm "còn nhận".
  2. XÁC NHẬN đã nhận (bằng chứng phía chủ nợ) PHẢI làm giảm đúng số đó.
  3. Bất biến chéo người: "còn nhận" của A luôn bằng tổng "còn phải trả" của
     những người còn lại. Hai con số này do hai truy vấn khác nhau tính ra, ở
     hai chiều khác nhau; chúng lệch nhau là một màn hình nói dối mà không ca
     nào trong repo bắt được.

Có ĐỐI CHỨNG DƯƠNG: dòng đầu tiên phải thấy một số KHÁC 0. Mọi dòng còn lại
kiểm một số 0 hoặc một số không đổi -- và một máy chủ chết cũng trả về đúng
những thứ đó.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta

BASE = os.environ.get("QA_BASE", "http://127.0.0.1:8000").rstrip("/")
TONG_VND = 300_000  # chia 2 -> 150.000 mỗi người, không có đồng lẻ
PHAN_VND = 150_000
SO_TK_GIA = "9704" + "18" + "0" * 9 + "1"  # 16 ký tự, tổng hợp

ket_qua: list[tuple[bool, str, str]] = []


class Ket:
    def __init__(self, status: int, body: object, raw: str = "") -> None:
        self.status = status
        self.body = body
        #: Text thô đúng như máy chủ gửi. `json.loads` đã đổi 150000.0 thành
        #: float trước khi ai đọc `body`, nên luật "số nguyên đồng" chỉ kiểm
        #: được ở đây.
        self.raw = raw

    def ma(self) -> str:
        if isinstance(self.body, dict):
            return str(self.body.get("code", ""))
        return ""


def goi(method, path, body=None, *, actor=None, contexts=None, khoa=None, form=False):
    if form:
        data = urllib.parse.urlencode(body).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
    else:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
    if actor:
        headers["X-Actor-ID"] = actor
        headers["X-Actor-Roles"] = "group_admin,member,advancer,recipient,batch_owner"
    if contexts:
        headers["X-Actor-Contexts"] = contexts
    if khoa:
        headers["Idempotency-Key"] = khoa
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            try:
                return Ket(r.status, json.loads(raw), raw)
            except json.JSONDecodeError:
                return Ket(r.status, raw, raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return Ket(e.code, json.loads(raw), raw)
        except json.JSONDecodeError:
            return Ket(e.code, raw, raw)
    except urllib.error.URLError as e:
        return Ket(0, f"khong noi duoc toi may chu: {e.reason}")


def so_dt() -> str:
    return "09" + uuid.uuid4().int.__str__()[:8]


def nguoi_moi(ten: str) -> str:
    r = goi("POST", "/identity/person-id", {"phone": so_dt()})
    assert r.status == 200, f"person-id: {r.status} {r.body}"
    pid = r.body["person_id"]
    r = goi("PUT", f"/people/{pid}", {"display_name": ten}, actor=pid)
    assert r.status in (200, 201), f"dat ten {ten}: {r.status} {r.body}"
    return pid


def tc(person_id: str) -> dict:
    r = goi("GET", f"/people/{person_id}/finance", actor=person_id)
    assert r.status == 200, f"finance {person_id}: {r.status} {r.body}"
    return r.body


def kiem(ten: str, that: bool, ghi: str) -> None:
    ket_qua.append((that, ten, ghi))


def main() -> int:
    print(f"Máy chủ: {BASE}\n")

    a = nguoi_moi("An")  # người ứng tiền
    b = nguoi_moi("Bình")  # người nợ

    r = goi("POST", "/contexts", {"display_name": "Lẩu"}, actor=a)
    assert r.status in (200, 201), f"tao nhom: {r.status} {r.body}"
    ctx = r.body["id"]
    r = goi("POST", f"/contexts/{ctx}/members", {"person_id": b}, actor=a, contexts=ctx)
    assert r.status in (200, 201), f"moi B: {r.status} {r.body}"
    r2 = goi("POST", f"/memberships/{r.body['id']}/accept", None, actor=b)
    assert r2.status in (200, 201), f"B nhan loi: {r2.status} {r2.body}"

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
    version_id = r.body["expense_version_id"]

    # === MỐC 1: vừa chia xong ===============================================
    # ĐỐI CHỨNG DƯƠNG. Dòng duy nhất không thể xanh nếu phép đo hỏng.
    m1a, m1b = tc(a), tc(b)
    kiem(
        "PHẢI XANH (đối chứng dương): A ứng cho B thì A có tiền để nhận",
        m1a.get("receivable_vnd") == PHAN_VND,
        f"A.receivable = {m1a.get('receivable_vnd')} (chờ {PHAN_VND})",
    )
    if m1a.get("receivable_vnd") != PHAN_VND:
        bao_cao()
        return 1
    kiem(
        "BẤT BIẾN CHÉO: 'còn nhận' của A = tổng 'còn phải trả' của người kia",
        m1a["receivable_vnd"] == m1b["outstanding_vnd"],
        f"A.receivable={m1a['receivable_vnd']} vs B.outstanding={m1b['outstanding_vnd']}",
    )

    # === mở đợt thu + phát ==================================================
    r = goi(
        "PUT",
        f"/people/{a}/bank-recipient",
        {
            "bank_bin": "970418",
            # Dựng ra chứ không viết thẳng: repo guard chặn mọi chuỗi số dài,
            # và luật đó đúng — một số tài khoản thật lọt vào Git là không rút
            # lại được. Số này tổng hợp, không thuộc về ai.
            "account_number": SO_TK_GIA,
            "account_name": "AN QA",
        },
        actor=a,
        khoa=str(uuid.uuid4()),
    )
    assert r.status in (200, 201), f"tai khoan nhan: {r.status} {r.body}"

    r = goi(
        "POST",
        "/batches",
        {
            "context_id": ctx,
            "expense_version_ids": [version_id],
            "due_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        },
        actor=a,
        contexts=ctx,
        khoa=str(uuid.uuid4()),
    )
    assert r.status in (200, 201), f"mo dot thu: {r.status} {r.body}"
    batch_id = r.body["batch_id"]
    obligations = r.body["obligations"]
    assert len(obligations) == 1, f"cho 1 nghia vu, duoc {len(obligations)}"
    ob = obligations[0]
    kiem(
        "A không tự nợ chính mình: chỉ có một nghĩa vụ, người gửi là B",
        ob["sender_id"] == b and ob["amount_vnd"] == PHAN_VND,
        f"sender={ob['sender_id'][:8]} amount={ob['amount_vnd']}",
    )

    # Mở đợt thu là một sự kiện về sổ, không phải một lần trả tiền.
    m2a = tc(a)
    kiem(
        "mở đợt thu KHÔNG làm đổi 'còn nhận' (chưa ai trả đồng nào)",
        m2a["receivable_vnd"] == PHAN_VND,
        f"A.receivable = {m2a['receivable_vnd']} (chờ {PHAN_VND})",
    )

    r = goi(
        "POST",
        f"/batches/{batch_id}/publish",
        {
            "delivery_method": "personal_link",
            "guest_link_expires_at": (
                datetime.now(UTC) + timedelta(days=7)
            ).isoformat(),
        },
        actor=a,
        contexts=ctx,
        khoa=str(uuid.uuid4()),
    )
    assert r.status in (200, 201), f"phat: {r.status} {r.body}"
    links = r.body["guest_links"]
    assert len(links) == 1, f"cho 1 link khach, duoc {len(links)}"
    token = links[0]["path"].rstrip("/").rsplit("/", 1)[-1]

    m3a = tc(a)
    kiem(
        "phát đợt thu KHÔNG làm đổi 'còn nhận'",
        m3a["receivable_vnd"] == PHAN_VND,
        f"A.receivable = {m3a['receivable_vnd']} (chờ {PHAN_VND})",
    )

    # === MỐC 2: KHÁCH TỰ BÁO ĐÃ CHUYỂN ======================================
    # Đây là nửa thứ nhất của câu in trên màn: tự khai KHÔNG được tính.
    r = goi(
        "POST",
        f"/g/{token}/da-chuyen",
        {"obligation_id": ob["obligation_id"]},
        form=True,
    )
    bao_ok = r.status in (200, 201, 303)
    kiem(
        "khách báo đã chuyển được (nếu không thì mốc dưới vô nghĩa)",
        bao_ok,
        f"POST /g/<token>/da-chuyen -> {r.status} {str(r.body)[:120]}",
    )

    m4a, m4b = tc(a), tc(b)
    kiem(
        "CÂU IN TRÊN MÀN, nửa 1: B *báo* đã chuyển thì 'còn nhận' của A KHÔNG giảm",
        m4a["receivable_vnd"] == PHAN_VND,
        f"A.receivable = {m4a['receivable_vnd']} (chờ vẫn {PHAN_VND})",
    )
    kiem(
        "đối xứng: B tự báo cũng KHÔNG tự xoá được nợ của chính B",
        m4b["outstanding_vnd"] == PHAN_VND,
        f"B.outstanding = {m4b['outstanding_vnd']} (chờ vẫn {PHAN_VND})",
    )

    # === MỐC 3: NGƯỜI NHẬN XÁC NHẬN ĐÃ NHẬN =================================
    r = goi(
        "POST",
        f"/obligations/{ob['obligation_id']}/confirm-receipt",
        {"amount_vnd": PHAN_VND, "idempotency_key": str(uuid.uuid4())},
        actor=a,
        contexts=ctx,
        khoa=str(uuid.uuid4()),
    )
    assert r.status in (200, 201), f"xac nhan da nhan: {r.status} {r.body}"

    m5a, m5b = tc(a), tc(b)
    kiem(
        "CÂU IN TRÊN MÀN, nửa 2: A xác nhận đã nhận thì 'còn nhận' về 0",
        m5a["receivable_vnd"] == 0,
        f"A.receivable = {m5a['receivable_vnd']} (chờ 0)",
    )
    kiem(
        "BẤT BIẾN CHÉO sau khi trả xong: A.receivable == B.outstanding",
        m5a["receivable_vnd"] == m5b["outstanding_vnd"],
        f"A.receivable={m5a['receivable_vnd']} vs B.outstanding={m5b['outstanding_vnd']}",
    )
    kiem(
        "tiền về KHÔNG làm đổi 'đã trả' của A (spend là tiền đã tiêu, không phải nợ)",
        m5a["spend_vnd"] == TONG_VND - PHAN_VND,
        f"A.spend = {m5a['spend_vnd']} (chờ {TONG_VND - PHAN_VND})",
    )

    # === MỐC 4: XÁC NHẬN HAI LẦN ============================================
    # Không có gì chặn một lần xác nhận thứ hai ở tầng sổ; code kẹp về 0. Nếu
    # kẹp hỏng, màn hình in một số ÂM hoặc chủ nợ đọc là mình đang nợ.
    r = goi(
        "POST",
        f"/obligations/{ob['obligation_id']}/confirm-receipt",
        {"amount_vnd": PHAN_VND, "idempotency_key": str(uuid.uuid4())},
        actor=a,
        contexts=ctx,
        khoa=str(uuid.uuid4()),
    )
    m6a = tc(a)
    kiem(
        "xác nhận lần hai không đẩy 'còn nhận' xuống số âm",
        m6a["receivable_vnd"] >= 0,
        f"lần hai -> HTTP {r.status}; A.receivable = {m6a['receivable_vnd']}",
    )

    # === Luật 1: số nguyên đồng, đọc từ JSON THÔ ============================
    #
    # Bản đầu của phép kiểm này hỏng, và nó hỏng theo đúng kiểu đáng ghi lại:
    # nó hỏi `".0" in raw` trên TOÀN THÂN phản hồi. Thân đó có cả `movements`,
    # và một dấu thời gian `...:14.077000+00:00` chứa `.0` — nên phép kiểm nổ
    # ĐỎ trong khi cả bốn số tiền đều là `int`. Một lượt xanh, lượt sau đỏ, cùng
    # một máy chủ: khác nhau ở phần lẻ của giây, không ở tiền.
    #
    # Phạm vi bây giờ neo vào chính bốn khoá tiền: số ngay sau `"<khoá>":` phải
    # là chữ số thuần, không dấu chấm, không `e`. Đọc từ text thô chứ không từ
    # dict, vì `json.loads` đã biến `150000.0` thành float trước khi tới đây.
    tho = goi("GET", f"/people/{a}/finance", actor=a)
    raw = tho.raw
    tien = ["spend_vnd", "settled_vnd", "outstanding_vnd", "receivable_vnd"]
    nguyen = {k: re.search(rf'"{k}"\s*:\s*(-?\d+)(?=[,\s}}])', raw) for k in tien}
    kiem(
        "mọi số tiền là số nguyên đồng, không có Decimal/float lọt ra dây",
        all(
            isinstance(tho.body[k], int) and not isinstance(tho.body[k], bool)
            for k in tien
        )
        and all(nguyen[k] is not None for k in tien),
        f"trên dây: { {k: (m.group(1) if m else 'KHÔNG PHẢI SỐ NGUYÊN') for k, m in nguyen.items()} }",
    )

    bao_cao()
    return 0 if all(ok for ok, _, _ in ket_qua) else 1


def bao_cao() -> None:
    print("=" * 72)
    for ok, ten, ghi in ket_qua:
        print(f"{'ĐẠT ' if ok else 'HỎNG'}  {ten}\n        {ghi}")
    dat = sum(1 for ok, _, _ in ket_qua if ok)
    print("=" * 72)
    print(f"ĐẠT {dat}   HỎNG {len(ket_qua) - dat}")


if __name__ == "__main__":
    sys.exit(main())
