"""F24: cross-group message_id must be 404, identical to a nonexistent one."""

import json
import urllib.error
import urllib.request
import uuid

BASE = "http://localhost:8286"


def call(
    m,
    p,
    actor=None,
    ctxs=None,
    body=None,
    roles="member,advancer,recipient,batch_owner",
):
    r = urllib.request.Request(BASE + p, method=m)
    r.add_header("Content-Type", "application/json")
    if actor:
        r.add_header("X-Actor-ID", actor)
        r.add_header("X-Actor-Roles", roles)
    if ctxs:
        r.add_header("X-Actor-Contexts", ctxs)
    d = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(r, d) as x:
            return x.status, json.loads(x.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw or b"{}")
        except Exception:
            return e.code, {"raw": raw[:200].decode("utf8", "replace")}


HA, NAM = str(uuid.uuid4()), str(uuid.uuid4())
for pid, n in [(HA, "Ha"), (NAM, "Nam")]:
    call("PUT", f"/people/{pid}", pid, body={"display_name": n})
_, gA = call("POST", "/contexts", HA, body={"display_name": "Nhom A"})
A = gA["id"]
_, gB = call("POST", "/contexts", NAM, body={"display_name": "Nhom B"})
B = gB["id"]

c, mA = call(
    "POST",
    f"/contexts/{A}/messages",
    HA,
    ctxs=A,
    body={"kind": "text", "body": "Toi vua tra 180k tien bun bo"},
)
c2, mB = call(
    "POST",
    f"/contexts/{B}/messages",
    NAM,
    ctxs=B,
    body={"kind": "text", "body": "Bi mat cua nhom B"},
)
print(f"msg A={c} msg B={c2}")
mAid = mA.get("id")
mBid = mB.get("id")
print("mA:", mAid, "| mB:", mBid)

print("\n=== F24 message_id cua nhom KHAC vs message KHONG TON TAI ===")
ghost = str(uuid.uuid4())
c1, b1 = call("POST", f"/contexts/{A}/messages/{mBid}/expense-draft", HA, ctxs=A)
c2, b2 = call("POST", f"/contexts/{A}/messages/{ghost}/expense-draft", HA, ctxs=A)
print(f"  msg cua nhom B  -> {c1} {json.dumps(b1)[:120]}")
print(f"  msg khong ton tai-> {c2} {json.dumps(b2)[:120]}")
print(
    f"  GIONG HET NHAU? {'CO' if (c1, b1) == (c2, b2) else 'KHONG -- phan biet duoc = cua so nhin vao nhom khac'}"
)

print("\n=== F24 co the khai danh tinh qua BODY khong? ===")
for body, label in [
    ({"paid_by_id": NAM}, "paid_by_id"),
    ({"shared_by": [NAM]}, "shared_by"),
    ({"person_id": NAM}, "person_id"),
    (None, "khong body (dung hop dong)"),
]:
    c, b = call(
        "POST", f"/contexts/{A}/messages/{mAid}/expense-draft", HA, ctxs=A, body=body
    )
    print(f"  {label:28s} -> {c} {json.dumps(b)[:90]}")
