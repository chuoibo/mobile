"""Drive one experiment against an already-running probe server."""
import json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE, MODE, N = sys.argv[1], sys.argv[2], int(sys.argv[3])

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read().decode())

def one(_):
    t = time.time()
    try:
        return {"ok": True, "body": get("/places"), "ms": int((time.time()-t)*1000)}
    except Exception as e:
        return {"ok": False, "err": f"{type(e).__name__}: {e}", "ms": int((time.time()-t)*1000)}

t0 = time.time()
if MODE == "par":
    with ThreadPoolExecutor(max_workers=N) as ex:
        results = list(ex.map(one, range(N)))
else:
    results = [one(i) for i in range(N)]
wall = int((time.time()-t0)*1000)

cnt = get("/__qa_probe/count")
ok = [r for r in results if r["ok"]]
bad = [r for r in results if not r["ok"]]

# Data correctness on the last good response.
summary = {}
if ok:
    places = ok[-1]["body"]["places"]
    summary = {
        "so_place": len(places),
        "co_score": sum(1 for p in places if isinstance(p["match"]["score"], int)),
        "source_ai": sum(1 for p in places if p["match"]["source"] == "ai"),
        "source_none": sum(1 for p in places if p["match"]["source"] == "none"),
        "refused_source": next(
            (p["match"]["source"] for p in places if p["id"] == cnt["refused_place"]), "KHONG-CO"
        ),
        "refused_score": next(
            (p["match"]["score"] for p in places if p["id"] == cnt["refused_place"]), None
        ),
        "verdict_none_khi_source_none": all(
            p["match"]["verdict"] is None for p in places if p["match"]["source"] == "none"
        ),
    }

print(json.dumps({
    "mode": MODE, "n": N, "http_ok": len(ok), "http_fail": len(bad),
    "MODEL_CALLS": cnt["post"], "wall_ms": wall,
    "loi": [b["err"] for b in bad][:3], "payload": summary,
}, ensure_ascii=False, indent=2))
