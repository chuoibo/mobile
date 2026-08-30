"""Storm -> recovery -> cooldown, on a live server."""

import json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = sys.argv[1]


def get(p):
    with urllib.request.urlopen(BASE + p, timeout=60) as r:
        return json.loads(r.read().decode())


def labels(b):
    ps = b["places"]
    return (sum(1 for p in ps if p["match"]["source"] == "ai"), len(ps))


def calls():
    return get("/__qa_probe/count")["post"]


out = {}
with ThreadPoolExecutor(max_workers=20) as ex:
    storm = list(ex.map(lambda _: get("/places"), range(20)))
out["storm_nhan_ai_moi_response"] = sorted(labels(b)[0] for b in storm)
out["storm_model_calls"] = calls()

time.sleep(2)  # let the one in-flight call land
r1 = get("/places")
out["ngay_sau_storm"] = {"ai": labels(r1)[0], "tong": labels(r1)[1], "calls": calls()}
r2 = get("/places")
out["lan_ke_tiep"] = {"ai": labels(r2)[0], "calls": calls()}

print("... doi 65s de kiem cooldown 60s that su het han ...", flush=True)
time.sleep(65)
r3 = get("/places")
out["sau_65s_cooldown"] = {
    "ai": labels(r3)[0],
    "calls": calls(),
    "ky_vong": "calls tang them 1 (hoi lai hang bi tu choi)",
}
r4 = get("/places")
out["ngay_sau_do"] = {
    "ai": labels(r4)[0],
    "calls": calls(),
    "ky_vong": "calls KHONG tang (lai vao cooldown)",
}
print(json.dumps(out, ensure_ascii=False, indent=2))
