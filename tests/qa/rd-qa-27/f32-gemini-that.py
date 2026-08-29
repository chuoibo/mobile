"""F32 live probe: real Gemini, repeated, plus cross-group isolation.

Two questions no unit test answers. First: does a real model stay inside the
catalogue across repeated calls, or does the happy path just happen to have been
lucky once? Nondeterministic output means one green call proves one green call.
Second: can group B's card carry group A's past? The route summarises a group in
five numbers, so a scoping slip here is a privacy leak with a number attached.
"""
import json
import sys
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timedelta, timezone

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8165"
ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 8


def call(method, path, body=None, actor=None, ctx=None, roles="member,group_admin"):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if actor:
        req.add_header("X-Actor-ID", actor)
        req.add_header("X-Actor-Roles", roles)
        if ctx:
            req.add_header("X-Actor-Contexts", ctx)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except Exception:
            return e.code, None


def person(name):
    pid = str(uuid.uuid4())
    call("PUT", f"/people/{pid}", {"display_name": name}, pid)
    return pid


def build_group(owner, mate, name, trips, checkins, secret_title=None):
    st, ctx = call("POST", "/contexts", {"display_name": name}, owner)
    cid = ctx["id"]
    st, m = call("POST", f"/contexts/{cid}/members", {"person_id": mate}, owner, cid)
    call("POST", f"/memberships/{m['id']}/accept", {}, mate)
    today = date.today()
    for title, days_ago, amount in trips:
        e_on = today - timedelta(days=days_ago)
        call("POST", f"/contexts/{cid}/outings", {
            "title": secret_title or title,
            "starts_on": e_on.isoformat(), "ends_on": e_on.isoformat(),
            "headcount": 2, "budget_per_person_vnd": 500_000}, owner, cid)
        occurred = datetime.combine(e_on, datetime.min.time(), timezone.utc)
        st, ex = call("POST", "/expenses", {
            "context_id": cid, "recorded_by_id": owner, "paid_by_id": owner,
            "verification_scope": "totals_only", "occurred_at": occurred.isoformat(),
            "participants": [owner, mate], "total_amount_vnd": amount,
            "description": title}, owner, cid)
        call("POST", f"/expenses/{ex['expense_id']}/confirm", {
            "proposal": ex["proposal"],
            "expected_allocations": ex["allocation"]["allocations"],
            "acknowledge_as_advancer": True},
            owner, cid, roles="member,group_admin,advancer")
    for pid in checkins:
        call("POST", f"/contexts/{cid}/checkins", {"place_id": pid}, owner, cid)
    return cid


AN, BINH = person("An"), person("Binh")
MAI, LAN = person("Mai"), person("Lan")

catalogue = {p["id"] for p in call("GET", "/places", None, AN)[1].get("places", [])}
print(f"catalogue size = {len(catalogue)} place ids")

# A group with a title nobody would produce by accident, so a leak is unmistakable.
SECRET = "SENTINEL-chuyen-rieng-cua-nhom-A-khong-duoc-lo"
A = build_group(AN, BINH, "Nhom A", [("Da Lat", 20, 640_000), ("Nuong dem", 9, 520_000)],
                ["p-tiem-nuong-xom-lao", "p-lung-chung-cafe"], secret_title=SECRET)
B = build_group(MAI, LAN, "Nhom B", [("Vung Tau", 15, 300_000)],
                ["p-lung-chung-cafe"])
print(f"group A = {A}\ngroup B = {B}\n")

print("=" * 74)
print(f"LIVE GROUNDING, {ROUNDS} real Gemini calls on group A")
print("=" * 74)
bad = []
reasons = {}
for i in range(1, ROUNDS + 1):
    st, s = call("GET", f"/contexts/{A}/suggestion", None, AN, A)
    if st != 200:
        bad.append(f"round {i}: HTTP {st}")
        print(f"  {i:>2}  HTTP {st}  !!")
        continue
    r = s.get("reason")
    reasons[r] = reasons.get(r, 0) + 1
    stops = s.get("stops") or []
    ids = [(x.get("place") or {}).get("id") for x in stops]
    outside = [i2 for i2 in ids if i2 not in catalogue]
    unpaired = [x.get("time_text") for x in stops
                if (x.get("reason") is None) != (x.get("verdict") is None)]
    coord = [k for x in stops for k in (x.get("place") or {})
             if k in ("lat", "lng", "latitude", "longitude")]
    # Only the model-authored text. `basis.recent_titles` is the group's own
    # data served back to its own member -- finding it there is correct, and an
    # earlier version of this probe flagged it as a leak. It is not one.
    authored = json.dumps([s.get("title"), s.get("when_text")]
                          + [[x.get("note"), x.get("reason")] for x in stops],
                          ensure_ascii=False)
    leak = SECRET in authored
    flags = []
    if outside:
        flags.append(f"OUTSIDE_CATALOGUE={outside}")
    if unpaired:
        flags.append(f"UNPAIRED={unpaired}")
    if coord:
        flags.append(f"COORDS={coord}")
    if leak:
        flags.append("OWN_TITLE_ECHOED_BY_MODEL")
    if flags:
        bad.append(f"round {i}: {' '.join(flags)}")
    verdicts = ",".join(str(x.get("verdict")) for x in stops)
    print(f"  {i:>2}  reason={r:<12} stops={len(stops)} verdicts=[{verdicts}] "
          f"{'  !! ' + ' '.join(flags) if flags else 'ok'}")
    print(f"      title={s.get('title')!r}")

print(f"\n  reason distribution: {reasons}")
print(f"  rounds with a problem: {len(bad)}/{ROUNDS}")
for b in bad:
    print("   !!", b)

print("\n" + "=" * 74)
print("CROSS-GROUP ISOLATION")
print("=" * 74)
st, sb = call("GET", f"/contexts/{B}/suggestion", None, MAI, B)
bb = (sb or {}).get("basis") or {}
raw_b = json.dumps(sb, ensure_ascii=False)
st, sa = call("GET", f"/contexts/{A}/suggestion", None, AN, A)
ba = (sa or {}).get("basis") or {}
print(f"  A basis: outings={ba.get('outing_count')} total={ba.get('split_total_vnd'):,} "
      f"titles={ba.get('recent_titles')}")
print(f"  B basis: outings={bb.get('outing_count')} total={bb.get('split_total_vnd'):,} "
      f"titles={bb.get('recent_titles')}")
checks = [
    ("group B never sees A's sentinel title", SECRET not in raw_b),
    ("group B outing_count is its own (1)", bb.get("outing_count") == 1),
    ("group B total is its own (300,000)", bb.get("split_total_vnd") == 300_000),
    ("group A total is its own (1,160,000)", ba.get("split_total_vnd") == 1_160_000),
]
for name, ok in checks:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    if not ok:
        bad.append(name)

# A member of A asking about B, and vice versa.
st, _ = call("GET", f"/contexts/{B}/suggestion", None, AN, f"{A},{B}")
print(f"  {'PASS' if st == 403 else 'FAIL'}  An (group A) reading group B's card -> {st} (expect 403)")
if st != 403:
    bad.append("cross-group read allowed")

print("\n" + "=" * 74)
print("RESULT:", "PROBLEMS FOUND" if bad else "no problem found")
for b in bad:
    print("  !!", b)
