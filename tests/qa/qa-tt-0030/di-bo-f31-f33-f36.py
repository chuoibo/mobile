"""Walk F31 / F33 / F36 over HTTP on a running server, as a person would.

Everything below goes through the port. Nothing reaches into the repository or
constructs a service by hand, because the question this answers is whether the
three features work when they are wired to each other and to a real database --
not whether their units agree with their own fakes, which the suite already
covers.

Order matters. The preference profile (F31) and the album (F36) read history, so
the walk writes a conversation and an outing first and only then asks for them;
asking first would produce a legitimately empty answer that reads exactly like a
broken one. The contextual card (F33) calls Gemini for real, which is the point:
a card that is a template dressed as an answer is worth knowing about, and no
fake backend can tell you.

The last two blocks are the ones that can fail interestingly. `outsider` is a
real person who is not in the group and asks for all three; the group's taste
profile, its conversation-derived card, and its album are each somebody else's
data. Then one member fires the whole minute's allowance at the F33 card at once
-- concurrently, not in sequence -- because a per-actor window that only holds
when requests arrive one at a time is not a cap.

Usage: python3 tests/qa/qa-tt-0030/di-bo-f31-f33-f36.py [base_url]
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8134"

AN = uuid.uuid4()
BINH = uuid.uuid4()
OUTSIDER = uuid.uuid4()

FAILURES: list[str] = []


def call(
    method: str,
    path: str,
    actor: uuid.UUID,
    body: dict | None = None,
    roles: str = "member",
) -> tuple[int, dict | str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("X-Actor-ID", str(actor))
    req.add_header("X-Actor-Roles", roles)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw[:200]


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'OK ' if ok else 'LOI'}] {label}{(' -- ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


print("== dang ky nguoi ==")
# The API says so itself: `person_not_registered` / "Register this person with
# PUT /people/{person_id} first". Worth keeping in the walk -- an error that
# names the next call is the difference between a wall and a door.
for who, name in [(AN, "An"), (BINH, "Binh"), (OUTSIDER, "Nguoi la")]:
    code, _ = call("PUT", f"/people/{who}", who, {"display_name": name})
    if code not in (200, 201):
        check("dang ky nguoi", False, f"HTTP {code}")
print("  da dang ky 3 nguoi")

print("\n== dung nhom ==")
code, ctx = call("POST", "/contexts", AN, {"display_name": "Hoi ban di an"})
check("tao nhom", code == 201, f"HTTP {code}")
CID = ctx["id"]

code, invite = call(
    "POST",
    f"/contexts/{CID}/members",
    AN,
    {"person_id": str(BINH)},
    roles="group_admin,member",
)
check("moi thanh vien", code == 201, f"HTTP {code}")
# INVITED is not ACTIVE: the invitee has to say yes. Skipping this step is how
# a walk ends up measuring a stranger and calling it a member.
code, _ = call("POST", f"/memberships/{invite['id']}/accept", BINH)
check("thanh vien nhan loi moi", code == 200, f"HTTP {code}")

print("\n== viet hoi thoai (F33 doc cai nay) ==")
for who, text in [
    (AN, "Toi them lau ca ri, cay vao va co cho ngoi ngoai troi"),
    (BINH, "Chieu nay ranh, minh di quan nao gan Ba Dinh di"),
    (AN, "Dung, lan truoc an bun cha ngon ma hoi dong"),
]:
    code, _ = call(
        "POST", f"/contexts/{CID}/messages", who, {"kind": "text", "body": text}
    )
    if code not in (200, 201):
        check("gui tin nhan", False, f"HTTP {code}")
print(f"  da gui 3 tin nhan vao nhom {CID[:8]}")

print("\n== F31 ho so so thich ==")
code, prof = call("GET", f"/contexts/{CID}/preference-profile", AN)
check("thanh vien doc duoc", code == 200, f"HTTP {code}")
if code == 200:
    print("    ", json.dumps(prof, ensure_ascii=False)[:300])

print("\n== F36 album chuyen di ==")
code, alb = call("GET", f"/contexts/{CID}/albums", AN)
check("thanh vien doc duoc", code == 200, f"HTTP {code}")
if code == 200:
    print("    ", json.dumps(alb, ensure_ascii=False)[:300])

print("\n== F33 the goi y theo hoi thoai (Gemini that) ==")
code, card = call("GET", f"/contexts/{CID}/contextual-suggestion", AN)
check("thanh vien doc duoc", code == 200, f"HTTP {code}")
if code == 200:
    blob = json.dumps(card, ensure_ascii=False)
    print("    ", blob[:400])
    # Grounding: the card is supposed to be about THIS conversation. A card that
    # mentions nothing the group said is a template, and templates are the
    # failure mode a live backend is bought to avoid.
    hooks = ["cay", "ca ri", "ngoai troi", "Ba Dinh", "bun cha", "chieu"]
    hit = [h for h in hooks if h.lower() in blob.lower()]
    check(
        "the co bam vao hoi thoai",
        bool(hit),
        f"tu khoa khop: {hit}" if hit else "khong tu khoa nao cua nhom xuat hien",
    )

print("\n== nguoi ngoai nhom hoi ca ba ==")
for name, path in [
    ("F31 ho so", f"/contexts/{CID}/preference-profile"),
    ("F36 album", f"/contexts/{CID}/albums"),
    ("F33 the", f"/contexts/{CID}/contextual-suggestion"),
]:
    code, body = call("GET", path, OUTSIDER)
    check(f"{name}: nguoi ngoai bi tu choi", code in (403, 404), f"HTTP {code}")
    if code == 200:
        print("      RO RI:", json.dumps(body, ensure_ascii=False)[:200])

print("\n== 40 request SONG SONG cua mot actor vao cua F33 (tran 30/60s) ==")
with ThreadPoolExecutor(max_workers=40) as pool:
    codes = list(
        pool.map(
            lambda _: call("GET", f"/contexts/{CID}/contextual-suggestion", BINH)[0],
            range(40),
        )
    )
ok = codes.count(200)
refused = codes.count(429)
other = [c for c in codes if c not in (200, 429)]
print(f"  200={ok}  429={refused}  khac={other}")
check("khong vuot tran 30", ok <= 30, f"{ok} request qua cua")
check("co tu choi that", refused >= 1, f"{refused} lan 429")
check("khong loi la", not other, f"ma khac: {other}")

print("\n" + ("=" * 60))
print("KET QUA:", "DAT" if not FAILURES else f"HONG {len(FAILURES)}: {FAILURES}")
raise SystemExit(1 if FAILURES else 0)
