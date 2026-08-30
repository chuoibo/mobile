import json
import urllib.error
import urllib.request
import uuid

BASE = "http://localhost:8286"
ROLES = "member,group_admin,advancer,recipient,batch_owner"


def call(m, p, actor=None, ctxs=None, body=None, roles=ROLES):
    r = urllib.request.Request(BASE + p, method=m)
    r.add_header("Content-Type", "application/json")
    if actor:
        r.add_header("X-Actor-ID", actor)
        r.add_header("X-Actor-Roles", roles)
    if ctxs:
        r.add_header("X-Actor-Contexts", ctxs)
    d = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(r, d, timeout=90) as x:
            return x.status, json.loads(x.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw or b"{}")
        except Exception:
            return e.code, {"raw": raw[:250].decode("utf8", "replace")}


HA, NAM = str(uuid.uuid4()), str(uuid.uuid4())
for pid, n in [(HA, "Ha"), (NAM, "Nam")]:
    call("PUT", f"/people/{pid}", pid, body={"display_name": n})
_, gA = call("POST", "/contexts", HA, body={"display_name": "Nhom A"})
A = gA["id"]
_, inv = call("POST", f"/contexts/{A}/members", HA, ctxs=A, body={"person_id": NAM})
call("POST", f"/memberships/{inv['id']}/accept", NAM, ctxs=A)
print(f"HA ={HA}\nNAM={NAM}")
_, mA = call(
    "POST",
    f"/contexts/{A}/messages",
    HA,
    ctxs=A,
    body={"kind": "text", "body": "Minh vua tra 180k tien bun bo cho ca nhom nhe"},
)
c, r = call("POST", f"/contexts/{A}/messages/{mA['id']}/expense-draft", NAM, ctxs=A)
d = r.get("draft") or {}
pb = str(d.get("paid_by_id"))
sb = sorted(str(x) for x in (d.get("shared_by") or []))
a = d.get("amount_vnd")
print(f"\n  paid_by_id = TAC GIA (HA)?      {pb == HA}")
print(f"  paid_by_id = NGUOI BAM (NAM)?   {pb == NAM}   <-- True la sai tham quyen")
print(f"  shared_by  = roster ACTIVE?     {sb == sorted([HA, NAM])} ({len(sb)} nguoi)")
print(f"  amount_vnd = {a!r} kieu={type(a).__name__}  (luat 1: so nguyen dong)")
print(f"  needs_review = {d.get('needs_review')!r}  (khong tu dong ghi so)")
print(f"  '180k' -> 180000 dung?          {a == 180000}")
print(f"  draft co truong ten nguoi nao khong? {[k for k in d if 'name' in k.lower()]}")
