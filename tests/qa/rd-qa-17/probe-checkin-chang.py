"""rd-qa-17 probe 2: đúng hình dạng body. Mời bằng mã QR, và check-in theo chặng."""

from __future__ import annotations

import json
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
    print(f"  {tag:<50} HTTP {status}  {json.dumps(body, ensure_ascii=False)[:190]}")


KIET, BICH, LA = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
for pid, name in [(KIET, "Kiệt"), (BICH, "Bích"), (LA, "Kẻ lạ")]:
    call("PUT", f"/people/{pid}", actor=pid, roles="member", body={"display_name": name})
_, ctx = call("POST", "/contexts", actor=KIET, roles="member", body={"display_name": "Nhóm Đà Lạt"})
CTX = ctx["id"]

print("=" * 78)
print("F05 · CÂU 2 — MỜI BẰNG MÃ QUÉT ĐƯỢC (đúng body)")
print("=" * 78)
st, b = call("POST", f"/contexts/{CTX}/members", actor=KIET, roles="group_admin",
             contexts=CTX, body={"person_id": BICH})
show("Kiệt mời Bích (id lấy từ mã QR)", st, b, keep=["person_id", "state", "role", "invited_by_id"])

print("\n Bích ở trạng thái nào, và đọc được gì CHƯA nhận lời mời?")
for path, tag in [(f"/contexts/{CTX}/members", "GET members"),
                  (f"/contexts/{CTX}/memories", "GET memories"),
                  (f"/contexts/{CTX}/balances", "GET balances")]:
    st, b = call("GET", path, actor=BICH, roles="member", contexts=CTX)
    show(tag + " (Bích INVITED)", st, b)

print("\n Kẻ lạ cầm mã của Bích, tự mời MÌNH vào nhóm Kiệt:")
st, b = call("POST", f"/contexts/{CTX}/members", actor=LA, roles="group_admin",
             contexts=CTX, body={"person_id": LA})
show("kẻ lạ tự mời mình", st, b)
print("\n Kẻ lạ dùng mã của Bích để mời Bích vào nhóm CỦA MÌNH (mã là bearer?):")
_, ctx2 = call("POST", "/contexts", actor=LA, roles="member", body={"display_name": "Nhóm lạ"})
st, b = call("POST", f"/contexts/{ctx2['id']}/members", actor=LA, roles="group_admin",
             contexts=ctx2["id"], body={"person_id": BICH})
show("mời Bích vào nhóm kẻ lạ", st, b, keep=["person_id", "state", "role"])
st, b = call("GET", f"/contexts/{ctx2['id']}/members", actor=BICH, roles="member",
             contexts=ctx2["id"])
show("Bích có bị KÉO vào nhóm lạ không?", st, b)

print()
print("=" * 78)
print("F46 · CHECK-IN THEO CHẶNG DỪNG — trường nào rời khỏi máy chủ?")
print("=" * 78)
st, outing = call("POST", f"/contexts/{CTX}/outings", actor=KIET, roles="member", contexts=CTX,
                  body={"title": "Đà Lạt 2 ngày", "starts_on": "2026-09-05",
                        "ends_on": "2026-09-06", "headcount": 4,
                        "budget_per_person_vnd": 1_500_000})
OUT = outing["id"]
st, tl = call("PUT", f"/outings/{OUT}/timeline", actor=KIET, roles="member", contexts=CTX,
              body={"stops": [{"at": "18:00", "label": "Ăn tối",
                               "place_name": "Tiệm Nướng Xóm Lào"}]})
stops = tl.get("stops", []) if isinstance(tl, dict) else []
show("PUT timeline", st, tl, keep=["id"])
STOP = stops[0]["id"] if stops else None
print(f"  chặng dừng: {STOP}")
print(f"  TRƯỜNG CỦA MỘT CHẶNG: {sorted(stops[0].keys()) if stops else '—'}")

st, b = call("POST", f"/outing-stops/{STOP}/checkins", actor=KIET, roles="member", contexts=CTX)
show("check-in chặng (KHÔNG body)", st, b)
print(f"  TRƯỜNG TRẢ VỀ: {sorted(b.keys()) if isinstance(b, dict) else b}")

st, b = call("POST", f"/outing-stops/{STOP}/checkins", actor=KIET, roles="member",
             contexts=CTX, body={"lat": 11.9404, "lng": 108.4383})
show("check-in chặng KÈM lat/lng", st, b)

st, b = call("POST", f"/outing-stops/{STOP}/checkins", actor=LA, roles="group_admin",
             contexts=CTX)
show("kẻ lạ check-in chặng (tự khai quyền)", st, b)

st, b = call("GET", f"/outings/{OUT}/checkins", actor=LA, roles="group_admin", contexts=CTX)
show("kẻ lạ đọc ai đã tới", st, b)

st, b = call("GET", f"/outings/{OUT}/checkins", actor=KIET, roles="member", contexts=CTX)
rows = b.get("checkins", []) if isinstance(b, dict) else []
print(f"  thành viên đọc: {len(rows)} dòng")
for r in rows:
    print(f"    {json.dumps(r, ensure_ascii=False)}")
print(f"  CÓ lat/lng/accuracy trong câu trả lời không? "
      f"{[k for k in (rows[0] if rows else {}) if k in ('lat', 'lng', 'accuracy', 'latitude', 'longitude')] or 'KHÔNG'}")

print("\n Check-in hai lần cùng một chặng (bấm nhầm hai lần):")
st, b = call("POST", f"/outing-stops/{STOP}/checkins", actor=KIET, roles="member", contexts=CTX)
show("lần hai", st, b, keep=["id", "person_id"])
st, b = call("GET", f"/outings/{OUT}/checkins", actor=KIET, roles="member", contexts=CTX)
print(f"  tổng số dòng sau hai lần bấm: {len(b.get('checkins', []))}")

print()
print("=" * 78)
print("QUÉT TOÀN BỘ CÂU TRẢ LỜI F46: có chuỗi toạ độ nào của NGƯỜI không?")
print("=" * 78)
call("POST", f"/contexts/{CTX}/checkins", actor=KIET, roles="member", contexts=CTX,
     body={"place_id": "p-lung-chung-cafe"})
st, wall = call("GET", f"/contexts/{CTX}/memories", actor=KIET, roles="member", contexts=CTX)
for m in wall.get("memories", []):
    print(f"  {m['kind']:<8} place={m.get('place_id')} lat={m.get('lat')} lng={m.get('lng')} "
          f"author={m['author_id'][:8]}")
print("\n  Toạ độ trên có phải của MÁY người dùng không? Đối chiếu catalogue:")
st, places = call("GET", "/places", actor=KIET, roles="member", contexts=CTX)
cat = {p["id"]: (p.get("lat"), p.get("lng")) for p in places.get("places", [])}
for m in wall.get("memories", []):
    if m["kind"] == "checkin":
        same = cat.get(m["place_id"]) == (m["lat"], m["lng"])
        print(f"    {m['place_id']:<24} catalogue={cat.get(m['place_id'])} "
              f"lưu={(m['lat'], m['lng'])}  KHỚP CATALOGUE={same}")
