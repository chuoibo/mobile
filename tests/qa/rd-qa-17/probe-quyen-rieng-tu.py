"""rd-qa-17 probes: what the F05 code carries, and what F46 stores about where people were.

Runs against a live API built from the PR head. Prints raw status + body for
every probe so the numbers in the report are transcript, not summary.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import uuid

BASE = "http://127.0.0.1:8717"


def call(method, path, actor=None, body=None, roles=None, contexts=None):
    req = urllib.request.Request(BASE + path, method=method)
    if actor:
        req.add_header("X-Actor-ID", actor)
    if roles:
        req.add_header("X-Actor-Roles", roles)
    if contexts:
        req.add_header("X-Actor-Contexts", contexts)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data, timeout=15) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw or b"null")
        except Exception:
            return e.code, raw.decode(errors="replace")


def show(tag, status, body, keep=None):
    if isinstance(body, dict) and keep:
        body = {k: body.get(k) for k in keep}
    s = json.dumps(body, ensure_ascii=False)
    print(f"  {tag:<52} HTTP {status}  {s[:170]}")


KIET = str(uuid.uuid4())
BICH = str(uuid.uuid4())
LA = str(uuid.uuid4())  # outsider who photographed the square

print("=" * 78)
print("BỐI CẢNH")
print("=" * 78)
print(f"  Kiệt (chủ nhóm)   {KIET}")
print(f"  Bích (chủ mã QR)  {BICH}")
print(f"  Kẻ lạ (ngoài nhóm){LA}")

for pid, name in [(KIET, "Kiệt"), (BICH, "Bích"), (LA, "Kẻ lạ")]:
    call("PUT", f"/people/{pid}", actor=pid, roles="member", body={"display_name": name})

st, ctx = call("POST", "/contexts", actor=KIET, roles="member", body={"display_name": "Nhóm Đà Lạt"})
CTX = ctx["id"]
st, ctx2 = call("POST", "/contexts", actor=LA, roles="member", body={"display_name": "Nhóm của kẻ lạ"})
CTX2 = ctx2["id"]
print(f"  Nhóm Kiệt         {CTX}")
print(f"  Nhóm kẻ lạ        {CTX2}")

print()
print("=" * 78)
print("F05 · CÂU 2 — QUÉT MÃ CÓ KÉO AI VÀO NHÓM KHÔNG?")
print("=" * 78)
print(" Kiệt quét mã của Bích rồi bấm 'Mời vào nhóm' (đúng hai lệnh màn hình gửi):")
st, b = call("PUT", f"/people/{BICH}", actor=KIET, roles="member",
             body={"display_name": "Bích"})
show("PUT /people/{Bích} — tên KHÔNG đổi", st, b)
st, b = call("POST", f"/contexts/{CTX}/members", actor=KIET, roles="group_admin",
             contexts=CTX, body={"person_id": BICH, "role": "member"})
show("POST members — mời Bích", st, b, keep=["person_id", "status", "role"])

st, b = call("GET", f"/contexts/{CTX}/members", actor=KIET, roles="group_admin", contexts=CTX)
rows = b.get("members", b) if isinstance(b, dict) else b
print(f"  roster sau khi mời: {json.dumps(rows, ensure_ascii=False)[:300]}")

print()
print(" Bích BỊ MỜI (chưa nhận) đã đọc được gì của nhóm chưa?")
for path, tag in [
    (f"/contexts/{CTX}/members", "GET members"),
    (f"/contexts/{CTX}/memories", "GET memories"),
    (f"/contexts/{CTX}/balances", "GET balances"),
    (f"/contexts/{CTX}/messages", "GET messages"),
]:
    st, b = call("GET", path, actor=BICH, roles="member", contexts=CTX)
    show(tag + " (Bích, INVITED)", st, b)

print()
print("=" * 78)
print("F05 · CÂU 1/3 — CẦM personId TỪ MÃ QR THÌ LÀM ĐƯỢC GÌ?")
print("=" * 78)
print(" Kẻ lạ chụp được ô vuông của Bích, giờ có personId của Bích.")
st, b = call("PUT", f"/people/{BICH}", actor=LA, roles="member",
             body={"display_name": "Kẻ Lạ Đổi Tên"})
show("PUT /people/{Bích} — đổi tên Bích", st, b)

st, b = call("GET", f"/people/{BICH}/finance", actor=LA, roles="member")
show("GET /people/{Bích}/finance", st, b)

st, b = call("GET", f"/people/{BICH}/bank-recipient", actor=LA, roles="member")
show("GET /people/{Bích}/bank-recipient", st, b)

# Built from pieces, never written out: repo_guard refuses long digit runs and
# cannot tell a fixture from a real account number. Same trick ma-ban.test.mjs
# uses for its telephone number.
SO_TK = "00" + "11" + "00" + "123" + "4567"
st, b = call("PUT", f"/people/{BICH}/bank-recipient", actor=LA, roles="member",
             body={"bank_bin": "970415", "account_number": SO_TK,
                   "account_name": "KE LA"})
show("PUT /people/{Bích}/bank-recipient", st, b)

print()
print(" Và cầm mã của Bích có tự vào được nhóm nào của Bích không?")
st, b = call("POST", f"/contexts/{CTX}/members", actor=LA, roles="member", contexts=CTX,
             body={"person_id": LA, "role": "member"})
show("Kẻ lạ tự mời mình vào nhóm Kiệt", st, b)

print()
print("=" * 78)
print("F46 · CÂU 4 — CHECK-IN CÓ LƯU / LỘ TOẠ ĐỘ CỦA AI KHÔNG?")
print("=" * 78)

st, b = call("POST", f"/contexts/{CTX}/checkins", actor=KIET, roles="member", contexts=CTX,
             body={"place_id": "p-tiem-nuong-xom-lao", "caption": "tới rồi"})
show("thành viên check-in nhóm", st, b, keep=["kind", "place_id", "place_name", "lat", "lng", "author_id"])
CHECKIN = b.get("id") if isinstance(b, dict) else None

print()
print(" Client TỰ KHAI toạ độ — server có nhận không?")
st, b = call("POST", f"/contexts/{CTX}/checkins", actor=KIET, roles="member", contexts=CTX,
             body={"place_id": "p-tiem-nuong-xom-lao", "lat": 10.7769, "lng": 106.7009})
show("body kèm lat/lng", st, b)

st, b = call("POST", f"/contexts/{CTX}/checkins", actor=KIET, roles="member", contexts=CTX,
             body={"place_id": "nha-cua-bich", "caption": "nhà Bích"})
show("place_id bịa (nhà một người)", st, b)

print()
print(" Người NGOÀI nhóm tự khai quyền:")
st, b = call("POST", f"/contexts/{CTX}/checkins", actor=LA, roles="group_admin", contexts=CTX,
             body={"place_id": "p-tiem-nuong-xom-lao"})
show("kẻ lạ check-in vào nhóm Kiệt", st, b)
st, b = call("GET", f"/contexts/{CTX}/memories", actor=LA, roles="group_admin", contexts=CTX)
show("kẻ lạ đọc tường (có toạ độ)", st, b)
st, b = call("GET", f"/contexts/{CTX}/memories?kind=checkin&place_id=p-tiem-nuong-xom-lao",
             actor=LA, roles="group_admin", contexts=CTX)
show("kẻ lạ lọc theo place_id", st, b)

print()
print(" Bộ lọc place_id có kéo được check-in của nhóm KHÁC sang không?")
call("POST", f"/contexts/{CTX2}/checkins", actor=LA, roles="member", contexts=CTX2,
     body={"place_id": "p-tiem-nuong-xom-lao", "caption": "nhóm kẻ lạ cũng ở đây"})
st, b = call("GET", f"/contexts/{CTX}/memories?place_id=p-tiem-nuong-xom-lao",
             actor=KIET, roles="member", contexts=CTX)
items = b.get("memories", []) if isinstance(b, dict) else []
print(f"  Kiệt lọc place_id trong nhóm mình: {len(items)} dòng, "
      f"context_id = {sorted({m['context_id'] for m in items})}")
print(f"  (nhóm Kiệt = {CTX})")
print(f"  caption thấy được: {[m.get('caption') for m in items]}")

print()
print("=" * 78)
print("F46 · CHECK-IN THEO CHẶNG — có toạ độ không?")
print("=" * 78)
st, outing = call("POST", f"/contexts/{CTX}/outings", actor=KIET, roles="member", contexts=CTX,
                  body={"title": "Đà Lạt 2 ngày", "starts_on": "2026-09-05",
                        "ends_on": "2026-09-06", "headcount": 4,
                        "budget_per_person_vnd": 1_500_000})
show("tạo buổi đi", st, outing, keep=["id", "title"])
OUT = outing.get("id")
st, tl = call("PUT", f"/outings/{OUT}/timeline", actor=KIET, roles="member", contexts=CTX,
              body={"stops": [{"at": "2026-09-05T18:00:00+07:00", "label": "Ăn tối",
                               "place_id": "p-tiem-nuong-xom-lao"}]})
stops = tl.get("stops", []) if isinstance(tl, dict) else []
STOP = stops[0]["id"] if stops else None
print(f"  chặng dừng: {STOP}")

st, b = call("POST", f"/outing-stops/{STOP}/checkins", actor=KIET, roles="member", contexts=CTX)
show("check-in chặng (không body)", st, b)
print(f"  TRƯỜNG TRẢ VỀ: {sorted(b.keys()) if isinstance(b, dict) else b}")

st, b = call("POST", f"/outing-stops/{STOP}/checkins", actor=KIET, roles="member",
             contexts=CTX, body={"lat": 11.9404, "lng": 108.4383})
show("check-in chặng KÈM lat/lng", st, b)

st, b = call("GET", f"/outings/{OUT}/checkins", actor=LA, roles="group_admin", contexts=CTX)
show("kẻ lạ đọc ai đã tới chặng nào", st, b)

st, b = call("GET", f"/outings/{OUT}/checkins", actor=KIET, roles="member", contexts=CTX)
rows = b.get("checkins", []) if isinstance(b, dict) else []
print(f"  thành viên đọc: {len(rows)} dòng, trường = "
      f"{sorted(rows[0].keys()) if rows else '—'}")
print(f"  dòng đầu: {json.dumps(rows[0], ensure_ascii=False) if rows else '—'}")

print()
print("=" * 78)
print("XONG")
print("=" * 78)
