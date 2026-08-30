"""Post-merge walk of F39/F42 at main HEAD, over a REAL server and database.

#308 is already on `main` and already carries a PASS (qa-tt-0029, measured on a
merge tree that never became a commit). This walk re-measures at the SHA that
actually shipped and spends its effort on the four things that verdict left to
unit tests or did not reach at all:

    3. revocation of `friends` AFTER the post was written
    5. a PENDING friend request must not open `friends`
    6. EXIF stripping, and whether a post's image is reachable by someone who
       cannot read the post
    2. a `group` post must not cross into a different group

Items 1 and 4 are re-run too, because the fixture is already standing and a
re-measurement at a new SHA costs one request each.

Six people, two groups, three read surfaces. Every negative assertion counts
RECORDS, never status codes: a feed that leaks one row still answers 200.

    reader   relation to AN (the author)
    ------   --------------------------
    AN       the author
    BAN      accepted friend, in no group with AN
    CUONG    active member of G1, not a friend
    DUYEN    a stranger who knows the ids
    PHUC     a PENDING friend request, never accepted
    EM       active member of G2, not in G1, not a friend

Run: python3 tests/qa/qa-tt-0032/di-bo-f42-thu-hoi-va-anh.py http://127.0.0.1:8153
Exit 0 = every cell matched what F42 promises. Exit 1 = at least one did not.
"""

from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.request
import uuid

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8153"

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


def call_bytes(path: str, *, actor: str) -> tuple[int, bytes, str]:
    """A photo read. Returns raw bytes so EXIF can be inspected."""
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("X-Actor-ID", actor)
    req.add_header("X-Actor-Roles", "member")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read(), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get("Content-Type", "")


def upload_photo(context_id: str, actor: str, raw: bytes) -> tuple[int, dict | str]:
    """multipart/form-data by hand: the product's only image write path."""
    boundary = "----qa-tt-0032-" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="anh.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode()
    body += raw + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{BASE}/contexts/{context_id}/photos", data=body, method="POST"
    )
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("X-Actor-ID", actor)
    req.add_header("X-Actor-Roles", "member")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raw_err = exc.read().decode()
        try:
            return exc.code, json.loads(raw_err)
        except json.JSONDecodeError:
            return exc.code, raw_err


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


def feed_ids(actor: str) -> set[str]:
    status, payload = call("GET", "/posts?limit=100", actor=actor)
    if status != 200:
        FAILURES.append(f"GET /posts cho {actor} tra {status}")
        return set()
    return {p["id"] for p in payload["posts"]}


def wall_ids(author: str, actor: str) -> set[str]:
    status, payload = call("GET", f"/people/{author}/posts?limit=100", actor=actor)
    if status != 200:
        FAILURES.append(f"GET /people/{author}/posts cho {actor} tra {status}")
        return set()
    return {p["id"] for p in payload["posts"]}


# --------------------------------------------------------------------------
# Fixture: six people, one friendship, one pending request, two groups
# --------------------------------------------------------------------------
AN, BAN, CUONG, DUYEN, PHUC, EM = (str(uuid.uuid4()) for _ in range(6))
NAMES = {AN: "An", BAN: "Ban", CUONG: "Cuong", DUYEN: "Duyen", PHUC: "Phuc", EM: "Em"}

print("== dung du lieu ==")
for pid, name in NAMES.items():
    status, _ = call("PUT", f"/people/{pid}", actor=pid, body={"display_name": name})
    must(f"tao nguoi {name}", status in (200, 201), f"status={status}")

status, fr_ban = call("POST", "/friends/requests", actor=AN, body={"addressee_id": BAN})
must("An moi ket ban Ban", status == 201, f"status={status} {fr_ban}")
status, _ = call(
    "POST",
    f"/friends/requests/{fr_ban['id']}/respond",
    actor=BAN,
    body={"decision": "accept"},
)
must("Ban chap nhan -> ACCEPTED", status == 200, f"status={status}")

# Phuc's request is sent and never answered. This is item 5: the whole point is
# that asking is not being.
status, fr_phuc = call(
    "POST", "/friends/requests", actor=AN, body={"addressee_id": PHUC}
)
must("An moi ket ban Phuc (KHONG tra loi)", status == 201, f"status={status} {fr_phuc}")

status, g1 = call("POST", "/contexts", actor=AN, body={"display_name": "Nhom Mot"})
must("An tao nhom G1", status == 201, f"status={status} {g1}")
G1 = g1["id"]
status, g2 = call("POST", "/contexts", actor=AN, body={"display_name": "Nhom Hai"})
must("An tao nhom G2", status == 201, f"status={status} {g2}")
G2 = g2["id"]

status, mem_cuong = call(
    "POST",
    f"/contexts/{G1}/members",
    actor=AN,
    body={"person_id": CUONG},
    roles="group_admin,member",
)
must("An moi Cuong vao G1", status in (200, 201), f"status={status} {mem_cuong}")
status, _ = call("POST", f"/memberships/{mem_cuong['id']}/accept", actor=CUONG)
must("Cuong chap nhan -> ACTIVE trong G1", status in (200, 201), f"status={status}")

status, mem_em = call(
    "POST",
    f"/contexts/{G2}/members",
    actor=AN,
    body={"person_id": EM},
    roles="group_admin,member",
)
must("An moi Em vao G2", status in (200, 201), f"status={status} {mem_em}")
status, _ = call("POST", f"/memberships/{mem_em['id']}/accept", actor=EM)
must("Em chap nhan -> ACTIVE trong G2", status in (200, 201), f"status={status}")

# --------------------------------------------------------------------------
# An writes five posts: four audiences, plus a second group post for item 2
# --------------------------------------------------------------------------
print("\n== An viet 5 bai ==")
POSTS: dict[str, str] = {}
SPEC = [
    ("only_me", None),
    ("friends", None),
    ("group_g1", G1),
    ("group_g2", G2),
    ("public", None),
]
for label, ctx in SPEC:
    audience = "group" if label.startswith("group") else label
    body = {"audience": audience, "body": f"bai {label}"}
    if ctx is not None:
        body["context_id"] = ctx
    status, post = call("POST", "/posts", actor=AN, body=body)
    must(f"tao bai {label}", status == 201, f"status={status} {post}")
    POSTS[label] = post["id"]

ALL = set(POSTS.values())


def expect_visible(who: str, name: str, visible: set[str]) -> None:
    """Assert the exact set this reader may see, on all three surfaces."""
    hidden = ALL - visible
    got_feed = feed_ids(who) & ALL
    check(f"{name} · GET /posts (dem ban ghi)", sorted(got_feed), sorted(visible))
    got_wall = wall_ids(AN, who) & ALL
    check(
        f"{name} · GET /people/An/posts (dem ban ghi)",
        sorted(got_wall),
        sorted(visible),
    )
    for label, pid in POSTS.items():
        status, _ = call("GET", f"/posts/{pid}", actor=who)
        want = 200 if pid in visible else 404
        check(f"{name} · GET /posts/{{{label}}}", status, want)
    must(
        f"{name} · khong bai nao bi giau lot vao ({len(hidden)} bai)",
        not (got_feed & hidden) and not (got_wall & hidden),
        f"lot: {sorted((got_feed | got_wall) & hidden)}",
    )


print("\n== MUC 1+2: bon audience, hai nhom — truoc khi thu hoi gi ==")
expect_visible(AN, "An (tac gia)", ALL)
expect_visible(BAN, "Ban (ban, khong o nhom nao)", {POSTS["friends"], POSTS["public"]})
expect_visible(
    CUONG, "Cuong (G1, khong phai ban)", {POSTS["group_g1"], POSTS["public"]}
)
expect_visible(DUYEN, "Duyen (nguoi la)", {POSTS["public"]})
expect_visible(EM, "Em (G2, KHONG o G1)", {POSTS["group_g2"], POSTS["public"]})

print("\n== MUC 5: loi moi ket ban DANG CHO khong mo audience friends ==")
expect_visible(PHUC, "Phuc (loi moi CHUA tra loi)", {POSTS["public"]})
status, phuc_edges = call("GET", f"/people/{PHUC}/friend-requests", actor=PHUC)
must("Phuc that su co mot loi moi dang cho", status == 200, f"status={status}")
pending = [e for e in phuc_edges.get("requests", []) if e.get("state") == "pending"]
must(
    "trang thai loi moi cua Phuc la pending (khong phai accepted)",
    len(pending) == 1,
    f"requests={phuc_edges}",
)

print("\n== MUC 2 (doi chieu): bai group cua G1 khong lot sang nguoi cua G2 ==")
must(
    "Em khong thay bai group_g1 o bat ky be mat nao",
    POSTS["group_g1"] not in (feed_ids(EM) | wall_ids(AN, EM)),
    "",
)
must(
    "Cuong khong thay bai group_g2 o bat ky be mat nao",
    POSTS["group_g2"] not in (feed_ids(CUONG) | wall_ids(AN, CUONG)),
    "",
)

# --------------------------------------------------------------------------
# Item 3: unfriending after the post was written
# --------------------------------------------------------------------------
print("\n== MUC 3: bo ket ban SAU khi dang — Ban phai MAT quyen doc ngay ==")
must(
    "truoc khi bo: Ban doc duoc bai friends",
    POSTS["friends"] in feed_ids(BAN),
    "",
)
status, blocked = call(
    "POST",
    f"/friends/requests/{fr_ban['id']}/respond",
    actor=AN,
    body={"decision": "block"},
)
must("An bo ket ban (block tu ACCEPTED)", status == 200, f"status={status} {blocked}")
check("trang thai canh sau khi bo", blocked.get("state"), "blocked")

after_feed = feed_ids(BAN) & ALL
after_wall = wall_ids(AN, BAN) & ALL
check("Ban · GET /posts sau khi bi bo ket ban", sorted(after_feed), [POSTS["public"]])
check(
    "Ban · GET /people/An/posts sau khi bi bo ket ban",
    sorted(after_wall),
    [POSTS["public"]],
)
status, _ = call("GET", f"/posts/{POSTS['friends']}", actor=BAN)
check("Ban · GET /posts/{friends} sau khi bi bo ket ban", status, 404)
must(
    "audience friends KHONG dong bang luc ghi",
    POSTS["friends"] not in (after_feed | after_wall),
    "bai cu van doc duoc -> danh sach nguoi nhan bi dong bang",
)

# --------------------------------------------------------------------------
# Item 4: leaving the group after the post was written
# --------------------------------------------------------------------------
print("\n== MUC 4: roi nhom SAU khi dang — Cuong phai MAT quyen doc ngay ==")
must(
    "truoc khi roi: Cuong doc duoc bai group_g1",
    POSTS["group_g1"] in feed_ids(CUONG),
    "",
)
status, left = call("DELETE", f"/contexts/{G1}/members/{CUONG}", actor=CUONG)
must("Cuong tu roi G1", status in (200, 204), f"status={status} {left}")

after_feed_c = feed_ids(CUONG) & ALL
after_wall_c = wall_ids(AN, CUONG) & ALL
check("Cuong · GET /posts sau khi roi nhom", sorted(after_feed_c), [POSTS["public"]])
check(
    "Cuong · GET /people/An/posts sau khi roi nhom",
    sorted(after_wall_c),
    [POSTS["public"]],
)
status, _ = call("GET", f"/posts/{POSTS['group_g1']}", actor=CUONG)
check("Cuong · GET /posts/{group_g1} sau khi roi nhom", status, 404)

# --------------------------------------------------------------------------
# Item 6: the image on a post
# --------------------------------------------------------------------------
print("\n== MUC 6: anh trong bai — EXIF va ai lay duoc URL ==")

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is an app dependency
    print("  SKIP Pillow khong co, khong dung duoc anh co EXIF")
    sys.exit(1 if FAILURES else 0)

# A JPEG carrying GPS + camera EXIF. If the server hands these bytes back
# unchanged, a bill photo tells everybody where the group was standing.
buf = io.BytesIO()
source = Image.new("RGB", (64, 48), (200, 30, 30))
exif = Image.Exif()
exif[271] = "QA-TT-0032-Make"  # Make
exif[272] = "QA-TT-0032-Model"  # Model
exif[305] = "QA-TT-0032-Software"  # Software
exif[34853] = {1: "N", 2: (21.0, 1.0, 44.0), 3: "E", 4: (105.0, 51.0, 0.0)}  # GPSInfo
source.save(buf, format="JPEG", exif=exif, quality=90)
RAW = buf.getvalue()
must(
    "anh nguon THAT SU mang EXIF truoc khi gui",
    b"QA-TT-0032-Make" in RAW and b"QA-TT-0032-Model" in RAW,
    "phep thu hong: anh nguon khong co EXIF thi khang dinh sau vo nghia",
)

# EM is in G2 only; CUONG has just left G1. AN uploads into G2 so a reader
# outside it (CUONG, DUYEN) can be tested against the photo route.
status, up = upload_photo(G2, AN, RAW)
must("An tai anh len G2", status == 201, f"status={status} {up}")
PHOTO_URL = up["url"]
must(
    "url anh co dang /contexts/{id}/photos/{id}",
    PHOTO_URL.startswith(f"/contexts/{G2}/photos/"),
    f"url={PHOTO_URL}",
)

status, got, ctype = call_bytes(PHOTO_URL, actor=AN)
check("An doc lai anh cua chinh minh", status, 200)
must("anh tra ve khong rong", len(got) > 0, f"len={len(got)}")
for marker in (b"QA-TT-0032-Make", b"QA-TT-0032-Model", b"QA-TT-0032-Software"):
    must(
        f"EXIF {marker.decode()} da bi tuoc khoi byte tra ve",
        marker not in got,
        "chuoi EXIF con nguyen trong anh may chu tra ve",
    )
parsed = Image.open(io.BytesIO(got))
served_exif = parsed.getexif()
check("so truong EXIF con lai tren anh phuc vu", len(dict(served_exif)), 0)
must(
    "khong con khoi GPS (tag 34853)",
    34853 not in dict(served_exif),
    f"exif={dict(served_exif)}",
)
must(
    "byte tra ve KHAC byte da gui (anh duoc dung lai, khong phai luu nguyen)",
    got != RAW,
    "may chu tra lai dung byte da nhan -> khong he sanitise",
)

print("\n-- 6b. bai public mang anh cua nhom: ai doc duoc bai, ai lay duoc anh --")
status, pub_post = call(
    "POST",
    "/posts",
    actor=AN,
    body={"audience": "public", "body": "bai public co anh", "image_url": PHOTO_URL},
)
must("An dang bai public kem anh cua G2", status == 201, f"status={status} {pub_post}")
PUB_IMG = pub_post["id"]

status, seen = call("GET", f"/posts/{PUB_IMG}", actor=DUYEN)
check("Duyen (nguoi la) doc duoc bai public", status, 200)
check("… va payload co mang url anh", seen.get("image_url"), PHOTO_URL)
status_img, body_img, _ = call_bytes(PHOTO_URL, actor=DUYEN)
must(
    "Duyen KHONG lay duoc byte anh (cong anh gac theo tu cach thanh vien)",
    status_img == 403,
    f"status={status_img} len={len(body_img)}",
)

print("\n-- 6c. bai only_me mang anh: nguoi KHONG doc duoc bai co lay duoc anh --")
status, priv_post = call(
    "POST",
    "/posts",
    actor=AN,
    body={"audience": "only_me", "body": "bai rieng co anh", "image_url": PHOTO_URL},
)
must("An dang bai only_me kem anh", status == 201, f"status={status} {priv_post}")
PRIV_IMG = priv_post["id"]

status, _ = call("GET", f"/posts/{PRIV_IMG}", actor=EM)
check("Em (cung G2) KHONG doc duoc bai only_me cua An", status, 404)
must(
    "url anh khong lot vao BAT KY payload nao Em doc duoc",
    all(
        p.get("image_url") != PHOTO_URL or p["id"] == PUB_IMG
        for p in (call("GET", "/posts?limit=100", actor=EM)[1] or {}).get("posts", [])
    ),
    "",
)
status_img_em, _, _ = call_bytes(PHOTO_URL, actor=EM)
must(
    "Em VAN lay duoc byte anh vi Em o trong G2 — ACL anh la cua NHOM, khong phai cua BAI",
    status_img_em == 200,
    f"status={status_img_em}",
)
status_img_c, _, _ = call_bytes(PHOTO_URL, actor=CUONG)
must(
    "Cuong (ngoai G2) khong lay duoc byte anh",
    status_img_c == 403,
    f"status={status_img_c}",
)

print("\n-- 6d. anh cua nhom minh KHONG o trong: duong ghi phai tu choi --")
status, refused = call(
    "POST",
    "/posts",
    actor=DUYEN,
    body={"audience": "public", "body": "cuop anh", "image_url": PHOTO_URL},
)
check("Duyen dang bai kem anh cua G2 (khong phai nhom cua Duyen)", status, 403)

# --------------------------------------------------------------------------
print(f"\n== TONG: {CHECKS} phep kiem, {len(FAILURES)} that bai ==")
for line in FAILURES:
    print(f"  - {line}")
sys.exit(1 if FAILURES else 0)
