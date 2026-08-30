"""QA walk for PR #308 (F39 posts + F42 audiences) against a REAL server.

This is not a unit test. It talks HTTP to a uvicorn process backed by a real
PostgreSQL database, the way the mobile client will, and counts *records* --
not status codes -- because a feed that leaks one row still answers 200.

Four readers, four audiences, three read surfaces:

    reader          relation to the author
    ------          ----------------------
    AN              the author
    BAN             accepted friend, not in the group
    CUONG           active group member, not a friend
    DUYEN           neither; a stranger who knows the ids

    surface         route
    -------         -----
    feed            GET /posts
    wall            GET /people/{author}/posts
    by id           GET /posts/{post_id}

Run: python3 tests/qa/qa-tt-0029/di-bo-f39-f42.py http://127.0.0.1:8129
Exit 0 = every cell matched what F42 promises. Exit 1 = at least one did not.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import uuid

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8129"

FAILURES: list[str] = []
CHECKS = 0


def call(
    method: str,
    path: str,
    *,
    actor: str | None = None,
    body: dict | None = None,
    contexts: str | None = None,
    roles: str | None = "member",
) -> tuple[int, dict | list | str]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if actor is not None:
        req.add_header("X-Actor-ID", actor)
    if contexts is not None:
        req.add_header("X-Actor-Contexts", contexts)
    if roles is not None:
        req.add_header("X-Actor-Roles", roles)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else "")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def check(label: str, got, want) -> None:
    global CHECKS
    CHECKS += 1
    if got == want:
        print(f"  OK   {label}: {got!r}")
    else:
        print(f"  FAIL {label}: got {got!r}, want {want!r}")
        FAILURES.append(f"{label}: got {got!r}, want {want!r}")


def must(label: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        FAILURES.append(f"{label} {detail}")


# --- seed four people, one friendship, one group -------------------------
AN, BAN, CUONG, DUYEN = (str(uuid.uuid4()) for _ in range(4))
NAMES = {AN: "An", BAN: "Ban", CUONG: "Cuong", DUYEN: "Duyen"}

print("== dung du lieu ==")
for pid, name in NAMES.items():
    status, _ = call("PUT", f"/people/{pid}", actor=pid, body={"display_name": name})
    must(f"tao nguoi {name}", status in (200, 201), f"status={status}")

status, fr = call("POST", "/friends/requests", actor=AN, body={"addressee_id": BAN})
must("An gui loi moi ket ban toi Ban", status == 201, f"status={status} {fr}")
status, fr2 = call(
    "POST", f"/friends/requests/{fr['id']}/respond", actor=BAN, body={"decision": "accept"}
)
must("Ban chap nhan", status == 200, f"status={status} {fr2}")

status, ctx = call("POST", "/contexts", actor=AN, body={"display_name": "Nhom di an"})
must("An tao nhom", status == 201, f"status={status} {ctx}")
GROUP = ctx["id"]
status, mem = call(
    "POST",
    f"/contexts/{GROUP}/members",
    actor=AN,
    body={"person_id": CUONG},
    roles="group_admin,member",
)
must("An moi Cuong vao nhom", status in (200, 201), f"status={status} {mem}")
# Being added to a group is something that happens to you: the invite is
# INVITED until the person accepts, and only ACTIVE membership reads a
# `group` post. Skipping this step is what made the first walk read red.
status, acc = call("POST", f"/memberships/{mem['id']}/accept", actor=CUONG)
must("Cuong chap nhan loi moi", status in (200, 201), f"status={status} {acc}")

# --- An writes one post per audience -------------------------------------
print("\n== An viet 4 bai, moi audience mot bai ==")
POSTS: dict[str, str] = {}
for audience in ("only_me", "friends", "group", "public"):
    payload = {"body": f"bai {audience}", "audience": audience}
    if audience == "group":
        payload["context_id"] = GROUP
    status, post = call("POST", "/posts", actor=AN, body=payload)
    must(f"tao bai {audience}", status == 201, f"status={status} {post}")
    POSTS[audience] = post["id"]

# The author is never in doubt; every audience includes them.
EXPECTED_FEED = {
    AN: {"only_me", "friends", "group", "public"},
    BAN: {"friends", "public"},
    CUONG: {"group", "public"},
    DUYEN: {"public"},
}
BY_ID = {v: k for k, v in POSTS.items()}


def audiences_in(rows: list[dict]) -> set[str]:
    return {BY_ID[r["id"]] for r in rows if r["id"] in BY_ID}


print("\n== GET /posts (feed) — dem BAN GHI, khong dem status ==")
for reader, want in EXPECTED_FEED.items():
    status, page = call("GET", "/posts", actor=reader)
    must(f"feed cua {NAMES[reader]} tra 200", status == 200, f"status={status}")
    rows = page["posts"] if isinstance(page, dict) else []
    check(f"feed {NAMES[reader]} audience nhin thay", audiences_in(rows), want)

print("\n== GET /people/{An}/posts (tuong cua An) ==")
for reader, want in EXPECTED_FEED.items():
    status, page = call("GET", f"/people/{AN}/posts", actor=reader)
    must(f"tuong An doc boi {NAMES[reader]} tra 200", status == 200, f"status={status}")
    rows = page["posts"] if isinstance(page, dict) else []
    check(f"tuong An qua mat {NAMES[reader]}", audiences_in(rows), want)

print("\n== GET /posts/{id} (doc theo id) — 404 chu khong phai 403 ==")
for reader, want in EXPECTED_FEED.items():
    for audience, pid in POSTS.items():
        status, _ = call("GET", f"/posts/{pid}", actor=reader)
        expect = 200 if audience in want else 404
        check(f"{NAMES[reader]} doc bai {audience}", status, expect)

print("\n== 404 cua bai co that phai giong 404 cua id bia ==")
status_real, body_real = call("GET", f"/posts/{POSTS['only_me']}", actor=DUYEN)
status_fake, body_fake = call("GET", f"/posts/{uuid.uuid4()}", actor=DUYEN)
check("status bai that vs id bia", (status_real, status_fake), (404, 404))
check("than loi giong het nhau", body_real, body_fake)

print("\n== Header X-Actor-Contexts khai bua khong mua duoc gi ==")
status, page = call("GET", "/posts", actor=DUYEN, contexts=GROUP)
rows = page["posts"] if isinstance(page, dict) else []
check("Duyen khai minh o trong nhom -> feed", audiences_in(rows), {"public"})
status, _ = call("GET", f"/posts/{POSTS['group']}", actor=DUYEN, contexts=GROUP)
check("Duyen khai o trong nhom -> doc bai group", status, 404)
status, page = call("GET", "/posts", actor=DUYEN, contexts=GROUP, roles="group_admin,member")
rows = page["posts"] if isinstance(page, dict) else []
check("Duyen tu phong group_admin -> feed", audiences_in(rows), {"public"})

print("\n== Tac gia LA actor: gui kem author_id phai 422, khong phai bi bo qua ==")
status, err = call(
    "POST",
    "/posts",
    actor=DUYEN,
    body={"body": "gia mao", "audience": "public", "author_id": AN},
)
check("POST /posts kem author_id", status, 422)

print("\n== only_me mang context_id, va group thieu context_id ==")
status, _ = call(
    "POST",
    "/posts",
    actor=AN,
    body={"body": "x", "audience": "only_me", "context_id": GROUP},
)
check("only_me kem context_id", status, 422)
status, _ = call("POST", "/posts", actor=AN, body={"body": "x", "audience": "group"})
check("group thieu context_id", status, 422)

print("\n== Bai group cua nhom NGUOI KHAC: Cuong khong doc duoc ==")
status, ctx2 = call("POST", "/contexts", actor=DUYEN, body={"display_name": "Nhom khac"})
GROUP2 = ctx2["id"]
status, p2 = call(
    "POST",
    "/posts",
    actor=DUYEN,
    body={"body": "bai nhom khac", "audience": "group", "context_id": GROUP2},
)
must("Duyen tao bai trong nhom rieng", status == 201, f"status={status} {p2}")
status, _ = call("GET", f"/posts/{p2['id']}", actor=CUONG)
check("Cuong doc bai nhom khac", status, 404)
status, page = call("GET", "/posts", actor=CUONG)
rows = page["posts"] if isinstance(page, dict) else []
check("bai nhom khac lot vao feed Cuong", sum(1 for r in rows if r["id"] == p2["id"]), 0)

print("\n== Roi nhom thi mat quyen doc (group phan giai luc DOC) ==")
# The existing route only lets a person remove themselves (`is_self`), so
# Cuong leaves rather than An ejecting them. Same end state for F42: an
# inactive membership must stop resolving.
status, body = call(
    "DELETE",
    f"/contexts/{GROUP}/members/{CUONG}",
    actor=CUONG,
    roles="group_admin,member",
)
must("Cuong roi nhom", status in (200, 204), f"status={status} {body}")
status, page = call("GET", "/posts", actor=CUONG)
rows = page["posts"] if isinstance(page, dict) else []
check("feed Cuong sau khi roi nhom", audiences_in(rows), {"public"})
status, _ = call("GET", f"/posts/{POSTS['group']}", actor=CUONG)
check("Cuong doc bai group sau khi roi nhom", status, 404)

print(f"\n== TONG: {CHECKS} phep kiem, {len(FAILURES)} that bai ==")
for f in FAILURES:
    print("  - " + f)
sys.exit(1 if FAILURES else 0)
