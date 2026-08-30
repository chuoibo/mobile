"""F16 walk: post the spec's own itinerary prompt and read what the server grounds.

Nothing here recomputes an itinerary. The probe asserts only on what the server
returned; a second planner written here would just be two wrong answers agreeing
with each other.
"""
import json
import sys
import urllib.error
import urllib.request
import uuid

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8451"
PROMPT = sys.argv[2] if len(sys.argv) > 2 else "Đi Đà Lạt 2 ngày 1 đêm, 8 người, budget 2 triệu/người."


def call(method, path, body=None, actor=None, ctx=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if actor:
        req.add_header("X-Actor-ID", actor)
        req.add_header("X-Actor-Roles", "member,group_admin")
        if ctx:
            req.add_header("X-Actor-Contexts", ctx)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


me = str(uuid.uuid4())
print("PUT  /people   ->", call("PUT", f"/people/{me}", {"display_name": "QA F16"}, me)[0])
st, ctx = call("POST", "/contexts", {"display_name": "Đà Lạt 2N1D"}, me)
cid = ctx["id"]
print("POST /contexts ->", st, cid)

st, _ = call("POST", f"/contexts/{cid}/messages", {"kind": "text", "body": PROMPT}, me, cid)
print("POST message   ->", st)
print("     prompt    =", PROMPT)

st, turn = call("POST", f"/contexts/{cid}/ai-turn", None, me, cid)
print("POST ai-turn   ->", st)
print("     spoke     =", turn.get("spoke"))
print("     reason    =", turn.get("reason"))

card = (turn.get("message") or {}).get("card")
print()
if not card:
    print("NO CARD RETURNED:", json.dumps(turn, ensure_ascii=False)[:500])
    sys.exit(1)

kind = card.get("kind")
payload = card.get("payload", {})
print("card kind      =", kind)
if kind == "itinerary":
    stops = payload.get("stops", [])
    print("title          =", payload.get("title"))
    print("stop count     =", len(stops))
    for s in stops:
        print(f"   {str(s.get('time_text')):<14} {s['place']['name']:<30} {str(s.get('note',''))[:44]}")
else:
    print("payload        =", json.dumps(payload, ensure_ascii=False)[:800])
