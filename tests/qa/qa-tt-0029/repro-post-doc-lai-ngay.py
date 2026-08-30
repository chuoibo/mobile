"""Does POST /posts answer 201 before the row is readable? 200 rounds."""

import json
import time
import uuid
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8129"


def call(method, path, actor=None, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if actor:
        req.add_header("X-Actor-ID", actor)
        req.add_header("X-Actor-Roles", "member")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else "")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


me = str(uuid.uuid4())
print("tao nguoi:", call("PUT", f"/people/{me}", me, {"display_name": "Tac gia"})[0])
time.sleep(1)
miss_read = miss_feed = 0
N = 200
for i in range(N):
    s, post = call("POST", "/posts", me, {"body": f"bai so {i}", "audience": "public"})
    if s != 201:
        print(f"[{i}] POST /posts -> {s} {post}")
        continue
    s2, _ = call("GET", f"/posts/{post['id']}", me)
    if s2 != 200:
        miss_read += 1
        print(f"[{i}] doc lai ngay bai vua tao -> {s2}")
        for _ in range(10):
            time.sleep(0.3)
            if call("GET", f"/posts/{post['id']}", me)[0] == 200:
                print("      -> xuat hien muon")
                break
    s3, page = call("GET", "/posts", me)
    ids = {r["id"] for r in page.get("posts", [])} if isinstance(page, dict) else set()
    if post["id"] not in ids:
        miss_feed += 1
        print(f"[{i}] bai vua tao KHONG co trong feed cua chinh tac gia")
print(f"== {N} vong: {miss_read} lan doc-theo-id truot, {miss_feed} lan feed truot ==")
