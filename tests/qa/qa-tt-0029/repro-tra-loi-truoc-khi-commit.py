"""Hammer send-then-immediately-respond to see whether the 404 recurs."""
import json, sys, uuid, urllib.request, urllib.error
BASE = "http://127.0.0.1:8129"
def call(method, path, actor=None, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE+path, data=data, method=method)
    if data is not None: req.add_header("Content-Type","application/json")
    if actor: req.add_header("X-Actor-ID", actor); req.add_header("X-Actor-Roles","member")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw=r.read().decode(); return r.status,(json.loads(raw) if raw else "")
    except urllib.error.HTTPError as e:
        raw=e.read().decode()
        try: return e.code, json.loads(raw)
        except Exception: return e.code, raw
bad=0
N=200
for i in range(N):
    a,b = str(uuid.uuid4()), str(uuid.uuid4())
    call("PUT", f"/people/{a}", a, {"display_name":"A"})
    call("PUT", f"/people/{b}", b, {"display_name":"B"})
    s1, fr = call("POST","/friends/requests", a, {"addressee_id": b})
    if s1 != 201:
        print(f"[{i}] gui loi moi that bai: {s1} {fr}"); bad+=1; continue
    s2, res = call("POST", f"/friends/requests/{fr['id']}/respond", b, {"decision":"accept"})
    if s2 != 200:
        print(f"[{i}] respond: {s2} {res}"); bad+=1
print(f"== {N} vong, {bad} that bai ==")
sys.exit(1 if bad else 0)
