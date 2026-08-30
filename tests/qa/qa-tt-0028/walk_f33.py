"""Walk PR #301's three routes on the live server, then attack its claims."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

BASE = "http://localhost:8137"


def call(path, actor=None, method="GET"):
    req = urllib.request.Request(BASE + path, method=method)
    if actor:
        req.add_header("X-Actor-ID", actor)
        req.add_header("X-Actor-Roles", "member")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body


ids = call("/__probe")[1]["ids"]
CTX, OWNER, OUTSIDER = ids["ctx"], ids["owner"], ids["outsider"]
OUTING, OTHER_OUTING = ids["outing"], ids["other_outing"]
FAKE = "deadbeef-face-4000-b00c-0ddba11deca7"

print("=" * 66)
print("A. DUONG HANH PHUC — thanh vien goi ca ba route")
print("=" * 66)
for name, path in (
    ("F31 preference-profile", f"/contexts/{CTX}/preference-profile"),
    ("F33 contextual-suggestion", f"/contexts/{CTX}/contextual-suggestion"),
    ("F36 albums", f"/contexts/{CTX}/albums"),
    ("F36 album chi tiet", f"/contexts/{CTX}/albums/{OUTING}"),
):
    st, body = call(path, OWNER)
    print(f"  {name:28s} -> {st}  {json.dumps(body, ensure_ascii=False)[:150]}")

print()
print("=" * 66)
print("B. RIENG TU — nguoi ngoai, id THAT vs id BIA (oracle do id chuyen di)")
print("=" * 66)
st_real, b_real = call(f"/contexts/{CTX}/albums/{OUTING}", OUTSIDER)
st_fake, b_fake = call(f"/contexts/{CTX}/albums/{FAKE}", OUTSIDER)
st_other, b_other = call(f"/contexts/{CTX}/albums/{OTHER_OUTING}", OUTSIDER)
print(
    f"  outing THAT cua nhom kia -> {st_real}  {json.dumps(b_real, ensure_ascii=False)}"
)
print(
    f"  outing BIA hoan toan     -> {st_fake}  {json.dumps(b_fake, ensure_ascii=False)}"
)
print(
    f"  outing CUA CHINH HO      -> {st_other}  {json.dumps(b_other, ensure_ascii=False)}"
)
same = (st_real == st_fake) and (b_real == b_fake)
print(f"  => THAT va BIA khong phan biet duoc: {same}")
for nhan, path in (
    ("F31", f"/contexts/{CTX}/preference-profile"),
    ("F33", f"/contexts/{CTX}/contextual-suggestion"),
    ("F36", f"/contexts/{CTX}/albums"),
):
    st, b = call(path, OUTSIDER)
    print(f"  nguoi ngoai goi {nhan}      -> {st}")

print()
print("=" * 66)
print("C. KHONG AI BI NEU TEN — doc PROMPT that se gui toi Gemini")
print("=" * 66)
call("/__reset", method="POST")
call(f"/contexts/{CTX}/contextual-suggestion", OWNER)
prompts = call("/__probe")[1]["prompts"]
print(f"  so prompt bat duoc: {len(prompts)}")
if prompts:
    p = prompts[0]
    checks = {
        "ten hien thi 'Tran Bao Khanh'": "Khánh" in p,
        "ten hien thi 'Nguyen Thu Ha'": "Hà" in p,
        "uuid nguoi (owner)": OWNER in p,
        "uuid nguoi (friend)": ids["friend"] in p,
        "the ai_card cu (CANARY_AI_CARD)": "CANARY_AI_CARD" in p,
        "cau nguoi that go 'Doi qua'": "Đói quá" in p,
    }
    for k, v in checks.items():
        flag = "CO  <-- RO RI" if v else "khong"
        if k.startswith("cau nguoi"):
            flag = "CO (dung, day la tinh nang)" if v else "KHONG (prompt rong?)"
        print(f"  {k:36s}: {flag}")
    print(f"\n  --- prompt that, {len(p)} ky tu ---")
    print("  " + p.replace("\n", "\n  ")[:900])
