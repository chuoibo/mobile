"""Walk #286 live, with people registered first."""

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


HA, NAM, LA = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
for pid, name in [(HA, "Ha"), (NAM, "Nam"), (LA, "Nguoi La")]:
    c, _ = call("PUT", f"/people/{pid}", pid, body={"display_name": name})
    assert c in (200, 201), (c, name)
print("da dang ky 3 nguoi")

c, gA = call("POST", "/contexts", HA, body={"display_name": "Nhom A"})
A = gA.get("id")
c2, gB = call("POST", "/contexts", NAM, body={"display_name": "Nhom B"})
B = gB.get("id")
print(f"nhom A={c} {A}\nnhom B={c2} {B}")
assert A and B, "khong tao duoc nhom - dung lai, harness hong"

print("\n=== F34 QUYEN DOC NGAN SACH (privacy) ===")
for label, actor, ctxs in [
    ("chu nhom A (ACTIVE)      ", HA, A),
    ("NGUOI LA + noi doi header", LA, A),
    ("nguoi la, khong khai ctx ", LA, None),
    ("thanh vien nhom KHAC     ", NAM, A),
]:
    c, b = call("GET", f"/contexts/{A}/budget", actor, ctxs=ctxs)
    flag = " <-- LO TIEN NHOM" if (c == 200 and actor != HA) else ""
    print(f"  {label}: {c}{flag}")

print("\n=== F34 LUAT TIEN 1 (candidate_per_person_vnd) ===")
for q, label in [
    ("true", "bool true"),
    ("180000.5", "float le"),
    ("180000.0", "float integral"),
    ("-5", "am"),
    ("0", "khong"),
    ("180000", "int hop le"),
]:
    c, b = call("GET", f"/contexts/{A}/budget?candidate_per_person_vnd={q}", HA, ctxs=A)
    print(f"  {label:16s} -> {c}")

print("\n=== F34 CHUA CO CHUYEN XONG: co bia so khong? ===")
c, b = call("GET", f"/contexts/{A}/budget?candidate_per_person_vnd=180000", HA, ctxs=A)
print(f"  {c} keys={list(b)}")
print("  ", json.dumps(b)[:400])
