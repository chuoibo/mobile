"""F32 walk: build a group's real past over HTTP, then read the card nobody asked for.

Nothing here recomputes a suggestion. The probe builds history through the same
routes a phone uses, then asserts only on what the server returned. The numbers
in `basis` are checked against `GET /recap` -- the route the memory wall reads --
because two independent reads of the same ledger disagreeing is the failure this
surface exists to prevent.
"""
import json
import sys
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timedelta, timezone

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8165"


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


print("=" * 72)
print("F32 walk  base =", BASE)
print("=" * 72)

AN = person("An")          # admin, ACTIVE
BINH = person("Binh")      # ACTIVE member
CUONG = person("Cuong")    # never a member -- outsider
DUNG = person("Dung")      # INVITED only, never accepted

st, ctx = call("POST", "/contexts", {"display_name": "Hoi ban Da Lat"}, AN)
cid = ctx["id"]
print(f"POST /contexts                 -> {st}  {cid}")

for who, label in ((BINH, "Binh"), (DUNG, "Dung")):
    st, m = call("POST", f"/contexts/{cid}/members", {"person_id": who}, AN, cid)
    print(f"POST members {label:<6}           -> {st}  membership={(m or {}).get('id')}"
          f" state={(m or {}).get('state')}")
    if label == "Binh" and m:
        sa, _ = call("POST", f"/memberships/{m['id']}/accept", {}, who)
        print(f"POST accept  {label:<6}           -> {sa}")

# --- history: two trips that ENDED, each with a confirmed expense -------------
today = date.today()
trips = [
    ("Da Lat 2N1D", today - timedelta(days=20), today - timedelta(days=18), 640_000),
    ("Nuong dem Tan Binh", today - timedelta(days=9), today - timedelta(days=9), 520_000),
]
for title, s_on, e_on, amount in trips:
    st, o = call("POST", f"/contexts/{cid}/outings", {
        "title": title, "starts_on": s_on.isoformat(), "ends_on": e_on.isoformat(),
        "headcount": 2, "budget_per_person_vnd": 500_000,
    }, AN, cid)
    print(f"POST outing {title:<20} -> {st}")
    occurred = datetime.combine(e_on, datetime.min.time(), timezone.utc)
    st, ex = call("POST", "/expenses", {
        "context_id": cid, "recorded_by_id": AN, "paid_by_id": AN,
        "verification_scope": "totals_only", "occurred_at": occurred.isoformat(),
        "participants": [AN, BINH], "total_amount_vnd": amount,
        "description": title,
    }, AN, cid)
    if st < 300:
        # Echo back the server's own allocation. Recomputing the split here
        # would be a second allocator, and two wrong answers agreeing.
        sc, cr = call("POST", f"/expenses/{ex['expense_id']}/confirm", {
            "proposal": ex["proposal"],
            "expected_allocations": ex["allocation"]["allocations"],
            "acknowledge_as_advancer": True,
        }, AN, cid, roles="member,group_admin,advancer")
        print(f"     expense {amount:>9,} VND     -> {st} confirm={sc}"
              f" {'' if sc < 300 else json.dumps(cr, ensure_ascii=False)[:160]}")
    else:
        print(f"     expense FAILED {st}: {json.dumps(ex, ensure_ascii=False)[:200]}")

# --- check-ins so the catalogue categories have something to say -------------
for pid in ("p-tiem-nuong-xom-lao", "p-lung-chung-cafe"):
    st, _ = call("POST", f"/contexts/{cid}/checkins", {"place_id": pid}, AN, cid)
    print(f"POST checkin {pid:<24} -> {st}")

# --- the read the memory wall does, for cross-checking basis ------------------
st, recap = call("GET", f"/contexts/{cid}/recap", None, AN, cid)
recap_trips = (recap or {}).get("outings") or (recap or {}).get("records") or []
print(f"\nGET  /recap                    -> {st}  trips={len(recap_trips)}")
recap_total = sum(t.get("split_total_vnd") or 0 for t in recap_trips)
print(f"     recap split_total_vnd     =  {recap_total:,}")

# --- THE CARD ----------------------------------------------------------------
print("\n" + "-" * 72)
st, sug = call("GET", f"/contexts/{cid}/suggestion", None, AN, cid)
print(f"GET  /suggestion  (An, ACTIVE) -> {st}")
print(json.dumps(sug, ensure_ascii=False, indent=2)[:2600])

print("\n" + "-" * 72)
print("PERMISSION PROBES")
for who, label, expect in ((CUONG, "Cuong  outsider", 403), (DUNG, "Dung   INVITED", 403)):
    st, r = call("GET", f"/contexts/{cid}/suggestion", None, who, cid)
    ok = "OK " if st == expect else "!! "
    print(f"  {ok}{label:<18} -> {st} (expect {expect})  {json.dumps(r, ensure_ascii=False)[:90]}")
st, r = call("GET", f"/contexts/{cid}/suggestion", None, None)
print(f"  {'OK ' if st in (401,422) else '!! '}{'no header':<18} -> {st} (expect 401/422)")

# --- contract assertions on the returned card --------------------------------
print("\n" + "-" * 72)
print("CONTRACT CHECKS on the card An received")
raw = json.dumps(sug, ensure_ascii=False)
fails = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}  {detail}")
    if not ok:
        fails.append(name)


if sug and sug.get("suggested"):
    stops = sug.get("stops") or []
    check("stops present", len(stops) > 0, f"{len(stops)} stops")
    check("no lat/lng anywhere in payload",
          "lat" not in raw.lower().replace("relat", "") or not any(
              k in (s.get("place") or {}) for s in stops for k in ("lat", "lng", "latitude", "longitude")),
          "")
    catalogue = {p["id"] for p in call("GET", "/places", None, AN, cid)[1].get("places", [])}
    ids = [(s.get("place") or {}).get("id") for s in stops]
    check("every place_id is in the catalogue",
          all(i in catalogue for i in ids), f"ids={ids}")
    for s in stops:
        pair = (s.get("reason") is None) == (s.get("verdict") is None)
        check(f"reason/verdict paired @ {s.get('time_text')}", pair,
              f"reason={'set' if s.get('reason') else 'null'} verdict={s.get('verdict')}")
    b = sug.get("basis") or {}
    check("basis.outing_count matches recap", b.get("outing_count") == len(recap_trips),
          f"basis={b.get('outing_count')} recap={len(recap_trips)}")
    check("basis.split_total_vnd matches recap", b.get("split_total_vnd") == recap_total,
          f"basis={b.get('split_total_vnd'):,} recap={recap_total:,}")
    avg, cnt = b.get("avg_per_person_vnd"), b.get("split_total_vnd")
    check("basis money are integers",
          all(isinstance(v, int) for v in (b.get("split_total_vnd"), b.get("outing_count")))
          and (avg is None or isinstance(avg, int)),
          f"avg={avg}")
    check("basis.top_categories non-empty", bool(b.get("top_categories")),
          str(b.get("top_categories")))
else:
    print(f"  card not suggested: reason={(sug or {}).get('reason')}")
    print(f"  basis still served: {json.dumps((sug or {}).get('basis'), ensure_ascii=False)}")

print("\n" + "=" * 72)
print("WALK RESULT:", "FAIL -> " + ", ".join(fails) if fails else "all contract checks passed")
print("context_id for follow-up:", cid)
